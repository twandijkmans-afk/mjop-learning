"""Tests voor de Kengetal Product Bridge Review v1 (read-only review; geen activatie).

Controleert dat de review reproduceerbaar is, alleen de officiële kengetallenbron gebruikt, alle app-elementen dekt,
geen eenheidsconversie toelaat, en dat niets in kengetallen, bundels, besluiten, resoluties of app-prijzen verandert.
"""
import hashlib
import inspect
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import crosswalk as xw  # noqa: E402
import kengetal_product_bridge_review as kpb  # noqa: E402

KG_FILE_SHA = "e8b9b2260fb681da242817e51dfdb5ca3b1ab3ec1e3e5dcd6b56d3cc71761897"
BUNDLES = {"maldenhof_DOC-005_DOC-006_v3.json": "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933",
           "doc012_meppelweg_v3.json": "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191",
           "maldenhof_expanded_v3.json": "c78f387e66ce7963d7a434270350f0ee8fa4c9f232099f871e83ed202cd2975d",
           "maldenhof_geometry_expanded_v3.json": "8264bdceb2c0ee633333b79ac6a073f8c9ea48661659007f69ff22df391a52ca",
           "doc012_geometry_v3.json": "fe12a4eb7999f784056d46a607e5e37b6223fc30a6eff0c4c86924390f074a87"}
APP_PRICE_VALUES_SHA = "b0f567058426"   # prefix van price_values_sha256 van MJOP-App b77909a (vóór de labelfix)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def report():
    return kpb.build()


def test_committed_report_is_up_to_date(report):
    assert open(kpb.OUT_JSON, encoding="utf-8").read() == json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    assert open(kpb.OUT_MD, encoding="utf-8").read() == kpb.render(report)


def test_official_source_is_data_kengetallen_only(report):
    assert report["inputs"]["official_kengetallen"]["path"] == "data/kengetallen/kengetallen_batch1.json"
    assert "data/kentallen/" in report["inputs"]["not_used_as_official"]
    src = inspect.getsource(kpb)
    code = src[src.index("ROOT = "):]
    assert '"kentallen"' not in code and "kentallen_batch1" not in code and "compute_kentallen" not in code.replace('"scripts/compute_kentallen.py"', "")
    # de review leest de actuele AVAILABLE kengetallen, niet een hardgecodeerde lijst
    raw = json.load(open(kpb.OFFICIAL_KG, encoding="utf-8"))
    want = sorted(k["kengetal_id"] for k in raw["kengetallen"] if k["status"] == "AVAILABLE")
    got = sorted(k["kengetal_id"] for k in report["A_official_kengetallen"]["kengetallen"])
    assert got == want and report["A_official_kengetallen"]["available_count"] == len(want)


def test_kg_fields_and_no_market_price_claims(report):
    for k in report["A_official_kengetallen"]["kengetallen"]:
        for f in ("element_code", "action", "material", "unit", "value_display", "min_display", "max_display", "source_cluster_count",
                  "price_levels_per_cluster", "vat_basis", "caveats", "calculation_method", "independent_source_clusters"):
            assert f in k
        assert k["independent_source_clusters"] == k["source_cluster_count"] >= 3
        assert "geen actuele marktprijs" in k["presentation"]
    md = open(kpb.OUT_MD, encoding="utf-8").read().lower()
    for bad in ("prijspeil 2026", "actuele marktprijs is", "normprijs is"):
        assert bad not in md


def test_all_app_elements_covered(report):
    app = json.load(open(kpb.APP_PRICES, encoding="utf-8"))
    keys = [d["key"] for d in app["snapshots"][-1]["prices"]["element_library"]]
    assert len(keys) == 24 and sorted(keys) == sorted(kpb.ELEMENTS)
    assert [r["app_element_key"] for r in report["C_app_element_kg_matrix"]] == keys
    assert sum(report["K_coverage"]["counts"].values()) == 24
    assert all(r["result"] in kpb.MATCH_RESULTS for r in report["C_app_element_kg_matrix"])


