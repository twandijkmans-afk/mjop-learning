#!/usr/bin/env python3
"""
promotion_v3_dry_run.py  (PROMOTION v3 - cloud-only, evidence-based review + scenario-dry-run)

Voor batch1_v1, zonder xpdf en zonder canonieke wijzigingen:

  1. materiaalbewijs  elk klasse-A-materiaalverschil uit Promotion v2 (oude verified-afleiding
                      verdwenen) wordt getoetst aan de deterministische broncontext van batch1_v1:
                      elementnaam + locatie (element-niveau) en actietekst (conflictcontrole).
                      Alleen woorden uit vocabularies/material.json, exacte tokens (dezelfde
                      tokenisatie als MATERIAL_FROM_TEXT), geen nieuwe woorden, geen fuzzy:
                        EXPLICIT_SOURCE_EVIDENCE  element noemt precies één vocabulairemateriaal,
                                                  gelijk aan het oude materiaal; actietekst zonder
                                                  ander materiaal en zonder materiaalwissel ('>')
                        AMBIGUOUS_SOURCE_EVIDENCE aanwijzingen maar geen deterministische beslissing
                        OLD_DERIVATION_ONLY       geen bronbewijs in batch1_v1
  2. accepts          de accepts zonder EXACT_MATCH_CANDIDATE (review_required uit v2), per record
                      met bewijsvelden: SAFE_EXACT_RELINK / SOURCE_CHANGED_REVIEW / NO_NEW_ACTION /
                      DUPLICATE_SKIP / AMBIGUOUS - alleen als analysevoorstel.
  3. PO               build_promoted_price_observations (cloud-only, invarianten afgedwongen).
  4. scenario's       STRICT (alleen de bestaande MATERIAL_FROM_TEXT-regel) en SOURCE_EVIDENCE
                      (daarnaast alleen EXPLICIT_SOURCE_EVIDENCE, als simulatie op element-niveau):
                      normalized PO -> comparability -> human decisions -> kengetallen, met de
                      bestaande scripts, ongewijzigd.
  5. decisions        per record: SAME_EVIDENCE_SAME_DECISION_CANDIDATE / INPUT_CHANGED_MATERIAL_ONLY /
                      INPUT_CHANGED_OTHER / PAIR_NO_LONGER_EXISTS, met de exact gewijzigde velden.

Uitvoer: data/promotion_v3_dry_run/batch1_v1/ en reports/promotion_v3_batch1_v1.json
(+ reports/review/*_batch1_v1.json). UTF-8, LF, gesorteerd, geen tijdstempels.
"""
import argparse
import copy
import filecmp
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import build_kengetallen as bk  # noqa: E402
import build_promoted_price_observations as bpp  # noqa: E402
import normalize_price_observations as npo  # noqa: E402
import promote_deterministic_batch as pdb  # noqa: E402
import promotion_v2_dry_run as pv2  # noqa: E402

TOOL_VERSION = "promotion_v3_dry_run_v1.0.0"
OUT_DIR = os.path.join("data", "promotion_v3_dry_run", "batch1_v1")
REPORT = os.path.join("reports", "promotion_v3_batch1_v1.json")
REVIEW_DIR = os.path.join("reports", "review")
MATERIAL_REVIEW = os.path.join(REVIEW_DIR, "material_evidence_batch1_v1.json")
ACCEPT_REVIEW = os.path.join(REVIEW_DIR, "accepts_review_batch1_v1.json")
DECISION_REVIEW = os.path.join(REVIEW_DIR, "decisions_review_batch1_v1.json")
SCENARIOS = ("STRICT", "SOURCE_EVIDENCE")
EVIDENCE_SOURCE = "deterministic_source_text_evidence_simulation"


# ------------------------------------------------------------------ 1. materiaalbewijs

def material_vocab(root):
    return npo.load_vocab_utf8(os.path.join(root, "vocabularies"), "material")


