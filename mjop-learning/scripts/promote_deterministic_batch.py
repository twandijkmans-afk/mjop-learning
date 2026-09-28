#!/usr/bin/env python3
"""
promote_deterministic_batch.py  (PROMOTION FOUNDATIONS v1 - alleen controle en analyse)

Werkt op de gevalideerde deterministische handoff-laag
data/extracted_deterministic/batch1_v1/ (9 PASS-documenten + manifest).

  --check    Controleert de opgeslagen handoff-laag zonder xpdf opnieuw te draaien:
             manifeststructuur, manifest.sha256, documentset DOC-001..DOC-010
             (exact 9 PASS + DOC-003 DUPLICATE_SKIP), source_sha256 tegen het
             document_registry en het ruwe bestand, output_sha256, metadata
             (parser/profiel/extractor, xpdf 4.06) en de inhoud van elk record
             tegen zijn manifestregel. Schrijft niets. Exitcode 0 = geldig.

  --dry-run  Voert eerst --check uit en schrijft daarna ALLEEN een analyserapport
             (standaard reports/deterministic_promotion_batch1_v1.json):
             verschillen met data/extracted, data/normalized en data/verified
             (gecategoriseerd A-G), classificatie van de oude review-accepts
             (EXACT_MATCH_CANDIDATE / AMBIGUOUS / NO_MATCH) en een read-only
             analyse van data/review_decisions/human_decision_records.json.
             Er wordt niets gepromoot, gemigreerd of in data/ geschreven.

Harde regels: verified-data is geen gouden standaard; geen fuzzy matching (alleen
exacte sleutels na witruimte-/hoofdletter-/getalnormalisatie); geen accept wordt
overgenomen; human decisions worden nooit toegevoegd, gewijzigd of gesuperseded;
pair_id-volgnummers worden niet als identiteit gebruikt.

output_sha256 is STRIKT: het moet gelijk zijn aan de sha256 van de bytes in de
repository. Er is geen line-ending-tolerantie. Wijkt de hash af, dan is dat een fout;
--check voegt alleen een diagnose toe (output_hash_diagnosis: of uitsluitend LF->CRLF
de manifest-hash oplevert, of de geparste JSON gelijk is, de canonieke inhoudshash) -
de diagnose maakt de check nooit geldig. Zie docs/promotion_foundations_v1.md
(manifest v1.1-voorstel).

--dry-run weigert bij een ongeldige handoff, tenzij expliciet
--analyse-despite-invalid-handoff wordt meegegeven; het rapport zegt dan
handoff_valid: false met alle fouten.

Uitvoer: UTF-8, newline '\\n', gesorteerde sleutels, geen tijdstempels -
twee runs op dezelfde invoer zijn byte-identiek.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

TOOL_VERSION = "promote_deterministic_batch_v1.0.0"
BATCH_ID = "batch1_v1"
BATCH_DIR = os.path.join("data", "extracted_deterministic", BATCH_ID)
EXPECTED_DOCUMENTS = [f"DOC-{i:03d}" for i in range(1, 11)]
EXPECTED_DUPLICATES = {"DOC-003": {"duplicate_of": "DOC-002", "relation": "DREL-001"}}
EXPECTED_PASS = [d for d in EXPECTED_DOCUMENTS if d not in EXPECTED_DUPLICATES]
XPDF = "pdftotext version 4.06 [www.xpdfreader.com]"
DEFAULT_REPORT = os.path.join("reports", "deterministic_promotion_batch1_v1.json")
CANONICAL_DIRS = ("extracted", "normalized", "verified")

MANIFEST_TOP_KEYS = {"batch_id", "branch", "documents", "manifest_version", "source_commit", "xpdf_version"}
PASS_KEYS = {"code_commit", "currency_rule", "document_id", "document_profile", "extraction_mode", "extractor",
             "extractor_version", "output_path", "output_sha256", "parser_family", "pdftotext_version",
             "rules_version", "source_path", "source_sha256", "status"}
PASS_OPTIONAL_KEYS = {"code_commit_verification"}
DUPLICATE_KEYS = {"document_id", "duplicate_of", "relation", "source_path", "source_sha256", "status"}


# ------------------------------------------------------------------ helpers

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(obj))


def squash(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def to_decimal(v):
    """Bedrag/hoeveelheid naar Decimal: '332,00', '332.00', '€ 23.667', '23667',
    '€ 1.233 (totaal; ...)' (alleen het eerste bedrag). None als het niet exact kan."""
    if v is None:
        return None
    s = str(v).replace("€", " ").replace("\xa0", " ").strip()
    m = re.match(r"^-?[\d.,]+", s)
    if not m:
        return None
    s = m.group(0)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def dec_str(d):
    return None if d is None else format(d.normalize(), "f")


def value_of(field):
    if isinstance(field, dict):
        if "value" in field:
            return field["value"]
        return field.get("original_value")
    return field


# ------------------------------------------------------------------ --check

def canonical_content_sha256(obj):
    """Line-ending-onafhankelijke inhoudshash: sha256 van de geparste JSON, opnieuw
    geserialiseerd met gesorteerde sleutels, compacte scheidingstekens, UTF-8."""
    return sha256_bytes(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def diagnose_output_hash(data, expected):
    """Alleen diagnose bij een afwijkende output_sha256 - maakt nooit iets geldig."""
    crlf = data.replace(b"\n", b"\r\n")
    diag = {"repository_sha256": sha256_bytes(data), "manifest_output_sha256": expected,
            "repository_contains_cr": b"\r" in data,
            "manifest_matches_lf_to_crlf_only": b"\r" not in data and sha256_bytes(crlf) == expected}
    try:
        parsed = json.loads(data.decode("utf-8"))
        diag["json_equal_after_lf_to_crlf"] = parsed == json.loads(crlf.decode("utf-8"))
        diag["canonical_content_sha256"] = canonical_content_sha256(parsed)
    except ValueError:
        diag["json_equal_after_lf_to_crlf"] = None
        diag["canonical_content_sha256"] = None
    return diag


def check_handoff(root, batch_dir=BATCH_DIR):
    """Returns {'ok', 'errors', 'warnings', 'documents'}. Schrijft niets."""
    errors, warnings, docs_out = [], [], {}
    bdir = os.path.join(root, batch_dir)
    mpath = os.path.join(bdir, "manifest.json")
    spath = os.path.join(bdir, "manifest.sha256")
    if not os.path.isfile(mpath):
        return {"ok": False, "errors": [f"manifest.json ontbreekt in {batch_dir}"], "warnings": [], "documents": {}}

    # manifest.sha256
    if not os.path.isfile(spath):
        errors.append("manifest.sha256 ontbreekt")
    else:
        line = open(spath, encoding="utf-8").read().strip()
        m = re.fullmatch(r"([0-9a-f]{64})\s+\*?manifest\.json", line)
        if not m:
            errors.append(f"manifest.sha256 heeft een onverwacht formaat: {line!r}")
        elif m.group(1) != sha256_file(mpath):
            errors.append("manifest.sha256 klopt niet met manifest.json")

    try:
        manifest = load_json(mpath)
    except ValueError as e:
        return {"ok": False, "errors": errors + [f"manifest.json is geen geldige JSON: {e}"], "warnings": [],
                "documents": {}}

    # structuur
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_TOP_KEYS:
        errors.append(f"manifest-sleutels wijken af: {sorted(manifest) if isinstance(manifest, dict) else type(manifest)}")
        manifest = manifest if isinstance(manifest, dict) else {}
    if manifest.get("batch_id") != BATCH_ID:
        errors.append(f"batch_id is {manifest.get('batch_id')!r}, verwacht {BATCH_ID!r}")
    if manifest.get("xpdf_version") != XPDF:
        errors.append(f"xpdf_version is {manifest.get('xpdf_version')!r}, verwacht {XPDF!r}")
    entries = manifest.get("documents")
    if not isinstance(entries, list):
        errors.append("manifest.documents is geen lijst")
        entries = []
    ids = [e.get("document_id") for e in entries if isinstance(e, dict)]
    dup_ids = sorted(d for d, n in Counter(ids).items() if n > 1)
    if dup_ids:
        errors.append(f"dubbele document_id's in manifest: {dup_ids}")
    unexpected = sorted(set(ids) - set(EXPECTED_DOCUMENTS))
    missing = sorted(set(EXPECTED_DOCUMENTS) - set(ids))
    if unexpected:
        errors.append(f"onverwachte documenten in manifest: {unexpected}")
    if missing:
        errors.append(f"ontbrekende documenten in manifest: {missing}")

    registry = {d["document_id"]: d for d in load_json(os.path.join(root, "reports", "document_registry.json"))["documents"]}
    relations = {r["relation_id"]: r for r in
                 load_json(os.path.join(root, "data", "price_observations", "document_relations.json"))["relations"]}

    statuses = {}
    for e in entries:
        if not isinstance(e, dict):
            errors.append(f"manifestregel is geen object: {e!r}")
            continue
        doc = e.get("document_id")
        status = e.get("status")
        statuses[doc] = status
        info = {"status": status}
        docs_out[doc] = info

        # bron: registry + ruw bestand
        reg = registry.get(doc)
        if reg is None:
            errors.append(f"{doc}: staat niet in document_registry")
        else:
            if e.get("source_sha256") != reg["sha256"]:
                errors.append(f"{doc}: source_sha256 wijkt af van document_registry")
            if e.get("source_path") != "data/raw/" + reg["relative_path"]:
                errors.append(f"{doc}: source_path wijkt af van document_registry")
            raw = os.path.join(root, *str(e.get("source_path", "")).split("/"))
            if not os.path.isfile(raw):
                errors.append(f"{doc}: bronbestand ontbreekt ({e.get('source_path')})")
            elif sha256_file(raw) != e.get("source_sha256"):
                errors.append(f"{doc}: bronbestand heeft een andere sha256 dan het manifest")

        if status == "DUPLICATE_SKIP":
            exp = EXPECTED_DUPLICATES.get(doc)
            if set(e) != DUPLICATE_KEYS:
                errors.append(f"{doc}: DUPLICATE_SKIP-sleutels wijken af: {sorted(e)}")
            if exp is None:
                errors.append(f"{doc}: onverwacht DUPLICATE_SKIP")
            else:
                if e.get("duplicate_of") != exp["duplicate_of"] or e.get("relation") != exp["relation"]:
                    errors.append(f"{doc}: DUPLICATE_SKIP moet duplicate_of {exp['duplicate_of']} / "
                                  f"relation {exp['relation']} zijn")
                rel = relations.get(exp["relation"]) or {}
                if not (rel.get("type") == "duplicate_source" and rel.get("primary_document_id") == exp["duplicate_of"]
                        and rel.get("secondary_document_id") == doc):
                    errors.append(f"{doc}: {exp['relation']} in document_relations.json bevestigt de duplicaatrelatie niet")
            if "output_path" in e or "output_sha256" in e:
                errors.append(f"{doc}: DUPLICATE_SKIP mag geen output hebben")
            if os.path.exists(os.path.join(bdir, f"{doc}.json")):
                errors.append(f"{doc}: DUPLICATE_SKIP maar {doc}.json staat in {batch_dir}")
            continue

        if status != "PASS":
            errors.append(f"{doc}: status {status!r} (alleen PASS of DUPLICATE_SKIP toegestaan)")
            continue
        if doc in EXPECTED_DUPLICATES:
            errors.append(f"{doc}: moet DUPLICATE_SKIP zijn, niet PASS")
        if not PASS_KEYS <= set(e) <= PASS_KEYS | PASS_OPTIONAL_KEYS:
            errors.append(f"{doc}: PASS-sleutels wijken af (ontbrekend {sorted(PASS_KEYS - set(e))}, "
                          f"extra {sorted(set(e) - PASS_KEYS - PASS_OPTIONAL_KEYS)})")
        if e.get("code_commit") != manifest.get("source_commit"):
            errors.append(f"{doc}: code_commit wijkt af van manifest.source_commit")
        exp_path = f"{batch_dir.replace(os.sep, '/')}/{doc}.json"
        if e.get("output_path") != exp_path:
            errors.append(f"{doc}: output_path {e.get('output_path')!r}, verwacht {exp_path!r}")
        out = os.path.join(root, *str(e.get("output_path", "")).split("/"))
        if not os.path.isfile(out):
            errors.append(f"{doc}: outputbestand ontbreekt ({e.get('output_path')})")
            continue
        data = open(out, "rb").read()
        info["repository_sha256"] = sha256_bytes(data)
        if sha256_bytes(data) != e.get("output_sha256"):
            diag = diagnose_output_hash(data, e.get("output_sha256"))
            info["output_hash_diagnosis"] = diag
            errors.append(f"{doc}: output_sha256 klopt niet met de repository-bytes"
                          + (" (diagnose: manifest-hash = sha256 van LF->CRLF; JSON-inhoud gelijk)"
                             if diag["manifest_matches_lf_to_crlf_only"] and diag["json_equal_after_lf_to_crlf"] else ""))

        # metadata in manifest
        if e.get("pdftotext_version") != XPDF:
            errors.append(f"{doc}: pdftotext_version is geen xpdf 4.06")
        if e.get("extraction_mode") != "deterministic":
            errors.append(f"{doc}: extraction_mode is niet 'deterministic'")
        prof = e.get("document_profile") or {}
        if not (prof.get("profile_id") and prof.get("profile_version") and e.get("parser_family")
                and e.get("extractor") and e.get("extractor_version") and e.get("rules_version")):
            errors.append(f"{doc}: parser-/profiel-/extractormetadata onvolledig")

        # record-inhoud tegen manifest
        try:
            rec = json.loads(data.decode("utf-8"))
        except ValueError as ex:
            errors.append(f"{doc}: output is geen geldige JSON: {ex}")
            continue
        md = rec.get("extraction_metadata") or {}
        checks = [("document_id", rec.get("document_id"), doc),
                  ("extraction_mode", rec.get("extraction_mode"), "deterministic"),
                  ("source_sha256", md.get("source_sha256"), e.get("source_sha256")),
                  ("source_relative_path", "data/raw/" + str(md.get("source_relative_path")), e.get("source_path")),
                  ("pdftotext_version", md.get("pdftotext_version"), e.get("pdftotext_version")),
                  ("extractor", md.get("extractor"), e.get("extractor")),
                  ("extractor_version", md.get("extractor_version"), e.get("extractor_version")),
                  ("document_profile", md.get("document_profile"), prof.get("profile_id")),
                  ("profile_version", md.get("profile_version"), prof.get("profile_version")),
                  ("rules_version", md.get("rules_version"), e.get("rules_version")),
                  ("currency_rule", md.get("currency_rule"), e.get("currency_rule")),
                  ("uses_ai_api", md.get("uses_ai_api"), False),
                  ("network_calls", md.get("network_calls"), False)]
        for name, got, want in checks:
            if got != want:
                errors.append(f"{doc}: record {name}={got!r} past niet bij manifest ({want!r})")
        info.update(elements=len(rec.get("elements", [])), observations=len(rec.get("observations", [])),
                    maintenance_actions=len(rec.get("maintenance_actions", [])),
                    text_layer_libraries=(md.get("text_layer_generator") or {}).get("libraries"))

    pass_docs = sorted(d for d, s in statuses.items() if s == "PASS")
    dup_docs = sorted(d for d, s in statuses.items() if s == "DUPLICATE_SKIP")
    if pass_docs != EXPECTED_PASS:
        errors.append(f"PASS-set is {pass_docs}, verwacht {EXPECTED_PASS}")
    if dup_docs != sorted(EXPECTED_DUPLICATES):
        errors.append(f"DUPLICATE_SKIP-set is {dup_docs}, verwacht {sorted(EXPECTED_DUPLICATES)}")

    # geen onverwachte bestanden in de batchmap
    allowed = {f"{d}.json" for d in EXPECTED_PASS} | {"manifest.json", "manifest.sha256"}
    extra = sorted(os.path.basename(p) for p in glob.glob(os.path.join(bdir, "*")) if os.path.basename(p) not in allowed)
    if extra:
        errors.append(f"onverwachte bestanden in {batch_dir}: {extra}")

    return {"ok": not errors, "errors": errors, "warnings": warnings, "documents": docs_out,
            "manifest": {k: manifest.get(k) for k in sorted(MANIFEST_TOP_KEYS - {"documents"})}}


# ------------------------------------------------------------------ vergelijking

def element_key(el, with_code):
    code = value_of(el.get("element_code")) if with_code else None
    name = value_of(el.get("element_name")) or value_of(el.get("element_type"))
    return (code, squash(name), squash(value_of(el.get("location"))),
            dec_str(to_decimal(value_of(el.get("quantity")))), squash(value_of(el.get("unit"))))


def new_rows(rec):
    """Groepeert de nieuwe acties (één per jaarbedrag) per bronrij. Een bronrij =
    zelfde pagina + zelfde provenance-tekst + zelfde block_id + actietekst/hoeveelheid/eenheid."""
    rows = {}
    for a in rec.get("maintenance_actions", []):
        prov = (a.get("action") or {}).get("provenance") or {}
        key = (a.get("source_page"), prov.get("text_fragment"), prov.get("block_id"),
               squash(value_of(a.get("action"))), dec_str(to_decimal(value_of(a.get("quantity")))),
               squash(value_of(a.get("unit"))))
        r = rows.setdefault(key, {"page": a.get("source_page"), "action_text": squash(value_of(a.get("action"))),
                                  "quantity": key[4], "unit": key[5], "block_id": prov.get("block_id"),
                                  "text_fragment": prov.get("text_fragment"),
                                  "years": [], "action_ids": [], "element_ids": set()})
        r["years"].append((value_of(a.get("planned_year")), to_decimal(a.get("total_cost_as_stated"))))
        r["action_ids"].append(a["action_id"])
        r["element_ids"].add(a.get("element_id"))
    return list(rows.values())


def match_old_action(old, rows):
    """Exacte koppeling van een oude actie aan een nieuwe bronrij.
    Returns (class, detail). class in EXACT_MATCH_CANDIDATE / AMBIGUOUS / NO_MATCH."""
    page = old.get("source_page") or ((old.get("planned_year") or {}).get("provenance") or {}).get("page")
    text = squash(value_of(old.get("action")))
    qty = dec_str(to_decimal(value_of(old.get("quantity"))))
    unit = squash(value_of(old.get("unit")))
    amount = to_decimal(old.get("total_cost_as_stated"))
    year = value_of(old.get("planned_year"))
    base = {"page": page, "action_text": text, "quantity": qty, "unit": unit, "amount": dec_str(amount), "planned_year": year}
    if None in (page, qty, amount) or not text:
        return "NO_MATCH", dict(base, reason="old_action_missing_key_field")
    cands = [r for r in rows if r["page"] == page and r["action_text"] == text and r["quantity"] == qty
             and r["unit"] == unit]
    if not cands:
        same_text = [r for r in rows if r["action_text"] == text]
        # Hulpinformatie voor menselijke review (geen koppeling): rijen die op alles behalve de
        # actietekst exact gelijk zijn (pagina, hoeveelheid, eenheid, jaar en jaarbedrag).
        text_only = [r for r in rows if r["page"] == page and r["quantity"] == qty and r["unit"] == unit
                     and (year, amount) in r["years"]]
        return "NO_MATCH", dict(base, reason="no_row_with_same_page_text_quantity_unit",
                                same_text_rows_elsewhere=len(same_text),
                                rows_equal_except_action_text=len(text_only))
    hits = []
    for r in cands:
        years = {y: amt for y, amt in r["years"]}
        total = sum((amt for _, amt in r["years"] if amt is not None), Decimal(0))
        if year in years and years[year] == amount:
            hits.append((r, "per_year_amount"))
        elif year in years and total == amount:
            hits.append((r, "row_total_over_years" if len(r["years"]) > 1 else "per_year_amount"))
    if not hits:
        return "NO_MATCH", dict(base, reason="amount_or_year_differs", candidate_rows=len(cands))
    if len(hits) > 1:
        return "AMBIGUOUS", dict(base, reason="multiple_identical_source_rows",
                                 candidate_action_ids=sorted(i for r, _ in hits for i in r["action_ids"]))
    r, how = hits[0]
    return "EXACT_MATCH_CANDIDATE", dict(base, amount_basis=how, new_action_ids=sorted(r["action_ids"]),
                                         new_block_id=r["block_id"], new_element_ids=sorted(x for x in r["element_ids"] if x))


def load_canonical(root, layer, doc):
    p = os.path.join(root, "data", layer, f"{doc}.json")
    return load_json(p) if os.path.isfile(p) else None


def compare_document(root, doc, new):
    old = {layer: load_canonical(root, layer, doc) for layer in CANONICAL_DIRS}
    ver = old["verified"] or {}
    cats = Counter()
    details = defaultdict(list)

    # hashes / aanwezigheid van de oude lagen
    layers = {layer: (sha256_file(os.path.join(root, "data", layer, f"{doc}.json")) if old[layer] is not None else None)
              for layer in CANONICAL_DIRS}

    # elementen
    with_code = any(value_of(e.get("element_code")) for e in ver.get("elements", []))
    old_el = Counter(element_key(e, with_code) for e in ver.get("elements", []))
    new_el = Counter(element_key(e, with_code) for e in new.get("elements", []))
    old_ids = {element_key(e, with_code): e["element_id"] for e in ver.get("elements", [])}
    for k in sorted(set(old_el) | set(new_el), key=str):
        common = min(old_el[k], new_el[k])
        if old_el[k] != new_el[k]:
            cats["A_content_extraction"] += abs(old_el[k] - new_el[k])
            details["A_content_extraction"].append({"kind": "element", "key": list(k), "old": old_el[k], "new": new_el[k]})
        if common:
            cats["C_format_provenance"] += common
    new_ids = defaultdict(list)
    for e in new.get("elements", []):
        new_ids[element_key(e, with_code)].append(e["element_id"])
    for k, oid in old_ids.items():
        if new_el[k] == 1 and old_el[k] == 1 and new_ids[k][0] != oid:
            cats["B_id_difference"] += 1
            details["B_id_difference"].append({"kind": "element", "old_id": oid, "new_id": new_ids[k][0]})

    # acties
    rows = new_rows(new)
    matched_new = set()
    for a in ver.get("maintenance_actions", []):
        cls, d = match_old_action(a, rows)
        if cls == "EXACT_MATCH_CANDIDATE":
            matched_new.update(d["new_action_ids"])
            if d["amount_basis"] == "row_total_over_years":
                cats["G_one_action_per_year_amount"] += 1
                details["G_one_action_per_year_amount"].append({"old_action_id": a["action_id"],
                                                                "new_action_ids": d["new_action_ids"]})
            if a["action_id"] not in d["new_action_ids"]:
                cats["B_id_difference"] += 1
            cats["C_format_provenance"] += 1
            # D: waarden die alleen uit normalisatie/review van de oude laag komen
            if any((a.get(f) or {}).get("normalized_value") for f in ("action", "unit")) or a.get("review_note"):
                cats["D_old_verified_derivations"] += 1
        elif cls == "AMBIGUOUS":
            cats["E_review_ambiguity"] += 1
            details["E_review_ambiguity"].append(dict(d, old_action_id=a["action_id"]))
        else:
            cats["A_content_extraction"] += 1
            details["A_content_extraction"].append(dict(d, kind="old_action_without_exact_new_row",
                                                        old_action_id=a["action_id"]))
    unmatched_new = sorted(x["action_id"] for x in new.get("maintenance_actions", []) if x["action_id"] not in matched_new)
    if unmatched_new:
        cats["A_content_extraction"] += len(unmatched_new)
        details["A_content_extraction"].append({"kind": "new_actions_without_exact_old_action",
                                                "action_ids": unmatched_new})
    review_new = sum(1 for x in new.get("maintenance_actions", []) + new.get("observations", [])
                     if x.get("requires_human_review"))
    unlinked = sum(1 for x in new.get("maintenance_actions", []) if str(x.get("element_id", "")).endswith("UNLINKED"))
    cats["E_review_ambiguity"] += review_new
    for el in ver.get("elements", []):
        if any((el.get(f) or {}).get("normalized_value") for f in ("element_type", "element_code", "material", "unit")):
            cats["D_old_verified_derivations"] += 1

    return {
        "document_id": doc,
        "old_layers_sha256": layers,
        "old_extracted_equals_normalized_input": layers["extracted"] is not None,
        "counts": {
            "old_verified": {k: len(ver.get(k, [])) for k in ("elements", "observations", "maintenance_actions")},
            "new": {k: len(new.get(k, [])) for k in ("elements", "observations", "maintenance_actions")},
            "new_source_rows": len(rows),
            "new_requires_human_review": review_new,
            "new_unlinked_actions": unlinked,
        },
        "categories": dict(sorted(cats.items())),
        "details": {k: v for k, v in sorted(details.items())},
    }


# ------------------------------------------------------------------ oude accepts

def classify_accepts(root, new_records):
    out, counts = [], Counter()
    for path in sorted(glob.glob(os.path.join(root, "data", "verified", "DOC-*.json"))):
        ver = load_json(path)
        doc = ver.get("document_id") or os.path.splitext(os.path.basename(path))[0]
        rows = new_rows(new_records[doc]) if doc in new_records else None
        for a in ver.get("maintenance_actions", []):
            note = a.get("review_note") or ""
            if "accept door" not in note:
                continue
            if doc in EXPECTED_DUPLICATES:
                cls, d = "NO_MATCH", {"reason": "DUPLICATE_SKIP", "duplicate_of": EXPECTED_DUPLICATES[doc]["duplicate_of"]}
            elif rows is None:
                cls, d = "NO_MATCH", {"reason": "document_not_in_batch"}
            else:
                cls, d = match_old_action(a, rows)
            counts[cls] += 1
            out.append(dict(d, document_id=doc, old_action_id=a["action_id"], classification=cls))
    return {"counts": dict(sorted(counts.items())), "total": sum(counts.values()), "accepts": out}


# ------------------------------------------------------------------ human decisions (read-only)

def source_key(text):
    return re.sub(r"\s+", "", str(text or "").replace("€", ""))


def analyse_human_decisions(root, new_records):
    store = load_json(os.path.join(root, "data", "review_decisions", "human_decision_records.json"))
    norm = load_json(os.path.join(root, "data", "price_observations", "price_observations_batch1_normalized.json"))
    comp = load_json(os.path.join(root, "data", "comparability", "comparability_batch1.json"))
    obs_ids = {o["observation_id"] for o in norm["observations"]}
    source = {}
    for o in load_json(os.path.join(root, "data", "price_observations", "price_observations_batch1.json"))["observations"]:
        prim = next((r for r in o["source_representations"] if r["role"] == "primary_financial_row"), None)
        source[o["observation_id"]] = prim
    pair_by_id = {p["pair_id"]: frozenset(p["observation_ids"]) for p in comp.get("pairs", [])}
    # nieuwe bronrijen per document: sleutel = pagina + eerste regel van de provenance-tekst (euro/witruimte weg)
    new_by_key = defaultdict(list)
    for doc, rec in new_records.items():
        for row in new_rows(rec):
            first = (row["text_fragment"] or "").split("\n")[0]
            new_by_key[(doc, row["page"], source_key(first))].append(row["action_ids"])
    recs, counts = [], Counter()
    for r in store["records"]:
        ids = r["observation_ids"]
        present = all(i in obs_ids for i in ids)
        pair_same = pair_by_id.get(r["pair_id"]) == frozenset(ids)
        mapping = {}
        for i in ids:
            s = source.get(i)
            hits = new_by_key.get((s["document_id"], s["page"], source_key(s["source_text"])), []) if s else []
            if s is None:
                mapping[i] = {"status": "observation_not_found"}
            elif len(hits) == 1:
                mapping[i] = {"status": "unique_new_source_row", "new_action_ids": sorted(hits[0])}
                counts["observations_unique_new_source_row"] += 1
            elif hits:
                mapping[i] = {"status": "ambiguous_new_source_rows", "candidates": len(hits)}
                counts["observations_ambiguous_new_source_rows"] += 1
            else:
                mapping[i] = {"status": "no_exact_new_source_row"}
                counts["observations_no_exact_new_source_row"] += 1
        counts["records"] += 1
        counts[f"status_{r['status']}"] += 1
        counts["observation_ids_present"] += present
        counts["pair_id_still_same_observations"] += pair_same
        recs.append({"decision_id": r["decision_id"], "pair_id": r["pair_id"], "status": r["status"],
                     "observation_ids": ids, "observation_ids_present": present,
                     "pair_id_currently_same_observations": pair_same, "new_layer_source_rows": mapping})
    return {
        "store_sha256": sha256_file(os.path.join(root, "data", "review_decisions", "human_decision_records.json")),
        "counts": dict(sorted(counts.items())),
        "findings": [
            "observation_id (PO-DOC-<doc>-P<pagina>-L<xpdf-regel>) is positioneel afgeleid uit de xpdf -table-bronlaag "
            "en onafhankelijk van de extractieroute: dit is de stabiele identiteit voor herkoppeling.",
            "pair_id is een volgnummer (PAIR-nnnnn) in iteratievolgorde van build_comparability; bij een andere set "
            "paren schuift het - nooit als identiteit gebruiken, altijd frozenset(observation_ids).",
            "block_id's van de nieuwe laag (P<pagina>-L<tekstlaagregel>, pdfplumber) gebruiken een ANDERE "
            "regelnummering dan observation_id (xpdf-regel); koppelen kan alleen via pagina + brontekst, niet via "
            "regelnummer.",
            "Deze analyse voegt niets toe, wijzigt niets en supersedet niets.",
        ],
        "records": recs,
    }


# ------------------------------------------------------------------ dry-run

def dry_run(root, check):
    new_records = {}
    for doc in EXPECTED_PASS:
        new_records[doc] = load_json(os.path.join(root, BATCH_DIR, f"{doc}.json"))
    documents = [compare_document(root, doc, new_records[doc]) for doc in EXPECTED_PASS]
    dup = []
    for doc, exp in sorted(EXPECTED_DUPLICATES.items()):
        old = {layer: load_canonical(root, layer, doc) for layer in CANONICAL_DIRS}
        dup.append({"document_id": doc, "category": "F_duplicate_skip", "duplicate_of": exp["duplicate_of"],
                    "relation": exp["relation"],
                    "old_layers_present": {k: v is not None for k, v in sorted(old.items())},
                    "old_verified_counts": {k: len((old["verified"] or {}).get(k, []))
                                            for k in ("elements", "observations", "maintenance_actions")},
                    "note": "Niet promoten en niet opnieuw genereren; de oude bestanden zijn kopieën van DOC-002 "
                            "(bron van de dubbeltelling in de legacy kentallen)."})
    totals = Counter()
    for d in documents:
        totals.update(d["categories"])
    totals["F_duplicate_skip"] = len(dup)
    return {
        "report": "deterministic_promotion_dry_run",
        "tool_version": TOOL_VERSION,
        "batch_id": BATCH_ID,
        "principles": ["verified-data is geen gouden standaard", "geen fuzzy matching", "niets gepromoot of gemigreerd",
                       "human decisions alleen gelezen"],
        "category_legend": {
            "A_content_extraction": "inhoudelijk verschil: element/actie zonder exact tegenhanger (oud of nieuw)",
            "B_id_difference": "zelfde inhoud, ander element_id/action_id",
            "C_format_provenance": "exact gekoppeld; alleen notatie (332,00 vs 332.00, '€ 23.667' vs '23667') en "
                                   "provenance (block_id, extraction_rule) verschillen",
            "D_old_verified_derivations": "normalized_value's/review-notities die alleen uit de oude "
                                          "normalisatie-/reviewlaag komen (nieuwe laag: null)",
            "E_review_ambiguity": "meerdere identieke bronrijen of requires_human_review in de nieuwe laag",
            "F_duplicate_skip": "DOC-003: niet gepromoot",
            "G_one_action_per_year_amount": "oude actie met rijtotaal = som van meerdere nieuwe jaaracties",
        },
        "handoff_valid": check["ok"],
        "check": {"ok": check["ok"], "errors": check["errors"], "warnings": check["warnings"],
                  "documents": check["documents"], "manifest": check["manifest"]},
        "totals": dict(sorted(totals.items())),
        "documents": documents,
        "duplicate_skip": dup,
        "old_accepts": classify_accepts(root, new_records),
        "human_decisions": analyse_human_decisions(root, new_records),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--analyse-despite-invalid-handoff", action="store_true",
                    help="alleen --dry-run: analyse toch uitvoeren; het rapport markeert handoff_valid: false")
    ap.add_argument("--report", default=DEFAULT_REPORT, help="alleen --dry-run; pad relatief aan --root")
    args = ap.parse_args(argv)

    check = check_handoff(args.root)
    for w in check["warnings"]:
        print(f"WAARSCHUWING: {w}")
    if not check["ok"]:
        for e in check["errors"]:
            print(f"FOUT: {e}")
        print("HANDOFF ONGELDIG")
        if args.check or not args.analyse_despite_invalid_handoff:
            return 1
        print("--analyse-despite-invalid-handoff: analyse wordt uitgevoerd; rapport markeert handoff_valid: false")
    else:
        print(f"HANDOFF GELDIG: {len(EXPECTED_PASS)} PASS + {len(EXPECTED_DUPLICATES)} DUPLICATE_SKIP")
    if args.check:
        return 0

    report_path = os.path.join(args.root, args.report)
    real = os.path.realpath(report_path)
    if real.startswith(os.path.realpath(os.path.join(args.root, "data")) + os.sep):
        print("FOUT: --dry-run schrijft nooit in data/")
        return 2
    report = dry_run(args.root, check)
    write_json(report_path, report)
    acc = report["old_accepts"]["counts"]
    print(f"rapport -> {os.path.relpath(report_path, args.root)}")
    print(f"oude accepts: {report['old_accepts']['total']} -> {acc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
