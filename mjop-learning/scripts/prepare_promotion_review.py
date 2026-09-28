#!/usr/bin/env python3
"""
prepare_promotion_review.py  (compact reviewpakket + promotion readiness plan, batch1_v1)

Leidt uitsluitend af uit de gecommitte Promotion v3-uitvoer (scenario SOURCE_EVIDENCE, beleidsbesluit
2026-09-28) en de gevalideerde handoff-laag. Wijzigt geen canonieke data en neemt geen beslissingen:

  reports/review/source_evidence_approval_set_batch1_v1.json
      alle EXPLICIT_SOURCE_EVIDENCE-kandidaten (per element, met observations, materiaal, letterlijk
      bronfragment, pagina/block, classificatie en gebruikte regel) + samenvatting per materiaal en
      document + approval_set_sha256, zodat één besluit ("approve all EXPLICIT_SOURCE_EVIDENCE candidates
      in this reviewed set") exact naar deze set verwijst.
  reports/review/accepts_human_review_batch1_v1.json
      SAFE_EXACT_RELINK als batch-confirmation-kandidaat; SOURCE_CHANGED_REVIEW + AMBIGUOUS als
      inhoudelijke reviewgevallen (oud, nieuw, gewijzigde velden, bronbewijs, opties);
      NO_NEW_ACTION en DUPLICATE_SKIP alleen als historie.
  reports/review/decisions_review_package_batch1_v1.json
      SAME_EVIDENCE als batch-confirmation-kandidaat; MATERIAL_ONLY gegroepeerd per identiek
      wijzigingspatroon.
  reports/promotion_readiness_plan_batch1_v1.json
      canoniek promotieplan (niet uitgevoerd): history, nieuwe lagen, ID's, nieuwe/gesupersede
      records, rollback, hashes/manifests.

Gebruik:  python3 scripts/prepare_promotion_review.py [--check]
"""
import argparse
import filecmp
import os
import sys
import tempfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote_deterministic_batch as pdb  # noqa: E402
import promotion_v2_dry_run as pv2  # noqa: E402
import promotion_v3_dry_run as pv3  # noqa: E402

TOOL_VERSION = "prepare_promotion_review_v1.0.0"
SCENARIO = "SOURCE_EVIDENCE"
V3 = os.path.join("data", "promotion_v3_dry_run", "batch1_v1")
OUT = {
    "approval": os.path.join("reports", "review", "source_evidence_approval_set_batch1_v1.json"),
    "accepts": os.path.join("reports", "review", "accepts_human_review_batch1_v1.json"),
    "decisions": os.path.join("reports", "review", "decisions_review_package_batch1_v1.json"),
    "plan": os.path.join("reports", "promotion_readiness_plan_batch1_v1.json"),
}
MATERIAL_RULE = ("promotion_v3.EXPLICIT_SOURCE_EVIDENCE: exact token uit vocabularies/material.json in elementnaam "
                 "of -locatie van batch1_v1 (tokenisatie gelijk aan MATERIAL_FROM_TEXT), precies één materiaal, "
                 "gelijk aan de oude afleiding; actietekst zonder ander materiaal en zonder materiaalwissel ('>')")
APPROVAL_STATEMENT = "approve all EXPLICIT_SOURCE_EVIDENCE candidates in this reviewed set"


def load(root, rel):
    return pdb.load_json(os.path.join(root, rel))


# ------------------------------------------------------------------ 1. approval-set

