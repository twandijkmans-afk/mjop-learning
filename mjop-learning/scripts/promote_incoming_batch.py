#!/usr/bin/env python3
"""
promote_incoming_batch.py - incoming batch promotion v1 (docs/incoming_pipeline_v1.md, deel 2).

Promoveert goedgekeurde documenten uit een staging-batch (data/incoming_batches/<batch_id>/) naar de
canonieke kennislaag, zonder bestaande data stil te wijzigen.

  --check                 keten van canonieke promoties + incoming-register + batches controleren
  --dry-run  --batch-id   preflight, beslissing per document en een volledige simulatie op een tijdelijke
                          kopie; schrijft ALLEEN het reviewrapport reports/incoming/<batch_id>.promotion_review.json
  --approve  --batch-id --reviewer NAAM [--include-review DOC-...]
                          menselijke goedkeuring vastleggen in <batch>/approval.json (gebonden aan de
                          manifest-sha256). Alle EXTRACTED-documenten; REVIEW_REQUIRED-documenten alleen
                          als ze expliciet genoemd worden (hun open punten worden dan vastgelegd).
  --promote  --batch-id   preflight + snapshot + promotie + invarianten; bij een fout automatisch terug
  --rollback --batch-id   laatste promotie exact terugdraaien (hashes gecontroleerd); history blijft bewaard

Beslissing per document (alleen APPROVED_FOR_PROMOTION wordt canoniek):
  SKIPPED_DUPLICATE       exacte duplicate (DUPLICATE_SKIP)
  BLOCKED                 UNKNOWN_TEMPLATE, UNSUPPORTED_FORMAT, FAILED_VALIDATION, READY_FOR_EXTRACTION,
                          UNSUPPORTED_EXTRACTION, runner niet geverifieerd, bronbestand ontbreekt/gewijzigd,
                          al canoniek
  REVIEW_REQUIRED         wacht op menselijke goedkeuring of heeft open reviewpunten die niet expliciet
                          zijn goedgekeurd
  APPROVED_FOR_PROMOTION  EXTRACTED (of expliciet goedgekeurde REVIEW_REQUIRED) + approval.json

Downstream voor goedgekeurde documenten (bestaande regels, niets nieuws):
  data/raw/incoming/<DOC>/<bestand> + register/inventaris/raw_manifest (append)
  data/extracted|normalized|verified/<DOC>.json (verified = genormaliseerd record; geen veldniveau-
      human-verification - de goedkeuring staat in de promotiestatus)
  price observations (append, relatie-ID's hernummerd), normalized PO, comparability (herbouwd),
  kengetallen (herbouwd; inhoud MOET gelijk blijven zolang er geen nieuwe ACTIVE human decisions zijn)
  data/price_observations/relation_proposals.json (relatiekandidaten: alleen voorstel, nooit bevestigd;
      data/price_observations/document_relations.json wordt NIET gewijzigd)

Harde invarianten: bestaande price observations byte-gelijk; bestaande genormaliseerde observations
gelijk op één expliciet genoemd provenance-veld na (source_ref.source_file_sha256); bestaande paren
(identiteit = observation-set) inhoudelijk gelijk; human decision store ongewijzigd; kengetallen
inhoudelijk gelijk; registry append-only. Geen AI, geen netwerk, geen xpdf nodig (alles is gestaged).
"""
import argparse
import copy
import csv
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import build_kengetallen as bk  # noqa: E402
import build_price_observations as bpo  # noqa: E402
import document_registry as dr  # noqa: E402
import export_human_review_queue as hrq  # noqa: E402
import incoming_registry as ir  # noqa: E402
import normalize_price_observations as npo  # noqa: E402
import process_incoming_batch as pib  # noqa: E402
import promote_canonical_batch1 as pcb  # noqa: E402
import promotion_ledger as pl  # noqa: E402

TOOL_VERSION = "promote_incoming_batch_v1.0.0"
DECISIONS = ("APPROVED_FOR_PROMOTION", "REVIEW_REQUIRED", "SKIPPED_DUPLICATE", "BLOCKED")
BLOCKING_STATUSES = ("UNKNOWN_TEMPLATE", "UNSUPPORTED_FORMAT", "FAILED_VALIDATION", "READY_FOR_EXTRACTION")
PO_PATH = os.path.join("data", "price_observations", "price_observations_batch1.json")
NORM_PO_PATH = os.path.join("data", "price_observations", "price_observations_batch1_normalized.json")
COMP_PATH = os.path.join("data", "comparability", "comparability_batch1.json")
KG_PATH = os.path.join("data", "kengetallen", "kengetallen_batch1.json")
DECISIONS_PATH = os.path.join("data", "review_decisions", "human_decision_records.json")
RELATION_PROPOSALS = os.path.join("data", "price_observations", "relation_proposals.json")
REGISTRY = os.path.join("reports", "document_registry.json")
INVENTORY_JSON = os.path.join("reports", "document_inventory.json")
INVENTORY_CSV = os.path.join("reports", "document_inventory.csv")
RAW_MANIFEST = os.path.join("reports", "raw_manifest.json")
INVENTORY_FIELDS = ["document_id", "project_folder", "relative_path", "filename", "file_type", "file_size_bytes",
                    "sha256", "page_count", "text_pdf_or_scan", "has_tables", "has_photos", "has_inspection_data",
                    "has_quantities", "has_costs", "has_condition_scores", "possible_mjop_period", "document_type",
                    "quality_estimate"]
