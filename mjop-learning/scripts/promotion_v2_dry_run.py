#!/usr/bin/env python3
"""
promotion_v2_dry_run.py  (PROMOTION v2 - volledige downstream dry-run vanaf batch1_v1)

Bouwt de downstream-lagen opnieuw op met de deterministische handoff-laag
data/extracted_deterministic/batch1_v1/ als bron - ZONDER canonieke data te wijzigen:

  1. normalisatie      normalize_batch.normalize_record op batch1_v1 (external_element_coding
                       voor DOC-004 blijft extern)
  2. gesimuleerde      de 220 oude accepts alleen als analyse-input: EXACT_MATCH_CANDIDATE met
     verified-laag     gelijke genormaliseerde waarden -> gesimuleerde accept; al het andere
                       blijft zoals de normalisatie het zette (review_required)
  3. price obs.        bronwaarden (observation_id, bedragen, Stj/Cy, bronweergaven) blijven die
                       van de canonieke xpdf-bronlaag; alleen de koppelstap wordt vervangen door
                       een EXACTE koppeling aan batch1_v1 (zelfde document + pagina + brontekst,
                       euro/witruimte genegeerd - dezelfde sleutel als record_validation).
                       Bedragen worden tegen batch1_v1 gecontroleerd; een verschil is blocking.
  4. normalized PO, comparability, kengetallen: de BESTAANDE scripts, ongewijzigd, op een
                       tijdelijke projectroot waarin data/verified en data/price_observations
                       door de dry-run-lagen zijn vervangen.
  5. vergelijking      per observation_id, per paar (frozenset van observation_ids - nooit
                       PAIR-volgnummers), per human decision en per kengetal_id.

Uitvoer: data/promotion_v2_dry_run/batch1_v1/ (buiten alle canonieke globs) en
reports/promotion_v2_batch1_v1.json. UTF-8, LF, gesorteerde sleutels, geen tijdstempels.

Waarom de PO-bronwaarden niet opnieuw uit de PDF's worden gehaald: dat vereist xpdf 4.06
(alleen lokaal). De canonieke PO-bronlaag is met xpdf gebouwd; deze dry-run vervangt alleen
wat uit de oude extractieroute (data/verified) kwam.

Gebruik:
    python3 scripts/promotion_v2_dry_run.py            # bouwt en schrijft
    python3 scripts/promotion_v2_dry_run.py --check    # herbouwt in tmp en vergelijkt byte-voor-byte
"""
import argparse
import copy
import filecmp
import glob
import json
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import build_kengetallen as bk  # noqa: E402
import normalize_batch as nb  # noqa: E402
import normalize_price_observations as npo  # noqa: E402
import promote_deterministic_batch as pdb  # noqa: E402

TOOL_VERSION = "promotion_v2_dry_run_v1.0.0"
OUT_DIR = os.path.join("data", "promotion_v2_dry_run", "batch1_v1")
REPORT = os.path.join("reports", "promotion_v2_batch1_v1.json")
LINK_METHOD = "exact_page_source_text_v1"
LINK_REASONS = {"no_extraction_link", "action_not_normalized", "conflicting_action_normalization",
                "ambiguous_extraction_link", "element_unlinked_in_deterministic_extraction"}
PO_PATH = os.path.join("data", "price_observations", "price_observations_batch1.json")
NORM_PO_PATH = os.path.join("data", "price_observations", "price_observations_batch1_normalized.json")
COMP_PATH = os.path.join("data", "comparability", "comparability_batch1.json")
KG_PATH = os.path.join("data", "kengetallen", "kengetallen_batch1.json")
DECISIONS_PATH = os.path.join("data", "review_decisions", "human_decision_records.json")
# velden die alleen hashes/verwijzingen naar invoerbestanden bevatten (platform-/CRLF-afhankelijk)
VOLATILE_KEYS = {"source_file_sha256", "vocabularies_sha256", "inputs", "generated_at", "supersedes"}


def load(root, rel):
    return pdb.load_json(os.path.join(root, rel))


def as_json(obj):
    """Zelfde vorm als een weggeschreven en ingelezen JSON-bestand (bijv. None-sleutels -> "null"),
    zodat vergelijking met de canonieke bestanden zuiver is."""
    return json.loads(json.dumps(obj, ensure_ascii=False))


def strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(x) for x in obj]
    return obj


def lookups(root):
    vd = os.path.join(root, "vocabularies")
    return {k: nb.load_vocab(vd, v) for k, v in
            [("element_type", "element_type"), ("element_code", "element_code"), ("material", "material"),
             ("unit", "unit"), ("defect_type", "defect_type"), ("action", "maintenance_action")]}


# ------------------------------------------------------------------ 1+2. normalisatie en gesimuleerde verified

def field_counts(rec):
    c = Counter()
    for el in rec.get("elements", []):
        for f in ("element_type", "element_code", "material", "unit"):
            if isinstance(el.get(f), dict) and el[f].get("normalized_value") is not None:
                c[f"elements.{f}.normalized"] += 1
    for a in rec.get("maintenance_actions", []):
        for f in ("action", "unit"):
            if isinstance(a.get(f), dict) and a[f].get("normalized_value") is not None:
                c[f"actions.{f}.normalized"] += 1
        c["actions.requires_human_review"] += bool(a.get("requires_human_review"))
    c["elements"] = len(rec.get("elements", []))
    c["maintenance_actions"] = len(rec.get("maintenance_actions", []))
    return dict(sorted(c.items()))


def build_normalized(root, new_records):
    lk = lookups(root)
    out, diffs = {}, {}
    for doc, rec in sorted(new_records.items()):
        n = nb.normalize_record(copy.deepcopy(rec), lk)
        out[doc] = n
        old = pdb.load_canonical(root, "normalized", doc) or {}
        external = nb.uses_external_element_coding(n)
        diffs[doc] = {"old": field_counts(old), "new": field_counts(n), "external_element_coding": external,
                      "new_internal_codes_on_external_document": sum(
                          1 for e in n.get("elements", []) if external and e["element_code"].get("normalized_value"))}
    return out, diffs


def simulate_verified(root, normalized, new_records):
    """Kopie van de genormaliseerde laag + gesimuleerde accepts. data/verified wordt niet aangeraakt."""
    verified = copy.deepcopy(normalized)
    old_ver = {doc: {a["action_id"]: a for a in (pdb.load_canonical(root, "verified", doc) or {}).get(
        "maintenance_actions", [])} for doc in pdb.EXPECTED_DOCUMENTS}
    accepts = pdb.classify_accepts(root, new_records)
    sim = Counter()
    details = []
    for acc in accepts["accepts"]:
        doc, cls = acc["document_id"], acc["classification"]
        if cls != "EXACT_MATCH_CANDIDATE":
            sim["review_required"] += 1
            details.append({"old_action_id": acc["old_action_id"], "document_id": doc,
                            "result": "review_required", "reason": acc.get("reason") or cls})
            continue
        old = old_ver[doc][acc["old_action_id"]]
        acts = {a["action_id"]: a for a in verified[doc]["maintenance_actions"]}
        targets = [acts[i] for i in acc["new_action_ids"]]
        same = all((t.get("action") or {}).get("normalized_value") == (old.get("action") or {}).get("normalized_value")
                   and (t.get("unit") or {}).get("normalized_value") == (old.get("unit") or {}).get("normalized_value")
                   for t in targets)
        if same:
            for t in targets:
                t["requires_human_review"] = False
                t["review_note"] = f"[gesimuleerde accept uit {acc['old_action_id']} - promotion v2 dry-run]"
            sim["simulated_accept"] += 1
            details.append({"old_action_id": acc["old_action_id"], "document_id": doc, "result": "simulated_accept",
                            "new_action_ids": acc["new_action_ids"]})
        else:
            sim["review_required"] += 1
            details.append({"old_action_id": acc["old_action_id"], "document_id": doc, "result": "review_required",
                            "reason": "exact_row_but_normalized_value_differs", "new_action_ids": acc["new_action_ids"]})
    return verified, {"classification": accepts["counts"], "simulation": dict(sorted(sim.items())),
                      "details": details}


# ------------------------------------------------------------------ 3. price observations