def approval_set(root):
    review = load(root, pv3.MATERIAL_REVIEW)
    records = {d: pdb.load_json(os.path.join(root, pdb.BATCH_DIR, f"{d}.json")) for d in pdb.EXPECTED_PASS}
    elements = {e["element_id"]: e for r in records.values() for e in r["elements"]}
    by_el = defaultdict(list)
    for r in review["records"]:
        if r["classification"] == "EXPLICIT_SOURCE_EVIDENCE":
            by_el[r["element_id"]].append(r)
    cands = []
    for eid in sorted(by_el):
        rs = by_el[eid]
        el = elements[eid]
        prov = (el.get("element_name") or {}).get("provenance") or {}
        pc = rs[0]["promotion_candidate"]
        cands.append({
            "candidate_id": f"SEC-{eid}", "document_id": rs[0]["document_id"], "element_id": eid,
            "observation_ids": sorted(r["observation_id"] for r in rs),
            "material": {"original": pc["material_original"], "normalized": pc["material_normalized"]},
            "source_fragment": prov.get("text_fragment"), "page": prov.get("page"), "block_id": prov.get("block_id"),
            "extraction_rule": prov.get("extraction_rule"),
            "element_name": rs[0]["evidence"]["element_name"], "element_location": rs[0]["evidence"]["element_location"],
            "action_texts": sorted({r["evidence"]["action_text"] for r in rs}),
            "classification": "EXPLICIT_SOURCE_EVIDENCE", "material_rule": MATERIAL_RULE,
            "old_material_basis": "verified_element (oude extractie/LLM-afleiding)",
        })
    by_mat = Counter()
    by_doc = Counter()
    by_doc_mat = defaultdict(Counter)
    for c in cands:
        n = len(c["observation_ids"])
        by_mat[c["material"]["normalized"]] += n
        by_doc[c["document_id"]] += n
        by_doc_mat[c["document_id"]][c["material"]["normalized"]] += n
    content = {"candidates": cands}
    return {
        "set_id": "SOURCE_EVIDENCE_APPROVAL_SET_batch1_v1", "tool_version": TOOL_VERSION, "scenario": SCENARIO,
        "policy": "materiaal alleen bij EXPLICIT_SOURCE_EVIDENCE; geen OLD_DERIVATION_ONLY/AMBIGUOUS, geen fuzzy, "
                  "geen vocabulaire-uitbreiding (besluit 2026-09-28)",
        "approval_statement": APPROVAL_STATEMENT,
        "approval_set_sha256": pv3.pdb.canonical_content_sha256(content),
        "material_vocabulary_sha256": pdb.sha256_file(os.path.join(root, "vocabularies", "material.json")),
        "source_review_file": pv3.MATERIAL_REVIEW.replace(os.sep, "/"),
        "source_review_sha256": pdb.sha256_file(os.path.join(root, pv3.MATERIAL_REVIEW)),
        "summary": {"elements": len(cands), "observations": sum(by_mat.values()),
                    "by_material": dict(sorted(by_mat.items())), "by_document": dict(sorted(by_doc.items())),
                    "by_document_material": {d: dict(sorted(v.items())) for d, v in sorted(by_doc_mat.items())}},
        "approval": {"status": "PENDING_HUMAN_DECISION", "decided_by": None, "decided_at": None,
                     "note": "Nog geen canonieke wijziging. Een besluit verwijst naar approval_set_sha256."},
        **content,
    }


# ------------------------------------------------------------------ 2. accepts

def accepts_package(root):
    review = load(root, pv3.ACCEPT_REVIEW)
    records = {d: pdb.load_json(os.path.join(root, pdb.BATCH_DIR, f"{d}.json")) for d in pdb.EXPECTED_PASS}
    rows_by_doc = {d: pdb.new_rows(r) for d, r in records.items()}

    def row_view(r):
        return {"action_ids": r["action_ids"], "action_text": r["action_text"], "quantity": r["quantity"],
                "unit": r["unit"], "years": [[y, pdb.dec_str(a)] for y, a in r["years"]], "block_id": r["block_id"],
                "element_ids": sorted(x for x in r["element_ids"] if x)}

    batch, human, history = [], [], []
    for r in review["records"]:
        ev = r["evidence"]
        cls = r["classification"]
        if cls == "SAFE_EXACT_RELINK":
            batch.append({"old_action_id": r["old_action_id"], "new_action_ids": r["new_action_ids"], "evidence": ev,
                          "reason": r["reason"]})
        elif cls in ("NO_NEW_ACTION", "DUPLICATE_SKIP"):
            history.append({"old_action_id": r["old_action_id"], "classification": cls, "reason": r["reason"],
                            "treatment": "niet migreren; oude accept blijft alleen als historie"})
        else:
            if cls == "AMBIGUOUS" and not r["new_action_ids"]:
                cands = [row_view(x) for x in rows_by_doc.get(ev["document_id"], [])
                         if x["page"] == ev["page"] and x["quantity"] == ev["quantity"]
                         and any(y == ev["planned_year"] for y, _ in x["years"])]
            else:
                ids = set(r["new_action_ids"])
                cands = [row_view(x) for x in rows_by_doc.get(ev["document_id"], []) if ids & set(x["action_ids"])]
            changed = r["reason"].split("verschil in: ")[-1].split(", ") if "verschil in:" in r["reason"] else \
                ["meerdere kandidaatrijen"]
            options = (["CONFIRM_ON_NEW_ACTIONS: oude accept geldt voor de nieuwe actie(s)",
                        "REJECT: niet overnemen; nieuwe actie volgt de normale review",
                        "DEFER: later beoordelen"] if cls == "SOURCE_CHANGED_REVIEW" else
                       ["CHOOSE_CANDIDATE: kies expliciet één kandidaatrij (action_ids)",
                        "APPLY_TO_ALL_IDENTICAL: alleen als de kandidaten identiek zijn",
                        "REJECT: niet overnemen", "DEFER: later beoordelen"])
            human.append({"case_id": f"ACC-{r['old_action_id']}", "old_action_id": r["old_action_id"],
                          "classification": cls, "old": ev, "new_candidates": cands, "changed_fields": changed,
                          "source_evidence": {"page": ev["page"], "document_id": ev["document_id"],
                                              "new_block_ids": sorted({c["block_id"] for c in cands if c["block_id"]})},
                          "options": options, "decision": None})
    return {"tool_version": TOOL_VERSION, "source_review_file": pv3.ACCEPT_REVIEW.replace(os.sep, "/"),
            "counts": {"batch_confirmation_candidates": len(batch), "human_review_cases": len(human),
                       "history_only": len(history), "total": len(batch) + len(human) + len(history)},
            "batch_confirmation": {"statement": "confirm SAFE_EXACT_RELINK accepts in this set", "records": batch,
                                   "set_sha256": pdb.canonical_content_sha256(batch)},
            "human_review": sorted(human, key=lambda x: x["case_id"]),
            "history_only": sorted(history, key=lambda x: x["old_action_id"])}


