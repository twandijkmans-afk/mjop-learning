"""Tests voor Sloped Roof Quantity Activation v1.

Besluiten van de gebruiker (2026-10-05):
- XQ-dak-hellend-ROOF_SLOPED_AREA-m2: app-element dak-hellend -> ROOF_SLOPED_AREA (geometrie), VERIFIED (XWD-00004);
- HSM-ROOF_TILES_REPORTED_AREA-4712-m2-DOC-005-006: exact 'Dakpan beton' / 'Hellend dak', VERIFIED (XWD-00005);
- ROOF_TILES_REPORTED_AREA ~ ROOF_SLOPED_AREA = RELATED_NOT_EQUIVALENT;
- XW-dak-hellend-4712-m2 blijft REVIEW_REQUIRED; ROOF_TOTAL_AREA/BUILDING_HEIGHT nooit PRIMARY.
Read-only: mutaties gebeuren op kopieën in het geheugen.
"""
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

import build_building_quantity_evidence as bqe  # noqa: E402
import crosswalk as xw  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402
import validate_app_quantity_bundle as vab  # noqa: E402

BUNDLES = os.path.join(ROOT, "reports", "quantity", "app_bundles")
EXPANDED = os.path.join(BUNDLES, "maldenhof_expanded_v3.json")
APPROVED = sorted("""0363100012137996 0363100012102659 0363100012078022 0363100012140664 0363100012141419 0363100012091974
0363100012070344 0363100012107492 0363100012071880 0363100012144766 0363100012091756 0363100012143647 0363100012121455
0363100012134188 0363100012127361""".split())
SCOPE = "BAG:" + "+".join(APPROVED)
DOC012 = "BAG:0518100000354752"
XQ = "XQ-dak-hellend-ROOF_SLOPED_AREA-m2"
TILES_HSM = "HSM-ROOF_TILES_REPORTED_AREA-4712-m2-DOC-005-006"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def vocab():
    return load(xw.SUBJECTS)


@pytest.fixture(scope="module")
def store():
    return load(bqe.OUT_EVIDENCE)


@pytest.fixture(scope="module")
def bundle():
    return load(EXPANDED)


def export(building_id, store, vocab, app_elements=None):
    return eab.build_bundle(building_id, store["evidence"], load(xw.APP_CROSSWALK), xw.effective(), vocab,
                            app_elements=app_elements)


def by(b, el, role):
    return [e for e in b["entries"] if e["app_element_key"] == el and e["role"] == role]


# --- besluiten en vocabulaire ------------------------------------------------------------
def test_app_quantity_subject_mapping_is_not_an_element_code_mapping():
    m = {x["mapping_id"]: x for x in load(xw.APP_CROSSWALK)["mappings"]}[XQ]
    assert m["mapping_kind"] == "APP_QUANTITY_SUBJECT" and m["internal_element_code"] is None
    assert (m["app_element_key"], m["unit"], m["quantity_subject"]) == ("dak-hellend", "m2", "ROOF_SLOPED_AREA")
    eff = xw.effective()
    assert eff[XQ]["status"] == "VERIFIED" and eff[XQ]["decision_id"] == "XWD-00004"
    assert eff["XW-dak-hellend-4712-m2"]["status"] == "REVIEW_REQUIRED"  # besluit C


def test_decisions_are_human_and_reason_is_verbatim():
    recs = {r["decision_id"]: r for r in load(xw.DECISIONS)["records"]}
    assert sorted(recs) == ["XWD-00001", "XWD-00002", "XWD-00003", "XWD-00004", "XWD-00005"]
    assert recs["XWD-00004"]["mapping_id"] == XQ and recs["XWD-00005"]["mapping_id"] == TILES_HSM
    for d in ("XWD-00004", "XWD-00005"):
        assert recs[d]["decision"] == "VERIFY" and recs[d]["reviewer"]["reviewer_type"] == "human"
    assert recs["XWD-00004"]["decision_reason"].startswith("Het app-element 'Dakbedekking hellend dak (pannen)'")
    assert "Dit besluit zegt niets over historische code 4712" in recs["XWD-00004"]["decision_reason"]
    assert not any(r["mapping_id"] == "XW-dak-hellend-4712-m2" for r in recs.values())