# observation-assessment-velden die door nieuwe tegenhangers mogen veranderen (afgeleid, niet de bron)
DERIVED_ASSESSMENT_FIELDS = ("pair_ids", "comparison_class", "comparison_class_reason", "tariff_group_id")
SIMULATION_COPY = ("data/raw", "data/extracted", "data/normalized", "data/verified", "data/price_observations",
                   "data/comparability", "data/kengetallen", "data/review_decisions", "data/match_review_decisions",
                   "data/history", "data/incoming_promotions", "data/promotion_state_batch1_v1.json",
                   "data/incoming_registry.json", "reports/document_registry.json", "reports/document_inventory.json",
                   "reports/document_inventory.csv", "reports/raw_manifest.json", "schemas", "vocabularies", "docs")


class PromotionError(RuntimeError):
    pass


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj, trailing_newline=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + ("\n" if trailing_newline else ""))


def batch_dir(root, batch_id):
    return os.path.join(root, pib.BATCHES_DIR, batch_id)


# ------------------------------------------------------------------ batch laden en beslissen

def load_batch(root, batch_id):
    bdir = batch_dir(root, batch_id)
    if not pib.BATCH_ID_RE.match(batch_id or "") or not os.path.isfile(os.path.join(bdir, "manifest.json")):
        raise PromotionError(f"batch {batch_id!r} niet gevonden in {pib.BATCHES_DIR}")
    manifest = load(os.path.join(bdir, "manifest.json"))
    docs = [load(p) for p in sorted(glob.glob(os.path.join(bdir, "documents", "*.json")))]
    staged = {}
    for sub in ("extracted", "normalized", "price_observations"):
        staged[sub] = {os.path.basename(p)[:-5]: p for p in glob.glob(os.path.join(bdir, sub, "*.json"))}
    return {"batch_id": batch_id, "dir": bdir, "manifest": manifest,
            "manifest_sha256": pl.sha256_file(os.path.join(bdir, "manifest.json")),
            "documents": docs, "staged": staged,
            "proposal": load(os.path.join(bdir, "promotion_proposal.json"))}


