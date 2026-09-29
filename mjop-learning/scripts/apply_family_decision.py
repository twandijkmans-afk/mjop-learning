#!/usr/bin/env python3
"""
apply_family_decision.py - één EXPLICIET menselijk familiebesluit toepassen op exact opgesomde paren.

Een familiebesluit is een JSON-bestand dat een mens invult op basis van reports/review/comparability_review_v2.json:

    {
      "review_package_sha256": "<sha256 van comparability_review_v2.json zoals bekeken>",
      "review_family_id": "RF-5211-...",
      "family_input_sha256": "<family_input_sha256 uit dat pakket>",
      "pair_ids": ["PAIR-00632", "PAIR-00634"],          # exact; deelverzameling van de familie mag
      "decision": "COMPARABLE_WITH_CAVEATS",             # COMPARABLE | COMPARABLE_WITH_CAVEATS | NOT_COMPARABLE | UNKNOWN
      "decision_reason": "...",
      "decision_caveats": ["PRICE_LEVEL_DIFFERENCE"],
      "reviewer": "twandijkmans",
      "reviewed_at": "2026-09-29T12:00:00Z",
      "notes": null,
      "acknowledged_kengetal_effects": []                # verplicht exact als het besluit een AVAILABLE
    }                                                    # kengetal laat verdwijnen of laat ontstaan

Veiligheid (geen silent batch approval):
  - het bekeken pakket moet byte-gelijk zijn aan reports/review/comparability_review_v2.json (sha256);
  - het pakket wordt opnieuw opgebouwd uit de HUIDIGE invoer; comparability en genormaliseerde observations
    moeten gelijk zijn aan die van het pakket, en de familie moet nog bestaan met exact dezelfde
    family_input_sha256 (anders vervalt het besluit: invoer, paren of bestaande beslissingen gewijzigd);
  - alleen de opgesomde pair_ids, elk lid van die familie; geen dynamische matching;
  - per paar één nieuw ACTIVE HDR-record (schema + store-invarianten + append-only gecontroleerd); een bestaand
    ACTIVE of REVIEW_REQUIRED record van dat paar wordt SUPERSEDED en via 'supersedes' gekoppeld;
  - het besluit wordt bewaard in data/review_decisions/family_decisions/RFD-NNNNN.json (audit trail);
  - kengetallen worden herbouwd met de bestaande regels (oude versie in history); price observations,
    comparability en document_relations blijven byte-gelijk;
  - uitvoering als canonieke ketenschakel (scripts/canonical_change.py): rollback van de laatste schakel.

    python scripts/apply_family_decision.py --decision pad/naar/besluit.json [--dry-run]
    python scripts/apply_family_decision.py --rollback RFD-00001
"""
import argparse
import copy
import glob
import json
import os
import shutil
import sys
import tempfile

import jsonschema

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import canonical_change as cc  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import export_human_review_queue as hrq  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402
import record_relation_decision as rrd  # noqa: E402

FAMILY_DIR = os.path.join("data", "review_decisions", "family_decisions")
REQUIRED = ("review_package_sha256", "review_family_id", "family_input_sha256", "pair_ids", "decision",
            "decision_reason", "decision_caveats", "reviewer", "reviewed_at")


class FamilyDecisionError(RuntimeError):
    pass


def next_family_decision_id(root):
    n = len(glob.glob(os.path.join(root, FAMILY_DIR, "RFD-*.json")))
    hist = glob.glob(os.path.join(root, pl.HISTORY_ROOT, "RFD-*"))
    return f"RFD-{max(n, len(hist)) + 1:05d}"


