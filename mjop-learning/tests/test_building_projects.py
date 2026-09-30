"""Tests voor scripts/building_projects.py en de vastgelegde besluiten (Maldenhof goedgekeurd, Meppelweg unresolved).

De 'bewijs'-tests lezen de echte, vastgelegde stores en het echte candidate package (data/external/building_validation/
real_validation_v1). De weigerings-tests werken op een kopie in tmp_path; er wordt nooit in data/ geschreven."""
import copy
import json
import os
import shutil
import sys

import jsonschema
import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import append_only_store as aos  # noqa: E402
import building_projects as bp  # noqa: E402
import fetch_real_building_validation as frbv  # noqa: E402

MALDENHOF_PANDEN = [
    "0363100012070344", "0363100012071880", "0363100012078022", "0363100012091756", "0363100012091974",
    "0363100012102659", "0363100012107492", "0363100012121455", "0363100012127361", "0363100012134188",
    "0363100012137996", "0363100012140664", "0363100012141419", "0363100012143647", "0363100012144766"]
EVEN_NUMBERS = [str(n) for n in range(240, 297, 2)]
MEPPELWEG_PANDEN = ["0518100000208891", "0518100000277993", "0518100000354752", "0518100001631386"]
EXPECT = dict(pand_count=15, address_count=29, vbo_total=29, number_of_units=29, construction_year=1981,
              missing_addresses=0, panden_sharing_numbers_outside_scope=0)
KW = dict(hypothesis_id="EVEN_ONLY", reviewer_id="tester", reason="test", decided_at="2026-10-01T10:00:00Z", expect=EXPECT,
          decision_source="test")


def legacy_records():
    """Records van de legacy stores (bestaan alleen op branches met het legacy building_link/crosswalk-mechanisme)."""
    out = []
    for rel_path in ("data/building_links/building_link_records.json", "data/crosswalk_decisions/crosswalk_decision_records.json"):
        path = os.path.join(ROOT, rel_path)
        if os.path.exists(path):
            out += json.load(open(path, encoding="utf-8"))["records"]
    return out


def schema(name):
    return json.load(open(os.path.join(ROOT, "schemas", name), encoding="utf-8"))


@pytest.fixture(scope="module")
def stores():
    return (bp.load_store(bp.PROJECT_STORE, bp.new_project_store), bp.load_store(bp.UNRESOLVED_STORE, bp.new_unresolved_store))


@pytest.fixture()
def val(tmp_path):
    d = tmp_path / "val"
    shutil.copytree(bp.VALIDATION_DIR, d)
    return d


def active(store):
    return [r for r in store["records"] if r["status"] == "ACTIVE"]


# --- bewijs: Maldenhof is gekoppeld aan exact deze 15 panden --------------------------------------------------------

def test_maldenhof_project_links_exactly_the_15_pand_ids(stores):
    proj = active(stores[0])
    assert len(proj) == 1
    p = proj[0]
    assert p["building_project_id"] == "BPRJ-00001" and p["candidate_id"] == "BPC-DOC-005-006"
    assert p["document_ids"] == ["DOC-005", "DOC-006"] and p["project_status"] == "APPROVED"
    assert p["bag_pand_ids"] == MALDENHOF_PANDEN and p["bag_pand_count"] == 15
    assert [x["bag_pand_id"] for x in p["panden"]] == MALDENHOF_PANDEN
    assert sorted({a["bag_pand_id"] for a in p["addresses"]}) == MALDENHOF_PANDEN
    assert p["scope"]["hypothesis_id"] == "EVEN_ONLY" and p["scope"]["house_numbers"] == EVEN_NUMBERS
    assert sorted((a["house_number"] for a in p["addresses"]), key=int) == EVEN_NUMBERS
    assert len({a["nummeraanduiding_id"] for a in p["addresses"]}) == 29 == len({a["adresseerbaarobject_id"] for a in p["addresses"]})
    assert sum(x["aantal_verblijfsobjecten_bag"] for x in p["panden"]) == 29 == p["totals"]["vbo_total_bag"]
    assert sorted(len(x["house_numbers"]) for x in p["panden"]) == [1] + [2] * 14
    assert {x["bouwjaar_bag"] for x in p["panden"]} == {1981}
    assert p["totals"] == {"addresses": 29, "vbo_total_bag": 29, "bag_panden": 15, "mjop_number_of_units": 29}