def classify_material_evidence(old_norm, strict_norm, promoted_po, verified, vocab):
    """Alle klasse-A-gevallen (oud: materiaal uit verified-element; nieuw: veld leeg) afzonderlijk."""
    onb = {o["observation_id"]: o for o in old_norm["observations"]}
    pob = {o["observation_id"]: o for o in promoted_po["observations"]}
    elements = {e["element_id"]: e for rec in verified.values() for e in rec["elements"]}
    out, counts = [], Counter()
    for o in strict_norm["observations"]:
        oid = o["observation_id"]
        a, b = onb[oid]["material"], o["material"]
        if pv2.material_value(onb[oid]) == pv2.material_value(o):
            continue
        if not (a.get("material_source") == "verified_element" and b.get("material_not_derived_reason") ==
                "verified_material_empty"):
            continue   # alleen klasse A uit v2
        p = pob[oid]
        el = elements.get(p["element"]["element_id"]) or {}
        name = pdb.value_of(el.get("element_name")) or ""
        loc = pdb.value_of(el.get("location")) or ""
        action = p["action"]["action_text_original"] or ""
        el_toks = npo.material_tokens(f"{name} {loc}", vocab)
        act_toks = npo.material_tokens(action, vocab)
        el_norm = sorted({vocab[t] for t in el_toks})
        act_norm = sorted({vocab[t] for t in act_toks})
        old_orig, old_norm_v = a.get("material_original"), a.get("material_normalized")
        old_literal = bool(old_orig) and re.search(r"(?<![a-z0-9])" + re.escape(old_orig.lower()) + r"(?![a-z0-9])",
                                                  f"{name} {loc} {action}".lower()) is not None
        evidence = {"element_name": name, "element_location": loc or None, "action_text": action,
                    "element_provenance": ((el.get("element_name") or {}).get("provenance") or {}).get("text_fragment"),
                    "element_vocabulary_tokens": el_toks, "action_vocabulary_tokens": act_toks,
                    "old_material": {"original": old_orig, "normalized": old_norm_v},
                    "old_material_word_literally_in_source": old_literal}
        if len(el_norm) == 1 and el_norm[0] == old_norm_v and not (set(act_norm) - set(el_norm)) \
                and not npo.MATERIAL_CHANGE_MARKER.search(action):
            cls, why = "EXPLICIT_SOURCE_EVIDENCE", "elementcontext noemt precies dit vocabulairemateriaal"
        elif el_norm or act_norm or old_literal:
            if len(el_norm) > 1:
                why = "meerdere vocabulairematerialen in de elementcontext"
            elif el_norm and el_norm[0] != old_norm_v:
                why = "elementcontext noemt een ander materiaal dan de oude afleiding"
            elif set(act_norm) - set(el_norm):
                why = "actietekst noemt een (ander) materiaal - niet uit de actie afleiden"
            elif npo.MATERIAL_CHANGE_MARKER.search(action):
                why = "materiaalwissel in de actietekst"
            else:
                why = "oud materiaalwoord staat letterlijk in de bron maar niet in vocabularies/material.json " \
                      "(geen nieuwe woorden toegestaan)"
            cls = "AMBIGUOUS_SOURCE_EVIDENCE"
        else:
            cls, why = "OLD_DERIVATION_ONLY", "geen materiaalbewijs in de deterministische broncontext"
        counts[cls] += 1
        rec = {"observation_id": oid, "document_id": p["document_id"], "element_id": p["element"]["element_id"],
               "classification": cls, "reason": why, "evidence": evidence}
        if cls == "EXPLICIT_SOURCE_EVIDENCE":
            tok = next(t for t in el_toks if vocab[t] == el_norm[0])
            rec["promotion_candidate"] = {"material_original": tok, "material_normalized": el_norm[0],
                                          "status": "PROMOTION_CANDIDATE (niet canoniek)"}
        out.append(rec)
    return {"counts": {k: counts.get(k, 0) for k in ("EXPLICIT_SOURCE_EVIDENCE", "OLD_DERIVATION_ONLY",
                                                     "AMBIGUOUS_SOURCE_EVIDENCE")}, "records": out}


def evidence_overlay(verified, material_review):
    """SOURCE_EVIDENCE-simulatie: materiaal op element-niveau, alleen als ALLE klasse-A-observations
    van dat element EXPLICIT zijn met hetzelfde materiaal. Returns (verified_kopie, toegepast, overgeslagen)."""
    by_el = defaultdict(list)
    for r in material_review["records"]:
        by_el[r["element_id"]].append(r)
    sim = copy.deepcopy(verified)
    applied, skipped = [], []
    for doc, rec in sim.items():
        for el in rec["elements"]:
            recs = by_el.get(el["element_id"])
            if not recs:
                continue
            cands = {(r["promotion_candidate"]["material_original"], r["promotion_candidate"]["material_normalized"])
                     for r in recs if r["classification"] == "EXPLICIT_SOURCE_EVIDENCE"}
            if len(cands) == 1 and all(r["classification"] == "EXPLICIT_SOURCE_EVIDENCE" for r in recs):
                orig, norm = next(iter(cands))
                el["material"] = {"original_value": orig, "normalized_value": norm, "source": EVIDENCE_SOURCE}
                applied.append({"element_id": el["element_id"], "material": norm,
                                "observations": sorted(r["observation_id"] for r in recs)})
            elif cands:
                skipped.append({"element_id": el["element_id"], "reason": "niet alle observations EXPLICIT/gelijk"})
    return sim, applied, skipped


