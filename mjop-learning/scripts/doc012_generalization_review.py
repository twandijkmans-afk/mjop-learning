"""Quantity Engine Generalization v1 — DOC-012 (read-only discovery + review).

Bewijst dat de bestaande keten (bag_snapshot_v1, building links, multi-pand scope, quantity observations, evidence-
regels, onderwerpen/relaties, crosswalk, bundel) buiten Maldenhof werkt, ZONDER besluiten te nemen.

Twee scope-hypotheses, met gescheiden provenance:
  H1  alleen het opgegeven adres (building.address 'Meppelweg 819')
      -> canonieke snapshot uit de bestaande lookup_plan-route (data/bag_snapshots, bag_snapshot_v1).
  H2  het huisnummerbereik uit de objectnaam ('VvE Meppelweg 801-883', document_level_values.object_name)
      -> bag_snapshot_v1 kent geen 'query_source'; een range uit de objectnaam is GEEN document-adres. Daarom staat
         deze opvraging NIET in data/bag_snapshots (dan zou building_links.py record die panden accepteren), maar als
         read-only hypothese-opname in reports/quantity/doc012_scope_hypotheses/ (zelfde structuur en hash-controle,
         canonical=false). Geen tweede snapshotsysteem.

Leest alleen; schrijft uitsluitend:
  reports/quantity/doc012_generalization_review_v1.json / .md

3D BAG-waarden zijn PREVIEW (berekend met build_building_quantity_evidence.bag3d_evidence/scope_aggregate, niet
opgeslagen). Geen building links, geen mapping-besluiten, geen quantity resolution, geen app-bundel.

    python scripts/doc012_generalization_review.py [--check]
"""

import argparse
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bag3d_quantity_rules as rules_mod  # noqa: E402
import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOC = "DOC-012"
HYP_DIR = ROOT / "reports" / "quantity" / "doc012_scope_hypotheses"
OUT_JSON = ROOT / "reports" / "quantity" / "doc012_generalization_review_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "doc012_generalization_review_v1.md"
RESOLUTIONS = ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json"
MALDENHOF_BUNDLE = ROOT / "reports" / "quantity" / "app_bundles" / "maldenhof_DOC-005_DOC-006_v3.json"
MALDENHOF_BUNDLE_SHA256 = "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933"
SUBJECT_ORDER = ("ROOF_FLAT_AREA", "ROOF_SLOPED_AREA", "ROOF_TOTAL_AREA", "OUTER_WALL_GROSS_AREA", "BUILDING_HEIGHT")
CLASSES = ("DIRECTLY_COMPARABLE", "RELATED_NOT_EQUIVALENT", "NO_3DBAG_COUNTERPART", "NEEDS_SEMANTIC_REVIEW", "NOT_MEASURED_QUANTITY")


# --------------------------------------------------------------------------
# Scope-hypotheses
# --------------------------------------------------------------------------

def parse_object_name_range(object_name):
    """'VvE Meppelweg 801-883' -> (street, lo, hi) of None. Deterministisch via building_links.parse_address op de
    objectnaam zonder 'VvE '-voorvoegsel; alleen kind 'range'. Geen fuzzy interpretatie."""
    name = re.sub(r"^(vve|v\.v\.e\.)\s+", "", object_name or "", flags=re.I)
    parts = [p for p in bl.parse_address(name) if p["kind"] == "range"]
    if len(parts) != 1:
        return None
    p = parts[0]
    return p["street"], int(p["numbers"][0]), int(p["numbers"][1])


def load_h2_capture(directory=HYP_DIR):
    files = sorted(Path(directory).glob("H2_BAGSNAP-*.json"))
    if len(files) != 1:
        raise SystemExit(f"verwacht precies één H2-opname in {directory}, gevonden {len(files)}")
    snap = json.loads(files[0].read_text(encoding="utf-8"))
    errs = bs.snapshot_errors(snap)
    if errs:
        raise SystemExit("; ".join(errs))
    return files[0], snap


def pand_rows(snap, pand_ids=None):
    by_id = {m["pdok_id"]: m for m in snap["address_matches"]}
    rows = []
    for p in snap["panden"]:
        if pand_ids is not None and p["bag_pand_id"] not in pand_ids:
            continue
        addrs = [by_id[a] for a in p["contains_address_point_of"]]
        nums = sorted({a.get("huisnummer") for a in addrs if isinstance(a.get("huisnummer"), int)})
        props = p.get("bag_properties") or {}
        tb = p.get("threedbag") or {}
        rows.append({
            "bag_pand_id": p["bag_pand_id"],
            "addresses": sorted(a["weergavenaam"] for a in addrs),
            "address_count_in_query": len(addrs),
            "huisnummers": nums,
            "parity": sorted({"even" if n % 2 == 0 else "oneven" for n in nums}),
            "postcodes": sorted({a.get("postcode") or "GEEN" for a in addrs}),
            "with_suffix": sum(1 for a in addrs if a.get("has_suffix")),
            "verblijfsobjecten_bag": props.get("aantal_verblijfsobjecten"),
            "bouwjaar": props.get("bouwjaar"),
            "gebruiksdoel": props.get("gebruiksdoel"),
            "status": props.get("status"),
            "threedbag_available": bool(tb.get("attributes")),
            "threedbag_error": tb.get("error"),
            "contains_meppelweg_819": 819 in nums,
        })
    return rows