def test_tiles_subject_and_relation(vocab):
    s = {x["subject_key"]: x for x in vocab["subjects"]}["ROOF_TILES_REPORTED_AREA"]
    assert (s["unit"], s["method_class"], s["source_reported_only"]) == ("m2", "SOURCE_REPORTED", True)
    rel = [r for r in vocab["subject_relations"] if set(r["subjects"]) == {"ROOF_TILES_REPORTED_AREA", "ROOF_SLOPED_AREA"}]
    assert len(rel) == 1 and rel[0]["relation"] == "RELATED_NOT_EQUIVALENT"
    for flag in ("resolvable_as_same_quantity", "average", "single_resolution", "auto_select_winner"):
        assert rel[0][flag] is False, flag
    assert bqe.related_subjects(vocab, "ROOF_SLOPED_AREA") == {"ROOF_TILES_REPORTED_AREA": rel[0]["relation_id"]}


def test_product_roles(vocab):
    roles = {x["subject_key"]: x.get("product_role") for x in vocab["subjects"]}
    assert roles["ROOF_TOTAL_AREA"] == "INFRASTRUCTURE_ONLY" and roles["BUILDING_HEIGHT"] == "CONTEXT_ONLY"


def test_tiles_mapping_matches_only_doc005_doc006_dakpan_beton(vocab):
    hsm = {m["mapping_id"]: m for m in vocab["historical_subject_mappings"]}[TILES_HSM]
    assert xw.effective()[TILES_HSM]["status"] == "VERIFIED" and xw.effective()[TILES_HSM]["decision_id"] == "XWD-00005"
    qos = load(bqe.QO_PATH)["observations"]
    assert sorted(o["quantity_observation_id"] for o in qos if bqe.mapping_matches(hsm, o)) == \
        ["QO-DOC-005-EL-027", "QO-DOC-006-EL-027"]
    # leisteen (besluit D), shingles, zink, loodslab en m1 vallen er buiten
    others = [o for o in qos if o["element"]["element_code_internal"] == "4712" and not bqe.mapping_matches(hsm, o)]
    assert any(o["unit_normalized"] == "m1" for o in others)
    descr = {(o["element"].get("element_description_original") or "").lower() for o in others}
    assert any("leisteen" in d for d in descr)


def test_tiles_mapping_is_exact_not_fuzzy(vocab):
    hsm = {m["mapping_id"]: m for m in vocab["historical_subject_mappings"]}[TILES_HSM]
    qo = copy.deepcopy([o for o in load(bqe.QO_PATH)["observations"] if o["quantity_observation_id"] == "QO-DOC-005-EL-027"][0])
    assert bqe.mapping_matches(hsm, qo)
    for path, val in ((("element", "element_description_original"), "Dakpannen beton"),
                      (("element", "location_original"), "Hellend dak "), (("document_id",), "DOC-001"),
                      (("unit_normalized",), "m1")):
        q = copy.deepcopy(qo)
        tgt = q
        for k in path[:-1]:
            tgt = tgt[k]
        tgt[path[-1]] = val
        assert not bqe.mapping_matches(hsm, q), path


# --- evidence ------------------------------------------------------------------------------
def test_sloped_aggregate_read_from_canonical_evidence(store):
    agg = [e for e in store["evidence"] if e["building_id"] == SCOPE and e["quantity_subject"]["subject_key"] == "ROOF_SLOPED_AREA"]
    assert len(agg) == 1 and agg[0]["source_ref"].get("aggregation")
    kids = {e["evidence_id"]: e for e in store["evidence"]}
    total = sum(Decimal(kids[i]["value"]) for i in agg[0]["calculation"]["input_evidence_ids"])
    assert Decimal(agg[0]["value"]) == total and len(agg[0]["calculation"]["input_evidence_ids"]) == 15