def batch_integrity_errors(root, batch):
    errors = [e for e in pib.check(root) if e.startswith(batch["batch_id"] + "/") or e.startswith(batch["batch_id"] + ":")]
    import jsonschema
    schema = load(os.path.join(root, "schemas", pib.SCHEMAS["manifest"]))
    errors += [f"manifest: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(batch["manifest"])]
    for d in batch["documents"]:
        if d.get("status") not in pib.STATUSES:
            errors.append(f"{d.get('input_path')}: geen expliciete status")
    if len(batch["documents"]) != len(batch["manifest"]["inputs"]):
        errors.append("aantal documents/ wijkt af van manifest.inputs")
    return errors


def runner_verified(batch):
    return batch["manifest"]["runner"].get("runner_setup_status") == "VERIFIED_RUNNER_SETUP"


def locate_source(root, doc):
    """Bronbestand in data/incoming op basis van sha256 (eerst het eerst waargenomen pad)."""
    inc = os.path.join(root, pib.INCOMING_DIR)
    first = os.path.join(inc, *doc["input_path"].split("/"))
    if os.path.isfile(first) and pl.sha256_file(first) == doc["sha256"]:
        return first
    for rel in pib.scan_incoming(inc):
        p = os.path.join(inc, *rel.split("/"))
        if os.path.getsize(p) == doc["file_size_bytes"] and pl.sha256_file(p) == doc["sha256"]:
            return p
    return None


def load_approval(batch):
    path = os.path.join(batch["dir"], "approval.json")
    return load(path) if os.path.exists(path) else None


def approval_errors(approval, batch):
    errs = []
    if approval.get("batch_id") != batch["batch_id"]:
        errs.append("approval.batch_id wijkt af")
    if approval.get("manifest_sha256") != batch["manifest_sha256"]:
        errs.append("approval is niet gebonden aan de huidige manifest.json (batch opnieuw verwerkt?)")
    if not (approval.get("reviewer") or "").strip():
        errs.append("approval.reviewer ontbreekt")
    if not isinstance(approval.get("approved_document_ids"), list):
        errs.append("approval.approved_document_ids ontbreekt")
    return errs


def decide(root, batch, approval=None, hypothetical=False):
    """Beslissing per document. hypothetical=True (dry-run zonder approval): EXTRACTED telt als
    'zou goedgekeurd kunnen worden' voor de simulatie, maar het label blijft REVIEW_REQUIRED."""
    canonical = dr.load_registry(os.path.join(root, REGISTRY))
    canon_ids = {d["document_id"] for d in canonical["documents"]}
    canon_sha = {d["sha256"] for d in canonical["documents"]}
    excluded = set((approval or {}).get("excluded_document_ids") or [])
    approved = set((approval or {}).get("approved_document_ids") or []) - excluded
    acks = (approval or {}).get("review_acknowledgements") or {}
    runner_ok = runner_verified(batch)
    out = []
    for d in batch["documents"]:
        did = d["document_id"]
        key = did or "INPUT-" + d["sha256"][:12]
        reasons, simulate = [], False
        if d["status"] == "DUPLICATE_SKIP":
            decision = "SKIPPED_DUPLICATE"
            reasons.append(f"duplicate_of:{d['duplicate_of']}")
        elif d["status"] in BLOCKING_STATUSES:
            decision, reasons = "BLOCKED", [d["status"]] + d["reasons"]
        elif "UNSUPPORTED_EXTRACTION" in d["reasons"]:
            decision, reasons = "BLOCKED", ["UNSUPPORTED_EXTRACTION"]
        elif not runner_ok:
            decision, reasons = "BLOCKED", [f"RUNNER_NOT_VERIFIED:{batch['manifest']['runner'].get('runner_setup_status')}"]
        elif did in canon_ids or d["sha256"] in canon_sha:
            decision, reasons = "BLOCKED", ["ALREADY_CANONICAL"]
        elif any(did not in batch["staged"][s] for s in ("extracted", "normalized", "price_observations")):
            decision, reasons = "BLOCKED", ["MISSING_STAGED_OUTPUT"]
        elif locate_source(root, d) is None:
            decision, reasons = "BLOCKED", ["SOURCE_FILE_MISSING_OR_CHANGED"]
        elif did in excluded:
            decision = "REVIEW_REQUIRED"
            reasons = ["EXCLUDED_BY_REVIEWER"] + [i for i in d["open_review_items"]]
        elif d["status"] == "EXTRACTED":
            if did in approved:
                decision = "APPROVED_FOR_PROMOTION"
            else:
                decision, reasons = "REVIEW_REQUIRED", ["AWAITING_HUMAN_APPROVAL"]
                simulate = hypothetical
        elif d["status"] == "REVIEW_REQUIRED":
            items = sorted(d["open_review_items"])
            if did in approved and sorted(acks.get(did, [])) == items:
                decision, reasons = "APPROVED_FOR_PROMOTION", [f"review_acknowledged:{i}" for i in items]
            else:
                decision, reasons = "REVIEW_REQUIRED", items or ["REVIEW_REQUIRED"]
                simulate = hypothetical
        else:
            decision, reasons = "BLOCKED", [f"UNEXPECTED_STATUS:{d['status']}"]
        out.append({"key": key, "document_id": did, "input_path": d["input_path"], "status": d["status"],
                    "decision": decision, "reasons": reasons, "simulate": decision == "APPROVED_FOR_PROMOTION" or simulate,
                    "open_review_items": d["open_review_items"]})
    for did in sorted(approved):
        if not any(x["document_id"] == did and x["decision"] == "APPROVED_FOR_PROMOTION" for x in out):
            out.append({"key": did, "document_id": did, "input_path": None, "status": None, "decision": "BLOCKED",
                        "reasons": ["APPROVAL_FOR_NON_ELIGIBLE_DOCUMENT"], "simulate": False, "open_review_items": []})
    return out


# ------------------------------------------------------------------ preflight

def canonical_errors(root):
    errors = []
    if pl.states(root):
        errors += pl.chain_errors(root)
    elif os.path.exists(os.path.join(root, pcb.STATE)):
        errors += [f"batch1: {e}" for e in pcb.verify(root)]
    reg = dr.load_registry(os.path.join(root, REGISTRY))
    try:
        _, report = dr.reconcile(copy.deepcopy(reg), os.path.join(root, "data", "raw"), register_new=False)
        if report["new"] or report["missing"]:
            errors.append(f"document_registry niet in lijn met data/raw: new={report['new']} missing={report['missing']}")
    except dr.RegistryError as e:
        errors.append(str(e))
    store = load(os.path.join(root, DECISIONS_PATH))
    errors += [f"decision store: {e}" for e in hrq.store_invariant_errors(store)]
    kg = load(os.path.join(root, KG_PATH))
    if kg["inputs"] != bk.input_hashes(root):
        errors.append("kengetallen niet actueel t.o.v. hun invoer")
    errors += [f"incoming-register: {e}" for e in ir.integrity_errors(
        ir.load(os.path.join(root, ir.REGISTRY_PATH)), reg)]
    return errors


def preflight(root, batch_id, need_approval):
    fails = []
    batch = load_batch(root, batch_id)
    fails += batch_integrity_errors(root, batch)
    if not runner_verified(batch):
        fails.append(f"runner niet geverifieerd: {batch['manifest']['runner'].get('runner_setup_status')}")
    fails += canonical_errors(root)
    approval = load_approval(batch)
    if need_approval:
        if approval is None:
            fails.append("geen approval.json (eerst --approve door een mens)")
        else:
            fails += approval_errors(approval, batch)
    decisions = decide(root, batch, approval if not (approval and approval_errors(approval, batch)) else None,
                       hypothetical=not need_approval and approval is None)
    bad_approvals = [d for d in decisions if "APPROVAL_FOR_NON_ELIGIBLE_DOCUMENT" in d["reasons"]]
    if need_approval and bad_approvals:
        fails.append(f"approval noemt niet-promoveerbare documenten: {[d['document_id'] for d in bad_approvals]}")
    if need_approval and not any(d["decision"] == "APPROVED_FOR_PROMOTION" for d in decisions):
        fails.append("geen enkel document APPROVED_FOR_PROMOTION")
    return fails, batch, approval, decisions


# ------------------------------------------------------------------ toepassen (in een root)

def _norm_without_source_sha(o):
    o = copy.deepcopy(o)
    o.get("source_ref", {}).pop("source_file_sha256", None)
    return o


def _pairs_by_set(comp, obs_ids=None):
    out = {}
    for p in comp["pairs"]:
        k = tuple(sorted(p["observation_ids"]))
        if obs_ids is None or set(k) <= obs_ids:
            out[k] = {x: v for x, v in p.items() if x != "pair_id"}
    return out


def _assess_without_derived(a):
    return {k: v for k, v in a.items() if k not in DERIVED_ASSESSMENT_FIELDS}


def _inventory_record(root, entry):
    import inventory_documents as inv
    full = os.path.join(root, "data", "raw", *entry["relative_path"].split("/"))
    fn = os.path.basename(entry["relative_path"])
    ext = os.path.splitext(fn)[1].lower().lstrip(".")
    rec = {"document_id": entry["document_id"], "filename": fn, "relative_path": entry["relative_path"],
           "project_folder": entry["relative_path"].split("/")[0], "file_type": ext,
           "file_size_bytes": os.path.getsize(full), "sha256": inv.sha256_of(full),
           "document_type": None, "possible_building_year": None, "possible_number_of_units": None,
           "possible_inspection_date": None, "possible_advisor": None, "quality_estimate": None}
    if ext == "pdf":
        rec.update(inv.analyze_pdf(full))
    return rec


def _write_inventory(root, records):
    # exact dezelfde serialisatie als scripts/inventory_documents.py
    json.dump(records, open(os.path.join(root, INVENTORY_JSON), "w"), ensure_ascii=False, indent=2)
    with open(os.path.join(root, INVENTORY_CSV), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)


def apply_promotion(root, source_root, batch, decisions, approval, now):
    """Voert de promotie uit in `root` (echte repo of tijdelijke kopie). Bronnen (incoming-bestanden en
    staging) komen uit `source_root`. Returns samenvatting. Gooit PromotionError bij een invariantfout."""
    approved = sorted((d for d in decisions if d["simulate"]), key=lambda d: dr._id_num(d["document_id"]))
    if not approved:
        raise PromotionError("geen documenten om te promoveren")
    docs = {d["document_id"]: d for d in batch["documents"]}
    kg_before = load(os.path.join(root, KG_PATH))
    po = load(os.path.join(root, PO_PATH))
    old_po_obs = json.dumps(po["observations"], sort_keys=True)
    old_norm = {o["observation_id"]: _norm_without_source_sha(o)
                for o in load(os.path.join(root, NORM_PO_PATH))["observations"]}
    old_comp = load(os.path.join(root, COMP_PATH))
    old_obs_ids = {o["observation_id"] for o in po["observations"]}
    old_pairs = _pairs_by_set(old_comp)
    old_assess = {a["observation_id"]: _assess_without_derived(a) for a in old_comp["observations"]}
    store_bytes = open(os.path.join(root, DECISIONS_PATH), "rb").read()
    registry = dr.load_registry(os.path.join(root, REGISTRY))
    old_registry = copy.deepcopy(registry)
    raw_manifest = load(os.path.join(root, RAW_MANIFEST))
    inventory = load(os.path.join(root, INVENTORY_JSON))
    old_inventory = copy.deepcopy(inventory)
    inc_registry = {e["document_id"]: e for e in ir.load(os.path.join(source_root, ir.REGISTRY_PATH))["documents"]}

    promoted = []
    for d in approved:
        did = d["document_id"]
        doc = docs[did]
        src_file = locate_source(source_root, doc)
        rel = pib.raw_relative_path(did, inc_registry[did]["first_observed_path"])
        dst = os.path.join(root, "data", "raw", *rel.split("/"))
        if os.path.exists(dst):
            raise PromotionError(f"{rel} bestaat al in data/raw (nooit overschrijven)")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src_file, dst)
        if pl.sha256_file(dst) != doc["sha256"]:
            raise PromotionError(f"{did}: sha256 na kopiëren wijkt af")
        extracted = load(batch["staged"]["extracted"][did])
        if extracted["extraction_metadata"]["source_relative_path"] != rel or \
                extracted["extraction_metadata"]["source_sha256"] != doc["sha256"]:
            raise PromotionError(f"{did}: extractie verwijst niet naar het gepromoveerde bronbestand")
        registry["documents"].append({"document_id": did, "relative_path": rel, "filename": os.path.basename(rel),
                                      "project_folder": rel.split("/")[0], "sha256": doc["sha256"],
                                      "file_size_bytes": doc["file_size_bytes"], "inventaris_document_id": None})
        raw_manifest[rel] = {"sha256": doc["sha256"], "size": doc["file_size_bytes"]}
        for layer, sub in (("extracted", "extracted"), ("normalized", "normalized"), ("verified", "normalized")):
            shutil.copyfile(batch["staged"][sub][did], os.path.join(root, "data", layer, f"{did}.json"))
        # price observations (append; relatie-ID's hernummeren; bestaande observations blijven byte-gelijk)
        staged_po = load(batch["staged"]["price_observations"][did])
        next_rel = max([int(r["relation_id"].split("-")[1]) for r in po["observation_relations"]] or [0]) + 1
        rel_map = {}
        for r in staged_po["observation_relations"]:
            rel_map[r["relation_id"]] = f"OREL-{next_rel:04d}"
            next_rel += 1
            po["observation_relations"].append(dict(r, relation_id=rel_map[r["relation_id"]]))
        for o in staged_po["observations"]:
            if o["observation_id"] in old_obs_ids:
                raise PromotionError(f"{o['observation_id']} bestaat al")
            o["relation_ids"] = [rel_map[x] for x in o["relation_ids"]]
            po["observations"].append(o)
        doc_entry = dict(staged_po["document"])
        po["documents"].append(doc_entry)
        po["checks"]["per_document"][did] = staged_po["checks"]
        po["unlinked_section_rows"].extend(staged_po["unlinked_section_rows"])
        promoted.append({"document_id": did, "raw_relative_path": rel, "sha256": doc["sha256"],
                         "price_observations": len(staged_po["observations"]), "status_in_batch": doc["status"],
                         "acknowledged_review_items": (approval or {}).get("review_acknowledgements", {}).get(did, [])})
    po["checks"]["totals"] = bpo.compute_totals(po["observations"], po["observation_relations"],
                                                po["unlinked_section_rows"])
    po.setdefault("incoming_promotions", []).append(
        {"batch_id": batch["batch_id"], "document_ids": [p["document_id"] for p in promoted],
         "note": "observations toegevoegd uit de incoming staging (build_price_observations.build_document)"})
    if json.dumps(po["observations"][:len(old_obs_ids)], sort_keys=True) != old_po_obs:
        raise PromotionError("INVARIANT: bestaande price observations gewijzigd")
    errs = bpo.validate_observations(po, os.path.join(root, "schemas", "price_observation.schema.json"))
    if errs:
        raise PromotionError(f"price observation schemafouten: {errs[:3]}")
    pcb.write_json_lf(os.path.join(root, PO_PATH), po)

    # registry / raw_manifest / inventaris (append-only)
    dr.save_registry(registry, os.path.join(root, REGISTRY))
    if [d for d in registry["documents"] if d["document_id"] in {x["document_id"] for x in old_registry["documents"]}] \
            != sorted(old_registry["documents"], key=lambda x: dr._id_num(x["document_id"])):
        raise PromotionError("INVARIANT: document_registry niet append-only")
    with open(os.path.join(root, RAW_MANIFEST), "w") as f:
        json.dump(raw_manifest, f, indent=2, sort_keys=True)
    for p in promoted:
        entry = next(e for e in registry["documents"] if e["document_id"] == p["document_id"])
        inventory.append(_inventory_record(root, entry))
    inventory = sorted(inventory, key=lambda r: r["document_id"])
    if [r for r in inventory if r["document_id"] in {x["document_id"] for x in old_inventory}] != old_inventory:
        raise PromotionError("INVARIANT: bestaande inventarisrecords gewijzigd")
    _write_inventory(root, inventory)

    # normalized PO -> comparability -> kengetallen
    norm = npo.normalize(root, os.path.join(root, PO_PATH))
    errs = npo.validate_output(norm, os.path.join(root, "schemas", "price_observation_normalized.schema.json"))
    if errs:
        raise PromotionError(f"normalized PO schemafouten: {errs[:3]}")
    new_norm = {o["observation_id"]: o for o in norm["observations"]}
    changed = [i for i, o in old_norm.items() if _norm_without_source_sha(new_norm[i]) != o]
    if changed:
        raise PromotionError(f"INVARIANT: bestaande genormaliseerde observations gewijzigd: {changed[:5]}")
    pcb.write_json_lf(os.path.join(root, NORM_PO_PATH), pcb.pv2.as_json(norm))
    comp = bc.build(root)
    errs = bc.validate_output(comp, os.path.join(root, "schemas", "comparability.schema.json"))
    if errs:
        raise PromotionError(f"comparability schemafouten: {errs[:3]}")
    comp = pcb.pv2.as_json(comp)
    if _pairs_by_set(comp, old_obs_ids) != old_pairs:
        raise PromotionError("INVARIANT: bestaande paren (observation-set) inhoudelijk gewijzigd")
    new_assess = {a["observation_id"]: a for a in comp["observations"]}
    moved = [i for i, a in old_assess.items() if _assess_without_derived(new_assess[i]) != a]
    if moved:
        raise PromotionError(f"INVARIANT: bestaande observation-beoordelingen gewijzigd: {moved[:5]}")
    pcb.write_json_lf(os.path.join(root, COMP_PATH), comp)
    if open(os.path.join(root, DECISIONS_PATH), "rb").read() != store_bytes:
        raise PromotionError("INVARIANT: human decision store gewijzigd")
    kg_new = bk.build(root, generated_at=now)
    errs = bk.validate_output(kg_new, os.path.join(root, "schemas", "kengetal.schema.json"))
    if errs:
        raise PromotionError(f"kengetallen schemafouten: {errs[:3]}")
    if (kg_new["kengetallen"], kg_new["summary"]) != (kg_before["kengetallen"], kg_before["summary"]):
        raise PromotionError("INVARIANT: kengetallen inhoudelijk gewijzigd zonder nieuwe human decisions")
    old_kg_path = os.path.join(root, KG_PATH)
    old_sha = pl.sha256_file(old_kg_path)
    hist = os.path.join(os.path.dirname(old_kg_path), "history",
                        os.path.basename(old_kg_path).replace(".json", f".{old_sha[:12]}.json"))
    os.makedirs(os.path.dirname(hist), exist_ok=True)
    shutil.copyfile(old_kg_path, hist)
    kg_new["supersedes"] = {"file": os.path.relpath(hist, root).replace("\\", "/"), "sha256": old_sha}
    with open(old_kg_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(bk.dump(kg_new))

    # relatievoorstellen (nooit bevestigd; document_relations.json blijft ongewijzigd)
    rp_path = os.path.join(root, RELATION_PROPOSALS)
    rp = load(rp_path) if os.path.exists(rp_path) else {
        "description": "Relatie- en source-cluster-KANDIDATEN uit incoming batches. Alleen voorstel: niet gebruikt "
                       "door price observations, comparability of kengetallen. Bevestigen = handmatige, beoordeelde "
                       "wijziging van document_relations.json.", "proposals": []}
    promoted_ids = {p["document_id"] for p in promoted}
    for r in batch["proposal"]["relation_candidates"]:
        if set(r["document_ids"]) & promoted_ids:
            rp["proposals"].append(dict(r, batch_id=batch["batch_id"], status="PROPOSAL_REQUIRES_HUMAN_CONFIRMATION"))
    write_json(rp_path, rp)

    new_pairs = [p for k, p in _pairs_by_set(comp).items() if not set(k) <= old_obs_ids]
    open_rel_docs = {d for r in batch["proposal"]["relation_candidates"] for d in r["document_ids"]}
    obs_doc = {o["observation_id"]: o["document_id"] for o in po["observations"]}
    flagged = [p for p in new_pairs if {obs_doc[i] for i in p["observation_ids"]} <= open_rel_docs
               and len({obs_doc[i] for i in p["observation_ids"]}) == 2]
    return {
        "promoted_documents": promoted,
        "price_observations": {"before": len(old_obs_ids), "added": len(po["observations"]) - len(old_obs_ids),
                               "after": len(po["observations"])},
        "comparability_impact": {"pairs_before": len(old_pairs), "pairs_after": len(comp["pairs"]),
                                 "new_pairs": len(new_pairs),
                                 "new_pairs_by_class": _count(p["class"] for p in new_pairs),
                                 "new_pairs_by_candidate_key": _count("|".join(map(str, p["candidate_key"]))
                                                                      for p in new_pairs),
                                 "new_pairs_have_human_decisions": 0,
                                 "new_pairs_between_documents_with_open_relation_candidate": len(flagged),
                                 "warning": ("Paren tussen documenten met een open relatiekandidaat (mogelijke "
                                             "duplicate/nieuwe versie/deelplan) zijn mogelijk NIET onafhankelijk; "
                                             "eerst de relatie beoordelen.") if flagged else None,
                                 "source_clusters_after": [c["source_cluster"] for c in comp["source_clusters"]]},
        "kengetallen": {"before": _kg_summary(kg_before), "after": _kg_summary(kg_new),
                        "content_changed": False,
                        "statement": "Nieuwe observations dragen pas bij na comparability-review met ACTIVE human "
                                     "decisions volgens de bestaande regels."},
        "relation_proposals_added": sum(1 for r in batch["proposal"]["relation_candidates"]
                                        if set(r["document_ids"]) & promoted_ids),
    }


def _count(items):
    out = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items()))


