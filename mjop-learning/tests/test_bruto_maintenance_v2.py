"""Maintenance Actions & Door Treatment v1: onderhoudshoeveelheidsvoorstellen uit een triage-reviewpack.

Uitsluitend synthetische fixtures. Geen prijzen, kengetallen, besluiten, foto-inhoud of netwerk.
"""
import copy
import json
import random
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

import bruto_maintenance_actions as ma  # noqa: E402
import bruto_quantity_core as core  # noqa: E402
import test_bruto_triage_v2 as T  # noqa: E402


def req(aid, atype, ids, tr="UNDECIDED", basis=None, ref=None):
    return {"action_id": f"MQ-{aid}", "action_type": atype, "object_ids": [f"BQO-{i}" for i in ids], "door_treatment": tr, "measurement_basis": basis, "basis_source_ref": ref}


def doc(*rs):
    return {"contract_version": "bruto_maintenance_request_v2", "requests": list(rs)}


def window_types():
    return [T.ftype(), T.ftype("BQT-W", refs=[{"reference_id": "R1", "dimension": T.dim("1.20", "2.40")}], cat="FRAME_WITH_DOOR"),
            T.ftype("BQT-D", refs=[{"reference_id": "R1", "dimension": T.dim("0.90", "2.10")}], cat="DOOR")]


def pack(objects, observations, *, calibrated=True, **kw):
    kw.setdefault("types", window_types())
    return T.run(T.inp(objects, observations, **kw), calibrated=calibrated)


def base_pack(calibrated=True):
    objs = [T.bobj("1", ["OBS-1"], cat="FRAME_WITH_DOOR", tid="BQT-W", d=T.dim("1.20", "2.40")), T.bobj("2", ["OBS-2"]),
            T.bobj("3", ["OBS-3"], cat="DOOR", tid="BQT-D", d=T.dim("0.90", "2.10"), q=2)]
    return pack(objs, [T.obs(1, cat="FRAME_WITH_DOOR"), T.obs(2), T.obs(3, cat="DOOR")], calibrated=calibrated)


def P(res, aid):
    return next(p for p in res["proposals"] if p["action_id"] == f"MQ-{aid}")


def rule_ids(res, aid=None):
    return {f["rule_id"] for f in res["findings"] if aid is None or f"MQ-{aid}" in f["action_ids"]}


# --- kozijn, glas, draaiende delen, deur --------------------------------------------------------

def test_frame_with_several_windows_stays_one_object_counted_once():
    objs = [T.bobj("1", ["OBS-1", "OBS-2", "OBS-3"])]
    ev = [T.ev(1, 1, 2), T.ev(2, 2, 3)]
    pk = pack(objs, [T.obs(1, "P1"), T.obs(2, "P2"), T.obs(3, "P3")], evidence=ev)
    assert len(pk["objects"]) == 1
    res = ma.propose(pk, doc(req("1", "EXTERIOR_PAINTING", [1], "NOT_RELEVANT")))
    assert P(res, "1")["proposed_quantity"]["value_exact"] == "1.8"  # niet 3 x 1.8


def test_glass_not_deducted_and_moving_parts_not_added():
    st = base_pack()["baseline_state"]
    assert st["method"]["includes_glass"] is True and st["method"]["glass_area_deducted"] is False and st["method"]["movable_parts_added_separately"] is False
    res = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    q = P(res, "1")["proposed_quantity"]
    assert q == {"value_exact": "1.8", "value_presented": "1.80", "unit": "m2"}  # 1.20 x 1.50 x 1, geen aftrek, geen extra delen
    assert "glas niet afgetrokken" in P(res, "1")["quantity_provenance"]["derivation"]


def test_gross_area_of_frame_with_door_part_of_gross_area_example_a():
    res = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [1], "PART_OF_GROSS_FRAME_AREA")))
    p = P(res, "1")
    assert p["proposed_quantity"] == {"value_exact": "2.88", "value_presented": "2.88", "unit": "m2"} and p["scope"]["door_area_included"] is True
    assert p["measurement_basis"] == "GROSS_FRAME_AREA_OUTER" and p["quantity_unit"] == "m2" and p["vocabulary_action_id"] == "PAINT_EXTERIOR"
    assert len(res["proposals"]) == 1  # geen extra schilderpost voor de deur
    assert p["source_quantity_status"] == "KNOWN_SUPPORTED" and p["review_status"] == "CLEAN_PROVISIONAL" and p["release_state"] == "NOT_RELEASED"