def row_index(new_records):
    idx = defaultdict(list)
    for doc, rec in new_records.items():
        for r in pdb.new_rows(rec):
            idx[(doc, r["page"], pdb.source_key((r["text_fragment"] or "").split("\n")[0]))].append(r)
    return idx


def relink(po, verified, new_records):
    """Vervangt uitsluitend de koppelvelden. Returns (nieuwe PO, per observation link-info)."""
    idx = row_index(new_records)
    new = copy.deepcopy(po)
    info = {}
    for o in new["observations"]:
        doc = o["document_id"]
        o["review_reasons"] = [r for r in o["review_reasons"] if r not in LINK_REASONS]
        o["extraction_link"] = {"action_ids": [], "method": LINK_METHOD, "score": None}
        o["element"]["element_id"] = None
        o["element"]["element_code_internal"] = None
        o["action"]["action_normalized"] = None
        o["action"]["action_normalization_basis"] = None
        o["legacy_extracted_cost_years"] = []
        o["extraction_review"] = None
        if doc not in verified:
            o["review_reasons"].append("no_extraction_link")
            o["requires_human_review"] = True
            info[o["observation_id"]] = {"link": "document_not_in_batch"}
            continue
        prim = next(r for r in o["source_representations"] if r["role"] == "primary_financial_row")
        rows = idx.get((doc, prim["page"], pdb.source_key(prim["source_text"])), [])
        acts = {a["action_id"]: a for a in verified[doc]["maintenance_actions"]}
        elements = {e["element_id"]: e for e in verified[doc]["elements"]}
        # bedragcontrole tegen batch1_v1 (alle kandidaatrijen)
        po_amounts = {y: Decimal(v) for y, v in o["annual_amounts"].items()}
        amount_ok = [({str(y): a for y, a in r["years"]} == po_amounts) for r in rows]
        link = {"candidate_rows": len(rows), "amounts_equal": all(amount_ok) if rows else None}
        if not rows:
            o["review_reasons"].append("no_extraction_link")
            link["link"] = "none"
        else:
            cand_acts = [acts[i] for r in rows for i in r["action_ids"]]
            # '<doc>-EL-UNLINKED' is een plaatshouder van de extractor, geen element
            el_ids = sorted({a["element_id"] for a in cand_acts if not a["element_id"].endswith("-EL-UNLINKED")})
            if any(a["element_id"].endswith("-EL-UNLINKED") for a in cand_acts):
                o["review_reasons"].append("element_unlinked_in_deterministic_extraction")
                el_ids = []
            codes = sorted({((elements.get(e) or {}).get("element_code") or {}).get("normalized_value") for e in el_ids}
                           - {None})
            norm = sorted({(a.get("action") or {}).get("normalized_value") for a in cand_acts} - {None})
            if len(rows) == 1:
                o["extraction_link"]["action_ids"] = sorted(rows[0]["action_ids"])
                o["element"]["element_id"] = el_ids[0] if len(el_ids) == 1 else None
                link["link"] = "unique"
            else:
                o["review_reasons"].append("ambiguous_extraction_link")
                link["link"] = "ambiguous"
            # zelfde regel als build_price_observations: alleen bij één eenduidige waarde
            o["element"]["element_code_internal"] = codes[0] if len(codes) == 1 else None
            if len(norm) == 1:
                o["action"]["action_normalized"] = norm[0]
                srcs = sorted({(a.get("action") or {}).get("normalization_source", "vocabulary") for a in cand_acts
                               if (a.get("action") or {}).get("normalized_value")})
                o["action"]["action_normalization_basis"] = "; ".join(srcs)
            else:
                o["review_reasons"].append("action_not_normalized" if not norm else "conflicting_action_normalization")
            linked = [acts[i] for i in o["extraction_link"]["action_ids"]]
            if linked:
                o["extraction_review"] = {
                    "any_requires_human_review": any(a.get("requires_human_review") for a in linked),
                    "human_verification_statuses": [],
                    "review_notes": sorted({a.get("review_note") for a in linked if a.get("review_note")}),
                }
        o["requires_human_review"] = bool(o["review_reasons"])
        info[o["observation_id"]] = link
    new["note"] = (po.get("note", "") + " | PROMOTION v2 DRY-RUN: koppelvelden exact opnieuw bepaald tegen "
                   "data/extracted_deterministic/batch1_v1 (" + LINK_METHOD + "); bronwaarden ongewijzigd.")
    return new, info


