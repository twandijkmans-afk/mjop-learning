"""Quantity Review & Triage v1: schema-validatie (alleen lezen). Hergebruikt de v2-schema's van het Bruto Quantity Model."""
import sys
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bruto_quantity_contracts as bq  # noqa: E402

TRIAGE_SCHEMAS = ("bruto_triage_input_v2", "bruto_triage_calibration_v2", "bruto_review_pack_v2")
VOCAB_NAME = "bruto_triage_rules_v2"


def _store():
    store = {f"{n}.schema.json": bq.load_schema(n) for n in bq.SCHEMA_NAMES + TRIAGE_SCHEMAS}
    return store


def schema_errors(instance, name):
    schema = bq.load_schema(name)
    resolver = jsonschema.RefResolver(base_uri=f"{name}.schema.json", referrer=schema, store=_store())
    validator = jsonschema.Draft7Validator(schema, resolver=resolver)
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in validator.iter_errors(instance))


def input_errors(inp):
    return schema_errors(inp, "bruto_triage_input_v2")


def calibration_errors(cfg):
    return schema_errors(cfg, "bruto_triage_calibration_v2")


def pack_errors(pack):
    return schema_errors(pack, "bruto_review_pack_v2")


def load_rules():
    return bq.load_vocabulary(VOCAB_NAME)
