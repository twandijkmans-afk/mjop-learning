"""Contract- en schematests voor agent.get_kengetal_candidates: strikte invoer, strikte uitvoer, modelonafhankelijk."""
import copy
import json
import os

import jsonschema
import pytest

import support  # noqa: F401  (zet sys.path op project en scripts)
from support import FIXTURE_ROOT, PROJECT_ROOT

from agent import TOOLS, call_tool, tool_specs
from agent.contract import ToolError, load_schema, schema_errors
from agent.tools.get_kengetal_candidates import get_kengetal_candidates

NAME = "get_kengetal_candidates"
IN_SCHEMA = load_schema("get_kengetal_candidates.input.schema.json")
OUT_SCHEMA = load_schema("get_kengetal_candidates.output.schema.json")


def c2(**over):
    base = dict(object_id="MJOP-2", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", material_source="user", object_description="Hemelwaterafvoer pvc",
                quantity="100", vat_basis="inclusive")
    base.update(over)
    return base


def run(raw):
    return get_kengetal_candidates(raw, root=FIXTURE_ROOT)


def test_schemas_are_valid_draft7():
    jsonschema.Draft7Validator.check_schema(IN_SCHEMA)
    jsonschema.Draft7Validator.check_schema(OUT_SCHEMA)
    assert IN_SCHEMA["additionalProperties"] is False and OUT_SCHEMA["additionalProperties"] is False


def test_tool_specs_are_model_independent_json_schema():
    specs = tool_specs()
    assert [s["name"] for s in specs] == [NAME]
    for s in specs:
        assert set(s) == {"name", "description", "input_schema"}
        json.dumps(s)   # puur JSON: geen model- of SDK-objecten
        assert s["input_schema"]["type"] == "object"
    assert specs[0]["input_schema"] == IN_SCHEMA
    assert "geaccepteerde prijs" in specs[0]["description"]


@pytest.mark.parametrize("extra", ["root", "path", "file", "out", "data_dir", "kengetallen_file", "store", "url"])
def test_input_rejects_paths_and_unknown_fields(extra):
    for value in ("/etc/passwd", "../../data/raw", "https://example.com/x"):
        with pytest.raises(ToolError) as e:
            call_tool(NAME, c2(**{extra: value}))
        assert e.value.code == "INVALID_INPUT"


def test_call_tool_cannot_choose_the_data_root():
    # root is een Python-argument van de functie, geen toolparameter: via call_tool komt het als onbekend veld binnen.
    with pytest.raises(ToolError) as e:
        call_tool(NAME, c2(root=str(FIXTURE_ROOT)))
    assert e.value.code == "INVALID_INPUT"
    with pytest.raises(TypeError):
        call_tool(NAME, c2(), root=str(FIXTURE_ROOT))


@pytest.mark.parametrize("bad", [
    {"object_id": ""}, {"object_id": "a b"}, {"object_id": "../x"}, {"element_code_internal": "52 11"},
    {"element_code_internal": "5211/../"}, {"quantity": 100}, {"quantity": 100.5}, {"quantity": "1e3"},
    {"quantity": "1.250,50"}, {"quantity": "-3"}, {"quantity": "abc"}, {"vat_basis": "incl"},
    {"price_level_requested": "2026"}, {"price_level_requested": 1800}, {"action_text": "a\x00b"},
    {"object_description": "x" * 301}, {"construction_year": 1.5}, {"material_source": "User!"},
])
def test_input_is_strict(bad):
    with pytest.raises(ToolError) as e:
        run(c2(**bad))
    assert e.value.code == "INVALID_INPUT" and e.value.details


@pytest.mark.parametrize("missing", ["object_id", "element_code_internal"])
def test_input_requires_identity_and_element_code(missing):
    raw = c2()
    del raw[missing]
    with pytest.raises(ToolError) as e:
        run(raw)
    assert e.value.code == "INVALID_INPUT"


@pytest.mark.parametrize("not_a_dict", [None, "5211", [1], 5])
def test_input_must_be_an_object(not_a_dict):
    with pytest.raises(ToolError) as e:
        run(not_a_dict)
    assert e.value.code == "INVALID_INPUT"


def test_input_is_not_mutated():
    raw = c2()
    before = copy.deepcopy(raw)
    run(raw)
    assert raw == before


def test_unknown_tool_is_refused():
    with pytest.raises(ToolError) as e:
        call_tool("write_decision", {})
    assert e.value.code == "UNKNOWN_TOOL"
    assert sorted(TOOLS) == [NAME]      # fase 1: precies één tool, en die is alleen-lezen


def test_output_validates_for_all_statuses():
    cases = [c2(), c2(object_description="hemelwaterafvoer ander woordgebruik"), c2(element_code_internal="9999"),
             c2(material_normalized="unobtainium"), c2(unit_normalized="m2")]
    seen = set()
    for raw in cases:
        out = run(raw)
        assert schema_errors(out, OUT_SCHEMA) == []
        seen.add(out["status"])
    assert {"MATCH_PENDING_DECISION", "NO_KENGETAL"} <= seen


def _good():
    return copy.deepcopy(run(c2()))


def test_output_schema_rejects_accepted_price_without_decision():
    out = _good()
    out["price_presentation"].update(is_accepted_price=True, effective_amount="54.39")
    assert schema_errors(out, OUT_SCHEMA)
    out = _good()
    out["price_presentation"]["effective_amount"] = "54.39"          # bedrag zonder is_accepted_price
    assert schema_errors(out, OUT_SCHEMA)


def test_output_schema_rejects_candidate_marked_accepted_without_decision():
    out = _good()
    out["candidates"][0]["is_accepted_price"] = True
    assert schema_errors(out, OUT_SCHEMA)


@pytest.mark.parametrize("mutate", [
    lambda o: o["provenance"]["source_hashes"].pop("kengetallen_output_sha256"),
    lambda o: o["provenance"]["source_hashes"].update(decision_store_sha256="xyz"),
    lambda o: o["candidates"][0].update(observation_ids=[]),
    lambda o: o["candidates"][0].update(source_cluster_ids=[]),
    lambda o: o["candidates"][0].update(source_clusters=[]),
    lambda o: o["candidates"][0].update(value_exact=54.39),            # float i.p.v. Decimal-string
    lambda o: o["candidates"][0].update(value_exact="54,39"),
    lambda o: o.update(read_only=False),
    lambda o: o.pop("notice"),
    lambda o: o.update(unexpected="x"),
])
def test_output_schema_enforces_traceability_and_decimal_strings(mutate):
    out = _good()
    mutate(out)
    assert schema_errors(out, OUT_SCHEMA)