def test_tiles_evidence_one_source_cluster(store):
    tiles = [e for e in store["evidence"] if e["quantity_subject"]["subject_key"] == "ROOF_TILES_REPORTED_AREA"]
    assert sorted(e["source_ref"]["quantity_observation_id"] for e in tiles) == ["QO-DOC-005-EL-027", "QO-DOC-006-EL-027"]
    assert {e["value"] for e in tiles} == {"1485.60"} and {e["building_id"] for e in tiles} == {SCOPE}
    assert {e["dependency"]["source_cluster"] for e in tiles} == {"SC-DOC-005+DOC-006"}
    assert all(e["method_class"] == "SOURCE_REPORTED" and e["source_ref"]["subject_mapping_ref"] == TILES_HSM for e in tiles)


def test_doc012_sloped_zero_is_measured_and_has_no_context(store, vocab):
    ev = [e for e in store["evidence"] if e["building_id"] == DOC012 and e["quantity_subject"]["subject_key"] == "ROOF_SLOPED_AREA"]
    assert len(ev) == 1 and ev[0]["value"] == "0.0" and ev[0]["method_class"] == "DIRECT_MEASURED"
    assert not any(e["building_id"] == DOC012 and e["quantity_subject"]["subject_key"] == "ROOF_TILES_REPORTED_AREA"
                   for e in store["evidence"])
    b = export(DOC012, store, vocab, app_elements={"dak-hellend"})
    assert [(e["subject_key"], e["evidence"]["value"]) for e in b["entries"]] == [("ROOF_SLOPED_AREA", "0.0")]
    assert not any(e.get("role") == "RELATED_CONTEXT" for e in b["entries"])


# --- bundels -------------------------------------------------------------------------------
def test_reference_bundles_unchanged():
    assert sha(os.path.join(BUNDLES, "maldenhof_DOC-005_DOC-006_v3.json")) == \
        "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933"
    assert sha(os.path.join(BUNDLES, "doc012_meppelweg_v3.json")) == \
        "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191"


def test_expanded_bundle_deterministic_and_valid(bundle, store, vocab):
    raw = open(EXPANDED, "rb").read()
    assert vab.bundle_bytes(export(SCOPE, store, vocab)) == raw
    assert vab.bundle_bytes(export(SCOPE, store, vocab, app_elements={"dak-plat", "dak-hellend"})) == raw
    assert vab.validate(bundle, expect_panden=15) == []
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "validate_app_quantity_bundle.py"), EXPANDED,
                        "--expect-panden", "15", "--check-export"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "GELDIG" in r.stdout, r.stdout + r.stderr


def test_expanded_bundle_contents(bundle):
    assert bundle["bundle_version"] == "mjop_app_quantity_bundle_v3" and bundle["bag_pand_ids"] == APPROVED
    (p,) = by(bundle, "dak-hellend", "PRIMARY")
    assert (p["subject_key"], p["selectable"], p["crosswalk_mapping_id"], p["crosswalk_decision_id"]) == \
        ("ROOF_SLOPED_AREA", True, XQ, "XWD-00004")
    assert sorted(c["bag_pand_id"] for c in p["evidence"]["components"]) == APPROVED
    assert sum(Decimal(c["value"]) for c in p["evidence"]["components"]) == Decimal(p["evidence"]["value"])
    ctx = by(bundle, "dak-hellend", "RELATED_CONTEXT")
    assert sorted(e["evidence"]["source_ref"]["document_id"] for e in ctx) == ["DOC-005", "DOC-006"]
    for e in ctx:
        assert e["subject_key"] == "ROOF_TILES_REPORTED_AREA" and e["primary_subject_key"] == "ROOF_SLOPED_AREA"
        assert e["selectable"] is False and e["evidence"]["value"] == "1485.60"
        assert e["subject_relation"]["resolvable_as_same_quantity"] is False
        assert e["crosswalk_mapping_id"] == XQ  # context hangt aan de app-onderwerpmapping, niet aan XW-dak-hellend-4712
        assert e["evidence"]["evidence_refs"]["subject_mapping_ref"] == TILES_HSM
    assert len({e["evidence"]["source_cluster"] for e in ctx}) == 1
    # dak-plat ongewijzigd t.o.v. de referentiebundel
    ref = load(os.path.join(BUNDLES, "maldenhof_DOC-005_DOC-006_v3.json"))
    assert [e for e in bundle["entries"] if e["app_element_key"] == "dak-plat"] == ref["entries"]
    assert not any(e["crosswalk_mapping_id"] == "XW-dak-hellend-4712-m2" for e in bundle["entries"])
    assert not set(vab._walk_keys(bundle)) & vab.FORBIDDEN_KEYS
    assert load(vab.RESOLUTIONS)["records"] == []


