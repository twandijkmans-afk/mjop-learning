"""Tests voor het Human Instance Decision Register v1. Alle registraties gebeuren in tijdelijke bestanden; het echte register blijft leeg."""
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import human_instance_decision_register as H  # noqa: E402
import physical_instance_approval as P  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
PROTECTED = ["data/frame_inventory/maldenhof_photo_frame_instances_v1.json", "data/frame_inventory/frame_inventory_v1.json",
             "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md", "reports/frames/physical_object_identity_pilot_v1.json",
             "reports/frames/physical_instance_approval_framework_v1.json", "reports/frames/physical_instance_approval_framework_v1.md"]


@pytest.fixture(scope="module")
def ctx():
    return H.load_context()


@pytest.fixture(scope="module")
def live(ctx):
    return P.evaluate_request(ctx, P.build_request(ctx, "OIC-VR-027"))


@pytest.fixture()
def reg(tmp_path):
    p = tmp_path / "register.jsonl"
    p.write_bytes(b"")
    return p


def make(live, decision="NEEDS_MORE_EVIDENCE", **over):
    t = H.blank_template(live)
    t.update(decision=decision, covers_levels=["A"], decision_source="HUMAN_CHAT_CONFIRMATION", decided_by="Testpersoon Voorbeeld",
             decision_timestamp="2026-10-13T11:00:00Z", acknowledged_open_app_ids=["APP-012", "APP-025"], acknowledged_open_relations=["VR-045"],
             evidence_reviewed=live["observation_ids"] + live["photo_ids"] + live["supporting_relation_ids"] + ["MAP-009"], reviewer_notes="testnotitie")
    t["decision_provenance"].update(channel="CLAUDE_CODE_CHAT", entered_by_kind="HUMAN_DIRECT", source_message_ref="testbericht-1",
                                    source_message_text=f"Voor {live['approval_request_id']} met request_hash {live['request_hash']} kies ik {decision} (testverklaring).",
                                    identity_verification="NONE_SELF_ASSERTED", ai_authored_decision=False)
    for k, v in over.items():
        t[k] = v
    return t


def reg_ok(inp, path, ctx, mode="REGISTER"):
    return H.register(inp, mode=mode, confirm=H.CONFIRM_TOKEN if mode == "REGISTER" else None, path=path, ctx=ctx, now=NOW)


def reasons(res):
    return " | ".join(res["reasons"])


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# --- uitgangssituatie ---------------------------------------------------------------------------------------------------------
def test_real_register_is_empty_and_valid():
    assert H.REGISTER_PATH.read_bytes() == b""
    assert H.load_register(H.REGISTER_PATH) == []


def test_live_request_hash_is_current_and_stale_hashes_are_superseded(live):
    assert live["request_hash"] == "e276feeb5849ba8af4c41e2e429aca21"
    assert live["approval_status"] == "READY_FOR_HUMAN_REVIEW"
    assert "aa556297be5d6713d298a06fa40492b8" in P.SUPERSEDED_HASHES and live["request_hash"] not in P.SUPERSEDED_HASHES


def test_current_state_has_no_human_decision(ctx):
    st = H.decision_state(ctx, "OIC-VR-027", H.REGISTER_PATH)
    assert st["step_1_technically_valid_request"] and not st["step_2_explicit_human_decision_registered"]
    assert not st["step_3_technically_verified_decision"] and st["step_4_instance_activated"] is False
    assert (st["level_A"], st["level_B"], st["level_C"]) == ("NOT_DECIDED",) * 3


def test_all_48_app_decisions_still_open(ctx):
    assert len(ctx["app_decisions"]) == 48 and all(a["status"] == "OPEN" for a in ctx["app_decisions"].values())


# --- registratievalidatie / gesloten schema ------------------------------------------------------------------------------------
def test_valid_decision_dry_run_writes_nothing(live, ctx, reg):
    res = reg_ok(make(live), reg, ctx, "DRY_RUN")
    assert res["status"] == "DRY_RUN", res["reasons"]
    assert reg.read_bytes() == b"" and res["changes"] == [] and res["instance_activated"] is False
    assert res["decision_id"] == "HID-0001"


def test_default_mode_is_dry_run(live, ctx, reg):
    res = H.register(make(live), path=reg, ctx=ctx, now=NOW)
    assert res["mode"] == "DRY_RUN" and res["status"] == "DRY_RUN" and reg.read_bytes() == b""


