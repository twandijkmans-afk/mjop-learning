#!/usr/bin/env python3
"""
promote_canonical_batch1.py  (CANONIEKE PROMOTIE - deterministische Batch 1, batch1_v1)

Voert reports/promotion_readiness_plan_batch1_v1.json uit met de besluiten van de gebruiker
(2026-09-28), scenario SOURCE_EVIDENCE. Batch 1 cloud promotion gebruikt de reeds gevalideerde
Xpdf-derived PO values; er wordt geen PDF geparsed.

  --preflight   alle voorwaarden; schrijft niets
  --execute     preflight; history + pre-manifest; nieuwe canonieke lagen; post-manifest
  --verify      huidige bestanden == post-manifest en history == pre-manifest
  --rollback    herstel exact de pre-promotie-toestand uit history (hashes gecontroleerd)

Besluiten (DECISIONS): alle EXPLICIT_SOURCE_EVIDENCE-kandidaten uit de reviewed approval-set
(exacte sha256); 2 SAFE_EXACT_RELINK bevestigd op de nieuwe acties; 24 SOURCE_CHANGED_REVIEW en
4 AMBIGUOUS -> REVIEW_REQUIRED (niet gemigreerd); 58 NO_NEW_ACTION en 1 DUPLICATE_SKIP alleen historie;
3 SAME_EVIDENCE + DF-3 (2) herbevestigd als nieuwe records (oude SUPERSEDED); DF-1/DF-2 -> status
REVIEW_REQUIRED (bewaard, niet gebruikt). Oude accepts zonder expliciet besluit (EXACT_MATCH_CANDIDATE)
worden NIET overgenomen: de nieuwe acties houden hun eigen reviewstatus.
"""
import argparse
import copy
import glob
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import build_promoted_price_observations as bpp  # noqa: E402
import export_human_review_queue as hrq  # noqa: E402
import normalize_price_observations as npo  # noqa: E402
import prepare_promotion_review as ppr  # noqa: E402
import promote_deterministic_batch as pdb  # noqa: E402
import promotion_ledger as pl  # noqa: E402
import promotion_v2_dry_run as pv2  # noqa: E402
import promotion_v3_dry_run as pv3  # noqa: E402

TOOL_VERSION = "promote_canonical_batch1_v1.0.0"
APPROVED_SET_SHA256 = "e5f7836485106d4840b68c9c209effab31dd18359af06b12af60a4bb64d1461c"
REVIEWER = "twandijkmans"
HISTORY = os.path.join("data", "history", "pre_deterministic_promotion_batch1_v1")
STATE = os.path.join("data", "promotion_state_batch1_v1.json")
AFFECTED = ["data/extracted", "data/normalized", "data/verified", "data/price_observations", "data/comparability",
            "data/kengetallen", "data/review_decisions", "data/match_review_decisions"]
ACCEPT_MIGRATION = os.path.join("data", "review_decisions", "legacy_accept_migration_batch1_v1.json")
DECISIONS = {
    "source_evidence": "APPROVE ALL EXPLICIT_SOURCE_EVIDENCE candidates in the reviewed set",
    "accepts": {"SAFE_EXACT_RELINK": "CONFIRM_ON_NEW_ACTIONS", "SOURCE_CHANGED_REVIEW": "REVIEW_REQUIRED",
                "AMBIGUOUS": "REVIEW_REQUIRED", "NO_NEW_ACTION": "HISTORY_ONLY", "DUPLICATE_SKIP": "HISTORY_ONLY",
                "EXACT_MATCH_CANDIDATE": "NOT_MIGRATED_NO_EXPLICIT_DECISION"},
    "comparability": {"SAME_EVIDENCE": "RECONFIRM", "DF-3": "RECONFIRM_FAMILY", "DF-1": "REVIEW_REQUIRED",
                      "DF-2": "REVIEW_REQUIRED"},
    "decided_by": REVIEWER, "decision_date": "2026-09-28",
}
EXPECTED_KENGETALLEN = {("5211", "replace", "m1"): "AVAILABLE"}   # overige: INSUFFICIENT_DATA of afwezig -> rapport


class PromotionStop(RuntimeError):
    pass


def rel(root, p):
    return os.path.relpath(p, root).replace(os.sep, "/")