def _kg_summary(kg):
    return [{"kengetal_id": k["kengetal_id"], "status": k["status"], "value": k["value_display"],
             "clusters": k["source_cluster_count"]} for k in kg["kengetallen"]]


# ------------------------------------------------------------------ snapshot / rollback

def next_promotion_id(root, batch_id):
    n = len(glob.glob(os.path.join(root, pl.HISTORY_ROOT, f"{batch_id}-P*"))) + 1
    return f"{batch_id}-P{n}"


def snapshot(root, hist):
    pre = pl.tracked_hashes(root)
    for path in pre:
        if path.startswith("data/raw/"):
            continue  # raw wordt alleen aangevuld; hashes staan in pre_manifest
        dst = os.path.join(hist, "pre", path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(root, path), dst)
    write_json(os.path.join(hist, "pre_manifest.json"), {"files": pre, "tool_version": TOOL_VERSION})
    return pre


def restore(root, hist, pre):
    cur = pl.tracked_hashes(root)
    for path in cur:
        if path not in pre:
            os.remove(os.path.join(root, path))
    for path, sha in pre.items():
        if path.startswith("data/raw/"):
            continue
        dst = os.path.join(root, path)
        if cur.get(path) != sha:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(hist, "pre", path), dst)
    for base in ("data/raw/incoming", "data/kengetallen/history"):
        top = os.path.join(root, base)
        for r, _, _ in sorted(os.walk(top), key=lambda x: -len(x[0])) if os.path.isdir(top) else []:
            if not os.listdir(r):
                os.rmdir(r)
    if pl.tracked_hashes(root) != pre:
        raise PromotionError("herstel: hashes komen niet overeen met pre_manifest")