def test_door_registration_in_pieces_and_replacement_example_b():
    res = ma.propose(base_pack(), doc(req("1", "DOOR_REPLACEMENT", [1], "AS_PIECES"), req("2", "DOOR_MAINTENANCE", [3], "AS_PIECES")))
    assert P(res, "1")["proposed_quantity"] == {"value_exact": "1", "value_presented": "1", "unit": "stuks"} and P(res, "1")["measurement_basis"] == "DOOR_PIECES"
    assert P(res, "2")["proposed_quantity"]["value_exact"] == "2" and P(res, "2")["quantity_unit"] == "stuks"


def test_door_in_gross_m2_without_separate_painting_line_and_door_piece_does_not_double():
    res = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [1, 3], "PART_OF_GROSS_FRAME_AREA")))
    p = P(res, "1")
    assert p["proposed_quantity"]["value_exact"] == "6.66"  # 2.88 + 0.90 x 2.10 x 2 = 3.78
    assert len(res["proposals"]) == 1 and p["scope"]["door_pieces_registered"] is None
    only_frame = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [1, 3], "AS_PIECES")))
    assert P(only_frame, "1")["proposed_quantity"]["value_exact"] == "2.88"  # losse deuren niet in m2 bij AS_PIECES
    assert "M-R4" in rule_ids(only_frame, "1")  # deur zit in kozijn-m2 maar wordt in stuks gevraagd


def test_door_replacement_next_to_painting_is_valid_dual_registration_not_double():
    res = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [1], "PART_OF_GROSS_FRAME_AREA"), req("2", "DOOR_REPLACEMENT", [1], "AS_PIECES")))
    assert "M-N2" in rule_ids(res) and not ({"M-C1", "M-R1", "M-R2"} & rule_ids(res))
    assert P(res, "1")["proposed_quantity"] is not None and P(res, "2")["proposed_quantity"] is not None
    assert P(res, "1")["overlap_group"] == P(res, "2")["overlap_group"] and P(res, "1")["additive"] is False and res["invariants"]["combined_total_across_actions"] is None


def test_undecided_and_mismatching_door_treatment_blocks_door_quantity():
    res = ma.propose(base_pack(), doc(req("1", "DOOR_REPLACEMENT", [1], "UNDECIDED"), req("2", "DOOR_MAINTENANCE", [3], "PART_OF_GROSS_FRAME_AREA"), req("3", "EXTERIOR_PAINTING", [1], "UNDECIDED")))
    for a in ("1", "2"):
        assert P(res, a)["proposed_quantity"] is None and "M-R3" in rule_ids(res, a) and P(res, a)["review_status"] == "REVIEW_REQUIRED"
    assert P(res, "1")["scope"]["door_pieces_registered"] == 1  # alleen geregistreerd, geen onderhoudshoeveelheid
    assert "M-R3" in rule_ids(res, "3") and P(res, "3")["review_status"] == "REVIEW_REQUIRED"
    nr = ma.propose(base_pack(), doc(req("1", "DOOR_MAINTENANCE", [1], "NOT_RELEVANT")))
    assert P(nr, "1")["proposed_quantity"] is None


# --- dubbeltelling -------------------------------------------------------------------------------

