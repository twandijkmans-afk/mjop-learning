"""
Tests voor scripts/mjop_plan.py - domeinmodel voor een versie van een nieuw MJOP
(docs/mjop_plan_v1.md). Regels zijn echte Maintenance Lines (v1, ongewijzigd) met
C1/C2-workflowresultaten; beslissingen alleen in het geheugen.
"""
import copy
import hashlib
import os
import sys
from decimal import Decimal

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import human_match_review as h  # noqa: E402
import match_kengetal as m  # noqa: E402
import mjop_maintenance_line as L  # noqa: E402
import mjop_plan as P  # noqa: E402
import promotion_history as ph  # noqa: E402

# Na de canonieke promotie van batch1_v1 is C1 (4645) geen canoniek kengetal meer. Deze workflowtests
# gebruiken de pre-promotie-kengetallen (C1/C2) uit data/history als vaste, alleen-lezen fixture.
FIXTURE_ROOT = ph.pre_promotion_fixture_root(PROJECT_ROOT)
HP = h.paths(FIXTURE_ROOT)
DECISION_SCHEMA, MATCH_SCHEMA = h.load_json(HP["schema"]), h.load_json(HP["match_schema"])
KENGETALLEN, EMPTY = h.load_json(HP["kengetallen"]), h.load_json(HP["store"])
CTX = m.load_context(FIXTURE_ROOT)
T0, T1, T2, T3 = ("2026-09-24T10:00:00Z", "2026-09-24T11:00:00Z", "2026-09-24T12:00:00Z", "2026-09-24T13:00:00Z")
MJOP = "MJOP-TEST"


def c1_line(line_id="ML-1", **over):
    base = dict(element_code_internal="4645", action_normalized="exterior_painting", unit_normalized="m2",
                material_normalized="concrete", material_source="user",
                object_description="Buitenschilderwerk betonconstructie plafond", quantity="80", vat_basis="inclusive",
                planned_year=2028)
    base.update(over)
    return L.new_line(line_id, MJOP, "OBJ-1", **base)


def c2_line(line_id="ML-2", **over):
    base = dict(element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", material_source="user", object_description="Hemelwaterafvoer pvc",
                quantity="100", vat_basis="inclusive", planned_year=2030)
    base.update(over)
    return L.new_line(line_id, MJOP, "OBJ-2", **base)


def decided(line, decision="ACCEPT", **kw):
    _, result = L.run_workflow_for_line(line, EMPTY, CTX, root=PROJECT_ROOT)
    store, _ = h.add_decision(EMPTY, result["match_result"], decision, "twandijkmans", "reden",
                              schema=DECISION_SCHEMA, match_schema=MATCH_SCHEMA, kengetallen_doc=KENGETALLEN,
                              reviewed_at=T0, **kw)
    return L.run_workflow_for_line(line, store, CTX, root=PROJECT_ROOT)[0]


def manual_line(line_id="ML-3", amount="20", unit="m1", vat="exclusive", **over):
    base = dict(unit_normalized=unit, quantity="10", planned_year=2031, vat_basis=vat,
                action_normalized="replace", element_code_internal="3141")
    base.update(over)
    return L.set_manual_amount(L.new_line(line_id, MJOP, "OBJ-3", **base), amount, unit, "2026", vat, "offerte")


def draft(line_ids=("ML-1", "ML-2"), start=2026, end=2040):
    v = P.new_plan(MJOP, "BLD-1", at=T0, by="twandijkmans", name="Testcomplex")
    if start is not None:
        v = P.set_horizon(v, start, end, at=T0)
    return P.set_line_ids(v, list(line_ids), at=T0)


def ready(lines, **kw):
    v = P.submit_for_review(draft([l["maintenance_line_id"] for l in lines], **kw), lines, at=T1, by="twandijkmans")
    return P.approve(v, lines, at=T2, by="twandijkmans", reason="gecontroleerd")[0]


@pytest.fixture(scope="module")
def lines():
    return [decided(c1_line()), decided(c2_line())]


# --------------------------------------------------------------------------
# 1. Aanmaken en metadata
# --------------------------------------------------------------------------

def test_new_plan_is_valid_draft():
    v = P.new_plan(MJOP, "BLD-1", at=T0, by="twandijkmans", name="Complex", construction_year=1975, number_of_units=24)
    assert (v["version_id"], v["version_number"], v["plan_status"]) == ("MJOP-TEST-V001", 1, "DRAFT")
    assert v["supersedes_version_id"] is None and v["metadata_source"] == "USER_ENTERED"
    assert [e["event"] for e in v["status_history"]] == ["CREATED"] and P.plan_errors(v) == []
    assert v["line_hashes"] is v["content_sha256"] is v["knowledge_basis"] is v["readiness_warnings"] is None