def preview(snap, pand_ids, rules, vocab):
    """Read-only 3D BAG-preview per pand + scope-aggregaat (bij meerdere panden). Niets wordt opgeslagen."""
    subjects = {s["subject_key"]: s for s in vocab["subjects"]}
    agg_rule = next(r for r in vocab["scope_aggregation_rules"] if r["status"] == "ACTIVE")
    per_pand, by_subject = [], {}
    for pid in sorted(pand_ids):
        evs, na = bqe.bag3d_evidence(pid, snap, rules, subjects, [])
        row = {"bag_pand_id": pid, "values": {}, "not_available": sorted({n["rule_id"] for n in na})}
        for k in SUBJECT_ORDER:
            ev = next((e for e in evs if e["quantity_subject"]["subject_key"] == k), None)
            row["values"][k] = None if ev is None else {"value": ev["value"], "unit": ev["unit_normalized"],
                                                       "method_class": ev["method_class"], "evidence_id_preview": ev["evidence_id"]}
            if ev is not None:
                by_subject.setdefault(k, {})[pid] = ev
        per_pand.append(row)
    aggregates = {}
    if len(pand_ids) > 1:
        for k in agg_rule["applies_to_subjects"]:
            ev, np_ = bqe.scope_aggregate(sorted(pand_ids), subjects[k], agg_rule, by_subject.get(k, {}), [])
            aggregates[k] = ({"status": "PREVIEW", "value": ev["value"], "unit": ev["unit_normalized"], "method_class": ev["method_class"],
                              "evidence_id_preview": ev["evidence_id"], "child_count": len(ev["calculation"]["input_evidence_ids"])}
                             if ev else {"status": "NOT_PUBLISHED", "reason": np_["reason"], "missing_bag_pand_ids": np_["missing_bag_pand_ids"]})
        aggregates["BUILDING_HEIGHT"] = {"status": "NOT_AGGREGATED", "reason": "BUILDING_HEIGHT wordt niet opgeteld (scope_aggregation_rules)"}
    return {"building_id_preview": bqe.building_id_for(pand_ids), "pand_count": len(pand_ids), "per_pand": per_pand,
            "scope_aggregate": aggregates or None}


# --------------------------------------------------------------------------
# Historische hoeveelheden
# --------------------------------------------------------------------------

def classify_observations(qos, vocab, app_cw, eff):
    maps = vocab["historical_subject_mappings"]
    not_mapped = {n["element_code_internal"]: n for n in vocab["not_mapped"] if n.get("element_code_internal")}
    bag3d_subjects = {r["subject_key"] for r in vocab["bag3d_rules"] if r["status"] == "ACTIVE"}
    rows = []
    for o in qos:
        el = o["element"]
        code, unit = el.get("element_code_internal"), o.get("unit_normalized")
        hits = [m for m in maps if bqe.mapping_matches(m, o)]
        doc_specific = [m for m in hits if m.get("match")]
        generic = [m for m in hits if not m.get("match")]
        app = [m["mapping_id"] for m in app_cw["mappings"] if m.get("internal_element_code") == code and m.get("unit") == unit]
        app_unresolved = [u.get("reason") for u in app_cw["unresolved"] if u.get("internal_element_code") == code and u.get("unit") == unit]
        subj, rel, cls, notes = None, None, None, []
        if not o.get("measurable") or o.get("quantity_kind") != "ELEMENT_QUANTITY" or unit in (None, "lump_sum"):
            cls = "NOT_MEASURED_QUANTITY"
        elif doc_specific:
            m = doc_specific[0]
            subj = m["subject_key"]
            related = bqe.related_subjects(vocab, subj)
            if subj in bag3d_subjects and eff.get(m["mapping_id"], {}).get("status") == "VERIFIED":
                cls = "DIRECTLY_COMPARABLE"
            elif related:
                cls, rel = "RELATED_NOT_EQUIVALENT", sorted(related.items())[0]
            else:
                cls = "NEEDS_SEMANTIC_REVIEW"
            notes.append(f"exacte document-mapping {m['mapping_id']} ({eff.get(m['mapping_id'], {}).get('status')})")
            for g in generic:
                notes.append(f"generieke mapping {g['mapping_id']} ({eff.get(g['mapping_id'], {}).get('status')}) zou ook matchen "
                             f"naar {g['subject_key']}, maar is NIET geverifieerd (onvoldoende bewijs dat het hetzelfde onderwerp is)")
        elif generic:
            g = generic[0]
            subj = g["subject_key"]
            cls = "DIRECTLY_COMPARABLE" if eff.get(g["mapping_id"], {}).get("status") == "VERIFIED" else "NEEDS_SEMANTIC_REVIEW"
            notes.append(f"alleen generieke mapping {g['mapping_id']} ({eff.get(g['mapping_id'], {}).get('status')})")
        elif code in not_mapped and unit == "m2":
            subj = not_mapped[code]["subject_key"]
            cls = "NEEDS_SEMANTIC_REVIEW"
            notes.append("geen onderwerp-relatie vastgelegd; " + not_mapped[code]["reason"])
        else:
            cls = "NO_3DBAG_COUNTERPART"
        if code == "4711" and unit == "m1":
            notes.append("4711-m1 (dakrand/randstrook) — NOOIT samen met 4711-m2 dakbedekking behandelen")
        rows.append({
            "quantity_observation_id": o["quantity_observation_id"], "element_code": code,
            "description": el.get("element_description_original"), "location": el.get("location_original"),
            "quantity": o.get("quantity_value"), "unit": unit, "status": o.get("status"),
            "requires_human_review": o.get("requires_human_review"),
            "page": (o.get("provenance") or {}).get("page"), "block_id": (o.get("provenance") or {}).get("block_id"),
            "text_fragment": (o.get("provenance") or {}).get("text_fragment"),
            "possible_subject": subj, "subject_relation": None if rel is None else {"related_subject": rel[0], "relation_id": rel[1]},
            "possible_app_crosswalk": app, "app_crosswalk_unresolved": app_unresolved,
            "classification": cls, "caveats": o.get("caveats", []) + notes,
        })
    return rows