def file_hashes(root, dirs):
    out = {}
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(root, d, "**", "*"), recursive=True)):
            if os.path.isfile(p):
                out[rel(root, p)] = pdb.sha256_file(p)
    return out


# ------------------------------------------------------------------ preflight

def preflight(root):
    fails = []
    check = pdb.check_handoff(root)
    if not check["ok"]:
        fails.append("handoff --check FAIL: " + "; ".join(check["errors"][:3]))
    for name, mod in (("promotion v2", pv2), ("promotion v3", pv3), ("review package", ppr)):
        if mod.main(["--root", root, "--check"]) != 0:
            fails.append(f"{name} niet ACTUEEL")
    try:
        promoted = bpp.build_promoted(root)
    except bpp.PromotionError as e:
        fails.append(f"PO-promotie geweigerd: {e} {e.violations[:3]}")
        promoted = None
    approval = pdb.load_json(os.path.join(root, ppr.OUT["approval"]))
    if approval["approval_set_sha256"] != APPROVED_SET_SHA256 or \
            pdb.canonical_content_sha256({"candidates": approval["candidates"]}) != APPROVED_SET_SHA256:
        fails.append("approval_set_sha256 wijkt af van de goedgekeurde set")
    if os.path.exists(os.path.join(root, HISTORY)):
        fails.append(f"{HISTORY} bestaat al (promotie al uitgevoerd?)")
    store = pdb.load_json(os.path.join(root, pv2.DECISIONS_PATH))
    if hrq.store_invariant_errors(store):
        fails.append("human decision store invarianten: " + "; ".join(hrq.store_invariant_errors(store)))
    if promoted and len(promoted[0]["observations"]) != 404:
        fails.append("observation count != 404")
    return fails, promoted, approval


# ------------------------------------------------------------------ nieuwe lagen

def canonical_verified(normalized, approval, accepts_pkg, accept_review, now):
    verified = copy.deepcopy(normalized)
    els = {e["element_id"]: e for r in verified.values() for e in r["elements"]}
    acts = {a["action_id"]: a for r in verified.values() for a in r["maintenance_actions"]}
    note_sha = f"SOURCE_EVIDENCE approval set {APPROVED_SET_SHA256}"
    for c in approval["candidates"]:
        el = els[c["element_id"]]
        prov = copy.deepcopy((el.get("element_name") or {}).get("provenance"))
        el["material"] = {"original_value": c["material"]["original"], "normalized_value": c["material"]["normalized"],
                          "requires_human_review": False,
                          "human_verification": {"status": "accept", "reviewer": REVIEWER, "timestamp": now,
                                                 "notes": f"{note_sha}: EXPLICIT_SOURCE_EVIDENCE ({c['candidate_id']})"}}
        if prov:
            el["material"]["provenance"] = prov
    migrated, review_required, history = [], [], []
    for r in accepts_pkg["batch_confirmation"]["records"]:
        for aid in r["new_action_ids"]:
            a = acts[aid]
            a["requires_human_review"] = False
            a["action"]["human_verification"] = {"status": "accept", "reviewer": REVIEWER, "timestamp": now,
                                                 "notes": f"bevestigd oude accept {r['old_action_id']} (SAFE_EXACT_RELINK, "
                                                          "batchbesluit 2026-09-28)"}
            a["review_note"] = f"[accept {r['old_action_id']} bevestigd op nieuwe actie door {REVIEWER} op {now}]"
        migrated.append({"old_action_id": r["old_action_id"], "new_action_ids": r["new_action_ids"],
                         "result": "CONFIRM_ON_NEW_ACTIONS"})
    for h in accepts_pkg["human_review"]:
        ids = sorted({i for c in h["new_candidates"] for i in c["action_ids"]})
        for aid in ids:
            a = acts[aid]
            a["requires_human_review"] = True
            a["review_note"] = (f"[REVIEW_REQUIRED: oude accept {h['old_action_id']} niet gemigreerd "
                                f"({h['classification']}: {', '.join(h['changed_fields'])})]")
        review_required.append({"old_action_id": h["old_action_id"], "classification": h["classification"],
                                "new_action_ids": ids, "result": "REVIEW_REQUIRED"})
    for h in accepts_pkg["history_only"]:
        history.append({"old_action_id": h["old_action_id"], "classification": h["classification"],
                        "result": "HISTORY_ONLY"})
    not_migrated = [{"old_action_id": r["old_action_id"], "document_id": r["document_id"],
                     "new_action_ids": r.get("new_action_ids", []), "result": "NOT_MIGRATED_NO_EXPLICIT_DECISION"}
                    for r in accept_review_exact(accept_review)]
    return verified, {"migrated": migrated, "review_required": review_required, "history_only": history,
                      "exact_candidates_not_migrated": not_migrated}


