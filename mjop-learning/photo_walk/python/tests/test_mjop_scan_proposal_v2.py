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
COUNT_BLOCKED = json.loads((FIX / "count_building_blocked_v2.json").read_text())
AREA_BLOCKED = json.loads((FIX / "area_building_blocked_v2.json").read_text())


def errors(doc):
    return list(jsonschema.Draft7Validator(SCHEMA).iter_errors(doc))


def test_schema_valid_and_fixtures_conform():
    jsonschema.Draft7Validator.check_schema(SCHEMA)
    assert errors(COUNT) == []
    assert errors(AREA) == []
    assert errors(COUNT_BLOCKED) == []
    assert errors(AREA_BLOCKED) == []


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


# ---- mogelijke dubbeltelling (onbeoordeelde duplicaten / niet-gecontroleerde AR-sessies) blokkeert aantal en oppervlak
# Zelfde regel als ScanProposalV2.validate() (.quantityWithUncheckedDuplicates) en RoundProposalBuilder in Swift.

def _blocked(doc):
    return doc["value"] is None and doc["partial_value"] is None and doc["reliability"]["level"] == "INCOMPLETE"


@pytest.mark.parametrize("base", ["count", "area"])
@pytest.mark.parametrize("condition", ["duplicates", "cross_session", "both"])
def test_unchecked_duplicates_forbid_any_quantity(base, condition):
    d = copy.deepcopy(COUNT if base == "count" else AREA)
    assert errors(d) == []
    if condition in ("duplicates", "both"):
        d["basis"]["duplicates_unresolved"] = 1
    if condition in ("cross_session", "both"):
        d["basis"]["cross_session_unchecked"] = True
    assert errors(d), "een (deel)waarde bij een mogelijke dubbeltelling moet ongeldig zijn"
    d["value"], d["partial_value"], d["reliability"]["level"] = None, None, "INCOMPLETE"
    assert errors(d) == [], "zonder waarde en deelwaarde (INCOMPLETE) is hetzelfde voorstel geldig: basis en bewijs blijven"


@pytest.mark.parametrize("doc", [COUNT_BLOCKED, AREA_BLOCKED], ids=["count", "area"])
@pytest.mark.parametrize("mutate", [
    lambda d: d.update(value=12),
    lambda d: d.update(partial_value=17.4),
    lambda d: d["reliability"].update(level="CHECK_REQUIRED"),
])
def test_blocked_fixtures_reject_values(doc, mutate):
    d = copy.deepcopy(doc)
    mutate(d)
    assert errors(d)


def test_blocked_fixtures_keep_reasons_and_evidence():
    for d in (COUNT_BLOCKED, AREA_BLOCKED):
        assert _blocked(d) and "DUPLICATES_UNRESOLVED" in d["reliability"]["reasons"] and d["basis"]["duplicates_unresolved"] > 0
        assert d["evidence"]["object_ids"] and d["evidence"]["photo_ids"] and d["basis"]["objects_total"] > 0
    assert "CROSS_SESSION_UNCHECKED" in COUNT_BLOCKED["reliability"]["reasons"] and COUNT_BLOCKED["basis"]["cross_session_unchecked"] is True


def test_resolved_duplicates_keep_normal_values():
    assert COUNT["basis"]["duplicates_unresolved"] == 0 and COUNT["basis"]["cross_session_unchecked"] is False
    assert COUNT["value"] == 12 and COUNT["reliability"]["level"] == "CHECK_REQUIRED" and errors(COUNT) == []
    assert AREA["partial_value"] == 17.4 and errors(AREA) == []