def test_building_id_required_and_not_pattern_checked():
    with pytest.raises(P.PlanError):
        P.new_plan(MJOP, "", at=T0)
    # historische document-ID-achtige waarde wordt niet geweigerd (geen regex/prefixcontrole)
    assert P.new_plan(MJOP, "DOC-002-BLD-001", at=T0)["building_id"] == "DOC-002-BLD-001"


def test_metadata_unknown_or_derived_fields_refused():
    with pytest.raises(P.PlanError):
        P.new_plan(MJOP, "BLD-1", at=T0, plan_status="READY")
    with pytest.raises(P.PlanError):
        P.update_plan_metadata(draft(), at=T1, content_sha256="0" * 64)


@pytest.mark.parametrize("field,value", [("construction_year", 99), ("number_of_units", 0), ("renovation_year", "1990")])
def test_invalid_metadata_fails(field, value):
    with pytest.raises(P.PlanError):
        P.update_plan_metadata(draft(), at=T1, **{field: value})


def test_draft_edit_only_updates_updated_at():
    v = P.update_plan_metadata(draft(), at=T1, address="Straat 1")
    assert (v["address"], v["created_at"], v["updated_at"]) == ("Straat 1", T0, T1)
    assert len(v["status_history"]) == 1


# --------------------------------------------------------------------------
# 2. Horizon en regel-IDs
# --------------------------------------------------------------------------

def test_horizon_free_length_but_start_not_after_end():
    assert P.set_horizon(draft(start=None), 2026, 2026, at=T1)["plan_end_year"] == 2026
    assert P.set_horizon(draft(start=None), 2026, 2075, at=T1)["plan_end_year"] == 2075
    with pytest.raises(P.PlanError):
        P.set_horizon(draft(start=None), 2040, 2030, at=T1)


def test_line_ids_unique():
    with pytest.raises(P.PlanError):
        P.set_line_ids(draft(), ["ML-1", "ML-1"], at=T1)


# --------------------------------------------------------------------------
# 3. Indienen
# --------------------------------------------------------------------------

def test_submit_captures_line_hashes(lines):
    v = P.submit_for_review(draft(), lines, at=T1, by="twandijkmans")
    assert v["plan_status"] == "IN_REVIEW" and v["status_history"][-1]["event"] == "SUBMITTED_FOR_REVIEW"
    assert v["line_hashes"] == {l["maintenance_line_id"]: h.canonical_sha256(l) for l in lines}
    assert v["content_sha256"] is None


def test_submit_requires_horizon(lines):
    with pytest.raises(P.PlanError, match="horizon"):
        P.submit_for_review(draft(start=None), lines, at=T1, by="twandijkmans")


@pytest.mark.parametrize("variant", ["missing", "extra", "other_mjop", "duplicate"])
def test_submit_requires_exact_line_set_of_same_mjop(lines, variant):
    ls = {"missing": lines[:1], "extra": lines + [manual_line()],
          "other_mjop": [lines[0], L.new_line("ML-2", "MJOP-OTHER", "OBJ-2")],
          "duplicate": lines + [lines[0]]}[variant]
    with pytest.raises(P.PlanError):
        P.submit_for_review(draft(), ls, at=T1, by="twandijkmans")


def test_submit_refuses_invalid_line(lines):
    broken = copy.deepcopy(lines[1])
    broken["financial"]["effective_total"] = "1"
    with pytest.raises(P.PlanError):
        P.submit_for_review(draft(), [lines[0], broken], at=T1, by="twandijkmans")


def test_return_to_draft_requires_reason_and_clears_hashes(lines):
    v = P.submit_for_review(draft(), lines, at=T1, by="twandijkmans")
    with pytest.raises(P.PlanError):
        P.return_to_draft(v, at=T2, by="twandijkmans", reason="")
    d = P.return_to_draft(v, at=T2, by="twandijkmans", reason="regel ontbreekt")
    assert d["plan_status"] == "DRAFT" and d["line_hashes"] is None
    assert [e["event"] for e in d["status_history"]] == ["CREATED", "SUBMITTED_FOR_REVIEW", "RETURNED_TO_DRAFT"]


# --------------------------------------------------------------------------
# 4. Goedkeuren (READY)
# --------------------------------------------------------------------------

def test_approve_requires_human_and_reason(lines):
    v = P.submit_for_review(draft(), lines, at=T1, by="twandijkmans")
    for by, reason in ((None, "ok"), ("twandijkmans", None), ("", "ok")):
        with pytest.raises(P.PlanError):
            P.approve(v, lines, at=T2, by=by, reason=reason)


