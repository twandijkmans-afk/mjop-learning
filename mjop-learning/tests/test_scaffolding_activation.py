"""Tests voor Scaffolding Quantity Activation v1 (Outer Wall + Scaffolding Semantics v1).

Besluit van de gebruiker: XQ-steiger-OUTER_WALL_GROSS_AREA-m2 (app-element steiger -> OUTER_WALL_GROSS_AREA), VERIFY
pas nadat de kostenlogica per pand veilig was (MJOP-App Q.scaffoldPricing). BUILDING_HEIGHT blijft CONTEXT_ONLY en
komt alleen als prijscontext per pand in de bundel. Geen historische 2110-context, geen resolutie.
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
import scaffolding_height_review as shr  # noqa: E402
import validate_app_quantity_bundle as vab  # noqa: E402

BUNDLES = os.path.join(ROOT, "reports", "quantity", "app_bundles")
MALDENHOF_GEO = os.path.join(BUNDLES, "maldenhof_geometry_expanded_v3.json")
DOC012_GEO = os.path.join(BUNDLES, "doc012_geometry_v3.json")
XQ = "XQ-steiger-OUTER_WALL_GROSS_AREA-m2"
APPROVED = sorted("""0363100012137996 0363100012102659 0363100012078022 0363100012140664 0363100012141419 0363100012091974
0363100012070344 0363100012107492 0363100012071880 0363100012144766 0363100012091756 0363100012143647 0363100012121455
0363100012134188 0363100012127361""".split())
SCOPE = "BAG:" + "+".join(APPROVED)
DOC012 = "BAG:0518100000354752"
OLD_HASHES = {"maldenhof_DOC-005_DOC-006_v3.json": "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933",
              "doc012_meppelweg_v3.json": "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191",
              "maldenhof_expanded_v3.json": "c78f387e66ce7963d7a434270350f0ee8fa4c9f232099f871e83ed202cd2975d"}
REASON = ("Het app-element 'Steiger of hoogwerker' gebruikt bruto buitenmuuroppervlak als rekenoppervlak voor steiger/hoogwerker. "
          "Voor deze kostenbasis is OUTER_WALL_GROSS_AREA de bedoelde geometrische hoeveelheid. Dit besluit zegt niets over "
          "metselwerk, voegwerk of schilderwerk.")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def store():
    return load(bqe.OUT_EVIDENCE)


@pytest.fixture(scope="module")
def vocab():
    return load(xw.SUBJECTS)


def export(bid, evidence, vocab, app_elements=None, eff=None):
    return eab.build_bundle(bid, evidence, load(xw.APP_CROSSWALK), eff or xw.effective(), vocab, app_elements=app_elements)


def steiger(b):
    (e,) = [x for x in b["entries"] if x["app_element_key"] == "steiger"]
    return e


# --- besluit en vocabulaire --------------------------------------------------------------
def test_xq_steiger_mapping_verified_by_user():
    m = {x["mapping_id"]: x for x in load(xw.APP_CROSSWALK)["mappings"]}[XQ]
    assert (m["mapping_kind"], m["internal_element_code"], m["app_element_key"], m["unit"], m["quantity_subject"]) == \
        ("APP_QUANTITY_SUBJECT", None, "steiger", "m2", "OUTER_WALL_GROSS_AREA")
    assert m["pricing_context"]["context_subject"] == "BUILDING_HEIGHT" and m["pricing_context"]["per_pand"] is True
    eff = xw.effective()[XQ]
    assert (eff["status"], eff["decision_id"]) == ("VERIFIED", "XWD-00006")
    (rec,) = [r for r in load(xw.DECISIONS)["records"] if r["mapping_id"] == XQ]
    assert rec["decision"] == "VERIFY" and rec["decision_reason"] == REASON
    assert rec["reviewer"] == {"reviewer_id": "user-approved", "reviewer_type": "human"}
    assert rec["proposal_sha256"] == xw.canonical_sha256(xw.load_proposals()[XQ])


def test_building_height_stays_context_only(vocab, store):
    roles = {s["subject_key"]: s.get("product_role") for s in vocab["subjects"]}
    assert roles["BUILDING_HEIGHT"] == "CONTEXT_ONLY"
    for p in (MALDENHOF_GEO, DOC012_GEO):
        b = load(p)
        assert all(e["subject_key"] != "BUILDING_HEIGHT" for e in b["entries"])        # nooit een bundelregel
        assert all(e.get("selectable") is not True or e["subject_key"] != "BUILDING_HEIGHT" for e in b["entries"])
        pc = steiger(b)["pricing_context"]
        assert (pc["context_subject_key"], pc["context_product_role"], pc["selectable"]) == ("BUILDING_HEIGHT", "CONTEXT_ONLY", False)
    # een mapping die BUILDING_HEIGHT als PRIMARY zou leveren wordt door export en validator geweigerd
    cw = load(xw.APP_CROSSWALK)
    fake = dict({x["mapping_id"]: x for x in cw["mappings"]}[XQ], mapping_id="XQ-test-height", quantity_subject="BUILDING_HEIGHT", unit="m")
    del fake["pricing_context"]
    cw["mappings"].append(fake)
    eff = dict(xw.effective(), **{"XQ-test-height": {"status": "VERIFIED", "human_verified": True, "decision_id": "XWD-T"}})
    b = eab.build_bundle(DOC012, store["evidence"], cw, eff, vocab)
    assert all(e["subject_key"] != "BUILDING_HEIGHT" for e in b["entries"])


def test_no_historical_2110_context():
    eff = xw.effective()
    assert not [k for k, v in eff.items() if "2110" in k and v["status"] == "VERIFIED"]
    assert not [m for m in load(xw.SUBJECTS)["historical_subject_mappings"] if m.get("element_code_internal") == "2110"]
    for p in (MALDENHOF_GEO, DOC012_GEO):
        b = load(p)
        assert not [e for e in b["entries"] if e["app_element_key"] in ("gevel-metselwerk", "voegwerk", "schilderwerk-buiten")]
        assert steiger(b).get("role") == "PRIMARY"
        assert not [e for e in b["entries"] if e.get("role") == "RELATED_CONTEXT" and e.get("primary_subject_key") == "OUTER_WALL_GROSS_AREA"]
        assert "evidence" in steiger(b) and steiger(b)["evidence"]["source_type"] == "3D_BAG"


# --- evidence ------------------------------------------------------------------------------
def test_outer_wall_evidence_per_pand_and_exact_scope_sum(store):
    ev = store["evidence"]
    per = {e["building_id"]: e for e in ev if e["quantity_subject"]["subject_key"] == "OUTER_WALL_GROSS_AREA"}
    assert all(f"BAG:{p}" in per for p in APPROVED) and DOC012 in per
    agg = per[SCOPE]
    kids = agg["calculation"]["input_evidence_ids"]
    by_id = {e["evidence_id"]: e for e in ev}
    assert sorted(by_id[k]["source_ref"]["bag_pand_id"] for k in kids) == APPROVED
    assert sum(Decimal(by_id[k]["value"]) for k in kids) == Decimal(agg["value"]) == Decimal("1747.35")
    assert per[DOC012]["value"] == "3048.46"


def test_height_context_per_pand_matches_canonical(store):
    by_id = {e["evidence_id"]: e for e in store["evidence"]}
    for p, panden in ((MALDENHOF_GEO, APPROVED), (DOC012_GEO, ["0518100000354752"])):
        e = steiger(load(p))
        rows = e["pricing_context"]["rows"]
        assert sorted(r["bag_pand_id"] for r in rows) == panden
        for r in rows:
            h = by_id[r["context_evidence_id"]]
            assert r["status"] == "AVAILABLE" and h["quantity_subject"]["subject_key"] == "BUILDING_HEIGHT"
            assert (r["value"], r["unit"], h["building_id"]) == (h["value"], "m", f"BAG:{r['bag_pand_id']}")
        comps = e["evidence"].get("components") or []
        if comps:
            assert sorted((c["bag_pand_id"], c["evidence_id"]) for c in comps) == sorted((r["bag_pand_id"], r["quantity_evidence_id"]) for r in rows)
        else:
            assert rows[0]["quantity_evidence_id"] == e["evidence"]["evidence_id"]


def test_missing_child_height_is_missing_not_zero(store, vocab):
    ev = copy.deepcopy(store["evidence"])
    gone = "0363100012127361"
    ev = [e for e in ev if not (e["building_id"] == f"BAG:{gone}" and e["quantity_subject"]["subject_key"] == "BUILDING_HEIGHT")]
    e = steiger(export(SCOPE, ev, vocab))
    (r,) = [x for x in e["pricing_context"]["rows"] if x["bag_pand_id"] == gone]
    assert (r["status"], r["value"], r["context_evidence_id"]) == ("MISSING", None, None)
    assert all(x["status"] == "AVAILABLE" for x in e["pricing_context"]["rows"] if x["bag_pand_id"] != gone)
    # de validator weigert een 0 (of een verzonnen hoogte) voor een ontbrekend pand
    b = load(MALDENHOF_GEO)
    for row in steiger(b)["pricing_context"]["rows"]:
        if row["bag_pand_id"] == gone:
            row.update(status="MISSING", value="0", context_evidence_id=None)
    assert any("MISSING moet waarde null" in x for x in vab.validate(b, expect_panden=15))


# --- review --------------------------------------------------------------------------------
def test_height_review_up_to_date_and_findings():
    r = shr.build()
    assert open(shr.OUT_JSON, encoding="utf-8").read() == json.dumps(r, ensure_ascii=False, indent=1) + "\n"
    assert open(shr.OUT_MD, encoding="utf-8").read() == shr.render(r)
    mald, d12 = r["buildings"]
    assert (mald["kind"], mald["pand_count"], mald["outer_wall_total_m2"]) == ("MULTI_PAND_SCOPE", 15, "1747.35")
    assert mald["sum_of_pand_walls_equals_scope_total"] and mald["panden_missing_height"] == []
    assert mald["panden_per_tariff_band"] == {"> 8 m": 15} and mald["single_tariff_band"] is True
    assert (mald["cost_A_scope_total_x_plan_pand_rate_eur"], mald["cost_B_per_pand_sum_eur"], mald["A_equals_B"]) == ([19221], 19221, True)
    assert min(x["app_work_height_m"] for x in mald["rows"]) == 9 and max(x["app_work_height_m"] for x in mald["rows"]) == 12
    assert (d12["kind"], d12["outer_wall_total_m2"], d12["rows"][0]["app_work_height_m"], d12["cost_B_per_pand_sum_eur"]) == \
        ("SINGLE_PAND", "3048.46", 20, 33533)
    assert r["state"]["xq_steiger_status"] == "VERIFIED" and r["state"]["quantity_resolutions"] == 0
    assert all(v["unchanged"] for v in r["state"]["reference_bundles"].values())


def test_review_rate_replication_matches_app_rule():
    assert [shr.work_height(h) for h in ("9.444", "8.46", "8.44", "19.555")] == [9, 9, 8, 20]
    assert [shr.rate(w) for w in (8, 9)] == [Decimal(6), Decimal(11)]
    assert shr.work_height(None) is None and shr.rate(None) is None


# --- bundels -------------------------------------------------------------------------------
def test_old_bundle_hashes_stable(store, vocab):
    for name, h in OLD_HASHES.items():
        assert sha(os.path.join(BUNDLES, name)) == h
    assert sha(os.path.join(BUNDLES, "maldenhof_DOC-005_DOC-006_v3.json")) == \
        hashlib.sha256(vab.bundle_bytes(export(SCOPE, store["evidence"], vocab, {"dak-plat"}))).hexdigest()
    assert sha(os.path.join(BUNDLES, "doc012_meppelweg_v3.json")) == \
        hashlib.sha256(vab.bundle_bytes(export(DOC012, store["evidence"], vocab, {"dak-plat"}))).hexdigest()
    assert sha(os.path.join(BUNDLES, "maldenhof_expanded_v3.json")) == \
        hashlib.sha256(vab.bundle_bytes(export(SCOPE, store["evidence"], vocab, {"dak-plat", "dak-hellend"}))).hexdigest()


@pytest.mark.parametrize("path,bid,n", [(MALDENHOF_GEO, SCOPE, 15), (DOC012_GEO, DOC012, 1)])
def test_geometry_bundles_deterministic_and_valid(store, vocab, path, bid, n):
    raw = open(path, "rb").read()
    assert vab.bundle_bytes(export(bid, store["evidence"], vocab)) == raw
    assert vab.validate(load(path), expect_panden=n) == []
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "validate_app_quantity_bundle.py"), path,
                        "--expect-panden", str(n), "--check-export"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "GELDIG" in r.stdout, r.stdout + r.stderr


def test_maldenhof_geometry_bundle_contents():
    b = load(MALDENHOF_GEO)
    assert sorted({e["app_element_key"] for e in b["entries"]}) == ["dak-hellend", "dak-plat", "steiger"]
    e = steiger(b)
    assert (e["subject_key"], e["selectable"], e["crosswalk_decision_id"], e["evidence"]["value"]) == \
        ("OUTER_WALL_GROSS_AREA", True, "XWD-00006", "1747.35")
    assert len(e["evidence"]["components"]) == 15
    # dak-plat en dak-hellend zijn gelijk aan de eerdere uitgebreide bundel
    old = load(os.path.join(BUNDLES, "maldenhof_expanded_v3.json"))
    assert [x for x in b["entries"] if x["app_element_key"] != "steiger"] == old["entries"]


def test_no_resolution():
    assert load(vab.RESOLUTIONS)["records"] == []
    for p in (MALDENHOF_GEO, DOC012_GEO):
        assert not set(vab._walk_keys(load(p))) & vab.FORBIDDEN_KEYS


def _pc(b):
    return steiger(b)["pricing_context"]


@pytest.mark.parametrize("name,fn,needle", [
    ("context weg", lambda b: steiger(b).pop("pricing_context"), "pricing_context ontbreekt"),
    ("hoogte aangepast", lambda b: _pc(b)["rows"][0].update(value="7.9"), "wijkt af van canoniek"),
    ("pand weg", lambda b: _pc(b)["rows"].pop(), "dekt niet precies"),
    ("pand extra", lambda b: _pc(b)["rows"].append(dict(_pc(b)["rows"][0])), "dekt niet precies"),
    ("verkeerde evidence", lambda b: _pc(b)["rows"][0].update(context_evidence_id=_pc(b)["rows"][1]["context_evidence_id"]), "hoort niet bij"),
    ("verzonnen missing", lambda b: _pc(b)["rows"][0].update(status="MISSING", value=None, context_evidence_id=None), "terwijl BUILDING_HEIGHT-evidence bestaat"),
    ("kiesbaar", lambda b: _pc(b).update(selectable=True), "CONTEXT_ONLY en niet kiesbaar"),
    ("ander onderwerp", lambda b: _pc(b).update(context_subject_key="ROOF_TOTAL_AREA"), "past niet bij de app-mapping"),
    ("context op dak-plat", lambda b: [x for x in b["entries"] if x["app_element_key"] == "dak-plat" and x["role"] == "PRIMARY"][0]
        .update(pricing_context=copy.deepcopy(_pc(b))), "zonder declaratie"),
])
def test_validator_rejects_pricing_context_mutations(name, fn, needle):
    b = copy.deepcopy(load(MALDENHOF_GEO))
    fn(b)
    errs = vab.validate(b, expect_panden=15)
    assert errs and any(needle in e for e in errs), (name, errs)


def test_unverified_steiger_mapping_gives_no_steiger_entry(store, vocab):
    eff = dict(xw.effective())
    eff[XQ] = {"status": "PROPOSED", "human_verified": False, "decision_id": None}
    b = export(SCOPE, store["evidence"], vocab, eff=eff)
    assert not [e for e in b["entries"] if e["app_element_key"] == "steiger"]
