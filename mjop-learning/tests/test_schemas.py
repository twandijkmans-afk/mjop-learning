"""
Tests voor de schemas zelf: zijn het geldige JSON-schema's, en accepteren ze
het "null i.p.v. gokken"-patroon dat CLAUDE.md voorschrijft?
"""
import glob
import json
import os

import jsonschema
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS_DIR = os.path.join(PROJECT_ROOT, "schemas")


def _schema_files():
    return sorted(glob.glob(os.path.join(SCHEMAS_DIR, "*.schema.json")))


@pytest.mark.parametrize("path", _schema_files())
def test_schema_is_valid_json_schema(path):
    schema = json.load(open(path))
    jsonschema.Draft7Validator.check_schema(schema)


def _resolver():
    """Simpele resolver zodat $ref naar _provenance.schema.json en
    _extracted_value.schema.json binnen dezelfde map wordt gevonden."""
    store = {}
    for path in glob.glob(os.path.join(SCHEMAS_DIR, "*.json")):
        schema = json.load(open(path))
        store[schema.get("$id", os.path.basename(path))] = schema
    return jsonschema.RefResolver.from_schema(
        {"$id": "root", "properties": {}}, store=store
    )


def test_extracted_value_allows_null_value():
    """Een ExtractedValue met value=null moet geldig zijn - ontbrekende data
    mag NOOIT verplicht een waarde hebben (CLAUDE.md: null i.p.v. gokken)."""
    schema = json.load(open(os.path.join(SCHEMAS_DIR, "_extracted_value.schema.json")))
    instance = {"value": None, "requires_human_review": True}
    jsonschema.validate(instance, schema)


def test_extracted_value_requires_review_flag_present():
    schema = json.load(open(os.path.join(SCHEMAS_DIR, "_extracted_value.schema.json")))
    instance = {"value": "iets"}  # requires_human_review ontbreekt
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_maintenance_action_minimal_record_valid():
    schema = json.load(open(os.path.join(SCHEMAS_DIR, "maintenance_action.schema.json")))
    instance = {"action_id": "ACT-001", "element_id": "EL-001"}
    jsonschema.validate(instance, schema)


def test_document_requires_sha256_for_provenance():
    """Een document-record zonder sha256 mag niet geldig zijn: zonder
    checksum kan de immutability van data/raw/ niet worden gecontroleerd."""
    schema = json.load(open(os.path.join(SCHEMAS_DIR, "document.schema.json")))
    instance = {
        "document_id": "DOC-001",
        "filename": "test.pdf",
        "relative_path": "test.pdf",
        "file_type": "pdf",
        "file_size_bytes": 123,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)
