#!/usr/bin/env python3
"""
record_validation.py - controles op records in de BESTAANDE architectuur.

Bewust beperkt (zie docs/deterministic_extraction_v1.md, beslissing C1):
geen eigen recordmodel, geen eigen envelop-schema, geen tweede parser.

1. validate_entities: building/elements/observations/maintenance_actions tegen de
   bestaande schemas/ (lokale $ref-resolutie via `referencing`, geen netwerk).
2. verify_block_provenance: alleen voor provenance MET block_id (aanvullende
   tekstlaag-provenance): bestaat het blok, klopt de pagina, en bestaat
   text_fragment letterlijk uit regels van de genoemde blokken. Provenance
   zonder block_id (bestaande records) wordt niet afgekeurd.
3. link_source_row_to_blocks: koppelt een rij van de GEZAGHEBBENDE bronlaag
   (mjop_source_sections: pagina + regel in de pdftotext -table-weergave +
   source_text) aan de tekstlaagregel(s) op dezelfde pagina. Levert alleen
   aanvullende provenance (block-ID's), nooit een tweede waarde. Geen unieke
   match -> None (niet raden).
"""
import glob
import json
import os
import re

import jsonschema
from referencing import Registry, Resource

import text_layer as tl

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS_DIR = os.path.join(PROJECT_ROOT, "schemas")

ENTITY_SCHEMAS = (
    ("elements", "element.schema.json"),
    ("observations", "observation.schema.json"),
    ("maintenance_actions", "maintenance_action.schema.json"),
)


# ---------------------------------------------------------------- schema's

def schema_registry(schemas_dir=SCHEMAS_DIR):
    """Registreert elk schema onder zijn bestandsnaam én zijn $id (die wijken af,
    bijv. _provenance.schema.json heeft $id provenance.schema.json)."""
    resources = []
    for path in sorted(glob.glob(os.path.join(schemas_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            contents = json.load(f)
        res = Resource.from_contents(contents)
        resources.append((os.path.basename(path), res))
        if contents.get("$id") and contents["$id"] != os.path.basename(path):
            resources.append((contents["$id"], res))
    return Registry().with_resources(resources)


def schema_errors(instance, schema_name, registry=None, schemas_dir=SCHEMAS_DIR):
    registry = registry or schema_registry(schemas_dir)
    with open(os.path.join(schemas_dir, schema_name), encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft7Validator(schema, registry=registry)
    return [f"{schema_name}:{'/'.join(map(str, e.absolute_path))}: {e.message}"
            for e in sorted(validator.iter_errors(instance), key=lambda e: list(map(str, e.absolute_path)))]


def validate_entities(record, schemas_dir=SCHEMAS_DIR):
    """Zelfde omvang als extract_batch.validate_record (bestaande schemas), zonder
    de verouderde RefResolver."""
    reg = schema_registry(schemas_dir)
    errors = []
    if record.get("building") is not None:
        errors += schema_errors(record["building"], "building.schema.json", reg, schemas_dir)
    for key, name in ENTITY_SCHEMAS:
        for i, item in enumerate(record.get(key, [])):
            errors += [f"{key}[{i}] {e}" for e in schema_errors(item, name, reg, schemas_dir)]
    return errors


# ---------------------------------------------------------------- block-provenance

def iter_provenance(obj, path=""):
    if isinstance(obj, dict):
        if "document_id" in obj and "source_confidence" in obj:
            yield path, obj
        for k, v in obj.items():
            yield from iter_provenance(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_provenance(v, f"{path}/{i}")


def _line_text(blk, idx):
    return idx[blk["line_id"]]["text"] if blk["kind"] == "word" else blk["text"]


def verify_block_provenance(record, layer):
    """Controleert alleen provenance met block_id; de rest blijft ongemoeid."""
    errors = []
    idx = tl.block_index(layer)
    doc_id = record.get("document_id")
    for path, p in iter_provenance(record):
        bid = p.get("block_id")
        if not bid:
            continue
        if p.get("document_id") != doc_id or layer.get("document_id") != doc_id:
            errors.append(f"{path}: document_id past niet bij record/tekstlaag")
        if bid not in idx:
            errors.append(f"{path}: block_id {bid} bestaat niet in de tekstlaag")
            continue
        blk = idx[bid]
        if blk["page"] is not None and blk["page"] != p.get("page"):
            errors.append(f"{path}: page {p.get('page')} != pagina van blok {blk['page']}")
        if blk["kind"] == "sheet_cell":
            if p.get("cell_ref") not in (None, blk["cell_ref"]) or p.get("sheet") not in (None, blk["sheet"]):
                errors.append(f"{path}: sheet/cell_ref past niet bij blok {bid}")
        allowed = {_line_text(blk, idx) if blk["kind"] in ("word", "line") else blk["text"]}
        for rid in p.get("related_block_ids", []):
            if rid not in idx:
                errors.append(f"{path}: related_block_id {rid} bestaat niet")
                continue
            r = idx[rid]
            allowed.add(_line_text(r, idx) if r["kind"] in ("word", "line") else r["text"])
        frag = p.get("text_fragment")
        if frag is not None:
            for fl in frag.split("\n"):
                if fl not in allowed:
                    errors.append(f"{path}: text_fragment-regel {fl!r} komt niet letterlijk uit de genoemde blokken")
    return errors


def literal_runs(value, fragment):
    """True als de woorden van `value` in volgorde bestaan uit één aaneengesloten
    woordreeks per bronregel (regels gescheiden door \\n) - niets verzonnen,
    overgeslagen binnen een reeks of herschikt."""
    want = value.split()
    lines = [l.split() for l in fragment.split("\n")]

    def match(vi, li):
        if vi == len(want):
            return True
        if li == len(lines):
            return False
        if match(vi, li + 1):
            return True
        toks = lines[li]
        for start in range(len(toks)):
            k = 0
            while vi + k < len(want) and start + k < len(toks) and toks[start + k] == want[vi + k]:
                k += 1
                if match(vi + k, li + 1):
                    return True
        return False

    return match(0, 0)


# ---------------------------------------------------------------- brug naar de gezaghebbende bronlaag

def _source_key(text):
    """Vergelijkingssleutel tussen de pdftotext -table-weergave (mjop_source_sections
    haalt '€' weg en splitst '5,93m2' soms als '5,93 m2') en de tekstlaag:
    zonder '€' en zonder witruimte. Geen andere normalisatie."""
    return re.sub(r"\s+", "", (text or "").replace("€", ""))


def link_source_row_to_blocks(layer, page, source_text):
    """Returns {'block_id', 'text_fragment', 'match'} voor precies één tekstlaagregel
    op `page` met dezelfde sleutel als source_text; anders None ('none' of
    'ambiguous' - nooit raden)."""
    key = _source_key(source_text)
    if not key:
        return None
    pg = next((p for p in layer.get("pages", []) if p["page"] == page), None)
    if pg is None:
        return None
    hits = [l for l in pg["lines"] if _source_key(l["text"]) == key]
    if len(hits) != 1:
        return None
    return {"block_id": hits[0]["id"], "text_fragment": hits[0]["text"], "match": "exact_without_euro_and_whitespace"}