def test_approve_sets_ready_fields(lines):
    r = ready(lines)
    assert r["plan_status"] == "READY" and r["status_history"][-1]["event"] == "APPROVED"
    assert r["content_sha256"] == P.content_sha256(r) and P.plan_errors(r, lines) == []
    assert r["readiness_warnings"] == {"no_amount": 0, "rejected": 0, "amount_without_total": 0,
                                       "outside_horizon": 0, "without_planned_year": 0}


def test_only_in_review_can_be_approved(lines):
    with pytest.raises(P.PlanError):
        P.approve(draft(), lines, at=T2, by="twandijkmans", reason="ok")


def test_review_required_line_blocks_ready():
    line, _ = L.run_workflow_for_line(c1_line(vat_basis="exclusive"), EMPTY, CTX, root=PROJECT_ROOT)
    assert line["line_status"] == "REVIEW_REQUIRED"
    v = P.submit_for_review(draft(["ML-1"]), [line], at=T1, by="twandijkmans")   # indienen mag
    with pytest.raises(P.PlanError, match="REVIEW_REQUIRED"):
        P.approve(v, [line], at=T2, by="twandijkmans", reason="ok")


def test_ready_allowed_with_warnings():
    no_amount = c1_line("ML-1", quantity=None, action_normalized="interior_painting")
    rejected = decided(c2_line(), "REJECT")
    outside = manual_line("ML-3", planned_year=2050)
    no_year = manual_line("ML-4", planned_year=None)
    ls = [no_amount, rejected, outside, no_year]
    r = ready(ls)
    assert r["readiness_warnings"] == {"no_amount": 1, "rejected": 1, "amount_without_total": 0,
                                       "outside_horizon": 1, "without_planned_year": 1}


def test_line_changed_after_submit_blocks_approve(lines):
    v = P.submit_for_review(draft(), lines, at=T1, by="twandijkmans")
    changed = L.update_user_fields(lines[1], planned_year=2032)
    with pytest.raises(P.PlanError, match="line_hash"):
        P.approve(v, [lines[0], changed], at=T2, by="twandijkmans", reason="ok")


# --------------------------------------------------------------------------
# 5. Immutability en integriteit
# --------------------------------------------------------------------------

def test_ready_version_cannot_be_edited(lines):
    r = ready(lines)
    for call in (lambda: P.update_plan_metadata(r, at=T3, name="x"), lambda: P.set_horizon(r, 2026, 2030, at=T3),
                 lambda: P.set_line_ids(r, ["ML-1"], at=T3),
                 lambda: P.submit_for_review(r, lines, at=T3, by="twandijkmans"),
                 lambda: P.return_to_draft(r, at=T3, by="twandijkmans", reason="x")):
        with pytest.raises(P.PlanError):
            call()


@pytest.mark.parametrize("field,value", [("name", "anders"), ("plan_end_year", 2041), ("building_id", "BLD-2"),
                                         ("maintenance_line_ids", ["ML-1"])])
def test_tampered_ready_version_detected(lines, field, value):
    r = copy.deepcopy(ready(lines))
    r[field] = value
    assert P.plan_errors(r) != []


def test_line_drift_after_ready_detected(lines):
    r = ready(lines)
    changed = L.update_user_fields(lines[0], quantity="81")
    assert any("line_hash" in e for e in P.plan_errors(r, [changed, lines[1]]))
    assert P.plan_errors(r, lines) == []


def test_content_hash_excludes_status_history_and_timestamps(lines):
    r = ready(lines)
    moved = copy.deepcopy(r)
    moved["updated_at"], moved["plan_status"] = T3, "SUPERSEDED"
    moved["status_history"].append(P.event("SUPERSEDED", T3, "twandijkmans", "x"))
    assert P.content_sha256(moved) == r["content_sha256"]


def test_status_history_must_match_status(lines):
    r = copy.deepcopy(ready(lines))
    r["status_history"].pop()
    assert any("laatste gebeurtenis" in e for e in P.plan_errors(r))


# --------------------------------------------------------------------------
# 6. Versies en opvolging
# --------------------------------------------------------------------------