def promote(root, batch_id, now=None):
    now = now or now_utc()
    fails, batch, approval, decisions = preflight(root, batch_id, need_approval=True)
    if fails:
        raise PromotionError("PREFLIGHT FAALT:\n- " + "\n- ".join(fails))
    pid = next_promotion_id(root, batch_id)
    hist = os.path.join(root, pl.HISTORY_ROOT, pid)
    os.makedirs(hist)
    pre = snapshot(root, hist)
    try:
        summary = apply_promotion(root, root, batch, decisions, approval, now)
    except BaseException:
        restore(root, hist, pre)
        write_json(os.path.join(hist, "failed_attempt.json"), {"promotion_id": pid, "status": "FAILED_RESTORED"})
        raise
    post = pl.tracked_hashes(root)
    prev = pl.latest(root)
    state = {"promotion_id": pid, "tool_version": TOOL_VERSION, "status": "PROMOTED", "batch_id": batch_id,
             "sequence": (prev["sequence"] + 1) if prev else 1, "promoted_at": now,
             "approval": {"reviewer": approval["reviewer"], "approved_at": approval.get("approved_at"),
                          "sha256": pl.sha256_file(os.path.join(batch["dir"], "approval.json"))},
             "manifest_sha256": batch["manifest_sha256"], "runner": batch["manifest"]["runner"]["runner_setup_status"],
             "decisions": [{k: d[k] for k in ("key", "document_id", "decision", "reasons")} for d in decisions],
             "verified_layer_note": "data/verified/<DOC> = genormaliseerd record; geen veldniveau-human-verification. "
                                    "De documentgoedkeuring staat hier (approval).",
             "history": os.path.relpath(hist, root).replace(os.sep, "/"),
             "pre_manifest_sha256": pl.sha256_file(os.path.join(hist, "pre_manifest.json")),
             "pre_manifest": pre, "post_manifest": post, "summary": summary}
    write_json(os.path.join(root, pl.STATE_DIR, f"{pid}.json"), state)
    return state


