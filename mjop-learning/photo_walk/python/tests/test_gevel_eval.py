"""Evaluatiescript voor de veldvalidatie van Gevelscanner 2.0. De referentie hier is SYNTHETISCH: deze tests bewijzen dat het script goed
rekent, niets over de nauwkeurigheid op echte gevels."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

from photo_walk_core import gevel_eval

ROOT = Path(__file__).resolve().parents[2]
INV = json.loads((ROOT / "ios" / "Tests" / "GevelscanTests" / "Fixtures" / "gevel_inventory_v1_example.json").read_text())
REF = json.loads((ROOT / "examples" / "ground_truth" / "gevelscan_reference_synthetic.json").read_text())


def test_reports_all_required_measures_without_verdict():
    r = gevel_eval.evaluate(REF, INV)
    assert r["sample"] == {"reference_frames": 3, "matched": 3, "double_counted": 0, "missed": 0, "spurious_objects": 0, "unknown_object_ids_in_reference": 0}
    for k in ("width_m", "height_m", "area_m2", "glass_area_m2", "operable_parts"):
        assert r["errors"][k]["n"] == 3, k
    assert r["rates"] == {"double_counted": 0.0, "missed": 0.0}
    assert [c["error"] for c in r["frame_count_per_facade"]] == [0, 0]
    assert r["verdict"] is None and "SYNTHETISCHE" in r["note"]          # geen oordeel, geen acceptatiegrens
    assert r["reference"]["data_origin"] == "SYNTHETIC"
    # de synthetische scène wordt binnen centimeters teruggevonden (zegt alleen iets over de rekenregels)
    assert r["errors"]["width_m"]["max_abs"] < 0.03 and r["errors"]["operable_parts"]["max_abs"] == 0


def test_double_counted_missed_and_spurious_are_counted():
    ref = copy.deepcopy(REF)
    ids = [o["object_id"] for o in INV["facades"][0]["objects"]]
    ref["facades"][0]["frames"][0]["matched_object_ids"] = ids             # één echt kozijn, twee app-objecten
    ref["facades"][0]["frames"][1]["matched_object_ids"] = []              # gemist
    r = gevel_eval.evaluate(ref, INV)
    assert r["sample"]["double_counted"] == 1 and r["sample"]["missed"] == 1 and r["sample"]["matched"] == 1
    assert r["rates"] == {"double_counted": round(1 / 3, 4), "missed": round(1 / 3, 4)}
    assert r["errors"]["width_m"]["n"] == 1                                # maatfout alleen bij goed gekoppelde kozijnen
    ref["facades"][0]["frames"][0]["matched_object_ids"] = [ids[0]]
    r = gevel_eval.evaluate(ref, INV)
    assert r["spurious_object_ids"] == [ids[1]]                            # app-object dat bij geen enkel echt kozijn hoort


def test_unknown_values_are_skipped_not_treated_as_zero():
    inv = copy.deepcopy(INV)
    o = inv["facades"][1]["objects"][0]
    o["glass_area"].update(value=None, outcome="NIET_VAST_TE_STELLEN", origin="NONE", sigma=None)
    inv["facades"][1]["totals"]["glass_area"].update(value=None, outcome="NIET_VAST_TE_STELLEN", origin="NONE", sigma=None)
    inv["building_totals"]["glass_area"].update(value=None, outcome="NIET_VAST_TE_STELLEN", origin="NONE", sigma=None)
    r = gevel_eval.evaluate(REF, inv)
    assert r["errors"]["glass_area_m2"]["n"] == 2
    ref = copy.deepcopy(REF)
    ref["facades"][0]["frames"][0]["width_m"] = None                       # niet te meten met de rolmaat
    assert gevel_eval.evaluate(ref, INV)["errors"]["width_m"]["n"] == 2


def test_incomplete_facade_gives_no_count_error_and_invalid_input_is_refused():
    ref = copy.deepcopy(REF)
    ref["facades"][0]["frames_complete"] = False
    assert len(gevel_eval.evaluate(ref, INV)["frame_count_per_facade"]) == 1
    bad = copy.deepcopy(INV)
    bad["booking_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        gevel_eval.evaluate(REF, bad)
    with pytest.raises(jsonschema.ValidationError):
        gevel_eval.evaluate({"schema": "x"}, INV)
