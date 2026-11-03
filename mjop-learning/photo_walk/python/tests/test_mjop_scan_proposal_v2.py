"""Contract mjop_scan_proposal_v2 (fotoronde -> MJOP): schema + gedeelde fixtures (dezelfde bestanden staan in de website-repo, test/fixtures/photo-round/)."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "mjop_scan_proposal_v2.schema.json").read_text())
FIX = ROOT / "ios" / "Tests" / "MJOPIntegrationTests" / "Fixtures"
COUNT = json.loads((FIX / "count_building_v2.json").read_text())
AREA = json.loads((FIX / "area_building_incomplete_v2.json").read_text())


def errors(doc):
    return list(jsonschema.Draft7Validator(SCHEMA).iter_errors(doc))


def test_schema_valid_and_fixtures_conform():
    jsonschema.Draft7Validator.check_schema(SCHEMA)
    assert errors(COUNT) == []
    assert errors(AREA) == []


def test_unknown_value_is_null_not_zero():
    assert AREA["value"] is None and AREA["partial_value"] == 17.4
    assert AREA["reliability"]["level"] == "INCOMPLETE"


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(booking_allowed=True),
    lambda d: d.update(contract="mjop_scan_proposal_v1"),
    lambda d: d.update(extra=1),
    lambda d: d["confirmation"].update(status="CONFIRMED_BY_USER"),
    lambda d: d["confirmation"].update(uncertainty_acknowledged=True),
    lambda d: d["target"].update(quantity_kind="WALL_AREA"),
    lambda d: d["target"].update(unit="kg"),
    lambda d: d["target"]["scope"].update(orientation="UP"),
    lambda d: d["project"].update(plan_ref="x"),
    lambda d: d["project"].update(bag_pand_id="123"),
    lambda d: d.update(value=-1),
    lambda d: d["basis"].update(objects_total=-1),
    lambda d: d["measurement"]["methods"].append("GUESS"),
    lambda d: d["reliability"].update(level="OK"),
    lambda d: d["reliability"]["reasons"].append("WHATEVER"),
    lambda d: d.pop("evidence"),
])
def test_invalid_variants_are_rejected(mutate):
    d = copy.deepcopy(COUNT)
    mutate(d)
    assert errors(d)


def test_no_price_or_cost_fields():
    text = json.dumps(SCHEMA).lower()
    for w in ("price", "prijs", "kengetal", "cost", "kosten", "eur"):
        assert w not in text.replace("measurement", "")