def test_one_logical_project_no_single_pand_is_the_building(stores):
    p = active(stores[0])[0]
    assert "bag_pand_id" not in p and "pand_id" not in p and "primary_bag_pand_id" not in p
    assert "bag_pand_id" not in p["scope"]
    assert len(p["bag_pand_ids"]) > 1


def test_approval_decision_is_explicit_and_human(stores):
    a = active(stores[0])[0]["approval"]
    assert a["decision"] == "APPROVED" and a["scope_hypothesis_id"] == "EVEN_ONLY"
    assert a["reviewer"] == {"reviewer_id": "twandijkmans", "reviewer_type": "human"}
    assert a["decided_at"] and a["decision_reason"] and a["decision_source"]
    assert a["confirmed_facts"] == EXPECT


def test_provenance_points_to_candidate_package_and_still_matches_disk(stores):
    p = active(stores[0])[0]["provenance"]
    assert p["validation_dir"] == "data/external/building_validation/real_validation_v1"
    assert p["candidate_package"]["candidate_id"] == "BPC-DOC-005-006"
    assert p["candidate_package"]["path"].endswith("candidates/DOC-005-006.json") and p["manifest"]["path"].endswith("manifest.json")
    assert bp.provenance_errors() == []  # sha256 van package + manifest kloppen nog met de bestanden


def test_threedbag_stays_evidence_only(stores):
    p = active(stores[0])[0]
    assert p["evidence_policy"] == {"threedbag": "EVIDENCE_ONLY", "translated_to_quantities": False, "crosswalk_written": False,
                                    "legacy_building_link_store_written": False}
    for x in p["panden"]:
        ref = x["threedbag_evidence_ref"]
        assert ref["evidence_only"] is True and ref["raw_response_sha256"] and ref["http_status"] == 200
    text = json.dumps(p)
    assert "b3_opp_grond" not in text and "ground_area" not in text and "cost_per_m2" not in text  # geen 3D BAG-waarden in het project


def test_legal_vve_stays_open(stores):
    lv = active(stores[0])[0]["legal_vve"]
    assert lv["status"] == "OPEN" and lv["linked_legal_vve_id"] is None
    assert lv["identifiers_seen_are_not_legal"][0]["relation_id"] == "DREL-002"


def test_related_duplicate_document_is_noted_not_linked(stores):
    p = active(stores[0])[0]
    assert [d["document_id"] for d in p["related_documents_not_linked"]] == ["DOC-014"]
    assert "DOC-014" not in p["document_ids"]


# --- bewijs: DOC-012 blijft ongekoppeld ---------------------------------------------------------------------------------

def test_doc012_is_not_linked_anywhere(stores):
    for r in stores[0]["records"]:
        assert "DOC-012" not in r["document_ids"]
        assert not set(MEPPELWEG_PANDEN) & set(r["bag_pand_ids"])
    for r in legacy_records():
        text = json.dumps(r)
        assert "DOC-012" not in text and not any(pid in text for pid in MEPPELWEG_PANDEN)


def test_doc012_candidate_package_unchanged_and_unreviewed():
    d = bp.VALIDATION_DIR
    pkg = json.load(open(d / "candidates" / "DOC-012.json", encoding="utf-8"))
    assert pkg["status"] == "CANDIDATE_UNREVIEWED" and pkg["approval"]["building_link_approved"] is False
    b = pkg["building_project_candidate"]
    assert b["selected_scope"] is None and b["best_supported_hypothesis_id"] is None and b["canonical_building_project_written"] is False
    assert b["strength"] == "WEAK_BUILDING_PROJECT_CANDIDATE"


