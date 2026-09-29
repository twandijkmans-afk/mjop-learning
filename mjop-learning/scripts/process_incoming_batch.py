#!/usr/bin/env python3
"""
process_incoming_batch.py - incoming / bulk MJOP pipeline v1 (docs/incoming_pipeline_v1.md).

    data/incoming/  ->  intake (formaat, sha256)  ->  duplicate-detectie  ->  stabiel DOC-ID
    ->  incoming-register  ->  familieherkenning  ->  deterministische extractie (xpdf 4.06)
    ->  validatie / reviewstatus  ->  staging-batch + batchrapport + promotievoorstel

Harde regels:
  - Geen AI/LLM, geen netwerk, geen andere PDF-parser als stille fallback. Zonder xpdf
    pdftotext 4.06 blijft een ondersteund PDF op READY_FOR_EXTRACTION staan.
  - Nieuwe bestanden wijzigen NOOIT canonieke kennis. Er wordt alleen geschreven naar
      data/incoming_registry.json, data/incoming_batches/<batch_id>/ en reports/incoming/<batch_id>.json
    Canonieke lagen (data/raw, extracted, normalized, verified, price_observations, comparability,
    kengetallen, review_decisions, ...) en reports/document_registry.json worden alleen gelezen.
  - Identiteit = sha256. Bestandsnamen zijn metadata. Bestaande DOC-ID's verschuiven nooit.
  - Transactioneel: alles wordt eerst volledig in het geheugen opgebouwd en gevalideerd; daarna
    worden alle bestanden via tijdelijke bestanden + os.replace geschreven, het register als
    laatste. Bij een fout wordt alles teruggezet: geen half bijgewerkt register of halve batch.
  - Reproduceerbaar: geen tijdstempels; JSON UTF-8, LF, gesorteerde sleutels. Dezelfde invoer
    in dezelfde omgeving geeft byte-identieke uitvoer (standaard batch_id = inhoudshash).

Gebruik:
    python scripts/process_incoming_batch.py               # = --dry-run: toont wat er zou gebeuren
    python scripts/process_incoming_batch.py --process     # verwerkt en schrijft de staging-batch
    python scripts/process_incoming_batch.py --check       # controleert register en bestaande batches
Opties: --batch-id ID, --incoming-dir DIR, --pdftotext PAD, --require-xpdf, --runner-setup JSON
"""
import argparse
import copy
import hashlib
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_price_observations as bpo  # noqa: E402
import deterministic_extraction as de  # noqa: E402
import document_registry  # noqa: E402
import incoming_registry as ir  # noqa: E402
import mjop_source_sections as src  # noqa: E402
import normalize_batch as nb  # noqa: E402
import record_validation as rv  # noqa: E402
import template_detection as td  # noqa: E402
import text_layer as tl  # noqa: E402

PIPELINE_VERSION = "incoming_pipeline_v1"
MANIFEST_VERSION = "1.0.0"
STATUSES = ("NEW", "DUPLICATE_SKIP", "READY_FOR_EXTRACTION", "EXTRACTED", "REVIEW_REQUIRED",
            "UNKNOWN_TEMPLATE", "UNSUPPORTED_FORMAT", "FAILED_VALIDATION")

INCOMING_DIR = os.path.join("data", "incoming")
BATCHES_DIR = os.path.join("data", "incoming_batches")
REPORTS_DIR = os.path.join("reports", "incoming")
SCHEMAS = {"document": "incoming_document.schema.json", "manifest": "incoming_batch_manifest.schema.json",
           "report": "incoming_batch_report.schema.json"}
PROTECTED = ("data/raw", "data/extracted", "data/normalized", "data/verified", "data/price_observations",
             "data/comparability", "data/kengetallen", "data/review_decisions", "data/match_review_decisions",
             "data/extracted_deterministic", "reports/document_registry.json")
IGNORED_NAMES = {"thumbs.db", "desktop.ini"}
ROOT_IGNORED = {"README.md"}
BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
POSTCODE_RE = re.compile(r"\b([1-9]\d{3})\s?([A-Z]{2})\b")
MAX_DETAILS = 20


class PipelineError(RuntimeError):
    pass


# ------------------------------------------------------------------ helpers

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _posix(p):
    return p.replace("\\", "/")