# --------------------------------------------------------------------------
# Generalisatie-audit
# --------------------------------------------------------------------------

AUDIT_PATTERNS = ("DOC-005", "DOC-006", "Maldenhof", "1106EZ", "1106 EZ", "190.65", "425.80", "15 panden")
# Scripts die per definitie over één casus rapporteren (reviews/demo's/PoC's). Alles wat niet hier staat en geen test
# of fixture is, geldt als generieke code.
REPORT_ONLY_SCRIPTS = {
    "scripts/multi_pand_scope_demo.py", "scripts/maldenhof_quantity_activation.py", "scripts/quantity_engine_activation_review.py",
    "scripts/doc012_generalization_review.py", "scripts/facade_coverage_poc_v2.py", "scripts/facade_element_detection_poc.py",
    "scripts/facade_ground_truth_poc.py", "scripts/facade_panorama_poc.py", "scripts/facade_poc_v2_report.py",
}

# Handmatig beoordeelde treffers in niet-rapportscripts: geen hardcoding in quantity-logica.
REVIEWED_NOT_A_PROBLEM = {
    "scripts/bag_snapshots.py": "DOCSTRING_EXAMPLE: CLI-voorbeelden en een docstring-voorbeeld ('Maldenhof 240 - 296')",
    "scripts/building_links.py": "DOCSTRING_EXAMPLE: CLI-voorbeeld '--document DOC-005'",
    "scripts/validate_app_quantity_bundle.py": "DOCSTRING_EXAMPLE: CLI-voorbeeld met het pad van de Maldenhof-bundel",
    "scripts/prepare_relation_review.py": "DOCSTRING_EXAMPLE: CLI-voorbeeld",
    "scripts/record_relation_decision.py": "DOCSTRING_EXAMPLE: CLI-voorbeeld",
    "scripts/export_human_review_queue.py": "COMMENT: uitleg bij een regel",
    "scripts/build_comparability.py": "COMMENT: herkomst van regel F7",
    "scripts/backfill_element_codes.py": "PER_DOCUMENT_CONFIG: bronbestand per document (alle documenten, niet alleen Maldenhof)",
    "scripts/deterministic_extraction.py": "PER_DOCUMENT_CONFIG: extractieprofiel per document (alle documenten)",
    "scripts/decision_package_4645_interior_painting_wood.py": "DOCUMENT_SPECIFIC_DECISION_PACKAGE: vaste observation-ID's van een beslispakket",
}


def generalization_audit(root=ROOT):
    files = subprocess.run(["git", "ls-files", "scripts", "tests", "vocabularies", "schemas"], cwd=root, capture_output=True,
                           text=True, check=True).stdout.split()
    hits = []
    for f in files:
        if not f.endswith((".py", ".json")):
            continue
        text = (Path(root) / f).read_text(encoding="utf-8", errors="replace")
        found = [p for p in AUDIT_PATTERNS if p in text]
        if not found:
            continue
        if f.startswith("tests/"):
            kind = "TEST_ONLY"
        elif f in REPORT_ONLY_SCRIPTS:
            kind = "REPORT_ONLY"
        elif f.startswith("vocabularies/"):
            kind = "REPORT_ONLY"  # bewijs-/notitieteksten bij document-specifieke mappings
        elif f in REVIEWED_NOT_A_PROBLEM:
            kind = "NOT_A_PROBLEM"
        else:
            kind = "GENERIC_CODE_PROBLEM"
        lines = [i + 1 for i, line in enumerate(text.splitlines()) if any(p in line for p in found)]
        hits.append({"file": f, "classification": kind, "patterns": found, "lines": lines[:20],
                     "reason": REVIEWED_NOT_A_PROBLEM.get(f)})
    # gevonden en opgelost in deze milestone (geen string-hardcoding, wel een generiek probleem)
    hits.append({"file": "scripts/bag_snapshots.py", "classification": "GENERIC_CODE_PROBLEM_FIXED", "patterns": [],
                 "lines": [], "reason": ("exact_address_match/range-filter vergeleken de woonplaats uit het document letterlijk met "
                                         "de BAG-woonplaatsnaam; 'Den Haag' (DOC-012) vond daardoor zelfs het exacte adres niet "
                                         "('s-Gravenhage). Opgelost met de expliciete aliaslijst vocabularies/woonplaats_aliases_v1.json "
                                         "(exacte gelijkheid, vastgelegd in de snapshot-query; bestaande snapshots ongewijzigd).")})
    return hits