def test_doc012_unresolved_case_records_all_open_points(stores):
    cases = active(stores[1])
    assert len(cases) == 1
    c = cases[0]
    assert c["case_id"] == "UCASE-00001" and c["case_key"] == "DOC-012:BUILDING_PROJECT_SCOPE" and c["document_ids"] == ["DOC-012"]
    assert c["case_status"] == "REVIEW_REQUIRED" and c["candidate_status"] == "CANDIDATE_UNREVIEWED"
    assert c["selected_scope"] is None and c["building_project_linked"] is False and c["legal_vve_linked"] is False
    pts = {p["point_id"]: p for p in c["open_points"]}
    assert set(pts) == {"ADDRESS_MISSING_IN_BAG", "PAND_SPANS_BEYOND_RANGE", "MJOP_UNIT_COUNT_MISSING", "CONSTRUCTION_YEAR_MISMATCH", "OBJECT_NAME_CONFLICT"}
    assert pts["ADDRESS_MISSING_IN_BAG"]["evidence"]["number"] == "801"
    span = pts["PAND_SPANS_BEYOND_RANGE"]
    assert "0518100000354752" in span["statement"] and "803-883" in span["statement"] and "885" in span["statement"]
    assert span["evidence"]["vbo_outside_range"][0]["huisnummer"] == 885
    assert pts["CONSTRUCTION_YEAR_MISMATCH"]["evidence"] == {"mjop_construction_year": 1956, "bag_bouwjaar": [1957]}
    assert "801-883" in pts["OBJECT_NAME_CONFLICT"]["statement"] and "801-803" in pts["OBJECT_NAME_CONFLICT"]["statement"]
    assert c["decisions_needed"] and c["hypotheses"]["ODD_ONLY"]["strength"] == "WEAK_BUILDING_PROJECT_CANDIDATE"
    assert c["hypotheses"]["ODD_ONLY"]["addresses_missing"] == ["801"]


def test_stores_validate_against_schemas_and_invariants(stores):
    jsonschema.validate(stores[0], schema("building_project_record.schema.json"))
    jsonschema.validate(stores[1], schema("unresolved_case_record.schema.json"))
    assert bp.project_store_errors(stores[0]) == [] and bp.unresolved_store_errors(stores[1]) == []


def test_writes_only_under_data_building_projects():
    assert bp.PROJECT_STORE.parent == bp.UNRESOLVED_STORE.parent
    assert bp.PROJECT_STORE.parent.as_posix().endswith("data/building_projects")


# --- weigeringen (op een kopie) ---------------------------------------------------------------------------------------------

def approve(val, tmp_path, store=None, group="DOC-005-006", **over):
    kw = dict(KW, **over)
    return bp.approve_building_project(store or bp.new_project_store(), out_dir=val, group_id=group, root=tmp_path, **kw)


def test_approve_from_scratch_reproduces_the_stored_project(val, tmp_path, stores):
    new = approve(val, tmp_path)
    r = new["records"][0]
    stored = active(stores[0])[0]
    for k in ("bag_pand_ids", "panden", "addresses", "totals", "scope", "mjop_context", "candidate_id", "document_ids", "selected_scope"):
        assert r[k] == stored[k]
    assert r["legal_vve"]["status"] == "OPEN"


def test_approve_is_pure_and_reapproval_supersedes(val, tmp_path):
    s0 = bp.new_project_store()
    s1 = approve(val, tmp_path, s0)
    assert s0["records"] == []
    s2 = approve(val, tmp_path, s1, reason="opnieuw")
    assert [r["status"] for r in s2["records"]] == ["SUPERSEDED", "ACTIVE"] and s2["records"][1]["supersedes"] == "BPRJ-00001"
    assert bp.project_store_errors(s2) == []


def test_refuses_weak_candidate_doc012(val, tmp_path):
    with pytest.raises(bp.ProjectError, match="WEAK"):
        approve(val, tmp_path, group="DOC-012", hypothesis_id="ODD_ONLY", expect=dict(EXPECT, pand_count=1))


def test_refuses_non_strong_scope_for_maldenhof(val, tmp_path):
    with pytest.raises(bp.ProjectError, match="WEAK"):
        approve(val, tmp_path, hypothesis_id="ALL_NUMBERS")


@pytest.mark.parametrize("bad", [dict(pand_count=14), dict(address_count=28), dict(number_of_units=30), dict(construction_year=1982),
                                 dict(missing_addresses=1), dict(vbo_total=30)])
def test_refuses_when_confirmed_facts_differ(val, tmp_path, bad):
    with pytest.raises(bp.ProjectError, match="wijken af"):
        approve(val, tmp_path, expect=dict(EXPECT, **bad))