# ------------------------------------------------------------------ 3. decisions

def material_basis(norm_obs, overlay_obs, evidence_cls):
    m = norm_obs["material"]
    oid = norm_obs["observation_id"]
    if oid in overlay_obs:
        return f"explicit_source:{m.get('material_normalized')}"
    if m.get("material_status") == "MATERIAL_FROM_TEXT":
        return f"material_from_text:{(m.get('material_from_text') or {}).get('normalized_value')}"
    if m.get("material_source") == "verified_element":
        return f"verified:{m.get('material_normalized') or ('original=' + str(m.get('material_original')))}"
    if evidence_cls.get(oid):
        return f"unknown[{evidence_cls[oid]}]"
    return "unknown"


def generic_transition(t):
    """'verified:concrete -> unknown[OLD_DERIVATION_ONLY]' -> 'verified -> unknown[OLD_DERIVATION_ONLY]'."""
    a, b = t.split(" -> ")
    if a == b or (a.startswith("material_from_text") and b.startswith("material_from_text")):
        return "unchanged"
    return f"{a.split(':')[0]} -> {b.split(':')[0]}"


def decisions_package(root):
    review = load(root, pv3.DECISION_REVIEW)[SCENARIO]
    old_norm = {o["observation_id"]: o for o in load(root, pv2.NORM_PO_PATH)["observations"]}
    new_norm = {o["observation_id"]: o for o in load(root, os.path.join(V3, "source_evidence",
                                                                         "price_observations_batch1_normalized.json"))["observations"]}
    old_comp = {pv2.pair_key(p): p for p in load(root, pv2.COMP_PATH)["pairs"]}
    new_comp = {pv2.pair_key(p): p for p in load(root, os.path.join(V3, "source_evidence", "comparability_batch1.json"))["pairs"]}
    overlay = {o for a in load(root, os.path.join(V3, "source_evidence", "verified_material_overlay.json"))
               for o in a["observations"]}
    ev_cls = {r["observation_id"]: r["classification"] for r in load(root, pv3.MATERIAL_REVIEW)["records"]}
    same, groups = [], defaultdict(list)
    for r in review["records"]:
        k = tuple(r["observation_ids"])
        entry = {"decision_id": r["decision_id"], "observation_ids": list(k), "decision": r["decision"],
                 "pair_id_metadata": r["pair_id_metadata"]}
        if r["classification"] == "SAME_EVIDENCE_SAME_DECISION_CANDIDATE":
            same.append(entry)
            continue
        trans = sorted(f"{material_basis(old_norm[o], set(), {})} -> {material_basis(new_norm[o], overlay, ev_cls)}"
                       for o in k)
        a, b = old_comp.get(k, {}), new_comp.get(k, {})
        effect = f"{a.get('class')} -> {b.get('class')}"
        key = (r["classification"], tuple(trans), effect, r["decision"])
        entry.update(old_class=a.get("class"), new_class=b.get("class"),
                     pair_reason_changes=r.get("pair_reason_changes", []))
        groups[key].append(entry)
    out = []
    for i, (key, members) in enumerate(sorted(groups.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))), start=1):
        cls, trans, effect, decision = key
        out.append({"group_id": f"DG-{i:02d}", "classification": cls, "decisions": len(members),
                    "material_transition_per_observation": list(trans), "comparability_effect": effect,
                    "existing_human_decision": decision,
                    "pair_reason_changes": sorted({x for m in members for x in m["pair_reason_changes"]}),
                    "records": members,
                    "options": ["RECONFIRM_GROUP: bestaande beslissing opnieuw bevestigen op de nieuwe invoer",
                                "REVIEW_INDIVIDUALLY", "SUPERSEDE_WITH_OTHER_DECISION"]})
    families = defaultdict(list)
    for g in out:
        fam = sorted({generic_transition(t) for t in g["material_transition_per_observation"]} - {"unchanged"})
        g["family"] = " + ".join(fam)
        families[g["family"]].append(g)
    fam_out = [{"family_id": f"DF-{i}", "pattern": fam, "decisions": sum(g["decisions"] for g in gs),
                "groups": [g["group_id"] for g in gs],
                "comparability_effects": dict(sorted(Counter(g["comparability_effect"] for g in gs
                                                             for _ in range(g["decisions"])).items())),
                "existing_human_decisions": dict(sorted(Counter(g["existing_human_decision"] for g in gs
                                                                for _ in range(g["decisions"])).items())),
                "options": ["RECONFIRM_FAMILY", "REVIEW_BY_GROUP", "REVIEW_INDIVIDUALLY"]}
               for i, (fam, gs) in enumerate(sorted(families.items(), key=lambda kv: -sum(g["decisions"] for g in kv[1])),
                                             start=1)]
    return {"tool_version": TOOL_VERSION, "scenario": SCENARIO,
            "counts": {"same_evidence_batch": len(same), "material_only_decisions": sum(g["decisions"] for g in out),
                       "material_only_families": len(fam_out), "material_only_groups": len(out), "other": review["counts"]["INPUT_CHANGED_OTHER"],
                       "pair_no_longer_exists": review["counts"]["PAIR_NO_LONGER_EXISTS"]},
            "same_evidence_batch": {"statement": "reconfirm SAME_EVIDENCE decisions in this set", "records": same,
                                    "set_sha256": pdb.canonical_content_sha256(same)},
            "material_only_families": fam_out,
            "material_only_groups": out,
            "note": "Identiteit = observation_id-set; pair_id alleen metadata. Geen beslissing genomen."}


