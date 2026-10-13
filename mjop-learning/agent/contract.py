"""Gedeeld toolcontract: fouten, schema-validatie, canonieke hash en vaste projectroot.

De root van de gegevens wordt hier uit de bestandslocatie afgeleid en komt nooit uit modelinvoer.
Alleen lezen: dit module schrijft niets.
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")

# Bestaande scripts worden hergebruikt via dezelfde sys.path-conventie als de rest van de repository.
_SCRIPTS = os.path.join(PROJECT_ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import human_match_review  # noqa: E402  (canonieke hashfunctie, alleen lezen)


class ToolError(Exception):
    """Een tool weigert of faalt expliciet; er wordt nooit een gegokte waarde teruggegeven."""

    def __init__(self, code, message, details=None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.details = code, message, list(details or [])

    def as_dict(self):
        return {"error": self.code, "message": self.message, "details": self.details}


def load_schema(filename):
    with open(os.path.join(SCHEMA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def schema_errors(instance, schema):
    import jsonschema
    validator = jsonschema.Draft7Validator(schema)
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}"
                  for e in validator.iter_errors(instance))


def canonical_sha256(obj):
    return human_match_review.canonical_sha256(obj)