def test_refuses_incomplete_facts_and_missing_human(val, tmp_path):
    with pytest.raises(bp.ProjectError, match="ontbreken"):
        approve(val, tmp_path, expect={"pand_count": 15})
    with pytest.raises(bp.ProjectError, match="reviewer"):
        approve(val, tmp_path, reviewer_id=" ")
    with pytest.raises(bp.ProjectError, match="reden"):
        approve(val, tmp_path, reason="")


def test_refuses_tampered_or_prematurely_approved_package(val, tmp_path):
    path = val / "candidates" / "DOC-005-006.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    d["approval"]["building_link_approved"] = True
    path.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(bp.ProjectError, match="niet consistent"):
        approve(val, tmp_path)


def test_refuses_tampered_raw_response(val, tmp_path):
    raw = sorted((val / "raw" / "3dbag").iterdir())[0]
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(bp.ProjectError, match="niet consistent"):
        approve(val, tmp_path)


def test_refuses_pand_overlap_with_other_active_project(val, tmp_path, stores):
    other = copy.deepcopy(stores[0])
    other["records"][0]["candidate_id"] = "BPC-OTHER"
    with pytest.raises(bp.ProjectError, match="horen al bij"):
        approve(val, tmp_path, store=other)


def test_unresolved_refused_for_document_already_linked(val, tmp_path, stores):
    with pytest.raises(bp.ProjectError, match="al aan een building_project"):
        bp.record_unresolved_case(bp.new_unresolved_store(), out_dir=val, group_id="DOC-005-006", focus_hypothesis_id="EVEN_ONLY",
                                  recorded_by="x", reason="r", recorded_at="2026-10-01T10:00:00Z", decision_source="t",
                                  projects_store=stores[0], root=tmp_path)


def test_unresolved_records_no_project_and_no_scope(val, tmp_path):
    s = bp.record_unresolved_case(bp.new_unresolved_store(), out_dir=val, group_id="DOC-012", focus_hypothesis_id="ODD_ONLY",
                                  recorded_by="x", reason="r", recorded_at="2026-10-01T10:00:00Z", decision_source="t", root=tmp_path)
    assert s["records"][0]["selected_scope"] is None and s["records"][0]["building_project_linked"] is False
    s2 = bp.record_unresolved_case(s, out_dir=val, group_id="DOC-012", focus_hypothesis_id="ODD_ONLY", recorded_by="x", reason="r2",
                                   recorded_at="2026-10-02T10:00:00Z", decision_source="t", root=tmp_path)
    assert [r["status"] for r in s2["records"]] == ["SUPERSEDED", "ACTIVE"] and bp.unresolved_store_errors(s2) == []


# --- bescherming van vastgelegde provenance -------------------------------------------------------------------------------------

def test_validation_dir_is_locked_against_regeneration(tmp_path):
    assert bp.is_locked(bp.VALIDATION_DIR) is True
    assert bp.is_locked(bp.ROOT / "data" / "external" / "building_validation" / "real_validation_v2") is True  # BPEV-00001
    assert bp.is_locked(bp.ROOT / "data" / "external" / "building_validation" / "real_validation_v3") is False
    assert bp.is_locked(tmp_path) is False


def test_provenance_errors_detect_changed_package_and_raw_evidence(tmp_path):
    for sub in ("data/external/building_validation/real_validation_v1", "data/external/building_validation/real_validation_v2",
                "data/building_projects"):
        shutil.copytree(os.path.join(ROOT, sub), tmp_path / sub)
    kw = dict(root=tmp_path, project_path=tmp_path / "data/building_projects/building_project_records.json",
              unresolved_path=tmp_path / "data/building_projects/unresolved_case_records.json",
              support_path=tmp_path / "data/building_projects/supporting_evidence_records.json")
    assert bp.provenance_errors(**kw) == []
    raw = sorted((tmp_path / "data/external/building_validation/real_validation_v1/raw/3dbag").iterdir())[0]
    raw.write_bytes(raw.read_bytes() + b" ")
    assert any("sha256" in e for e in bp.provenance_errors(**kw))
    pkg = tmp_path / "data/external/building_validation/real_validation_v1/candidates/DOC-005-006.json"
    pkg.write_bytes(pkg.read_bytes() + b" ")
    assert any("candidate_package komt niet meer overeen" in e for e in bp.provenance_errors(**kw))


# --- DOC-005 + DOC-006 = hetzelfde logical building_project --------------------------------------------------------------

