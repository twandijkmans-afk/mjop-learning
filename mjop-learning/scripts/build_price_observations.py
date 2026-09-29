#!/usr/bin/env python3
"""
build_price_observations.py  (bronlaag: RAW PDF + VERIFIED -> PRICE OBSERVATIONS)

Bouwt de price observation source layer voor batch 1.

Kernregel (uit de bronanalyses, zie data/price_observations/document_relations.json):
  1 rij in "Overzicht NN - Jarenplan (Gedetailleerd)" met een bedrag > 0
  binnen het getoonde venster = 1 price observation.

  - Jaarplan- en Bevindingen-regels zijn GEEN extra observations. Worden ze
    aan een jarenplan-rij gekoppeld, dan staan ze als extra
    source_representation bij die observation. Lukt koppelen niet, dan komen
    ze in unlinked_section_rows (status UNKNOWN) - nooit als nieuwe observation.
  - Een duplicate_source-document (DOC-003, XLS van DOC-002) levert geen
    observations op.
  - Stj en Cy komen letterlijk uit de bron; een lege Cy blijft null.
  - Prijspeil alleen als het document een 'Prijspeil'-veld heeft; nooit
    afgeleid uit inspectie- of printdatum.
  - cost_year uit de extractie wordt alleen als legacy_extracted_cost_years
    bewaard, niet als prijsjaar.
  - unit_price_calculated = total_as_stated / quantity (Decimal), alleen bij
    een deelbare, genormaliseerde eenheid en een sluitend rijtotaal. Bij
    MULTIPLE_EXECUTIONS is dat een verhouding over het rijtotaal, NIET een
    prijs per uitvoering (calculated_unit_price_basis zegt dat expliciet).
  - Afhankelijkheid: alleen vastgestelde relatietypen. 'Geen afhankelijkheid
    gevonden' (NO_DEPENDENCY_FOUND) betekent NIET onafhankelijk.

Geen matching, geen vergelijkbaarheid, geen kengetallen.

Gebruik:
    python scripts/build_price_observations.py
    python scripts/build_price_observations.py --pdftotext /pad/naar/pdftotext
"""
import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_batch import NON_DIVISIBLE_UNITS, load_vocab, to_decimal  # noqa: E402
import mjop_source_sections as src  # noqa: E402

BUILDER_VERSION = "price_observation_source_layer_v1"
LINK_THRESHOLD = 0.8

DEPENDENCY_RANK = {"NO_DEPENDENCY_FOUND": 0, "POSSIBLY_DEPENDENT": 1, "UNKNOWN": 2}


def dec_str(d):
    return None if d is None else str(d)


