"""
De provenance-uitbreiding is alleen optioneel en aanvullend: alle bestaande
records blijven geldig, nieuwe velden worden geaccepteerd, onbekende velden
blijven verboden (additionalProperties: false).
"""
import copy
import glob
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import record_validation as rv  # noqa: E402

PROV = {"document_id": "DOC-010", "page": 10, "table_index": None,
        "text_fragment": "Keuren hanebalk 1,00m2 2028 6 € 491 € 491 € 981", "source_confidence": "high"}
BLOCK_PROV = dict(PROV, block_id="P10-L012-W07", related_block_ids=["P10-L003-W13"],
                  extraction_rule="nl_values.profile:pdf_whole_euro_dot_thousands")


@pytest.mark.parametrize("layer", ["extracted", "normalized", "verified"])
def test_all_existing_records_remain_valid(layer):
    paths = sorted(glob.glob(os.path.join(PROJECT_ROOT, "data", layer, "*.json")))
    assert paths
    for p in paths:
        assert rv.validate_entities(json.load(open(p))) == [], p


def test_new_optional_provenance_fields_accepted():
    assert rv.schema_errors(BLOCK_PROV, "_provenance.schema.json") == []
    xls = dict(PROV, page=None, sheet="Sheet", cell_ref="C13", block_id="S01-R0013-C003")
    assert rv.schema_errors(xls, "_provenance.schema.json") == []


def test_provenance_still_rejects_unknown_fields():
    bad = dict(PROV, line=12)
    assert rv.schema_errors(bad, "_provenance.schema.json")
    bad2 = dict(PROV, block_id=123)
    assert rv.schema_errors(bad2, "_provenance.schema.json")


def test_pairs_and_plain_fields_can_carry_provenance():
    action = {
        "action_id": "DOC-010-ACT-001", "element_id": "DOC-010-EL-001",
        "action": {"original_value": "Keuren hanebalk", "normalized_value": None, "provenance": BLOCK_PROV},
        "unit": {"original_value": "m2", "normalized_value": None, "provenance": BLOCK_PROV},
        "total_cost_as_stated": "491",
        "field_provenance": {"total_cost_as_stated": BLOCK_PROV},
    }
    assert rv.schema_errors(action, "maintenance_action.schema.json") == []
    bad = copy.deepcopy(action)
    bad["field_provenance"]["iets_anders"] = BLOCK_PROV
    assert rv.schema_errors(bad, "maintenance_action.schema.json")
    element = {"element_id": "E", "building_id": "B",
               "element_type": {"original_value": "Hijsbalk staal", "normalized_value": None, "provenance": BLOCK_PROV},
               "element_code": {"original_value": "2120", "normalized_value": None, "provenance": BLOCK_PROV}}
    assert rv.schema_errors(element, "element.schema.json") == []
    obs = {"observation_id": "O", "element_id": "E", "source": BLOCK_PROV,
           "condition_score": {"original_value": "8", "normalized_value": None, "scale": None, "provenance": BLOCK_PROV}}
    assert rv.schema_errors(obs, "observation.schema.json") == []


def test_validate_entities_agrees_with_existing_extract_batch_validation():
    import warnings
    import extract_batch as eb
    rec = json.load(open(os.path.join(PROJECT_ROOT, "data", "extracted", "DOC-010.json")))
    bad = copy.deepcopy(rec)
    bad["maintenance_actions"][0]["planned_year"] = {"value": 2028}  # requires_human_review ontbreekt
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert bool(eb.validate_record(bad, os.path.join(PROJECT_ROOT, "schemas"))) is True
        assert eb.validate_record(rec, os.path.join(PROJECT_ROOT, "schemas")) == []
    assert rv.validate_entities(bad)
    assert rv.validate_entities(rec) == []
