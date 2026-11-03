"""Dekking van de duplicaatcontrole (fotoronde -> MJOP) en herkomst in de hoekkiezer. Swift: DuplicateCoverage, Linking.sameFrameOverlaps,
PickedQuad (pariteit via de gegenereerde fixtures). Alles synthetisch: rekenregels, geen nauwkeurigheid op echte gevels."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

from photo_walk_core import duplicate_coverage as D
from photo_walk_core import facade as F
from photo_walk_core import facade_parity as P

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "mjop_scan_proposal_v2.schema.json").read_text())
COUNT = json.loads((ROOT / "ios" / "Tests" / "MJOPIntegrationTests" / "Fixtures" / "count_building_v2.json").read_text())


def o(i, frames, checkable=True):
    return {"id": i, "frame_ids": frames, "duplicate_checkable": checkable}


def test_fixtures_are_current():
    c = D.cases()
    overlap = c.pop("same_frame_overlaps")
    assert json.loads(D.OUT.read_text()) == json.loads(json.dumps(c))
    committed = json.loads(D.OUT_OVERLAP.read_text())
    assert committed["items"] == json.loads(json.dumps(overlap["items"])) and committed["expected"] == overlap["expected"]
    assert json.loads(P.OUT.read_text())["picked_quad"] == json.loads(json.dumps(P.picked_quad_cases()))


def test_zero_suggestions_without_geometry_is_not_a_pass():
    r = D.evaluate([o("A", ["F0"], False), o("B", ["F1"], False)], [{"w1"}], {"F0": "w1", "F1": "w1"}, 0, False)
    assert r["complete"] is False and r["check_incomplete"] and r["unchecked_objects"] == 2


def test_facades_with_their_own_world_block_the_building_not_each_facade():
    objs = [o("A", ["F0"]), o("B", ["F1"])]
    fw = {"F0": "w1", "F1": "w2"}
    assert D.evaluate(objs, [{"w1"}, {"w2"}], fw, 0, False)["cross_session_unchecked"] is True        # gebouw
    assert D.evaluate([objs[0]], [{"w1"}], fw, 0, False)["complete"] is True                          # gevel Voor
    assert D.evaluate([objs[1]], [{"w2"}], fw, 0, False)["complete"] is True                          # gevel Achter


def test_missing_world_ids():
    r = D.evaluate([o("A", ["F0"]), o("B", ["F1"])], [{"w1"}], {"F0": "w1"}, 0, False)
    assert r["complete"] is False and r["unknown_world_photos"] == 1
    assert D.evaluate([o("A", ["F0"]), o("B", ["F0"])], [set()], {}, 0, False)["complete"] is True, "zelfde foto: daarvoor de overlapregel"


def test_manual_review_covers_gaps_but_not_open_suggestions():
    objs = [o("A", ["F0"], False), o("B", ["F1"])]
    r = D.evaluate(objs, [{"w1"}, {"w2"}], {"F0": "w1"}, 0, True)
    assert r["complete"] and r["manual"] and r["unchecked_objects"] == 1 and r["unknown_world_photos"] == 1
    assert D.evaluate(objs, [{"w1"}, {"w2"}], {"F0": "w1"}, 1, True)["complete"] is False


def test_fingerprint_is_order_independent_and_change_sensitive():
    assert D.fingerprint(["a", "b"]) == D.fingerprint(["b", "a"]) != D.fingerprint(["a", "c"])


def test_same_frame_overlaps():
    q = [(0, 0), (10, 0), (10, 10), (0, 10)]
    inner = [(2, 2), (8, 2), (8, 8), (2, 8)]
    other = [(20, 0), (30, 0), (30, 10), (20, 10)]
    assert D.same_frame_overlaps([("a", "F0", q), ("b", "F0", inner), ("c", "F0", other), ("d", "F1", q)]) == [("a", "b")]


# ---- schema: onvolledige dekking blokkeert elke hoeveelheid; velden optioneel (oude voorstellen blijven geldig)

def errors(d):
    return list(jsonschema.Draft7Validator(SCHEMA).iter_errors(d))


def test_schema_incomplete_coverage_blocks_quantities():
    d = copy.deepcopy(COUNT)
    assert errors(d) == [] and "duplicate_review_complete" not in d["basis"], "oude voorstellen zonder de nieuwe velden blijven geldig"
    d["basis"].update(duplicate_review_complete=False, duplicate_review_manual=False, duplicate_check_unchecked_objects=2, duplicate_check_unknown_world_photos=0)
    assert errors(d), "waarde bij onvolledige duplicaatcontrole"
    d["value"], d["partial_value"], d["reliability"]["level"] = None, None, "INCOMPLETE"
    d["reliability"]["reasons"].append("DUPLICATE_CHECK_INCOMPLETE")
    assert errors(d) == []
    ok = copy.deepcopy(COUNT)
    ok["basis"].update(duplicate_review_complete=True, duplicate_review_manual=True, duplicate_check_unchecked_objects=1, duplicate_check_unknown_world_photos=1)
    assert errors(ok) == [], "handmatig nagelopen: waarde toegestaan, herkomst zichtbaar"
    bad = copy.deepcopy(ok)
    bad["basis"]["duplicate_check_unchecked_objects"] = -1
    assert errors(bad)


# ---- hoekkiezer: herkomst (issue D vervolg)

CAND = [(200.0, 150.0), (420.0, 150.0), (420.0, 450.0), (200.0, 450.0)]


def test_picked_unchanged_candidate():
    r = F.classify_picked_quad(CAND, CAND)
    assert (r["source"], r["outer_contour"], r["edited"]) == ("AUTO_DETECTED_CONFIRMED", "USER_CONFIRMED", [])


def test_picked_candidate_with_moved_corner_keeps_origin():
    moved = [CAND[0], (421.0, 150.0), CAND[2], CAND[3]]
    r = F.classify_picked_quad(moved, CAND)
    assert (r["source"], r["outer_contour"], r["edited"]) == ("MANUAL_CORRECTED", "USER_CONFIRMED", [1])
    assert r["original_corners"] == CAND and r["outer_contour"] != "MANUAL"


def test_picked_self_drawn_is_manual_and_legacy_untouched():
    r = F.classify_picked_quad(CAND, None)
    assert (r["source"], r["outer_contour"]) == ("MANUAL", "MANUAL")
    assert F.after_corner_edit("LEGACY") == "LEGACY"