def verify(root):
    errors = pl.chain_errors(root)
    for s in pl.states(root):
        hist = os.path.join(root, s["history"])
        if pl.sha256_file(os.path.join(hist, "pre_manifest.json")) != s["pre_manifest_sha256"]:
            errors.append(f"{s['promotion_id']}: pre_manifest in history gewijzigd")
        for path, sha in s["pre_manifest"].items():
            if not path.startswith("data/raw/") and pl.sha256_file(os.path.join(hist, "pre", path)) != sha:
                errors.append(f"{s['promotion_id']}: history-kopie {path} wijkt af")
                break
    return errors


def rollback(root, batch_id):
    last = pl.latest(root)
    if last is None or last["batch_id"] != batch_id:
        raise PromotionError(f"alleen de laatste promotie kan worden teruggedraaid "
                             f"(laatste: {last['promotion_id'] if last else 'geen'})")
    if pl.tracked_hashes(root) != last["post_manifest"]:
        raise PromotionError("huidige canonieke bestanden wijken af van de post_manifest; eerst onderzoeken")
    hist = os.path.join(root, last["history"])
    restore(root, hist, last["pre_manifest"])
    state_path = os.path.join(root, pl.STATE_DIR, f"{last['promotion_id']}.json")
    rolled = dict(last, status="ROLLED_BACK")
    write_json(os.path.join(hist, "rolled_back_state.json"), rolled)     # bewaard, niet verwijderd
    os.remove(state_path)
    if os.path.isdir(os.path.join(root, pl.STATE_DIR)) and not os.listdir(os.path.join(root, pl.STATE_DIR)):
        os.rmdir(os.path.join(root, pl.STATE_DIR))
    return f"ROLLBACK OK ({last['promotion_id']})"


