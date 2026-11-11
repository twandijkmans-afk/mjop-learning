"""Contract mjop_gevel_inventory_v1 (Gevelscanner 2.0 -> MJOP): schema + het gedeelde voorbeeld dat de Swift-app zelf produceert
(ios/Tests/GevelscanTests/Fixtures; dezelfde inhoud staat in de website-repo, test/fixtures/gevel-inventory/)."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "mjop_gevel_inventory_v1.schema.json").read_text())
EXAMPLE = json.loads((ROOT / "ios" / "Tests" / "GevelscanTests" / "Fixtures" / "gevel_inventory_v1_example.json").read_text())
V2_SCHEMA = (ROOT / "schemas" / "mjop_scan_proposal_v2.schema.json").read_text()


def errors(doc):
    return list(jsonschema.Draft7Validator(SCHEMA).iter_errors(doc))


def obj0(d):
    return d["facades"][0]["objects"][0]


def test_schema_valid_and_app_output_conforms():
    jsonschema.Draft7Validator.check_schema(SCHEMA)
    assert errors(EXAMPLE) == []


def test_six_quantities_stay_separate_and_unknown_is_null():
    t = EXAMPLE["facades"][0]["totals"]
    assert set(t) == {"frame_count", "frame_area_gross", "operable_parts", "fixed_parts", "glass_area", "door_count"}
    assert t["frame_count"]["unit"] == "st" and t["frame_area_gross"]["unit"] == "m2" and t["glass_area"]["unit"] == "m2"
    assert t["door_count"]["value"] is None and t["door_count"]["outcome"] == "NIET_VAST_TE_STELLEN"   # geen model: onbekend, niet 0
    assert t["glass_area"]["value"] < t["frame_area_gross"]["value"]
    assert t["glass_area"]["origin"] == "DERIVED_SEGMENTATION_ON_MEASURED_PLANE"                       # geen LiDAR-meting


def test_nothing_is_reliable_or_auto_processed_without_validation():
    assert EXAMPLE["validation"] == {"geometry_field_validated": False, "detector_validated": False, "auto_processing_allowed": False,
                                     "reasons": ["GEOMETRIE_NIET_IN_HET_VELD_GEVALIDEERD", "HERKENNING_NIET_GEVALIDEERD"]}
    assert EXAMPLE["booking_allowed"] is False
    for f in EXAMPLE["facades"]:
        assert f["completeness"] != "BETROUWBAAR_VASTGESTELD"
        for o in f["objects"]:
            assert o["outcome"] != "BETROUWBAAR_VASTGESTELD" and o["nen2767_condition_score"] is None
            for k in ("width", "height", "area", "glass_area", "sections"):
                assert o[k]["outcome"] != "BETROUWBAAR_VASTGESTELD"


def test_no_prices_or_kengetallen_anywhere():
    text = json.dumps(EXAMPLE).lower()
    for word in ("prijs", "price", "kengetal", "cost", "kosten", "tarief", "eur", "btw"):
        assert f'"{word}' not in text


def test_evidence_is_traceable():
    photos = {p["photo_id"] for p in EXAMPLE["photos"]}
    for f in EXAMPLE["facades"]:
        for o in f["objects"]:
            assert o["photo_ids"] and set(o["photo_ids"]) <= photos
            assert set(o["measured_sighting_ids"]) <= set(o["sighting_ids"])
            assert o["detectors"] and all(d["version"] for d in o["detectors"])
    assert EXAMPLE["versions"]["thresholds_status"] == "PROVISIONAL_UNVALIDATED"


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(booking_allowed=True),
    lambda d: d.update(contract="mjop_scan_proposal_v2"),
    lambda d: d.update(extra=1),
    lambda d: d["confirmation"].update(status="CONFIRMED_BY_USER"),
    lambda d: d["validation"].update(auto_processing_allowed=True),
    lambda d: d["project"].update(plan_ref="x"),
    lambda d: obj0(d).update(nen2767_condition_score=3),
    lambda d: obj0(d).update(count=3),                                         # drie vakken zijn niet drie kozijnen
    lambda d: obj0(d)["glass_area"].update(origin="LIDAR_PLANE_MEASUREMENT"),  # glas is nooit een directe LiDAR-meting
    lambda d: obj0(d)["width"].update(value=None),                             # onbekend zonder NIET_VAST_TE_STELLEN
    lambda d: obj0(d)["width"].update(value=-1),
    lambda d: obj0(d)["area"].update(unit="st"),
    lambda d: obj0(d)["area"].update(outcome="NIET_VAST_TE_STELLEN"),          # waarde bij "niet vast te stellen"
    lambda d: obj0(d)["area"].update(prijs=100),                               # geen prijsvelden
    lambda d: obj0(d)["panes"][0].update(origin="LIDAR_PLANE_MEASUREMENT"),
    lambda d: obj0(d)["condition"].append({"id": "c", "kind": "ZICHTBAAR_GEBREK", "category": "CORROSIE", "label_nl": "Corrosie", "photo_id": None,
                                           "region_px": None, "score": 0.9, "detector": None, "reasons": []}),   # gebrek zonder bronfoto/plek/gevalideerd model
    lambda d: d["photos"][0].update(depth_source="ESTIMATED_FROM_PHOTO"),
    lambda d: d["facades"][0]["totals"].pop("glass_area"),
])
def test_schema_rejects_violations(mutate):
    d = copy.deepcopy(EXAMPLE)
    mutate(d)
    assert errors(d), "mutatie had geweigerd moeten worden"


def test_existing_v2_contract_is_untouched():
    """De nieuwe inventaris is een apart contract: het v2-schema kent geen inventaris en blijft gesloten."""
    v2 = json.loads(V2_SCHEMA)
    assert v2["$id"] == "mjop_scan_proposal_v2" and v2["additionalProperties"] is False
    assert v2["properties"]["target"]["properties"]["quantity_kind"]["enum"] == ["FRAME_COUNT", "FRAME_AREA_GROSS"]
    assert list(jsonschema.Draft7Validator(v2).iter_errors(EXAMPLE))            # een inventaris is geen v2-voorstel