def validate(root, decision):
    """Alle controles; returns (familie uit het HUIDIGE pakket, paren uit comparability). Schrijft niets."""
    missing = [k for k in REQUIRED if k not in decision]
    if missing:
        raise FamilyDecisionError(f"besluit mist velden: {missing}")
    if decision["decision"] not in hrq.DECISION_OPTIONS:
        raise FamilyDecisionError(f"ongeldige beslissing {decision['decision']!r}; toegestaan: {hrq.DECISION_OPTIONS}")
    if not str(decision["decision_reason"]).strip() or not str(decision["reviewer"]).strip():
        raise FamilyDecisionError("decision_reason en reviewer zijn verplicht (menselijk besluit)")
    pids = decision["pair_ids"]
    if not isinstance(pids, list) or not pids or len(set(pids)) != len(pids):
        raise FamilyDecisionError("pair_ids moet een niet-lege lijst zonder dubbelen zijn")
    pkg_path = os.path.join(root, crv.OUT_JSON)
    if not os.path.exists(pkg_path) or pl.sha256_file(pkg_path) != decision["review_package_sha256"]:
        raise FamilyDecisionError("reviewpakket gewijzigd of ontbreekt t.o.v. het bekeken pakket (sha256)")
    with open(pkg_path, encoding="utf-8") as f:
        seen = json.load(f)
    fresh = crv.build(root)
    for k in ("comparability_sha256", "normalized_observations_sha256", "document_relations_sha256",
              "comparability_rules_version"):
        if fresh["inputs"][k] != seen["inputs"][k]:
            raise FamilyDecisionError(f"invoer gewijzigd sinds het pakket ({k}); besluit vervallen")
    fam_seen = next((f for f in seen["families"] if f["review_family_id"] == decision["review_family_id"]), None)
    fam = next((f for f in fresh["families"] if f["review_family_id"] == decision["review_family_id"]), None)
    if fam_seen is None or fam is None:
        raise FamilyDecisionError(f"familie {decision['review_family_id']} bestaat niet (meer)")
    if not (fam_seen["family_input_sha256"] == fam["family_input_sha256"] == decision["family_input_sha256"]):
        raise FamilyDecisionError("family_input_sha256 wijkt af: paren, observations of bestaande beslissingen zijn "
                                  "gewijzigd; besluit vervallen, opnieuw beoordelen")
    outside = sorted(set(pids) - set(fam["pair_ids"]))
    if outside:
        raise FamilyDecisionError(f"pair_ids buiten de familie: {outside}")
    comp = pr.load(os.path.join(root, crv.COMP))
    pairs = {p["pair_id"]: p for p in comp["pairs"]}
    fam_pairs = {p["pair_id"]: p for p in fam["pairs"]}
    for pid in pids:
        p = pairs.get(pid)
        if p is None or p["observation_ids"] != fam_pairs[pid]["observation_ids"]:
            raise FamilyDecisionError(f"{pid}: paar niet (meer) gelijk aan het pakket")
    # effect op AVAILABLE kengetallen (bestaande regels): nooit stil - moet exact bevestigd zijn
    effect = crv.kengetal_effect(crv.Context(root), [pairs[pid]["observation_ids"] for pid in pids],
                                 decision["decision"])
    ack = sorted(decision.get("acknowledged_kengetal_effects") or [])
    if ack != effect["acknowledgement_required"]:
        raise FamilyDecisionError(
            f"kengetal-effect niet (exact) bevestigd: vereist acknowledged_kengetal_effects = "
            f"{effect['acknowledgement_required']} (verloren AVAILABLE: {effect['available_kengetallen_lost']}, "
            f"nieuw AVAILABLE: {effect['new_available_kengetallen']}); opgegeven: {ack}")
    return fam, [pairs[pid] for pid in pids]


def _evidence(norm, oid):
    p = crv.primary(norm[oid])
    return {"observation_id": oid, "document_id": norm[oid]["document_id"], "page": p.get("page"),
            "line": p.get("line"), "sheet": p.get("sheet"), "row": p.get("row"),
            "source_text": p.get("source_text"), "reviewer_note": None}