# ------------------------------------------------------------------ dry-run en reviewrapport

def simulate(root, batch, decisions, approval):
    """Volledige promotie op een tijdelijke kopie. Het echte repo blijft onaangeroerd."""
    with tempfile.TemporaryDirectory() as tmp:
        for rel in SIMULATION_COPY:
            src_p = os.path.join(root, rel)
            dst_p = os.path.join(tmp, rel)
            if os.path.isdir(src_p):
                shutil.copytree(src_p, dst_p)
            elif os.path.isfile(src_p):
                os.makedirs(os.path.dirname(dst_p), exist_ok=True)
                shutil.copy2(src_p, dst_p)
        summary = apply_promotion(tmp, root, batch, decisions, approval, "2000-01-01T00:00:00Z")
        post_errors = canonical_after_errors(tmp)
    return summary, post_errors


def canonical_after_errors(root):
    """Canonieke controles na een (gesimuleerde) promotie."""
    errors = []
    reg = dr.load_registry(os.path.join(root, REGISTRY))
    _, report = dr.reconcile(copy.deepcopy(reg), os.path.join(root, "data", "raw"), register_new=False)
    if report["new"] or report["missing"] or report["modified"]:
        errors.append(f"registry/raw: {report['new']} {report['missing']} {report['modified']}")
    raw_manifest = load(os.path.join(root, RAW_MANIFEST))
    for rel, meta in raw_manifest.items():
        p = os.path.join(root, "data", "raw", *rel.split("/"))
        if not os.path.isfile(p) or pl.sha256_file(p) != meta["sha256"]:
            errors.append(f"raw_manifest: {rel}")
    kg = load(os.path.join(root, KG_PATH))
    if kg["inputs"] != bk.input_hashes(root):
        errors.append("kengetallen niet actueel na promotie")
    errors += [f"decision store: {e}" for e in hrq.store_invariant_errors(load(os.path.join(root, DECISIONS_PATH)))]
    return errors


def review_report(root, batch, decisions, summary, post_errors, preflight_fails, approval):
    groups = {k: [d for d in decisions if d["decision"] == k] for k in DECISIONS}
    eligible_direct = [d["document_id"] for d in decisions if d["decision"] == "APPROVED_FOR_PROMOTION" or
                       (d["decision"] == "REVIEW_REQUIRED" and d["reasons"] == ["AWAITING_HUMAN_APPROVAL"])]
    return {
        "batch_id": batch["batch_id"], "tool_version": TOOL_VERSION, "manifest_sha256": batch["manifest_sha256"],
        "runner_setup_status": batch["manifest"]["runner"].get("runner_setup_status"),
        "approval_present": approval is not None,
        "preflight_blockers": preflight_fails,
        "decisions": {k: [{"document_id": d["document_id"] or d["key"], "input_path": d["input_path"],
                           "reasons": d["reasons"]} for d in v] for k, v in groups.items()},
        "can_be_promoted_directly": eligible_direct,
        "needs_review": [{"document_id": d["document_id"], "open_review_items": d["reasons"]}
                         for d in groups["REVIEW_REQUIRED"] if d["reasons"] != ["AWAITING_HUMAN_APPROVAL"]],
        "possible_duplicates_and_relations": batch["proposal"]["relation_candidates"],
        "simulation": summary, "canonical_checks_after_simulation": post_errors,
        "note": "Dry-run: volledige promotie gesimuleerd op een tijdelijke kopie; canonieke data ongewijzigd.",
    }


