"""Building quantity evidence v1 + 3D BAG vs historisch-vergelijking.

Zie docs/building_link_3dbag_evidence_v1.md.

Leest (read-only):
  data/building_links/building_link_records.json      ACTIVE + CONFIRMED links (menselijk)
  data/bag_snapshots/*.json                            ruwe PDOK/BAG/3D BAG-antwoorden
  data/quantity_observations/quantity_observations_v1.json
  vocabularies/quantity_subjects_v1.json               onderwerpen + 3D BAG-regels + voorgestelde mappings
  data/crosswalk_decisions/crosswalk_decision_records.json  menselijke verificatie van mappings

Schrijft (afgeleid):
  data/quantity_evidence/building_quantity_evidence_v1.json
  reports/quantity/3dbag_vs_historical_v1.json / .md

Regels:
- building_id = 'BAG:' + gesorteerde, ontdubbelde, door een mens bevestigde pand-ID's van het document
  ('+'-gescheiden): de gebouwscope. Volgorde maakt niet uit. Nooit afgeleid uit document-ID's.
- 3D BAG-evidence: per bevestigd pand per ACTIEVE regel, waarde exact (geen afronding), status PROPOSED.
  building_id = 'BAG:<pand>'. Deze per-pand-evidence blijft altijd bestaan.
- Gebouwscope met meerdere panden: per onderwerp uit scope_aggregation_rules één AFGELEIDE evidence
  (GEOMETRY_DERIVED, SUM van de child evidence, exact Decimal) met building_id = de scope en verwijzingen naar
  alle child evidence, panden, snapshots en links. Mist één pandwaarde, dan wordt het aggregaat NIET
  gepubliceerd (nooit als 0 tellen) en staat het in scope_aggregates_not_published.
- Historische evidence: alleen quantity observations van een document met ACTIVE links, alleen voor een
  mapping (element_code + eenheid -> onderwerp) die door een mens is geverifieerd. Een mapping kan via 'match'
  beperkt zijn tot bepaalde documenten en exacte omschrijving/locatie (geen fuzzy matching). Meerdere rijen per
  onderwerp worden NIET opgeteld.
- Vergelijking: historisch vs. 3D BAG van dezelfde gebouwscope (enkel pand of scope-aggregaat); verschil =
  historisch - 3D BAG, percentage t.o.v. 3D BAG. Geen score, geen gemiddelde van bronnen, geen keuze.
- Een historisch onderwerp dat volgens subject_relations RELATED_NOT_EQUIVALENT is aan een 3D BAG-onderwerp
  (bijv. ROOF_COVERING_REPORTED_AREA ~ ROOF_FLAT_AREA) wordt alleen als bronverschil/andere definitie getoond
  (comparison_kind RELATED_SUBJECT_NOT_EQUIVALENT) en telt niet mee in de verschilstatistiek.
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bag3d_quantity_rules as rules_mod  # noqa: E402
import bag_snapshots as bs  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import quantity_evidence as qe  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QO_PATH = ROOT / "data" / "quantity_observations" / "quantity_observations_v1.json"
OUT_EVIDENCE = ROOT / "data" / "quantity_evidence" / "building_quantity_evidence_v1.json"
OUT_JSON = ROOT / "reports" / "quantity" / "3dbag_vs_historical_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "3dbag_vs_historical_v1.md"
BUILDER_VERSION = "building_quantity_evidence_v1.0.0"
BANDS = (("WITHIN_5_PCT", Decimal(5)), ("5_TO_15_PCT", Decimal(15)))


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def building_id_for(pand_ids):
    """Gebouwscope: 'BAG:' + gesorteerde, ontdubbelde pand-ID's. Volgorde-onafhankelijk; één pand = 'BAG:<id>'."""
    ids = sorted({str(p) for p in pand_ids})
    if not ids:
        raise ValueError("een gebouwscope heeft minstens één bevestigd pand nodig")
    return "BAG:" + "+".join(ids)