def test_overlapping_maintenance_actions():
    dup = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [1, 2], "PART_OF_GROSS_FRAME_AREA"), req("2", "EXTERIOR_PAINTING", [2, 1], "PART_OF_GROSS_FRAME_AREA")))
    assert "M-C1" in rule_ids(dup)
    for a in ("1", "2"):
        assert P(dup, a)["review_status"] == "CONFLICT" and P(dup, a)["proposed_quantity"] is None and P(dup, a)["source_quantity_status"] == "BLOCKED_BY_CONFLICT"
    part = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [1, 2], "NOT_RELEVANT"), req("2", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    assert "M-R1" in rule_ids(part) and P(part, "1")["review_status"] == "REVIEW_REQUIRED"
    repl = ma.propose(base_pack(), doc(req("1", "FRAME_REPLACEMENT", [1], "PART_OF_GROSS_FRAME_AREA", "GROSS_FRAME_AREA_OUTER", "SYN-BASIS"), req("2", "DOOR_REPLACEMENT", [1], "AS_PIECES"),
                                       req("3", "EXTERIOR_PAINTING", [1], "NOT_RELEVANT")))
    assert {"M-R2"} <= rule_ids(repl) and P(repl, "2")["review_status"] == "REVIEW_REQUIRED"


def test_two_valid_actions_on_same_object():
    res = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT"), req("2", "INTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    assert rule_ids(res) >= {"M-N2"} and not ({"M-C1", "M-R1", "M-R2"} & rule_ids(res))
    assert P(res, "1")["proposed_quantity"]["value_exact"] == "1.8" and P(res, "2")["proposed_quantity"] is None
    assert P(res, "1")["review_status"] == "CLEAN_PROVISIONAL"


def test_possible_duplicate_object_in_scope_is_flagged():
    objs = [T.bobj("1", ["OBS-1"]), T.bobj("2", ["OBS-2"])]
    pk = pack(objs, [T.obs(1, "P1"), T.obs(2, "P2")], evidence=[T.ev(1, 1, 2, "FEATURE_MATCH")])
    res = ma.propose(pk, doc(req("1", "EXTERIOR_PAINTING", [1, 2], "NOT_RELEVANT")))
    assert "M-R5" in rule_ids(res) and P(res, "1")["review_status"] == "REVIEW_REQUIRED" and P(res, "1")["proposed_quantity"]["value_exact"] == "3.6"
    assert P(res, "1")["source_quantity_status"] == "PROVISIONAL_CALCULATED"


def test_type_group_deviation_uses_own_dimension():
    objs = [T.bobj("1", ["OBS-1"]), T.bobj("2", ["OBS-2"], d=T.dim("1.30", "1.50"))]
    pk = pack(objs, [T.obs(1), T.obs(2)])
    res = ma.propose(pk, doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    assert P(res, "1")["proposed_quantity"]["value_exact"] == "1.95" and "M-N3" in rule_ids(res)
    assert P(res, "1")["review_status"] == "REVIEW_REQUIRED"


# --- binnen, geschat, onbekend, conflict -------------------------------------------------------

def test_interior_painting_without_established_basis_stays_unknown():
    res = ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT"), req("2", "INTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    i = P(res, "2")
    assert i["proposed_quantity"] is None and i["source_quantity_status"] == "UNKNOWN" and i["measurement_basis"] == "UNKNOWN" and i["quantity_unit"] is None
    assert i["review_status"] == "INSUFFICIENT_EVIDENCE" and "M-I1" in rule_ids(res, "2") and i["vocabulary_action_id"] == "PAINT_INTERIOR"
    for basis in ("GROSS_FRAME_AREA_OUTER", "DOOR_PIECES"):
        with pytest.raises(core.BrutoError) as ex:
            ma.propose(base_pack(), doc(req("3", "INTERIOR_PAINTING", [2], "NOT_RELEVANT", basis, "SYN")))
        assert ex.value.code == "INTERIOR_FROM_EXTERIOR_FORBIDDEN"
    hist = ma.propose(base_pack(), doc(req("3", "INTERIOR_PAINTING", [2], "NOT_RELEVANT", "HISTORICAL_SOURCE_BASIS", "SYN-HIST")))
    assert P(hist, "3")["proposed_quantity"] is None and P(hist, "3")["measurement_basis_status"] == "REQUESTED"


def test_frame_maintenance_and_replacement_need_an_established_basis():
    res = ma.propose(base_pack(), doc(req("1", "FRAME_MAINTENANCE", [2], "NOT_RELEVANT"), req("2", "FRAME_REPLACEMENT", [2], "NOT_RELEVANT")))
    assert P(res, "1")["proposed_quantity"] is None and P(res, "2")["proposed_quantity"] is None and "M-R2" in rule_ids(res)
    explicit = ma.propose(base_pack(), doc(req("3", "FRAME_REPLACEMENT", [2], "NOT_RELEVANT", "GROSS_FRAME_AREA_OUTER", "SYN-BASIS")))
    assert P(explicit, "3")["proposed_quantity"]["value_exact"] == "1.8" and P(explicit, "3")["measurement_basis_status"] == "REQUESTED"
    with pytest.raises(core.BrutoError):
        ma.propose(base_pack(), doc(req("4", "DOOR_MAINTENANCE", [1], "AS_PIECES", "GROSS_FRAME_AREA_OUTER", "SYN")))


def test_estimated_gross_area_stays_estimated():
    ref_type, d = T._estimate()
    pk = pack([T.bobj("1", ["OBS-1"], d=d)], [T.obs(1)], types=[T.ftype(), ref_type])
    res = ma.propose(pk, doc(req("1", "EXTERIOR_PAINTING", [1], "NOT_RELEVANT")))
    p = P(res, "1")
    assert p["source_quantity_status"] == "ESTIMATED" and "M-N1" in rule_ids(res) and p["quantity_provenance"]["area_classes"] == ["ESTIMATED"]
    assert p["source_quantity_status"] != "KNOWN_SUPPORTED" and p["is_final_quantity"] is False


def test_unknown_gross_area_is_null_not_zero_and_not_partial():
    objs = [T.bobj("1", ["OBS-1"]), T.bobj("2", ["OBS-2"], d=T.dim(status="UNKNOWN"))]
    pk = pack(objs, [T.obs(1), T.obs(2)])
    res = ma.propose(pk, doc(req("1", "EXTERIOR_PAINTING", [1, 2], "NOT_RELEVANT"), req("2", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    for a in ("1", "2"):
        assert P(res, a)["proposed_quantity"] is None and P(res, a)["source_quantity_status"] == "UNKNOWN" and "M-I2" in rule_ids(res, a)
    pieces = ma.propose(T.run(T.inp([T.bobj("1", ["OBS-1"], cat="DOOR", tid="BQT-D", d=T.dim(status="UNKNOWN"))], [T.obs(1, cat="DOOR")], types=window_types()), calibrated=True),
                        doc(req("9", "DOOR_MAINTENANCE", [1], "AS_PIECES")))
    assert P(pieces, "9")["proposed_quantity"]["value_exact"] == "1"  # stuks hangen niet van de maat af


def test_conflicting_source_quantities_are_blocked():
    objs = [T.bobj("1", ["OBS-1"]), T.bobj("2", ["OBS-1"]), T.bobj("3", ["OBS-3"])]
    pk = pack(objs, [T.obs(1), T.obs(3)])
    res = ma.propose(pk, doc(req("1", "EXTERIOR_PAINTING", [1, 3], "NOT_RELEVANT"), req("2", "EXTERIOR_PAINTING", [3], "NOT_RELEVANT")))
    assert P(res, "1")["source_quantity_status"] == "BLOCKED_BY_CONFLICT" and P(res, "1")["proposed_quantity"] is None and "M-C2" in rule_ids(res, "1")
    assert P(res, "1")["review_status"] == "CONFLICT" and P(res, "2")["proposed_quantity"]["value_exact"] == "1.8"
    dev = [{"object_id": "BQO-1", "sources": [{"source_ref": "SYN-T", "outer_width_m": "1.50", "outer_height_m": "1.50", "uncertainty_m": "0.01"}]}]
    pk2 = pack([T.bobj("1", ["OBS-1"])], [T.obs(1)], dev=dev)
    assert ma.propose(pk2, doc(req("1", "EXTERIOR_PAINTING", [1], "NOT_RELEVANT")))["proposals"][0]["source_quantity_status"] == "BLOCKED_BY_CONFLICT"


def test_uncalibrated_triage_never_gives_clean_or_known_supported():
    res = ma.propose(base_pack(calibrated=False), doc(req("1", "EXTERIOR_PAINTING", [1], "PART_OF_GROSS_FRAME_AREA"), req("2", "DOOR_REPLACEMENT", [1], "AS_PIECES")))
    for p in res["proposals"]:
        assert p["review_status"] == "REVIEW_REQUIRED" and p["source_quantity_status"] == "PROVISIONAL_CALCULATED" and p["quantity_provenance"]["triage_calibration_status"] == "UNCALIBRATED"
    assert "M-R6" in rule_ids(res) and res["source"]["calibration_effective_status"] == "UNCALIBRATED"


# --- afbakening ----------------------------------------------------------------------------------

def full():
    return ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [1, 2], "PART_OF_GROSS_FRAME_AREA"), req("2", "DOOR_REPLACEMENT", [1], "AS_PIECES"), req("3", "INTERIOR_PAINTING", [1], "UNDECIDED")))


def test_no_final_approval_confirmed_or_decision():
    res = full()
    inv = res["invariants"]
    assert inv["release_state"] == "NOT_RELEASED" and inv["usable_for_mjop"] is False and inv["decisions_registered"] is False and inv["approvals_simulated"] is False
    assert inv["confirmed_output"] is False and inv["final_quantities"] is False and inv["combined_total_across_actions"] is None
    for p in res["proposals"]:
        assert p["release_state"] == "NOT_RELEASED" and p["is_final_quantity"] is False and p["usable_for_mjop"] is False
    assert "CONFIRMED" not in json.dumps(res)
    bad = copy.deepcopy(res)
    bad["invariants"]["final_quantities"] = True
    assert ma.schema_errors(bad, "bruto_maintenance_pack_v2")
    bad = copy.deepcopy(res)
    bad["proposals"][0]["is_final_quantity"] = True
    assert ma.schema_errors(bad, "bruto_maintenance_pack_v2")


def test_no_kengetal_link_no_price_no_cost_no_fi_id():
    res = full()
    text = json.dumps(res)
    assert all(p["price_link"] is None and p["kengetal_link"] is None for p in res["proposals"])
    keys = set(re.findall(r'"([a-z_0-9]+)":', text))
    assert not {k for k in keys if re.search(r"price|cost|prijs|kosten|euro|eur_|bedrag|kengetal_ref|unit_cost", k) and k not in ("price_link", "kengetal_link", "price_calculated", "cost_calculated", "kengetal_linked")}
    inv = res["invariants"]
    assert inv["price_calculated"] is False and inv["cost_calculated"] is False and inv["kengetal_linked"] is False and inv["fi_ids_created"] is False
    assert '"FI-' not in text and "FI-" not in "".join(p["action_id"] for p in res["proposals"])
    src = (ROOT / "scripts" / "bruto_maintenance_actions.py").read_text(encoding="utf-8")
    imports = re.findall(r"^(?:import|from) (\S+)", src, re.M)
    assert not [m for m in imports if re.search(r"price|kengetal|kosten|cost|mjop", m)]
    assert all(a["historical_kengetal_ref"] is None and a["price_unit"] is None for a in ma.ACTIONS_VOCAB["actions"])


def test_vocabulary_is_reused_not_duplicated():
    assert set(ma.VOCAB["action_types"]) == {"EXTERIOR_PAINTING", "INTERIOR_PAINTING", "FRAME_MAINTENANCE", "FRAME_REPLACEMENT", "DOOR_MAINTENANCE", "DOOR_REPLACEMENT"}
    assert all(v["vocabulary_action_id"] in ma.VOC_ACTION for v in ma.VOCAB["action_types"].values())
    treatments = [t["treatment"] for t in ma.ACTIONS_VOCAB["door_treatments"]]
    assert set(treatments) == set(core.DOOR_TREATMENTS) == {"PART_OF_GROSS_FRAME_AREA", "AS_PIECES", "NOT_RELEVANT", "UNDECIDED"}
    assert ma.VOCAB["reuses"] == "bruto_quantity_actions_v2" and "door_treatments" not in ma.VOCAB and "measurement_bases" not in ma.VOCAB
    req_schema = ma.bq.load_schema("bruto_maintenance_request_v2")
    assert set(req_schema["properties"]["requests"]["items"]["properties"]["door_treatment"]["enum"]) == set(treatments)
    src = (ROOT / "scripts" / "bruto_maintenance_actions.py").read_text(encoding="utf-8")
    used = set(re.findall(r'_finding\("(M-[A-Z]\d)"', src))
    assert used == set(ma.RULES)


def test_contract_has_required_fields_and_is_closed():
    p = full()["proposals"][0]
    for k in ("action_id", "action_type", "element_category", "quantity_unit", "measurement_basis", "door_treatment", "scope", "source_quantity_ref",
              "source_quantity_status", "proposed_quantity", "quantity_provenance", "review_status", "contract_version"):
        assert k in p
    assert p["contract_version"] == "bruto_maintenance_action_v2"
    bad = copy.deepcopy(full())
    bad["proposals"][0]["extra"] = 1
    assert ma.schema_errors(bad, "bruto_maintenance_pack_v2")
    assert ma.schema_errors({"contract_version": "bruto_maintenance_request_v2", "requests": [{"action_id": "x"}]}, "bruto_maintenance_request_v2")


def test_invalid_requests_and_tampered_source_are_rejected():
    with pytest.raises(core.BrutoError) as ex:
        ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [99], "NOT_RELEVANT")))
    assert ex.value.code == "SCOPE_OBJECT_UNKNOWN"
    with pytest.raises(core.BrutoError) as ex2:
        ma.propose(base_pack(), doc(req("1", "DOOR_MAINTENANCE", [2], "AS_PIECES")))
    assert ex2.value.code == "SCOPE_CATEGORY_MISMATCH"
    with pytest.raises(core.BrutoError) as ex3:
        ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT"), req("1", "INTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    assert ex3.value.code == "DUPLICATE_ACTION_ID"
    tampered = copy.deepcopy(base_pack())
    tampered["objects"][1]["dimension"]["gross_area_m2_exact"] = "99"
    with pytest.raises(core.BrutoError) as ex4:
        ma.propose(tampered, doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT")))
    assert ex4.value.code == "SOURCE_PACK_TAMPERED"
    with pytest.raises(core.BrutoError) as ex5:
        ma.propose(base_pack(), doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT", "HISTORICAL_SOURCE_BASIS", None)))
    assert ex5.value.code == "BASIS_SOURCE_MISSING"


def test_input_pack_is_not_modified():
    pk = base_pack()
    before = json.dumps(pk, sort_keys=True)
    ma.propose(pk, doc(req("1", "EXTERIOR_PAINTING", [1, 2], "PART_OF_GROSS_FRAME_AREA")))
    assert json.dumps(pk, sort_keys=True) == before


def _porcelain():
    return subprocess.run(["git", "status", "--porcelain", "--", "data", "reports", "vocabularies", "config", "schemas"], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def test_no_canonical_changes_no_writes_no_network(tmp_path, monkeypatch):
    before = _porcelain()

    def boom(*a, **k):
        raise AssertionError("netwerkgebruik")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    res = full()
    pf, rf = tmp_path / "pack.json", tmp_path / "req.json"
    pf.write_text(json.dumps(base_pack()), encoding="utf-8")
    rf.write_text(json.dumps(doc(req("1", "EXTERIOR_PAINTING", [2], "NOT_RELEVANT"))), encoding="utf-8")
    assert ma.main([str(pf), str(rf), "--out-dir", str(tmp_path / "out")]) == 0
    assert len(list((tmp_path / "out").iterdir())) == 1
    with pytest.raises(SystemExit):
        ma.main([str(pf), str(rf), "--out-dir", str(ROOT / "reports" / "x")])
    assert _porcelain() == before and not (ROOT / "reports" / "x").exists() and res
    src = (ROOT / "scripts" / "bruto_maintenance_actions.py").read_text(encoding="utf-8")
    banned = {"socket", "urllib", "http", "requests", "httpx", "anthropic", "openai", "subprocess", "shutil"}
    assert not (set(re.findall(r"^(?:import|from) (\w+)", src, re.M)) & banned)
    assert src.count("write_text") == 1  # alleen de CLI, na de repository-controle


def test_deterministic_regardless_of_request_order():
    rs = [req("1", "EXTERIOR_PAINTING", [1, 2], "PART_OF_GROSS_FRAME_AREA"), req("2", "DOOR_REPLACEMENT", [1], "AS_PIECES"), req("3", "INTERIOR_PAINTING", [1], "UNDECIDED")]
    a = ma.propose(base_pack(), doc(*rs))
    rs2 = list(reversed(rs))
    random.Random(3).shuffle(rs2)
    b = ma.propose(base_pack(), doc(*rs2))
    assert ma.pack_json(a) == ma.pack_json(b) and a["pack_id"] == b["pack_id"] and ma.pack_json(full()) == ma.pack_json(full())