def accept_review_exact(accept_review):
    return [a for a in accept_review["accepts"] if a["classification"] == "EXACT_MATCH_CANDIDATE"]


def decision_updates(store, pkg, comp, po, now):
    """Nieuwe ACTIVE records voor herbevestigde decisions; oude -> SUPERSEDED; DF-1/DF-2 -> REVIEW_REQUIRED."""
    store = copy.deepcopy(store)
    by_id = {r["decision_id"]: r for r in store["records"]}
    pairs = {pv2.pair_key(p): p for p in comp["pairs"]}
    obs = {o["observation_id"]: o for o in po["observations"]}
    reconfirm = [r["decision_id"] for r in pkg["same_evidence_batch"]["records"]]
    review_required = []
    for fam in pkg["material_only_families"]:
        ids = [r["decision_id"] for g in pkg["material_only_groups"] if g["group_id"] in fam["groups"] for r in g["records"]]
        if fam["pattern"] == "verified -> explicit_source":
            reconfirm += ids
        else:
            review_required += [(i, fam["family_id"]) for i in ids]
    next_n = max(int(r["decision_id"].split("-")[1]) for r in store["records"]) + 1
    comp_sha, norm_sha = None, None
    new_records = []
    for did in sorted(reconfirm):
        old = by_id[did]
        k = tuple(sorted(old["observation_ids"]))
        p = pairs[k]
        new_id = f"HDR-{next_n:05d}"
        next_n += 1
        ev = []
        for oid in p["observation_ids"]:
            src = next(r for r in obs[oid]["source_representations"] if r["role"] == "primary_financial_row")
            ev.append({"observation_id": oid, "document_id": obs[oid]["document_id"], "page": src["page"],
                       "line": src["line"], "source_text": src.get("source_text"), "reviewer_note": None})
        new_records.append({
            "decision_id": new_id, "pair_id": p["pair_id"], "observation_ids": p["observation_ids"],
            "candidate_key": p["candidate_key"], "system_class": p["class"],
            "system_reasons": {"hard_violations": p["hard_violations"], "unknown_reasons": p["unknown_reasons"],
                               "pair_caveats": p["pair_caveats"], "observation_caveats": p["observation_caveats"]},
            "decision": old["decision"],
            "decision_reason": (f"Herbevestiging van {did} bij deterministische promotie batch1_v1 (besluit "
                                f"{REVIEWER} 2026-09-28): zelfde bewijs of alleen de materiaalherkomst veranderd "
                                f"(verified -> explicit source). Oorspronkelijke reden: {old['decision_reason']}"),
            "decision_caveats": old["decision_caveats"], "reviewer": {"reviewer_id": REVIEWER, "reviewer_type": "human"},
            "reviewed_at": now, "rule_version": old["rule_version"], "input_hashes": "__FILLED__",
            "evidence": ev, "notes": "batchbesluit 2026-09-28", "supersedes": did, "status": "ACTIVE"})
        old["status"] = "SUPERSEDED"
    for did, fam in review_required:
        by_id[did]["status"] = "REVIEW_REQUIRED"
    store["records"].extend(new_records)
    return store, [r["decision_id"] for r in new_records], sorted(reconfirm), review_required


# ------------------------------------------------------------------ execute

def write_json_lf(path, obj):
    pdb.write_json(path, obj)