PO_CATEGORIES = {
    "A_exact_equal": "alle inhoudsvelden gelijk (alleen koppelmetadata zoals method/score/extraction_review "
                     "en materiaal-herkomstvelden mogen verschillen)",
    "B_link_changed": "extraction_link.action_ids of element_id veranderd",
    "C_action_normalization_changed": "action_normalized/basis veranderd",
    "D_internal_code_changed": "element_code_internal veranderd",
    "E_material_changed": "materiaalwaarde (material_original/material_normalized/material_from_text) veranderd",
    "F_missing_or_new": "observation ontbreekt of is nieuw",
    "G_amount_changed": "bedrag veranderd (KRITIEK)",
}
AMOUNT_FIELDS = ("annual_amounts", "total_value", "total_as_stated", "quantity_value", "unit_price_calculated")


def material_value(norm_obs):
    m = (norm_obs or {}).get("material") or {}
    return (m.get("material_original"), m.get("material_normalized"), m.get("material_from_text"))


def compare_po(old_po, new_po, old_norm, new_norm, link_info):
    old_by = {o["observation_id"]: o for o in old_po["observations"]}
    new_by = {o["observation_id"]: o for o in new_po["observations"]}
    onb = {o["observation_id"]: o for o in old_norm["observations"]}
    nnb = {o["observation_id"]: o for o in new_norm["observations"]}
    counts, per = Counter(), {}
    blocking = []
    for oid in sorted(set(old_by) | set(new_by)):
        cats = []
        a, b = old_by.get(oid), new_by.get(oid)
        if a is None or b is None:
            cats.append("F_missing_or_new")
        else:
            if any(a.get(f) != b.get(f) for f in AMOUNT_FIELDS) or link_info[oid].get("amounts_equal") is False:
                cats.append("G_amount_changed")
                blocking.append({"observation_id": oid, "issue": "amount_changed_or_differs_from_batch1_v1"})
            if a["extraction_link"]["action_ids"] != b["extraction_link"]["action_ids"] or \
                    a["element"]["element_id"] != b["element"]["element_id"]:
                cats.append("B_link_changed")
            if a["action"]["action_normalized"] != b["action"]["action_normalized"] or \
                    a["action"]["action_normalization_basis"] != b["action"]["action_normalization_basis"]:
                cats.append("C_action_normalization_changed")
            if a["element"]["element_code_internal"] != b["element"]["element_code_internal"]:
                cats.append("D_internal_code_changed")
            if material_value(onb.get(oid)) != material_value(nnb.get(oid)):
                cats.append("E_material_changed")
            if not cats:
                cats.append("A_exact_equal")
        for c in cats:
            counts[c] += 1
        per[oid] = {"categories": cats, "link": link_info.get(oid, {}).get("link"),
                    "old": {"element_code_internal": (a or {}).get("element", {}).get("element_code_internal"),
                            "action_normalized": (a or {}).get("action", {}).get("action_normalized"),
                            "material": ((onb.get(oid) or {}).get("material") or {}).get("material_normalized")},
                    "new": {"element_code_internal": (b or {}).get("element", {}).get("element_code_internal"),
                            "action_normalized": (b or {}).get("action", {}).get("action_normalized"),
                            "material": ((nnb.get(oid) or {}).get("material") or {}).get("material_normalized")}}
    return {"old_observations": len(old_by), "new_observations": len(new_by),
            "category_counts": {k: counts.get(k, 0) for k in PO_CATEGORIES},
            "link_counts": dict(sorted(Counter(i.get("link") for i in link_info.values()).items())),
            "amount_blocking": blocking, "per_observation": per}


# ------------------------------------------------------------------ 5. comparability, decisions, kengetallen

def pair_key(p):
    return tuple(sorted(p["observation_ids"]))


