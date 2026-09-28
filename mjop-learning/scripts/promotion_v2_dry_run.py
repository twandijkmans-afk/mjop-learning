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


def element_context(el):
    if not el:
        return None
    return (pdb.value_of(el.get("element_code")), pdb.squash(pdb.value_of(el.get("element_name"))),
            pdb.squash(pdb.value_of(el.get("location"))))


def po_element_context(o):
    e = o["element"]
    return (e["element_code_original"], pdb.squash(e["element_description_original"]),
            pdb.squash(e["element_location_original"]))


def rows_identical(rows):
    """Bewijs dat ambigue kandidaatrijen inhoudelijk identiek zijn: pagina, actietekst,
    hoeveelheid, eenheid en alle jaarbedragen."""
    sig = {(r["page"], r["action_text"], r["quantity"], r["unit"], tuple((y, str(a)) for y, a in r["years"]))
           for r in rows}
    return len(sig) == 1


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
        key = (doc, prim["page"], pdb.source_key(prim["source_text"]))
        rows = idx.get(key, [])
        acts = {a["action_id"]: a for a in verified[doc]["maintenance_actions"]}
        elements = {e["element_id"]: e for e in verified[doc]["elements"]}
        link = {"candidate_rows": len(rows), "group_key": list(key)}
        if len(rows) > 1:
            # exact onderscheid, geen tie-break: (1) volledige actietekst incl. vervolgregels + hoeveelheid,
            # (2) elementcontext (code + omschrijving + locatie uit de xpdf-bronlaag tegen batch1_v1)
            qty = pdb.dec_str(pdb.to_decimal(o["quantity_value"]))
            txt = [r for r in rows if r["action_text"] == pdb.squash(o["action"]["action_text_original"])
                   and r["quantity"] == qty]
            if len(txt) == 1:
                rows, link["resolved_by"] = txt, "action_text"
            else:
                rows = txt or rows
                ctx = [r for r in rows if element_context(elements.get(next(iter(r["element_ids"])))) ==
                       po_element_context(o)]
                if len(ctx) == 1:
                    rows, link["resolved_by"] = ctx, "element_context"
                else:
                    link["identical_rows"] = rows_identical(rows)
        # bedragcontrole tegen batch1_v1 (alle kandidaatrijen)
        po_amounts = {y: Decimal(v) for y, v in o["annual_amounts"].items()}
        amount_ok = [({str(y): a for y, a in r["years"]} == po_amounts) for r in rows]
        link["amounts_equal"] = all(amount_ok) if rows else None
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
                link["link"] = f"unique_by_{link['resolved_by']}" if link.get("resolved_by") else "unique"
            else:
                o["review_reasons"].append("ambiguous_extraction_link")
                link["link"] = "ambiguous"
                link["candidate_action_ids"] = sorted(i for r in rows for i in r["action_ids"])
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
                    "new_candidate_key": [((nnb.get(oid) or {}).get("element") or {}).get("element_code_internal"),
                                          ((nnb.get(oid) or {}).get("action") or {}).get("action_normalized"),
                                          ((nnb.get(oid) or {}).get("unit") or {}).get("unit_normalized")],
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


# ------------------------------------------------------------------ verklaring van verschillen

def ambiguous_groups(new_po, link_info):
    """DOC-007-achtige multiset-groepen: meerdere PO-observations en meerdere bronrijen met
    exact dezelfde pagina + brontekst, niet te onderscheiden op elementcontext."""
    groups = defaultdict(list)
    for o in new_po["observations"]:
        li = link_info[o["observation_id"]]
        if li.get("link") == "ambiguous":
            groups[tuple(li["group_key"])].append((o["observation_id"], li))
    out = []
    for key, members in sorted(groups.items()):
        li = members[0][1]
        out.append({"document_id": key[0], "page": key[1], "observation_ids": sorted(m[0] for m in members),
                    "candidate_rows": li["candidate_rows"], "candidate_action_ids": li["candidate_action_ids"],
                    "rows_identical": all(m[1].get("identical_rows") for m in members),
                    "amounts_equal": all(m[1].get("amounts_equal") for m in members),
                    "multiset_sizes_equal": len(members) == li["candidate_rows"]})
    return out