def execute(root, now=None):
    now = now or datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    fails, promoted, approval = preflight(root)
    if fails:
        raise PromotionStop("PREFLIGHT FAALT:\n- " + "\n- ".join(fails))
    po, link_info, normalized, _sim_verified, _ = promoted
    pre = file_hashes(root, AFFECTED)
    hist = os.path.join(root, HISTORY)
    for path in pre:
        dst = os.path.join(hist, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(root, path), dst)
    write_json_lf(os.path.join(hist, "pre_manifest.json"), {"files": pre, "tool_version": TOOL_VERSION})
    if file_hashes(os.path.join(root, HISTORY), AFFECTED) != pre:
        raise PromotionStop("history-kopie komt niet overeen met pre-manifest")

    accepts_pkg = pdb.load_json(os.path.join(root, ppr.OUT["accepts"]))
    new_records = {d: pdb.load_json(os.path.join(root, pdb.BATCH_DIR, f"{d}.json")) for d in pdb.EXPECTED_PASS}
    verified, accept_result = canonical_verified(normalized, approval, accepts_pkg,
                                                 pdb.classify_accepts(root, new_records), now)
    # PO-koppeling tegen de canonieke verified-laag (zelfde exacte koppeling), invarianten opnieuw
    old_po = pdb.load_json(os.path.join(root, pv2.PO_PATH))
    po, link_info = pv2.relink(old_po, verified, new_records)
    violations = bpp.invariant_violations(old_po, po, link_info)
    if violations:
        raise PromotionStop("PO-invarianten na canonieke koppeling: " + "; ".join(violations[:5]))
    po["promotion"] = dict(promoted[0]["promotion"], link_source="data/verified (canoniek, uit batch1_v1)")

    # 1. extracted / normalized / verified (oude bestanden staan in history)
    for layer, recs in (("extracted", new_records), ("normalized", normalized), ("verified", verified)):
        d = os.path.join(root, "data", layer)
        for f in glob.glob(os.path.join(d, "*.json")):
            os.remove(f)
        for doc, rec in sorted(recs.items()):
            if layer == "extracted":
                shutil.copyfile(os.path.join(root, pdb.BATCH_DIR, f"{doc}.json"), os.path.join(d, f"{doc}.json"))
            else:
                write_json_lf(os.path.join(d, f"{doc}.json"), rec)
    # 2. price observations -> normalized -> comparability
    write_json_lf(os.path.join(root, pv2.PO_PATH), po)
    norm = npo.normalize(root, os.path.join(root, pv2.PO_PATH))
    errs = npo.validate_output(norm, os.path.join(root, "schemas", "price_observation_normalized.schema.json"))
    if errs:
        raise PromotionStop(f"normalized PO schemafouten: {errs[:3]}")
    write_json_lf(os.path.join(root, pv2.NORM_PO_PATH), pv2.as_json(norm))
    comp = bc.build(root)
    errs = bc.validate_output(comp, os.path.join(root, "schemas", "comparability.schema.json"))
    if errs:
        raise PromotionStop(f"comparability schemafouten: {errs[:3]}")
    write_json_lf(os.path.join(root, pv2.COMP_PATH), pv2.as_json(comp))
    # 3. review state
    pkg = pdb.load_json(os.path.join(root, ppr.OUT["decisions"]))
    store_old = pdb.load_json(os.path.join(root, pv2.DECISIONS_PATH))
    store, new_ids, reconfirmed, review_required = decision_updates(store_old, pkg, pv2.as_json(comp), po, now)
    comp_sha = pdb.sha256_file(os.path.join(root, pv2.COMP_PATH))
    norm_sha = pdb.sha256_file(os.path.join(root, pv2.NORM_PO_PATH))
    for r in store["records"]:
        if r["input_hashes"] == "__FILLED__":
            r["input_hashes"] = {"comparability_output_sha256": comp_sha, "normalized_observations_sha256": norm_sha}
    inv = hrq.store_invariant_errors(store) + hrq.append_only_errors(store_old, store)
    if inv:
        raise PromotionStop(f"decision store invarianten: {inv[:3]}")
    write_json_lf(os.path.join(root, pv2.DECISIONS_PATH), store)
    write_json_lf(os.path.join(root, ACCEPT_MIGRATION), {
        "store": "legacy_accept_migration_batch1_v1", "append_only": True, "decisions": DECISIONS["accepts"],
        "decided_by": REVIEWER, "applied_at": now, **accept_result,
        "counts": {k: len(v) for k, v in accept_result.items()}})
    # 4. kengetallen via het bestaande --supersede-mechanisme
    r = subprocess.run([sys.executable, os.path.join(root, "scripts", "build_kengetallen.py"), "--supersede"],
                       cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise PromotionStop(f"build_kengetallen --supersede faalde: {r.stdout}{r.stderr}")
    kg = pdb.load_json(os.path.join(root, pv2.KG_PATH))
    post = file_hashes(root, AFFECTED)
    state = {
        "tool_version": TOOL_VERSION, "status": "PROMOTED", "promoted_at": now, "batch_id": pdb.BATCH_ID,
        "statement": bpp.STATEMENT, "decisions": DECISIONS, "approval_set_sha256": APPROVED_SET_SHA256,
        "handoff_manifest_sha256": pdb.sha256_file(os.path.join(root, pdb.BATCH_DIR, "manifest.json")),
        "history": HISTORY.replace(os.sep, "/"), "pre_manifest_sha256": pdb.sha256_file(os.path.join(hist, "pre_manifest.json")),
        "post_manifest": post,
        "summary": {
            "price_observations": len(po["observations"]), "amount_changes": 0,
            "link_counts": dict(sorted(Counter(i["link"] for i in link_info.values()).items())),
            "accepts": {k: len(v) for k, v in accept_result.items()},
            "decisions": {"reconfirmed_old": reconfirmed, "new_records": new_ids,
                          "review_required": sorted(d for d, _ in review_required)},
            "kengetallen": [{"candidate_key": k["candidate_key"], "status": k["status"], "value": k["value_display"],
                             "clusters": k["source_cluster_ids"], "insufficient_data_reasons": k["insufficient_data_reasons"]}
                            for k in sorted(kg["kengetallen"], key=lambda x: x["candidate_key"])],
        },
    }
    write_json_lf(os.path.join(root, STATE), state)
    return state


# ------------------------------------------------------------------ verify / rollback

def verify(root):
    state = pdb.load_json(os.path.join(root, STATE))
    errors = []
    cur = file_hashes(root, AFFECTED)
    if pl.states(root):
        # latere incoming-promoties: batch 1 is het beginpunt van de keten; de huidige toestand hoort
        # bij de laatste incoming-promotie (promotion_ledger.chain_errors controleert beide)
        errors += pl.chain_errors(root)
    elif cur != state["post_manifest"]:
        errors.append(f"huidige bestanden wijken af van post-manifest: "
                      f"{sorted(set(cur.items()) ^ set(state['post_manifest'].items()))[:5]}")
    hist = os.path.join(root, state["history"])
    pre = pdb.load_json(os.path.join(hist, "pre_manifest.json"))["files"]
    if file_hashes(hist, AFFECTED) != pre:
        errors.append("history wijkt af van pre-manifest")
    if pdb.sha256_file(os.path.join(hist, "pre_manifest.json")) != state["pre_manifest_sha256"]:
        errors.append("pre-manifest gewijzigd")
    return errors


def rollback(root):
    state = pdb.load_json(os.path.join(root, STATE))
    hist = os.path.join(root, state["history"])
    pre = pdb.load_json(os.path.join(hist, "pre_manifest.json"))["files"]
    for path in file_hashes(root, AFFECTED):
        if path not in pre:
            os.remove(os.path.join(root, path))
    for path, sha in pre.items():
        dst = os.path.join(root, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(hist, path), dst)
    if file_hashes(root, AFFECTED) != pre:
        raise PromotionStop("rollback: hashes komen niet overeen met pre-manifest")
    shutil.rmtree(hist)
    os.remove(os.path.join(root, STATE))
    for d in (os.path.dirname(hist), os.path.join(root, "data", "kengetallen", "history")):
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
    return "ROLLBACK OK"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("--preflight", "--execute", "--verify", "--rollback"):
        g.add_argument(f, action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.preflight:
            fails, _, _ = preflight(args.root)
            print("PREFLIGHT OK" if not fails else "PREFLIGHT FAALT:\n- " + "\n- ".join(fails))
            return 0 if not fails else 1
        if args.execute:
            state = execute(args.root)
            print(json.dumps(state["summary"], ensure_ascii=False, indent=1))
            return 0
        if args.verify:
            errs = verify(args.root)
            print("VERIFY OK" if not errs else "VERIFY FAALT: " + "; ".join(errs))
            return 0 if not errs else 1
        print(rollback(args.root))
        return 0
    except PromotionStop as e:
        print(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