def scan_incoming(incoming_dir):
    """Alle bestanden (ook in submappen), gesorteerd op relatief pad. Verborgen bestanden,
    Thumbs.db/desktop.ini en de README in de hoofdmap worden overgeslagen."""
    out = []
    if not os.path.isdir(incoming_dir):
        return out
    for root, dirs, files in os.walk(incoming_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for fn in sorted(files):
            if fn.startswith(".") or fn.lower() in IGNORED_NAMES:
                continue
            rel = _posix(os.path.relpath(os.path.join(root, fn), incoming_dir))
            if rel in ROOT_IGNORED:
                continue
            out.append(rel)
    return sorted(out)


def default_batch_id(shas):
    return "IB-" + sha256_bytes("\n".join(sorted(set(shas))).encode("utf-8"))[:12]


def _norm_postcode(text):
    m = POSTCODE_RE.search(text or "")
    return f"{m.group(1)}{m.group(2)}" if m else None


def _norm_text(text):
    return " ".join(str(text).lower().split()) if text else None


def _value(ev):
    return ev.get("value") if isinstance(ev, dict) else None


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


# ------------------------------------------------------------------ runner / xpdf

def runner_info(pdftotext=None, runner_setup=None):
    """Welke xpdf is beschikbaar en is de runner-installatie geverifieerd? Geen installatie hier."""
    setup = None
    if runner_setup and os.path.exists(runner_setup):
        with open(runner_setup, encoding="utf-8") as f:
            setup = json.load(f)
    try:
        binary, version = de.check_pdftotext(pdftotext)
    except de.DependencyError as e:
        return {"xpdf_available": False, "binary": None, "pdftotext_version": None,
                "unavailable_reason": str(e).split(".")[0], "runner_setup": setup,
                "runner_setup_status": (setup or {}).get("status", "NO_XPDF")}
    status = (setup or {}).get("status", "UNVERIFIED_RUNNER_SETUP")
    return {"xpdf_available": True, "binary": binary, "pdftotext_version": version,
            "unavailable_reason": None, "runner_setup": setup, "runner_setup_status": status}


def _public_runner(info):
    return {k: v for k, v in info.items() if k != "binary"}


# ------------------------------------------------------------------ validatie

def _check(name, result, count=0, details=()):
    return {"check": name, "result": result, "count": count, "details": list(details)[:MAX_DETAILS]}


def validate_extracted(record, doc_id, sha, page_count, recheck_missing):
    """Controles per geëxtraheerd document. result: PASS | WARN | REVIEW | FAIL.
    FAIL -> FAILED_VALIDATION, REVIEW -> REVIEW_REQUIRED (blokkeert promotie), WARN = zichtbaar,
    wordt in de normale human review afgehandeld."""
    checks = []
    schema_errors = rv.validate_entities(record)   # ook al in extract_file; hier expliciet vastgelegd
    checks.append(_check("schema", "PASS" if not schema_errors else "FAIL", len(schema_errors), schema_errors))
    meta = record.get("extraction_metadata", {})
    ok_hash = meta.get("source_sha256") == sha and record.get("document_id") == doc_id
    checks.append(_check("source_hash", "PASS" if ok_hash else "FAIL", 0 if ok_hash else 1))
    checks.append(_check("no_ai", "PASS" if meta.get("uses_ai_api") is False and meta.get("network_calls") is False
                         else "FAIL"))
    checks.append(_check("template_recheck_xpdf", "PASS" if not recheck_missing else "REVIEW",
                         len(recheck_missing), recheck_missing))

    bad_prov = []
    for path, p in rv.iter_provenance(record):
        if p.get("document_id") != doc_id or not isinstance(p.get("page"), int) or not 1 <= p["page"] <= page_count:
            bad_prov.append(str(path))
    checks.append(_check("provenance", "PASS" if not bad_prov else "FAIL", len(bad_prov), bad_prov))
    trace = record.get("deterministic_trace", {})
    nolink = trace.get("provenance_without_block_link", 0)
    checks.append(_check("provenance_block_links", "PASS" if not nolink else "WARN", nolink))

    elements = record.get("elements", [])
    no_code = [e["element_id"] for e in elements if not (e.get("element_code") or {}).get("original_value")]
    unclassified = trace.get("unclassified_element_overview_lines", [])
    checks.append(_check("elements", "FAIL" if not elements else ("REVIEW" if unclassified else
                                                                  ("WARN" if no_code else "PASS")),
                         len(elements), [f"zonder code: {i}" for i in no_code] +
                         [f"ongeclassificeerde regel p{u.get('page')}" for u in unclassified]))

    actions = record.get("maintenance_actions", [])
    checks.append(_check("maintenance_actions", "PASS" if actions else "FAIL", len(actions)))
    unlinked = [a["action_id"] for a in actions if str(a.get("element_id", "")).endswith("-EL-UNLINKED")]
    checks.append(_check("unlinked_records", "PASS" if not unlinked else "REVIEW", len(unlinked), unlinked))
    qty = [a["action_id"] for a in actions if _value(a.get("quantity")) is None]
    checks.append(_check("quantities", "PASS" if not qty else "WARN", len(qty), qty))
    units = [a["action_id"] for a in actions if (a.get("unit") or {}).get("requires_human_review")]
    checks.append(_check("units", "PASS" if not units else "WARN", len(units), units))

    no_amount = [a["action_id"] for a in actions if _dec(a.get("total_cost_as_stated")) is None]
    recon = [r for r in trace.get("row_reconciliation", []) if r.get("status") not in ("consistent", "zero")]
    evidence_ok = (meta.get("currency_evidence") or {}).get("consistent") is True
    amount_issues = [f"geen bedrag: {i}" for i in no_amount] + \
                    [f"rij p{r['page']} r{r['line']}: {r['status']}" for r in recon] + \
                    ([] if evidence_ok else ["valutabewijs niet consistent"])
    checks.append(_check("amounts", "PASS" if not amount_issues else "REVIEW", len(amount_issues), amount_issues))

    dv = record.get("document_level_values", {})
    checks.append(_check("vat", "PASS" if _value(dv.get("vat_statement")) else "WARN",
                         0 if _value(dv.get("vat_statement")) else 1))
    checks.append(_check("price_level", "PASS" if _value(dv.get("price_level_date")) else "WARN",
                         0 if _value(dv.get("price_level_date")) else 1))
    legend = _value(dv.get("condition_legend"))
    checks.append(_check("condition_legend", "PASS" if legend else "WARN", len(legend or [])))

    flags = sum(1 for _ in _review_flags(record))
    checks.append(_check("review_flags", "PASS" if not flags else "WARN", flags))
    results = {c["result"] for c in checks}
    outcome = "FAILED_VALIDATION" if "FAIL" in results else ("REVIEW_REQUIRED" if "REVIEW" in results else "EXTRACTED")
    return {"outcome": outcome, "checks": checks}


def _review_flags(node):
    if isinstance(node, dict):
        if node.get("requires_human_review") is True:
            yield node
        for v in node.values():
            yield from _review_flags(v)
    elif isinstance(node, list):
        for v in node:
            yield from _review_flags(v)


# ------------------------------------------------------------------ relaties

def _signals_from_record(record):
    dv, b = record.get("document_level_values", {}), record.get("building", {})
    return {"postcode": _norm_postcode(_value(dv.get("object_postcode"))),
            "address": _norm_text(_value(b.get("address"))),
            "price_level_date": _value(dv.get("price_level_date")),
            "inspection_date": _value(b.get("inspection_date"))}


def _signals_from_sheet(layer, header_loc):
    """Postcode uit de kopregels vóór de jarenplan-kolomkop (bijv. DOC-003)."""
    for loc, text in td.layer_lines(layer):
        if loc == header_loc:
            break
        pc = _norm_postcode(text)
        if pc:
            return {"postcode": pc, "address": None, "price_level_date": None, "inspection_date": None}
    return {"postcode": None, "address": None, "price_level_date": None, "inspection_date": None}


def known_documents(root, state_root, exclude_ids):
    """Signalen van canonieke documenten (data/extracted) en eerder gestagede batches. Alleen lezen."""
    out = {}
    ext = os.path.join(root, "data", "extracted")
    for fn in sorted(os.listdir(ext)) if os.path.isdir(ext) else []:
        if re.match(r"^DOC-\d+\.json$", fn):
            with open(os.path.join(ext, fn), encoding="utf-8") as f:
                rec = json.load(f)
            out[rec["document_id"]] = {"origin": "canonical", "kind": "pdf", **_signals_from_record(rec)}
    bdir = os.path.join(state_root, BATCHES_DIR)
    for batch in sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []:
        edir = os.path.join(bdir, batch, "extracted")
        for fn in sorted(os.listdir(edir)) if os.path.isdir(edir) else []:
            did = fn[:-5]
            if did in exclude_ids or did in out:
                continue
            with open(os.path.join(edir, fn), encoding="utf-8") as f:
                out[did] = {"origin": f"incoming_batch:{batch}", "kind": "pdf", **_signals_from_record(json.load(f))}
    return out


def relation_candidates(batch_docs, known):
    """Alleen KANDIDATEN; nooit automatisch dezelfde source cluster of een duplicate aannemen.
    SAME_BUILDING_CANDIDATE: zelfde objectpostcode of zelfde adres (exact, na witruimte/hoofdletters).
    POSSIBLE_DUPLICATE_OTHER_BYTES: spreadsheet-export van een jarenplan + PDF met dezelfde postcode
    (precedent DOC-003/DOC-002), of twee PDF's met dezelfde postcode, prijspeil en inspectiedatum."""
    pool = dict(known)
    pool.update({d: {"origin": "this_batch", **s} for d, s in batch_docs.items()})
    ids = sorted(pool, key=lambda x: document_registry._id_num(x))
    out = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if a not in batch_docs and b not in batch_docs:
                continue
            sa, sb = pool[a], pool[b]
            evidence = []
            if sa.get("postcode") and sa["postcode"] == sb.get("postcode"):
                evidence.append(f"objectpostcode gelijk: {sa['postcode']}")
            if sa.get("address") and sa["address"] == sb.get("address"):
                evidence.append(f"adres gelijk: {sa['address']}")
            if not evidence:
                continue
            kinds = {sa.get("kind"), sb.get("kind")}
            if kinds == {"pdf", "spreadsheet"}:
                kind = "POSSIBLE_DUPLICATE_OTHER_BYTES"
                evidence.append("spreadsheet-export van een jarenplan naast een PDF van hetzelfde object")
            elif sa.get("price_level_date") and (sa.get("price_level_date"), sa.get("inspection_date")) == \
                    (sb.get("price_level_date"), sb.get("inspection_date")):
                kind = "POSSIBLE_DUPLICATE_OTHER_BYTES"
                evidence.append(f"prijspeil en inspectiedatum gelijk: {sa['price_level_date']} / {sa['inspection_date']}")
            else:
                kind = "SAME_BUILDING_CANDIDATE"
            key = f"{a}|{b}|{kind}"
            out.append({"relation_candidate_id": "RC-" + sha256_bytes(key.encode())[:10], "document_ids": [a, b],
                        "origins": {a: pool[a]["origin"], b: pool[b]["origin"]}, "kind": kind,
                        "possible_meanings": ["same_building_other_inspection", "new_version", "subplan",
                                              "duplicate_other_bytes"],
                        "evidence": evidence, "status": "CANDIDATE_REQUIRES_HUMAN_CONFIRMATION",
                        "source_cluster": "NOT_ASSUMED"})
    return out


# ------------------------------------------------------------------ plan (alles in het geheugen)

def plan_batch(root, incoming_dir=None, state_root=None, batch_id=None, runner=None, extractor=None):
    """Bouwt de volledige batch in het geheugen. Schrijft niets. Returns plan-dict of None (leeg)."""
    state_root = state_root or root
    incoming_dir = incoming_dir or os.path.join(root, INCOMING_DIR)
    runner = runner or runner_info()
    extractor = extractor or de.extract_file
    canonical = document_registry.load_registry(os.path.join(root, ir.CANONICAL_REGISTRY_PATH))
    reg_path = os.path.join(state_root, ir.REGISTRY_PATH)
    old_registry = ir.load(reg_path)
    errs = ir.integrity_errors(old_registry, canonical)
    if errs:
        raise PipelineError(f"incoming-register ongeldig: {errs}")
    registry = json.loads(json.dumps(old_registry))

    files = scan_incoming(incoming_dir)
    if not files:
        return None
    entries = []
    for rel in files:
        path = os.path.join(incoming_dir, *rel.split("/"))
        entries.append({"input_path": rel, "abs": path, "sha256": ir.document_registry.sha256_of(path),
                        "file_size_bytes": os.path.getsize(path)})
    batch_id = batch_id or default_batch_id([e["sha256"] for e in entries])
    if not BATCH_ID_RE.match(batch_id):
        raise PipelineError(f"ongeldige batch-id: {batch_id!r}")

    docs, extracted, validations, layers, signals = [], {}, {}, {}, {}
    staged_extra = {"normalized": {}, "price_observations": {}}
    seen = {}
    for e in entries:
        d = {"input_path": e["input_path"], "sha256": e["sha256"], "file_size_bytes": e["file_size_bytes"],
             "format": None, "document_id": None, "registration": None, "duplicate_of": None,
             "status_history": ["NEW"], "reasons": [], "family": None, "extraction": None,
             "validation_outcome": None, "open_review_items": [], "price_observation_candidates": 0}
        docs.append(d)
        origin, known = ir.lookup(e["sha256"], registry, canonical)
        if origin == "canonical":
            d.update(duplicate_of=known["document_id"], registration="canonical_duplicate")
            d["reasons"].append(f"EXACT_SHA256_DUPLICATE_OF_CANONICAL:{known['document_id']}")
            d["status_history"].append("DUPLICATE_SKIP")
            continue
        if e["sha256"] in seen:
            d.update(duplicate_of=seen[e["sha256"]]["document_id"] or seen[e["sha256"]]["input_path"],
                     registration="in_batch_duplicate")
            d["reasons"].append("EXACT_SHA256_DUPLICATE_IN_BATCH")
            d["status_history"].append("DUPLICATE_SKIP")
            continue
        seen[e["sha256"]] = d
        fmt, reason = td.detect_format(e["abs"])
        d["format"] = fmt
        if fmt is None:
            d["reasons"].append(reason)
            d["status_history"].append("UNSUPPORTED_FORMAT")
            continue
        if origin == "incoming":
            # door DEZE batch geregistreerd (herhaalde run) = nog steeds "new": zelfde invoer, zelfde uitvoer
            d.update(document_id=known["document_id"],
                     registration="new" if known["first_batch_id"] == batch_id else "existing_incoming")
        else:
            new_id = f"DOC-{ir.next_id(registry, canonical):03d}"
            registry["documents"].append({"document_id": new_id, "sha256": e["sha256"], "format": fmt,
                                          "file_size_bytes": e["file_size_bytes"], "first_batch_id": batch_id,
                                          "first_observed_path": e["input_path"]})
            d.update(document_id=new_id, registration="new")
        reg_entry = next(r for r in registry["documents"] if r["document_id"] == d["document_id"])
        # stabiel, botsingsvrij bronpad (= toekomstig pad onder data/raw na promotie)
        doc_meta = {"relative_path": raw_relative_path(d["document_id"], reg_entry["first_observed_path"]),
                    "sha256": e["sha256"]}
        _process_document(d, e, doc_meta, runner, extractor, extracted, validations, layers, signals,
                          staged_extra, root)

    batch_docs = {d["document_id"]: signals[d["document_id"]] for d in docs if d["document_id"] in signals}
    known = known_documents(root, state_root, set(batch_docs))
    relations = relation_candidates(batch_docs, known)
    for d in docs:
        rel = [r["relation_candidate_id"] for r in relations if d["document_id"] in r["document_ids"]]
        if rel and d["status_history"][-1] in ("EXTRACTED", "READY_FOR_EXTRACTION", "REVIEW_REQUIRED"):
            d["open_review_items"].append("RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION")
            if d["status_history"][-1] == "EXTRACTED":
                d["status_history"].append("REVIEW_REQUIRED")
    for d in docs:
        d["status"] = d["status_history"][-1]
        assert d["status"] in STATUSES
    return {"batch_id": batch_id, "docs": docs, "extracted": extracted, "validations": validations,
            "normalized": staged_extra["normalized"], "price_observations": staged_extra["price_observations"],
            "relations": relations, "registry_old": old_registry, "registry": registry, "runner": runner,
            "root": root, "state_root": state_root}


def raw_relative_path(document_id, first_observed_path):
    """Pad onder data/raw na promotie: incoming/<DOC-ID>/<bestandsnaam>. Het DOC-ID maakt het uniek."""
    return f"incoming/{document_id}/{first_observed_path.split('/')[-1]}"


def normalization_lookups(root):
    vdir = os.path.join(root, "vocabularies")
    return {k: nb.load_vocab(vdir, v) for k, v in
            [("element_type", "element_type"), ("element_code", "element_code"), ("material", "material"),
             ("unit", "unit"), ("defect_type", "defect_type"), ("action", "maintenance_action")]}


def stage_downstream(record, pages, doc_meta, root):
    """Genormaliseerd record + price-observation-kandidaten van één document, met exact de bestaande
    regels (normalize_batch.normalize_record, build_price_observations.build_document). Alleen staging."""
    normalized = nb.normalize_record(copy.deepcopy(record), normalization_lookups(root))
    doc = {"document_id": record["document_id"], "relative_path": doc_meta["relative_path"],
           "sha256": doc_meta["sha256"], "file_type": "pdf"}
    unit_lookup = nb.load_vocab(os.path.join(root, "vocabularies"), "unit")
    extra, obs, unlinked, checks = bpo.build_document(doc, pages, copy.deepcopy(normalized), unit_lookup, [])
    relations = bpo.build_relations({doc["document_id"]: obs}, [])
    po = {"builder_version": bpo.BUILDER_VERSION,
          "note": "Kandidaat-price-observations (incoming staging). Relatie-ID's zijn lokaal en worden bij "
                  "promotie hernummerd. Niet canoniek.",
          "document": {**doc, "document_relation_ids": [], **extra},
          "checks": checks, "observations": obs, "observation_relations": relations,
          "unlinked_section_rows": unlinked}
    return normalized, po


def _process_document(d, e, doc_meta, runner, extractor, extracted, validations, layers, signals,
                      staged_extra=None, root=None):
    did = d["document_id"]
    try:
        layer = tl.build_text_layer_for_file(e["abs"], did, e["sha256"], doc_meta["relative_path"])
    except Exception as ex:  # corrupt/onleesbaar bestand: nooit gokken
        d["reasons"].append(f"TEXT_LAYER_FAILED:{type(ex).__name__}")
        d["status_history"].append("FAILED_VALIDATION")
        return
    fam = td.detect_family(d["format"], layer)
    d["family"] = {k: fam[k] for k in ("family_id", "markers", "reason", "detection_version")}
    if not fam["family_id"]:
        d["reasons"].append(fam["reason"])
        d["status_history"].append("UNKNOWN_TEMPLATE")
        return
    if d["format"] != "pdf":
        signals[did] = {"kind": "spreadsheet", **_signals_from_sheet(layer, fam["markers"]["jarenplan_header"])}
        d["reasons"].append("UNSUPPORTED_EXTRACTION")
        d["open_review_items"].append("UNSUPPORTED_EXTRACTION: geen productie-parser voor dit spreadsheetformaat")
        d["status_history"].append("REVIEW_REQUIRED")
        return
    d["status_history"].append("READY_FOR_EXTRACTION")
    signals[did] = {"kind": "pdf", "postcode": None, "address": None, "price_level_date": None,
                    "inspection_date": None}
    if not runner["xpdf_available"]:
        d["reasons"].append("XPDF_4_06_NOT_AVAILABLE")
        return
    profile = td.FAMILY_PROFILES[fam["family_id"]]
    try:
        record, pages = extractor(did, e["abs"], doc_meta, profile, runner["binary"], runner["pdftotext_version"],
                                  layer=layer)
    except de.ExtractionError as ex:
        d["reasons"].append("EXTRACTION_VALIDATION_FAILED")
        validations[did] = {"outcome": "FAILED_VALIDATION",
                            "checks": [_check("schema", "FAIL", len(ex.errors), [str(x) for x in ex.errors])]}
        d["validation_outcome"] = "FAILED_VALIDATION"
        d["status_history"].append("FAILED_VALIDATION")
        return
    except Exception as ex:
        d["reasons"].append(f"EXTRACTION_ERROR:{type(ex).__name__}")
        d["status_history"].append("FAILED_VALIDATION")
        return
    if ir.document_registry.sha256_of(e["abs"]) != e["sha256"]:
        d["reasons"].append("SOURCE_CHANGED_DURING_PROCESSING")
        d["status_history"].append("FAILED_VALIDATION")
        return
    missing = td.recheck_on_xpdf_pages(src.classify_sections(pages))
    val = validate_extracted(record, did, e["sha256"], len(pages), missing)
    validations[did] = val
    d["validation_outcome"] = val["outcome"]
    d["extraction"] = {"profile_id": profile["profile_id"], "profile_version": profile["profile_version"],
                       "extractor_version": de.EXTRACTOR_VERSION, "rules_version": de.RULES_VERSION,
                       "pdftotext_version": runner["pdftotext_version"],
                       "canonical_content_sha256": sha256_bytes(json.dumps(
                           record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))}
    extracted[did] = record
    signals[did] = {"kind": "pdf", **_signals_from_record(record)}
    if val["outcome"] != "FAILED_VALIDATION" and staged_extra is not None:
        try:
            normalized, po = stage_downstream(record, pages, doc_meta, root)
        except Exception as ex:  # nooit half gestaged: dan faalt het document
            val["checks"].append(_check("staging_downstream", "FAIL", 1, [f"{type(ex).__name__}: {ex}"]))
            val["outcome"] = "FAILED_VALIDATION"
        else:
            po_errors = po_schema_errors(root, po)
            diff = _dec(po["checks"].get("totaal_object_difference"))
            val["checks"].append(_check("price_observations", "FAIL" if po_errors else
                                        ("WARN" if diff not in (None, 0) else "PASS"),
                                        len(po["observations"]),
                                        po_errors or ([f"verschil met Totaal object: {diff}"] if diff else [])))
            if po_errors:
                val["outcome"] = "FAILED_VALIDATION"
            else:
                staged_extra["normalized"][did] = normalized
                staged_extra["price_observations"][did] = po
        d["validation_outcome"] = val["outcome"]
    d["price_observation_candidates"] = len(staged_extra["price_observations"].get(did, {}).get("observations", [])) \
        if staged_extra is not None else 0
    d["open_review_items"] += [f"{c['check']}: {c['count']}" for c in val["checks"] if c["result"] == "REVIEW"]
    if val["outcome"] == "FAILED_VALIDATION":
        d["status_history"].append("FAILED_VALIDATION")
    else:
        d["status_history"].append("EXTRACTED")
        if val["outcome"] == "REVIEW_REQUIRED":
            d["status_history"].append("REVIEW_REQUIRED")


def po_schema_errors(root, po):
    import jsonschema
    schema = json.load(open(os.path.join(root, "schemas", "price_observation.schema.json"), encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema)
    return [f"{o['observation_id']}: {e.message}" for o in po["observations"] for e in v.iter_errors(o)][:MAX_DETAILS]


# ------------------------------------------------------------------ outputs

PROPOSAL_DECISIONS = ("APPROVED_FOR_PROMOTION", "REVIEW_REQUIRED", "SKIPPED_DUPLICATE", "BLOCKED")


def proposal_decision(d, runner_ok, runner_status):
    """Beslissing per document in het promotievoorstel (zelfde labels als promote_incoming_batch.py).
    APPROVED_FOR_PROMOTION bestaat hier nog niet: dat vereist een menselijke goedkeuring (approval.json)."""
    if d["status"] == "DUPLICATE_SKIP":
        return "SKIPPED_DUPLICATE", [f"duplicate_of:{d['duplicate_of']}"]
    if d["status"] in ("UNKNOWN_TEMPLATE", "UNSUPPORTED_FORMAT", "FAILED_VALIDATION", "READY_FOR_EXTRACTION"):
        return "BLOCKED", [d["status"]] + d["reasons"]
    if "UNSUPPORTED_EXTRACTION" in d["reasons"]:
        return "BLOCKED", ["UNSUPPORTED_EXTRACTION"]
    if not runner_ok:
        return "BLOCKED", [f"RUNNER_NOT_VERIFIED:{runner_status}"]
    if d["status"] == "EXTRACTED":
        return "REVIEW_REQUIRED", ["AWAITING_HUMAN_APPROVAL"]
    return "REVIEW_REQUIRED", sorted(d["open_review_items"]) or ["REVIEW_REQUIRED"]


def kengetallen_impact(root, plan):
    """Mogelijke impact ALS de batch later wordt gepromoveerd. Er wordt niets gewijzigd."""
    path = os.path.join(root, "data", "kengetallen", "kengetallen_batch1.json")
    kg = json.load(open(path, encoding="utf-8"))["kengetallen"] if os.path.exists(path) else []
    codes = {}
    for k in kg:
        codes.setdefault(k["element_code"], []).append(k["kengetal_id"])
    touching = {}
    for did, rec in sorted(plan["extracted"].items()):
        el_code = {e["element_id"]: (e.get("element_code") or {}).get("original_value") for e in rec["elements"]}
        for a in rec["maintenance_actions"]:
            code = el_code.get(a["element_id"])
            if code in codes and (_dec(a.get("total_cost_as_stated")) or 0) > 0:
                for kid in codes[code]:
                    touching.setdefault(kid, set()).add(did)
    return {"existing_kengetallen_changed": 0,
            "statement": "Geen directe impact: kengetallen veranderen pas na een aparte promotie, comparability "
                         "en ACTIVE human decisions. Hieronder alleen welke bestaande kengetallen dezelfde "
                         "elementcode hebben (geen match, geen berekening).",
            "existing_kengetallen_with_same_element_code": [
                {"kengetal_id": k, "documents": sorted(v)} for k, v in sorted(touching.items())]}


def build_outputs(plan):
    """Alle te schrijven bestanden als {relatief pad (t.o.v. state_root): bytes}. Valideert tegen schemas."""
    root, bid = plan["root"], plan["batch_id"]
    bdir = f"{_posix(BATCHES_DIR)}/{bid}"
    files = {}
    docs_out = []
    for d in plan["docs"]:
        key = d["document_id"] or "INPUT-" + d["sha256"][:12]
        rec = {k: v for k, v in d.items()}
        rec["batch_id"] = bid
        rec["pipeline_version"] = PIPELINE_VERSION
        docs_out.append((key, rec))
    for key, rec in docs_out:
        files[f"{bdir}/documents/{key}.json"] = dumps(rec)
    for did, record in sorted(plan["extracted"].items()):
        files[f"{bdir}/extracted/{did}.json"] = de.dumps(record)
    for did, rec in sorted(plan.get("normalized", {}).items()):
        files[f"{bdir}/normalized/{did}.json"] = de.dumps(rec)
    for did, po in sorted(plan.get("price_observations", {}).items()):
        files[f"{bdir}/price_observations/{did}.json"] = dumps(po)
    for did, val in sorted(plan["validations"].items()):
        files[f"{bdir}/validation/{did}.json"] = dumps({"document_id": did, "batch_id": bid, **val})

    runner = _public_runner(plan["runner"])
    runner_ok = runner["runner_setup_status"] == "VERIFIED_RUNNER_SETUP"
    impact = kengetallen_impact(root, plan)
    proposal_docs = []
    for key, d in docs_out:
        decision, reasons = proposal_decision(d, runner_ok, runner["runner_setup_status"])
        proposal_docs.append({
            "key": key, "document_id": d["document_id"], "input_path": d["input_path"], "status": d["status"],
            "decision": decision, "reasons": reasons,
            "eligible_for_direct_promotion": reasons == ["AWAITING_HUMAN_APPROVAL"]})
    proposal = {
        "batch_id": bid, "status": "PROPOSAL_ONLY_NOT_EXECUTED", "requires_separate_promotion_step": True,
        "canonical_targets_not_written": ["data/raw", "data/extracted", "data/normalized", "data/verified",
                                          "data/price_observations", "data/comparability", "data/kengetallen"],
        "global_blockers": [] if runner_ok else [f"RUNNER_SETUP_NOT_VERIFIED:{runner['runner_setup_status']}"],
        "documents": proposal_docs, "relation_candidates": plan["relations"], "kengetallen_impact_if_promoted": impact,
        "rule": "Nieuwe documenten wijzigen nooit automatisch canonieke kennis. Promotie is een aparte, "
                "expliciete stap met menselijke review van de open punten en relatiekandidaten.",
    }
    files[f"{bdir}/promotion_proposal.json"] = dumps(proposal)

    by_status = {s: 0 for s in STATUSES if s != "NEW"}
    for d in plan["docs"]:
        by_status[d["status"]] += 1
    families = {}
    for d in plan["docs"]:
        if d["family"] and d["family"]["family_id"]:
            families[d["family"]["family_id"]] = families.get(d["family"]["family_id"], 0) + 1
    new_ids = [d["document_id"] for d in plan["docs"] if d["registration"] == "new"]
    manifest = {
        "manifest_version": MANIFEST_VERSION, "pipeline_version": PIPELINE_VERSION, "batch_id": bid,
        "status": "STAGED", "canonical_write": False, "uses_ai_api": False, "network_calls": False,
        "inputs": [{"input_path": d["input_path"], "sha256": d["sha256"], "file_size_bytes": d["file_size_bytes"],
                    "format": d["format"], "document_id": d["document_id"], "duplicate_of": d["duplicate_of"],
                    "status": d["status"]} for d in plan["docs"]],
        "runner": runner,
        "tool_versions": {"extractor_version": de.EXTRACTOR_VERSION, "rules_version": de.RULES_VERSION,
                          "detection_version": td.DETECTION_VERSION,
                          "text_layer": {"script": tl.GENERATOR, "version": tl.GENERATOR_VERSION,
                                         "libraries": tl.library_versions("pdf")}},
        "registry": {"path": _posix(ir.REGISTRY_PATH), "new_document_ids": new_ids,
                     "registry_sha256_after": sha256_bytes(ir.dumps(plan["registry"]).encode("utf-8"))},
        "files": {p[len(bdir) + 1:]: sha256_bytes(b.encode("utf-8")) for p, b in sorted(files.items())},
    }
    files[f"{bdir}/manifest.json"] = dumps(manifest)

    report = {
        "batch_id": bid, "pipeline_version": PIPELINE_VERSION, "staging_path": bdir,
        "manifest_sha256": sha256_bytes(files[f"{bdir}/manifest.json"].encode("utf-8")),
        "totals": {"total_files": len(plan["docs"]), "new_documents": len(new_ids),
                   "previously_registered_documents": sum(1 for d in plan["docs"]
                                                          if d["registration"] == "existing_incoming"),
                   "duplicates": by_status["DUPLICATE_SKIP"],
                   "supported_templates": sum(families.values()),
                   "extracted_successfully": sum(1 for d in plan["docs"] if "EXTRACTED" in d["status_history"]),
                   "review_required": by_status["REVIEW_REQUIRED"],
                   "ready_for_extraction": by_status["READY_FOR_EXTRACTION"],
                   "unknown_templates": by_status["UNKNOWN_TEMPLATE"],
                   "unsupported_formats": by_status["UNSUPPORTED_FORMAT"],
                   "validation_failures": by_status["FAILED_VALIDATION"],
                   "new_price_observation_candidates": sum(d["price_observation_candidates"] for d in plan["docs"]),
                   "relation_candidates": len(plan["relations"])},
        "by_status": by_status, "families": families,
        "runner_setup_status": runner["runner_setup_status"], "xpdf_available": runner["xpdf_available"],
        "documents": [{"key": key, "document_id": d["document_id"], "input_path": d["input_path"],
                       "status": d["status"], "reasons": d["reasons"], "open_review_items": d["open_review_items"],
                       "duplicate_of": d["duplicate_of"], "family": (d["family"] or {}).get("family_id"),
                       "price_observation_candidates": d["price_observation_candidates"]} for key, d in docs_out],
        "relation_candidates": [{k: r[k] for k in ("relation_candidate_id", "document_ids", "kind", "evidence")}
                                for r in plan["relations"]],
        "kengetallen_impact_if_promoted": impact,
        "canonical_data_changed": False,
        "next_steps": _next_steps(by_status, runner),
    }
    files[f"{_posix(REPORTS_DIR)}/{bid}.json"] = dumps(report)
    files[_posix(ir.REGISTRY_PATH)] = ir.dumps(plan["registry"])
    _validate_outputs(root, files, bdir)
    return files, report


def _next_steps(by_status, runner):
    steps = []
    if by_status["READY_FOR_EXTRACTION"]:
        steps.append("Ondersteunde PDF's wachten op xpdf 4.06: draai de GitHub Actions-workflow "
                     "'Process incoming MJOPs'.")
    if by_status["REVIEW_REQUIRED"]:
        steps.append("Bekijk de documenten met REVIEW_REQUIRED (open_review_items) en de relatiekandidaten.")
    if by_status["UNKNOWN_TEMPLATE"]:
        steps.append("UNKNOWN_TEMPLATE: dit rapportformaat wordt nog niet ondersteund; een nieuw profiel is "
                     "een aparte beslissing.")
    if by_status["UNSUPPORTED_FORMAT"]:
        steps.append("UNSUPPORTED_FORMAT: alleen PDF, XLS en XLSX worden verwerkt.")
    if by_status["FAILED_VALIDATION"]:
        steps.append("FAILED_VALIDATION: zie validation/<DOC-ID>.json in de batchmap.")
    if runner["runner_setup_status"] != "VERIFIED_RUNNER_SETUP":
        steps.append(f"Runner-status {runner['runner_setup_status']}: promotie blijft geblokkeerd tot de "
                     "xpdf-installatie is geverifieerd.")
    steps.append("Promotie naar canonieke data is een aparte stap; deze batch wijzigt niets canoniek.")
    return steps


def _validate_outputs(root, files, bdir):
    import jsonschema
    sdir = os.path.join(root, "schemas")
    load = lambda n: json.load(open(os.path.join(sdir, SCHEMAS[n]), encoding="utf-8"))  # noqa: E731
    checks = [(p, "document") for p in files if p.startswith(f"{bdir}/documents/")] + \
             [(f"{bdir}/manifest.json", "manifest"), (next(p for p in files if p.startswith(_posix(REPORTS_DIR))),
                                                      "report")]
    errors = []
    for p, n in checks:
        v = jsonschema.Draft7Validator(load(n))
        errors += [f"{p}: {e.message}" for e in v.iter_errors(json.loads(files[p]))]
    if errors:
        raise PipelineError(f"schemavalidatie van de batch-uitvoer mislukt: {errors[:5]}")


# ------------------------------------------------------------------ transactioneel schrijven

def _guard(state_root, rel):
    rel = _posix(os.path.normpath(rel))
    allowed = (_posix(BATCHES_DIR) + "/", _posix(REPORTS_DIR) + "/")
    if not (rel.startswith(allowed) or rel == _posix(ir.REGISTRY_PATH)):
        raise PipelineError(f"weigering: {rel} valt buiten de toegestane incoming-uitvoer")
    for p in PROTECTED:
        if rel == p or rel.startswith(p + "/"):
            raise PipelineError(f"weigering: {rel} is canoniek")
    return os.path.join(state_root, *rel.split("/"))


def plan_writes(state_root, files, batch_id):
    """Bepaalt write/delete-operaties. Bestaat de batch al met andere inhoud, dan gaat de oude
    versie eerst naar <batch>/history/<manifest-sha12>/ (nooit verwijderen zonder history)."""
    bdir_rel = f"{_posix(BATCHES_DIR)}/{batch_id}"
    bdir = os.path.join(state_root, *bdir_rel.split("/"))
    ops = []
    existing = {}
    if os.path.isdir(bdir):
        for r, dirs, fns in os.walk(bdir):
            dirs[:] = [x for x in dirs if not (r == bdir and x == "history")]
            for fn in fns:
                p = os.path.join(r, fn)
                existing[f"{bdir_rel}/{_posix(os.path.relpath(p, bdir))}"] = open(p, "rb").read()
    new_batch = {p: b.encode("utf-8") for p, b in files.items() if p.startswith(bdir_rel + "/")}
    if existing and existing != new_batch:
        old_manifest = existing.get(f"{bdir_rel}/manifest.json", b"")
        hdir = f"{bdir_rel}/history/{sha256_bytes(old_manifest)[:12]}"
        for p, b in sorted(existing.items()):
            ops.append(("write", f"{hdir}/{p[len(bdir_rel) + 1:]}", b))
        for p in sorted(set(existing) - set(new_batch)):
            ops.append(("delete", p, None))
    for p, b in sorted(files.items()):
        data = b.encode("utf-8")
        target = os.path.join(state_root, *p.split("/"))
        if os.path.exists(target) and open(target, "rb").read() == data:
            continue
        ops.append(("write", p, data))
    # register altijd als laatste
    ops.sort(key=lambda o: o[1] == _posix(ir.REGISTRY_PATH))
    return ops


def apply_writes(state_root, ops):
    """Alles-of-niets: eerst alle tijdelijke bestanden, dan os.replace; bij een fout terugzetten."""
    temps, applied = [], []
    try:
        for kind, rel, data in ops:
            target = _guard(state_root, rel)
            if kind == "write":
                os.makedirs(os.path.dirname(target), exist_ok=True)
                tmp = target + ".incoming-tmp"
                with open(tmp, "wb") as f:
                    f.write(data)
                temps.append(tmp)
        for kind, rel, data in ops:
            target = _guard(state_root, rel)
            backup = open(target, "rb").read() if os.path.exists(target) else None
            if kind == "write":
                os.replace(target + ".incoming-tmp", target)
            else:
                os.remove(target)
            applied.append((target, backup))
    except BaseException:
        for target, backup in reversed(applied):
            if backup is None:
                if os.path.exists(target):
                    os.remove(target)
            else:
                with open(target, "wb") as f:
                    f.write(backup)
        for tmp in temps:
            if os.path.exists(tmp):
                os.remove(tmp)
        _prune_empty(state_root)
        raise
    return [rel for _, rel, _ in ops]


def _prune_empty(state_root):
    for base in (BATCHES_DIR, REPORTS_DIR):
        top = os.path.join(state_root, base)
        for r, dirs, fns in sorted(os.walk(top), key=lambda x: -len(x[0])) if os.path.isdir(top) else []:
            if r != top and not os.listdir(r):
                os.rmdir(r)


# ------------------------------------------------------------------ check

def check(root, state_root=None):
    state_root = state_root or root
    errors = []
    canonical = document_registry.load_registry(os.path.join(root, ir.CANONICAL_REGISTRY_PATH))
    reg = ir.load(os.path.join(state_root, ir.REGISTRY_PATH))
    errors += ir.integrity_errors(reg, canonical)
    bdir = os.path.join(state_root, BATCHES_DIR)
    for batch in sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []:
        mpath = os.path.join(bdir, batch, "manifest.json")
        if not os.path.isfile(mpath):
            continue
        m = json.load(open(mpath, encoding="utf-8"))
        for rel, h in m["files"].items():
            p = os.path.join(bdir, batch, *rel.split("/"))
            if not os.path.isfile(p) or sha256_bytes(open(p, "rb").read()) != h:
                errors.append(f"{batch}/{rel}: ontbreekt of sha256 wijkt af van manifest")
        if m.get("canonical_write") is not False:
            errors.append(f"{batch}: manifest.canonical_write moet false zijn")
        ids = {d["document_id"] for d in reg["documents"]}
        for new in m["registry"]["new_document_ids"]:
            if new not in ids:
                errors.append(f"{batch}: {new} ontbreekt in het incoming-register")
        if not os.path.isfile(os.path.join(state_root, REPORTS_DIR, f"{batch}.json")):
            errors.append(f"{batch}: rapport ontbreekt in {REPORTS_DIR}")
    return errors


# ------------------------------------------------------------------ CLI

def summary_lines(report):
    t = report["totals"]
    lines = [f"Batch {report['batch_id']}  (runner: {report['runner_setup_status']}, "
             f"xpdf {'beschikbaar' if report['xpdf_available'] else 'NIET beschikbaar'})"]
    lines += [f"  {k}: {v}" for k, v in t.items()]
    lines += ["Documenten:"] + [f"  {d['key']:<22} {d['status']:<20} {d['input_path']}" for d in report["documents"]]
    lines += ["Volgende stappen:"] + [f"  - {s}" for s in report["next_steps"]]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="Incoming / bulk MJOP pipeline v1 (geen AI, geen canonieke writes)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--process", action="store_true", help="verwerken en de staging-batch schrijven")
    mode.add_argument("--dry-run", action="store_true", help="alleen tonen wat er zou gebeuren (standaard)")
    mode.add_argument("--check", action="store_true", help="register en bestaande batches controleren")
    ap.add_argument("--batch-id", help="eigen batch-id (standaard: IB-<inhoudshash>)")
    ap.add_argument("--incoming-dir", help="standaard data/incoming")
    ap.add_argument("--pdftotext", help="pad naar xpdf pdftotext 4.06")
    ap.add_argument("--require-xpdf", action="store_true", help="stoppen als xpdf 4.06 ontbreekt (CI)")
    ap.add_argument("--runner-setup", help="runner_setup.json van scripts/xpdf_runner_setup.py")
    ap.add_argument("--summary-md", help="schrijf een korte markdown-samenvatting (bijv. GITHUB_STEP_SUMMARY)")
    ap.add_argument("--state-root", help="andere map voor register/batches/rapport (zelftest); standaard de repo")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    state_root = os.path.abspath(args.state_root) if args.state_root else root
    if args.check:
        errors = check(root, state_root)
        print("\n".join(errors) if errors else "CHECK OK")
        return 1 if errors else 0
    runner = runner_info(args.pdftotext, args.runner_setup)
    if args.require_xpdf and not runner["xpdf_available"]:
        print(f"FOUT: xpdf pdftotext 4.06 vereist maar niet beschikbaar: {runner['unavailable_reason']}",
              file=sys.stderr)
        return 3
    try:
        plan = plan_batch(root, args.incoming_dir, state_root=state_root, batch_id=args.batch_id, runner=runner)
        if plan is None:
            print("Geen bestanden in data/incoming/ - niets te doen.")
            return 0
        files, report = build_outputs(plan)
        errs = ir.append_only_errors(plan["registry_old"], plan["registry"])
        if errs:
            raise PipelineError(f"register niet append-only: {errs}")
    except (PipelineError, document_registry.RegistryError) as e:
        print(f"FOUT: {e}", file=sys.stderr)
        return 2
    lines = summary_lines(report)
    if args.process:
        written = apply_writes(state_root, plan_writes(state_root, files, plan["batch_id"]))
        lines.append(f"Geschreven: {len(written)} bestand(en); rapport: reports/incoming/{plan['batch_id']}.json")
    else:
        lines.append("DRY-RUN: niets geschreven. Gebruik --process om de batch te schrijven.")
    print("\n".join(lines))
    if args.summary_md:
        with open(args.summary_md, "a", encoding="utf-8") as f:
            f.write("## Incoming MJOP-batch\n\n```\n" + "\n".join(lines) + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