def compare_comparability(old, new):
    ob = {pair_key(p): p for p in old["pairs"]}
    nb_ = {pair_key(p): p for p in new["pairs"]}
    res = Counter()
    changed = []
    for k in sorted(set(ob) | set(nb_)):
        if k not in nb_:
            res["disappeared"] += 1
        elif k not in ob:
            res["new"] += 1
        elif ob[k]["class"] == nb_[k]["class"]:
            res["same_class"] += 1
        else:
            res["changed_class"] += 1
            changed.append({"observation_ids": list(k), "old_class": ob[k]["class"], "new_class": nb_[k]["class"]})
    oc = {o["observation_id"]: o["source_cluster"] for o in old["observations"]}
    nc = {o["observation_id"]: o["source_cluster"] for o in new["observations"]}
    cluster_diff = sorted(i for i in set(oc) | set(nc) if oc.get(i) != nc.get(i))
    return {"pairs_old": len(ob), "pairs_new": len(nb_),
            "counts": {k: res.get(k, 0) for k in ("same_class", "changed_class", "new", "disappeared")},
            "changed": changed, "source_clusters_identical": not cluster_diff,
            "source_cluster_differences": cluster_diff,
            "duplicate_documents_old": old.get("duplicate_documents"),
            "duplicate_documents_new": new.get("duplicate_documents")}


def pair_content(p):
    """Paarbeoordeling zonder PAIR-volgnummer en zonder volgorde van de observation_ids."""
    return {k: (sorted(v) if k == "observation_ids" else v) for k, v in p.items() if k != "pair_id"}


def classify_decisions(decisions, old_comp, new_comp, old_norm, new_norm):
    ob = {pair_key(p): p for p in old_comp["pairs"]}
    nb_ = {pair_key(p): p for p in new_comp["pairs"]}
    onb = {o["observation_id"]: strip_volatile(o) for o in old_norm["observations"]}
    nnb = {o["observation_id"]: strip_volatile(o) for o in new_norm["observations"]}
    out, counts = [], Counter()
    for r in decisions["records"]:
        k = tuple(sorted(r["observation_ids"]))
        if k not in nb_:
            cls, why = "PAIR_NO_LONGER_EXISTS", ["pair_not_in_dry_run_comparability"]
        else:
            why = []
            po, pn = pair_content(ob.get(k, {})), pair_content(nb_[k])
            if po != pn:
                why.append("pair_assessment_changed")
            for oid in k:
                if onb.get(oid) != nnb.get(oid):
                    why.append(f"observation_changed:{oid}")
            cls = "INPUT_CHANGED_REVIEW_REQUIRED" if why else "STILL_APPLICABLE"
        counts[cls] += 1
        out.append({"decision_id": r["decision_id"], "status": r["status"], "observation_ids": list(k),
                    "decision": r["decision"], "classification": cls, "reasons": why})
    return {"counts": {k: counts.get(k, 0) for k in ("STILL_APPLICABLE", "INPUT_CHANGED_REVIEW_REQUIRED",
                                                     "PAIR_NO_LONGER_EXISTS")}, "records": out,
            "note": "Alleen gelezen: niets gesuperseded, toegevoegd of herschreven. Koppeling op observation_ids."}


KG_FIELDS = ("status", "source_cluster_ids", "source_cluster_count", "cluster_contributions", "value_exact",
             "value_display", "insufficient_data_reasons")