def scope_aggregate(scope_pand_ids, subject, rule, children_by_pand, link_ids):
    """Afgeleide scope-evidence: SUM van de per-pand-evidence (exact Decimal). Geeft (evidence, None) of
    (None, niet-gepubliceerd-record) als een pand geen (OK-)waarde heeft. Een ontbrekende waarde is nooit 0."""
    building_id = building_id_for(scope_pand_ids)
    pids = sorted({str(p) for p in scope_pand_ids})
    missing = [p for p in pids if p not in children_by_pand or children_by_pand[p].get("value") is None]
    if missing:
        return None, {"building_id": building_id, "subject_key": subject["subject_key"], "rule_id": rule["rule_id"],
                      "bag_pand_ids": pids, "missing_bag_pand_ids": missing,
                      "reason": "CHILD_EVIDENCE_MISSING_NOT_PUBLISHED"}
    children = [children_by_pand[p] for p in pids]
    total = sum((Decimal(c["value"]) for c in children), Decimal(0))
    units = {c["unit_normalized"] for c in children}
    if units != {subject["unit"]}:
        return None, {"building_id": building_id, "subject_key": subject["subject_key"], "rule_id": rule["rule_id"],
                      "bag_pand_ids": pids, "missing_bag_pand_ids": [], "reason": "CHILD_UNIT_MISMATCH_NOT_PUBLISHED"}
    child_ids = [c["evidence_id"] for c in children]
    sid = qe.make_building_subject_id(building_id, subject["subject_key"], subject["unit"])
    calc = {"rule_id": rule["rule_id"], "rule_version": rule["rule_version"], "formula": rule["formula"],
            "input_evidence_ids": child_ids,
            "raw_inputs": {c["source_ref"]["bag_pand_id"]: c["value"] for c in children}}
    ev = qe.make_evidence(
        building_id=building_id,
        subject={"subject_id": sid, "subject_key": subject["subject_key"], "element_code_internal": None,
                 "subject_text": f"{subject['label_nl']} — som over {len(pids)} bevestigde panden", "location_scope": None,
                 "material_normalized": None, "quantity_kind": subject["quantity_kind"]},
        value=str(total), unit_normalized=subject["unit"], method_class="GEOMETRY_DERIVED", source_type="3D_BAG",
        source_ref={"aggregation": "SUM_OVER_CONFIRMED_PANDEN", "bag_pand_ids": pids, "child_evidence_ids": child_ids,
                    "child_rule_ids": sorted({c["source_ref"]["rule_id"] for c in children}),
                    "snapshot_ids": sorted({c["source_ref"]["snapshot_id"] for c in children}),
                    "building_link_ids": sorted(link_ids), "missing_bag_pand_ids": []},
        calculation=calc, created_by=BUILDER_VERSION,
        input_hashes={"child_evidence_ids": child_ids})
    return ev, None


def bag3d_evidence(pand_id, snapshot, rules, subjects_by_key, link_ids):
    pand = next(p for p in snapshot["panden"] if p["bag_pand_id"] == pand_id)
    tb = pand.get("threedbag") or {}
    attrs = tb.get("attributes")
    building_id = building_id_for([pand_id])
    out, not_available = [], []
    for res in rules_mod.apply_rules(attrs, rules):
        rule = next(r for r in rules if r["rule_id"] == res["rule_id"])
        if res["status"] != "OK":
            not_available.append({"bag_pand_id": pand_id, "rule_id": res["rule_id"], "status": res["status"],
                                  "missing_fields": res["missing_fields"]})
            continue
        subj = subjects_by_key[rule["subject_key"]]
        sid = qe.make_building_subject_id(building_id, subj["subject_key"], subj["unit"])
        calc = None
        if rule["method_class"] == "GEOMETRY_DERIVED":
            calc = {"rule_id": rule["rule_id"], "rule_version": rule["rule_version"], "formula": rule["formula"],
                    "input_evidence_ids": [], "raw_inputs": res["raw_inputs"]}
        out.append(qe.make_evidence(
            building_id=building_id,
            subject={"subject_id": sid, "subject_key": subj["subject_key"], "element_code_internal": None,
                     "subject_text": subj["label_nl"], "location_scope": None, "material_normalized": None,
                     "quantity_kind": subj["quantity_kind"]},
            value=res["value"], unit_normalized=subj["unit"], method_class=rule["method_class"], source_type="3D_BAG",
            source_ref={"bag_pand_id": pand_id, "snapshot_id": snapshot["snapshot_id"], "fields": rule["fields"],
                        "raw_inputs": res["raw_inputs"], "rule_id": rule["rule_id"], "rule_version": rule["rule_version"],
                        "url": tb.get("url"), "fetched_at": tb.get("fetched_at"), "api_version": tb.get("api_version"),
                        "response_sha256": tb.get("response_sha256"), "live_api_status": snapshot.get("live_api_status"),
                        "building_link_ids": link_ids},
            calculation=calc, created_by=BUILDER_VERSION,
            input_hashes={"snapshot_id": snapshot["snapshot_id"]}))
    return out, not_available