def dry_run(root, batch_id, documents=None):
    """Volledige simulatie op een tijdelijke kopie. Met een approval.json: exact die goedkeuring.
    Zonder approval: hypothetisch alle promoveerbare documenten, of alleen `documents` (moeten
    EXTRACTED en verder promoveerbaar zijn; REVIEW_REQUIRED-documenten nooit via deze route)."""
    fails, batch, approval, decisions = preflight(root, batch_id, need_approval=False)
    if documents:
        if approval is not None:
            raise PromotionError("--documents alleen zonder approval.json (met approval wordt die exact gesimuleerd)")
        eligible = {d["document_id"] for d in decisions if d["reasons"] == ["AWAITING_HUMAN_APPROVAL"]}
        wrong = sorted(set(documents) - eligible)
        if wrong:
            raise PromotionError(f"niet promoveerbaar zonder aparte review: {wrong}")
        for d in decisions:
            d["simulate"] = d["document_id"] in set(documents)
    summary, post_errors = None, []
    if not [f for f in fails if not f.startswith("geen approval")] and any(d["simulate"] for d in decisions):
        summary, post_errors = simulate(root, batch, decisions, approval)
    report = review_report(root, batch, decisions, summary, post_errors, fails, approval)
    return report


# ------------------------------------------------------------------ approve

def approve(root, batch_id, reviewer, include_review=(), now=None, exclude=(), exclude_reason=None):
    batch = load_batch(root, batch_id)
    errs = batch_integrity_errors(root, batch)
    if errs:
        raise PromotionError(f"batch ongeldig: {errs[:3]}")
    decisions = decide(root, batch, None)
    known = {d["document_id"] for d in decisions if d["document_id"]}
    unknown = sorted(set(exclude) - known)
    if unknown:
        raise PromotionError(f"uit te sluiten documenten horen niet bij deze batch: {unknown}")
    if set(exclude) & set(include_review):
        raise PromotionError("een document kan niet tegelijk goedgekeurd en uitgesloten worden")
    extracted = sorted(d["document_id"] for d in decisions
                       if d["decision"] == "REVIEW_REQUIRED" and d["reasons"] == ["AWAITING_HUMAN_APPROVAL"]
                       and d["document_id"] not in set(exclude))
    acks = {}
    for did in include_review:
        d = next((x for x in decisions if x["document_id"] == did), None)
        if d is None or d["decision"] != "REVIEW_REQUIRED" or d["reasons"] == ["AWAITING_HUMAN_APPROVAL"]:
            raise PromotionError(f"{did} is geen REVIEW_REQUIRED-document van deze batch")
        acks[did] = sorted(d["open_review_items"])
    approval = {"batch_id": batch_id, "manifest_sha256": batch["manifest_sha256"],
                "reviewer": reviewer, "approved_at": now or now_utc(),
                "approved_document_ids": sorted(set(extracted) | set(acks), key=dr._id_num),
                "review_acknowledgements": acks,
                "excluded_document_ids": sorted(set(exclude), key=dr._id_num),
                "exclusion_reason": exclude_reason if exclude else None,
                "statement": "Menselijke goedkeuring voor promotie. Relatiekandidaten worden hiermee NIET bevestigd."}
    path = os.path.join(batch["dir"], "approval.json")
    if os.path.exists(path):
        old = load(path)
        write_json(os.path.join(batch["dir"], "approval_history", f"approval.{pl.sha256_file(path)[:12]}.json"), old)
    write_json(path, approval)
    return approval


# ------------------------------------------------------------------ CLI

def check(root):
    errors = canonical_errors(root) + verify(root) + pib.check(root)
    return sorted(set(errors))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("--check", "--dry-run", "--approve", "--promote", "--rollback"):
        g.add_argument(f, action="store_true")
    ap.add_argument("--batch-id")
    ap.add_argument("--reviewer")
    ap.add_argument("--include-review", nargs="*", default=[])
    ap.add_argument("--no-write", action="store_true", help="dry-run: ook het reviewrapport niet schrijven")
    ap.add_argument("--exclude", nargs="*", default=[], help="--approve: documenten expliciet uitsluiten")
    ap.add_argument("--exclude-reason", help="--approve: reden van de uitsluiting (vastgelegd in approval.json)")
    ap.add_argument("--documents", nargs="*", default=[],
                    help="dry-run zonder approval: simuleer alleen deze (EXTRACTED) documenten")
    args = ap.parse_args(argv)
    root = args.root
    try:
        if args.check:
            errs = check(root)
            print("CHECK OK" if not errs else "CHECK FAALT:\n- " + "\n- ".join(errs))
            return 0 if not errs else 1
        if not args.batch_id:
            ap.error("--batch-id is verplicht")
        if args.dry_run:
            report = dry_run(root, args.batch_id, args.documents or None)
            text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if not args.no_write:
                out = os.path.join(root, pib.REPORTS_DIR, f"{args.batch_id}.promotion_review.json")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                print(f"reviewrapport: {os.path.relpath(out, root)}")
            print(json.dumps({"preflight_blockers": report["preflight_blockers"],
                              "decisions": {k: len(v) for k, v in report["decisions"].items()},
                              "can_be_promoted_directly": report["can_be_promoted_directly"],
                              "canonical_checks_after_simulation": report["canonical_checks_after_simulation"]},
                             ensure_ascii=False, indent=2))
            return 0
        if args.approve:
            if not args.reviewer:
                ap.error("--reviewer is verplicht bij --approve")
            a = approve(root, args.batch_id, args.reviewer, args.include_review, exclude=args.exclude,
                        exclude_reason=args.exclude_reason)
            print(f"approval.json geschreven: {a['approved_document_ids']}")
            return 0
        if args.promote:
            state = promote(root, args.batch_id)
            print(json.dumps({"promotion_id": state["promotion_id"], **state["summary"]}, ensure_ascii=False, indent=2))
            return 0
        print(rollback(root, args.batch_id))
        return 0
    except PromotionError as e:
        print(f"FOUT: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
