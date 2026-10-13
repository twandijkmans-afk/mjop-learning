"""Determinisme: zelfde invoer + zelfde bronnen => byte-identieke uitvoer; een andere bron => ander call_id."""
import copy
import json

import support  # noqa: F401
from support import FIXTURE_ROOT, PROJECT_ROOT, root_with_store

import human_match_review as h
import match_kengetal as m
from agent import call_tool
from agent.tools.get_kengetal_candidates import get_kengetal_candidates

HP = h.paths(FIXTURE_ROOT)
EMPTY = h.load_json(HP["store"])
KENGETALLEN = h.load_json(HP["kengetallen"])
CTX = m.load_context(FIXTURE_ROOT)


def c2(**over):
    base = dict(object_id="MJOP-2", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", material_source="user", object_description="Hemelwaterafvoer pvc",
                quantity="100", vat_basis="inclusive")
    base.update(over)
    return base


def dump(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, indent=2)


def test_repeated_calls_are_byte_identical():
    first = dump(get_kengetal_candidates(c2(), root=FIXTURE_ROOT))
    for _ in range(3):
        assert dump(get_kengetal_candidates(c2(), root=FIXTURE_ROOT)) == first


def test_key_order_of_the_input_does_not_matter():
    raw = c2()
    reordered = dict(reversed(list(raw.items())))
    a = get_kengetal_candidates(raw, root=FIXTURE_ROOT)
    b = get_kengetal_candidates(reordered, root=FIXTURE_ROOT)
    assert dump(a) == dump(b) and a["call_id"] == b["call_id"]


def test_output_contains_no_timestamps_or_randomness_for_a_case_without_decision():
    out = get_kengetal_candidates(c2(), root=FIXTURE_ROOT)
    text = dump(out)
    for key in ("generated_at", "timestamp", "created_at", "reviewed_at"):
        assert key not in text


def test_call_id_depends_on_input_and_on_sources(tmp_path):
    base = get_kengetal_candidates(c2(), root=FIXTURE_ROOT)
    assert get_kengetal_candidates(c2(quantity="101"), root=FIXTURE_ROOT)["call_id"] != base["call_id"]
    # andere beslissingenopslag (zelfs leeg maar anders van inhoud) => andere bronhash => ander call_id
    other_store = copy.deepcopy(EMPTY)
    other_store["description"] = other_store["description"] + " (test)"
    root = root_with_store(tmp_path, other_store)
    changed = get_kengetal_candidates(c2(), root=root)
    assert changed["provenance"]["source_hashes"]["decision_store_sha256"] != \
        base["provenance"]["source_hashes"]["decision_store_sha256"]
    assert changed["call_id"] != base["call_id"]
    assert changed["workflow_result_id"] == base["workflow_result_id"]    # de workflow zelf is onveranderd


def test_dispatcher_and_function_agree():
    assert dump(call_tool("get_kengetal_candidates", c2())) == dump(get_kengetal_candidates(c2()))


def test_two_processes_give_the_same_bytes():
    """Ook over processen/hash-seeds heen (geen afhankelijkheid van set-volgorde of PYTHONHASHSEED)."""
    import subprocess
    import sys
    code = ("import sys,json;sys.path.insert(0,%r);from agent import call_tool;"
            "print(json.dumps(call_tool('get_kengetal_candidates',json.loads(sys.argv[1])),sort_keys=True))" % PROJECT_ROOT)
    outs = []
    for seed in ("1", "2"):
        p = subprocess.run([sys.executable, "-B", "-c", code, json.dumps(c2())], capture_output=True, text=True,
                           env={"PYTHONHASHSEED": seed, "PYTHONDONTWRITEBYTECODE": "1", "PATH": ""}, cwd=PROJECT_ROOT)
        assert p.returncode == 0, p.stderr
        outs.append(p.stdout)
    assert outs[0] == outs[1]