def norm_text(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _v(x):
    return x.get("value", x.get("original_value")) if isinstance(x, dict) else x


def _amount(v):
    """Totaal uit de extractie; DOC-007 bevat soms '€ 1.233 (totaal; ...)'."""
    if v is None:
        return None
    return to_decimal(str(v).split(" (")[0])


# --------------------------------------------------------------------------
# Observations uit jarenplan-rijen
# --------------------------------------------------------------------------

def build_row_observation(doc, row, doc_ctx, unit_lookup):
    total, amounts, recon = src.reconcile_row_amounts(row)
    scope = src.total_scope(len(amounts), recon)
    qty = to_decimal(row["quantity_as_stated"])
    unit_original = row["unit_original"]
    unit_normalized = unit_lookup.get(unit_original.strip().lower()) if unit_original else None

    calc, calc_basis, calc_reason = None, None, None
    if scope == "UNKNOWN":
        calc_reason = "total_scope UNKNOWN (rijtotaal sluit niet of ontbreekt)"
    elif not qty or qty <= 0:
        calc_reason = "hoeveelheid ontbreekt of is 0"
    elif unit_normalized is None:
        calc_reason = f"eenheid '{unit_original}' niet in vocabularies/unit.json"
    elif unit_normalized in NON_DIVISIBLE_UNITS:
        calc_reason = "niet-deelbare eenheid (stelpost/lump_sum)"
    else:
        calc = (total / qty).quantize(Decimal("0.01"))
        calc_basis = ("row_total_single_execution_in_window" if scope == "ONE_EXECUTION"
                      else "row_total_over_multiple_executions_in_window")

    el = row["element"]
    page, line = row["page"], row["line"]
    obs_id = f"PO-{doc['document_id']}-P{page:03d}-L{line:03d}"
    review_reasons = []
    provenance_gaps = []
    if el is None:
        provenance_gaps.append("elementregel niet op dezelfde pagina (mogelijk vorige pagina)")
        review_reasons.append("element_context_missing")
    if scope == "UNKNOWN":
        review_reasons.append("total_scope_unknown")
    if unit_normalized is None:
        review_reasons.append("unit_not_normalized")

    return {
        "observation_id": obs_id,
        "document_id": doc["document_id"],
        "source_file": {"relative_path": doc["relative_path"], "sha256": doc["sha256"], "file_type": doc["file_type"]},
        "element": {
            "element_code_original": el["code"] if el else None,
            "element_description_original": el["description"] if el else None,
            "element_location_original": (el["location"] or None) if el else None,
            "element_candidate_previous_page": row["element_candidate_previous_page"],
            "element_context_source": row.get("element_context_source"),
            "element_description_first_line": el.get("description_first_line") if el else None,
            "element_description_continuation_lines": list(el.get("continuation_lines", [])) if el else [],
            "element_description_excluded_tokens": list(el.get("excluded_tokens", [])) if el else [],
            "element_id": None,
            "element_code_internal": None,
        },
        "action": {
            "action_text_original": row["action_text"],
            "gebrek_or_location_text_original": row["gebrek_or_location_text"] or None,
            "action_normalized": None,
            "action_normalization_basis": None,
        },
        "unit_original": unit_original,
        "unit_normalized": unit_normalized,
        "quantity_as_stated": row["quantity_as_stated"],
        "quantity_value": dec_str(qty),
        "total_as_stated": row["total_as_stated"],
        "total_value": dec_str(total),
        "amount_reconciliation": recon,
        "total_scope": scope,
        "occurrences_in_window": len(amounts),
        "annual_amounts": {y: dec_str(v) for y, v in sorted(amounts.items())},
        "planned_years": sorted(amounts),
        "execution_window_start": int(row["window"][0]) if row["window"] else None,
        "execution_window_end": int(row["window"][1]) if row["window"] else None,
        "cycle_start_year": int(row["stj"]) if row["stj"] and row["stj"].isdigit() else None,
        "cycle_start_year_as_stated": row["stj"],
        "cycle_length_years": int(row["cy"]) if row["cy"] and row["cy"].isdigit() else None,
        "cycle_length_as_stated": row["cy"],
        "price_type": "calculated" if calc is not None else None,
        "unit_price_literal": None,
        "unit_price_calculated": dec_str(calc),
        "calculated_unit_price_basis": calc_basis,
        "calculation_method": "total_value / quantity_value (Decimal, 2 decimalen)" if calc is not None else None,
        "calculated_unit_price_not_computed_reason": calc_reason,
        "price_level_date": doc_ctx["price_level_date"],
        "price_level_basis": doc_ctx["price_level_basis"],
        "vat_basis": doc_ctx["vat_basis"],
        "vat_text": doc_ctx["vat_text"],
        "vat_rate_text": doc_ctx["vat_rate_text"],
        "indexation_statement": doc_ctx["indexation_statement"],
        "legacy_extracted_cost_years": [],
        "source_representations": [{
            "role": "primary_financial_row",
            "section": "JARENPLAN_GEDETAILLEERD",
            "document_id": doc["document_id"],
            "page": page,
            "line": line,
            "continuation_lines": row["continuation_lines"],
            "element_line": {"page": el["page"], "line": el["line"]} if el else None,
            "source_text": row["raw_line"],
        }],
        "provenance_status": "incomplete" if provenance_gaps else "complete",
        "provenance_gaps": provenance_gaps,
        "extraction_link": {"action_ids": [], "method": None, "score": None},
        "dependency_status": "NO_DEPENDENCY_FOUND",
        "relation_ids": [],
        "document_relation_ids": [],
        "review_status": "not_reviewed",
        "requires_human_review": bool(review_reasons),
        "review_reasons": review_reasons,
        "extraction_review": None,
    }


# --------------------------------------------------------------------------
# Koppeling aan bestaande extracted/verified acties (heuristisch, gemarkeerd)
# --------------------------------------------------------------------------

def link_verified_actions(observations, verified):
    """Koppelt verified maintenance_actions aan observations van hetzelfde
    document. Heuristiek (niet uit de bron zelf): gelijke hoeveelheid EN een
    extractietotaal dat gelijk is aan het rijtotaal of aan een jaarbedrag zijn
    verplicht (acties zonder positief totaal horen bij rijen zonder bedrag in
    het venster en worden niet gekoppeld); score = tekstgelijkenis actie +
    0.2 x gelijkenis element + 0.3 (bedrag) + 0.1 als planned_year gelijk is
    aan Stj of een uitvoeringsjaar. Beste scores eerst; per (observation,
    planned_year) hoogstens één actie. Methode en score worden bewaard."""
    if not verified:
        return
    elements = {e["element_id"]: e for e in verified.get("elements", [])}
    pairs = []
    for a in verified.get("maintenance_actions", []):
        q = to_decimal(_v(a.get("quantity")))
        at = norm_text(_v(a.get("action")))
        py = _v(a.get("planned_year"))
        tot = _amount(a.get("total_cost_as_stated"))
        ed = norm_text(_v((elements.get(a.get("element_id")) or {}).get("element_type")))
        if tot is None or tot <= 0:
            continue
        for o in observations:
            if q is None or o["quantity_value"] is None or Decimal(o["quantity_value"]) != q:
                continue
            amts = [Decimal(x) for x in o["annual_amounts"].values()]
            if not (o["total_value"] is not None and tot == Decimal(o["total_value"]) or tot in amts):
                continue
            s = difflib.SequenceMatcher(None, at, norm_text(o["action"]["action_text_original"])).ratio()
            s += 0.2 * difflib.SequenceMatcher(None, ed, norm_text(o["element"]["element_description_original"])).ratio()
            s += 0.3
            if py is not None and (py == o["cycle_start_year"] or str(py) in o["annual_amounts"]):
                s += 0.1
            if s >= LINK_THRESHOLD:
                pairs.append((s, a["action_id"], o["observation_id"], str(py)))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    by_id = {o["observation_id"]: o for o in observations}
    actions = {a["action_id"]: a for a in verified.get("maintenance_actions", [])}
    used_actions, used_slots = set(), set()
    for s, aid, oid, py in pairs:
        if aid in used_actions or (oid, py) in used_slots:
            continue
        used_actions.add(aid)
        used_slots.add((oid, py))
        o = by_id[oid]
        o["extraction_link"]["action_ids"].append(aid)
        prev = o["extraction_link"]["score"]
        o["extraction_link"]["score"] = round(s, 3) if prev is None else min(prev, round(s, 3))
        o["extraction_link"]["method"] = "heuristic_quantity_text_amount_v1"

    for o in observations:
        ids = sorted(o["extraction_link"]["action_ids"])
        o["extraction_link"]["action_ids"] = ids
        if not ids:
            o["review_reasons"].append("no_extraction_link")
            o["requires_human_review"] = True
            continue
        acts = [actions[i] for i in ids]
        el_ids = sorted({a.get("element_id") for a in acts})
        o["element"]["element_id"] = el_ids[0] if len(el_ids) == 1 else None
        codes = sorted({((elements.get(e) or {}).get("element_code") or {}).get("normalized_value") for e in el_ids} - {None})
        o["element"]["element_code_internal"] = codes[0] if len(codes) == 1 else None
        norm = sorted({(a.get("action") or {}).get("normalized_value") for a in acts} - {None})
        if len(norm) == 1:
            o["action"]["action_normalized"] = norm[0]
            srcs = sorted({(a.get("action") or {}).get("normalization_source", "vocabulary") for a in acts
                           if (a.get("action") or {}).get("normalized_value")})
            o["action"]["action_normalization_basis"] = "; ".join(srcs)
        else:
            o["review_reasons"].append("action_not_normalized" if not norm else "conflicting_action_normalization")
            o["requires_human_review"] = True
        o["legacy_extracted_cost_years"] = sorted({a.get("cost_year") for a in acts if a.get("cost_year") is not None})
        hv = [((a.get("action") or {}).get("human_verification") or {}).get("status") for a in acts]
        o["extraction_review"] = {
            "any_requires_human_review": any(a.get("requires_human_review") for a in acts),
            "human_verification_statuses": sorted({h for h in hv if h}),
            "review_notes": sorted({a.get("review_note") for a in acts if a.get("review_note")}),
        }


# --------------------------------------------------------------------------
# Jaarplan / Bevindingen als extra bronweergave
# --------------------------------------------------------------------------

def link_section_rows(observations, section_rows, section):
    """Koppelt een Jaarplan- of Bevindingen-regel met bedrag > 0 aan een
    observation van hetzelfde document: gelijke hoeveelheid, gelijk bedrag in
    de jaarkolom van dat jaar, en (indien beide bekend) gelijke elementcode.
    Bij meer dan één kandidaat met dezelfde score: niet koppelen (ambigu)."""
    linked, unlinked = [], []
    for r in section_rows:
        amt = to_decimal(r["amount_as_stated"]) if r.get("amount_as_stated") else None
        if not amt:
            continue  # regels zonder bedrag leveren geen financiele bronweergave
        qty = to_decimal(r["quantity_as_stated"])
        code = (r.get("element") or {}).get("code") if section == "BEVINDINGEN" else r.get("element_code")
        cands = []
        for o in observations:
            if o["quantity_value"] is None or Decimal(o["quantity_value"]) != qty:
                continue
            if o["annual_amounts"].get(r["year"]) is None or Decimal(o["annual_amounts"][r["year"]]) != amt:
                continue
            oc = o["element"]["element_code_original"]
            if code and oc and code != oc:
                continue
            score = difflib.SequenceMatcher(None, norm_text(r["action_text"]),
                                            norm_text(o["action"]["action_text_original"])).ratio()
            cands.append((round(score, 3), o))
        cands.sort(key=lambda c: -c[0])
        rep = {
            "role": "context_inspection" if section == "BEVINDINGEN" else "first_year_plan_view",
            "section": section,
            "page": r["page"],
            "line": r["line"],
            "year": r["year"],
            "source_text": r["raw_line"],
        }
        if section == "BEVINDINGEN":
            rep.update(defect=r.get("defect"), tag_location=r.get("tag_location"),
                       inspection_scores_raw=r.get("inspection_scores_raw"))
        if cands and (len(cands) == 1 or cands[0][0] > cands[1][0]):
            rep["match_text_similarity"] = cands[0][0]
            cands[0][1]["source_representations"].append(rep)
            linked.append(rep)
        else:
            rep.update(status="UNKNOWN", reason=("geen jarenplan-rij met gelijke hoeveelheid, "
                                                  "elementcode en bedrag in dit jaar" if not cands
                                                  else "meerdere even goede kandidaten (ambigu)"),
                       amount_as_stated=r["amount_as_stated"], quantity_as_stated=r["quantity_as_stated"],
                       action_text=r["action_text"], element=r.get("element") or r.get("element_code"))
            unlinked.append(rep)
    return linked, unlinked


# --------------------------------------------------------------------------
# Afhankelijkheden (alleen vastgestelde relatietypen)
# --------------------------------------------------------------------------

def _row_key(o):
    return (o["element"]["element_code_original"], norm_text(o["element"]["element_description_original"]),
            norm_text(o["element"]["element_location_original"]), norm_text(o["action"]["action_text_original"]),
            norm_text(o["action"]["gebrek_or_location_text_original"]), o["quantity_value"], o["unit_original"],
            tuple(sorted(o["annual_amounts"].items())))


def build_relations(observations_by_doc, doc_relations):
    relations = []

    def add(rtype, status, obs, reason):
        rid = f"OREL-{len(relations) + 1:04d}"
        relations.append({"relation_id": rid, "type": rtype, "dependency_status": status,
                          "observation_ids": [o["observation_id"] for o in obs], "reason": reason})
        for o in obs:
            o["relation_ids"].append(rid)
            if DEPENDENCY_RANK[status] > DEPENDENCY_RANK[o["dependency_status"]]:
                o["dependency_status"] = status

    # 1. identieke bronrijen binnen één document: betekenis onbekend
    for doc_id, obs in observations_by_doc.items():
        groups = defaultdict(list)
        for o in obs:
            groups[_row_key(o)].append(o)
        for g in groups.values():
            if len(g) > 1:
                add("identical_source_rows_same_document", "UNKNOWN", g,
                    "Bronrijen zijn in alle gelezen kenmerken identiek; of dit twee plekken of één dubbele invoer is, blijkt niet uit de bron.")

    # 2. rijrelaties binnen vastgestelde documentrelaties
    for rel in doc_relations:
        if rel["type"] == "version_of_same_mjop":
            a, b = rel["document_ids"]
            for x in observations_by_doc.get(a, []):
                for y in observations_by_doc.get(b, []):
                    if (x["element"]["element_code_original"] and
                            x["element"]["element_code_original"] == y["element"]["element_code_original"] and
                            x["quantity_value"] == y["quantity_value"] and x["unit_original"] == y["unit_original"] and
                            norm_text(x["action"]["action_text_original"]) == norm_text(y["action"]["action_text_original"])):
                        add("version_counterpart", "POSSIBLY_DEPENDENT", [x, y],
                            f"{rel['relation_id']}: zelfde elementcode, actietekst, hoeveelheid en eenheid in een andere versie van hetzelfde MJOP.")
        elif rel["type"] == "subplans_same_complex":
            a, b = rel["document_ids"]
            for x in observations_by_doc.get(a, []):
                for y in observations_by_doc.get(b, []):
                    if (x["quantity_value"] == y["quantity_value"] and x["unit_original"] == y["unit_original"] and
                            x["annual_amounts"] == y["annual_amounts"] and
                            norm_text(x["action"]["action_text_original"]) == norm_text(y["action"]["action_text_original"])):
                        add("same_post_in_related_subplan", "POSSIBLY_DEPENDENT", [x, y],
                            f"{rel['relation_id']}: zelfde actie, hoeveelheid, eenheid en jaarbedragen in een ander deelplan van hetzelfde complex.")
    return relations


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def build_document(doc, pages, verified, unit_lookup, document_relation_ids, jarenplan_vat_fallback=False):
    """Price observations van één document uit zijn pdftotext-pagina's (xpdf 4.06, -table).
    Returns (entry-velden, observations, ongekoppelde sectieregels, checks). Gebruikt door build()
    en door de incoming pipeline (zelfde regels, geen afwijkingen)."""
    doc_id = doc["document_id"]
    sections = src.classify_sections(pages)
    ctx = src.parse_document_context(pages, jarenplan_vat_fallback=jarenplan_vat_fallback)
    rows, jaarplan_rows, bev_rows = [], [], []
    carry = None
    totaal_object = None
    for pno, sec in sections:
        text = pages[pno - 1]
        if sec == "JARENPLAN":
            r, carry, t = src.parse_jarenplan_page(text, pno, carry)
            rows.extend(r)
            if t is not None:
                totaal_object = t
        elif sec == "JAARPLAN":
            jaarplan_rows.extend(src.parse_jaarplan_page(text, pno))
        elif sec == "BEVINDINGEN":
            bev_rows.extend(src.parse_bevindingen_page(text, pno))

    obs, zero_rows = [], 0
    for row in rows:
        o = build_row_observation(doc, row, ctx, unit_lookup)
        if o["total_value"] is not None and Decimal(o["total_value"]) == 0 and not o["annual_amounts"]:
            zero_rows += 1
            continue
        o["document_relation_ids"] = list(document_relation_ids)
        obs.append(o)

    link_verified_actions(obs, verified)
    jl, ju = link_section_rows(obs, jaarplan_rows, "JAARPLAN")
    bl, bu = link_section_rows(obs, bev_rows, "BEVINDINGEN")
    for u in ju + bu:
        u["document_id"] = doc_id

    extra = {"status": "parsed", "pages": len(pages), "document_context": ctx,
             "jarenplan_totaal_object": dec_str(totaal_object)}
    obs_sum = sum((Decimal(o["total_value"]) for o in obs if o["total_value"]), Decimal("0"))
    linked_actions = {a for o in obs for a in o["extraction_link"]["action_ids"]}
    checks = {
        "status": "parsed",
        "jarenplan_rows_parsed": len(rows),
        "zero_total_rows_not_observations": zero_rows,
        "observations": len(obs),
        "total_scope": dict(Counter(o["total_scope"] for o in obs)),
        "cycle_length_blank_in_source": sum(1 for o in obs if o["cycle_length_as_stated"] is None),
        "cycle_start_missing": sum(1 for o in obs if o["cycle_start_year"] is None),
        "cycle_start_before_window": sum(1 for o in obs if o["cycle_start_year"] and o["execution_window_start"]
                                         and o["cycle_start_year"] < o["execution_window_start"]),
        "amount_reconciliation_not_consistent": sum(1 for o in obs if o["amount_reconciliation"] != "consistent"),
        "sum_observation_totals": dec_str(obs_sum),
        "jarenplan_totaal_object": dec_str(totaal_object),
        "totaal_object_difference": dec_str(obs_sum - totaal_object) if totaal_object is not None else None,
        "price_level_basis": ctx["price_level_basis"],
        "price_level_date": ctx["price_level_date"],
        "vat_basis": ctx["vat_basis"],
        "provenance_incomplete": sum(1 for o in obs if o["provenance_status"] != "complete"),
        "observations_without_extraction_link": sum(1 for o in obs if not o["extraction_link"]["action_ids"]),
        "verified_actions_linked": len(linked_actions),
        "verified_actions_total": len(verified.get("maintenance_actions", [])) if verified else 0,
        "unit_price_calculated": sum(1 for o in obs if o["unit_price_calculated"]),
        "calculated_over_multiple_executions": sum(1 for o in obs if o["calculated_unit_price_basis"] ==
                                                   "row_total_over_multiple_executions_in_window"),
        "jaarplan_rows_with_amount": sum(1 for r in jaarplan_rows if to_decimal(r["amount_as_stated"])),
        "jaarplan_rows_linked": len(jl),
        "bevindingen_rows_with_amount": sum(1 for r in bev_rows if r["amount_as_stated"] and to_decimal(r["amount_as_stated"])),
        "bevindingen_rows_linked": len(bl),
        "section_rows_unlinked": len(ju) + len(bu),
    }
    return extra, obs, ju + bu, checks


def compute_totals(observations, relations, unlinked_rows):
    return {
        "observations": len(observations),
        "total_scope": dict(Counter(o["total_scope"] for o in observations)),
        "dependency_status": dict(Counter(o["dependency_status"] for o in observations)),
        "price_level_basis": dict(Counter(o["price_level_basis"] for o in observations)),
        "cycle_length_blank_in_source": sum(1 for o in observations if o["cycle_length_as_stated"] is None),
        "provenance_incomplete": sum(1 for o in observations if o["provenance_status"] != "complete"),
        "requires_human_review": sum(1 for o in observations if o["requires_human_review"]),
        "unit_price_calculated": sum(1 for o in observations if o["unit_price_calculated"]),
        "calculated_over_multiple_executions": sum(1 for o in observations if o["calculated_unit_price_basis"] ==
                                                   "row_total_over_multiple_executions_in_window"),
        "section_rows_unlinked": len(unlinked_rows),
        "relations": dict(Counter(r["type"] for r in relations)),
    }


def build(project_root, pdftotext_bin, document_ids=None):
    inventory = json.load(open(os.path.join(project_root, "reports", "document_inventory.json"), encoding="utf-8"))
    rel_doc = json.load(open(os.path.join(project_root, "data", "price_observations", "document_relations.json"), encoding="utf-8"))
    doc_relations = rel_doc["relations"]
    duplicates = {r["secondary_document_id"]: r for r in doc_relations if r["type"] == "duplicate_source"}
    unit_lookup = load_vocab(os.path.join(project_root, "vocabularies"), "unit")

    documents, observations, section_links, unlinked_rows = [], [], [], []
    by_doc = {}
    checks = {}
    for doc in inventory:
        doc_id = doc["document_id"]
        if document_ids and doc_id not in document_ids:
            continue
        entry = {"document_id": doc_id, "relative_path": doc["relative_path"], "sha256": doc["sha256"],
                 "file_type": doc["file_type"],
                 "document_relation_ids": [r["relation_id"] for r in doc_relations
                                           if doc_id in r.get("document_ids", []) or doc_id in
                                           (r.get("primary_document_id"), r.get("secondary_document_id"))]}
        if doc_id in duplicates:
            entry.update(status="duplicate_source_no_observations",
                         duplicate_of=duplicates[doc_id]["primary_document_id"],
                         note="Levert geen eigen price observations op (duplicate_source). Niet rij-voor-rij geparst.")
            documents.append(entry)
            checks[doc_id] = {"status": entry["status"], "observations": 0}
            continue
        if doc["file_type"] != "pdf":
            entry.update(status="unsupported_file_type_not_parsed")
            documents.append(entry)
            checks[doc_id] = {"status": entry["status"], "observations": 0}
            continue

        pages = src.pdf_pages(os.path.join(project_root, "data", "raw", doc["relative_path"]), pdftotext_bin)
        vpath = os.path.join(project_root, "data", "verified", f"{doc_id}.json")
        verified = json.load(open(vpath, encoding="utf-8")) if os.path.exists(vpath) else None
        extra, obs, unlinked, checks[doc_id] = build_document(doc, pages, verified, unit_lookup,
                                                              entry["document_relation_ids"])
        unlinked_rows.extend(unlinked)
        entry.update(extra)
        documents.append(entry)
        by_doc[doc_id] = obs
        observations.extend(obs)

    relations = build_relations(by_doc, doc_relations)
    totals = compute_totals(observations, relations, unlinked_rows)
    return {
        "builder_version": BUILDER_VERSION,
        "text_extraction": {"tool": src.pdftotext_version(pdftotext_bin), "mode": src.PDFTOTEXT_MODE,
                            "line_numbers_refer_to": "regelnummer in de pdftotext -table weergave van die pagina"},
        "note": ("1 jarenplan-rij met bedrag > 0 binnen het venster = 1 price observation. Jaarplan/Bevindingen "
                 "zijn bronweergaven, geen extra observations. NO_DEPENDENCY_FOUND betekent niet onafhankelijk. "
                 "unit_price_calculated bij MULTIPLE_EXECUTIONS is een verhouding over het rijtotaal, geen prijs "
                 "per uitvoering. Geen prijspeil afgeleid waar de bron er geen geeft."),
        "documents": documents,
        "document_relations": doc_relations,
        "checks": {"per_document": checks, "totals": totals},
        "observations": observations,
        "observation_relations": relations,
        "unlinked_section_rows": unlinked_rows,
    }


def validate_observations(result, schema_path):
    import jsonschema
    schema = json.load(open(schema_path, encoding="utf-8"))
    errors = []
    for o in result["observations"]:
        for e in jsonschema.Draft7Validator(schema).iter_errors(o):
            errors.append(f"{o['observation_id']}: {e.message}")
    return errors


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdftotext", default=None, help="pad naar pdftotext (xpdf 4.06); standaard uit PATH of $PDFTOTEXT")
    ap.add_argument("--out", default=os.path.join("data", "price_observations", "price_observations_batch1.json"))
    ap.add_argument("--dry-run", action="store_true", help="bouw en controleer, maar schrijf niets weg")
    args = ap.parse_args()

    binary = src.find_pdftotext(args.pdftotext)
    if not binary:
        sys.exit("pdftotext niet gevonden (installeer xpdf/poppler of geef --pdftotext op).")
    result = build(project_root, binary)
    errors = validate_observations(result, os.path.join(project_root, "schemas", "price_observation.schema.json"))
    if errors:
        print(f"SCHEMA-FOUTEN ({len(errors)}):")
        for e in errors[:20]:
            print("  ", e)
        sys.exit(1)

    print(json.dumps(result["checks"], ensure_ascii=False, indent=2))
    if args.dry_run:
        print("\n--dry-run: niets geschreven.")
        return
    out = os.path.join(project_root, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
