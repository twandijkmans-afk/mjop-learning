import copy
import hashlib
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import physical_instance_approval as P  # noqa: E402
import physical_instance_approval_report as PR  # noqa: E402

CTX = P.load_context()
CTX["soc_groups"] = P.load_soc_groups()
BASE = P.build_request(CTX, "OIC-VR-027")
REP = json.loads(P.OUT_JSON.read_text(encoding="utf-8"))
OBS = ("OBS-MAP003-011", "OBS-MAP004-006")


def ctx_copy(**kw):
    c = copy.deepcopy(CTX)
    c.update(kw)
    return c


def req_copy():
    return copy.deepcopy(BASE)


def rehash(r):
    r["request_hash"] = P.request_hash(r)
    return r


def ev(req=None, ctx=None):
    return P.evaluate_request(ctx or CTX, req if req is not None else req_copy())


def not_ready(r):
    return r["approval_status"] in ("NEEDS_MORE_EVIDENCE", "REJECTED")


def failed(r):
    return [c["id"] for c in r["validation_results"]["checks"] if c["result"] != "PASS"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- positief en vorm
def test_oic_vr027_gets_one_draft_request_ready_for_review_but_not_approved():
    r = ev()
    assert r["approval_request_id"] == "IAR-OIC-VR-027" and r["approval_status"] == "READY_FOR_HUMAN_REVIEW"
    assert r["validation_results"]["technical_verdict"] == "SUITABLE_FOR_HUMAN_REVIEW" and r["human_decision"] is None
    assert r["is_instance"] is False and r["frame_instance_id"] is None and r["reserved_instance_id"] is None
    assert r["decision_levels"]["A"]["status"] == "NOT_DECIDED" and r["decision_levels"]["B"]["bag_pand_id"] is None
    assert r["decision_levels"]["C"]["quantity"] is None and r["decision_levels"]["C"]["cost"] is None
    for f in P.REQUIRED_FIELDS:
        assert f in r
    assert r["observation_ids"] == list(OBS) and r["supporting_relation_ids"] == ["VR-027"]
    assert r["decision_provenance"]["instance_decision"] is None


def test_committed_report_has_exactly_one_ready_request_and_no_approval():
    assert REP["draft_request"]["approval_status"] == "READY_FOR_HUMAN_REVIEW" and REP["draft_request"]["human_decision"] is None
    e = REP["effects"]
    assert e["instances_created"] == e["instance_ids_reserved"] == e["bag_links_created"] == e["merges"] == e["approved_requests"] == 0
    assert e["instance_store_written"] is False and e["building_totals"] is None and e["quantities"] is None and e["costs"] is None
    assert e["human_decisions_created"] == e["app_decisions_changed"] == e["pilot_decisions_changed"] == 0 and e["photo2_changed"] is False
    assert not P.FI_PATTERN.search(json.dumps(REP["draft_request"]))


def test_uncertainties_are_carried_over_not_converted():
    r0 = ev()
    q = " ".join(r0["unresolved_questions"] + r0["derived_open_questions"])
    for needle in ("MEDIUM", "dezelfde dag", "tijdelijk", "identieke woningen", "pand", "instance-besluit", "VR-045", "APP-012"):
        assert needle in q, needle
    assert ev()["required_human_decisions"]


def test_related_app_decisions_documented_all_48_open_and_unchanged():
    assert len(CTX["app_decisions"]) == 48 and all(a["status"] == "OPEN" for a in CTX["app_decisions"].values())
    rel = {r["app_id"]: r for r in ev()["validation_results"]["related_app_decisions"]}
    assert rel["APP-012"]["relevance"] == "DIRECT" and rel["APP-025"]["relevance"] == "DIRECT"
    assert rel["APP-002"]["kind"] == "PLATE_AND_PAND_LINK_LEVEL_B" and all(r["status"] == "OPEN" for r in rel.values())


# ---------------------------------------------------------------- de 15 negatieve tests
def test_01_oic_does_not_exist():
    c = ctx_copy()
    del c["oic_registry"]["OIC-VR-027"]
    r = ev(ctx=c)
    assert r["approval_status"] == "REJECTED" and "C1" in r["validation_results"]["blocked_by"]
    r = req_copy()
    r["candidate_group_id"] = "OIC-VR-999"
    r["supporting_relation_ids"] = ["VR-999"]
    r = ev(rehash(r))
    assert r["approval_status"] == "REJECTED" and "C1" in r["validation_results"]["blocked_by"]
    with pytest.raises(ValueError):
        P.build_request(CTX, "OIC-VR-999") if False else P.build_request(CTX, "OIC-VR-999")


def test_02_oic_lacks_required_status():
    r = req_copy()
    r["candidate_status"] = "CANDIDATE"
    out = ev(rehash(r))
    assert out["approval_status"] == "NEEDS_MORE_EVIDENCE" and "C2" in failed(out)
    c = ctx_copy()
    c["decisions"]["RV-REL-VR-027"]["decision"] = "UNDECIDABLE"      # het live verband zakt naar UNRESOLVED terwijl het register SUPPORTED zegt
    out = ev(ctx=c)
    assert not_ready(out) and "C2" in failed(out)
    c = ctx_copy()
    c["oic_registry"]["OIC-VR-027"]["identity_status"] = "CANDIDATE"
    assert not_ready(ev(ctx=c))
    for rid in ("VR-020", "VR-022", "VR-024", "VR-026"):
        with pytest.raises(ValueError):
            P.build_request(CTX, "OIC-" + rid)


def test_03_source_hash_changed():
    r = req_copy()
    r["source_hashes"]["MAP-003"] = "0" * 64
    out = ev(rehash(r))
    assert out["approval_status"] == "REJECTED" and "C3a" in out["validation_results"]["blocked_by"]
    c = ctx_copy()
    c["archive_sha"]["MAP-004"] = "f" * 64
    assert ev(ctx=c)["approval_status"] == "REJECTED"
    c = ctx_copy()
    c["observations"]["OBS-MAP003-011"]["source_sha256"] = "a" * 64
    assert ev(ctx=c)["approval_status"] == "REJECTED"
    r = req_copy()
    r["evidence_refs"][0]["sha256"] = "b" * 64
    out = ev(rehash(r))
    assert out["approval_status"] == "REJECTED" and "C4" in failed(out)


def test_04_human_candidate_decision_missing():
    c = ctx_copy()
    del c["decisions"]["RV-REL-VR-027"]
    assert not_ready(ev(ctx=c))
    r = req_copy()
    r["decision_provenance"]["candidate_decision"] = []
    out = ev(rehash(r))
    assert not_ready(out) and "C6" in failed(out)


def test_05_human_provenance_invalid():
    for bad in ("CLAUDE_PROPOSAL", "AI", None, ""):
        c = ctx_copy()
        c["decisions"]["RV-REL-VR-027"]["provenance"]["decision_source"] = bad
        assert not_ready(ev(ctx=c)), bad
    c = ctx_copy()
    c["decisions"]["RV-REL-VR-027"]["source_ref_hash_validated"] = False
    assert not_ready(ev(ctx=c))
    r = req_copy()
    r["decision_provenance"]["candidate_decision"][0]["source_ref_hash"] = "deadbeef"
    assert not_ready(ev(r))


@pytest.mark.parametrize("decision,expected", [("DIFFERENT", "REJECTED"), ("UNDECIDABLE", "NEEDS_MORE_EVIDENCE")])
def test_06_contradicting_decision_is_not_ignored(decision, expected):
    c = ctx_copy()
    c["relations"]["VR-XTRA"] = {"rel_id": "VR-XTRA", "left": "MAP-003:OBS-MAP003-011", "right": "MAP-009:REF-MAP009-001", "class": "POSSIBLY_SAME_PHYSICAL_FRAME",
                                 "strength": "LOW", "merged": False, "confirmed": False}
    c["decisions"]["RV-REL-VR-XTRA"] = {"review_id": "RV-REL-VR-XTRA", "decision": decision}
    out = ev(ctx=c)
    assert out["approval_status"] == expected and "C8" in failed(out)


def test_06b_grouped_endpoint_is_found_not_missed():
    c = ctx_copy()
    c["relations"]["VR-GRP"] = {"rel_id": "VR-GRP", "left": "MAP-003:OBS-MAP003-010/011/012", "right": "MAP-009:REF-MAP009-009", "class": "POSSIBLY_SAME_PHYSICAL_FRAME",
                                "strength": "LOW", "merged": False, "confirmed": False}
    c["decisions"]["RV-REL-VR-GRP"] = {"review_id": "RV-REL-VR-GRP", "decision": "DIFFERENT"}
    assert ev(ctx=c)["approval_status"] == "REJECTED"


def test_07_conflict_with_existing_instance():
    for mut in ("photo", "obs", "oic"):
        c = ctx_copy()
        inst = copy.deepcopy(c["instance_store"]["instances"][0])
        inst["frame_instance_id"] = "FI-M2-099"
        if mut == "photo":
            inst["source_refs"][0]["photo_id"] = "MAP-003"
        elif mut == "obs":
            inst["source_refs"].append({"ref_type": "NOTE", "observation_id": "OBS-MAP004-006"})
        else:
            inst["source_refs"].append({"ref_type": "NOTE", "candidate": "OIC-VR-027"})
        c["instance_store"]["instances"].append(inst)
        out = ev(ctx=c)
        assert out["approval_status"] == "REJECTED" and "C9" in out["validation_results"]["blocked_by"], mut


def test_07b_relation_tying_observation_to_frozen_photo2_blocks():
    c = ctx_copy()
    c["relations"]["VR-F2"] = {"rel_id": "VR-F2", "left": "MAP-003:OBS-MAP003-011", "right": "MAP-002:FC-M2-001", "class": "POSSIBLY_SAME_PHYSICAL_FRAME",
                               "strength": "LOW", "merged": False, "confirmed": False}
    assert ev(ctx=c)["approval_status"] == "REJECTED"


def test_08_two_candidates_claim_overlapping_observations():
    c = ctx_copy()
    other = copy.deepcopy(c["oic_registry"]["OIC-VR-027"])
    other.update(candidate_group_id="OIC-VR-500", observation_ids=["OBS-MAP004-006", "OBS-MAP009-001"])
    c["oic_registry"]["OIC-VR-500"] = other
    assert ev(ctx=c)["approval_status"] == "REJECTED"
    second = rehash({**req_copy(), "approval_request_id": "IAR-OIC-VR-501"})
    out = P.process_batch(CTX, [req_copy(), second])
    assert [o["approval_status"] for o in out] == ["REJECTED", "REJECTED"]


def test_09_identical_neighbour_homes_are_not_presented_as_same_object():
    for rid in ("VR-022", "VR-044", "VR-025"):       # te donker / groepseindpunt met herhaling / alleen gelijke indeling
        with pytest.raises(ValueError):
            P.build_request(CTX, "OIC-" + rid)
    r = req_copy()
    r["observation_ids"] = ["OBS-MAP003-011", "OBS-MAP004-007"]                  # buurraam in plaats van het echte partnerraam
    out = ev(rehash(r))
    assert out["approval_status"] == "REJECTED" and "C3a" in out["validation_results"]["blocked_by"]
    c = ctx_copy()
    c["quality"]["RV-REL-VR-027"]["evidence_basis"] = ["REPETITION_RISK", "SAME_LAYOUT"]
    assert not_ready(ev(ctx=c))


def test_10_facade_section_relation_is_not_physical_identity():
    c = ctx_copy()
    c["relations"]["VR-027"]["class"] = "SAME_FACADE_SECTION"
    assert ev(ctx=c)["approval_status"] == "REJECTED"
    c = ctx_copy()
    c["pack"]["RV-REL-VR-027"]["relation_semantics"]["relation_type"] = "FACADE_SECTION"
    assert ev(ctx=c)["approval_status"] == "REJECTED"
    with pytest.raises(ValueError):
        P.build_request(CTX, "OIC-VR-020")


@pytest.mark.parametrize("where", ["levels_b", "top", "human_record"])
def test_11_automatic_bag_link_is_refused(where):
    if where == "human_record":
        rec = _valid_record()
        rec["bag_pand_id"] = "0363100012121455"
        ok, why = P.verify_human_approval(_ctx_with(rec), _ready(), rec)
        assert not ok and any(("NIVEAU_B_OF_C" in w) or ("ONBEKENDE_VELDEN" in w) for w in why)
        return
    r = req_copy()
    if where == "levels_b":
        r["decision_levels"]["B"]["bag_pand_id"] = "0363100012121455"
    else:
        r["bag_pand_id"] = "0363100012121455"
    assert ev(rehash(r))["approval_status"] == "REJECTED"


@pytest.mark.parametrize("where,key", [("levels_c", "cost"), ("levels_c", "quantity"), ("levels_c", "dimensions"), ("top", "building_total"), ("top", "unique_total"), ("top", "cost"), ("human_record", "m2")])
def test_12_unique_total_or_maintenance_cost_change_is_refused(where, key):
    if where == "human_record":
        rec = _valid_record()
        rec[key] = 1
        assert not P.verify_human_approval(_ctx_with(rec), _ready(), rec)[0]
        return
    r = req_copy()
    if where == "levels_c":
        r["decision_levels"]["C"][key] = 12
    else:
        r[key] = 12
    assert ev(rehash(r))["approval_status"] == "REJECTED"


def _ready():
    return ev()


def _valid_record(req=None):
    req = req or _ready()
    return {"decision_id": "IAD-TEST-001", "request_id": req["approval_request_id"], "request_hash": req["request_hash"], "decision": "APPROVE_PHYSICAL_IDENTITY",
            "level": "A", "covers_levels": ["A"], "decided_by": "Test Beslisser", "decision_source": "HUMAN", "statement": "Synthetische testverklaring van een mens.",
            "acknowledged_app_decisions": ["APP-012", "APP-025"], "acknowledged_open_relations": ["VR-045"]}


def _ctx_with(rec):
    return ctx_copy(human_approvals=[copy.deepcopy(rec)])


def test_13_forged_approval_cannot_reach_approved_for_activation():
    for forged in (lambda r: r.update(approval_status="APPROVED_FOR_ACTIVATION"),
                   lambda r: r.update(human_decision={"decision": "APPROVE_PHYSICAL_IDENTITY"}),
                   lambda r: r["decision_levels"]["A"].update(status="APPROVED", decided_by_human=True),
                   lambda r: r.update(approval_status="READY_FOR_HUMAN_REVIEW")):
        r = req_copy()
        forged(r)
        out = ev(r)
        assert out["approval_status"] != "APPROVED_FOR_ACTIVATION"
        if r.get("human_decision") or r["approval_status"] != "DRAFT" or r["decision_levels"]["A"]["status"] != "NOT_DECIDED":
            assert out["approval_status"] == "REJECTED"
    ready = _ready()
    assert ready["approval_status"] == "READY_FOR_HUMAN_REVIEW"
    rec = _valid_record(ready)
    # zonder registratie, met verkeerde inhoud of van een niet-mens: geweigerd
    assert P.transition(CTX, ready, "APPROVED_FOR_ACTIVATION", rec)["ok"] is False
    assert P.transition(CTX, ready, "APPROVED_FOR_ACTIVATION", None)["ok"] is False
    bads = [dict(rec, request_hash="0" * 32), dict(rec, request_id="IAR-OIC-VR-999"), dict(rec, decided_by="Claude"), dict(rec, decided_by="AI assistent"), dict(rec, decision_source="CLAUDE_PROPOSAL"),
            dict(rec, level="B"), dict(rec, covers_levels=["A", "B"]), dict(rec, statement=""), dict(rec, acknowledged_app_decisions=[]), dict(rec, decision="REJECT"), dict(rec, decision="MAYBE")]
    for b in bads:
        assert P.transition(_ctx_with(b), ready, "APPROVED_FOR_ACTIVATION", b)["ok"] is False, b
    # niet-registratie van een anders geldig record
    assert P.transition(ctx_copy(human_approvals=[dict(rec, statement="andere tekst die niet is geregistreerd")]), ready, "APPROVED_FOR_ACTIVATION", rec)["ok"] is False
    # toegestane overgangen alleen volgens de machine
    for cur, bad in (("DRAFT", "APPROVED_FOR_ACTIVATION"), ("NEEDS_MORE_EVIDENCE", "APPROVED_FOR_ACTIVATION"), ("REJECTED", "READY_FOR_HUMAN_REVIEW"), ("REJECTED", "APPROVED_FOR_ACTIVATION")):
        assert P.transition(_ctx_with(rec), {**ready, "approval_status": cur}, bad, rec)["ok"] is False
    # positieve controle: alleen een volledig, geregistreerd menselijk record werkt, en het resultaat is nog steeds geen instance
    good = P.transition(_ctx_with(rec), ready, "APPROVED_FOR_ACTIVATION", rec)
    assert good["ok"] is True and good["request"]["approval_status"] == "APPROVED_FOR_ACTIVATION"
    assert good["request"]["is_instance"] is False and good["request"]["activation_performed"] is False and good["request"]["frame_instance_id"] is None
    # een geldig besluit op gewijzigd bewijs vervalt
    changed = rehash({**copy.deepcopy(ready), "source_hashes": {**ready["source_hashes"]}})
    c = _ctx_with(rec)
    c["archive_sha"]["MAP-003"] = "9" * 64
    assert P.transition(c, ready, "APPROVED_FOR_ACTIVATION", rec)["ok"] is False and changed


def test_13b_ready_is_only_reachable_through_validation():
    r = req_copy()
    out = P.transition(CTX, r, "READY_FOR_HUMAN_REVIEW")
    assert out["ok"] and out["request"]["approval_status"] == "READY_FOR_HUMAN_REVIEW"
    c = ctx_copy()
    del c["oic_registry"]["OIC-VR-027"]
    assert P.transition(c, r, "READY_FOR_HUMAN_REVIEW")["ok"] is False


def test_14_missing_or_corrupt_data_never_approves_and_never_raises():
    rng = random.Random(43)
    junk = [None, "", "x", 0, 1, -1, [], {}, [None], {"a": 1}, True, False, "FI-M2-001", 3.5, ["OBS-MAP003-011"], "0" * 64]
    cases = 0
    for f in P.REQUIRED_FIELDS + ["photo_ids", "evidence_refs", "is_instance", "frame_instance_id", "relation_strength_in_source", "evidence_class", "reserved_instance_id", "superseded_request_hashes"]:
        for j in junk:
            r = req_copy()
            r[f] = j
            out = ev(r)
            cases += 1
            if f == "validation_results" or P.canonical(j) == P.canonical(BASE.get(f)):    # uitvoerveld, of ongewijzigde waarde
                continue
            assert out["approval_status"] in ("NEEDS_MORE_EVIDENCE", "REJECTED"), (f, j, out["approval_status"])
            assert out["approval_status"] != "APPROVED_FOR_ACTIVATION" and out["is_instance"] is False
        r = req_copy()
        del r[f]
        if f in P.REQUIRED_FIELDS:
            assert ev(r)["approval_status"] == "REJECTED"
    for bad in (None, [], "x", 5, {}, {"approval_request_id": "IAR-X"}):
        assert P.evaluate_request(CTX, bad)["approval_status"] == "REJECTED"
    keys = list(CTX)
    for _ in range(200):
        c = copy.deepcopy(CTX)
        k = rng.choice(keys)
        c[k] = rng.choice(junk + [{}, []])
        out = ev(ctx=c)
        assert out["approval_status"] != "APPROVED_FOR_ACTIVATION"
        cases += 1
    assert cases > 300


def test_14b_missing_instance_store_or_app_table_fails_closed():
    assert ev(ctx=ctx_copy(app_decisions={}))["approval_status"] == "REJECTED"
    c = ctx_copy(app_decisions={k: v for k, v in list(CTX["app_decisions"].items())[:47]})
    assert ev(ctx=c)["approval_status"] == "REJECTED"
    assert not_ready(ev(ctx=ctx_copy(instance_store=None, oic_registry=None)))


def test_15_repeated_processing_is_idempotent_and_does_not_duplicate():
    a, b = ev(), ev()
    assert P.canonical(a) == P.canonical(b)
    once, twice = P.process_batch(CTX, [req_copy()]), P.process_batch(CTX, [req_copy(), req_copy()])
    assert len(once) == len(twice) == 1 and P.canonical(once) == P.canonical(twice)
    assert P.canonical(P.process_batch(CTX, [req_copy()])) == P.canonical(once)
    resubmitted = P.process_batch(CTX, once)          # een reeds beoordeelde aanvraag met status terugsturen is een niet-verifieerbare statusclaim
    assert resubmitted[0]["approval_status"] == "REJECTED" and len(resubmitted) == 1
    clash = req_copy()
    clash["proposed_instance_type"] = {**clash["proposed_instance_type"], "subtype": "OTHER"}
    out = P.process_batch(CTX, [req_copy(), rehash(clash)])
    assert [o["approval_status"] for o in out] == ["REJECTED", "REJECTED"]


# ---------------------------------------------------------------- niveaus, statusmachine, id-regels
def test_levels_are_separate_and_a_never_implies_b_or_c():
    assert set(P.LEVELS) == {"A", "B", "C"}
    rec = _valid_record()
    assert rec["covers_levels"] == ["A"]
    good = P.transition(_ctx_with(rec), _ready(), "APPROVED_FOR_ACTIVATION", rec)["request"]
    assert good["decision_levels"]["B"]["status"] == "NOT_DECIDED" and good["decision_levels"]["B"]["bag_pand_id"] is None
    assert good["decision_levels"]["C"]["cost"] is None and good["decision_levels"]["C"]["quantity"] is None


def test_status_machine_is_closed_and_has_no_activation_state():
    assert set(P.TRANSITIONS) == set(P.STATUSES) == {"DRAFT", "READY_FOR_HUMAN_REVIEW", "NEEDS_MORE_EVIDENCE", "APPROVED_FOR_ACTIVATION", "REJECTED"}
    assert P.TRANSITIONS["REJECTED"] == []
    sources_of_approved = [s for s, t in P.TRANSITIONS.items() if "APPROVED_FOR_ACTIVATION" in t]
    assert sources_of_approved == ["READY_FOR_HUMAN_REVIEW"]
    assert not any("ACTIVAT" in s and s != "APPROVED_FOR_ACTIVATION" for s in P.STATUSES)
    assert "READY_FOR_HUMAN_REVIEW" in P.STATUS_MEANING and "TECHNISCH GESCHIKT" in P.STATUS_MEANING["READY_FOR_HUMAN_REVIEW"]


def test_request_id_never_collides_with_instance_ids_and_fi_ids_are_blocked():
    ids = {i["frame_instance_id"] for i in CTX["instance_store"]["instances"]} | {s["instance"]["frame_instance_id"] for s in CTX["instance_store"]["superseded_instances"]}
    assert BASE["approval_request_id"].startswith("IAR-") and BASE["approval_request_id"] not in ids
    for key in ("reserved_instance_id", "frame_instance_id"):
        r = req_copy()
        r[key] = "FI-M3-001"
        assert ev(rehash(r))["approval_status"] == "REJECTED"
    r = req_copy()
    r["unresolved_questions"].append("gebruik FI-M3-001 voor dit kozijn")
    assert ev(rehash(r))["approval_status"] == "REJECTED"


def test_forbidden_effects_cannot_be_removed_or_allowed():
    r = req_copy()
    r["forbidden_effects"] = [e for e in r["forbidden_effects"] if e != "link_bag_pand"]
    assert ev(rehash(r))["approval_status"] == "REJECTED"
    r = req_copy()
    r["allowed_effects"].append("write_instance_store")
    assert ev(rehash(r))["approval_status"] == "REJECTED"


# ---------------------------------------------------------------- geen schrijfpad, determinisme, bevroren data
def test_module_has_no_write_path_to_instance_store_or_protected_data():
    src = (ROOT / "scripts/physical_instance_approval.py").read_text(encoding="utf-8")
    assert src.count(".write_text(") == 3 and "OUT_JSON.write_text" in src and "OUT_MD.write_text" in src and "PACK_HTML.write_text" in src
    for bad in ("build_frame_instance_activation", "append_only_store", "INSTANCE_STORE.write", "open(", "shutil", "os.remove", "unlink", ".replace(\"FI-"):
        assert bad not in src, bad
    assert "f\"FI-" not in src and "'FI-M" not in src and "\"FI-M" not in src


PROTECTED = [ROOT / "data" / "frame_inventory", ROOT / "data" / "photo_evidence", ROOT / "data" / "building_links", ROOT / "data" / "bag_snapshots", ROOT / "data" / "quantity_resolutions",
             ROOT / "reports/frames/photo_review_map003_map004_v1/pilot_decisions", ROOT / "reports/frames/photo_archive_audit_v1",
             ROOT / "reports/frames/physical_object_identity_pilot_v1.json", ROOT / "reports/frames/photo_review_map003_map004_v1/maldenhof_visual_photo_review_map003_map004_v1.json"]


def snapshot():
    out = {}
    for p in PROTECTED:
        for f in ([p] if p.is_file() else sorted(p.rglob("*")) if p.exists() else []):
            if f.is_file():
                out[str(f)] = sha(f)
    return out


def test_regeneration_is_deterministic_and_changes_no_protected_file():
    before = snapshot()
    rep = P.build_report()
    rep2 = P.build_report()
    assert P.canonical(rep) == P.canonical(rep2)
    assert json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True) + "\n" == P.OUT_JSON.read_text(encoding="utf-8")
    assert PR.render_md(rep) == P.OUT_MD.read_text(encoding="utf-8")
    assert PR.render_pack(rep) == P.PACK_HTML.read_text(encoding="utf-8")
    assert snapshot() == before and len(before) > 25
    assert sha(ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json") == "b18c36eb4c21abcb25bb9ff2162fcfd06a164b3f9e490aa11af858ef33b02378"
    approval_md = P.APP_APPROVAL_MD.read_text(encoding="utf-8")
    assert approval_md.count("| OPEN |") >= 48


def test_existing_oic_functionality_unchanged_by_this_framework():
    import object_identity_pilot as OI
    assert OI.build_report() == json.loads(OI.OUT_JSON.read_text(encoding="utf-8"))
    assert REP["draft_request"]["candidate_status"] == "SUPPORTED_CANDIDATE"


def test_review_pack_is_static_escaped_and_not_an_approval():
    html = P.PACK_HTML.read_text(encoding="utf-8")
    assert "<form" not in html and "<script" not in html and "<input" not in html
    assert "geen goedkeuring en geen instance" in html and "niet ingevuld, niet geregistreerd en zonder werking" in html
    assert html.count("data:image/jpeg;base64,") == 5
    rep = copy.deepcopy(REP)
    rep["draft_request"]["derived_open_questions"].append("<script>alert(1)</script>")
    out = PR.render_pack(rep)
    assert "<script>alert" not in out and "&lt;script&gt;" in out


def test_report_distinguishes_validated_manual_and_pending_and_documents_uncertainty():
    md = P.OUT_MD.read_text(encoding="utf-8")
    for k in REP["fact_classes"]:
        assert k in md
    for needle in ("VR-045", "tegenstrijdige beoordeling van MAP-009", "STOP", "Ontbrekend vóór deze PR", "APPROVE_PHYSICAL_IDENTITY"):
        assert needle in md, needle
    assert REP["later_activation_phase_proposal"] and REP["forbidden_effects"] == P.FORBIDDEN_EFFECTS


# ---------------------------------------------------------------- eindcontrole PR #43: aanvullende regressietests
def test_every_hashed_claim_field_is_checked_against_a_fresh_live_build_even_when_rehashed():
    for mutate in (lambda r: r["additional_evidence"][0]["arguments"].append("extra sterke claim"),
                   lambda r: r["proposed_instance_type"].update(material="WOOD"),
                   lambda r: r["proposed_instance_type"].update(component_type="DOOR"),
                   lambda r: r["evidence_refs"][0].update(region_px=[0, 0, 5, 5]),
                   lambda r: r["decision_provenance"].update(note="aangepast"),
                   lambda r: r["decision_provenance"]["candidate_decision"][0].update(approval_channel="HTML-formulier"),
                   lambda r: r.update(relation_strength_in_source="HIGH"), lambda r: r.update(evidence_class="MODERATE_VISUAL_SUPPORT"),
                   lambda r: r.update(photo_ids=["MAP-003", "MAP-009"])):
        r = req_copy()
        mutate(r)
        out = ev(rehash(r))                                  # ook met opnieuw berekende hash: afwijking van de live opbouw blokkeert
        assert out["approval_status"] == "REJECTED" and "C3a" in out["validation_results"]["blocked_by"]
        r2 = req_copy()
        mutate(r2)
        assert ev(r2)["approval_status"] == "REJECTED"        # zonder nieuwe hash faalt de hashcontrole


def test_request_hash_is_deterministic_bound_to_content_and_never_an_approval():
    h = BASE["request_hash"]
    assert h == P.request_hash(BASE) == P.request_hash(copy.deepcopy(BASE)) and len(h) == 32 and h not in P.SUPERSEDED_HASHES
    assert P.SUPERSEDED_HASHES == ["aa556297be5d6713d298a06fa40492b8", "34c61b5e5f274764e86491a838502ede"]
    for f in ("observation_ids", "evidence_refs", "unresolved_questions", "additional_evidence", "decision_provenance", "evidence_reconciliation", "proposed_instance_type", "photo_ids"):
        r = req_copy()
        r[f] = copy.deepcopy(r[f]) if f != "photo_ids" else ["X"]
        if isinstance(r[f], list):
            r[f].append("x")
        elif isinstance(r[f], dict):
            r[f]["zz"] = 1
        assert P.request_hash(r) != h, f
    out = ev()
    assert out["request_hash"] == h and out["human_decision"] is None and out["approval_status"] == "READY_FOR_HUMAN_REVIEW"     # de hash alleen is geen goedkeuring


def test_human_record_schema_is_closed_and_must_acknowledge_open_relations_and_app_questions():
    ready = ev()
    rec = _valid_record(ready)
    assert P.verify_human_approval(_ctx_with(rec), ready, rec) == (True, [])
    assert ready["validation_results"]["open_related_relations"] == ["VR-045"]
    for bad in (dict(rec, creates_instance=True), dict(rec, activate=True), dict(rec, bag_pand="x"), {k: v for k, v in rec.items() if k != "acknowledged_open_relations"},
                dict(rec, acknowledged_open_relations=[]), dict(rec, acknowledged_app_decisions=["APP-012"])):
        ok, why = P.verify_human_approval(_ctx_with(bad), ready, bad)
        assert ok is False and why, bad


def test_verify_never_trusts_a_caller_supplied_validation_result():
    ready = ev()
    rec = _valid_record(ready)
    forged = copy.deepcopy(ready)
    forged["validation_results"]["related_app_decisions"] = []
    forged["validation_results"]["open_related_relations"] = []
    bad = dict(rec, acknowledged_app_decisions=[], acknowledged_open_relations=[])
    assert P.verify_human_approval(_ctx_with(bad), forged, bad)[0] is False
    # een niet meer technisch geschikte aanvraag kan niet worden goedgekeurd, ook niet met een geldig record
    c = _ctx_with(rec)
    c["archive_sha"]["MAP-003"] = "9" * 64
    assert P.verify_human_approval(c, ready, rec)[0] is False


def test_status_machine_matches_the_code_for_every_pair():
    ready = ev()
    rec = _valid_record(ready)
    ctx = _ctx_with(rec)
    for cur in P.STATUSES:
        for target in P.STATUSES:
            r = {**ready, "approval_status": cur}
            out = P.transition(ctx, r, target, rec if target == "APPROVED_FOR_ACTIVATION" else None)
            allowed = target in P.TRANSITIONS[cur]
            if not allowed:
                assert out["ok"] is False, (cur, target)
            elif out["ok"]:
                assert out["request"]["approval_status"] == target and out["request"]["is_instance"] is False
            if target == "APPROVED_FOR_ACTIVATION" and out["ok"]:
                assert cur == "READY_FOR_HUMAN_REVIEW"
            if cur == "REJECTED":
                assert out["ok"] is False
    # evaluate_request levert alleen overgangen die vanuit DRAFT toegestaan zijn
    for case in (ev(), ev(ctx=ctx_copy(reconciliation={}))):
        assert case["approval_status"] in P.TRANSITIONS["DRAFT"]


def test_feature_match_alone_is_never_identity_evidence():
    c = ctx_copy()
    c["quality"]["RV-REL-VR-027"]["evidence_basis"] = ["FEATURE_MATCH"]            # alleen feature-match, geen anker
    out = ev(ctx=c)
    assert out["approval_status"] != "READY_FOR_HUMAN_REVIEW" and {"C2", "C7"} & set(failed(out))      # zonder anker vervalt zelfs het SUPPORTED-OIC
    c = ctx_copy()
    for k in c["feature"]["VR-027"]:
        if "inliers" in k or k == "good_matches":
            c["feature"]["VR-027"][k] = 999
    assert ev(ctx=c)["approval_status"] in ("READY_FOR_HUMAN_REVIEW", "NEEDS_MORE_EVIDENCE", "REJECTED")
    c2 = ctx_copy()
    c2["quality"]["RV-REL-VR-027"]["evidence_basis"] = ["FEATURE_MATCH", "SAME_LAYOUT"]
    assert ev(ctx=c2)["approval_status"] != "READY_FOR_HUMAN_REVIEW"


def test_fi_ids_are_scanned_everywhere_in_the_request():
    for key in ("request_note", "kind", "extra_field"):
        r = req_copy()
        r[key] = "FI-M3-777"
        assert ev(rehash(r))["approval_status"] == "REJECTED", key
    assert not any(P.FI_PATTERN.search(s) for s in P._walk_strings(BASE))
    assert "FI-M" not in P.OUT_JSON.read_text(encoding="utf-8").replace("FI-M2-nnn", "")


REGISTER_SCRIPTS = {"human_instance_decision_register.py", "human_instance_decision_register_report.py"}   # PR #44: het besluitenregister hergebruikt het framework bewust


def test_no_other_script_imports_or_drives_the_approval_framework():
    for f in (ROOT / "scripts").glob("*.py"):
        if f.name in REGISTER_SCRIPTS:
            continue
        if f.name.startswith(("physical_instance_", "object_identity_")) or f.name == "doc012_generalization_review.py":    # laatste: alleen de lijst REPORT_ONLY_SCRIPTS
            continue
        txt = f.read_text(encoding="utf-8")
        assert "physical_instance_approval" not in txt and "physical_instance_evidence_reconciliation" not in txt, f.name