def test_doc005_and_doc006_refer_to_the_same_logical_project(stores):
    assert bp.project_for_document(stores[0], "DOC-005") == bp.project_for_document(stores[0], "DOC-006") == ["BPRJ-00001"]
    assert bp.project_for_document(stores[0], "DOC-012") == []
    assert active(stores[0])[0]["document_ids"] == ["DOC-005", "DOC-006"]


def test_no_legacy_links_written_for_the_approval(stores):
    text = json.dumps(legacy_records())
    assert not any(pid in text for pid in MALDENHOF_PANDEN + MEPPELWEG_PANDEN)
    assert "DOC-005" not in text and "DOC-006" not in text and "DOC-012" not in text
    assert bp.PROJECT_STORE.name == "building_project_records.json" and "building_links" not in str(bp.PROJECT_STORE)
    src = open(bp.__file__, encoding="utf-8").read()
    assert "import building_links" not in src and "import crosswalk" not in src  # geen compatibiliteitslaag
    assert active(stores[0])[0]["evidence_policy"]["legacy_building_link_store_written"] is False


# --- append-only + pinnen van de approval -----------------------------------------------------------------------------------

def test_approval_record_pins_the_decision(stores):
    r = active(stores[0])[0]
    assert r["building_project_id"] == "BPRJ-00001" and r["candidate_id"] == "BPC-DOC-005-006"
    assert r["document_ids"] == ["DOC-005", "DOC-006"] and r["selected_scope"] == "EVEN_ONLY" == r["approval"]["scope_hypothesis_id"]
    assert r["bag_pand_ids"] == MALDENHOF_PANDEN and r["project_status"] == "APPROVED" and r["approval"]["decision"] == "APPROVED"
    prov = r["provenance"]
    assert prov["validation_dir"].endswith("real_validation_v1") and prov["candidate_package"]["sha256"] and prov["manifest"]["sha256"]
    assert r["approval"]["reviewer"]["reviewer_type"] == "human" and r["approval"]["decision_source"]
    assert r["supersedes"] is None and r["status"] == "ACTIVE"


def test_bprj_00001_cannot_be_silently_overwritten(stores):
    old = stores[0]["records"]
    edited = copy.deepcopy(stores[0])
    edited["records"][0]["bag_pand_ids"] = MALDENHOF_PANDEN[:-1]
    assert any("overschreven" in e for e in aos.append_only_errors(old, edited["records"], "building_project_id"))
    removed = copy.deepcopy(stores[0])
    removed["records"] = []
    assert any("verwijderd" in e for e in aos.append_only_errors(old, removed["records"], "building_project_id"))
    scope = copy.deepcopy(stores[0])
    scope["records"][0]["selected_scope"] = "ALL_NUMBERS"
    assert any("overschreven" in e for e in aos.append_only_errors(old, scope["records"], "building_project_id"))


def test_write_store_refuses_overwrite_and_accepts_supersede(tmp_path, stores, val):
    path = tmp_path / "store.json"
    bp.write_store(stores[0], path, bp.new_project_store, bp.project_store_errors, "building_project_id")
    edited = copy.deepcopy(stores[0])
    edited["records"][0]["label"] = "stil gewijzigd"
    with pytest.raises(bp.ProjectError, match="overschreven"):
        bp.write_store(edited, path, bp.new_project_store, bp.project_store_errors, "building_project_id")
    new = approve(val, tmp_path, copy.deepcopy(stores[0]), reason="wijziging via nieuw record")
    bp.write_store(new, path, bp.new_project_store, bp.project_store_errors, "building_project_id")  # supersede is toegestaan
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [(r["building_project_id"], r["status"], r["supersedes"]) for r in saved["records"]] == [
        ("BPRJ-00001", "SUPERSEDED", None), ("BPRJ-00002", "ACTIVE", "BPRJ-00001")]
    assert {k: v for k, v in saved["records"][0].items() if k != "status"} == {k: v for k, v in stores[0]["records"][0].items() if k != "status"}


# --- immutable evidence: approved package niet overschrijven, nieuwe versiemap wel ------------------------------------------------