def compare_kengetallen(old, new):
    ob = {k["kengetal_id"]: k for k in old["kengetallen"]}
    nb_ = {k["kengetal_id"]: k for k in new["kengetallen"]}
    changes = []
    for kid in sorted(set(ob) | set(nb_)):
        a, b = ob.get(kid), nb_.get(kid)
        if a is None or b is None:
            changes.append({"kengetal_id": kid, "change": "new" if a is None else "disappeared",
                            "status": (b or a).get("status")})
            continue
        fields = [f for f in KG_FIELDS if a.get(f) != b.get(f)]
        if fields:
            changes.append({"kengetal_id": kid, "change": "changed", "fields": fields,
                            "old": {f: a.get(f) for f in fields}, "new": {f: b.get(f) for f in fields}})
    # dezelfde kandidaatsleutel onder een andere kengetal_id (bijv. materiaal in de id veranderd)
    by_key = defaultdict(lambda: {"old": [], "new": []})
    for k in old["kengetallen"]:
        by_key[tuple(k["candidate_key"])]["old"].append(k)
    for k in new["kengetallen"]:
        by_key[tuple(k["candidate_key"])]["new"].append(k)
    by_candidate_key = []
    for key, v in sorted(by_key.items()):
        def brief(ks):
            return [{f: k.get(f) for f in ("kengetal_id", "status", "value_display", "source_cluster_count",
                                          "source_cluster_ids", "insufficient_data_reasons")} for k in ks]
        if brief(v["old"]) != brief(v["new"]):
            by_candidate_key.append({"candidate_key": list(key), "old": brief(v["old"]), "new": brief(v["new"])})
    return {"old": len(ob), "new": len(nb_), "unchanged": len(set(ob) & set(nb_)) - sum(
        1 for c in changes if c["change"] == "changed"), "changes": changes, "by_candidate_key": by_candidate_key,
            "summary_old": old.get("summary"), "summary_new": new.get("summary")}


# ------------------------------------------------------------------ orchestratie

def temp_root(root, tmp, verified, po_new):
    """Tijdelijke projectroot: alles verwijst naar de echte repo, behalve data/verified en
    data/price_observations (dry-run) en lege uitvoermappen."""
    for d in ("vocabularies", "schemas", "docs", "reports", "scripts"):
        os.symlink(os.path.join(root, d), os.path.join(tmp, d))
    os.makedirs(os.path.join(tmp, "data"))
    for d in ("raw", "review_decisions", "match_review_decisions"):
        os.symlink(os.path.join(root, "data", d), os.path.join(tmp, "data", d))
    for d in ("verified", "price_observations", "comparability", "kengetallen"):
        os.makedirs(os.path.join(tmp, "data", d))
    for doc, rec in verified.items():
        pdb.write_json(os.path.join(tmp, "data", "verified", f"{doc}.json"), rec)
    shutil.copy(os.path.join(root, "data", "price_observations", "document_relations.json"),
                os.path.join(tmp, "data", "price_observations"))
    pdb.write_json(os.path.join(tmp, PO_PATH), po_new)