# ------------------------------------------------------------------ 2. accepts

def alnum(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def review_accepts(root, new_records):
    accepts = pdb.classify_accepts(root, new_records)
    old_ver = {d: {a["action_id"]: a for a in (pdb.load_canonical(root, "verified", d) or {}).get(
        "maintenance_actions", [])} for d in pdb.EXPECTED_DOCUMENTS}
    rows_by_doc = {d: pdb.new_rows(r) for d, r in new_records.items()}
    out, counts = [], Counter()
    for acc in accepts["accepts"]:
        if acc["classification"] == "EXACT_MATCH_CANDIDATE":
            continue
        doc = acc["document_id"]
        old = old_ver[doc][acc["old_action_id"]]
        page = old.get("source_page") or ((old.get("planned_year") or {}).get("provenance") or {}).get("page")
        amount = pdb.to_decimal(old.get("total_cost_as_stated"))
        ev = {"document_id": doc, "page": page, "action_text": pdb.value_of(old.get("action")),
              "quantity": pdb.dec_str(pdb.to_decimal(pdb.value_of(old.get("quantity")))),
              "unit": pdb.value_of(old.get("unit")), "amount": pdb.dec_str(amount),
              "planned_year": pdb.value_of(old.get("planned_year"))}
        new_ids, cand_rows = [], []
        if doc in pdb.EXPECTED_DUPLICATES:
            cls, why = "DUPLICATE_SKIP", "DOC-003 is duplicaat van DOC-002 (DREL-001)"
        elif acc["classification"] == "AMBIGUOUS":
            cls, why = "AMBIGUOUS", "meerdere identieke bronrijen"
            new_ids = acc.get("candidate_action_ids", [])
        elif amount is None or amount == 0:
            cls, why = "NO_NEW_ACTION", "oude actie zonder positief bedrag; de deterministische route maakt geen " \
                                        "actie van een nulbedrag (rows_without_positive_amount)"
        else:
            year, qty = ev["planned_year"], ev["quantity"]
            same = [r for r in rows_by_doc[doc] if r["page"] == page and r["quantity"] == qty
                    and any(y == year for y, _ in r["years"])]
            with_amount = [r for r in same if any(y == year and (a == amount) for y, a in r["years"])
                           or sum(a for _, a in r["years"]) == amount]
            cand_rows = with_amount or same
            year_differs = False
            if not cand_rows:
                # zelfde pagina + hoeveelheid + (jaar- of rij)bedrag, maar een ander jaar (bijv. oud = Stj vóór het venster)
                cand_rows = [r for r in rows_by_doc[doc] if r["page"] == page and r["quantity"] == qty and
                             (any(a == amount for _, a in r["years"]) or sum(a for _, a in r["years"]) == amount)]
                year_differs = bool(cand_rows)
            text_only = False
            if not cand_rows:
                # zelfde pagina + exact dezelfde actietekst (alleen spaties/leestekens genegeerd) + hoeveelheid +
                # eenheid; jaar en/of bedrag wijken af (bijv. afronding van jaarbedragen)
                cand_rows = [r for r in rows_by_doc[doc] if r["page"] == page and r["quantity"] == qty
                             and r["unit"] == pdb.squash(ev["unit"]) and alnum(r["action_text"]) == alnum(ev["action_text"])]
                text_only = bool(cand_rows)
            if not cand_rows:
                cls, why = "NO_NEW_ACTION", "geen jarenplan-rij met dezelfde pagina, hoeveelheid en jaar in batch1_v1 " \
                                            "(bijv. Bevindingen-bedrag buiten het venster)"
            elif len(cand_rows) > 1:
                cls, why = "AMBIGUOUS", "meerdere kandidaatrijen met dezelfde pagina/hoeveelheid/jaar"
            else:
                r = cand_rows[0]
                new_ids = r["action_ids"]
                unit_same = pdb.squash(ev["unit"]) == r["unit"]
                if with_amount and not year_differs and not text_only and unit_same and alnum(ev["action_text"]) == alnum(r["action_text"]):
                    cls, why = "SAFE_EXACT_RELINK", "zelfde pagina/hoeveelheid/eenheid/jaar/bedrag; actietekst " \
                                                    "verschilt alleen in spaties/leestekens"
                else:
                    diffs = ["jaar"] if year_differs else []
                    if text_only:
                        diffs = ["jaar/bedrag (geen exacte jaar- of bedragmatch)"]
                    elif not with_amount and not year_differs:
                        diffs.append("bedrag")
                    if not unit_same:
                        diffs.append("eenheid")
                    if alnum(ev["action_text"]) != alnum(r["action_text"]):
                        diffs.append("actietekst")
                    cls, why = "SOURCE_CHANGED_REVIEW", f"één kandidaatrij; verschil in: {', '.join(diffs)}"
                ev["new_row"] = {"action_text": r["action_text"], "quantity": r["quantity"], "unit": r["unit"],
                                 "years": [[y, pdb.dec_str(a)] for y, a in r["years"]], "block_id": r["block_id"]}
        counts[cls] += 1
        out.append({"old_action_id": acc["old_action_id"], "new_action_ids": sorted(new_ids), "classification": cls,
                    "reason": why, "evidence": ev, "proposal_only": True})
    order = ("SAFE_EXACT_RELINK", "SOURCE_CHANGED_REVIEW", "NO_NEW_ACTION", "DUPLICATE_SKIP", "AMBIGUOUS")
    return {"counts": {k: counts.get(k, 0) for k in order}, "total": len(out), "records": out,
            "note": "Analysevoorstel; geen accept wordt overgenomen of gemigreerd."}


# ------------------------------------------------------------------ 3. decisions

def diff_paths(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            out += diff_paths(a.get(k), b.get(k), f"{prefix}.{k}" if prefix else str(k))
        return out
    return [] if a == b else [prefix]


# identiteit/herkomst/koppelmetadata, geen inhoud: source_ref (bestandshashes), element_id (andere
# ID-reeks) en price.legacy_extracted_cost_years (cost_year van de gekoppelde OUDE verified-actie)
IDENTITY_ONLY = ("source_ref", "element.element_id", "price.legacy_extracted_cost_years")


def obs_content(o):
    o = pv2.strip_volatile(o)
    o = dict(o, source_ref=None, element=dict(o["element"], element_id=None))
    if isinstance(o.get("price"), dict):
        o["price"] = dict(o["price"], legacy_extracted_cost_years=None)
    return o


def link_metadata_changes(a, b):
    out = []
    if (a.get("price") or {}).get("legacy_extracted_cost_years") != (b.get("price") or {}).get("legacy_extracted_cost_years"):
        out.append("price.legacy_extracted_cost_years")
    if a["element"].get("element_id") != b["element"].get("element_id"):
        out.append("element.element_id")
    return out


def classify_decisions_v3(decisions, old_comp, new_comp, old_norm, new_norm):
    ob = {pv2.pair_key(p): p for p in old_comp["pairs"]}
    nb_ = {pv2.pair_key(p): p for p in new_comp["pairs"]}
    raw_o = {o["observation_id"]: o for o in old_norm["observations"]}
    raw_n = {o["observation_id"]: o for o in new_norm["observations"]}
    onb = {i: obs_content(o) for i, o in raw_o.items()}
    nnb = {i: obs_content(o) for i, o in raw_n.items()}
    out, counts = [], Counter()
    for r in decisions["records"]:
        k = tuple(sorted(r["observation_ids"]))
        rec = {"decision_id": r["decision_id"], "pair_id_metadata": r["pair_id"], "observation_ids": list(k),
               "decision": r["decision"]}
        if k not in nb_:
            cls, fields = "PAIR_NO_LONGER_EXISTS", {}
        else:
            fields = {oid: diff_paths(onb[oid], nnb[oid]) for oid in k}
            fields["pair"] = diff_paths(pv2.pair_content(ob.get(k, {})), pv2.pair_content(nb_[k]))
            fields = {x: v for x, v in fields.items() if v}
            obs_paths = [p for x, v in fields.items() if x != "pair" for p in v]
            pair_paths = fields.get("pair", [])
            reason_items = set()
            if k in ob:
                for f in ("hard_violations", "unknown_reasons", "pair_caveats"):
                    reason_items |= set(ob[k].get(f) or []) ^ set(nb_[k].get(f) or [])
                for side in ("a", "b"):
                    reason_items |= set((ob[k].get("observation_caveats") or {}).get(side) or []) ^ \
                        set((nb_[k].get("observation_caveats") or {}).get(side) or [])
            rec["link_metadata_changes"] = {oid: link_metadata_changes(raw_o[oid], raw_n[oid]) for oid in k
                                            if link_metadata_changes(raw_o[oid], raw_n[oid])}
            if not fields:
                cls = "SAME_EVIDENCE_SAME_DECISION_CANDIDATE"
            elif all(p.startswith("material") for p in obs_paths) and \
                    all(p in ("class", "hard_violations", "unknown_reasons", "pair_caveats") or p.startswith("checks.material")
                        or p.startswith("observation_caveats") for p in pair_paths) and \
                    all("MATERIAL" in x for x in reason_items):
                cls = "INPUT_CHANGED_MATERIAL_ONLY"
            else:
                cls = "INPUT_CHANGED_OTHER"
            rec["pair_reason_changes"] = sorted(reason_items)
        counts[cls] += 1
        rec.update(classification=cls, changed_fields=fields)
        out.append(rec)
    order = ("SAME_EVIDENCE_SAME_DECISION_CANDIDATE", "INPUT_CHANGED_MATERIAL_ONLY", "INPUT_CHANGED_OTHER",
             "PAIR_NO_LONGER_EXISTS")
    return {"counts": {k: counts.get(k, 0) for k in order}, "records": out,
            "note": "Identiteit = observation_id-set; pair_id alleen metadata. Niets gesuperseded of herschreven."}


# ------------------------------------------------------------------ 4. scenario's

def run_scenario(root, verified, promoted_po):
    with tempfile.TemporaryDirectory() as tmp:
        pv2.temp_root(root, tmp, verified, promoted_po)
        norm = pv2.as_json(npo.normalize(tmp, os.path.join(tmp, pv2.PO_PATH)))
        pdb.write_json(os.path.join(tmp, pv2.NORM_PO_PATH), norm)
        comp = pv2.as_json(bc.build(tmp))
        pdb.write_json(os.path.join(tmp, pv2.COMP_PATH), comp)
        kg = pv2.as_json(bk.content(bk.build(tmp, generated_at="-")))
        errors = {"normalized_price_observations": npo.validate_output(
                      norm, os.path.join(root, "schemas", "price_observation_normalized.schema.json")),
                  "comparability": bc.validate_output(comp, os.path.join(root, "schemas", "comparability.schema.json"))}
    return norm, comp, kg, errors


def kg_table(kg):
    return [{"candidate_key": k["candidate_key"], "kengetal_id": k["kengetal_id"], "status": k["status"],
             "value": k["value_display"], "clusters": k["source_cluster_ids"],
             "insufficient_data_reasons": k["insufficient_data_reasons"]}
            for k in sorted(kg["kengetallen"], key=lambda x: x["candidate_key"])]


def scenario_summary(name, root, promoted_po, link_info, norm, comp, kg, errors, old):
    old_po, old_norm, old_comp, old_kg, decisions = old
    po_cmp = pv2.compare_po(old_po, promoted_po, old_norm, norm, link_info)
    material = pv2.explain_material(old_norm, norm)
    codes = pv2.explain_codes(old_po, promoted_po, link_info)
    comp_cmp = pv2.compare_comparability(old_comp, comp)
    pairs = pv2.explain_pairs(old_comp, comp, po_cmp["per_observation"])
    kg_cmp = pv2.compare_kengetallen(old_kg, kg)
    kg_sem = pv2.explain_kengetallen(kg_cmp, old_kg, kg, material, codes)
    dec = classify_decisions_v3(decisions, old_comp, comp, old_norm, norm)
    return {
        "scenario": name,
        "material_unknown": sum(1 for o in norm["observations"] if o["material"]["material_status"] == "MATERIAL_UNKNOWN"),
        "material_status": dict(sorted(Counter(o["material"]["material_status"] for o in norm["observations"]).items())),
        "material_changes_vs_canonical": material["counts"],
        "amount_changes": len(po_cmp["amount_blocking"]),
        "po_categories": po_cmp["category_counts"],
        "comparability": comp_cmp["counts"], "comparability_unexplained": pairs["unexplained"],
        "source_clusters_identical": comp_cmp["source_clusters_identical"],
        "human_decisions": dec["counts"],
        "decisions_review_required": dec["counts"]["INPUT_CHANGED_MATERIAL_ONLY"] + dec["counts"]["INPUT_CHANGED_OTHER"]
        + dec["counts"]["PAIR_NO_LONGER_EXISTS"],
        "kengetallen_status": dict(sorted(Counter(k["status"] for k in kg["kengetallen"]).items())),
        "kengetallen": kg_table(kg),
        "kengetallen_semantic": kg_sem,
        "schema_errors": errors,
    }, dec


# ------------------------------------------------------------------ orchestratie

def build_all(root):
    promoted, link_info, normalized, verified, accept_sim = bpp.build_promoted(root)
    new_records = {d: pdb.load_json(os.path.join(root, pdb.BATCH_DIR, f"{d}.json")) for d in pdb.EXPECTED_PASS}
    old = (pdb.load_json(os.path.join(root, pv2.PO_PATH)), pdb.load_json(os.path.join(root, pv2.NORM_PO_PATH)),
           pdb.load_json(os.path.join(root, pv2.COMP_PATH)), pdb.load_json(os.path.join(root, pv2.KG_PATH)),
           pdb.load_json(os.path.join(root, pv2.DECISIONS_PATH)))

    strict = run_scenario(root, verified, promoted)
    material_review = classify_material_evidence(old[1], strict[0], promoted, verified, material_vocab(root))
    ev_verified, applied, skipped = evidence_overlay(verified, material_review)
    evidence = run_scenario(root, ev_verified, promoted)

    s_sum, s_dec = scenario_summary("STRICT", root, promoted, link_info, *strict, old)
    e_sum, e_dec = scenario_summary("SOURCE_EVIDENCE", root, promoted, link_info, *evidence, old)
    e_sum["evidence_overlay"] = {"elements_applied": len(applied), "observations_covered": sum(
        len(a["observations"]) for a in applied), "elements_skipped": len(skipped), "applied": applied,
        "skipped": skipped, "note": "simulatie: materiaal op het verified-element met source " + EVIDENCE_SOURCE +
        "; in de genormaliseerde PO verschijnt het als material_source verified_element"}
    accepts = review_accepts(root, new_records)

    blockers = []
    for s in (s_sum, e_sum):
        if s["amount_changes"]:
            blockers.append({"blocker": "amount_changed", "scenario": s["scenario"]})
        if s["comparability_unexplained"]:
            blockers.append({"blocker": "unexplained_comparability_change", "scenario": s["scenario"]})
        if any(s["schema_errors"].values()):
            blockers.append({"blocker": "schema_errors", "scenario": s["scenario"]})
        if not s["source_clusters_identical"]:
            blockers.append({"blocker": "source_clusters_changed", "scenario": s["scenario"]})
        if s["material_changes_vs_canonical"]["C_regression"]:
            blockers.append({"blocker": "material_regression", "scenario": s["scenario"]})
    promotion_prerequisites = [
        {"item": "human_decisions_review", "strict": s_sum["decisions_review_required"],
         "source_evidence": e_sum["decisions_review_required"],
         "note": "bestaande decisions zijn op andere invoer genomen; per record opnieuw bevestigen of superseden"},
        {"item": "accepts_review", "count": accepts["total"] - accepts["counts"]["DUPLICATE_SKIP"]
         - accepts["counts"]["NO_NEW_ACTION"], "note": "SAFE_EXACT_RELINK/SOURCE_CHANGED_REVIEW/AMBIGUOUS bevestigen"},
        {"item": "material_evidence_decision", "explicit_candidates": material_review["counts"]["EXPLICIT_SOURCE_EVIDENCE"],
         "note": "kiezen tussen STRICT en SOURCE_EVIDENCE (EXPLICIT als PROMOTION_CANDIDATE)"},
    ]
    layer = {"price_observations_promoted": promoted, "strict": strict, "source_evidence": evidence,
             "source_evidence_verified_overlay": applied}
    report = {
        "report": "promotion_v3_dry_run", "tool_version": TOOL_VERSION, "batch_id": pdb.BATCH_ID,
        "cloud_only_statement": bpp.STATEMENT,
        "price_observations": {"observations": len(promoted["observations"]),
                               "link_counts": promoted["promotion"]["link_counts"],
                               "amount_changes": s_sum["amount_changes"], "invariants": "alle geslaagd"},
        "material_evidence": {"counts": material_review["counts"], "review_file": MATERIAL_REVIEW.replace(os.sep, "/")},
        "accepts": {"counts": accepts["counts"], "total": accepts["total"], "review_file": ACCEPT_REVIEW.replace(os.sep, "/"),
                    "exact_match_candidates_v2": accept_sim["classification"]},
        "human_decisions": {"STRICT": s_dec["counts"], "SOURCE_EVIDENCE": e_dec["counts"],
                            "review_file": DECISION_REVIEW.replace(os.sep, "/")},
        "scenarios": {"STRICT": s_sum, "SOURCE_EVIDENCE": e_sum},
        "blockers": blockers,
        "promotion_prerequisites": promotion_prerequisites,
        "principles": ["geen xpdf, geen PDF-parsing", "geen canonieke wijziging", "geen fuzzy matching",
                       "geen nieuwe materiaalwoorden of businessregels", "accepts en decisions alleen als voorstel"],
    }
    reviews = {MATERIAL_REVIEW: material_review, ACCEPT_REVIEW: accepts,
               DECISION_REVIEW: {"STRICT": s_dec, "SOURCE_EVIDENCE": e_dec}}
    return layer, report, reviews


def write_outputs(root, layer, report, reviews):
    base = os.path.join(root, OUT_DIR)
    for d in ("extracted", "normalized", "verified", "price_observations", "comparability", "kengetallen"):
        if os.path.realpath(base) == os.path.realpath(os.path.join(root, "data", d)):
            raise SystemExit("weigering: canonieke map")
    if os.path.isdir(base):
        shutil.rmtree(base)
    files = {"price_observations_batch1_promoted.json": layer["price_observations_promoted"],
             "source_evidence/verified_material_overlay.json": layer["source_evidence_verified_overlay"]}
    for name in ("strict", "source_evidence"):
        norm, comp, kg, _ = layer[name]
        files[f"{name}/price_observations_batch1_normalized.json"] = norm
        files[f"{name}/comparability_batch1.json"] = comp
        files[f"{name}/kengetallen_batch1.json"] = kg
    manifest = {"tool_version": TOOL_VERSION, "files": {}}
    for rel, obj in files.items():
        p = os.path.join(base, *rel.split("/"))
        pdb.write_json(p, obj)
        manifest["files"][rel] = pdb.sha256_file(p)
    pdb.write_json(os.path.join(base, "manifest.json"), manifest)
    for rel, obj in reviews.items():
        pdb.write_json(os.path.join(root, rel), obj)
    report = dict(report, dry_run_layer={"path": OUT_DIR.replace(os.sep, "/"),
                                         "manifest_sha256": pdb.sha256_file(os.path.join(base, "manifest.json"))})
    pdb.write_json(os.path.join(root, REPORT), report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--check", action="store_true", help="herbouw in tmp en vergelijk met de gecommitte uitvoer")
    args = ap.parse_args(argv)
    layer, report, reviews = build_all(args.root)
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "reports"))
            write_outputs(tmp, layer, report, reviews)
            rels = [REPORT] + list(reviews)
            same = all(filecmp.cmp(os.path.join(tmp, r), os.path.join(args.root, r), shallow=False) for r in rels)
            cmp = filecmp.dircmp(os.path.join(tmp, OUT_DIR), os.path.join(args.root, OUT_DIR))
            diffs = []

            def walk(c, prefix=""):
                diffs.extend(prefix + x for x in c.left_only + c.right_only + c.diff_files)
                for n, sub in c.subdirs.items():
                    walk(sub, prefix + n + "/")
            walk(cmp)
            ok = same and not diffs
            print("ACTUEEL" if ok else f"NIET ACTUEEL: rapporten gelijk={same}, verschillen={diffs}")
            return 0 if ok else 1
    report = write_outputs(args.root, layer, report, reviews)
    print(f"PO: {report['price_observations']}")
    print(f"materiaal: {report['material_evidence']['counts']}")
    print(f"accepts: {report['accepts']['counts']}")
    print(f"decisions: {report['human_decisions']}")
    for s in SCENARIOS:
        print(s, report["scenarios"][s]["kengetallen_status"], report["scenarios"][s]["comparability"],
              "materiaal unknown:", report["scenarios"][s]["material_unknown"])
    print(f"blockers: {report['blockers']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
