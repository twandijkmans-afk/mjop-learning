"""Contract mjop_scan_proposal_v1 (scanner -> MJOP): schema + voorbeeld; hetzelfde voorbeeld wordt door de Swift-tests gedecodeerd."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "mjop_scan_proposal_v1.schema.json").read_text())
EXAMPLE = json.loads((ROOT / "ios" / "Tests" / "MJOPIntegrationTests" / "Fixtures" / "scan_proposal_v1_example.json").read_text())


def errors(doc):
    return list(jsonschema.Draft7Validator(SCHEMA).iter_errors(doc))


def test_schema_is_valid_and_example_conforms():
    jsonschema.Draft7Validator.check_schema(SCHEMA)
    assert errors(EXAMPLE) == []


def test_example_is_a_proposal_not_a_booking():
    assert EXAMPLE["booking_allowed"] is False
    assert EXAMPLE["confirmation"]["status"] == "PROPOSED"
    assert EXAMPLE["measurement"]["uncertainty"]["validated"] is False


def test_booking_allowed_true_is_rejected():
    d = copy.deepcopy(EXAMPLE); d["booking_allowed"] = True
    assert errors(d)


@pytest.mark.parametrize("path,value", [
    (("contract",), "mjop_scan_proposal_v2"),
    (("element", "type"), "WINDOW"),
    (("quantity", "unit"), "km"),
    (("measurement", "method"), "GUESS"),
    (("quantity", "value"), -1),
    (("project", "bag_pand_id"), "123"),
])
def test_invalid_values_are_rejected(path, value):
    d = copy.deepcopy(EXAMPLE)
    t = d
    for k in path[:-1]:
        t = t[k]
    t[path[-1]] = value
    assert errors(d)


def test_unknown_fields_and_missing_fields_are_rejected():
    d = copy.deepcopy(EXAMPLE); d["extra"] = 1
    assert errors(d)
    d = copy.deepcopy(EXAMPLE); del d["evidence"]["source_photo_id"]
    assert errors(d)


def test_schema_has_no_price_or_cost_fields():
    text = json.dumps(SCHEMA).lower()
    for w in ("price", "prijs", "kengetal", "cost", "kosten", "eur"):
        assert w not in text.replace("measurement", "")
