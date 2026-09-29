#!/usr/bin/env python3
"""
normalize_price_observations.py  (PRICE OBSERVATIONS -> NORMALIZED + VALIDATED)

Afgeleide laag bovenop data/price_observations/price_observations_batch1.json.
De source observations worden NIET aangepast; dit script schrijft een aparte
output waarin elke observation naar zijn bron verwijst (observation_id +
sha256 van het bronbestand).

Wat het doet, per observation:
  1. ACTIE: combineert twee bestaande, onderbouwde bronnen voor de
     genormaliseerde actie - (a) de waarde uit de gekoppelde data/verified-
     actie (door de review-ronde gegaan) en (b) een exacte lookup van de
     originele actietekst in vocabularies/maintenance_action.json (zelfde
     regel als normalize_batch.py: hoofdletterongevoelig, witruimte
     samengevoegd). Gelijk of maar één aanwezig -> genormaliseerd. Verschillend
     -> null + review + beide waarden in possible_values. Geen van beide ->
     null + review. Als (a) en (b) niets opleveren: een expliciet
     goedgekeurde patroonregel op het eerste woord (ACTION_PREFIX_RULES).
     Geen fuzzy matching, geen nieuwe betekenissen.
  2. EENHEID: exacte lookup in vocabularies/unit.json; onbekend of
     onleesbaar -> null + review.
  3. ELEMENT: bewaart de originele code/omschrijving en de interne code uit
     data/verified; vergelijkt ze; label uit vocabularies/element_code.json.
     Het coderingssysteem heet hier 'internal_project_coding' - niet
     bevestigd als officiële NL/SfB.
  4. PRIJSVALIDATIE: controleert de bestaande prijsvelden (nooit corrigeren):
     hoeveelheid, totaal, eenheid, herberekening van unit_price_calculated,
     prijspeil, BTW, Stj/Cy (incl. of het cycluspatroon overeenkomt met de
     jaarbedragen), total_scope en meerdere uitvoeringen.
  5. MATERIAAL: neemt het materiaal van het gekoppelde verified-element over
     (ongewijzigd). Alleen voor documenten waarvan de extractie geen
     materiaalveld kende (MATERIAL_FROM_TEXT_DOCUMENTS, DOC-001) wordt een
     materiaal uit de elementomschrijving afgeleid, in een APART veld
     (material_from_text): precies één los woord dat letterlijk in
     vocabularies/material.json staat, geen ander of wisselend materiaal in
     de actietekst, en niet expliciet aangehouden voor menselijke
     interpretatie. Geen fuzzy matching, geen hiërarchie.
  6. REVIEW: één lijst review_reasons met categorie en herkomst
     (source_layer/normalization); de oorspronkelijke source-redenen blijven
     apart bewaard. Informatieve bevindingen staan in validation_flags en
     maken een observation niet automatisch review-plichtig.

Geen matching, geen vergelijkbaarheid, geen kengetallen.

Gebruik:
    python scripts/normalize_price_observations.py
    python scripts/normalize_price_observations.py --dry-run
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_batch import NON_DIVISIBLE_UNITS  # noqa: E402

NORMALIZER_VERSION = "price_observation_normalization_v1"
ELEMENT_CODE_SYSTEM = "internal_project_coding"
ELEMENT_CODE_SYSTEM_NOTE = ("Intern coderingssysteem uit de eigen MJOP's (vocabularies/element_code.json); "
                            "NL-SfB-achtig maar niet bevestigd als officiële NL/SfB.")

# review-reden -> categorie
REASON_CATEGORY = {
    "element_context_missing": "provenance",
    "no_extraction_link": "provenance",
    "total_scope_unknown": "price_data",
    "unit_not_normalized": "unit",
    "unit_unknown": "unit",
    "unit_missing_or_unreadable": "unit",
    "action_not_normalized": "action",
    "conflicting_action_normalization": "action",
    "element_code_mismatch_source_vs_verified": "classification",
    "element_code_internal_missing": "classification",
    "unresolved_source_relationship": "source_relationship",
    "quantity_not_positive": "price_data",
    "total_not_positive": "price_data",
    "calculated_unit_price_inconsistent": "price_data",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lookup_key(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def load_vocab_utf8(vocab_dir, name):
    """Zelfde lookup als normalize_batch.load_vocab (known_original_values ->
    normalized_value), maar expliciet als UTF-8 gelezen: load_vocab gebruikt de
    platformstandaard, waardoor 'm²' op Windows als 'mÂ²' wordt ingelezen."""
    doc = json.load(open(os.path.join(vocab_dir, f"{name}.json"), encoding="utf-8"))
    return {lookup_key(orig): e.get("normalized_value")
            for e in doc.get("entries", []) for orig in e.get("known_original_values", [])}


def D(s):
    return None if s is None else Decimal(s)


# --------------------------------------------------------------------------
# 5: materiaal
# --------------------------------------------------------------------------

# Documenten waarvan de (handmatige v1-)extractie geen materiaalveld had en
# waarvoor de gebruiker afleiding uit de elementtekst heeft goedgekeurd
# (2026-09-24). DOC-004 mist het veld ook, maar valt hier bewust buiten.
MATERIAL_FROM_TEXT_DOCUMENTS = {"DOC-001"}
# Door de gebruiker als 'interpretatie nodig' aangemerkt (2026-09-24) terwijl
# de woordregel wel een materiaal zou vinden: niet automatisch afleiden.
MATERIAL_FROM_TEXT_HOLD = {
    "PO-DOC-001-P025-L039": "'verzinkt staal': kwalificatie bij het materiaal; elders als 'staal (verzinkt)' "
                            "zonder genormaliseerde waarde vastgelegd",
}
MATERIAL_CHANGE_MARKER = re.compile(r">")  # materiaalwissel-notatie in de bron: "->", "- >", ">"
# Menselijke materiaalbesluiten per EXACTE observation (scripts/record_material_decision.py). Geen
# documentbrede scope: een besluit geldt alleen voor zijn observation_id en alleen zolang de bronobservation
# byte-gelijk is aan wat de mens beoordeelde (source_observation_sha256).
MATERIAL_DECISIONS_PATH = os.path.join("data", "review_decisions", "material_decision_records.json")


def observation_fingerprint(obs):
    """sha256 van de bronobservation (canonieke JSON) - binding van een materiaalbesluit aan zijn invoer."""
    return hashlib.sha256(json.dumps(obs, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def load_material_decisions(project_root):
    """ACTIVE materiaalbesluiten per observation_id (leeg als de opslag niet bestaat)."""
    path = os.path.join(project_root, MATERIAL_DECISIONS_PATH)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        store = json.load(f)
    return {r["observation_id"]: r for r in store["records"] if r["status"] == "ACTIVE"}


def material_tokens(text, material_vocab):
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t in material_vocab]


def _apply_material_decision(out, obs, decision):
    """Menselijk materiaalbesluit voor precies deze observation, alleen bij ongewijzigde invoer."""
    if decision["source_observation_sha256"] != observation_fingerprint(obs):
        out["material_not_derived_reason"] = "material_decision_input_changed"
        return out
    out.update(material_original=decision["material"]["original_value"],
               material_normalized=decision["material"]["normalized_value"],
               material_source="human_material_decision", material_status="MATERIAL_FROM_HUMAN_DECISION",
               material_not_derived_reason=None, material_decision_id=decision["decision_id"])
    return out


def normalize_material(obs, verified_elements, material_vocab, material_decisions=None):
    """Materiaal van het verified-element (ongewijzigd); anders een menselijk materiaalbesluit voor exact
    deze observation; en, alleen waar het materiaalveld in de extractie ontbrak, een aparte afleiding uit
    de tekst."""
    decision = (material_decisions or {}).get(obs["observation_id"])
    out = {"material_original": None, "material_normalized": None, "verified_material_field": None,
           "material_from_text": None, "material_source": None, "material_status": "MATERIAL_UNKNOWN",
           "material_not_derived_reason": None}
    eid = obs["element"]["element_id"]
    el = verified_elements.get(eid) if eid else None
    if el is None:
        out.update(verified_material_field="no_element_link", material_not_derived_reason="no_element_link")
        return out
    if "material" in el:
        m = el["material"] or {}
        out.update(verified_material_field="present", material_original=m.get("original_value"),
                   material_normalized=m.get("normalized_value"))
        if m.get("original_value"):
            out.update(material_source="verified_element", material_status="MATERIAL_FROM_VERIFIED")
            return out
        if decision:
            return _apply_material_decision(out, obs, decision)
        if obs["document_id"] not in MATERIAL_FROM_TEXT_DOCUMENTS:
            out["material_not_derived_reason"] = "verified_material_empty"
            return out
        # Leeg/null materiaalveld (bijv. deterministische extractie, die bewust geen materiaal
        # invult) telt voor de bestaande MATERIAL_FROM_TEXT-regel als ontbrekend veld
        # (besluit 2026-09-28) - zelfde regel, zelfde tekstpatronen, niets nieuws.
    else:
        out["verified_material_field"] = "absent"
        if decision:
            return _apply_material_decision(out, obs, decision)
        if obs["document_id"] not in MATERIAL_FROM_TEXT_DOCUMENTS:
            out["material_not_derived_reason"] = "material_field_absent_document_not_in_scope"
            return out
    toks = material_tokens(obs["element"]["element_description_original"], material_vocab)
    action = obs["action"]["action_text_original"]
    if not toks:
        reason = "no_vocabulary_token_in_element_text"
    elif len({material_vocab[t] for t in toks}) > 1:
        reason = "multiple_vocabulary_tokens_in_element_text"
    elif MATERIAL_CHANGE_MARKER.search(action or ""):
        reason = "material_change_in_action_text"
    elif any(material_vocab[t] != material_vocab[toks[0]] for t in material_tokens(action, material_vocab)):
        reason = "conflicting_material_in_action_text"
    elif obs["observation_id"] in MATERIAL_FROM_TEXT_HOLD:
        reason = "held_for_human_interpretation"
    else:
        out.update(material_from_text={"original_value": toks[0], "normalized_value": material_vocab[toks[0]],
                                       "source_field": "element_description_original"},
                   material_source="element_text", material_status="MATERIAL_FROM_TEXT")
        return out
    out["material_not_derived_reason"] = reason
    return out


# --------------------------------------------------------------------------
# 1-3: actie, eenheid, element
# --------------------------------------------------------------------------

# Patroonregels op het EERSTE woord van de actietekst, expliciet goedgekeurd
# door de gebruiker (2026-09-23) na analyse van de 71 niet-genormaliseerde
# acties. Onderbouwing: in vocabularies/maintenance_action.json gaan alle
# bekende teksten die met 'vervangen' (27/27), 'herstellen' (15/15) en
# 'reinigen' (6/6) beginnen naar dezelfde categorie. Alleen toegepast als
# verified-koppeling en exacte vocabulaire-lookup geen waarde geven.
# Bewust NIET: werkwoord achteraan ('Betontegels vervangen'), 'reinigen en
# controleren' (twee acties), en geen nieuwe actietypen voor materiaalwissel,
# deelvervanging of bundeling - die betekenis blijft in de originele tekst.
ACTION_PREFIX_RULES = {"vervangen": "replace", "herstellen": "repair", "herstel": "repair", "reinigen": "clean"}
ACTION_PREFIX_EXCLUSIONS = ("reinigen en controleren",)


def prefix_rule(text):
    key = lookup_key(text)
    if not key or any(key.startswith(x) for x in ACTION_PREFIX_EXCLUSIONS):
        return None, None
    first = key.split(" ", 1)[0]
    if first in ACTION_PREFIX_RULES:
        return ACTION_PREFIX_RULES[first], first
    return None, None


def normalize_action(obs, action_vocab):
    original = obs["action"]["action_text_original"]
    linked = obs["action"]["action_normalized"]
    linked_basis = obs["action"]["action_normalization_basis"]
    vocab = action_vocab.get(lookup_key(original))
    pattern, pattern_word = prefix_rule(original)
    out = {
        "action_text_original": original,
        "action_normalized": None,
        "normalization_basis": None,
        "candidates": {"verified_link": linked, "verified_link_basis": linked_basis, "vocabulary_lookup": vocab,
                       "prefix_pattern": pattern},
        "possible_values": [],
        "status": None,
    }
    reasons = []
    if linked and vocab and linked != vocab:
        out.update(status="conflict", possible_values=sorted({linked, vocab}))
        reasons.append("conflicting_action_normalization")
    elif linked and vocab:
        out.update(action_normalized=linked, normalization_basis="verified_link+vocabulary_lookup", status="normalized")
    elif linked:
        out.update(action_normalized=linked, normalization_basis=f"verified_link ({linked_basis})", status="normalized")
    elif vocab:
        out.update(action_normalized=vocab, normalization_basis="vocabulary_lookup_on_source_text", status="normalized")
    elif pattern:
        out.update(action_normalized=pattern, normalization_basis=f"prefix_pattern_rule:{pattern_word}", status="normalized")
    else:
        out["status"] = "unresolved"
        reasons.append("action_not_normalized")
    return out, reasons


def normalize_unit(obs, unit_vocab):
    original = obs["unit_original"]
    out = {"unit_original": original, "unit_normalized": None, "normalization_basis": None, "status": None}
    if not original:
        out["status"] = "missing_or_unreadable"
        return out, ["unit_missing_or_unreadable"]
    norm = unit_vocab.get(lookup_key(original))
    if norm is None:
        out["status"] = "unknown"
        return out, ["unit_unknown"]
    out.update(unit_normalized=norm, normalization_basis="vocabulary_lookup", status="normalized",
               divisible=norm not in NON_DIVISIBLE_UNITS)
    return out, []


def normalize_element(obs, element_codes):
    el = obs["element"]
    orig, internal = el["element_code_original"], el["element_code_internal"]
    meta = element_codes.get(internal) or {}
    out = {
        "element_code_original": orig,
        "element_code_internal": internal,
        "element_code_system": ELEMENT_CODE_SYSTEM,
        "element_code_system_note": ELEMENT_CODE_SYSTEM_NOTE,
        "internal_code_label": meta.get("label_nl"),
        "internal_hoofdgroep_code": meta.get("hoofdgroep_code"),
        "element_description_original": el["element_description_original"],
        "element_location_original": el.get("element_location_original"),
        "element_id": el["element_id"],
        "code_consistency": None,
    }
    reasons = []
    if orig and internal:
        out["code_consistency"] = "match" if orig == internal else "mismatch"
        if orig != internal:
            reasons.append("element_code_mismatch_source_vs_verified")
    elif internal:
        out["code_consistency"] = "original_missing"
    elif orig:
        out["code_consistency"] = "internal_missing"
        reasons.append("element_code_internal_missing")
    else:
        out["code_consistency"] = "both_missing"
        reasons.append("element_code_internal_missing")
    return out, reasons


# --------------------------------------------------------------------------
# 4: prijsvalidatie (alleen controleren, nooit corrigeren)
# --------------------------------------------------------------------------

def expected_cycle_years(stj, cy, start, end):
    if stj is None or not cy or start is None or end is None:
        return None
    years, y = [], stj
    while y <= end:
        if y >= start:
            years.append(str(y))
        y += cy
    return years


def validate_price(obs, unit_norm):
    checks, flags, reasons = {}, [], []
    qty, total = D(obs["quantity_value"]), D(obs["total_value"])

    checks["quantity_positive"] = qty is not None and qty > 0
    if not checks["quantity_positive"]:
        reasons.append("quantity_not_positive")
    checks["total_positive"] = total is not None and total > 0
    if not checks["total_positive"]:
        reasons.append("total_not_positive")
    checks["amount_reconciliation"] = obs["amount_reconciliation"]

    calc = D(obs["unit_price_calculated"])
    if calc is not None:
        recomputed = (total / qty).quantize(Decimal("0.01")) if checks["quantity_positive"] and total is not None else None
        checks["calculated_unit_price_recomputes"] = recomputed == calc
        if recomputed != calc:
            reasons.append("calculated_unit_price_inconsistent")
    else:
        checks["calculated_unit_price_recomputes"] = None
        expected = (unit_norm is not None and unit_norm not in NON_DIVISIBLE_UNITS and obs["total_scope"] != "UNKNOWN"
                    and checks["quantity_positive"])
        if expected:
            flags.append("calculated_unit_price_expected_but_absent")

    if obs["price_level_basis"] != "explicit":
        flags.append("price_level_absent_in_source")
    if obs["vat_basis"] is None:
        flags.append("vat_basis_unknown")
    elif obs["vat_basis"] == "exclusive":
        flags.append("vat_exclusive")

    stj, cy = obs["cycle_start_year"], obs["cycle_length_years"]
    start, end = obs["execution_window_start"], obs["execution_window_end"]
    if stj is None:
        flags.append("cycle_start_missing")
    elif start is not None and stj < start:
        flags.append("cycle_start_before_window")
    if cy is None:
        flags.append("cycle_length_blank_in_source")
    exp = expected_cycle_years(stj, cy, start, end)
    if exp is None and stj is not None and cy is None:
        exp = [str(stj)] if start is not None and start <= stj <= end else []
    checks["cycle_pattern_matches_annual_amounts"] = None if exp is None else exp == obs["planned_years"]
    if exp is not None and exp != obs["planned_years"]:
        flags.append("cycle_pattern_differs_from_annual_amounts")

    checks["total_scope"] = obs["total_scope"]
    if obs["total_scope"] == "MULTIPLE_EXECUTIONS":
        flags.append("multiple_executions_in_window")
        if calc is not None:
            flags.append("calculated_unit_price_is_row_total_ratio")
        if len(set(obs["annual_amounts"].values())) > 1:
            flags.append("unequal_amounts_across_executions")

    if obs["element"]["element_code_internal"] == "ZZZZ":
        flags.append("staartkosten_post_zzzz")
    if obs["dependency_status"] == "POSSIBLY_DEPENDENT":
        flags.append("possibly_dependent_relation")
    if obs["dependency_status"] == "UNKNOWN":
        reasons.append("unresolved_source_relationship")
    return checks, flags, reasons


# --------------------------------------------------------------------------
# Samenvoegen
# --------------------------------------------------------------------------

def normalize_observation(obs, action_vocab, unit_vocab, element_codes, source_ref,
                          verified_elements=None, material_vocab=None, material_decisions=None):
    action, r_action = normalize_action(obs, action_vocab)
    material = normalize_material(obs, verified_elements or {}, material_vocab or {}, material_decisions)
    unit, r_unit = normalize_unit(obs, unit_vocab)
    element, r_element = normalize_element(obs, element_codes)
    checks, flags, r_price = validate_price(obs, unit["unit_normalized"])

    reasons = []
    # source-layer redenen die hier opnieuw beoordeeld worden, worden vervangen
    # door het resultaat van deze laag (actie/eenheid); de rest blijft staan.
    superseded = {"action_not_normalized", "conflicting_action_normalization", "unit_not_normalized"}
    for r in obs["review_reasons"]:
        if r not in superseded:
            reasons.append({"code": r, "category": REASON_CATEGORY.get(r, "other"), "origin": "source_layer"})
    for r in r_action + r_unit + r_element + r_price:
        if r not in {x["code"] for x in reasons}:
            reasons.append({"code": r, "category": REASON_CATEGORY.get(r, "other"), "origin": "normalization"})

    return {
        "observation_id": obs["observation_id"],
        "document_id": obs["document_id"],
        "source_ref": dict(source_ref, observation_id=obs["observation_id"],
                           source_representations=obs["source_representations"],
                           extraction_action_ids=obs["extraction_link"]["action_ids"]),
        "action": action,
        "unit": unit,
        "element": element,
        "material": material,
        "price": {k: obs[k] for k in (
            "quantity_as_stated", "quantity_value", "total_as_stated", "total_value", "annual_amounts",
            "planned_years", "total_scope", "occurrences_in_window", "execution_window_start",
            "execution_window_end", "cycle_start_year", "cycle_length_years", "price_type",
            "unit_price_literal", "unit_price_calculated", "calculated_unit_price_basis",
            "price_level_date", "price_level_basis", "vat_basis", "vat_rate_text", "indexation_statement",
            "legacy_extracted_cost_years")},
        "validation": {"checks": checks, "flags": flags},
        "dependency_status": obs["dependency_status"],
        "relation_ids": obs["relation_ids"],
        "document_relation_ids": obs["document_relation_ids"],
        "source_review_reasons": list(obs["review_reasons"]),
        "review_reasons": reasons,
        "requires_human_review": bool(reasons),
        "review_status": obs["review_status"],
    }


def normalize(project_root, source_path):
    src = json.load(open(source_path, encoding="utf-8"))
    vocab_dir = os.path.join(project_root, "vocabularies")
    action_vocab = load_vocab_utf8(vocab_dir, "maintenance_action")
    unit_vocab = load_vocab_utf8(vocab_dir, "unit")
    element_codes = {e["normalized_value"]: e for e in
                     json.load(open(os.path.join(vocab_dir, "element_code.json"), encoding="utf-8"))["entries"]}
    material_vocab = load_vocab_utf8(vocab_dir, "material")
    verified_dir = os.path.join(project_root, "data", "verified")
    verified_elements = {e["element_id"]: e for name in sorted(os.listdir(verified_dir)) if name.endswith(".json")
                         for e in json.load(open(os.path.join(verified_dir, name), encoding="utf-8"))["elements"]}
    source_ref = {"source_file": os.path.relpath(source_path, project_root).replace("\\", "/"),
                  "source_file_sha256": sha256_file(source_path)}
    material_decisions = load_material_decisions(project_root)
    out = [normalize_observation(o, action_vocab, unit_vocab, element_codes, source_ref,
                                 verified_elements, material_vocab, material_decisions) for o in src["observations"]]

    summary = {
        "observations": len(out),
        "action_status": dict(Counter(o["action"]["status"] for o in out)),
        "action_normalization_basis": dict(Counter(o["action"]["normalization_basis"] for o in out)),
        "unit_status": dict(Counter(o["unit"]["status"] for o in out)),
        "element_code_consistency": dict(Counter(o["element"]["code_consistency"] for o in out)),
        "material_status": dict(Counter(o["material"]["material_status"] for o in out)),
        "material_not_derived_reason": dict(Counter(o["material"]["material_not_derived_reason"] for o in out
                                                    if o["material"]["material_not_derived_reason"])),
        "requires_human_review": sum(1 for o in out if o["requires_human_review"]),
        "review_reasons": dict(Counter(r["code"] for o in out for r in o["review_reasons"])),
        "review_categories": dict(Counter(c for o in out for c in {r["category"] for r in o["review_reasons"]})),
        "validation_flags": dict(Counter(f for o in out for f in o["validation"]["flags"])),
    }
    vocab_files = {n: sha256_file(os.path.join(vocab_dir, f"{n}.json")) for n in ("maintenance_action", "unit", "element_code", "material")}
    return {
        "normalizer_version": NORMALIZER_VERSION,
        "source": source_ref,
        "vocabularies_sha256": vocab_files,
        "note": ("Afgeleide laag: bronwaarden zijn niet gewijzigd. action/unit/element zijn genormaliseerd met "
                 "bestaande vocabularies en de gekoppelde verified-acties; onzeker -> null + review. "
                 "validation_flags zijn informatief; review_reasons vragen een menselijke beslissing. "
                 "element_code_internal is een intern coderingssysteem, niet bevestigd als officiële NL/SfB."),
        "summary": summary,
        "observations": out,
    }


def validate_output(result, schema_path):
    import jsonschema
    schema = json.load(open(schema_path, encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema)
    return [f"{o['observation_id']}: {e.message}" for o in result["observations"] for e in v.iter_errors(o)]


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.join("data", "price_observations", "price_observations_batch1.json"))
    ap.add_argument("--out", default=os.path.join("data", "price_observations", "price_observations_batch1_normalized.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    result = normalize(root, os.path.join(root, args.source))
    errors = validate_output(result, os.path.join(root, "schemas", "price_observation_normalized.schema.json"))
    if errors:
        print(f"SCHEMA-FOUTEN ({len(errors)}):")
        for e in errors[:20]:
            print("  ", e)
        sys.exit(1)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    if args.dry_run:
        print("\n--dry-run: niets geschreven.")
        return
    with open(os.path.join(root, args.out), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