def explain_material(old_norm, new_norm):
    """A: oude verified-afleiding (LLM) verdwijnt terecht - batch1_v1 heeft het materiaalveld, leeg
          (de bron heeft geen materiaalkolom);
       B: geen elementkoppeling (UNLINKED-plaatshouder of ambigue identieke rijen) -> null/review;
       C: echte regressie / onverwacht informatieverlies."""
    onb = {o["observation_id"]: o for o in old_norm["observations"]}
    out, counts = [], Counter()
    for o in new_norm["observations"]:
        oid = o["observation_id"]
        a, b = onb[oid]["material"], o["material"]
        if material_value(onb[oid]) == material_value(o):
            continue
        if b.get("verified_material_field") == "no_element_link":
            cls, why = "B_unlinked_or_ambiguous", "geen eenduidige elementkoppeling in batch1_v1"
        elif a.get("material_source") == "verified_element" and b.get("material_not_derived_reason") == \
                "verified_material_empty":
            cls, why = "A_old_verified_derivation", "materiaal kwam uit de oude verified-laag; batch1_v1 heeft " \
                                                    "het veld bewust leeg"
        elif a.get("material_source") == "element_text":
            cls, why = "C_regression", ("goedgekeurde tekstafleiding (MATERIAL_FROM_TEXT, DOC-001) vervalt omdat "
                                        "de regel alleen werkt als het materiaalveld ONTBREEKT; batch1_v1 heeft het "
                                        "veld wel (leeg)")
        else:
            cls, why = "C_regression", "onverwacht"
        counts[cls] += 1
        out.append({"observation_id": oid, "class": cls, "reason": why,
                    "old": {"source": a.get("material_source"), "value": a.get("material_normalized")
                            or (a.get("material_from_text") or {}).get("normalized_value")},
                    "new": {"field": b.get("verified_material_field"), "reason": b.get("material_not_derived_reason")}})
    return {"counts": {k: counts.get(k, 0) for k in ("A_old_verified_derivation", "B_unlinked_or_ambiguous",
                                                      "C_regression")}, "details": out}


def explain_codes(old_po, new_po, link_info):
    obb = {o["observation_id"]: o for o in old_po["observations"]}
    out, counts = [], Counter()
    for o in new_po["observations"]:
        oid = o["observation_id"]
        old_c, new_c = obb[oid]["element"]["element_code_internal"], o["element"]["element_code_internal"]
        if old_c == new_c:
            continue
        reasons = set(o["review_reasons"])
        if new_c and not old_c:
            cls = "gain_exact_link"
        elif "element_unlinked_in_deterministic_extraction" in reasons or link_info[oid].get("link") == "ambiguous":
            cls = "B_unlinked_or_ambiguous"
        else:
            cls = "C_regression"
        counts[cls] += 1
        out.append({"observation_id": oid, "class": cls, "old": old_c, "new": new_c, "link": link_info[oid].get("link")})
    return {"counts": {k: counts.get(k, 0) for k in ("B_unlinked_or_ambiguous", "C_regression", "gain_exact_link")},
            "details": out}


CAUSE_OF = {"E_material_changed": "material", "D_internal_code_changed": "internal_code",
            "C_action_normalization_changed": "action_normalization", "B_link_changed": "link_only"}


def explain_pairs(old_comp, new_comp, per_obs):
    ob = {pair_key(p): p for p in old_comp["pairs"]}
    nb_ = {pair_key(p): p for p in new_comp["pairs"]}
    out = []
    for k in sorted(set(ob) | set(nb_)):
        a, b = ob.get(k), nb_.get(k)
        if a and b and a["class"] == b["class"]:
            continue
        causes = sorted({CAUSE_OF[c] for oid in k for c in per_obs[oid]["categories"] if c in CAUSE_OF})
        entry = {"observation_ids": list(k), "change": "disappeared" if b is None else ("new" if a is None else "changed"),
                 "old_class": (a or {}).get("class"), "new_class": (b or {}).get("class"), "causes": causes,
                 "material_or_code_cause": bool({"material", "internal_code"} & set(causes))}
        if a and b:
            entry["hard_violations"] = {"removed": sorted(set(a["hard_violations"]) - set(b["hard_violations"])),
                                        "added": sorted(set(b["hard_violations"]) - set(a["hard_violations"]))}
            entry["unknown_reasons"] = {"removed": sorted(set(a["unknown_reasons"]) - set(b["unknown_reasons"])),
                                        "added": sorted(set(b["unknown_reasons"]) - set(a["unknown_reasons"]))}
        else:
            entry["candidate_keys"] = {"old": (a or {}).get("candidate_key"),
                                       "new": [per_obs[o]["new_candidate_key"] for o in k]}
        entry["explained"] = bool(causes) and causes != ["link_only"]
        out.append(entry)
    c = Counter(e["change"] for e in out)
    return {"counts": {k: c.get(k, 0) for k in ("changed", "new", "disappeared")}, "unexplained": sum(1 for e in out if not e["explained"]),
            "material_or_code_caused": sum(1 for e in out if e["material_or_code_cause"]), "details": out}