def build_records(root, decision, fam, pairs, fdid, store):
    comp_sha = pl.sha256_file(os.path.join(root, crv.COMP))
    norm_sha = pl.sha256_file(os.path.join(root, crv.NORM))
    norm = {o["observation_id"]: o for o in pr.load(os.path.join(root, crv.NORM))["observations"]}
    new = copy.deepcopy(store)
    n = max((int(r["decision_id"].split("-")[1]) for r in new["records"]), default=0)
    by_id = {r["decision_id"]: r for r in new["records"]}
    created = []
    for p in pairs:
        pair_set = frozenset(p["observation_ids"])
        prev = [r for r in new["records"] if frozenset(r["observation_ids"]) == pair_set
                and r["status"] in ("ACTIVE", "REVIEW_REQUIRED")]
        active = [r for r in prev if r["status"] == "ACTIVE"]
        supersede = active[0] if active else (max(prev, key=lambda r: r["decision_id"]) if prev else None)
        n += 1
        rec = {
            "decision_id": f"HDR-{n:05d}", "pair_id": p["pair_id"], "observation_ids": p["observation_ids"],
            "candidate_key": p["candidate_key"], "system_class": p["class"],
            "system_reasons": {"hard_violations": p["hard_violations"], "unknown_reasons": p["unknown_reasons"],
                               "pair_caveats": p["pair_caveats"], "observation_caveats": p["observation_caveats"]},
            "decision": decision["decision"], "decision_reason": decision["decision_reason"],
            "decision_caveats": list(decision["decision_caveats"]),
            "reviewer": {"reviewer_id": decision["reviewer"], "reviewer_type": "human"},
            "reviewed_at": decision["reviewed_at"], "rule_version": bc.RULES_VERSION,
            "input_hashes": {"comparability_output_sha256": comp_sha, "normalized_observations_sha256": norm_sha},
            "evidence": [_evidence(norm, i) for i in p["observation_ids"]],
            "notes": decision.get("notes"),
            "supersedes": supersede["decision_id"] if supersede else None,
            "status": "ACTIVE",
            "family_decision": {"family_decision_id": fdid, "review_family_id": fam["review_family_id"],
                                "review_package_sha256": decision["review_package_sha256"],
                                "family_input_sha256": decision["family_input_sha256"]},
        }
        if supersede:
            by_id[supersede["decision_id"]]["status"] = "SUPERSEDED"
        new["records"].append(rec)
        by_id[rec["decision_id"]] = rec
        created.append(rec["decision_id"])
    schema = json.load(open(os.path.join(root, "schemas", "human_decision_record.schema.json"), encoding="utf-8"))
    errs = [e.message for e in jsonschema.Draft7Validator(schema).iter_errors(new)]
    errs += hrq.store_invariant_errors(new) + hrq.append_only_errors(store, new)
    if errs:
        raise FamilyDecisionError(f"decision store ongeldig na toepassen: {errs[:5]}")
    return new, created


def make_apply(decision, fdid, now):
    def apply_fn(root):
        fixed = {rel: pl.sha256_file(os.path.join(root, rel))
                 for rel in (pr.PO_PATH, pr.NORM_PO_PATH, pr.COMP_PATH, rrd.RELATIONS_PATH)}
        fam, pairs = validate(root, decision)
        store_path = os.path.join(root, pr.DECISIONS_PATH)
        store = pr.load(store_path)
        new, created = build_records(root, decision, fam, pairs, fdid, store)
        with open(store_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(new, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        record = dict(decision, family_decision_id=fdid, applied_decision_ids=created,
                      superseded_decision_ids=sorted(r["supersedes"] for r in new["records"]
                                                     if r["decision_id"] in created and r["supersedes"]))
        pr.write_json(os.path.join(root, FAMILY_DIR, f"{fdid}.json"), record)
        kg = rrd.supersede_kengetallen(root, now, expect_unchanged=False)
        for rel, sha in fixed.items():
            if pl.sha256_file(os.path.join(root, rel)) != sha:
                raise FamilyDecisionError(f"INVARIANT: {rel} gewijzigd")
        return {"family_decision_id": fdid, "review_family_id": fam["review_family_id"],
                "candidate_group": fam["candidate_group"], "decision": decision["decision"],
                "pair_ids": decision["pair_ids"], "applied_decision_ids": created,
                "superseded_decision_ids": record["superseded_decision_ids"], "kengetallen": kg}
    return apply_fn


def apply(root, decision, now=None):
    now = now or pr.now_utc()
    validate(root, decision)                                   # vóór de snapshot: duidelijke weigering
    fdid = next_family_decision_id(root)
    return cc.apply_change(root, fdid, "family_decision", make_apply(decision, fdid, now),
                           {"family_decision": dict(decision, family_decision_id=fdid)}, now=now)


def dry_run(root, decision):
    with tempfile.TemporaryDirectory() as tmp:
        for rel in pr.SIMULATION_COPY + ("reports/review",):
            s, d = os.path.join(root, rel), os.path.join(tmp, rel)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            elif os.path.isfile(s):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
        return apply(tmp, decision, now="2000-01-01T00:00:00Z")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        if args.rollback:
            print(cc.rollback(root, args.rollback))
            return 0
        if not args.decision:
            ap.error("--decision is verplicht")
        with open(args.decision, encoding="utf-8") as f:
            decision = json.load(f)
        state = (dry_run if args.dry_run else apply)(root, decision)
        print(json.dumps(state["summary"], ensure_ascii=False, indent=2))
        print(("DRY-RUN OK " if args.dry_run else "TOEGEPAST ") + state["promotion_id"])
        return 0
    except (FamilyDecisionError, cc.ChangeError) as e:
        print(f"GEWEIGERD: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
