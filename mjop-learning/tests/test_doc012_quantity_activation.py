"""Tests voor DOC-012 Quantity Activation + Bundle v3: menselijke besluiten, evidence via de generieke pipeline,
de tweede echte bundel v3 en de generieke validator. Read-only; niets wordt in data/ geschreven."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import doc012_quantity_activation as act  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402
import validate_app_quantity_bundle as vab  # noqa: E402

PAND = "0518100000354752"
BID = "BAG:" + PAND
SNAP = "BAGSNAP-599d2f2004100011"
MAP = "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012"
BUNDLE = os.path.join(ROOT, "reports", "quantity", "app_bundles", "doc012_meppelweg_v3.json")
MALDENHOF = os.path.join(ROOT, "reports", "quantity", "app_bundles", "maldenhof_DOC-005_DOC-006_v3.json")


@pytest.fixture(scope="module")
def evidence():
    return json.load(open(bqe.OUT_EVIDENCE, encoding="utf-8"))


@pytest.fixture(scope="module")
def bundle():
    return json.load(open(BUNDLE, encoding="utf-8"))


def fresh():
    store = json.load(open(bqe.OUT_EVIDENCE, encoding="utf-8"))
    return eab.build_bundle(BID, store["evidence"], json.load(open(xw.APP_CROSSWALK, encoding="utf-8")), xw.effective(),
                            json.load(open(xw.SUBJECTS, encoding="utf-8")))


# --- besluiten -----------------------------------------------------------------------------

def test_exactly_one_confirmed_pand_for_doc012():
    recs = [r for r in bl.load_store()["records"] if r["document_id"] == "DOC-012"]
    assert len(recs) == 1
    r = recs[0]
    assert (r["link_id"], r["bag_pand_id"], r["link_status"], r["status"]) == ("BLINK-00081", PAND, "CONFIRMED", "ACTIVE")
    assert r["evidence"]["snapshot_id"] == SNAP and r["reviewer"] == {"reviewer_id": "user-approved", "reviewer_type": "human"}
    assert "42 verblijfsobjecten" in r["decision_reason"] and "42 postkasten" in r["decision_reason"]
    assert bl.active_links(bl.load_store())["DOC-012"] == [PAND]


def test_building_id_stable():
    assert bqe.building_id_for([PAND]) == BID == bqe.building_id_for([PAND, PAND])


def test_h2_not_selected_without_artificial_rejects():
    rep = json.load(open(act.OUT_JSON, encoding="utf-8"))
    assert rep["scope_decision"]["chosen"] == "H1" and rep["scope_decision"]["H2_FULL_RANGE"] == "NOT_SELECTED"
    assert "gesloopte panden" in rep["scope_decision"]["H2_reason"]
    assert not any(r["link_status"] == "REJECTED" for r in bl.load_store()["records"] if r["document_id"] == "DOC-012")
    # H2 blijft niet-canoniek: geen tweede DOC-012-snapshot
    assert [s["snapshot_id"] for s in bs.load_snapshots() if s["document_id"] == "DOC-012"] == [SNAP]


def test_exact_mapping_verified_and_4711_m1_excluded():
    eff = xw.effective()
    assert eff[MAP] == {"status": "VERIFIED", "human_verified": True, "decision_id": "XWD-00003"}
    assert eff["HSM-ROOF_FLAT_AREA-4711-m2"]["status"] != "VERIFIED"
    vocab = json.load(open(xw.SUBJECTS, encoding="utf-8"))
    m = next(x for x in vocab["historical_subject_mappings"] if x["mapping_id"] == MAP)
    qos = [o for o in json.load(open(bqe.QO_PATH, encoding="utf-8"))["observations"] if o["document_id"] == "DOC-012"]
    assert [o["quantity_observation_id"] for o in qos if bqe.mapping_matches(m, o)] == ["QO-DOC-012-EL-024"]
    m1 = [o for o in qos if o["element"]["element_code_internal"] == "4711" and o["unit_normalized"] == "m1"]
    assert len(m1) == 2 and not any(bqe.mapping_matches(m, o) for o in m1)


# --- evidence ------------------------------------------------------------------------------

def test_3dbag_evidence_from_canonical_snapshot(evidence):
    snap = next(s for s in bs.load_snapshots() if s["snapshot_id"] == SNAP)
    raw = next(p for p in snap["panden"] if p["bag_pand_id"] == PAND)["threedbag"]["attributes"]["b3_opp_dak_plat"]
    flat = [e for e in evidence["evidence"] if e["building_id"] == BID and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"]
    assert len(flat) == 1
    e = flat[0]
    assert Decimal(e["value"]) == Decimal(str(raw)) == Decimal("875.63")
    assert (e["method_class"], e["source_type"], e["status"]) == ("DIRECT_MEASURED", "3D_BAG", "PROPOSED")
    assert e["source_ref"]["snapshot_id"] == SNAP and e["source_ref"]["building_link_ids"] == ["BLINK-00081"]


def test_historical_evidence_is_roof_covering_not_flat(evidence):
    hist = [e for e in evidence["evidence"] if e["building_id"] == BID and e["source_type"] == "MJOP_ELEMENT_OVERVIEW"]
    assert len(hist) == 1  # 2110 gevel is NIET geactiveerd
    e = hist[0]
    assert (e["quantity_subject"]["subject_key"], e["value"], e["unit_normalized"], e["method_class"]) == (
        "ROOF_COVERING_REPORTED_AREA", "801.04", "m2", "SOURCE_REPORTED")
    assert e["source_ref"]["quantity_observation_id"] == "QO-DOC-012-EL-024" and e["source_ref"]["subject_mapping_ref"] == MAP
    rep = json.load(open(bqe.OUT_JSON, encoding="utf-8"))
    c = next(c for c in rep["comparisons"] if c["document_id"] == "DOC-012")
    assert (c["comparison_kind"], c["bag3d_subject_key"], c["review_status"]) == (
        "RELATED_SUBJECT_NOT_EQUIVALENT", "ROOF_FLAT_AREA", "NOT_RESOLVABLE_AS_SAME_QUANTITY")
    assert c["difference_band"] is None


def test_facade_not_activated(evidence):
    vocab = json.load(open(xw.SUBJECTS, encoding="utf-8"))
    assert not any("OUTER_WALL_GROSS_AREA" in r["subjects"] for r in vocab["subject_relations"])
    assert not any(m["subject_key"] == "OUTER_WALL_GROSS_AREA" for m in vocab["historical_subject_mappings"])
    assert not any(e["source_ref"].get("quantity_observation_id") == "QO-DOC-012-EL-001" for e in evidence["evidence"])


# --- bundel --------------------------------------------------------------------------------

def test_bundle_deterministic_and_up_to_date():
    raw = open(BUNDLE, "rb").read()
    assert vab.bundle_bytes(fresh()) == raw == vab.bundle_bytes(fresh())


def test_bundle_content(bundle):
    assert bundle["bundle_version"] == "mjop_app_quantity_bundle_v3"
    assert bundle["building_id"] == BID and bundle["bag_pand_ids"] == [PAND]
    assert bundle["building_scope"] == {"building_id": BID, "kind": "SINGLE_PAND", "bag_pand_ids": [PAND], "pand_count": 1}
    prim = [e for e in bundle["entries"] if e["role"] == "PRIMARY"]
    ctx = [e for e in bundle["entries"] if e["role"] == "RELATED_CONTEXT"]
    assert len(prim) == 1 and len(ctx) == 1
    p, c = prim[0], ctx[0]
    assert (p["app_element_key"], p["subject_key"], p["selectable"], p["evidence"]["value"], p["evidence"]["status"]) == (
        "dak-plat", "ROOF_FLAT_AREA", True, "875.63", "PROPOSED")
    assert p["evidence"]["source_ref"]["bag_pand_id"] == PAND
    r = p["evidence"]["evidence_refs"]
    assert (r["rule_id"], r["snapshot_ids"], r["building_link_ids"], r["bag_pand_ids"]) == ("bag3d.roof_flat_area", [SNAP], ["BLINK-00081"], [PAND])
    assert (c["subject_key"], c["selectable"], c["primary_subject_key"], c["evidence"]["value"]) == (
        "ROOF_COVERING_REPORTED_AREA", False, "ROOF_FLAT_AREA", "801.04")
    assert c["subject_relation"]["relation"] == "RELATED_NOT_EQUIVALENT"
    rc = c["evidence"]["evidence_refs"]
    assert rc["quantity_observation_id"] == "QO-DOC-012-EL-024" and rc["subject_mapping_ref"] == MAP and rc["source_sha256"]
    assert c["evidence"]["source_ref"]["document_id"] == "DOC-012" and c["evidence"]["source_ref"]["page"] == 7
    assert all(e["evidence"]["unit"] == "m2" for e in bundle["entries"])
    assert not set(vab._walk_keys(bundle)) & vab.FORBIDDEN_KEYS


def test_validator_accepts_and_rejects(bundle):
    assert vab.validate(bundle, expect_panden=1) == []
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "validate_app_quantity_bundle.py"), BUNDLE,
                        "--expect-panden", "1", "--check-export"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "GELDIG" in r.stdout, r.stdout + r.stderr
    ctx = lambda b: next(e for e in b["entries"] if e["role"] == "RELATED_CONTEXT")  # noqa: E731
    for name, fn, needle in [
        ("context kiesbaar", lambda b: ctx(b).update(selectable=True), "selectable false"),
        ("zelfde onderwerp", lambda b: ctx(b).update(subject_key="ROOF_FLAT_AREA"), "subject_key"),
        ("m1-eenheid", lambda b: ctx(b)["evidence"].update(unit="m1"), "eenheid"),
        ("waarde aangepast", lambda b: ctx(b)["evidence"].update(value="953.58"), "wijkt af van canoniek"),
        ("ander pand", lambda b: b.update(bag_pand_ids=["0518100001631386"]), "building_id"),
        ("resolutie", lambda b: b.update(resolved_value="875.63"), "verboden sleutel"),
    ]:
        b = copy.deepcopy(bundle)
        fn(b)
        errs = vab.validate(b, expect_panden=1)
        assert any(needle in e for e in errs), (name, errs)
    assert vab.validate(bundle, expect_panden=2)  # exact aantal panden wordt gecontroleerd


def test_same_generic_pipeline_for_single_and_multi_pand():
    # dezelfde exporter/validator; geen DOC-012-speciale gevallen in generieke code
    for f in ("export_app_quantity_bundle.py", "validate_app_quantity_bundle.py", "build_building_quantity_evidence.py"):
        text = open(os.path.join(ROOT, "scripts", f), encoding="utf-8").read()
        assert "DOC-012" not in text and "0518100000354752" not in text and "Meppelweg" not in text
    mald = json.load(open(MALDENHOF, encoding="utf-8"))
    assert vab.validate(mald, expect_panden=15) == []
    assert mald["building_scope"]["kind"] == "MULTI_PAND_SCOPE"


def test_no_resolution_and_maldenhof_hash_stable():
    assert json.load(open(vab.RESOLUTIONS, encoding="utf-8"))["records"] == []
    assert hashlib.sha256(open(MALDENHOF, "rb").read()).hexdigest() == "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933"


def test_activation_report_up_to_date():
    r = act.build()
    assert open(act.OUT_JSON, encoding="utf-8").read() == json.dumps(r, ensure_ascii=False, indent=1) + "\n"
    assert open(act.OUT_MD, encoding="utf-8").read() == act.render(r)
    assert r["bundle"]["validator_errors"] == [] and r["quantity_resolution"]["records_for_scope"] == 0