def mapping_matches(m, qo):
    """Exacte match van een historische onderwerp-mapping op een quantity observation (geen fuzzy matching)."""
    el = qo["element"]
    if el["element_code_internal"] != m["element_code_internal"] or qo["unit_normalized"] != m["unit_normalized"]:
        return False
    match = m.get("match") or {}
    if "document_ids" in match and qo["document_id"] not in match["document_ids"]:
        return False
    if "element_description_original_exact" in match and el.get("element_description_original") not in match["element_description_original_exact"]:
        return False
    if "location_original_exact" in match and el.get("location_original") not in match["location_original_exact"]:
        return False
    return True


def related_subjects(vocab, subject_key, relation="RELATED_NOT_EQUIVALENT"):
    """{andere subject_key: relation_id} voor onderwerpen die met subject_key verwant maar niet gelijk zijn."""
    out = {}
    for r in vocab.get("subject_relations", []):
        if r["relation"] == relation and subject_key in r["subjects"]:
            for k in r["subjects"]:
                if k != subject_key:
                    out[k] = r["relation_id"]
    return out


def build(links_store=None, snapshots=None, quantity_observations=None, subjects_vocab=None, crosswalk_effective=None):
    links_store = links_store if links_store is not None else bl.load_store()
    snapshots = snapshots if snapshots is not None else bs.load_snapshots()
    qos = quantity_observations if quantity_observations is not None else \
        json.loads(QO_PATH.read_text(encoding="utf-8"))["observations"]
    rules, vocab = rules_mod.load_rules() if subjects_vocab is None else \
        ([r for r in subjects_vocab["bag3d_rules"] if r["status"] == "ACTIVE"], subjects_vocab)
    eff = crosswalk_effective if crosswalk_effective is not None else xw.effective()
    subjects_by_key = {s["subject_key"]: s for s in vocab["subjects"]}
    verified_maps = [m for m in vocab["historical_subject_mappings"] if eff.get(m["mapping_id"], {}).get("status") == "VERIFIED"]
    snap_by_id = {s["snapshot_id"]: s for s in snapshots}

    active = [r for r in links_store["records"] if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED"]
    links_by_doc = defaultdict(list)
    for r in active:
        links_by_doc[r["document_id"]].append(r)

    evidence, not_available, notes = [], [], []
    bag_by_building_subject = defaultdict(list)
    seen_pand = set()
    for doc, recs in sorted(links_by_doc.items()):
        for r in sorted(recs, key=lambda x: x["bag_pand_id"]):
            if r["bag_pand_id"] in seen_pand:
                continue
            snap = snap_by_id.get(r["evidence"]["snapshot_id"])
            if snap is None:
                notes.append({"document_id": doc, "bag_pand_id": r["bag_pand_id"], "note": "SNAPSHOT_MISSING"})
                continue
            seen_pand.add(r["bag_pand_id"])
            link_ids = sorted(x["link_id"] for x in active if x["bag_pand_id"] == r["bag_pand_id"])
            evs, na = bag3d_evidence(r["bag_pand_id"], snap, rules, subjects_by_key, link_ids)
            evidence += evs
            not_available += na
            for e in evs:
                bag_by_building_subject[(e["building_id"], e["quantity_subject"]["subject_key"])].append(e)

    # gebouwscopes met meerdere bevestigde panden -> afgeleide som-evidence (per onderwerp)
    agg_rules = [r for r in vocab.get("scope_aggregation_rules", []) if r["status"] == "ACTIVE"]
    not_published = []
    scopes = {}
    for doc, recs in sorted(links_by_doc.items()):
        pids = sorted({r["bag_pand_id"] for r in recs})
        if len(pids) > 1:
            scopes.setdefault(building_id_for(pids), {"pand_ids": pids, "link_ids": set()})["link_ids"] |= {r["link_id"] for r in recs}
    for scope_id, sc in sorted(scopes.items()):
        for rule in agg_rules:
            for key in rule["applies_to_subjects"]:
                children = {}
                for p in sc["pand_ids"]:
                    evs = [e for e in bag_by_building_subject.get((building_id_for([p]), key), [])]
                    if evs:
                        children[p] = evs[0]
                ev, np_ = scope_aggregate(sc["pand_ids"], subjects_by_key[key], rule, children, sc["link_ids"])
                if ev is not None:
                    evidence.append(ev)
                    bag_by_building_subject[(scope_id, key)].append(ev)
                else:
                    not_published.append(np_)

    qo_by_doc = defaultdict(list)
    for o in qos:
        qo_by_doc[o["document_id"]].append(o)
    hist = []
    for doc, recs in sorted(links_by_doc.items()):
        building_id = building_id_for([r["bag_pand_id"] for r in recs])
        link_ref = ",".join(sorted(r["link_id"] for r in recs))
        for m in verified_maps:
            subj = subjects_by_key[m["subject_key"]]
            sid = qe.make_building_subject_id(building_id, subj["subject_key"], subj["unit"])
            for o in qo_by_doc.get(doc, []):
                if mapping_matches(m, o):
                    e = qe.evidence_from_quantity_observation(o, building_id=building_id, subject_id=sid, building_link_ref=link_ref,
                                                              subject_key=subj["subject_key"], mapping_ref=m["mapping_id"])
                    hist.append((doc, recs, e, o))
                    evidence.append(e)

    comparisons = []
    for doc, recs, e, o in hist:
        subject_key = e["quantity_subject"]["subject_key"]
        same_subject_rows = [x for x in hist if x[0] == doc and x[2]["quantity_subject"]["subject_key"] == subject_key]
        reasons = []
        bag_value = bag_unit = bag_ev_id = bag_method = None
        bag_children = []
        scope_id = building_id_for([r["bag_pand_id"] for r in recs])
        comparison_kind, relation_id, bag_subject_key = "SAME_SUBJECT", None, subject_key
        bags = bag_by_building_subject.get((scope_id, subject_key), [])
        if not bags:
            for other, rel in sorted(related_subjects(vocab, subject_key).items()):
                if bag_by_building_subject.get((scope_id, other)):
                    comparison_kind, relation_id, bag_subject_key = "RELATED_SUBJECT_NOT_EQUIVALENT", rel, other
                    bags = bag_by_building_subject[(scope_id, other)]
                    reasons.append("DIFFERENT_SUBJECT_DEFINITION")
                    break
        if not bags:
            reasons.append("MULTI_PAND_AGGREGATE_NOT_PUBLISHED" if len({r["bag_pand_id"] for r in recs}) > 1 else "NO_3DBAG_VALUE")
        else:
            bag_value, bag_unit, bag_ev_id = bags[0]["value"], bags[0]["unit_normalized"], bags[0]["evidence_id"]
            bag_method = bags[0]["method_class"]
            if bags[0]["source_ref"].get("aggregation"):
                bag_children = list((bags[0].get("calculation") or {}).get("input_evidence_ids") or [])
        if len(same_subject_rows) > 1:
            reasons.append("MULTIPLE_HISTORICAL_ROWS_NOT_SUMMED")
        if bag_unit and bag_unit != e["unit_normalized"]:
            reasons.append("UNIT_MISMATCH")
        if o["requires_human_review"]:
            reasons.append("HISTORICAL_OBSERVATION_REVIEW_REQUIRED")
        abs_diff = pct = None
        if bag_value is not None and "UNIT_MISMATCH" not in reasons:
            h, b = Decimal(e["value"]), Decimal(bag_value)
            abs_diff = h - b
            pct = (abs_diff / b * 100) if b != 0 else None
        band = None
        if pct is not None and comparison_kind == "SAME_SUBJECT":
            a = abs(pct)
            band = next((name for name, lim in BANDS if a <= lim), "ABOVE_15_PCT")
        comparisons.append({
            "document_id": doc, "building_id": building_id_for([r["bag_pand_id"] for r in recs]),
            "bag_pand_ids": sorted(r["bag_pand_id"] for r in recs),
            "subject_key": subject_key,
            "comparison_kind": comparison_kind, "bag3d_subject_key": bag_subject_key if bag_ev_id else None,
            "subject_relation_id": relation_id,
            "historical_evidence_id": e["evidence_id"], "historical_quantity_observation_id": o["quantity_observation_id"],
            "historical_value": e["value"], "historical_unit": e["unit_normalized"],
            "historical_description": o["element"]["element_description_original"], "historical_location": o["element"]["location_original"],
            "bag3d_evidence_id": bag_ev_id, "bag3d_value": bag_value, "bag3d_unit": bag_unit,
            "bag3d_method_class": bag_method, "bag3d_child_evidence_ids": bag_children,
            "absolute_difference": None if abs_diff is None else str(abs_diff),
            "percentage_difference": None if pct is None else str(pct.quantize(Decimal("0.0001"))),
            "difference_band": band,
            "historical_source_cluster": o["source_cluster"],
            "dependency_note": ("zelfde object als " + ", ".join(o["dependency"]["same_object_document_ids"])
                                + ": geen onafhankelijke bevestiging") if o["dependency"]["same_object_document_ids"] else None,
            "review_status": ("NOT_RESOLVABLE_AS_SAME_QUANTITY" if comparison_kind != "SAME_SUBJECT"
                              else "REVIEW_REQUIRED" if reasons else "COMPARED"),
            "mismatch_reasons": sorted(set(reasons)),
        })
    comparisons.sort(key=lambda c: (c["document_id"], c["subject_key"], c["historical_quantity_observation_id"]))
    evidence.sort(key=lambda e: e["evidence_id"])
    return {
        "evidence_store": {"builder_version": BUILDER_VERSION, "note": "Afgeleide evidence (PROPOSED). Resolutie via data/quantity_resolutions.",
                           "evidence": evidence, "bag3d_rules_not_available": not_available,
                           "scope_aggregates_not_published": not_published, "notes": notes},
        "report": build_report(comparisons, links_store, verified_maps, vocab, eff, evidence, not_available, not_published),
    }


def _median(xs):
    return None if not xs else str(median(xs))


def build_report(comparisons, links_store, verified_maps, vocab, eff, evidence, not_available, not_published=()):
    compared = [c for c in comparisons if c["percentage_difference"] is not None and c["comparison_kind"] == "SAME_SUBJECT"]
    related = [c for c in comparisons if c["comparison_kind"] != "SAME_SUBJECT"]
    hist_ev = [e for e in evidence if e["source_type"] == "MJOP_ELEMENT_OVERVIEW"]
    independent = {}
    for e in hist_ev:
        key = (e["building_id"], e["quantity_subject"]["subject_key"])
        independent.setdefault(key, {"evidences": 0, "source_clusters": set()})
        independent[key]["evidences"] += 1
        independent[key]["source_clusters"].add((e.get("dependency") or {}).get("source_cluster") or e["evidence_id"])
    per_subject = {}
    for key in sorted({c["subject_key"] for c in comparisons}):
        cs = [c for c in compared if c["subject_key"] == key]
        per_subject[key] = {
            "comparisons": sum(1 for c in comparisons if c["subject_key"] == key),
            "with_difference": len(cs),
            "median_absolute_difference": _median([abs(Decimal(c["absolute_difference"])) for c in cs]),
            "median_percentage_difference": _median([abs(Decimal(c["percentage_difference"])) for c in cs]),
        }
    active = [r for r in links_store["records"] if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED"]
    docs_multi = sorted({r["document_id"] for r in active if sum(1 for x in active if x["document_id"] == r["document_id"]) > 1})
    summary = {
        "confirmed_building_links": len(active),
        "bag_panden": len({r["bag_pand_id"] for r in active}),
        "documents_with_multiple_panden": docs_multi,
        "bag3d_evidences": sum(1 for e in evidence if e["source_type"] == "3D_BAG"),
        "bag3d_scope_aggregates": sum(1 for e in evidence if e["source_type"] == "3D_BAG" and e["source_ref"].get("aggregation")),
        "scope_aggregates_not_published": len(not_published),
        "historical_evidences": sum(1 for e in evidence if e["source_type"] == "MJOP_ELEMENT_OVERVIEW"),
        "verified_subject_mappings": [m["mapping_id"] for m in verified_maps],
        "unverified_subject_mappings": sorted(m["mapping_id"] for m in vocab["historical_subject_mappings"]
                                             if eff.get(m["mapping_id"], {}).get("status") != "VERIFIED"),
        "comparisons": len(comparisons),
        "comparisons_with_difference": len(compared),
        "comparable_subjects": sorted({(c["building_id"], c["subject_key"]) for c in compared}),
        "related_subject_source_differences": len(related),
        "historical_independent_sources": [
            {"building_id": b, "subject_key": k, "historical_evidences": v["evidences"],
             "independent_source_clusters": len(v["source_clusters"])}
            for (b, k), v in sorted(independent.items())],
        "per_subject": per_subject,
        "median_absolute_difference": _median([abs(Decimal(c["absolute_difference"])) for c in compared]),
        "median_percentage_difference": _median([abs(Decimal(c["percentage_difference"])) for c in compared]),
        "within_5_pct": sum(1 for c in compared if c["difference_band"] == "WITHIN_5_PCT"),
        "5_to_15_pct": sum(1 for c in compared if c["difference_band"] == "5_TO_15_PCT"),
        "above_15_pct": sum(1 for c in compared if c["difference_band"] == "ABOVE_15_PCT"),
        "missing_matches": sum(1 for c in comparisons if "NO_3DBAG_VALUE" in c["mismatch_reasons"]),
        "unit_mismatches": sum(1 for c in comparisons if "UNIT_MISMATCH" in c["mismatch_reasons"]),
        "multi_pand_aggregate_not_published": sum(1 for c in comparisons if "MULTI_PAND_AGGREGATE_NOT_PUBLISHED" in c["mismatch_reasons"]),
        "multiple_historical_rows_not_summed": sum(1 for c in comparisons if "MULTIPLE_HISTORICAL_ROWS_NOT_SUMMED" in c["mismatch_reasons"]),
        "bag3d_rules_not_available": len(not_available),
    }
    summary["comparable_subjects"] = [list(x) for x in summary["comparable_subjects"]]
    return {"report_version": "3dbag_vs_historical_v1",
            "note": ("Feitelijke verschillen historisch - 3D BAG (percentage t.o.v. 3D BAG). Geen kwaliteitsscore, "
                     "geen gemiddelde van bronnen, geen keuze. Afhankelijke documenten zijn geen onafhankelijke bevestiging. "
                     "Een verschil tussen verwante maar niet gelijke onderwerpen (RELATED_SUBJECT_NOT_EQUIVALENT) is een "
                     "bronverschil/andere definitie en telt niet mee in de verschilstatistiek."),
            "summary": summary, "comparisons": comparisons}


def render_report(rep, candidates=None):
    s = rep["summary"]
    L = ["# 3D BAG vs historisch v1", "", rep["note"], "",
         "## Samenvatting", "",
         f"- Bevestigde building links: {s['confirmed_building_links']} (BAG-panden: {s['bag_panden']}; "
         f"documenten met meerdere panden: {', '.join(s['documents_with_multiple_panden']) or '—'})",
         f"- 3D BAG-evidences: {s['bag3d_evidences']} (waarvan scope-aggregaten: {s['bag3d_scope_aggregates']}; "
         f"niet gepubliceerd wegens ontbrekende pandwaarde: {s['scope_aggregates_not_published']}); "
         f"historische evidences: {s['historical_evidences']}",
         f"- Geverifieerde onderwerp-mappings: {', '.join(s['verified_subject_mappings']) or '—'}",
         f"- Niet (menselijk) geverifieerde mappings: {', '.join(s['unverified_subject_mappings']) or '—'}",
         f"- Vergelijkingen: {s['comparisons']} (met verschil: {s['comparisons_with_difference']})",
         f"- Mediaan absoluut verschil: {s['median_absolute_difference'] or '—'}; mediaan % verschil: {s['median_percentage_difference'] or '—'}",
         f"- Binnen 5%: {s['within_5_pct']}; 5–15%: {s['5_to_15_pct']}; >15%: {s['above_15_pct']}",
         f"- Geen 3D BAG-waarde: {s['missing_matches']}; eenheidsverschil: {s['unit_mismatches']}; "
         f"meerdere panden zonder gepubliceerd aggregaat: {s['multi_pand_aggregate_not_published']}; meerdere historische rijen (niet opgeteld): "
         f"{s['multiple_historical_rows_not_summed']}",
         f"- Bronverschillen tussen verwante, niet-gelijke onderwerpen (andere definitie; niet in de statistiek): "
         f"{s['related_subject_source_differences']}"]
    for h in s["historical_independent_sources"]:
        L.append(f"- Historisch {h['subject_key']} ({h['building_id']}): {h['historical_evidences']} evidence(s) uit "
                 f"{h['independent_source_clusters']} onafhankelijke bron(cluster)(s)")
    if candidates is not None:
        L.append(f"- Building-link-kandidaten: {candidates['summary']['by_status']} "
                 "(zie reports/quantity/building_link_candidates_v1.md)")
    L.append("")
    if not rep["comparisons"]:
        L += ["**Nog geen vergelijkingen.** Daarvoor zijn nodig: (1) een BAG/3D BAG-snapshot per document "
              "(netwerktoegang tot api.pdok.nl en api.3dbag.nl), (2) een door een mens bevestigde building link, "
              "(3) een door een mens geverifieerde onderwerp-mapping (bijv. HSM-ROOF_FLAT_AREA-4711-m2).", ""]
    else:
        L += ["| Document | Pand(en) | Onderwerp historisch | Onderwerp 3D BAG | Historisch | 3D BAG | Verschil | % | Cluster | Status / redenen |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for c in rep["comparisons"]:
            pand = ", ".join(c["bag_pand_ids"]) if len(c["bag_pand_ids"]) <= 3 else f"{len(c['bag_pand_ids'])} panden"
            L.append(f"| {c['document_id']} | {pand} | {c['subject_key']} | {c['bag3d_subject_key'] or '—'} | "
                     f"{c['historical_value']} {c['historical_unit']} | {c['bag3d_value'] or '—'} {c['bag3d_unit'] or ''} | "
                     f"{c['absolute_difference'] or '—'} | {c['percentage_difference'] or '—'} | {c['historical_source_cluster']} | "
                     f"{c['review_status']} {', '.join(c['mismatch_reasons'])} |")
        L.append("")
    return "\n".join(L)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Building quantity evidence v1 + vergelijking")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    res = build()
    cand = bl.build_candidates()
    outputs = ((OUT_EVIDENCE, dumps(res["evidence_store"])), (OUT_JSON, dumps(res["report"])),
               (OUT_MD, render_report(res["report"], cand)))
    if args.check:
        ok = all(p.exists() and p.read_text(encoding="utf-8") == c for p, c in outputs)
        print("building quantity evidence up-to-date" if ok else "building quantity evidence NIET up-to-date")
        return 0 if ok else 1
    for p, c in outputs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(c, encoding="utf-8", newline="\n")
    s = res["report"]["summary"]
    print(f"{s['bag3d_evidences']} 3D BAG-evidences, {s['historical_evidences']} historische evidences, {s['comparisons']} vergelijkingen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
