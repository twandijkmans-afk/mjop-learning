"""
record_validation: block-provenance controleren en de brug naar de
gezaghebbende bronlaag (mjop_source_sections via de gecommitte
price_observations) - alleen extra provenance, nooit een tweede waarde.
Leest data/ alleen.
"""
import copy
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import record_validation as rv  # noqa: E402
import text_layer as tl  # noqa: E402

RAW = os.path.join(PROJECT_ROOT, "data", "raw")
REGISTRY = os.path.join(PROJECT_ROOT, "reports", "document_registry.json")
PRICE_OBS = os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json")


@pytest.fixture(scope="module")
def layer010():
    return tl.build_text_layer("DOC-010", RAW, REGISTRY)


@pytest.fixture(scope="module")
def source_rows010():
    d = json.load(open(PRICE_OBS))
    return [r for o in d["observations"] if o["document_id"] == "DOC-010" for r in o["source_representations"]]


def test_every_doc010_source_row_links_to_exactly_one_block(layer010, source_rows010):
    assert len(source_rows010) == 37
    for r in source_rows010:
        m = rv.link_source_row_to_blocks(layer010, r["page"], r["source_text"])
        assert m is not None, r
        assert m["block_id"].startswith(f"P{r['page']:02d}-L")


def test_link_example_row(layer010):
    m = rv.link_source_row_to_blocks(layer010, 10, "Herstellen metselwerk 5,93 m2 2028 12 1.351 1.351")
    assert m == {"block_id": "P10-L006", "text_fragment": "Herstellen metselwerk 5,93m2 2028 12 € 1.351 € 1.351",
                 "match": "exact_without_euro_and_whitespace"}


def test_link_never_guesses(layer010):
    assert rv.link_source_row_to_blocks(layer010, 11, "Herstellen metselwerk 5,93 m2 2028 12 1.351 1.351") is None
    assert rv.link_source_row_to_blocks(layer010, 10, "Herstellen metselwerk 5,93 m2 2028 12 1.352 1.352") is None
    assert rv.link_source_row_to_blocks(layer010, 10, "") is None
    # regel die meermaals op een pagina voorkomt -> dubbelzinnig -> None
    pg = next(p for p in layer010["pages"] if p["page"] == 10)
    dup = copy.deepcopy(layer010)
    dup_pg = next(p for p in dup["pages"] if p["page"] == 10)
    dup_pg["lines"].append(dict(pg["lines"][5], id="P10-L999"))
    assert rv.link_source_row_to_blocks(dup, 10, pg["lines"][5]["text"]) is None


def test_link_does_not_change_source_values(layer010, source_rows010):
    before = json.dumps(source_rows010, sort_keys=True)
    for r in source_rows010:
        rv.link_source_row_to_blocks(layer010, r["page"], r["source_text"])
    assert json.dumps(source_rows010, sort_keys=True) == before


def _rec(prov):
    return {"document_id": "DOC-010", "maintenance_actions": [
        {"action_id": "A", "element_id": "E", "field_provenance": {"total_cost_as_stated": prov}}]}


def test_verify_block_provenance_ok_and_tampering(layer010):
    good = {"document_id": "DOC-010", "page": 10, "block_id": "P10-L006-W07",
            "related_block_ids": ["P10-L003-W13"], "source_confidence": "high",
            "text_fragment": "Herstellen metselwerk 5,93m2 2028 12 € 1.351 € 1.351"}
    assert rv.verify_block_provenance(_rec(good), layer010) == []
    assert rv.verify_block_provenance(_rec(dict(good, block_id="P99-L001")), layer010)
    assert rv.verify_block_provenance(_rec(dict(good, page=11)), layer010)
    assert rv.verify_block_provenance(_rec(dict(good, text_fragment="Herstellen metselwerk 6,93m2")), layer010)


def test_existing_records_without_block_id_are_untouched(layer010):
    rec = json.load(open(os.path.join(PROJECT_ROOT, "data", "verified", "DOC-010.json")))
    assert rv.verify_block_provenance(rec, layer010) == []


def test_literal_runs():
    assert rv.literal_runs("Vervangen loodslabben opgaand werk",
                           "Vervangen loodslabben opgaand 10,00m1 2053 48 € 0\nwerk")
    assert not rv.literal_runs("Vervangen opgaand loodslabben", "Vervangen loodslabben opgaand")
    assert not rv.literal_runs("Vervangen lood", "Vervangen loodslabben")