def test_register_requires_explicit_confirmation(live, ctx, reg):
    for c in (None, "", "yes", H.CONFIRM_TOKEN.lower()):
        res = H.register(make(live), mode="REGISTER", confirm=c, path=reg, ctx=ctx, now=NOW)
        assert res["status"] == "VALIDATION_FAILED" and "BEVESTIGING" in reasons(res)
    assert reg.read_bytes() == b""


def test_unknown_mode_rejected(live, ctx, reg):
    assert H.register(make(live), mode="ACTIVATE", path=reg, ctx=ctx)["status"] == "VALIDATION_FAILED"


@pytest.mark.parametrize("d", ["APPROVE", "ACTIVATE_INSTANCE", "approve_physical_identity", "", None, 1, "APPROVE_PHYSICAL_IDENTITY ", "CONFIRM"])
def test_unknown_decision_choice_rejected(live, ctx, reg, d):
    res = reg_ok(make(live, decision=d), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b""


@pytest.mark.parametrize("d", H.DECISIONS)
def test_exactly_three_decisions_register(live, ctx, reg, d):
    assert reg_ok(make(live, decision=d), reg, ctx)["status"] == "REGISTERED"


def test_exactly_three_supported_decisions():
    assert H.DECISIONS == ("APPROVE_PHYSICAL_IDENTITY", "REJECT", "NEEDS_MORE_EVIDENCE")


@pytest.mark.parametrize("extra", [{"activate": True}, {"activate_instance": "FI-X"}, {"bag_pand_id": "0363100012121455"}, {"quantity": 2}, {"cost": 10}, {"dimensions": "1x1"},
                                   {"frame_instance_id": "FI-M2-099"}, {"decision_id": "HID-0001"}, {"record_hash": "x"}, {"level": "A"}, {"statement": "xxxxxxxxxxxx"}])
def test_unknown_fields_and_activation_commands_rejected(live, ctx, reg, extra):
    res = reg_ok({**make(live), **extra}, reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "ONBEKENDE_VELDEN" in reasons(res)
    assert reg.read_bytes() == b""


@pytest.mark.parametrize("k", H.INPUT_KEYS)
def test_missing_required_field_rejected(live, ctx, reg, k):
    inp = make(live)
    del inp[k]
    res = reg_ok(inp, reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "ONTBREEKT" in reasons(res)


@pytest.mark.parametrize("k", H.PROVENANCE_KEYS)
def test_provenance_closed_schema(live, ctx, reg, k):
    inp = make(live)
    del inp["decision_provenance"][k]
    assert reg_ok(inp, reg, ctx)["status"] == "VALIDATION_FAILED"
    inp = make(live)
    inp["decision_provenance"]["extra"] = 1
    assert reg_ok(inp, reg, ctx)["status"] == "VALIDATION_FAILED"


def test_garbage_inputs_never_raise(live, ctx, reg):
    for g in (None, [], "x", 3, {}, {"decision": "REJECT"}, make(live, covers_levels="A"), make(live, evidence_reviewed="MAP-009"), make(live, record_version=True),
              make(live, record_version=2), make(live, decision_timestamp="gisteren"), make(live, decision_timestamp="2026-10-13T11:00:00")):
        res = reg_ok(g, reg, ctx)
        assert res["status"] == "VALIDATION_FAILED"
    assert reg.read_bytes() == b""


def test_json_schema_is_closed_and_matches_code():
    s = H.json_schema()
    for variant in s["oneOf"]:
        assert variant["additionalProperties"] is False
    assert s["oneOf"][0]["required"] == H.INPUT_KEYS and s["oneOf"][1]["required"] == H.STORED_KEYS
    assert s["oneOf"][0]["properties"]["decision"]["enum"] == list(H.DECISIONS)
    assert s["oneOf"][0]["properties"]["covers_levels"] == {"const": ["A"]}
    assert json.loads((ROOT / "schemas/human_instance_decision.schema.json").read_text()) == json.loads(json.dumps(s, sort_keys=True))
    assert set(s["oneOf"][0]["properties"]["decision_provenance"]["properties"]) == set(H.PROVENANCE_KEYS)


# --- request-hashintegriteit ----------------------------------------------------------------------------------------------------
def test_stale_superseded_hash_rejected(live, ctx, reg):
    inp = make(live, request_hash="aa556297be5d6713d298a06fa40492b8")
    inp["decision_provenance"]["source_message_text"] += " aa556297be5d6713d298a06fa40492b8 " + live["request_hash"]
    res = reg_ok(inp, reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "VEROUDERD" in reasons(res)


def test_wrong_hash_rejected(live, ctx, reg):
    bad = "0" * 32
    inp = make(live, request_hash=bad)
    inp["decision_provenance"]["source_message_text"] = f"{live['approval_request_id']} {bad} NEEDS_MORE_EVIDENCE kies ik hierbij uitdrukkelijk"
    assert "KOMT_NIET_OVEREEN" in reasons(reg_ok(inp, reg, ctx))


def test_statement_must_name_request_hash_id_and_choice(live, ctx, reg):
    for old in (live["request_hash"], live["approval_request_id"], "NEEDS_MORE_EVIDENCE"):
        inp = make(live)
        inp["decision_provenance"]["source_message_text"] = inp["decision_provenance"]["source_message_text"].replace(old, "X" * len(old))
        assert reg_ok(inp, reg, ctx)["status"] == "VALIDATION_FAILED"


def test_request_changed_after_decision_makes_decision_stale(live, ctx, reg, monkeypatch):
    assert reg_ok(make(live), reg, ctx)["status"] == "REGISTERED"
    assert [a["state"] for a in H.audit_register(ctx, reg, now=NOW)] == ["VERIFIED"]
    changed = copy.deepcopy(ctx)
    changed["verification"]["additional_matches"][0]["limits"] = list(changed["verification"]["additional_matches"][0]["limits"]) + ["nieuw gebleken beperking"]
    new_live = P.evaluate_request(changed, P.build_request(changed, "OIC-VR-027"))
    assert new_live["request_hash"] != live["request_hash"]          # de aanvraag is echt veranderd
    audit = H.audit_register(changed, reg, now=NOW)
    assert audit[0]["state"] == "STALE_REQUEST_CHANGED" and audit[0]["counts_as_instance"] is False and audit[0]["instance_activated"] is False
    st = H.decision_state(changed, "OIC-VR-027", reg)
    assert st["step_3_technically_verified_decision"] is False and st["level_A"] == "NOT_DECIDED"
    # het oude besluit mag niet als besluit over de gewijzigde aanvraag worden herhaald
    again = make(new_live)
    again["request_hash"] = live["request_hash"]
    assert reg_ok(again, reg, changed)["status"] == "VALIDATION_FAILED"


def test_stale_old_decision_does_not_block_new_hash_but_is_warned(live, ctx, reg):
    old = {"approval_request_id": live["approval_request_id"], "request_hash": "f" * 32}
    rec = H.build_stored_record({**make(live), **old}, [])
    reg.write_bytes((H.canonical(rec) + "\n").encode())
    res = reg_ok(make(live), reg, ctx, "DRY_RUN")
    assert res["status"] == "DRY_RUN" and res["warnings"] and "HID-0001" in res["warnings"][0]


def test_live_request_not_ready_rejected(live, ctx, reg):
    bad = copy.deepcopy(ctx)
    bad["oic_registry"]["OIC-VR-027"] = {**bad["oic_registry"]["OIC-VR-027"], "identity_status": "CANDIDATE"}
    res = reg_ok(make(live), reg, bad)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b""


def test_unknown_candidate_or_mismatched_ids_rejected(live, ctx, reg):
    assert reg_ok(make(live, candidate_group_id="OIC-VR-999"), reg, ctx)["status"] == "VALIDATION_FAILED"
    assert reg_ok(make(live, approval_request_id="IAR-OIC-VR-999"), reg, ctx)["status"] == "VALIDATION_FAILED"
    inp = make(live, approval_request_id="IAR-OIC-VR-045")
    inp["decision_provenance"]["source_message_text"] += " IAR-OIC-VR-045"
    assert "AANVRAAG_ONBEKEND" in reasons(reg_ok(inp, reg, ctx))


# --- onbetrouwbare herkomst / vervalste autorisatie -----------------------------------------------------------------------------
@pytest.mark.parametrize("source", ["CLAUDE_PROPOSAL", "AI_RECOMMENDATION", "CHATGPT_ADVICE", "", "human", "UNKNOWN", None])
def test_ai_or_unknown_decision_source_rejected(live, ctx, reg, source):
    assert reg_ok(make(live, decision_source=source), reg, ctx)["status"] == "VALIDATION_FAILED"


@pytest.mark.parametrize("name", ["Claude", "claude code", "AI", "an AI assistant", "Assistant", "bot", "automatic", "", "   ", None])
def test_non_human_decider_rejected(live, ctx, reg, name):
    assert reg_ok(make(live, decided_by=name), reg, ctx)["status"] == "VALIDATION_FAILED"


@pytest.mark.parametrize("k,v", [("channel", "UNKNOWN"), ("channel", ""), ("entered_by_kind", "AI_AUTHORED"), ("entered_by_kind", "GENERATED_EXAMPLE"),
                                 ("identity_verification", "CRYPTOGRAPHICALLY_VERIFIED"), ("identity_verification", "VERIFIED"), ("identity_verification", ""),
                                 ("ai_authored_decision", True), ("ai_authored_decision", None), ("ai_authored_decision", "false"),
                                 ("source_message_ref", ""), ("source_message_text", ""), ("source_message_text", "kort")])
def test_unreliable_provenance_rejected(live, ctx, reg, k, v):
    inp = make(live)
    inp["decision_provenance"][k] = v
    res = reg_ok(inp, reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b""


def test_ai_recommendation_presented_as_human_approval_rejected(live, ctx, reg):
    inp = make(live, decision="APPROVE_PHYSICAL_IDENTITY", decision_source="CLAUDE_PROPOSAL", decided_by="Claude")
    inp["decision_provenance"].update(entered_by_kind="AI_AUTHORED", ai_authored_decision=True)
    assert reg_ok(inp, reg, ctx)["status"] == "VALIDATION_FAILED"


def test_blank_template_and_generated_example_are_never_a_decision(live, ctx, reg):
    res = reg_ok(H.blank_template(live), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b""
    t = json.loads((ROOT / "reports/frames/human_instance_decision_register_v1/IAR-OIC-VR-027_decision_input_TEMPLATE.json").read_text())
    assert reg_ok(t, reg, ctx, "DRY_RUN")["status"] == "VALIDATION_FAILED"


def test_template_decision_fields_are_empty_and_nothing_preselected(live):
    t = H.blank_template(live)
    for k in ("decision", "decision_source", "decided_by", "decision_timestamp", "reviewer_notes"):
        assert t[k] == ""
    for k in ("covers_levels", "acknowledged_open_app_ids", "acknowledged_open_relations", "evidence_reviewed"):
        assert t[k] == []
    assert all(v in ("", None) for v in t["decision_provenance"].values())
    committed = json.loads((ROOT / "reports/frames/human_instance_decision_register_v1/IAR-OIC-VR-027_decision_input_TEMPLATE.json").read_text())
    assert committed == t


def test_timestamp_in_future_rejected(live, ctx, reg):
    assert "TOEKOMST" in reasons(reg_ok(make(live, decision_timestamp="2026-10-14T00:00:00Z"), reg, ctx))


def test_register_never_trusts_framework_fields_in_input(live, ctx, reg):
    inp = make(live)
    inp["validation_results"] = {"technical_verdict": "SUITABLE_FOR_HUMAN_REVIEW"}
    inp["approval_status"] = "APPROVED_FOR_ACTIVATION"
    assert "ONBEKENDE_VELDEN" in reasons(reg_ok(inp, reg, ctx))


# --- niveau-A-isolatie, verboden effecten --------------------------------------------------------------------------------------
@pytest.mark.parametrize("levels", [["A", "B"], ["B"], ["C"], ["A", "B", "C"], [], ["a"], "A", ["A", "A"]])
def test_only_level_a_allowed(live, ctx, reg, levels):
    res = reg_ok(make(live, covers_levels=levels), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b""


@pytest.mark.parametrize("text", ["pand 0363100012121455", "FI-M2-014", "FI-M3-001 aanmaken", "bag 0363100012134188"])
def test_pand_and_fi_content_in_free_text_rejected(live, ctx, reg, text):
    res = reg_ok(make(live, reviewer_notes=text), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b""
    inp = make(live)
    inp["decision_provenance"]["source_message_text"] += " " + text
    assert reg_ok(inp, reg, ctx)["status"] == "VALIDATION_FAILED"


def test_register_has_no_fi_ids_and_no_activation_path(live, ctx, reg):
    for d in H.DECISIONS:
        r = reg_ok(make(live, decision=d, decision_timestamp="2026-10-13T11:%02d:00Z" % (10 + H.DECISIONS.index(d))), reg, ctx)
        res_h = H.load_register(reg)
        break
    assert not P.FI_PATTERN.search(reg.read_text())
    assert r["instance_activated"] is False and r["fi_ids_created"] == 0
    st = H.decision_state(ctx, "OIC-VR-027", reg)
    assert st["step_4_instance_activated"] is False and all(a["instance_activated"] is False and a["counts_as_instance"] is False for a in st["decisions"])
    assert res_h


def test_registered_approval_does_not_decide_levels_b_c_or_create_instance(live, ctx, reg):
    stores = {p: sha(ROOT / p) for p in PROTECTED}
    assert reg_ok(make(live, decision="APPROVE_PHYSICAL_IDENTITY"), reg, ctx)["status"] == "REGISTERED"
    st = H.decision_state(ctx, "OIC-VR-027", reg)
    assert st["level_A"] == "APPROVE_PHYSICAL_IDENTITY" and st["level_B"] == st["level_C"] == "NOT_DECIDED"
    assert stores == {p: sha(ROOT / p) for p in PROTECTED}
    req = P.evaluate_request(ctx, P.build_request(ctx, "OIC-VR-027"))
    assert req["is_instance"] is False and req["frame_instance_id"] is None and req["reserved_instance_id"] is None


def test_module_has_no_activation_or_instance_store_write():
    src = (ROOT / "scripts/human_instance_decision_register.py").read_text()
    tree = ast.parse(src)
    imported = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in imported if m and any(x in m for x in ("activation", "frame_instance", "build_frame"))}
    assert "INSTANCE_STORE" not in src and "maldenhof_photo_frame_instances" not in src
    for forbidden in ("activate_instance", "create_fi", "reserve_instance_id"):
        assert forbidden not in [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert "create_fi_id" in H.FORBIDDEN_EFFECTS and "activate_instance" in H.FORBIDDEN_EFFECTS
    assert set(P.FORBIDDEN_EFFECTS) <= set(H.FORBIDDEN_EFFECTS)


def test_no_other_script_writes_the_register():
    for f in (ROOT / "scripts").glob("*.py"):
        if f.name.startswith("human_instance_decision_register") or f.name == "doc012_generalization_review.py":   # laatste: alleen de REPORT_ONLY-lijst
            continue
        if f.name == "human_decision_intake.py":     # PR intake: leest het register uitsluitend (load_register/validate_input/...); bewaakt door tests/test_human_decision_intake.py
            continue
        assert "human_instance_decision_register" not in f.read_text(), f.name


# --- erkenning APP / VR-045 ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("apps", [[], ["APP-012"], ["APP-025"], ["APP-001"]])
def test_open_direct_app_questions_must_be_acknowledged(live, ctx, reg, apps):
    res = reg_ok(make(live, acknowledged_open_app_ids=apps), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "APP" in reasons(res)


def test_vr045_cannot_be_silently_resolved(live, ctx, reg):
    res = reg_ok(make(live, acknowledged_open_relations=[]), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "RELATIES_NIET_ERKEND" in reasons(res)


@pytest.mark.parametrize("apps,rels", [(["APP-012", "APP-025", "APP-999"], ["VR-045"]), (["APP-012", "APP-025"], ["VR-045", "VR-999"]), (["APP-012", "APP-025"], ["VR-045", "VR-027"])])
def test_cannot_acknowledge_unknown_things(live, ctx, reg, apps, rels):
    assert reg_ok(make(live, acknowledged_open_app_ids=apps, acknowledged_open_relations=rels), reg, ctx)["status"] == "VALIDATION_FAILED"


def test_app_marked_closed_in_source_is_not_acknowledgeable_as_open(live, ctx, reg):
    c = copy.deepcopy(ctx)
    c["app_decisions"]["APP-025"]["status"] = "CLOSED"
    res = reg_ok(make(live), reg, c)
    assert res["status"] == "VALIDATION_FAILED" and "NIET_OPEN" in reasons(res) and reg.read_bytes() == b""


def test_evidence_reviewed_must_cover_all_evidence(live, ctx, reg):
    for drop in live["observation_ids"] + live["photo_ids"] + ["MAP-009"]:
        inp = make(live)
        inp["evidence_reviewed"] = [e for e in inp["evidence_reviewed"] if e != drop]
        assert reg_ok(inp, reg, ctx)["status"] == "VALIDATION_FAILED", drop
    assert reg_ok(make(live, evidence_reviewed=[]), reg, ctx)["status"] == "VALIDATION_FAILED"


def test_duplicate_list_entries_rejected(live, ctx, reg):
    assert reg_ok(make(live, acknowledged_open_app_ids=["APP-012", "APP-012", "APP-025"]), reg, ctx)["status"] == "VALIDATION_FAILED"


# --- append-only, duplicaten, conflicten ----------------------------------------------------------------------------------------
def test_registration_appends_one_chained_record(live, ctx, reg):
    res = reg_ok(make(live), reg, ctx)
    assert res["status"] == "REGISTERED" and res["decision_id"] == "HID-0001"
    recs = H.load_register(reg)
    assert len(recs) == 1 and recs[0]["previous_record_hash"] == H.GENESIS and recs[0]["record_hash"] == H.record_hash(recs[0])
    assert res["register_head_after"] == recs[0]["record_hash"] and res["changes"] == ["append HID-0001 aan register.jsonl"]
    assert reg.read_bytes().endswith(b"\n") and set(recs[0]) == set(H.STORED_KEYS)
    assert not (reg.parent / (reg.name + ".lock")).exists() and not list(reg.parent.glob(".*.tmp"))


def test_same_decision_again_is_duplicate_and_writes_nothing(live, ctx, reg):
    inp = make(live)
    assert reg_ok(inp, reg, ctx)["status"] == "REGISTERED"
    before = reg.read_bytes()
    res = reg_ok(copy.deepcopy(inp), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "DUPLICAAT" in reasons(res) and reg.read_bytes() == before


@pytest.mark.parametrize("first,second", [("NEEDS_MORE_EVIDENCE", "APPROVE_PHYSICAL_IDENTITY"), ("REJECT", "APPROVE_PHYSICAL_IDENTITY"),
                                          ("APPROVE_PHYSICAL_IDENTITY", "REJECT"), ("NEEDS_MORE_EVIDENCE", "REJECT")])
def test_conflicting_second_decision_refused_and_first_kept(live, ctx, reg, first, second):
    assert reg_ok(make(live, decision=first), reg, ctx)["status"] == "REGISTERED"
    before = reg.read_bytes()
    res = reg_ok(make(live, decision=second), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "CONFLICTEREND" in reasons(res)
    assert reg.read_bytes() == before and H.load_register(reg)[0]["decision"] == first


def test_same_decision_with_different_text_is_also_a_conflict_not_an_overwrite(live, ctx, reg):
    assert reg_ok(make(live), reg, ctx)["status"] == "REGISTERED"
    before = reg.read_bytes()
    res = reg_ok(make(live, reviewer_notes="andere toelichting"), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == before


def test_existing_bytes_are_never_modified_by_later_appends(live, ctx, reg):
    assert reg_ok(make(live), reg, ctx)["status"] == "REGISTERED"
    first = reg.read_bytes()
    # tweede record voor een (ander) hash-scenario rechtstreeks via de bouwfunctie, zodat de append-logica zelf getest wordt
    other = {**make(live), "request_hash": "e" * 32}
    rec2 = H.build_stored_record(other, H.load_register(reg))
    H._atomic_replace(reg, first + (H.canonical(rec2) + "\n").encode())
    assert reg.read_bytes().startswith(first) and len(H.load_register(reg)) == 2
    assert H.load_register(reg)[1]["previous_record_hash"] == H.load_register(reg)[0]["record_hash"]


def test_no_delete_or_update_api():
    names = {n for n in dir(H) if callable(getattr(H, n))}
    assert not {n for n in names if any(w in n.lower() for w in ("delete", "remove", "update", "overwrite", "rewrite", "activate"))}


# --- corrupte en gedeeltelijk geschreven bestanden / atomische writes ------------------------------------------------------------
def _one(live, ctx, reg):
    assert reg_ok(make(live), reg, ctx)["status"] == "REGISTERED"
    return reg.read_bytes()


@pytest.mark.parametrize("mut", ["truncate", "badjson", "flip", "reorder", "extrakey", "noncanonical", "emptyline", "binary", "dupe", "garbage_tail"])
def test_corrupt_register_fails_closed_and_is_untouched(live, ctx, reg, mut):
    good = _one(live, ctx, reg)
    line = good.decode().rstrip("\n")
    rec = json.loads(line)
    bad = {"truncate": good[:-20], "badjson": b"{not json}\n", "flip": good.replace(b"NEEDS_MORE_EVIDENCE", b"REJECT"),
           "reorder": good + good, "extrakey": (H.canonical({**rec, "activate": True}) + "\n").encode(),
           "noncanonical": (json.dumps(rec, indent=1) + "\n").encode(), "emptyline": good + b"\n", "binary": b"\xff\xfe\x00\n",
           "dupe": good + good, "garbage_tail": good + b"x"}[mut]
    reg.write_bytes(bad)
    res = reg_ok(make(live, decision="REJECT"), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "BESCHADIGD" in reasons(res)
    assert reg.read_bytes() == bad
    with pytest.raises(H.RegisterCorrupt):
        H.load_register(reg)
    assert reg_ok(make(live), reg, ctx, "DRY_RUN")["status"] == "VALIDATION_FAILED"


def test_missing_register_fails_closed_and_is_not_created(live, ctx, tmp_path):
    p = tmp_path / "nope.jsonl"
    res = reg_ok(make(live), p, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "ONTBREEKT" in reasons(res) and not p.exists()


def test_tampered_record_detected_by_hash_chain(live, ctx, reg):
    _one(live, ctx, reg)
    rec = json.loads(reg.read_text())
    rec["decision"] = "APPROVE_PHYSICAL_IDENTITY"
    reg.write_text(H.canonical(rec) + "\n")
    with pytest.raises(H.RegisterCorrupt, match="KETEN_OF_HASH"):
        H.load_register(reg)


def test_failed_atomic_replace_leaves_register_and_directory_clean(live, ctx, reg, monkeypatch):
    before = reg.read_bytes()

    def boom(a, b):
        raise OSError("schijf vol")
    monkeypatch.setattr(H.os, "replace", boom)
    res = reg_ok(make(live), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "ONVERWACHTE_FOUT" in reasons(res)
    assert reg.read_bytes() == before and not list(reg.parent.glob(".*.tmp")) and not (reg.parent / (reg.name + ".lock")).exists()


def test_crash_while_writing_temp_file_leaves_register_untouched(live, ctx, reg, monkeypatch):
    real = os.fsync

    def boom(fd):
        raise OSError("crash tijdens fsync")
    monkeypatch.setattr(H.os, "fsync", boom)
    res = reg_ok(make(live), reg, ctx)
    monkeypatch.setattr(H.os, "fsync", real)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b"" and not list(reg.parent.glob(".*.tmp"))
    assert reg_ok(make(live), reg, ctx)["status"] == "REGISTERED"


def test_post_write_verification_failure_is_reported(live, ctx, reg, monkeypatch):
    real = H.load_register
    calls = {"n": 0}

    def flaky(path=H.REGISTER_PATH):
        calls["n"] += 1
        if calls["n"] == 2:
            raise H.RegisterCorrupt("simulatie")
        return real(path)
    monkeypatch.setattr(H, "load_register", flaky)
    res = reg_ok(make(live), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "ONVERWACHTE_FOUT" in reasons(res) or "NACONTROLE" in reasons(res)


def test_atomic_replace_writes_same_directory_tmp_then_replace(tmp_path, monkeypatch):
    p = tmp_path / "r.jsonl"
    p.write_bytes(b"")
    seen = {}
    real = os.replace

    def spy(a, b):
        seen["src"], seen["dst"] = Path(a), Path(b)
        assert Path(a).read_bytes() == b"abc\n" and Path(b).read_bytes() == b""
        return real(a, b)
    monkeypatch.setattr(H.os, "replace", spy)
    H._atomic_replace(p, b"abc\n")
    assert seen["src"].parent == seen["dst"].parent and p.read_bytes() == b"abc\n" and not list(tmp_path.glob(".*.tmp"))


# --- gelijktijdige registratie ----------------------------------------------------------------------------------------------------
def test_existing_lock_fails_closed(live, ctx, reg):
    lock = reg.parent / (reg.name + ".lock")
    lock.write_text("x")
    res = reg_ok(make(live), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "VERGRENDELD" in reasons(res) and reg.read_bytes() == b"" and lock.exists()


def test_dry_run_ignores_lock_and_never_creates_it(live, ctx, reg):
    assert reg_ok(make(live), reg, ctx, "DRY_RUN")["status"] == "DRY_RUN"
    assert not (reg.parent / (reg.name + ".lock")).exists()


def test_concurrent_identical_registrations_yield_exactly_one_record(live, ctx, reg):
    inp, results = make(live), []

    def work():
        results.append(reg_ok(copy.deepcopy(inp), reg, ctx)["status"])
    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count("REGISTERED") == 1 and len(results) == 8
    recs = H.load_register(reg)
    assert len(recs) == 1 and recs[0]["decision"] == "NEEDS_MORE_EVIDENCE"
    assert not (reg.parent / (reg.name + ".lock")).exists() and not list(reg.parent.glob(".*.tmp"))


def test_concurrent_conflicting_registrations_yield_exactly_one_record(live, ctx, reg):
    results = []

    def work(d):
        results.append((d, reg_ok(make(live, decision=d), reg, ctx)["status"]))
    ts = [threading.Thread(target=work, args=(d,)) for d in H.DECISIONS * 3]
    [t.start() for t in ts]
    [t.join() for t in ts]
    won = [d for d, s in results if s == "REGISTERED"]
    recs = H.load_register(reg)
    assert len(won) == 1 and len(recs) == 1 and recs[0]["decision"] == won[0]


def test_compare_and_swap_detects_change_under_lock(live, ctx, reg, monkeypatch):
    real = H.build_stored_record

    def sneaky(inp, existing):
        reg.write_bytes(b"")      # onder het slot verandert iemand het bestand
        rec = real(inp, existing)
        reg.write_bytes(b"\n")
        return rec
    monkeypatch.setattr(H, "build_stored_record", sneaky)
    res = reg_ok(make(live), reg, ctx)
    assert res["status"] == "VALIDATION_FAILED" and "TUSSENTIJDS" in reasons(res) and reg.read_bytes() == b"\n"


# --- bescherming van bestaande bestanden / deterministische generatie -------------------------------------------------------------
def test_register_flow_leaves_protected_files_byte_identical(live, ctx, reg):
    before = {p: sha(ROOT / p) for p in PROTECTED}
    real_before = H.REGISTER_PATH.read_bytes()
    reg_ok(make(live), reg, ctx, "DRY_RUN")
    reg_ok(make(live, decision="REJECT"), reg, ctx)
    H.audit_register(ctx, reg, now=NOW)
    assert before == {p: sha(ROOT / p) for p in PROTECTED} and H.REGISTER_PATH.read_bytes() == real_before == b""


def test_generation_is_deterministic_and_does_not_touch_the_register(tmp_path):
    outs = [H.OUT_JSON, H.OUT_MD, H.TEMPLATE_JSON, H.PACK_HTML, H.SCHEMA_PATH, H.REGISTER_PATH]
    before = {str(p): sha(p) for p in outs}
    r = subprocess.run([sys.executable, str(ROOT / "scripts/human_instance_decision_register.py"), "generate"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert before == {str(p): sha(p) for p in outs}
    assert H.REGISTER_PATH.read_bytes() == b""


def test_cli_check_is_dry_run_and_register_needs_confirm(live, tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps(H.blank_template(live)))
    r = subprocess.run([sys.executable, str(ROOT / "scripts/human_instance_decision_register.py"), "check", "--decision", str(f)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "VALIDATION_FAILED" in r.stdout
    r = subprocess.run([sys.executable, str(ROOT / "scripts/human_instance_decision_register.py"), "register", "--decision", str(f)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "BEVESTIGING" in r.stdout
    assert H.REGISTER_PATH.read_bytes() == b""


def test_report_states_no_decision_no_activation():
    rep = json.loads(H.OUT_JSON.read_text())
    assert rep["records_registered"] == 0 and rep["register_head"] == H.GENESIS and rep["default_mode"] == "DRY_RUN"
    assert rep["effects"]["instances_created"] == 0 and rep["effects"]["fi_ids_created"] == 0 and rep["effects"]["instance_store_written"] is False
    assert rep["request"]["request_hash"] == "e276feeb5849ba8af4c41e2e429aca21" and rep["decision_state"]["level_A"] == "NOT_DECIDED"
    assert rep["template_dry_run"]["status"] == "VALIDATION_FAILED" and rep["app_decisions"] == {"total": 48, "open": 48}
    assert "STOP" in H.OUT_MD.read_text() and "NONE_SELF_ASSERTED" in H.OUT_MD.read_text()


def test_decision_pack_has_no_preselected_choice_or_form():
    html = H.PACK_HTML.read_text()
    assert "<form" not in html and "<input" not in html and "<script" not in html and "checked" not in html and "selected" not in html
    assert "NEEDS_MORE_EVIDENCE is een gelijkwaardige keuze" in html and "APP-012" in html and "APP-025" in html and "VR-045" in html
    assert "e276feeb5849ba8af4c41e2e429aca21" in html and "STRONG_VISUAL_SUPPORT" in html and "MEDIUM" in html and "MAP-009" in html
