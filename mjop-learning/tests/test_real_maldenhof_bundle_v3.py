"""Tests voor de echte Maldenhof-bundel v3 (reports/quantity/app_bundles/) en de bundelvalidator.

Read-only: er wordt niets in data/ geschreven; mutaties gebeuren op kopieën in het geheugen.
"""
import copy
import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_building_quantity_evidence as bqe  # noqa: E402
import crosswalk as xw  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402
import validate_app_quantity_bundle as vab  # noqa: E402

BUNDLE_PATH = os.path.join(ROOT, "reports", "quantity", "app_bundles", "maldenhof_DOC-005_DOC-006_v3.json")
APPROVED = sorted("""0363100012137996 0363100012102659 0363100012078022 0363100012140664 0363100012141419 0363100012091974
0363100012070344 0363100012107492 0363100012071880 0363100012144766 0363100012091756 0363100012143647 0363100012121455
0363100012134188 0363100012127361""".split())
SCOPE = "BAG:" + "+".join(APPROVED)


@pytest.fixture(scope="module")
def raw():
    with open(BUNDLE_PATH, "rb") as f:
        return f.read()


@pytest.fixture(scope="module")
def bundle(raw):
    return json.loads(raw)


def fresh():
    store = json.load(open(bqe.OUT_EVIDENCE, encoding="utf-8"))
    # de referentiebundel is de oorspronkelijke dak-plat-bundel (Sloped Roof Activation voegt dak-hellend apart toe)
    return eab.build_bundle(SCOPE, store["evidence"], json.load(open(xw.APP_CROSSWALK, encoding="utf-8")), xw.effective(),
                            json.load(open(xw.SUBJECTS, encoding="utf-8")), app_elements={"dak-plat"})


def by_role(b, role):
    return [e for e in b["entries"] if e.get("role") == role]


def test_bundle_is_deterministic_and_up_to_date(raw):
    assert vab.bundle_bytes(fresh()) == raw
    assert vab.bundle_bytes(fresh()) == vab.bundle_bytes(fresh())


def test_cli_validator_and_export_check():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "validate_app_quantity_bundle.py"), BUNDLE_PATH,
                        "--expect-panden", "15", "--check-export"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "GELDIG" in r.stdout


def test_validator_accepts_real_bundle(bundle):
    assert vab.validate(bundle, expect_panden=15) == []


def test_scope_exactly_15_panden(bundle):
    assert bundle["bundle_version"] == "mjop_app_quantity_bundle_v3"
    assert bundle["building_id"] == SCOPE and bundle["bag_pand_ids"] == APPROVED
    assert bundle["building_scope"] == {"building_id": SCOPE, "kind": "MULTI_PAND_SCOPE", "bag_pand_ids": APPROVED, "pand_count": 15}
    assert len(set(bundle["bag_pand_ids"])) == 15


def test_selectable_aggregate_is_sum_of_15_components(bundle):
    prim = by_role(bundle, "PRIMARY")
    assert len(prim) == 1
    e = prim[0]
    assert (e["app_element_key"], e["subject_key"], e["selectable"]) == ("dak-plat", "ROOF_FLAT_AREA", True)
    ev = e["evidence"]
    assert (ev["value"], ev["method_class"], ev["status"], ev["scope_level"]) == ("190.65", "GEOMETRY_DERIVED", "PROPOSED", "COMPLEX")
    comps = ev["components"]
    assert sorted(c["bag_pand_id"] for c in comps) == APPROVED
    assert sum(Decimal(c["value"]) for c in comps) == Decimal("190.65")
    assert all(c["method_class"] == "DIRECT_MEASURED" and c["rule_id"] == "bag3d.roof_flat_area" and c["snapshot_id"] for c in comps)
    refs = ev["evidence_refs"]
    assert refs["rule_id"] == "scope.sum_over_confirmed_panden" and len(refs["child_evidence_ids"]) == 15
    assert len(refs["building_link_ids"]) == 30 and refs["snapshot_ids"] == ["BAGSNAP-431559474da45dcf"]