# --------------------------------------------------------------------------

def build():
    rules, vocab = rules_mod.load_rules()
    eff = xw.effective()
    app_cw = json.loads(xw.APP_CROSSWALK.read_text(encoding="utf-8"))
    docs = bl.load_documents()
    d = docs[DOC]
    cand = next(o for o in bl.build_candidates()["documents"] if o["document_id"] == DOC)
    h1_snaps = [s for s in bs.load_snapshots() if s["document_id"] == DOC]
    if len(h1_snaps) != 1:
        raise SystemExit(f"verwacht precies één canonieke snapshot voor {DOC}, gevonden {len(h1_snaps)}")
    h1 = h1_snaps[0]
    h1_pids = sorted(p["bag_pand_id"] for p in h1["panden"])
    h2_path, h2 = load_h2_capture()
    street, lo, hi = parse_object_name_range(d["object_name"])
    h2_rows = pand_rows(h2)
    h2_pids = sorted(r["bag_pand_id"] for r in h2_rows)
    h2_in_use = sorted(r["bag_pand_id"] for r in h2_rows if r["status"] == "Pand in gebruik")
    exact = [m for m in h2["address_matches"] if m["exact_match"]]
    qos = [o for o in json.loads(bqe.QO_PATH.read_text(encoding="utf-8"))["observations"] if o["document_id"] == DOC]
    obs = classify_observations(qos, vocab, app_cw, eff)
    roof = next(r for r in obs if r["quantity_observation_id"] == "QO-DOC-012-EL-024")
    wall = next(r for r in obs if r["quantity_observation_id"] == "QO-DOC-012-EL-001")
    pv = {"H1": preview(h1, h1_pids, rules, vocab), "H2": preview(h2, h2_pids, rules, vocab),
          "H2_IN_USE_ONLY_INFORMATIVE": preview(h2, h2_in_use, rules, vocab)}

    def flat_of(p):
        if p["scope_aggregate"]:
            a = p["scope_aggregate"]["ROOF_FLAT_AREA"]
            return a.get("value"), a["status"], a.get("method_class")
        v = p["per_pand"][0]["values"]["ROOF_FLAT_AREA"]
        return (v or {}).get("value"), "PREVIEW" if v else "NOT_AVAILABLE", (v or {}).get("method_class")

    def wall_of(p):
        if p["scope_aggregate"]:
            a = p["scope_aggregate"]["OUTER_WALL_GROSS_AREA"]
            return a.get("value"), a["status"]
        v = p["per_pand"][0]["values"]["OUTER_WALL_GROSS_AREA"]
        return (v or {}).get("value"), "PREVIEW" if v else "NOT_AVAILABLE"

    roof_cmp, wall_cmp = [], []
    for h, p in pv.items():
        fv, fst, fm = flat_of(p)
        roof_cmp.append({"hypothesis": h, "bag3d_subject": "ROOF_FLAT_AREA", "bag3d_value": fv, "bag3d_status": fst, "bag3d_method": fm,
                         "historical_value": roof["quantity"], "historical_subject": "ROOF_COVERING_REPORTED_AREA",
                         "difference_historical_minus_3dbag": None if fv is None else str(Decimal(roof["quantity"]) - Decimal(fv)),
                         "pct_of_3dbag": None if not fv else str(((Decimal(roof["quantity"]) - Decimal(fv)) / Decimal(fv) * 100).quantize(Decimal("0.1"))),
                         "kind": "RELATED_SUBJECT_NOT_EQUIVALENT"})
        wv, wst = wall_of(p)
        wall_cmp.append({"hypothesis": h, "bag3d_subject": "OUTER_WALL_GROSS_AREA", "bag3d_value": wv, "bag3d_status": wst,
                         "historical_value": wall["quantity"], "historical_description": wall["description"],
                         "difference_historical_minus_3dbag": None if wv is None else str(Decimal(wall["quantity"]) - Decimal(wv)),
                         "kind": "NEEDS_SEMANTIC_REVIEW (netto gerapporteerd metselwerk != bruto 3D BAG-buitenmuur)"})

    links = bl.load_store()
    xwd = xw.load_store()
    res = json.loads(RESOLUTIONS.read_text(encoding="utf-8"))
    bundle_sha = __import__("hashlib").sha256(MALDENHOF_BUNDLE.read_bytes()).hexdigest()
    h1_row = pand_rows(h1)[0] if h1["panden"] else None
    units_signal = [r for r in obs if r["description"] in ("Deurbelinstallatie", "Postkasten")]
    audit = generalization_audit()
    return {
        "report_version": "doc012_generalization_review_v1",
        "note": ("Read-only discovery + review. Geen building links, geen mapping-besluiten, geen quantity resolution, geen "
                 "app-bundel. 3D BAG-waarden zijn PREVIEW (niet opgeslagen). Geen accuracy-claim."),
        "document": {"document_id": DOC, "address_as_stated": d["address_as_stated"], "address_provenance": d["address_provenance"],
                     "object_name": d["object_name"], "postcode": d["postcode"], "city": d["city"],
                     "construction_year": d["construction_year"], "number_of_units": d["number_of_units"],
                     "source_cluster": cand["source_cluster"], "document_relations": cand["document_relations"],
                     "candidate_report_status": cand["status"], "candidate_review_reasons": cand["review_reasons"]},
        "hypotheses": {
            "H1": {"definition": "scope = alleen het opgegeven adres Meppelweg 819",
                   "query_source": "building.address", "query_provenance": d["address_provenance"],
                   "canonical": True, "snapshot_id": h1["snapshot_id"], "snapshot_path": f"data/bag_snapshots/{h1['snapshot_id']}.json",
                   "query": h1["query"], "requests": len(h1["requests"]),
                   "exact_address_matches": [m["weergavenaam"] for m in h1["address_matches"] if m["exact_match"]],
                   "panden": pand_rows(h1)},
            "H2": {"definition": f"scope = huisnummerbereik {street} {lo}-{hi} uit de objectnaam",
                   "query_source": "document_level_values.object_name", "object_name": d["object_name"],
                   "canonical": False,
                   "why_not_canonical": ("bag_snapshot_v1 legt geen query-bron vast; een range uit de objectnaam is geen document-adres. "
                                         "In data/bag_snapshots zou 'building_links.py record' deze panden als kandidaat accepteren. "
                                         "Daarom alleen als read-only hypothese-opname (zelfde structuur, hash gecontroleerd)."),
                   "capture_id": h2["snapshot_id"], "capture_path": str(h2_path.relative_to(ROOT)),
                   "query": h2["query"], "requests": len(h2["requests"]),
                   "addresses_found": len(exact),
                   "addresses_by_postcode": {pc: sum(1 for m in exact if (m.get("postcode") or "GEEN") == pc)
                                             for pc in sorted({m.get("postcode") or "GEEN" for m in exact})},
                   "addresses_by_parity": {"even": sum(1 for m in exact if m["huisnummer"] % 2 == 0),
                                           "oneven": sum(1 for m in exact if m["huisnummer"] % 2 == 1)},
                   "numbers_in_range_without_address": [n for n in range(lo, hi + 1) if n not in {m["huisnummer"] for m in exact}],
                   "panden": h2_rows},
        },
        "hypothesis_relation": {
            "h1_panden": h1_pids, "h2_panden": h2_pids,
            "h1_subset_of_h2": set(h1_pids) <= set(h2_pids),
            "h2_odd_addresses_all_in_h1_pand": all(any(m["pdok_id"] in p["contains_address_point_of"] for p in h2["panden"] if p["bag_pand_id"] in h1_pids)
                                                   for m in exact if m["huisnummer"] % 2 == 1),
            "h2_even_side_panden": sorted(r["bag_pand_id"] for r in h2_rows if "even" in r["parity"] and r["bag_pand_id"] not in h1_pids),
            "h1_pand_verblijfsobjecten": h1_row["verblijfsobjecten_bag"] if h1_row else None,
            "document_unit_signals": [{"quantity_observation_id": r["quantity_observation_id"], "description": r["description"],
                                       "quantity": r["quantity"], "unit": r["unit"], "page": r["page"]} for r in units_signal],
        },
        "ambiguities": [
            "Het adresveld noemt één adres (819); de objectnaam een bereik (801-883). Geen van beide is automatisch de scope.",
            f"Het bereik {lo}-{hi} bevat in BAG beide straatzijden: oneven (2544AW/AX) en even (2544BV/BW, andere panden). "
            "De objectnaam zegt niets over even/oneven.",
            f"Nummer(s) zonder BAG-adres in het bereik: {', '.join(str(n) for n in [n for n in range(lo, hi + 1) if n not in {m['huisnummer'] for m in exact}][:5])}"
            " (o.a. 801 bestaat niet).",
            "Twee kandidaat-panden aan de even zijde hebben status 'Pand gesloopt' (bouwjaar 1954) en geen 3D BAG-object.",
            "Adressen met huisletter T (bijv. 820T, 882T) hebben in PDOK geen postcode.",
            f"Bouwjaar document {d['construction_year']} vs BAG {h1_row['bouwjaar'] if h1_row else '?'} voor het pand van Meppelweg 819.",
            "Woonplaats in het document is 'Den Haag'; BAG-woonplaatsnaam is 's-Gravenhage (expliciete alias WPA-den-haag).",
        ],
        "historical_quantities": {"count": len(obs), "by_classification": {c: sum(1 for r in obs if r["classification"] == c) for c in CLASSES},
                                  "observations": obs},
        "roof_4711": {"m2_cover": roof, "m1_rows": [r for r in obs if r["element_code"] == "4711" and r["unit"] == "m1"]},
        "bag3d_preview": pv,
        "roof_comparison": {"rule": "RELATED_NOT_EQUIVALENT: naast elkaar, verschil tonen; geen accuracy-claim, geen gemiddelde, geen "
                                    "resolutie, geen winnaar", "rows": roof_cmp},
        "facade_comparison": {"rule": "netto/gerapporteerd metselwerk (2110) is niet de bruto 3D BAG-buitenmuur; geen subject_relation "
                                      "vastgelegd -> NEEDS_SEMANTIC_REVIEW", "rows": wall_cmp},
        "proposed_mappings": [{"mapping_id": m["mapping_id"], "status": xw.effective()[m["mapping_id"]]["status"], "subject_key": m["subject_key"],
                               "match": m["match"], "matches": [r["quantity_observation_id"] for r in obs if
                                                               any(bqe.mapping_matches(m, o) for o in qos if o["quantity_observation_id"] == r["quantity_observation_id"])]}
                              for m in vocab["historical_subject_mappings"] if DOC in (m.get("match") or {}).get("document_ids", [])],
        "app_readiness": {
            "dak-plat": {"crosswalk": "XW-dak-plat-4711-m2", "crosswalk_status": eff["XW-dak-plat-4711-m2"]["status"],
                         "primary": "3D BAG ROOF_FLAT_AREA (per pand DIRECT_MEASURED, of scope-aggregaat GEOMETRY_DERIVED)",
                         "related_context": f"historische dakbedekking {roof['quantity']} m2 (ROOF_COVERING_REPORTED_AREA, na VERIFY van de DOC-012-mapping)",
                         "blocked_by": ["building scope DOC-012 niet bevestigd", "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012 niet geverifieerd"]},
            "dak-hellend": {"crosswalk": "XW-dak-hellend-4712-m2", "crosswalk_status": eff["XW-dak-hellend-4712-m2"]["status"],
                            "note": "DOC-012 heeft geen 4712-rij; alleen 3D BAG ROOF_SLOPED_AREA zou beschikbaar zijn"},
            "gevel-metselwerk": {"crosswalk": "XW-gevel-metselwerk-2110-m2", "crosswalk_status": eff["XW-gevel-metselwerk-2110-m2"]["status"],
                                 "note": "geen gedeeld hoeveelheidsonderwerp (netto vs bruto)"},
            "bundle_generated": False,
        },
        "generalization_audit": audit,
        "mjop_app_audit": {"ref": "MJOP-App 9be178c23f9789dd49e7de7e9bb9bc0fb936c14e (src/, index.html, debug/)",
                           "hits": [{"file": "src/quantity.js", "line": 104, "classification": "NOT_A_PROBLEM",
                                     "reason": "COMMENT: voorbeeld '425.80' -> '425,80' bij formatSourceValue"}]},
        "state": {"building_link_records_for_doc": sum(1 for r in links["records"] if r["document_id"] == DOC),
                  "building_link_records_total": len(links["records"]),
                  "crosswalk_decisions": sorted(r["decision_id"] for r in xwd["records"]),
                  "quantity_resolutions": len(res["records"]),
                  "maldenhof_bundle_sha256": bundle_sha, "maldenhof_bundle_unchanged": bundle_sha == MALDENHOF_BUNDLE_SHA256},
    }