def test_next_draft_and_supersede(lines):
    r1 = ready(lines)
    d2 = P.create_next_draft(r1, at=T3, by="twandijkmans")
    assert (d2["version_id"], d2["version_number"], d2["supersedes_version_id"]) == ("MJOP-TEST-V002", 2, r1["version_id"])
    assert d2["maintenance_line_ids"] == r1["maintenance_line_ids"] and d2["plan_status"] == "DRAFT"
    new_line = manual_line("ML-3")
    d2 = P.set_line_ids(d2, ["ML-1", "ML-2", "ML-3"], at=T3)
    v2 = P.submit_for_review(d2, lines + [new_line], at=T3, by="twandijkmans")
    with pytest.raises(P.PlanError):
        P.approve(v2, lines + [new_line], at=T3, by="twandijkmans", reason="ok")          # opvolging ontbreekt
    r2, old = P.approve(v2, lines + [new_line], at=T3, by="twandijkmans", reason="ok", previous_ready=r1)
    assert r2["plan_status"] == "READY" and old["plan_status"] == "SUPERSEDED"
    assert old["content_sha256"] == r1["content_sha256"] and P.plan_errors(old, lines) == []
    assert r1["plan_status"] == "READY"                                                     # invoer niet gemuteerd
    assert P.versions_errors([old, r2]) == []
    # ongewijzigde regels worden door beide versies gebruikt en blijven voor beide geldig
    assert old["line_hashes"] == {k: r2["line_hashes"][k] for k in old["line_hashes"]}


def test_changed_line_gets_new_id_and_old_version_stays_valid(lines):
    r1 = ready(lines)
    changed = L.update_user_fields(copy.deepcopy(lines[1]), planned_year=2033)
    changed["maintenance_line_id"] = "ML-2B"
    d2 = P.set_line_ids(P.create_next_draft(r1, at=T3), ["ML-1", "ML-2B"], at=T3)
    v2 = P.submit_for_review(d2, [lines[0], changed], at=T3, by="twandijkmans")
    r2, old = P.approve(v2, [lines[0], changed], at=T3, by="twandijkmans", reason="ok", previous_ready=r1)
    assert P.plan_errors(old, lines) == [] and P.plan_errors(r2, [lines[0], changed]) == []


def test_next_draft_only_from_ready(lines):
    with pytest.raises(P.PlanError):
        P.create_next_draft(draft(), at=T1)


def test_versions_errors(lines):
    r1 = ready(lines)
    d2 = P.create_next_draft(r1, at=T3)
    assert P.versions_errors([r1, d2]) == []
    assert any("aaneengesloten" in e for e in P.versions_errors([d2]))
    other = P.new_plan("MJOP-OTHER", "BLD-1", at=T0)
    assert P.versions_errors([r1, other]) == ["versies horen bij verschillende mjop_ids"]
    ready2 = copy.deepcopy(r1)
    ready2["version_id"], ready2["version_number"] = "MJOP-TEST-V002", 2
    ready2["content_sha256"] = P.content_sha256(ready2)
    assert any("meer dan één READY" in e for e in P.versions_errors([r1, ready2]))
    lone = copy.deepcopy(r1)
    lone["plan_status"] = "SUPERSEDED"
    lone["status_history"].append(P.event("SUPERSEDED", T3))
    assert any("zonder vastgestelde opvolger" in e for e in P.versions_errors([lone, d2]))


# --------------------------------------------------------------------------
# 7. Totalen
# --------------------------------------------------------------------------

def test_totals_population_and_vat_separation(lines):
    ls = lines + [manual_line("ML-3", vat="exclusive"), manual_line("ML-4", vat=None, planned_year=2031)]
    v = draft([l["maintenance_line_id"] for l in ls])
    t = P.plan_totals(v, ls)
    c1_total = Decimal(lines[0]["financial"]["effective_total"]) + Decimal(lines[1]["financial"]["effective_total"])
    assert Decimal(t["per_vat_basis"]["inclusive"]["total_exact"]) == c1_total
    assert t["per_vat_basis"]["exclusive"] == {"total_exact": "200", "total_display": "200.00", "lines": 1}
    assert t["per_vat_basis"]["unknown"]["lines"] == 1
    assert "total" not in t and set(t["per_planned_year"]["2031"]) == {"exclusive", "unknown"}
    assert t["per_action"]["exterior_painting"]["inclusive"]["lines"] == 1
    assert t["per_element_code"]["5211"]["inclusive"]["total_exact"] == lines[1]["financial"]["effective_total"]
    assert t["counts"]["in_financial_totals"] == 4 and t["counts"]["lines_total"] == 4