def test_guard_fails_hard_on_approved_dir_and_passes_on_new_version_dir(capsys):
    base = str(bp.ROOT / "data" / "external" / "building_validation") + "/"  # absoluut: onafhankelijk van de werkmap
    assert bp.main(["guard", "--out", base + "real_validation_v1"]) == 1
    assert "onveranderlijk" in capsys.readouterr().err
    assert bp.main(["guard", "--out", base + "real_validation_v2"]) == 1  # gerefereerd door BPEV-00001
    assert bp.main(["guard", "--out", base + "real_validation_v3"]) == 0


def test_fetch_script_itself_refuses_to_write_into_approved_dir(capsys):
    assert frbv.main(["--out", str(bp.VALIDATION_DIR)]) == 5  # absoluut pad: nooit per ongeluk een live fetch
    assert "onveranderlijk" in capsys.readouterr().err


def test_lock_follows_the_store_not_the_directory_name(tmp_path):
    empty = dict(project_store=bp.new_project_store(), support_store=bp.new_support_store())
    assert bp.locked_validation_dirs(**empty) == []
    assert bp.is_locked(bp.VALIDATION_DIR, **empty) is False
    assert bp.is_locked(bp.VALIDATION_DIR) is True


def test_new_versioned_directory_is_still_writable(tmp_path):
    """Nieuwe fetches naar een nieuwe versiemap blijven mogelijk (de bestaande run()-route, hier met vaste testantwoorden)."""
    v2 = tmp_path / "data" / "external" / "building_validation" / "real_validation_v2"
    group = {"group_id": "T-1", "document_ids": ["DOC-T"], "label": "t", "street": "Teststraat", "numbers": ["1"], "city": "Testdam"}

    def fake(url):
        body = {"response": {"docs": []}} if "locatieserver" in url else {}
        return {"status": 200, "body": json.dumps(body).encode(), "content_type": "application/json", "error": None}
    m = frbv.run([group], v2, http_get=fake, now=lambda: "2026-10-01T10:00:00Z", mjop_loader=lambda ids: [], sleep=lambda s: None)
    assert (v2 / "manifest.json").exists() and m["requests"]
    assert bp.is_locked(v2, root=tmp_path) is False


def test_workflow_guards_before_any_rm_rf_and_never_touches_approved_dir():
    wf = yaml.safe_load(open(os.path.join(ROOT, "..", ".github", "workflows", "real-building-validation.yml"), encoding="utf-8"))
    steps = wf["jobs"]["fetch"]["steps"]
    names = [s.get("name", s.get("uses")) for s in steps]
    guard = next(i for i, s in enumerate(steps) if "building_projects.py guard" in s.get("run", ""))
    rm = [i for i, s in enumerate(steps) if "rm -rf" in s.get("run", "")]
    assert len(rm) == 1 and guard < rm[0], names
    assert "steps.target.outputs.out_dir" in steps[rm[0]]["if"] and "steps.target.outputs.out_dir" in steps[guard]["if"]
    text = json.dumps(wf)
    assert "real_validation_v1" not in text  # de goedgekeurde map wordt nergens hard ingesteld
    assert "workflow_dispatch" in wf[True] and "out_dir" in wf[True]["workflow_dispatch"]["inputs"]
    doel = next(s for s in steps if s.get("id") == "target")["run"]
    assert "real_validation_v[0-9]" in doel and "*..*" in doel  # alleen versiemappen, geen path traversal
    assert any("building_projects.py check" in s.get("run", "") for s in steps)  # bewijs-integriteit bij elke run


# --- range discovery v2: BPRJ-00001 gereproduceerd als SUPPORTING_EVIDENCE (geen nieuwe approval) ----------------

V2 = os.path.join(ROOT, "data", "external", "building_validation", "real_validation_v2")
REPRO_KW = dict(building_project_id="BPRJ-00001", group_id="DOC-005-006", hypothesis_id="EVEN_ONLY", recorded_by="tester",
                recorded_at="2026-10-01T10:00:00Z", decision_source="test")


def project_store():
    return bp.load_store(bp.PROJECT_STORE, bp.new_project_store)