def build_all(root):
    check = pdb.check_handoff(root)
    if not check["ok"]:
        raise SystemExit("HANDOFF ONGELDIG - eerst promote_deterministic_batch.py --check groen maken:\n"
                         + "\n".join(check["errors"]))
    new_records = {d: pdb.load_json(os.path.join(root, pdb.BATCH_DIR, f"{d}.json")) for d in pdb.EXPECTED_PASS}
    normalized, norm_diffs = build_normalized(root, new_records)
    verified, accept_sim = simulate_verified(root, normalized, new_records)
    old_po = load(root, PO_PATH)
    po_new, link_info = relink(old_po, verified, new_records)

    with tempfile.TemporaryDirectory() as tmp:
        temp_root(root, tmp, verified, po_new)
        norm_po = as_json(npo.normalize(tmp, os.path.join(tmp, PO_PATH)))
        pdb.write_json(os.path.join(tmp, NORM_PO_PATH), norm_po)
        comp = as_json(bc.build(tmp))
        pdb.write_json(os.path.join(tmp, COMP_PATH), comp)
        kg = as_json(bk.content(bk.build(tmp, generated_at="-")))
        errors = {"normalized_price_observations": npo.validate_output(
                      norm_po, os.path.join(root, "schemas", "price_observation_normalized.schema.json")),
                  "comparability": bc.validate_output(comp, os.path.join(root, "schemas", "comparability.schema.json"))}

    # canonieke referenties (inhoud, zonder platformafhankelijke hashvelden)
    old_norm = load(root, NORM_PO_PATH)
    old_comp = load(root, COMP_PATH)
    old_kg = load(root, KG_PATH)
    po_cmp = compare_po(old_po, po_new, old_norm, norm_po, link_info)
    comp_cmp = compare_comparability(old_comp, comp)
    dec = classify_decisions(load(root, DECISIONS_PATH), old_comp, comp, old_norm, norm_po)
    kg_cmp = compare_kengetallen(old_kg, kg)

    blocking = []
    if po_cmp["amount_blocking"]:
        blocking.append({"issue": "amount_changes", "count": len(po_cmp["amount_blocking"]),
                         "observations": po_cmp["amount_blocking"]})
    if any(errors.values()):
        blocking.append({"issue": "schema_validation_errors", "errors": errors})
    if not comp_cmp["source_clusters_identical"]:
        blocking.append({"issue": "source_clusters_changed", "observations": comp_cmp["source_cluster_differences"]})
    if any(d["new_internal_codes_on_external_document"] for d in norm_diffs.values()):
        blocking.append({"issue": "external_element_coding_violated"})
    if po_cmp["new_observations"] != po_cmp["old_observations"] or po_cmp["category_counts"]["F_missing_or_new"]:
        blocking.append({"issue": "observation_set_changed"})
    material_lost = sum(1 for v in po_cmp["per_observation"].values()
                        if v["old"]["material"] and not v["new"]["material"])
    material_gained = sum(1 for v in po_cmp["per_observation"].values()
                          if v["new"]["material"] and v["new"]["material"] != v["old"]["material"])
    kg_regressions = [c for c in kg_cmp["by_candidate_key"]
                      if any(k["status"] == "AVAILABLE" for k in c["old"])
                      and not any(k["status"] == "AVAILABLE" for k in c["new"])]
    promotion_blockers = [
        {"issue": "materials_not_in_batch1_v1", "observations_losing_material": material_lost,
         "observations_with_other_material": material_gained,
         "note": "batch1_v1 extraheert geen materiaal (bewust null); het materiaal kwam uit de oude "
                 "verified-laag. Promotie zonder materiaalbron verandert comparability/kengetallen."},
        {"issue": "kengetallen_lose_available_status", "count": len(kg_regressions),
         "candidate_keys": [c["candidate_key"] for c in kg_regressions],
         "cause": sorted({r for c in kg_regressions for k in c["new"] for r in (k["insufficient_data_reasons"] or [])})},
        {"issue": "decisions_to_recheck", "count": dec["counts"]["INPUT_CHANGED_REVIEW_REQUIRED"]
         + dec["counts"]["PAIR_NO_LONGER_EXISTS"]},
        {"issue": "accepts_review_required", "count": accept_sim["simulation"].get("review_required", 0)},
        {"issue": "ambiguous_extraction_links", "count": po_cmp["link_counts"].get("ambiguous", 0)},
        {"issue": "po_source_layer_not_rebuilt", "note": "PO-bronwaarden komen uit de canonieke xpdf-bronlaag; "
         "een echte promotie moet build_price_observations lokaal met xpdf 4.06 herbouwen (bronlaag-fixes "
         "212f2ea/be34bac zitten nog niet in de canonieke PO)."},
    ]

    layer = {
        "normalized": normalized, "verified": verified, "price_observations": po_new,
        "price_observations_normalized": norm_po, "comparability": comp, "kengetallen": kg,
    }
    report = {
        "report": "promotion_v2_dry_run", "tool_version": TOOL_VERSION, "batch_id": pdb.BATCH_ID,
        "handoff_valid": check["ok"], "manifest_version": check["manifest"]["manifest_version"],
        "principles": ["niets canoniek gewijzigd", "geen fuzzy matching", "accepts alleen gesimuleerd",
                       "human decisions alleen gelezen", "geen nieuwe businessregels: bestaande scripts ongewijzigd",
                       "vergelijking zonder platformafhankelijke hashvelden"],
        "normalization_differences": norm_diffs,
        "accept_simulation": accept_sim,
        "price_observations": {k: v for k, v in po_cmp.items() if k != "per_observation"},
        "price_observation_category_legend": PO_CATEGORIES,
        "price_observations_per_observation": po_cmp["per_observation"],
        "amount_changes": len(po_cmp["amount_blocking"]),
        "comparability": comp_cmp,
        "human_decisions": dec,
        "kengetallen": kg_cmp,
        "schema_validation_errors": errors,
        "blocking_issues": blocking,
        "blocking_issues_note": "dry-run-integriteit (bedragen, schema, source clusters, externe codering, "
                                "observation-set); leeg = dry-run bruikbaar",
        "promotion_blockers": promotion_blockers,
        "doc003": "DUPLICATE_SKIP: niet in de normalized/verified-dry-run; 0 observations (duplicate_source)",
        "recommended_promotion_plan": [
            "1. materiaalbron voor batch1_v1 vastleggen (materialen uit de oude verified-laag expliciet "
            "overnemen via exacte koppeling, of bewust null laten) - beslissing vereist",
            "2. menselijke review: accepts met review_required, ambigue koppelingen, decisions met "
            "INPUT_CHANGED_REVIEW_REQUIRED",
            "3. lokaal build_price_observations met xpdf 4.06 herbouwen tegen batch1_v1 en deze dry-run "
            "opnieuw draaien (observation_ids en bedragen moeten gelijk blijven)",
            "4. pas daarna canonieke promotie: extracted/normalized/verified vervangen (oude versies naar "
            "history), PO/comparability herbouwen, kengetallen --supersede",
        ],
    }
    return layer, report