def test_totals_exclude_non_definitive_and_out_of_horizon():
    proposed, _ = L.run_workflow_for_line(c1_line("ML-1", vat_basis="exclusive"), EMPTY, CTX, root=PROJECT_ROOT)
    ls = [proposed, decided(c2_line(), "REJECT"), manual_line("ML-3", planned_year=2050),
          manual_line("ML-4", planned_year=None), c1_line("ML-5", quantity=None), manual_line("ML-6")]
    t = P.plan_totals(draft([l["maintenance_line_id"] for l in ls]), ls)
    assert t["counts"] == {"lines_total": 6, "in_financial_totals": 1, "no_amount": 1, "system_proposed": 1,
                           "review_required": 1, "rejected": 1, "amount_without_total": 0, "outside_horizon": 1,
                           "without_planned_year": 1}
    assert list(t["per_vat_basis"]) == ["exclusive"] and t["per_vat_basis"]["exclusive"]["lines"] == 1


def test_amount_without_total_counted():
    line = manual_line("ML-3", quantity=None)
    t = P.plan_totals(draft(["ML-3"]), [line])
    assert t["counts"]["amount_without_total"] == 1 and t["counts"]["in_financial_totals"] == 0


def test_no_horizon_means_no_financial_totals(lines):
    t = P.plan_totals(draft(start=None), lines)
    assert t["horizon"]["set"] is False and t["per_vat_basis"] == {} and t["counts"]["in_financial_totals"] == 0


def test_totals_exact_decimal_display_only_rounded(lines):
    t = P.plan_totals(draft(), lines)
    exact = Decimal(t["per_vat_basis"]["inclusive"]["total_exact"])
    assert t["per_vat_basis"]["inclusive"]["total_display"] == format(exact.quantize(Decimal("0.01")), "f")


def test_price_levels_reported_not_indexed(lines):
    ls = lines + [manual_line("ML-3")]
    t = P.plan_totals(draft([l["maintenance_line_id"] for l in ls]), ls)
    pl = t["price_levels"]
    assert pl["indexation"] == "none" and pl["manual_price_levels"] == ["2026"]
    assert pl["any_missing_price_level"] is True                      # C2: DOC-001 zonder prijspeil
    assert pl["kengetal_price_level_years"] == sorted(set(lines[0]["financial"]["price_level"]["years"]))


# --------------------------------------------------------------------------
# 8. Provenance (knowledge_basis)
# --------------------------------------------------------------------------

def test_knowledge_basis_derived_from_line_provenance(lines):
    ls = lines + [manual_line("ML-3")]
    r = ready(ls)
    kb = r["knowledge_basis"]
    p = lines[0]["provenance"]
    assert kb["kengetallen_output_sha256"] == [p["input_hashes"]["kengetallen_output_sha256"]]
    assert kb["normalized_observations_sha256"] == [p["input_hashes"]["normalized_observations_sha256"]]
    assert set(kb["decision_store_sha256"]) == {lines[0]["provenance"]["decision_store_sha256"],
                                                lines[1]["provenance"]["decision_store_sha256"]}
    assert kb["rule_versions"] == {k: [v] for k, v in sorted(p["rule_versions"].items())}
    assert kb["amount_sources"] == {"MANUAL_AMOUNT": 1, "SYSTEM_KENGETAL": 2}
    assert kb["lines_without_provenance"] == 1


def test_plan_has_no_own_provenance_or_scoring_fields(lines):
    r = ready(lines)
    forbidden = {"score", "confidence", "ranking", "source_document", "observations", "indexation_factor",
                 "reserve_fund", "cashflow"}
    assert not forbidden & set(r) and not forbidden & set(P.plan_totals(r, lines))


# --------------------------------------------------------------------------
# 9. Puurheid en data-integriteit
# --------------------------------------------------------------------------

def test_functions_do_not_mutate_input_and_are_deterministic(lines):
    before_lines = copy.deepcopy(lines)
    d = draft()
    d_before = copy.deepcopy(d)
    v = P.submit_for_review(d, lines, at=T1, by="twandijkmans")
    v_before = copy.deepcopy(v)
    r, _ = P.approve(v, lines, at=T2, by="twandijkmans", reason="ok")
    r_before = copy.deepcopy(r)
    P.plan_totals(r, lines)
    P.create_next_draft(r, at=T3)
    P.return_to_draft(v, at=T2, by="twandijkmans", reason="x")
    assert (d, v, r, lines) == (d_before, v_before, r_before, before_lines)
    assert P.approve(v, lines, at=T2, by="twandijkmans", reason="ok")[0] == r


def data_hashes():
    out = {}
    for base in ("data", "vocabularies"):
        for dirpath, _, files in os.walk(os.path.join(PROJECT_ROOT, base)):
            for f in files:
                path = os.path.join(dirpath, f)
                out[os.path.relpath(path, PROJECT_ROOT)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return out


def test_plan_layer_does_not_change_existing_data(lines):
    before = data_hashes()
    r = ready(lines)
    P.plan_totals(r, lines)
    P.create_next_draft(r, at=T3)
    assert data_hashes() == before