def test_related_historical_context(bundle):
    ctx = by_role(bundle, "RELATED_CONTEXT")
    assert sorted(e["evidence"]["source_ref"]["document_id"] for e in ctx) == ["DOC-005", "DOC-006"]
    for e in ctx:
        ev = e["evidence"]
        assert e["selectable"] is False and e["subject_key"] == "ROOF_COVERING_REPORTED_AREA"
        assert e["subject_key"] != e["primary_subject_key"] == "ROOF_FLAT_AREA"
        assert e["subject_relation"]["relation"] == "RELATED_NOT_EQUIVALENT"
        assert e["subject_relation"]["resolvable_as_same_quantity"] is False
        assert (ev["value"], ev["method_class"], ev["scope_level"], ev["components"]) == ("425.80", "SOURCE_REPORTED", "COMPLEX", [])
        assert ev["source_cluster"] == "SC-DOC-005+DOC-006" and ev["source_ref"]["page"] == 7
        assert ev["evidence_refs"]["subject_mapping_ref"] == "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006"
        other = "DOC-006" if ev["source_ref"]["document_id"] == "DOC-005" else "DOC-005"
        assert other in ev["same_object_document_ids"]
    assert len({e["evidence"]["source_cluster"] for e in ctx}) == 1  # één onafhankelijke historische bron


def test_no_resolution_no_selection_no_equivalence(bundle):
    assert not set(vab._walk_keys(bundle)) & vab.FORBIDDEN_KEYS
    res = json.load(open(vab.RESOLUTIONS, encoding="utf-8"))
    assert res["records"] == []
    assert xw.effective()["HSM-ROOF_FLAT_AREA-4711-m2"]["status"] != "VERIFIED"
    subjects = {e["subject_key"] for e in by_role(bundle, "PRIMARY")}
    assert "ROOF_COVERING_REPORTED_AREA" not in subjects


def _mutate(bundle, fn):
    b = copy.deepcopy(bundle)
    fn(b)
    return vab.validate(b, expect_panden=15)


def _prim(b):
    return by_role(b, "PRIMARY")[0]


def _ctx(b):
    return by_role(b, "RELATED_CONTEXT")[0]


@pytest.mark.parametrize("name,fn,needle", [
    ("dubbel pand", lambda b: b["bag_pand_ids"].append(b["bag_pand_ids"][0]), "dubbele pand"),
    ("14 panden", lambda b: (b["bag_pand_ids"].pop(), b["building_scope"]["bag_pand_ids"].pop()), "verwacht 15"),
    ("verkeerde versie", lambda b: b.update(bundle_version="x"), "bundle_version"),
    ("aggregaat aangepast", lambda b: _prim(b)["evidence"].update(value="190.66"), "wijkt af van canoniek"),
    ("component weg", lambda b: _prim(b)["evidence"]["components"].pop(), "components"),
    ("context kiesbaar", lambda b: _ctx(b).update(selectable=True), "selectable false"),
    ("context zelfde onderwerp", lambda b: _ctx(b).update(subject_key="ROOF_FLAT_AREA"), "subject_key"),
    ("relatie equivalent", lambda b: _ctx(b)["subject_relation"].update(relation="EQUIVALENT"), "RELATED_NOT_EQUIVALENT"),
    ("historisch gesplitst", lambda b: _ctx(b)["evidence"].update(scope_level="PAND"), "complexniveau"),
    ("cluster weg", lambda b: _ctx(b)["evidence"].update(source_cluster=None), "source cluster"),
    ("keuze in bundel", lambda b: _prim(b)["evidence"].update(selected_evidence_id="x"), "verboden sleutel"),
    ("resolutie in bundel", lambda b: b.update(resolved_value="190.65"), "verboden sleutel"),
    ("onbekende evidence", lambda b: _prim(b)["evidence"].update(evidence_id="QE-0000000000000000"), "bestaat niet"),
    ("onbekende snapshot", lambda b: _prim(b)["evidence"]["evidence_refs"]["snapshot_ids"].append("BAGSNAP-x"), "snapshot"),
    ("secret", lambda b: b.update(tenant_note="sk-ant-abcdefghijklmnop"), "secret"),
])
def test_validator_rejects(bundle, name, fn, needle):
    errs = _mutate(bundle, fn)
    assert errs and any(needle in e for e in errs), (name, errs)


def test_validator_rejects_active_resolution(bundle):
    ev = json.load(open(bqe.OUT_EVIDENCE, encoding="utf-8"))
    res = {"records": [{"resolution_id": "QRR-00001", "building_id": SCOPE, "status": "ACTIVE"}]}
    errs = vab.validate(bundle, evidence_store=ev, resolutions=res, expect_panden=15)
    assert any("ACTIVE quantity resolution" in e for e in errs)


def test_v1_v2_bundles_without_vocab_have_no_evidence_refs():
    store = json.load(open(bqe.OUT_EVIDENCE, encoding="utf-8"))
    b = eab.build_bundle(SCOPE, store["evidence"], json.load(open(xw.APP_CROSSWALK, encoding="utf-8")), xw.effective())
    assert b["bundle_version"] == "mjop_app_quantity_bundle_v2"
    assert all("evidence_refs" not in e["evidence"] for e in b["entries"])
    assert vab.validate(b, expect_panden=15) == []