def _v(x):
    return "—" if x is None else str(x)


def render(r):
    H1, H2, rel = r["hypotheses"]["H1"], r["hypotheses"]["H2"], r["hypothesis_relation"]
    L = ["# Quantity Engine Generalization v1 — DOC-012 (review, read-only)", "", r["note"], "",
         f"Document: {r['document']['address_as_stated']} · {r['document']['postcode']} {r['document']['city']} · objectnaam "
         f"\"{r['document']['object_name']}\" · bouwjaar {r['document']['construction_year']} · cluster {r['document']['source_cluster']}", "",
         "## A. Scope-hypotheses", "",
         "| | Definitie | Query-bron | Canoniek | Opname | Adressen | Panden |", "|---|---|---|---|---|---|---|",
         f"| H1 | {H1['definition']} | `{H1['query_source']}` (p.{H1['query_provenance']['page']}) | ja | `{H1['snapshot_id']}` | "
         f"{len(H1['exact_address_matches'])} | {len(H1['panden'])} |",
         f"| H2 | {H2['definition']} | `{H2['query_source']}` | **nee** | `{H2['capture_id']}` | {H2['addresses_found']} "
         f"({H2['addresses_by_parity']['oneven']} oneven, {H2['addresses_by_parity']['even']} even) | {len(H2['panden'])} |", "",
         f"H2 is niet canoniek: {H2['why_not_canonical']}", "",
         f"Relatie: H1-pand ⊂ H2: {rel['h1_subset_of_h2']}; alle oneven adressen van H2 liggen in het H1-pand: "
         f"{rel['h2_odd_addresses_all_in_h1_pand']}; even zijde = {len(rel['h2_even_side_panden'])} andere panden. "
         f"H1-pand heeft {rel['h1_pand_verblijfsobjecten']} verblijfsobjecten; het document noemt "
         + ", ".join(f"{s['description']} {s['quantity']} {s['unit']}" for s in rel["document_unit_signals"]) + ".", "",
         "## B. BAG-panden en adressen (H2 bevat H1)", "",
         "| BAG-pand | In H1 | Huisnummers | Zijde | Postcodes | VBO (BAG) | Bouwjaar | Gebruiksdoel | Status | 3D BAG |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for p in H2["panden"]:
        nums = p["huisnummers"]
        L.append(f"| {p['bag_pand_id']} | {'ja' if p['bag_pand_id'] in rel['h1_panden'] else 'nee'} | "
                 f"{nums[0]}–{nums[-1]} ({p['address_count_in_query']} adr.) | {'/'.join(p['parity'])} | {', '.join(p['postcodes'])} | "
                 f"{_v(p['verblijfsobjecten_bag'])} | {_v(p['bouwjaar'])} | {p['gebruiksdoel']} | {p['status']} | "
                 f"{'ja' if p['threedbag_available'] else 'nee'} |")
    L += ["", "Ambiguïteiten:", ""] + [f"- {a}" for a in r["ambiguities"]]
    hq = r["historical_quantities"]
    L += ["", "## C. Historische hoeveelheden (51 observations)", "",
          "Classificatie: " + ", ".join(f"{k} {v}" for k, v in hq["by_classification"].items()) + ".", "",
          "| Observation | Code | Omschrijving | Hoeveelheid | Klasse | Onderwerp / relatie | App-crosswalk |", "|---|---|---|---|---|---|---|"]
    for o in hq["observations"]:
        if o["classification"] in ("NOT_MEASURED_QUANTITY", "NO_3DBAG_COUNTERPART") and o["element_code"] != "4711":
            continue
        relt = f"{o['possible_subject']}" + (f" ~ {o['subject_relation']['related_subject']}" if o["subject_relation"] else "")
        L.append(f"| {o['quantity_observation_id']} (p.{o['page']}) | {_v(o['element_code'])} | {o['description']} | {o['quantity']} {o['unit']} | "
                 f"{o['classification']} | {_v(relt if o['possible_subject'] else None)} | {', '.join(o['possible_app_crosswalk']) or '—'} |")
    L.append(f"\nOverige {sum(1 for o in hq['observations'] if o['classification'] in ('NOT_MEASURED_QUANTITY', 'NO_3DBAG_COUNTERPART') and o['element_code'] != '4711')} "
             "observations: NO_3DBAG_COUNTERPART of NOT_MEASURED_QUANTITY (volledige lijst in de JSON).")
    for key, title in (("H1", "D. 3D BAG-preview H1"), ("H2", "E. 3D BAG-preview H2"),
                       ("H2_IN_USE_ONLY_INFORMATIVE", "E2. Informatief: H2 alleen panden 'in gebruik'")):
        p = r["bag3d_preview"][key]
        L += ["", f"## {title} ({p['pand_count']} pand(en); preview, niet opgeslagen)", "",
              "| BAG-pand | " + " | ".join(SUBJECT_ORDER) + " |", "|---" * (len(SUBJECT_ORDER) + 1) + "|"]
        for row in p["per_pand"]:
            L.append(f"| {row['bag_pand_id']} | " + " | ".join(_v((row['values'][k] or {}).get('value')) if row['values'][k] else "NOT_AVAILABLE"
                                                           for k in SUBJECT_ORDER) + " |")
        if p["scope_aggregate"]:
            L.append("| **scope-som** | " + " | ".join(
                (p["scope_aggregate"][k].get("value") or p["scope_aggregate"][k]["status"]) for k in SUBJECT_ORDER) + " |")
            np_ = [k for k in SUBJECT_ORDER if p["scope_aggregate"][k]["status"] == "NOT_PUBLISHED"]
            if np_:
                L.append(f"\nNOT_PUBLISHED ({', '.join(np_)}): ontbrekende pandwaarde(n) "
                         f"{', '.join(p['scope_aggregate'][np_[0]]['missing_bag_pand_ids'])} — een ontbrekende waarde telt nooit als 0.")
    L += ["", "## F. Dakvergelijking (RELATED_NOT_EQUIVALENT — geen accuracy-claim)", "",
          "| Hypothese | 3D BAG ROOF_FLAT_AREA | Status | Historisch (ROOF_COVERING_REPORTED_AREA) | Verschil | % |", "|---|---|---|---|---|---|"]
    L += [f"| {c['hypothesis']} | {_v(c['bag3d_value'])} | {c['bag3d_status']} | {c['historical_value']} m2 | "
          f"{_v(c['difference_historical_minus_3dbag'])} | {_v(c['pct_of_3dbag'])} |" for c in r["roof_comparison"]["rows"]]
    L += ["", r["roof_comparison"]["rule"] + ".", "",
          "4711 apart houden: " + "; ".join(f"{x['description']} {x['quantity']} {x['unit']} ({x['classification']})" for x in r["roof_4711"]["m1_rows"])
          + " — niet bij de dakbedekking optellen.", "",
          "## G. Gevelvergelijking", "",
          "| Hypothese | 3D BAG OUTER_WALL_GROSS_AREA | Status | Historisch 2110 metselwerk | Verschil |", "|---|---|---|---|---|"]
    L += [f"| {c['hypothesis']} | {_v(c['bag3d_value'])} | {c['bag3d_status']} | {c['historical_value']} m2 | {_v(c['difference_historical_minus_3dbag'])} |"
          for c in r["facade_comparison"]["rows"]]
    L += ["", r["facade_comparison"]["rule"] + ".", "", "## H. Voorgestelde mappings (NIET geverifieerd)", ""]
    L += [f"- `{m['mapping_id']}` → {m['subject_key']} ({m['status']}); exacte match {json.dumps(m['match'], ensure_ascii=False)}; "
          f"matcht: {', '.join(m['matches'])}" for m in r["proposed_mappings"]]
    a = r["app_readiness"]["dak-plat"]
    L += ["", "## I. App-readiness (conceptueel; geen bundel gegenereerd)", "",
          f"- dak-plat ({a['crosswalk']} {a['crosswalk_status']}): PRIMARY {a['primary']}; RELATED_CONTEXT {a['related_context']}.",
          f"  Geblokkeerd door: {'; '.join(a['blocked_by'])}.",
          f"- dak-hellend: {r['app_readiness']['dak-hellend']['note']}.",
          f"- gevel-metselwerk: {r['app_readiness']['gevel-metselwerk']['note']}.", "",
          "## J. Generalisatie-audit", "",
          "Gezocht naar: " + ", ".join(AUDIT_PATTERNS) + " in scripts/, tests/, vocabularies/, schemas/. "
          + ", ".join(f"{k} {v}" for k, v in sorted(__import__('collections').Counter(h['classification'] for h in r['generalization_audit']).items())) + ".", "",
          "| Bestand | Klasse | Patronen | Toelichting |", "|---|---|---|---|"]
    L += [f"| `{h['file']}` | {h['classification']} | {', '.join(h['patterns']) or '—'} | {h['reason'] or '—'} |"
          for h in r["generalization_audit"] if h["classification"] != "TEST_ONLY"]
    L.append(f"\nPlus {sum(1 for h in r['generalization_audit'] if h['classification'] == 'TEST_ONLY')} testbestanden/fixtures (TEST_ONLY).")
    L.append("MJOP-App (" + r["mjop_app_audit"]["ref"] + "): " + "; ".join(f"`{h['file']}:{h['line']}` {h['classification']} ({h['reason']})"
                                                                        for h in r["mjop_app_audit"]["hits"]) + ".")
    st = r["state"]
    L += ["", f"Stand: building links voor DOC-012 {st['building_link_records_for_doc']} (totaal {st['building_link_records_total']}); "
              f"crosswalk-besluiten {', '.join(st['crosswalk_decisions'])}; quantity resolutions {st['quantity_resolutions']}; "
              f"Maldenhof-bundel ongewijzigd: {st['maldenhof_bundle_unchanged']}.", "",
          "## K. Menselijke beslissingen nodig", "",
          "SCOPE DECISION DOC-012", "",
          "- [ ] H1 — alleen Meppelweg 819 (pand " + ", ".join(rel["h1_panden"]) + ")",
          f"- [ ] H2 — volledige VvE Meppelweg {H2['query']['number']} ({len(H2['panden'])} panden, beide straatzijden)",
          "- [ ] anders / UNKNOWN", "", "Per kandidaat-pand:", "",
          "| BAG-pand | Adressen | CONFIRM | REJECT |", "|---|---|---|---|"]
    L += [f"| {p['bag_pand_id']} | {p['huisnummers'][0]}–{p['huisnummers'][-1]} ({'/'.join(p['parity'])}, {p['status']}) | [ ] | [ ] |" for p in H2["panden"]]
    L += ["", "Daarna (pas na de scope):", "",
          "- [ ] VERIFY / REJECT `HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012`",
          "- [ ] (later) quantity resolution plat dak — niet in deze milestone", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    r = build()
    js, md = json.dumps(r, ensure_ascii=False, indent=1) + "\n", render(r)
    if a.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("doc012 review up-to-date" if ok else "doc012 review NIET up-to-date")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(json.dumps({"H1": r["hypotheses"]["H1"]["snapshot_id"], "H2": r["hypotheses"]["H2"]["capture_id"],
                      "classes": r["historical_quantities"]["by_classification"],
                      "audit": [(h["file"], h["classification"]) for h in r["generalization_audit"] if h["classification"].startswith("GENERIC")]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