def explain_kengetallen(kg_cmp, old_kg, new_kg, material, codes):
    mat = {d["observation_id"]: d["class"] for d in material["details"]}
    cod = {d["observation_id"]: d["class"] for d in codes["details"]}
    ob = defaultdict(list)
    nb_ = defaultdict(list)
    for k in old_kg["kengetallen"]:
        ob[tuple(k["candidate_key"])].append(k)
    for k in new_kg["kengetallen"]:
        nb_[tuple(k["candidate_key"])].append(k)
    out = []
    for key in sorted(set(ob) | set(nb_)):
        a, b = ob.get(key, []), nb_.get(key, [])
        o0, n0 = (a or [{}])[0], (b or [{}])[0]
        oids = sorted(set(o0.get("observation_ids") or []) | set(n0.get("observation_ids") or []))
        reasons_added = sorted(set(n0.get("insufficient_data_reasons") or []) - set(o0.get("insufficient_data_reasons") or []))
        reasons_removed = sorted(set(o0.get("insufficient_data_reasons") or []) - set(n0.get("insufficient_data_reasons") or []))
        mat_causes = dict(sorted(Counter(mat[i] for i in oids if i in mat).items()))
        code_causes = dict(sorted(Counter(cod[i] for i in oids if i in cod).items()))
        fields_changed = [f for f in ("status", "value_exact", "source_cluster_ids", "source_cluster_count",
                                      "insufficient_data_reasons") if o0.get(f) != n0.get(f)]
        same_semantic = bool(a) and bool(b)
        cause = []
        if "MATERIAL_UNKNOWN" in reasons_added:
            cause.append("MATERIAL_UNKNOWN: materiaal van de groepsobservations niet meer bekend "
                         f"(materiaalklassen {mat_causes})")
        if o0.get("kengetal_id") != n0.get("kengetal_id") and same_semantic:
            cause.append("kengetal_id bevat het materiaal; zelfde candidate_key -> zelfde semantische kandidaat")
        if code_causes:
            cause.append(f"interne code gewijzigd bij groepsobservations {code_causes}")
        out.append({
            "candidate_key": list(key), "semantic_match": same_semantic,
            "old": {"kengetal_ids": [k["kengetal_id"] for k in a], "status": o0.get("status"),
                    "clusters": o0.get("source_cluster_ids"), "value": o0.get("value_display"),
                    "insufficient_data_reasons": o0.get("insufficient_data_reasons")},
            "new": {"kengetal_ids": [k["kengetal_id"] for k in b], "status": n0.get("status"),
                    "clusters": n0.get("source_cluster_ids"), "value": n0.get("value_display"),
                    "insufficient_data_reasons": n0.get("insufficient_data_reasons")},
            "content_changed": bool(fields_changed), "fields_changed": fields_changed,
            "reasons_added": reasons_added, "reasons_removed": reasons_removed,
            "cause": cause, "traceable": (not fields_changed) or bool(cause)})
    return out


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

    groups = ambiguous_groups(po_new, link_info)
    material = explain_material(old_norm, norm_po)
    codes = explain_codes(old_po, po_new, link_info)
    pairs = explain_pairs(old_comp, comp, po_cmp["per_observation"])
    kg_sem = explain_kengetallen(kg_cmp, old_kg, kg, material, codes)
    non_identical = [g for g in groups if not (g["rows_identical"] and g["amounts_equal"])]

    # BLOCKER (definitie gebruiker) - bij een lege lijst zijn alle verschillen verklaard
    blockers = []
    if po_cmp["amount_blocking"]:
        blockers.append({"blocker": "amount_changed", "count": len(po_cmp["amount_blocking"]),
                         "observations": po_cmp["amount_blocking"]})
    if po_cmp["category_counts"]["F_missing_or_new"]:
        blockers.append({"blocker": "observation_missing_or_new", "count": po_cmp["category_counts"]["F_missing_or_new"]})
    if codes["counts"]["C_regression"]:
        blockers.append({"blocker": "internal_code_regression", "count": codes["counts"]["C_regression"],
                         "observations": [d for d in codes["details"] if d["class"] == "C_regression"]})
    if pairs["unexplained"]:
        blockers.append({"blocker": "unexplained_comparability_change", "count": pairs["unexplained"]})
    if any(not k["traceable"] for k in kg_sem):
        blockers.append({"blocker": "untraceable_kengetal_change",
                         "candidate_keys": [k["candidate_key"] for k in kg_sem if not k["traceable"]]})
    if non_identical:
        blockers.append({"blocker": "ambiguous_rows_not_identical", "groups": non_identical})
    if material["counts"]["C_regression"]:
        blockers.append({"blocker": "material_information_loss", "count": material["counts"]["C_regression"],
                         "cause": "MATERIAL_FROM_TEXT (DOC-001, goedgekeurd) geldt alleen als het materiaalveld "
                                  "ontbreekt; batch1_v1 heeft het veld leeg. Oplossing vereist een expliciete "
                                  "beslissing (geen nieuwe businessregel in deze dry-run).",
                         "observations": [d["observation_id"] for d in material["details"] if d["class"] == "C_regression"]})
    if any(errors.values()) or not comp_cmp["source_clusters_identical"] or \
            any(d["new_internal_codes_on_external_document"] for d in norm_diffs.values()):
        blockers.append({"blocker": "dry_run_integrity", "schema_errors": errors,
                         "source_clusters_identical": comp_cmp["source_clusters_identical"]})

    not_blocking = [
        {"item": "identical_duplicate_rows", "groups": len(groups),
         "observations": sum(len(g["observation_ids"]) for g in groups),
         "note": "identieke bronrijen (pagina, tekst, hoeveelheid, eenheid, bedragen gelijk): expliciete "
                 "multiset-groep, geen tie-break; review_reason ambiguous_extraction_link"},
        {"item": "old_verified_material_derivations_dropped", "count": material["counts"]["A_old_verified_derivation"]},
        {"item": "unlinked_or_ambiguous_material", "count": material["counts"]["B_unlinked_or_ambiguous"]},
        {"item": "unlinked_or_ambiguous_internal_code", "count": codes["counts"]["B_unlinked_or_ambiguous"]},
        {"item": "explained_id_and_link_changes", "count": po_cmp["category_counts"]["B_link_changed"]},
        {"item": "kengetal_id_changes_same_candidate_key",
         "count": sum(1 for k in kg_sem if k["semantic_match"] and k["old"]["kengetal_ids"] != k["new"]["kengetal_ids"])},
    ]
    follow_up = [
        {"item": "decisions_to_recheck", "count": dec["counts"]["INPUT_CHANGED_REVIEW_REQUIRED"]
         + dec["counts"]["PAIR_NO_LONGER_EXISTS"]},
        {"item": "accepts_review_required", "count": accept_sim["simulation"].get("review_required", 0)},
        {"item": "po_source_layer_not_rebuilt", "note": "PO-bronwaarden komen uit de canonieke xpdf-bronlaag; een "
         "echte promotie herbouwt build_price_observations lokaal met xpdf 4.06 (bronlaag-fixes 212f2ea/be34bac)."},
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
        "kengetallen_semantic": kg_sem,
        "ambiguous_groups": groups,
        "material_changes": material,
        "internal_code_changes": codes,
        "comparability_explained": pairs,
        "schema_validation_errors": errors,
        "blockers": blockers,
        "not_blocking": not_blocking,
        "follow_up": follow_up,
        "doc003": "DUPLICATE_SKIP: niet in de normalized/verified-dry-run; 0 observations (duplicate_source)",
        "recommended_promotion_plan": [
            "1. beslissing materiaal: (a) MATERIAL_FROM_TEXT-regel ook laten gelden als het materiaalveld leeg is "
            "door deterministische extractie (lost de C-regressie op), en (b) de A-afleidingen bewust laten "
            "vervallen of per element menselijk bevestigen - geen stille terugvulling uit oude verified",
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
    print(f"materiaal A/B/C: {report['material_changes']['counts']}  interne code: {report['internal_code_changes']['counts']}")
    print(f"blockers: {[b['blocker'] for b in report['blockers']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