def test_committed_supporting_evidence_reproduces_bprj_00001_exactly():
    ss = bp.load_store(bp.SUPPORT_STORE, bp.new_support_store)
    jsonschema.validate(ss, json.load(open(os.path.join(ROOT, "schemas", "building_project_supporting_evidence_record.schema.json"))))
    assert bp.support_store_errors(ss) == []
    [r] = [x for x in ss["records"] if x["status"] == "ACTIVE"]
    assert (r["evidence_id"], r["building_project_id"], r["evidence_role"], r["result"]) == \
        ("BPEV-00001", "BPRJ-00001", "SUPPORTING_EVIDENCE", "REPRODUCES_APPROVED_SCOPE")
    assert r["approval_changed"] is False and r["new_approval_created"] is False and set(r["compared"].values()) == {True}
    assert r["provenance"]["validation_dir"] == "data/external/building_validation/real_validation_v2"
    [proj] = [p for p in project_store()["records"] if p["building_project_id"] == "BPRJ-00001"]
    assert r["project_record_sha256"] == bp._canonical_sha(proj)  # BPRJ-00001 is sindsdien niet gewijzigd
    assert proj["status"] == "ACTIVE" and proj["provenance"]["validation_dir"].endswith("real_validation_v1")
    assert len(project_store()["records"]) == 1  # geen nieuwe approval


def test_new_engine_even_only_equals_approved_panden_and_addresses():
    pkg = json.load(open(os.path.join(V2, "candidates", "DOC-005-006.json")))
    h = next(x for x in pkg["building_project_candidate"]["scope_hypotheses"] if x["hypothesis_id"] == "EVEN_ONLY")
    assert sorted(h["bag_pand_ids"]) == MALDENHOF_PANDEN and [a["number"] for a in h["addresses_found"]] == EVEN_NUMBERS
    [proj] = project_store()["records"]
    assert bp.reproduction_diff(proj, h)["differences"] == {}


def test_reproduction_refuses_on_any_difference():
    [proj] = project_store()["records"]
    tampered = copy.deepcopy(project_store())
    tampered["records"][0]["bag_pand_ids"] = MALDENHOF_PANDEN[:-1]
    tampered["records"][0]["addresses"] = proj["addresses"][:-1]
    with pytest.raises(bp.ProjectError, match="NIET exact"):
        bp.record_reproduction(bp.new_support_store(), project_store=tampered, out_dir=V2, **REPRO_KW)


def test_reproduction_is_pure_and_never_touches_the_project_store():
    before = copy.deepcopy(project_store())
    out = bp.record_reproduction(bp.new_support_store(), project_store=before, out_dir=V2, **REPRO_KW)
    assert before == project_store() and len(out["records"]) == 1 and out["records"][0]["result"] == "REPRODUCES_APPROVED_SCOPE"
    with pytest.raises(bp.ProjectError, match="al vastgelegd"):
        bp.record_reproduction(out, project_store=before, out_dir=V2, **REPRO_KW)


def test_reproduction_refuses_the_approval_package_itself_and_wrong_scope():
    with pytest.raises(bp.ProjectError, match="goedkeuring zelf"):
        bp.record_reproduction(bp.new_support_store(), project_store=project_store(), out_dir=bp.VALIDATION_DIR, **REPRO_KW)
    with pytest.raises(bp.ProjectError, match="scope"):
        bp.record_reproduction(bp.new_support_store(), project_store=project_store(), out_dir=V2, **dict(REPRO_KW, hypothesis_id="ALL_NUMBERS"))


def test_supporting_evidence_package_is_locked_too():
    assert bp.is_locked(V2) and bp.provenance_errors() == []


def test_discovery_reports_up_to_date_and_choose_nothing():
    import building_project_discovery_report as rep
    assert rep.main(["--check"]) == 0
    d = rep.build_discovery()
    cls = {g["group_id"]: g["classification"] for g in d["groups"]}
    assert all(c["selected_scope"] is None for c in cls.values())
    assert cls["DOC-005-006"]["candidate_class"] == "APPROVED_PROJECT" and cls["DOC-005-006"]["supporting_evidence_ids"] == ["BPEV-00001"]
    assert cls["DOC-012"]["unresolved_case_ids"] == ["UCASE-00001"]
    roof = rep.build_roof_review()
    assert roof["classification"] == "SCOPE_OR_DEFINITION_MISMATCH_REVIEW" and roof["corrections_applied"] is False
    assert [c["historical_m2"] for c in roof["comparisons"]] == ["425.80", "1485.60"]
    assert [c["threedbag_m2"] for c in roof["comparisons"]] == ["190.65", "1415.57"]