# ------------------------------------------------------------------ 4. plan + 5. kengetallen

def kengetallen_check(root):
    kg = load(root, os.path.join(V3, "source_evidence", "kengetallen_batch1.json"))
    return [{"candidate_key": k["candidate_key"], "status": k["status"], "value": k["value_display"],
             "clusters": k["source_cluster_ids"], "insufficient_data_reasons": k["insufficient_data_reasons"]}
            for k in sorted(kg["kengetallen"], key=lambda x: x["candidate_key"])]


def readiness_plan(root, approval, accepts, decisions):
    canon = ["data/extracted", "data/normalized", "data/verified"]
    return {
        "plan_id": "CANONICAL_PROMOTION_PLAN_batch1_v1", "tool_version": TOOL_VERSION, "status": "NOT_EXECUTED",
        "scenario": SCENARIO,
        "preconditions": [
            "promote_deterministic_batch.py --check: HANDOFF GELDIG",
            "build_promoted_price_observations: 404 observations, 0 bedragverschillen, alle invarianten",
            f"materiaalbesluit op approval_set_sha256 {approval['approval_set_sha256']}",
            f"accept-batch ({accepts['counts']['batch_confirmation_candidates']}) + "
            f"{accepts['counts']['human_review_cases']} reviewgevallen beslist",
            f"decision-batch ({decisions['counts']['same_evidence_batch']}) + "
            f"{decisions['counts']['material_only_families']} patroonfamilies "
            f"({decisions['counts']['material_only_groups']} groepen) beslist",
            "git-tag pre-promotion op de uitgangscommit",
        ],
        "A_to_history": {
            "target": "data/history/pre_deterministic_promotion_batch1_v1/<oorspronkelijk pad>",
            "files": [f"{d}/DOC-0{i:02d}.json" for d in canon for i in range(1, 11)] + [
                "data/price_observations/price_observations_batch1.json",
                "data/price_observations/price_observations_batch1_normalized.json",
                "data/comparability/comparability_batch1.json",
                "data/kengetallen/kengetallen_batch1.json (via build_kengetallen --supersede -> data/kengetallen/history/)",
                "reports/review_batch1.xlsx (blijft staan; bron van de oude accepts, alleen historie)"],
            "rule": "kopie + sha256-manifest vóór elke vervanging; niets verwijderen zonder history",
        },
        "B_new_canonical": {
            "data/extracted": "9 PASS-documenten uit batch1_v1 (DOC-003 niet: DUPLICATE_SKIP, oude kopie alleen in history)",
            "data/normalized": "normalize_batch.normalize_record op batch1_v1 (external_element_coding DOC-004)",
            "data/verified": "normalized + goedgekeurde materialen (approval-set) + bevestigde accepts, met provenance",
            "data/price_observations/price_observations_batch1.json": "build_promoted_price_observations (cloud-only)",
            "data/price_observations/price_observations_batch1_normalized.json": "normalize_price_observations",
            "data/comparability/comparability_batch1.json": "build_comparability",
            "data/kengetallen/kengetallen_batch1.json": "build_kengetallen --supersede",
            "data/price_observations/document_relations.json": "ongewijzigd",
        },
        "C_ids": {
            "kept": ["document_id (registry)", "observation_id (404, positioneel uit xpdf)", "relation_id (DREL-*)",
                     "decision_id van bestaande records (historie)", "kengetal-semantiek via candidate_key"],
            "new": ["element_id/action_id: batch1_v1-nummering; mapping oud->nieuw uit de accept- en "
                    "materiaalreview wordt als bestand vastgelegd", "pair_id: opnieuw genummerd (alleen metadata)",
                    "kengetal_id: kan wijzigen als het materiaal in de id wijzigt"],
        },
        "D_new_review_records": [
            "één beleidsrecord voor de materiaal-approval-set (approval_set_sha256, besluitnemer, tijdstip)",
            "human_verification op nieuwe acties voor bevestigde accepts (met verwijzing naar old_action_id)",
            "nieuwe HDR-records voor opnieuw bevestigde of gewijzigde comparability-decisions "
            "(nieuwe input_hashes, supersedes = oud decision_id)",
        ],
        "E_active_to_superseded": {
            "records": sorted(r["decision_id"] for g in decisions["material_only_groups"] for r in g["records"])
            + sorted(r["decision_id"] for r in decisions["same_evidence_batch"]["records"]),
            "rule": "alleen ACTIVE -> SUPERSEDED bij aanmaak van het vervangende record (append-only store)",
        },
        "F_rollback": [
            "promotie als één commit; rollback = git revert van die commit",
            "daarnaast herstel uit data/history/... met verificatie tegen het pre-manifest (sha256 per bestand)",
            "kengetallen: bestaande --supersede-historie terugzetten",
            "human decision store: append-only; rollback zet alleen de SUPERSEDED-status van de nieuwe records terug",
        ],
        "G_hashes_manifests": {
            "before": ["pre_promotion_manifest.json: sha256 van elk bestand in data/extracted, normalized, verified, "
                       "price_observations, comparability, kengetallen, review_decisions, match_review_decisions",
                       "batch1_v1 manifest.json sha256 (v1.1)", "approval_set_sha256 + accept/decision set_sha256"],
            "after": ["post_promotion_manifest.json met dezelfde velden + verwijzing naar het pre-manifest",
                      "kengetallen inputs (normalized/comparability/decisions/regels) via build_kengetallen",
                      "alle JSON UTF-8 + LF; hashes over repository-bytes"],
        },
    }


def build(root):
    approval = approval_set(root)
    accepts = accepts_package(root)
    decisions = decisions_package(root)
    plan = readiness_plan(root, approval, accepts, decisions)
    plan["kengetallen_source_evidence"] = kengetallen_check(root)
    return {"approval": approval, "accepts": accepts, "decisions": decisions, "plan": plan}


def write(root, outputs):
    for key, rel in OUT.items():
        pdb.write_json(os.path.join(root, rel), outputs[key])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    outputs = build(args.root)
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, outputs)
            ok = all(filecmp.cmp(os.path.join(tmp, rel), os.path.join(args.root, rel), shallow=False)
                     for rel in OUT.values())
        print("ACTUEEL" if ok else "NIET ACTUEEL")
        return 0 if ok else 1
    write(args.root, outputs)
    a, c, d = outputs["approval"], outputs["accepts"], outputs["decisions"]
    print(f"approval-set: {a['summary']['elements']} elementen / {a['summary']['observations']} observations")
    print(f"accepts: {c['counts']}")
    print(f"decisions: {d['counts']}")
    for k in outputs["plan"]["kengetallen_source_evidence"]:
        print(k["candidate_key"], k["status"], k["value"], k["insufficient_data_reasons"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