def test_product_roles_never_primary(store, vocab):
    v = copy.deepcopy(vocab)
    for s in v["subjects"]:
        if s["subject_key"] == "ROOF_SLOPED_AREA":
            s["product_role"] = "INFRASTRUCTURE_ONLY"
    b = export(SCOPE, store, v)
    assert not any(e["subject_key"] == "ROOF_SLOPED_AREA" for e in b["entries"])
    errs = vab.validate(load(EXPANDED), expect_panden=15, subjects_vocab=v)
    assert any("mag geen PRIMARY zijn" in e for e in errs)


def _ctx(b):
    return by(b, "dak-hellend", "RELATED_CONTEXT")[0]


def test_validator_rejects_context_without_verified_subject_mapping(bundle, vocab):
    v = copy.deepcopy(vocab)
    v["historical_subject_mappings"] = [m for m in v["historical_subject_mappings"] if m["mapping_id"] != TILES_HSM]
    errs = vab.validate(bundle, expect_panden=15, subjects_vocab=v)
    assert any("onderwerp-mapping" in e for e in errs)


def test_validator_rejects_context_via_element_code(bundle):
    b = copy.deepcopy(bundle)
    _ctx(b)["crosswalk_mapping_id"] = "XW-dak-hellend-4712-m2"  # gedeelde elementcode is geen grond voor context
    errs = vab.validate(b, expect_panden=15)
    assert any("crosswalk_decision_id" in e or "app-element" in e for e in errs)


def test_validator_rejects_context_without_relation(bundle, vocab):
    v = copy.deepcopy(vocab)
    v["subject_relations"] = [r for r in v["subject_relations"] if "ROOF_TILES_REPORTED_AREA" not in r["subjects"]]
    errs = vab.validate(bundle, expect_panden=15, subjects_vocab=v)
    assert any("RELATED_NOT_EQUIVALENT-relatie" in e for e in errs)


@pytest.mark.parametrize("name,fn,needle", [
    ("tweede primary", lambda b: b["entries"].append(copy.deepcopy(by(b, "dak-hellend", "PRIMARY")[0])), "hoogstens één"),
    ("primary verkeerd onderwerp", lambda b: by(b, "dak-hellend", "PRIMARY")[0].update(crosswalk_mapping_id="XW-dak-plat-4711-m2",
                                                                                       crosswalk_decision_id="XWD-00001"),
     "app-element"),
    ("context kiesbaar", lambda b: _ctx(b).update(selectable=True), "selectable false"),
    ("context bij ander element", lambda b: _ctx(b).update(primary_subject_key="ROOF_FLAT_AREA"), "primary_subject_key"),
    ("context waarde", lambda b: _ctx(b)["evidence"].update(value="1415.57"), "wijkt af van canoniek"),
    ("resolutie", lambda b: b.update(resolved_value="1415.57"), "verboden sleutel"),
])
def test_validator_rejects_expanded_mutations(bundle, name, fn, needle):
    b = copy.deepcopy(bundle)
    fn(b)
    errs = vab.validate(b, expect_panden=15)
    assert errs and any(needle in e for e in errs), (name, errs)