def write_outputs(root, layer, report, out_dir=OUT_DIR, report_path=REPORT):
    base = os.path.join(root, out_dir)
    real = os.path.realpath(base)
    for d in ("extracted", "normalized", "verified", "price_observations", "comparability", "kengetallen"):
        if real == os.path.realpath(os.path.join(root, "data", d)):
            raise SystemExit(f"weigering: {out_dir} is een canonieke map")
    if os.path.isdir(base):
        shutil.rmtree(base)
    files = {}
    for doc, rec in sorted(layer["normalized"].items()):
        files[f"normalized/{doc}.json"] = rec
    for doc, rec in sorted(layer["verified"].items()):
        files[f"verified/{doc}.json"] = rec
    files["price_observations_batch1.json"] = layer["price_observations"]
    files["price_observations_batch1_normalized.json"] = layer["price_observations_normalized"]
    files["comparability_batch1.json"] = layer["comparability"]
    files["kengetallen_batch1.json"] = layer["kengetallen"]
    manifest = {"tool_version": TOOL_VERSION, "batch_id": pdb.BATCH_ID, "files": {}}
    for rel, obj in files.items():
        p = os.path.join(base, *rel.split("/"))
        pdb.write_json(p, obj)
        manifest["files"][rel] = pdb.sha256_file(p)
    pdb.write_json(os.path.join(base, "manifest.json"), manifest)
    report = dict(report, dry_run_layer={"path": out_dir.replace(os.sep, "/"),
                                         "manifest_sha256": pdb.sha256_file(os.path.join(base, "manifest.json"))})
    pdb.write_json(os.path.join(root, report_path), report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--check", action="store_true", help="herbouw in tmp en vergelijk met de gecommitte uitvoer")
    args = ap.parse_args(argv)
    layer, report = build_all(args.root)
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "reports"))
            write_outputs(tmp, layer, report)
            same = filecmp.cmp(os.path.join(tmp, REPORT), os.path.join(args.root, REPORT), shallow=False)
            cmp = filecmp.dircmp(os.path.join(tmp, OUT_DIR), os.path.join(args.root, OUT_DIR))
            diffs = []

            def walk(c, prefix=""):
                diffs.extend(prefix + x for x in c.left_only + c.right_only + c.diff_files)
                for n, sub in c.subdirs.items():
                    walk(sub, prefix + n + "/")
            walk(cmp)
            print("ACTUEEL" if same and not diffs else f"NIET ACTUEEL: rapport gelijk={same}, verschillen={diffs}")
            return 0 if same and not diffs else 1
    report = write_outputs(args.root, layer, report)
    print(f"PO oud/nieuw: {report['price_observations']['old_observations']}/"
          f"{report['price_observations']['new_observations']}  bedragverschillen: {report['amount_changes']}")
    print(f"PO-categorieën: {report['price_observations']['category_counts']}")
    print(f"comparability: {report['comparability']['counts']}")
    print(f"human decisions: {report['human_decisions']['counts']}")
    print(f"kengetallen gewijzigd: {len(report['kengetallen']['changes'])}")
    print(f"blocking: {[b['issue'] for b in report['blocking_issues']]}")
    return 1 if report["blocking_issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