def test_unit_mismatch_blocks_mapping(report):
    assert not kpb.unit_compatible("m2", "m1")
    assert not kpb.unit_compatible("app", "m1")
    assert not kpb.unit_compatible("app", "piece")
    assert not kpb.unit_compatible(None, None)
    assert kpb.unit_compatible("m2", "m2")
    for r in report["C_app_element_kg_matrix"]:
        for c in r["official_kg_checks"]:
            if not c["unit_match"]:
                assert r["result"] != "READY_FOR_KG_INTEGRATION"
    rows = {r["app_element_key"]: r for r in report["C_app_element_kg_matrix"]}
    assert rows["dak-plat"]["result"] == "KG_EXISTS_BUT_NOT_COMPATIBLE"
    assert rows["dak-plat"]["official_kg_checks"][0]["unit_match"] is False      # m2 vs m1 aluminium daktrim
    assert rows["dakgoten"]["official_kg_checks"][0]["unit_match"] is False      # app. vs m1 hemelwaterafvoer
    for r in report["C_app_element_kg_matrix"]:                                  # geen omreken-/schaalfactor in de matching
        keys = {k for c in r["official_kg_checks"] + r["price_candidate_groups"] for k in c}
        assert not {k for k in keys if "factor" in k or "conversion" in k or "scale" in k}


def test_price_sources_classified_without_official_kg_in_app(report):
    b = report["B_app_price_inventory"]
    assert all(c["category"] in kpb.PRICE_SOURCE_CATEGORIES for c in b["components"])
    assert b["official_internal_kengetal_in_app"] == 0
    assert {c["category"] for c in b["components"] if c["component"].endswith((".kengetal", ".basis"))} == {"APP_DEFAULT_ESTIMATE"}
    assert [c for c in b["components"] if c["component"] == "steiger.tarief"][0]["category"] == "FORMULA_DEFAULT"
    assert b["code_facts"]["offers_used_in_element_cost"] is False


def test_roof_readiness_findings(report):
    d, e = report["D_flat_roof"], report["E_sloped_roof"]
    assert d["official_available_m2_kg"] == [] and e["official_available_m2_kg"] == []
    assert all(g["readiness"] == "INSUFFICIENT_CLUSTERS" for g in d["readiness_groups"])
    assert e["tile_price_observations"] == 0 and e["tile_quantity_observations_without_price"]
    assert "QO-DOC-002-EL-103" not in e["tile_quantity_observations_without_price"]   # leisteen telt niet als dakpan


def test_scaffolding_and_indexation(report):
    f = report["F_scaffolding_price"]
    assert f["historical_observations"] and f["historical_per_m2_evidence"] == []
    for k in report["I_indexation"]["per_kg"]:
        assert k["indexation_readiness"] in ("INDEXATION_READY", "INDEXATION_AMBIGUOUS", "INDEXATION_NOT_POSSIBLE")
    assert report["I_indexation"]["applied"] is False
    kg = {"price_levels": {"per_cluster": {"a": ["1-1-2024"], "b": ["1-1-2024"]}, "years": [2024], "mixed_price_level": False, "missing_price_level": False}}
    assert kpb.indexation_class(kg) == "INDEXATION_READY"
    kg["price_levels"].update(per_cluster={"a": ["1-1-2024"], "b": ["1-1-2025"]}, years=[2024, 2025], mixed_price_level=True)
    assert kpb.indexation_class(kg) == "INDEXATION_AMBIGUOUS"
    kg["price_levels"].update(per_cluster={"a": [None], "b": ["1-1-2025"]}, missing_price_level=True)
    assert kpb.indexation_class(kg) == "INDEXATION_NOT_POSSIBLE"


def test_official_kengetallen_byte_identical():
    assert sha(kpb.OFFICIAL_KG) == KG_FILE_SHA


def test_quantity_bundles_byte_identical(report):
    for name, h in BUNDLES.items():
        assert sha(os.path.join(kpb.BUNDLES, name)) == h
    assert report["state_unchanged"]["quantity_bundles_sha256"] == BUNDLES


def test_no_crosswalk_decision_or_resolution_changes(report):
    assert sorted(r["decision_id"] for r in xw.load_store()["records"]) == [f"XWD-0000{i}" for i in range(1, 7)]
    assert report["state_unchanged"]["quantity_resolutions"] == 0


def test_app_price_values_unchanged():
    app = json.load(open(kpb.APP_PRICES, encoding="utf-8"))
    assert app["reference_commit"].startswith("b77909a") and app["latest_commit"].startswith("eaeb256")
    assert app["price_values_identical_across_commits"] is True
    assert {s["price_values_sha256"][:12] for s in app["snapshots"]} == {APP_PRICE_VALUES_SHA}
    lib = {d["key"]: d for d in app["snapshots"][-1]["prices"]["element_library"]}
    assert (lib["dak-plat"]["kengetal"], lib["dak-hellend"]["kengetal"], lib["gevel-metselwerk"]["kengetal"]) == (165, 95, 26)
    assert app["snapshots"][-1]["prices"]["scaffold"] == {"rate_low_eur_per_m2": 6, "rate_high_eur_per_m2": 11, "height_threshold_m": 8}
