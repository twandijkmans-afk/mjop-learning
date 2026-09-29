"""Quantity observations v1 — historische ELEMENTHOEVEELHEDEN als bronlaag.

Zie docs/quantity_foundation_v1.md en docs/quantity_engine_feasibility_v1.md (§11, §12).

Leest uitsluitend (read-only):
  data/verified/*.json                                  elementenoverzicht -> elements[].quantity
  data/price_observations/price_observations_batch1.json  actiehoeveelheden (alleen verwijzing)
  data/price_observations/document_relations.json       documentrelaties
  data/comparability/comparability_batch1.json          source clusters (zoals comparability v1 ze bepaalt)
  reports/document_registry.json                        document_id -> bronbestand + sha256

Schrijft (afgeleide output, geen canonieke data):
  data/quantity_observations/quantity_observations_v1.json
  reports/quantity_observations_v1.md

Regels (deterministisch, geen AI, geen fuzzy matching, geen scores):
- Eén quantity observation per elementoverzicht-rij met een hoeveelheid. quantity_kind is altijd
  ELEMENT_QUANTITY (hoeveel er van het element is) en method_class SOURCE_REPORTED.
- Actiehoeveelheden (price_observation.quantity_value: hoeveel er per uitvoering gedaan wordt) blijven in
  de price observations. Hier staat alleen een verwijzing met quantity_kind ACTION_QUANTITY; er wordt niets
  gekopieerd of aangepast.
- Provenance wordt volledig overgenomen; of de hoeveelheid letterlijk in het brontekstfragment staat,
  wordt gecontroleerd (niet aangenomen).
- Afhankelijkheden: source cluster (ongewijzigd uit comparability) + documentrelaties. Gelijke
  hoeveelheden in documenten over hetzelfde object zijn géén onafhankelijke bevestiging.
- Verdachte gevallen krijgen deterministische review_reasons. Er wordt nooit gemiddeld of gekozen.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERIFIED_DIR = ROOT / "data" / "verified"
PRICE_OBS = ROOT / "data" / "price_observations" / "price_observations_batch1.json"
DOC_RELATIONS = ROOT / "data" / "price_observations" / "document_relations.json"
COMPARABILITY = ROOT / "data" / "comparability" / "comparability_batch1.json"
REGISTRY = ROOT / "reports" / "document_registry.json"
OUT_JSON = ROOT / "data" / "quantity_observations" / "quantity_observations_v1.json"
OUT_MD = ROOT / "reports" / "quantity_observations_v1.md"

BUILDER_VERSION = "quantity_observations_v1.0.0"
RULES_VERSION = "quantity_observation_rules_v1"

MEASURABLE_UNITS = {"m2", "m1", "m3", "piece"}

# Documentrelaties die over hetzelfde fysieke object gaan (hoeveelheden gaan over hetzelfde onderwerp).
# subplans_same_complex = zelfde complex, ANDER deelplan: geen vergelijking van hoeveelheden.
SAME_OBJECT_RELATION_TYPES = {"duplicate_source", "version_of_same_mjop", "same_building_other_inspection"}
SAME_COMPLEX_OTHER_SCOPE_RELATION_TYPES = {"subplans_same_complex"}

REQUIRED_PROVENANCE_FIELDS = ("document_id", "page", "text_fragment", "extraction_rule")

UNIT_TOKENS = {"m2": "m2", "m²": "m2", "m1": "m1", "st": "piece", "st.": "piece", "stuks": "piece", "m3": "m3"}

# Review-redenen (vereisen een mens) en caveats (alleen informatief).
REVIEW_REASONS = {
    "UNIT_UNKNOWN": "eenheid niet in de gecontroleerde vocabulaire (normalized_value null)",
    "FRACTIONAL_PIECE_COUNT": "eenheid stuks met een niet-geheel aantal",
    "ZERO_QUANTITY": "hoeveelheid is 0",
    "QUANTITY_ONE_IN_MEASURED_UNIT": "precies 1 in m2/m1/m3: mogelijk een plaatshouder i.p.v. een gemeten hoeveelheid",
    "UNIT_IN_TEXT_DIFFERS": "de omschrijving noemt een andere eenheid dan de eenheidskolom",
    "QUANTITY_TEXT_NOT_LOCATED": "de hoeveelheid is niet eenduidig terug te vinden in het brontekstfragment",
    "PROVENANCE_INCOMPLETE": "verplichte provenance ontbreekt",
    "SOURCE_FLAGGED": "de extractie markeerde deze hoeveelheid al (conflict/requires_human_review)",
    "DUPLICATE_KEY_DIFFERENT_QUANTITY": "zelfde element + locatie + eenheid komt in dit document vaker voor met een andere hoeveelheid",
    "AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH": "gekoppelde actiehoeveelheid heeft een andere meetbare eenheid dan het element",
    "ACTION_QUANTITY_EXCEEDS_ELEMENT_QUANTITY": "gekoppelde actiehoeveelheid is groter dan de elementhoeveelheid (zelfde eenheid)",
}
CAVEATS = {
    "LUMP_SUM_NOT_A_MEASURED_QUANTITY": "eenheid post: geen meetbare hoeveelheid",
    "ELEMENT_CODE_EXTERNAL": "document gebruikt externe elementcodering; geen interne element_code",
    "BLOCK_ID_MISSING": "geen block_id (regel komt meermaals voor in de tekstlaag); pagina + tekstfragment aanwezig",
    "DUPLICATE_KEY_SAME_QUANTITY": "zelfde element + locatie + eenheid + hoeveelheid komt in dit document vaker voor",
    "SAME_IN_RELATED_DOCUMENT": "identieke hoeveelheid in een document over hetzelfde object: geen onafhankelijke bevestiging",
    "DIFFERS_FROM_RELATED_DOCUMENT": "andere hoeveelheid in een document over hetzelfde object (niet opgelost, niet gemiddeld)",
}


# --------------------------------------------------------------------------
# Hulpfuncties
# --------------------------------------------------------------------------

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def nl_quantity_tokens(text):
    """Kandidaat-hoeveelheden in een tekstfragment (letterlijk + gelezen), bijv. '2983,00m2' -> ('2983,00', 2983.00).
    Alleen NL-notatie zoals in de elementoverzichten: optionele duizendtalpunten, decimale komma."""
    out = []
    for m in re.finditer(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+,\d+|\d+,\d+|\d+)(?=\s*(?:m2|m1|m3|m²|st\b|st\.|stuks|pst|app)\b)", text or "", re.I):
        raw = m.group(1)
        value = dec(raw.replace(".", "").replace(",", "."))
        if value is not None:
            out.append((raw, value))
    return out


def unit_tokens_in_text(text):
    found = set()
    for tok in re.findall(r"(?<![a-z0-9])(m2|m²|m1|m3|stuks|st\.?)(?![a-z0-9])", (text or "").lower()):
        found.add(UNIT_TOKENS.get(tok, UNIT_TOKENS.get(tok.rstrip("."))))
    found.discard(None)
    return found


def ev(pair):
    """Waarde van een {original_value, normalized_value}-paar of een {value}-object."""
    if not isinstance(pair, dict):
        return None, None
    return pair.get("original_value", pair.get("value")), pair.get("normalized_value")


# --------------------------------------------------------------------------
# Invoer
# --------------------------------------------------------------------------

def load_inputs():
    verified = {}
    for f in sorted(VERIFIED_DIR.glob("*.json")):
        d = load_json(f)
        verified[d["document_id"]] = (f, d)
    price = load_json(PRICE_OBS)
    relations = load_json(DOC_RELATIONS)
    comparability = load_json(COMPARABILITY)
    registry = load_json(REGISTRY)
    return verified, price, relations, comparability, registry


def input_hashes(verified):
    h = {
        "price_observations_sha256": sha256_file(PRICE_OBS),
        "document_relations_sha256": sha256_file(DOC_RELATIONS),
        "comparability_sha256": sha256_file(COMPARABILITY),
        "document_registry_sha256": sha256_file(REGISTRY),
        "verified_sha256": {doc: sha256_file(f) for doc, (f, _) in sorted(verified.items())},
    }
    return h


def cluster_map(comparability):
    out = {}
    for c in comparability.get("source_clusters", []):
        for d in c["document_ids"]:
            out[d] = c["source_cluster"]
    for dup in comparability.get("duplicate_documents", []):
        out.setdefault(dup["document_id"], dup["source_cluster"])
    return out


def relation_map(relations):
    """document_id -> [{relation_id, type, other_document_id, quantity_semantics}]"""
    out = defaultdict(list)
    for r in relations["relations"]:
        if r.get("document_ids"):
            docs = list(r["document_ids"])
        else:
            docs = [r["primary_document_id"], r["secondary_document_id"]]
        if r["type"] in SAME_OBJECT_RELATION_TYPES:
            sem = "SAME_OBJECT"
        elif r["type"] in SAME_COMPLEX_OTHER_SCOPE_RELATION_TYPES:
            sem = "SAME_COMPLEX_OTHER_SCOPE"
        else:
            sem = "OTHER"
        for d in docs:
            for other in docs:
                if other != d:
                    out[d].append({"relation_id": r["relation_id"], "type": r["type"], "other_document_id": other,
                                   "quantity_semantics": sem})
    for d in out:
        out[d].sort(key=lambda x: (x["relation_id"], x["other_document_id"]))
    return out


def registry_map(registry):
    docs = registry["documents"]
    items = docs if isinstance(docs, list) else list(docs.values())
    return {x["document_id"]: {"relative_path": x["relative_path"], "sha256": x["sha256"]} for x in items}


# --------------------------------------------------------------------------
# Opbouw
# --------------------------------------------------------------------------

def action_links(price):
    by_element = defaultdict(list)
    unlinked = []
    for o in price["observations"]:
        eid = (o.get("element") or {}).get("element_id")
        if not eid:
            unlinked.append(o["observation_id"])
            continue
        by_element[eid].append(o)
    return by_element, sorted(unlinked)


def classify_action(element_value, element_unit, o):
    unit = o.get("unit_normalized")
    qv = dec(o.get("quantity_value"))
    if unit is None or unit == "lump_sum" or qv is None:
        rel = "ACTION_LUMP_SUM_OR_UNKNOWN_UNIT"
    elif element_unit not in MEASURABLE_UNITS:
        rel = "ELEMENT_NOT_MEASURABLE"
    elif unit != element_unit:
        rel = "DIFFERENT_UNIT"
    elif qv == element_value:
        rel = "SAME_AS_ELEMENT"
    elif qv < element_value:
        rel = "FRACTION_OF_ELEMENT"
    else:
        rel = "EXCEEDS_ELEMENT"
    return {
        "price_observation_id": o["observation_id"],
        "quantity_kind": "ACTION_QUANTITY",
        "quantity_value": o.get("quantity_value"),
        "unit_normalized": unit,
        "action_normalized": (o.get("action") or {}).get("action_normalized"),
        "relation_to_element_quantity": rel,
    }


def build_observation(doc_id, d, e, ctx):
    q = e["quantity"]
    prov = dict(q.get("provenance") or {})
    unit_original, unit_normalized = ev(e.get("unit"))
    code_original, code_internal = ev(e.get("element_code"))
    name = (e.get("element_name") or {}).get("value")
    location = (e.get("location") or {}).get("value")
    mat_original, mat_normalized = ev(e.get("material"))
    value = dec(q["value"])
    review, caveats = [], []

    # provenance
    missing = [k for k in REQUIRED_PROVENANCE_FIELDS if prov.get(k) in (None, "")]
    if missing:
        review.append("PROVENANCE_INCOMPLETE")
    if not prov.get("block_id"):
        caveats.append("BLOCK_ID_MISSING")
    tokens = nl_quantity_tokens(prov.get("text_fragment"))
    matches = [raw for raw, v in tokens if v == value]
    quantity_as_stated = matches[0] if len(set(matches)) == 1 else None
    if quantity_as_stated is None:
        review.append("QUANTITY_TEXT_NOT_LOCATED")

    # eenheid en waarde
    measurable = unit_normalized in MEASURABLE_UNITS
    if unit_normalized is None:
        review.append("UNIT_UNKNOWN")
    if unit_normalized == "lump_sum":
        caveats.append("LUMP_SUM_NOT_A_MEASURED_QUANTITY")
    if value is not None:
        if unit_normalized == "piece" and value != value.to_integral_value():
            review.append("FRACTIONAL_PIECE_COUNT")
        if value == 0:
            review.append("ZERO_QUANTITY")
        if unit_normalized in {"m2", "m1", "m3"} and value == 1:
            review.append("QUANTITY_ONE_IN_MEASURED_UNIT")
    text_units = unit_tokens_in_text(name)
    if measurable and text_units and unit_normalized not in text_units:
        review.append("UNIT_IN_TEXT_DIFFERS")
    if q.get("conflict") or q.get("requires_human_review"):
        review.append("SOURCE_FLAGGED")
    if code_internal is None and (e.get("element_code") or {}).get("normalization_skipped_reason") == "external_element_coding":
        caveats.append("ELEMENT_CODE_EXTERNAL")

    # actiehoeveelheden (alleen verwijzing)
    links = [classify_action(value, unit_normalized, o) for o in ctx["actions"].get(e["element_id"], [])]
    links.sort(key=lambda x: x["price_observation_id"])
    rels = {x["relation_to_element_quantity"] for x in links}
    if measurable and "DIFFERENT_UNIT" in rels:
        review.append("AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH")
    if "EXCEEDS_ELEMENT" in rels:
        review.append("ACTION_QUANTITY_EXCEEDS_ELEMENT_QUANTITY")

    relations = ctx["relations"].get(doc_id, [])
    obs = {
        "quantity_observation_id": "QO-" + e["element_id"],
        "document_id": doc_id,
        "source_file": ctx["registry"].get(doc_id),
        "source_cluster": ctx["clusters"].get(doc_id),
        "document_relations": relations,
        "building_ref": e.get("building_id"),
        "element": {
            "element_id": e["element_id"],
            "element_code_original": code_original,
            "element_code_internal": code_internal,
            "element_description_original": name,
            "location_original": location,
            "material_original": mat_original,
            "material_normalized": mat_normalized,
        },
        "quantity_kind": "ELEMENT_QUANTITY",
        "method_class": "SOURCE_REPORTED",
        "source_type": "MJOP_ELEMENT_OVERVIEW",
        "direct_or_derived": "DIRECT",
        "quantity_as_stated": quantity_as_stated,
        "quantity_value": q["value"],
        "unit_original": unit_original,
        "unit_normalized": unit_normalized,
        "measurable": measurable,
        "extraction_method": prov.get("extraction_rule"),
        "provenance": prov,
        "provenance_check": {
            "complete": not missing,
            "missing_fields": missing,
            "quantity_text_located": quantity_as_stated is not None,
        },
        "linked_action_quantities": links,
        "dependency": {"same_object_document_ids": sorted({r["other_document_id"] for r in relations
                                                            if r["quantity_semantics"] == "SAME_OBJECT"}),
                       "identical_in_same_object_documents": [], "differs_in_same_object_documents": []},
        "caveats": caveats,
        "review_reasons": review,
    }
    return obs


def compare_key(o):
    el = o["element"]
    return (el["element_code_original"], el["element_description_original"], el["location_original"], o["unit_normalized"])


def apply_cross_checks(observations):
    # binnen één document: dubbele sleutel
    by_doc_key = defaultdict(list)
    for o in observations:
        by_doc_key[(o["document_id"],) + compare_key(o)].append(o)
    for group in by_doc_key.values():
        if len(group) < 2:
            continue
        values = {dec(o["quantity_value"]) for o in group}
        for o in group:
            code = "DUPLICATE_KEY_DIFFERENT_QUANTITY" if len(values) > 1 else "DUPLICATE_KEY_SAME_QUANTITY"
            (o["review_reasons"] if code in REVIEW_REASONS else o["caveats"]).append(code)

    # tussen documenten over hetzelfde object: exacte sleutel, geen fuzzy matching
    by_doc = defaultdict(lambda: defaultdict(list))
    for o in observations:
        by_doc[o["document_id"]][compare_key(o)].append(o)
    for o in observations:
        for other_doc in o["dependency"]["same_object_document_ids"]:
            for p in by_doc.get(other_doc, {}).get(compare_key(o), []):
                if dec(p["quantity_value"]) == dec(o["quantity_value"]):
                    o["dependency"]["identical_in_same_object_documents"].append(p["quantity_observation_id"])
                else:
                    o["dependency"]["differs_in_same_object_documents"].append(p["quantity_observation_id"])
        for k in ("identical_in_same_object_documents", "differs_in_same_object_documents"):
            o["dependency"][k].sort()
        if o["dependency"]["identical_in_same_object_documents"]:
            o["caveats"].append("SAME_IN_RELATED_DOCUMENT")
        if o["dependency"]["differs_in_same_object_documents"]:
            o["caveats"].append("DIFFERS_FROM_RELATED_DOCUMENT")

    for o in observations:
        o["review_reasons"] = sorted(set(o["review_reasons"]))
        o["caveats"] = sorted(set(o["caveats"]))
        o["requires_human_review"] = bool(o["review_reasons"])
        o["status"] = "REVIEW_REQUIRED" if o["requires_human_review"] else "SOURCE_REPORTED"


def build(inputs=None):
    verified, price, relations, comparability, registry = inputs or load_inputs()
    actions, unlinked_actions = action_links(price)
    ctx = {"actions": actions, "relations": relation_map(relations), "clusters": cluster_map(comparability),
           "registry": registry_map(registry)}
    observations, docs_without = [], []
    for doc_id, (_, d) in sorted(verified.items()):
        n = 0
        for e in d.get("elements", []):
            q = e.get("quantity")
            if not isinstance(q, dict) or q.get("value") in (None, ""):
                continue
            observations.append(build_observation(doc_id, d, e, ctx))
            n += 1
        if n == 0:
            docs_without.append({"document_id": doc_id, "elements": len(d.get("elements", [])),
                                 "reason": "geen elementhoeveelheden in de verified extractie"})
    observations.sort(key=lambda o: o["quantity_observation_id"])
    apply_cross_checks(observations)
    return {
        "builder_version": BUILDER_VERSION,
        "rules_version": RULES_VERSION,
        "note": ("Afgeleide bronlaag: historische ELEMENTHOEVEELHEDEN uit de elementenoverzichten (SOURCE_REPORTED). "
                 "Geen gemiddelden, geen keuze tussen bronnen, geen ratio's; price observations ongewijzigd."),
        "input_hashes": input_hashes(verified),
        "vocabulary": {"review_reasons": REVIEW_REASONS, "caveats": CAVEATS},
        "summary": summarize(observations, docs_without, unlinked_actions),
        "documents_without_element_quantities": docs_without,
        "price_observations_without_element_link": unlinked_actions,
        "observations": observations,
    }


def summarize(observations, docs_without, unlinked_actions):
    def count(fn):
        c = defaultdict(int)
        for o in observations:
            for k in fn(o):
                c[k if k is not None else "null"] += 1
        return dict(sorted(c.items()))
    rel_counts = defaultdict(int)
    for o in observations:
        for l in o["linked_action_quantities"]:
            rel_counts[l["relation_to_element_quantity"]] += 1
    return {
        "quantity_observations": len(observations),
        "documents_with_quantities": len({o["document_id"] for o in observations}),
        "documents_without_quantities": [x["document_id"] for x in docs_without],
        "by_unit": count(lambda o: [o["unit_normalized"]]),
        "by_document": count(lambda o: [o["document_id"]]),
        "by_source_cluster": count(lambda o: [o["source_cluster"]]),
        "measurable": sum(1 for o in observations if o["measurable"]),
        "provenance_complete": sum(1 for o in observations if o["provenance_check"]["complete"]),
        "quantity_text_located": sum(1 for o in observations if o["provenance_check"]["quantity_text_located"]),
        "with_block_id": sum(1 for o in observations if o["provenance"].get("block_id")),
        "review_required": sum(1 for o in observations if o["requires_human_review"]),
        "review_reasons": count(lambda o: o["review_reasons"]),
        "caveats": count(lambda o: o["caveats"]),
        "linked_action_quantities": sum(len(o["linked_action_quantities"]) for o in observations),
        "action_relation_counts": dict(sorted(rel_counts.items())),
        "price_observations_without_element_link": len(unlinked_actions),
        "identical_in_same_object_documents": sum(1 for o in observations if o["dependency"]["identical_in_same_object_documents"]),
        "differs_in_same_object_documents": sum(1 for o in observations if o["dependency"]["differs_in_same_object_documents"]),
    }


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------

def render_report(result):
    s = result["summary"]
    L = ["# Quantity observations v1", "",
         f"Builder `{result['builder_version']}`, regels `{result['rules_version']}`. "
         "Afgeleid uit `data/verified/*.json` (elementenoverzicht); zie `docs/quantity_foundation_v1.md`.", "",
         "Alle hoeveelheden hieronder zijn **ELEMENT_QUANTITY / SOURCE_REPORTED**: letterlijk gerapporteerd in een "
         "historisch MJOP, niet gemeten, niet gemiddeld en niet gekozen.", "",
         "## Totalen", "",
         f"- Quantity observations: **{s['quantity_observations']}** uit {s['documents_with_quantities']} documenten",
         f"- Documenten zonder elementhoeveelheden: {', '.join(s['documents_without_quantities']) or '—'}",
         f"- Meetbaar (m2/m1/m3/stuks): {s['measurable']}",
         f"- Provenance compleet (document, pagina, tekstfragment, extractieregel): {s['provenance_complete']}/{s['quantity_observations']}",
         f"- Hoeveelheid letterlijk teruggevonden in het tekstfragment: {s['quantity_text_located']}/{s['quantity_observations']}",
         f"- Met block_id: {s['with_block_id']}/{s['quantity_observations']}",
         f"- REVIEW_REQUIRED: **{s['review_required']}**",
         f"- Gekoppelde actiehoeveelheden (price observations, alleen verwijzing): {s['linked_action_quantities']}; "
         f"price observations zonder elementkoppeling: {s['price_observations_without_element_link']}", "",
         "## Eenheden", "", "| Eenheid | Aantal |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in s["by_unit"].items()]
    L += ["", "## Per document en source cluster", "", "| Document | Source cluster | Aantal | Relaties |", "|---|---|---|---|"]
    by_doc = defaultdict(list)
    for o in result["observations"]:
        by_doc[o["document_id"]].append(o)
    for doc, obs in sorted(by_doc.items()):
        rels = ", ".join(f"{r['relation_id']} {r['type']} ↔ {r['other_document_id']}" for r in obs[0]["document_relations"]) or "—"
        L.append(f"| {doc} | {obs[0]['source_cluster']} | {len(obs)} | {rels} |")
    L += ["", "## Review-redenen", "", "| Reden | Aantal | Betekenis |", "|---|---|---|"]
    L += [f"| `{k}` | {v} | {REVIEW_REASONS[k]} |" for k, v in s["review_reasons"].items()]
    L += ["", "## Caveats (informatief, geen review)", "", "| Caveat | Aantal | Betekenis |", "|---|---|---|"]
    L += [f"| `{k}` | {v} | {CAVEATS[k]} |" for k, v in s["caveats"].items()]
    L += ["", "## Actiehoeveelheden t.o.v. elementhoeveelheid", "",
          "Actiehoeveelheden blijven in de price observations; hier alleen de relatie per koppeling.", "",
          "| Relatie | Aantal |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in s["action_relation_counts"].items()]
    L += ["", "## Afhankelijkheid tussen documenten over hetzelfde object", "",
          f"- Observations met een identieke hoeveelheid in een document over hetzelfde object: "
          f"{s['identical_in_same_object_documents']} (géén onafhankelijke bevestiging)",
          f"- Observations met een afwijkende hoeveelheid in zo'n document: {s['differs_in_same_object_documents']} "
          "(niet opgelost, niet gemiddeld)", ""]
    differs = [o for o in result["observations"] if o["dependency"]["differs_in_same_object_documents"]]
    if differs:
        L += ["| Observation | Element | Locatie | Waarde | Afwijkend in |", "|---|---|---|---|---|"]
        for o in differs:
            L.append(f"| {o['quantity_observation_id']} | {o['element']['element_description_original']} | "
                     f"{o['element']['location_original'] or '—'} | {o['quantity_value']} {o['unit_normalized']} | "
                     f"{', '.join(o['dependency']['differs_in_same_object_documents'])} |")
        L.append("")
    L += ["## Invoer (sha256)", ""]
    h = result["input_hashes"]
    for k in ("price_observations_sha256", "document_relations_sha256", "comparability_sha256", "document_registry_sha256"):
        L.append(f"- `{k}`: `{h[k]}`")
    L.append("")
    return "\n".join(L)


def dumps(result):
    return json.dumps(result, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="controleer of de output nog bij de invoer hoort; schrijft niets")
    ap.add_argument("--replace", action="store_true", help="bestaande output met andere inhoud vervangen")
    args = ap.parse_args(argv)
    result = build()
    js, md = dumps(result), render_report(result)
    if args.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.exists() \
            and OUT_MD.read_text(encoding="utf-8") == md
        print("quantity observations up-to-date" if ok else "quantity observations NIET up-to-date")
        return 0 if ok else 1
    for path, content in ((OUT_JSON, js), (OUT_MD, md)):
        if path.exists() and path.read_text(encoding="utf-8") != content and not args.replace:
            print(f"{path} bestaat met andere inhoud; gebruik --replace om bewust te vervangen", file=sys.stderr)
            return 2
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    s = result["summary"]
    shown = OUT_JSON.relative_to(ROOT) if ROOT in OUT_JSON.parents else OUT_JSON
    print(f"{s['quantity_observations']} quantity observations, {s['review_required']} REVIEW_REQUIRED -> {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
