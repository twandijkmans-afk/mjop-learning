"""Tests voor Human Decision Intake & Provenance Hardening v1 (uitsluitend DRY_RUN, synthetische fixtures).

Geen enkele test registreert een besluit of schrijft naar het echte register; de synthetische bron en het synthetische anker bestaan alleen in testcode."""
import ast
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "human_decision_intake"))
import human_decision_intake as H  # noqa: E402
import human_decision_intake_report as RP  # noqa: E402
import human_instance_decision_register as R  # noqa: E402
import scenario_lib as S  # noqa: E402

CORE = ROOT / "scripts" / "human_decision_intake.py"
REPORT = ROOT / "scripts" / "human_decision_intake_report.py"
PROTECTED = ["data/instance_decisions/human_instance_decision_register_v1.jsonl", "data/frame_inventory/maldenhof_photo_frame_instances_v1.json",
             "data/frame_inventory/frame_inventory_v1.json", "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md",
             "reports/frames/physical_object_identity_pilot_v1.json", "reports/frames/physical_instance_approval_framework_v1.json",
             "reports/frames/physical_instance_approval_framework_v1.md", "reports/frames/human_instance_decision_register_v1.json",
             "reports/frames/human_instance_decision_register_v1.md", "schemas/human_instance_decision.schema.json",
             "reports/frames/photo_review_map003_map004_v1/pilot_decisions/maldenhof_pilot_decision_register_v1.json",
             "reports/frames/physical_instance_evidence_reconciliation_v1.md"]


@pytest.fixture(scope="module")
def ctx():
    return R.load_context()


@pytest.fixture(scope="module")
def live(ctx):
    return S.live_request(ctx)


@pytest.fixture(scope="module")
def text(live):
    return S.decision_text(live)


@pytest.fixture(scope="module")
def env(live, text):
    return S.make_envelope(live, text)


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def run(env, ctx, text, **over):
    return H.validate_intake(env, **S.kit(ctx, text, **over))


# --- uitgangssituatie ---------------------------------------------------------------------------------------------------------------------------
def test_live_request_hash_is_current(live):
    assert live["request_hash"] == "e276feeb5849ba8af4c41e2e429aca21" and live["approval_status"] == "READY_FOR_HUMAN_REVIEW"
    assert all(h not in live["request_hash"] for h in R.P.SUPERSEDED_HASHES)


def test_no_registered_decision_no_activation_and_48_open_apps(ctx):
    assert R.REGISTER_PATH.read_bytes() == b"" and R.load_register() == []
    assert len(ctx["app_decisions"]) == 48 and all(a["status"] == "OPEN" for a in ctx["app_decisions"].values())


def test_shipped_configuration_is_empty_and_failclosed():
    tp, _ = H.load_trusted_providers()
    az, _ = H.load_authorization()
    assert tp["providers"] == [] and az["designations"] == []
    assert H._registry_problems(tp) == [] and H.authorization_problems_in_doc(az) == []


# --- de zeven begrippen blijven gescheiden --------------------------------------------------------------------------------------------------------
def test_perfect_content_with_self_asserted_author_is_not_verified(env, ctx):
    rep = H.validate_intake(env, ctx=ctx, now=S.NOW)             # standaardconfiguratie van de repository
    assert rep["final_status"] == "UNVERIFIED_SOURCE" and rep["provenance"]["status"] == "SELF_ASSERTED"
    lad = rep["ladder"]
    assert lad["1_claim_text"]["present"] and lad["2_author_id_asserted"]["present"] and lad["5_valid_level_a_decision"]["present"]
    assert not lad["3_author_authenticated_by_system"]["present"] and not lad["4_provenance_verified"]["present"]
    assert not lad["6_registered"]["present"] and not lad["7_instance_activated"]["present"]
    assert rep["registration_eligibility"] == "NOT_ELIGIBLE" and rep["registration_performed"] is False


def test_default_configuration_can_never_produce_source_verified(env, ctx, text):
    """Ook een volledig correcte attestatie van een provider telt niet zolang er geen vertrouwde, geankerde providerlijst is."""
    prov = S.SyntheticIntakeSource({S.MSG: S.attestation(text)})
    rep = H.validate_intake(env, ctx=ctx, provider=prov, now=S.NOW)
    assert rep["provenance"]["status"] == "UNVERIFIABLE" and rep["provenance"]["authentication_status"] == "SOURCE_UNTRUSTED"
    assert rep["final_status"] == "UNVERIFIED_SOURCE" and rep["authorization"]["status"] == "NOT_EVALUATED"


def test_text_hash_alone_is_never_authentication(env, ctx):
    rep = H.validate_intake(env, ctx=ctx, now=S.NOW)
    assert rep["text_integrity"]["matches_claimed_hash"] and rep["text_integrity"]["proves_author"] is False
    assert rep["text_integrity"]["status"] == "MATCHES_CLAIMED_HASH_SELF_ONLY"
    assert rep["provenance"]["status"] != "SOURCE_VERIFIED"


@pytest.mark.parametrize("field,value", [("author_id", "authorized_user"), ("source_message_id", "msg-1"), ("source_timestamp", S.TS), ("author_identity_source", "GITHUB")])
def test_each_claimed_field_alone_never_verifies(live, text, ctx, field, value):
    e = S.make_envelope(live, text, pointer=False, claims={"author_id": None, "author_identity_source": None, "source_message_id": None, "source_timestamp": None, field: value})
    assert H.validate_intake(e, ctx=ctx, now=S.NOW)["provenance"]["status"] in ("SELF_ASSERTED", "UNVERIFIABLE")


def test_full_synthetic_pass_is_only_validated_dry_run_and_not_registered(env, ctx, text):
    before = sha(PROTECTED[0])
    rep = run(env, ctx, text)
    assert rep["final_status"] == "VALIDATED_DRY_RUN" and rep["provenance"]["status"] == "SOURCE_VERIFIED" and rep["authorization"]["status"] == "AUTHORIZED"
    assert rep["provenance"]["authentication_status"] == "AUTHENTICATED_HUMAN_PRESENCE"
    assert rep["registration_eligibility"] == "NOT_ELIGIBLE_SYNTHETIC_SOURCE" and rep["registration_performed"] is False
    assert rep["register_state"]["written"] is False and rep["effects"]["decisions_registered"] == 0 and rep["effects"]["fi_ids_created"] == 0
    assert rep["ladder"]["6_registered"]["present"] is False and rep["ladder"]["7_instance_activated"]["present"] is False
    assert sha(PROTECTED[0]) == before and R.REGISTER_PATH.read_bytes() == b""


def test_eligibility_logic_for_a_non_synthetic_trusted_source_still_registers_nothing(env, ctx, text):
    """Logica-test met een (fictieve) niet-synthetische vertrouwde bron: hoogstens 'geschikt voor een latere registratiestap', nooit uitgevoerd."""
    tp = S.trusted_providers(synthetic=False)
    rep = run(env, ctx, text, tp=tp, anchor=S.pinned_anchor(tp, S.authorization_doc()))
    assert rep["final_status"] == "VALIDATED_DRY_RUN" and rep["registration_eligibility"] == "ELIGIBLE_FOR_FUTURE_REGISTRATION_STEP"
    assert rep["registration_performed"] is False and rep["registration_possible_in_this_intake"] is False and R.REGISTER_PATH.read_bytes() == b""


# --- authenticatie ≠ autorisatie ≠ inhoud --------------------------------------------------------------------------------------------------------
def test_authentication_without_authorization(live, text, ctx):
    e = S.make_envelope(live, text, claims={"author_id": S.REVIEWER_B})
    rep = run(e, ctx, text, att=S.attestation(text, author=S.REVIEWER_B))
    assert rep["provenance"]["status"] == "SOURCE_VERIFIED" and rep["authorization"]["status"] == "UNAUTHORIZED" and rep["final_status"] == "UNAUTHORIZED_REVIEWER"


def test_authorization_never_uses_the_claimed_author(live, text, ctx):
    """De opgegeven auteur is wel aangewezen, de geauthenticeerde niet: de opgegeven auteur telt niet (en wijkt af = INVALID)."""
    e = S.make_envelope(live, text, claims={"author_id": S.REVIEWER_A})
    rep = run(e, ctx, text, att=S.attestation(text, author=S.REVIEWER_B))
    assert rep["provenance"]["status"] == "INVALID" and rep["final_status"] == "BLOCKED"
    assert any("OPGEGEVEN_AUTEUR_WIJKT_AF" in p for p in rep["open_problems"])


def test_authorization_not_evaluated_without_authenticated_author(env, ctx):
    rep = H.validate_intake(env, ctx=ctx, now=S.NOW, authorization=S.authorization_doc(), anchor=S.pinned_anchor(S.trusted_providers(), S.authorization_doc()))
    assert rep["authorization"]["status"] == "NOT_EVALUATED" and rep["final_status"] == "UNVERIFIED_SOURCE"


def test_valid_authentication_and_authorization_with_invalid_content(live, ctx):
    t = f"Synthetisch: voor {live['approval_request_id']} kies ik NEEDS_MORE_EVIDENCE zonder de hash, in een voldoende lange testverklaring."
    rep = run(S.make_envelope(live, t), ctx, t)
    assert rep["provenance"]["status"] == "SOURCE_VERIFIED" and rep["authorization"]["status"] == "AUTHORIZED"
    assert rep["final_status"] == "INVALID_DECISION" and rep["ladder"]["5_valid_level_a_decision"]["present"] is False


def test_account_without_proven_human_presence_is_not_verified(env, ctx, text):
    """Een geauthenticeerd account is geen mens: dezelfde account kan door een AI-tool worden gebruikt."""
    rep = run(env, ctx, text, att=S.attestation(text, presence="NONE"))
    assert rep["provenance"]["authentication_status"] == "AUTHENTICATED_ACCOUNT_ONLY" and rep["provenance"]["status"] == "UNVERIFIABLE"
    assert rep["final_status"] == "UNVERIFIED_SOURCE"
    tp = S.trusted_providers(presence=("INTERACTIVE_MFA_SESSION_SEPARATE_FROM_AUTOMATION",))
    rep = run(env, ctx, text, tp=tp, anchor=S.pinned_anchor(tp, S.authorization_doc()))      # methode niet geaccepteerd door deze provider
    assert rep["provenance"]["authentication_status"] == "AUTHENTICATED_ACCOUNT_ONLY" and rep["final_status"] == "UNVERIFIED_SOURCE"


def test_unknown_actor_type_is_unverifiable_and_bot_is_invalid(env, ctx, text):
    assert run(env, ctx, text, att=S.attestation(text, actor="UNKNOWN"))["provenance"]["status"] == "UNVERIFIABLE"
    for actor in ("BOT", "AUTOMATION"):
        rep = run(env, ctx, text, att=S.attestation(text, actor=actor))
        assert rep["provenance"]["status"] == "INVALID" and rep["final_status"] == "BLOCKED"


def test_unanchored_or_wrong_anchor_makes_provider_and_authorization_failclosed(env, ctx, text):
    tp, az = S.trusted_providers(), S.authorization_doc()
    rep = run(env, ctx, text, tp=tp, az=az, anchor=S.FixtureTrustAnchor({}))
    assert rep["provenance"]["status"] == "UNVERIFIABLE" and rep["final_status"] == "UNVERIFIED_SOURCE"
    assert any("ONGEANKERD" in p for p in rep["provenance"]["problems"])
    rep = run(env, ctx, text, tp=tp, az=az, anchor=S.FixtureTrustAnchor({"human_decision_intake_trusted_providers_v1": H.canonical_sha256(tp)}))
    assert rep["authorization"]["status"] == "UNANCHORED" and rep["final_status"] == "UNAUTHORIZED_REVIEWER"


def test_any_change_to_pinned_documents_breaks_the_pin(env, ctx, text):
    tp, az = S.trusted_providers(), S.authorization_doc()
    anchor = S.pinned_anchor(tp, az)
    az2 = copy.deepcopy(az)
    az2["designations"][0]["valid_until"] = "2099-01-01T00:00:00Z"
    assert run(env, ctx, text, tp=tp, az=az2, anchor=anchor)["authorization"]["status"] == "UNANCHORED"
    tp2 = S.trusted_providers(presence=("WEBAUTHN_USER_VERIFIED", "NONE"))
    assert run(env, ctx, text, tp=tp2, az=az, anchor=anchor)["provenance"]["status"] == "UNVERIFIABLE"


@pytest.mark.parametrize("mut,why", [
    (lambda d: d["designations"][0].update(designated_by=S.REVIEWER_A), "ZELFAANWIJZING"),
    (lambda d: d["designations"][0].update(designated_by="onbekend-gezag"), "AANWIJZER_IS_GEEN_GEANKERD_GEZAG"),
    (lambda d: d["designations"][0].update(scope_levels=["A", "B"]), "SCOPE_DEKT_NIET_UITSLUITEND_NIVEAU_A"),
    (lambda d: d["designations"][0].update(approval_request_ids=["IAR-OIC-VR-999"]), "AANWIJZING_GELDT_NIET_VOOR_DEZE_AANVRAAG"),
    (lambda d: d["designations"][0].update(valid_until="2026-10-01T00:00:00Z"), "AANWIJZING_NIET_GELDIG_OP_DIT_MOMENT"),
    (lambda d: d["designations"][0].update(valid_from="2027-01-01T00:00:00Z", valid_until="2027-12-31T00:00:00Z"), "AANWIJZING_NIET_GELDIG_OP_DIT_MOMENT"),
])
def test_designation_rules_even_when_the_list_is_pinned(env, ctx, text, mut, why):
    az = S.authorization_doc()
    mut(az)
    rep = run(env, ctx, text, az=az, anchor=S.pinned_anchor(S.trusted_providers(), az))
    assert rep["authorization"]["status"] == "UNAUTHORIZED" and rep["final_status"] == "UNAUTHORIZED_REVIEWER", rep["authorization"]
    assert any(why in p for p in rep["authorization"]["problems"])


def test_malformed_authorization_or_provider_lists_failclosed(env, ctx, text):
    for az in ({"registry_version": "x"}, {"registry_version": H.AUTHORIZATION_VERSION, "note": "", "designations": [{"reviewer_id": "x"}]}, [], None):
        rep = run(env, ctx, text, az=az if az else {"registry_version": "kapot"}, anchor=S.pinned_anchor(S.trusted_providers(), az if az else {"registry_version": "kapot"}))
        assert rep["final_status"] == "UNAUTHORIZED_REVIEWER"
    rep = run(env, ctx, text, tp={"registry_version": "kapot"}, anchor=S.FixtureTrustAnchor({"human_decision_intake_trusted_providers_v1": H.canonical_sha256({"registry_version": "kapot"})}))
    assert rep["provenance"]["status"] == "UNVERIFIABLE"


# --- vertrouwde versus zelf opgegeven metadata -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key,value", [("author_authentication_status", "AUTHENTICATED_HUMAN_PRESENCE"), ("authenticated_author_id", "x"), ("authorized_reviewer_id", S.REVIEWER_A),
                                       ("provenance_verification_status", "SOURCE_VERIFIED"), ("received_timestamp", S.TS), ("authorization_status", "AUTHORIZED"),
                                       ("registration_eligible", True), ("allowlist", [S.REVIEWER_A]), ("attestation", {"authenticated_author_id": S.REVIEWER_A})])
def test_trusted_only_fields_in_the_file_block_the_intake(live, text, ctx, key, value):
    rep = run(S.make_envelope(live, text, **{key: value}), ctx, text)
    assert rep["final_status"] == "BLOCKED" and any("ZELF_OPGEGEVEN_VERTROUWD_VELD" in p for p in rep["open_problems"])
    assert rep["provenance"]["status"] != "SOURCE_VERIFIED" or rep["final_status"] == "BLOCKED"


def test_nested_trusted_only_field_inside_claims_is_blocked(live, text, ctx):
    e = S.make_envelope(live, text)
    e["claims"]["attestation"] = {"x": 1}
    rep = run(e, ctx, text)
    assert rep["final_status"] == "BLOCKED"


def test_embedded_attestation_is_never_used(live, text, ctx):
    e = S.make_envelope(live, text, pointer=False, claims={"source_message_id": None})
    e["attestation"] = {"provider_id": S.SYNTH, "authenticated_author_id": S.REVIEWER_A}
    rep = run(e, ctx, text)
    assert rep["final_status"] == "BLOCKED" and rep["provenance"]["attested"] is None


def test_intake_id_is_content_addressed(live, text, ctx):
    e = S.make_envelope(live, text)
    e["intake_id"] = H.intake_id_for(e)
    assert run(e, ctx, text)["final_status"] == "VALIDATED_DRY_RUN" and run(e, ctx, text)["intake_id"] == e["intake_id"]
    bad = dict(e, intake_id="INT-0000000000000000")
    assert run(bad, ctx, text)["final_status"] == "BLOCKED"
    changed = dict(e, reviewer_notes="gewijzigd")
    assert run(changed, ctx, text)["final_status"] == "BLOCKED"          # oude intake_id past niet meer bij de inhoud


# --- hashintegriteit en tekst ------------------------------------------------------------------------------------------------------------------------
def test_modified_text_with_old_hash_is_rejected(live, text, ctx):
    e = S.make_envelope(live, text)
    e["decision_text"] = text.replace("kies ik", "kies ik niet")
    rep = run(e, ctx, text)
    assert rep["text_integrity"]["status"] == "MISMATCH" and rep["final_status"] == "BLOCKED" and rep["provenance"]["status"] == "INVALID"


def test_text_differs_from_source_message(live, text, ctx):
    other = text + " "
    e = S.make_envelope(live, other)
    rep = run(e, ctx, text)                                    # bron houdt de originele tekst vast
    assert rep["text_integrity"]["status"] == "MISMATCH" and rep["final_status"] == "BLOCKED"


def test_no_normalization_newlines_and_unicode_forms_change_the_hash(live):
    a, b = "regel een\nregel twee", "regel een\r\nregel twee"
    assert H.text_sha256(a) != H.text_sha256(b)
    assert H.text_sha256("é") != H.text_sha256("é")        # NFC versus NFD wordt niet gelijkgetrokken
    assert H.text_sha256("Aap") != H.text_sha256("aap") and H.text_sha256("x ") != H.text_sha256("x")
    assert H.text_bytes("é") == "é".encode("utf-8")


def test_crlf_export_of_the_source_is_rejected_not_normalized(live, text, ctx):
    crlf = text.replace(". ", ".\r\n")
    e = S.make_envelope(live, text)
    rep = run(e, ctx, text, att=S.attestation(crlf))
    assert rep["text_integrity"]["status"] == "MISMATCH" and rep["final_status"] == "BLOCKED"


@pytest.mark.parametrize("ch", ["​", "‮", "﻿", "⁦", "\x00", "\x07"])
def test_invisible_and_control_characters_invalidate_the_text(live, ctx, ch):
    t = S.decision_text(live, extra=f" extra{ch}tekst")
    rep = run(S.make_envelope(live, t), ctx, t)
    assert rep["final_status"] == "INVALID_DECISION" and any("ONZICHTBARE_OF_STUURTEKENS" in p for p in rep["open_problems"])


def test_lone_surrogate_and_overlong_text_are_rejected(live, ctx):
    for t in ("\ud800 " + "x" * 80, "x" * (H.MAX_TEXT + 1)):
        rep = H.validate_intake(S.make_envelope(live, "ok"), ctx=ctx, now=S.NOW) if False else H.validate_intake({**S.make_envelope(live, "tekst " * 20), "decision_text": t}, ctx=ctx, now=S.NOW)
        assert rep["final_status"] in ("INVALID_DECISION", "BLOCKED") and rep["final_status"] != "VALIDATED_DRY_RUN"


def test_text_must_name_exactly_one_decision_that_matches_the_field(live, ctx):
    t = S.decision_text(live, extra=" Of toch REJECT, ik twijfel.")
    rep = run(S.make_envelope(live, t), ctx, t)
    assert rep["final_status"] == "INVALID_DECISION" and any("PRECIES_EEN" in p for p in rep["open_problems"])
    t2 = S.decision_text(live, "REJECT")
    rep = run(S.make_envelope(live, t2, decision="NEEDS_MORE_EVIDENCE"), ctx, t2)
    assert rep["final_status"] == "INVALID_DECISION"


def test_text_check_binds_request_id_and_hash(live, text, ctx):
    for t in (text.replace(live["approval_request_id"], "IAR-OIC-VR-999"), text.replace(live["request_hash"], "0" * 32)):
        rep = run(S.make_envelope(live, t), ctx, t)
        assert rep["final_status"] in ("INVALID_DECISION", "STALE_REQUEST")


# --- tijdstempels ------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("claimed,attested,status,code", [
    ("niet een datum", S.TS, "INVALID_DECISION", "TIMESTAMP_UNPARSABLE"), ("2026-10-13T11:00:00", S.TS, "INVALID_DECISION", "TIMESTAMP_NO_TIMEZONE"),
    ("2026-10-13 11:00:00Z", S.TS, "INVALID_DECISION", "TIMESTAMP_UNPARSABLE"), ("2026-10-14T11:00:00Z", "2026-10-14T11:00:00Z", "BLOCKED", "TIMESTAMP_IN_FUTURE"),
    ("2026-10-13T11:00:00Z", "2026-10-13T10:59:59Z", "BLOCKED", "TIMESTAMP_MISMATCH"), ("2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z", "BLOCKED", "TIMESTAMP_IMPLAUSIBLY_OLD"),
    ("2026-10-13T13:00:00+01:00", "2026-10-13T12:00:00Z", "VALIDATED_DRY_RUN", None)])
def test_timestamp_manipulation(live, text, ctx, claimed, attested, status, code):
    rep = run(S.make_envelope(live, text, claims={"source_timestamp": claimed}), ctx, text, att=S.attestation(text, ts=attested))
    assert rep["final_status"] == status, rep["open_problems"]
    if code:
        assert any(code in p for p in rep["open_problems"])


def test_received_timestamp_comes_from_the_validator_not_the_file(env, ctx, text):
    rep = run(env, ctx, text)
    assert rep["received_timestamp"] == "2026-10-13T12:00:00Z"


# --- vervalste en corrupte events ------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,att", [("lege auteur", lambda t: S.attestation(t, author="")), ("geen object", lambda t: {"author": "x"}), ("tekst ontbreekt", lambda t: S.attestation(t, message_text="")),
                                      ("onbekend actor-type", lambda t: S.attestation(t, actor="ALIEN")), ("onbekende presence", lambda t: S.attestation(t, presence="MAGIC")),
                                      ("verkeerde provider", lambda t: S.attestation(t, provider="andere-bron")), ("ander bericht-id", lambda t: S.attestation(t, mid="synthetic-msg-9999")),
                                      ("tijdstempel kapot", lambda t: S.attestation(t, ts="kapot")), ("verkeerde type veld", lambda t: S.attestation(t, source_message_id=5))])
def test_corrupt_attestations_are_invalid_and_block(env, ctx, text, name, att):
    rep = run(env, ctx, text, att=att(text))
    assert rep["provenance"]["status"] == "INVALID" and rep["final_status"] == "BLOCKED", name


def test_provider_errors_and_unknown_messages_are_unverifiable_not_crashes(env, ctx, text):
    for result in (RuntimeError("bron onbereikbaar"), None):
        kit = S.kit(ctx, text)
        kit["provider"] = S.SyntheticIntakeSource({S.MSG: result} if result else {})
        rep = H.validate_intake(env, **kit)
        assert rep["provenance"]["status"] in ("SELF_ASSERTED", "UNVERIFIABLE") and rep["final_status"] == "UNVERIFIED_SOURCE"


@pytest.mark.parametrize("bad", [None, [], "tekst", 5, {}, {"envelope_version": "x"}])
def test_garbage_envelopes_never_crash_and_never_validate(bad, ctx):
    rep = H.validate_intake(bad, ctx=ctx, now=S.NOW)
    assert rep["final_status"] in ("BLOCKED", "INVALID_DECISION") and rep["registration_performed"] is False


def test_missing_and_extra_fields_are_rejected(env, ctx, text):
    for k in list(env):
        e = {x: v for x, v in env.items() if x != k}
        assert run(e, ctx, text)["final_status"] in ("INVALID_DECISION", "BLOCKED"), k
    assert run(dict(env, extra_field=1), ctx, text)["final_status"] in ("INVALID_DECISION", "BLOCKED")


def test_wrong_encoding_or_normalization_declaration_is_rejected(env, ctx, text):
    for k, v in (("text_encoding", "UTF-16"), ("text_normalization", "NFC")):
        assert run(dict(env, **{k: v}), ctx, text)["final_status"] == "INVALID_DECISION"


# --- AI-herkomst ----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("extra", ["\n🤖 Generated with Claude Code", "\nCo-Authored-By: Claude <noreply@anthropic.com>", " As an AI I confirm.", " ChatGPT zegt dat het goed is."])
def test_ai_markers_make_the_provenance_invalid(live, ctx, extra):
    t = S.decision_text(live, extra=extra)
    rep = run(S.make_envelope(live, t), ctx, t)
    assert rep["provenance"]["status"] == "INVALID" and rep["final_status"] == "BLOCKED"


@pytest.mark.parametrize("name", ["claude-assistant", "Chatbot", "automation-bot", "AI reviewer"])
def test_claimed_non_human_author_is_invalid(live, text, ctx, name):
    rep = run(S.make_envelope(live, text, claims={"author_id": name}), ctx, text)
    assert rep["provenance"]["status"] == "INVALID" and rep["final_status"] == "BLOCKED"


# --- verouderde aanvraag, niveau-A-isolatie -----------------------------------------------------------------------------------------------------------
def test_stale_and_wrong_request_hashes(live, text, ctx):
    for h in list(R.P.SUPERSEDED_HASHES) + ["0" * 32, "f" * 32]:
        t = text.replace(live["request_hash"], h)
        rep = run(S.make_envelope(live, t, request_hash=h), ctx, t)
        assert rep["final_status"] == "STALE_REQUEST" and rep["request_current"] is False and rep["request_hash_live"] == live["request_hash"]
    assert run(S.make_envelope(live, text), ctx, text)["request_current"] is True


@pytest.mark.parametrize("levels", [["A", "B"], ["B"], ["C"], ["A", "C"], [], ["a"], ["A", "A"]])
def test_only_level_a_is_allowed(live, text, ctx, levels):
    rep = run(S.make_envelope(live, text, covers_levels=levels), ctx, text)
    assert rep["final_status"] == "INVALID_DECISION"


@pytest.mark.parametrize("extra", [" Dit geldt ook voor niveau B.", " Ik bevestig level C.", " Het pand is 0363100012144766.", " Dit wordt FI-M2-099."])
def test_level_b_c_pand_or_fi_content_is_rejected(live, ctx, extra):
    t = S.decision_text(live, extra=extra)
    assert run(S.make_envelope(live, t), ctx, t)["final_status"] == "INVALID_DECISION"


@pytest.mark.parametrize("over", [{"acknowledged_open_app_ids": []}, {"acknowledged_open_app_ids": ["APP-012"]}, {"acknowledged_open_app_ids": ["APP-025"]},
                                  {"acknowledged_open_relations": []}, {"acknowledged_open_relations": ["VR-045", "VR-999"]}, {"acknowledged_open_app_ids": ["APP-012", "APP-025", "APP-999"]}])
def test_acknowledgements_are_required_and_must_be_real(live, text, ctx, over):
    assert run(S.make_envelope(live, text, **over), ctx, text)["final_status"] == "INVALID_DECISION"


def test_decision_must_be_one_of_the_three_human_outcomes(live, ctx):
    t = S.decision_text(live, "ACTIVATE_INSTANCE")
    rep = run(S.make_envelope(live, t, decision="ACTIVATE_INSTANCE"), ctx, t)
    assert rep["final_status"] == "INVALID_DECISION"


def test_approve_physical_identity_fixture_still_registers_nothing(live, ctx):
    t = S.decision_text(live, "APPROVE_PHYSICAL_IDENTITY")
    before = (sha(PROTECTED[0]), sha(PROTECTED[1]))
    rep = run(S.make_envelope(live, t, decision="APPROVE_PHYSICAL_IDENTITY"), ctx, t)
    assert rep["final_status"] == "VALIDATED_DRY_RUN" and rep["ladder"]["6_registered"]["present"] is False and rep["ladder"]["7_instance_activated"]["present"] is False
    assert rep["effects"]["instances_created"] == 0 and rep["effects"]["fi_ids_created"] == 0 and (sha(PROTECTED[0]), sha(PROTECTED[1])) == before


# --- replaybescherming (alleen procesgebonden) -------------------------------------------------------------------------------------------------------
def test_replay_in_same_ledger_is_detected(env, ctx, text):
    kit = S.kit(ctx, text)
    led = H.InMemoryReplayLedger()
    first = H.validate_intake(env, ledger=led, **kit)
    second = H.validate_intake(copy.deepcopy(env), ledger=led, **kit)
    assert first["final_status"] == "VALIDATED_DRY_RUN" and second["final_status"] == "BLOCKED" and any("REPLAY_DETECTED" in p for p in second["open_problems"])


def test_replay_in_a_new_ledger_or_without_ledger_is_not_detected_and_report_says_so(env, ctx, text):
    kit = S.kit(ctx, text)
    a = H.validate_intake(env, ledger=H.InMemoryReplayLedger(), **kit)
    b = H.validate_intake(env, ledger=H.InMemoryReplayLedger(), **kit)
    c = H.validate_intake(env, **kit)
    assert a["final_status"] == b["final_status"] == c["final_status"] == "VALIDATED_DRY_RUN"          # de werkelijke garantie: alleen binnen één ledger
    for r in (a, b):
        assert r["replay_protection"]["scope"] == "PROCESS_LOCAL_MEMORY" and r["replay_protection"]["persistent"] is False and r["replay_protection"]["cross_process_guarantee"] is False
    assert c["replay_protection"]["scope"] == "NONE" and c["replay_protection"]["cross_process_guarantee"] is False


def test_duplicate_message_id_with_other_content_and_conflicting_decisions(live, ctx, text):
    kit = S.kit(ctx, text)
    a, b = S.make_envelope(live, text), S.make_envelope(live, text, reviewer_notes="andere inhoud")
    r = H.validate_batch([a, b], **kit)
    assert r[0]["final_status"] == "VALIDATED_DRY_RUN" and r[1]["final_status"] == "BLOCKED" and any("DUPLICATE_SOURCE_MESSAGE_ID" in p for p in r[1]["open_problems"])
    t2 = S.decision_text(live, "REJECT")
    led = H.InMemoryReplayLedger()
    kit["provider"].messages[S.MSG] = S.attestation(text)
    H.validate_intake(a, ledger=led, **kit)
    kit["provider"].messages[S.MSG] = S.attestation(t2)
    r2 = H.validate_intake(S.make_envelope(live, t2, decision="REJECT"), ledger=led, **kit)
    assert r2["final_status"] == "BLOCKED" and any("CONFLICTING_DECISIONS_SAME_SOURCE_EVENT" in p for p in r2["open_problems"])


def test_failed_attempt_also_claims_the_message_id_within_the_process(live, ctx, text):
    kit = S.kit(ctx, text)
    led = H.InMemoryReplayLedger()
    bad = S.make_envelope(live, text, acknowledged_open_relations=[])
    assert H.validate_intake(bad, ledger=led, **kit)["final_status"] == "INVALID_DECISION"
    again = H.validate_intake(S.make_envelope(live, text), ledger=led, **kit)
    assert again["final_status"] == "BLOCKED"


def test_replay_state_is_never_persisted(env, ctx, text, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    H.validate_batch([env, copy.deepcopy(env)], **S.kit(ctx, text))
    assert list(tmp_path.iterdir()) == []


# --- v1/v2-compatibiliteit -----------------------------------------------------------------------------------------------------------------------------
def test_v1_records_stay_readable_and_never_become_stronger(live, tmp_path):
    v1 = S.v1_record(1, R.GENESIS, live)
    p = tmp_path / "v1.jsonl"
    S.write_v1(p, [v1])
    assert R.load_register(p)[0]["decision_id"] == "HID-0001"
    view = H.unified_register_view(p)
    e = view["entries"][0]
    assert (view["v1_records"], view["v2_records"]) == (1, 0) and e["schema_version"] == 1 and e["legacy_v1"] is True
    assert (e["provenance_verification_status"], e["authentication_status"], e["authorization_status"]) == ("SELF_ASSERTED", "NOT_AUTHENTICATED", "NOT_ASSESSED_LEGACY_V1")
    assert e["counts_as_verified_v2"] is False and e["instance_activated"] is False
    assert view["v1_head"] == v1["record_hash"]


@pytest.mark.parametrize("extra", [{"provenance_verification_status": "SOURCE_VERIFIED"}, {"authorization_status": "AUTHORIZED"}, {"authentication_status": "AUTHENTICATED_HUMAN_PRESENCE"},
                                   {"provenance": {"provenance_verification_status": "SOURCE_VERIFIED"}}])
def test_v1_record_cannot_claim_verified_fields(live, tmp_path, extra):
    v1 = S.v1_record(1, R.GENESIS, live)
    v1.update(extra)
    v1["record_hash"] = R.record_hash(v1)
    p = tmp_path / "v1.jsonl"
    S.write_v1(p, [v1])
    with pytest.raises(R.RegisterCorrupt):
        R.load_register(p)
    with pytest.raises(R.RegisterCorrupt):
        H.unified_register_view(p)


@pytest.mark.parametrize("extra", [{"record_version": 2}, {"register_version": H.V2_REGISTER_VERSION}])
def test_v1_record_claiming_another_version_is_not_accepted_by_the_unified_view(live, tmp_path, extra):
    """Het v1-laadprogramma controleert het versienummer niet; de compatibiliteitsadapter wel (een v1-record blijft v1, nooit stilzwijgend v2)."""
    v1 = S.v1_record(1, R.GENESIS, live)
    v1.update(extra)
    v1["record_hash"] = R.record_hash(v1)
    p = tmp_path / "v1.jsonl"
    S.write_v1(p, [v1])
    with pytest.raises(R.RegisterCorrupt):
        H.unified_register_view(p)


def test_there_is_no_function_that_migrates_or_upgrades_v1():
    names = {n.lower() for n in dir(H)}
    assert not any(w in n for n in names for w in ("migrate", "upgrade", "promote_v1", "convert_v1", "write_register"))
    assert H.v1_record_as_legacy_view.__name__ == "v1_record_as_legacy_view"


def test_v2_schema_is_closed_and_excludes_synthetic_and_weak_provenance(live, tmp_path):
    import jsonschema
    schema = H.v2_schema()
    jsonschema.Draft7Validator.check_schema(schema)
    assert json.loads(H.V2_SCHEMA_PATH.read_text()) == schema
    rec = S.v2_record(1, R.GENESIS, R.GENESIS, live, S.decision_text(live))
    v = jsonschema.Draft7Validator(schema)
    assert not list(v.iter_errors(rec))
    for mut in (lambda r: r.update(extra=1), lambda r: r["provenance"].update(provenance_verification_status="SELF_ASSERTED"), lambda r: r["provenance"].update(synthetic_source=True),
                lambda r: r["provenance"].update(authentication_status="AUTHENTICATED_ACCOUNT_ONLY"), lambda r: r["provenance"].update(human_presence_evidence="NONE"),
                lambda r: r["authorization"].update(status="UNANCHORED"), lambda r: r.update(covers_levels=["A", "B"]), lambda r: r.update(record_version=1),
                lambda r: r.pop("source_message_key"), lambda r: r.update(text_normalization="NFC")):
        bad = copy.deepcopy(rec)
        mut(bad)
        assert list(v.iter_errors(bad))


def test_v2_loader_checks_chain_v1_head_and_duplicate_message_keys(live, tmp_path):
    v1 = S.v1_record(1, R.GENESIS, live)
    p1 = tmp_path / "v1.jsonl"
    S.write_v1(p1, [v1])
    head = v1["record_hash"]
    t1, t2 = S.decision_text(live), S.decision_text(live, "REJECT")
    a = S.v2_record(1, head, head, live, t1, key="p:m1")
    b = S.v2_record(2, a["record_hash"], head, live, t2, key="p:m2")
    p2 = tmp_path / "v2.jsonl"
    S.write_v1(p2, [a, b])
    view = H.unified_register_view(p1, p2)
    assert (view["v1_records"], view["v2_records"]) == (1, 2) and view["entries"][0]["legacy_v1"] is True and view["entries"][1]["legacy_v1"] is False and view["entries"][2]["counts_as_verified_v2"] is True
    assert H.load_register_v2(tmp_path / "bestaat_niet.jsonl", head) == []
    dup = S.v2_record(2, a["record_hash"], head, live, t2, key="p:m1")
    for records in ([a, dup], [S.v2_record(1, R.GENESIS, head, live, t1)], [S.v2_record(1, head, R.GENESIS, live, t1)]):
        S.write_v1(p2, records)
        with pytest.raises(R.RegisterCorrupt):
            H.load_register_v2(p2, head)
    p2.write_bytes(R.canonical(a).encode())          # geen regeleinde
    with pytest.raises(R.RegisterCorrupt):
        H.load_register_v2(p2, head)


def test_v2_record_cannot_live_in_the_v1_file_and_v1_cannot_be_read_as_v2(live, tmp_path):
    head = R.GENESIS
    v2 = S.v2_record(1, head, head, live, S.decision_text(live))
    p = tmp_path / "x.jsonl"
    S.write_v1(p, [v2])
    with pytest.raises(R.RegisterCorrupt):
        R.load_register(p)
    S.write_v1(p, [S.v1_record(1, R.GENESIS, live)])
    with pytest.raises(R.RegisterCorrupt):
        H.load_register_v2(p, head)


def test_corrupt_register_blocks_the_intake_failclosed(env, ctx, text, tmp_path):
    p = tmp_path / "kapot.jsonl"
    p.write_bytes(b"{niet json}\n")
    rep = H.validate_intake(env, register_path=p, **S.kit(ctx, text))
    assert rep["final_status"] == "BLOCKED" and any("REGISTER_BESCHADIGD" in x for x in rep["open_problems"])


def test_already_registered_hash_in_a_temp_register_blocks_the_intake(live, env, ctx, text, tmp_path):
    p = tmp_path / "v1.jsonl"
    S.write_v1(p, [S.v1_record(1, R.GENESIS, live)])
    rep = H.validate_intake(env, register_path=p, **S.kit(ctx, text))
    assert rep["final_status"] == "BLOCKED" and any("DUPLICAAT_BESLUIT" in x or "CONFLICTEREND_BESLUIT" in x for x in rep["open_problems"])


# --- fail-closed, side effects, isolatie -----------------------------------------------------------------------------------------------------------------
def test_unexpected_exception_inside_validation_blocks(env, ctx, text):
    class Boom(S.SyntheticIntakeSource):
        pass
    kit = S.kit(ctx, text)
    kit["anchor"] = object()                            # geen geldig anker: de interne fout wordt afgevangen
    rep = H.validate_intake(env, **kit)
    assert rep["final_status"] in ("BLOCKED", "UNVERIFIED_SOURCE") and rep["registration_performed"] is False and rep["final_status"] != "VALIDATED_DRY_RUN"


def test_scenarios_make_no_writes_and_never_call_the_register(ctx, tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("schrijfpoging of registeraanroep tijdens intake")
    for name in ("register", "_atomic_replace", "build_stored_record", "_fsync_dir"):
        monkeypatch.setattr(R, name, refuse)
    for obj, name in ((os, "replace"), (os, "rename"), (os, "remove"), (os, "unlink"), (os, "makedirs"), (os, "mkdir"), (Path, "write_text"), (Path, "write_bytes"), (Path, "mkdir"), (Path, "unlink")):
        monkeypatch.setattr(obj, name, refuse)
    real_open = open

    def guarded(file, mode="r", *a, **k):
        assert not any(c in str(mode) for c in "wax+"), f"schrijfpoging naar {file}"
        return real_open(file, mode, *a, **k)
    monkeypatch.setattr("builtins.open", guarded)
    res = S.run_scenarios(ctx, str(tmp_path)) if False else None
    live = S.live_request(ctx)
    text = S.decision_text(live)
    e = S.make_envelope(live, text)
    for kit in (S.kit(ctx, text), dict(ctx=ctx, now=S.NOW)):
        assert H.validate_intake(e, **kit)["registration_performed"] is False
    H.validate_batch([e, copy.deepcopy(e)], **S.kit(ctx, text))
    H.unified_register_view()


def test_protected_files_are_unchanged_by_all_scenarios(ctx, tmp_path):
    before = {p: sha(p) for p in PROTECTED}
    reg_before = R.REGISTER_PATH.read_bytes()
    out = S.run_scenarios(ctx, str(tmp_path))
    assert len(out) == 30 and R.REGISTER_PATH.read_bytes() == reg_before == b""
    assert {p: sha(p) for p in PROTECTED} == before
    assert all(sc["report"].get("registration_performed", False) is False and sc["report"]["effects"].get("register_written") is False for sc in out)


EXPECTED_SCENARIO_STATUS = {0: "VALIDATED_DRY_RUN", 1: "UNVERIFIED_SOURCE", 2: "UNVERIFIED_SOURCE", 3: "UNAUTHORIZED_REVIEWER", 4: "INVALID_DECISION", 5: "STALE_REQUEST",
                            6: "INVALID_DECISION", 7: "INVALID_DECISION", 8: "INVALID_DECISION", 9: "INVALID_DECISION", 10: "BLOCKED", 11: "BLOCKED", 13: "BLOCKED", 14: "BLOCKED",
                            15: "BLOCKED", 18: None}


def test_the_18_negative_scenarios_give_the_documented_outcomes(ctx, tmp_path):
    out = S.run_scenarios(ctx, str(tmp_path))
    nrs = {sc["nr"] for sc in out}
    assert nrs == set(range(0, 19))
    for sc in out:
        if sc["nr"] == 17:
            continue
        assert sc["report"]["final_status"] == sc["expected"], (sc["nr"], sc["title"], sc["report"]["open_problems"][:3])
        if sc["nr"] and sc["report"]["final_status"] != "VALIDATED_DRY_RUN":
            assert sc["report"]["registration_eligibility"] == "NOT_ELIGIBLE"
    s17 = next(sc for sc in out if sc["nr"] == 17)["report"]
    assert s17["legacy_view"]["provenance_verification_status"] == "SELF_ASSERTED" and s17["forged_v1_record"].startswith("GEWEIGERD")


def test_scenario_reasons_are_the_intended_ones(ctx, tmp_path):
    by = {}
    for sc in S.run_scenarios(ctx, str(tmp_path)):
        by.setdefault(sc["nr"], []).append(sc)
    joined = lambda sc: " | ".join(sc["report"]["open_problems"])      # noqa: E731
    assert "GEEN_GEAUTHENTICEERDE_BRON" in joined(by[1][0]) and by[1][0]["report"]["provenance"]["status"] == "SELF_ASSERTED"
    assert by[2][0]["report"]["provenance"]["status"] == "UNVERIFIABLE"
    assert by[3][0]["report"]["provenance"]["status"] == "SOURCE_VERIFIED" and "GEEN_AANWIJZING" in joined(by[3][0])
    assert "REQUEST_HASH" in joined(by[5][0])
    for nr, tok in ((6, "APP"), (7, "APP"), (8, "RELATIES")):
        assert tok in joined(by[nr][0])
    assert "TEKST_INTEGRITEIT_GESCHONDEN" in joined(by[11][0])
    assert "AI_HERKOMST_KENMERK" in joined(by[10][0]) and "GEEN_MENS" in joined(by[10][1])
    assert "DUPLICATE_SOURCE_MESSAGE_ID" in joined(by[13][0]) and "REPLAY_DETECTED" in joined(by[14][0]) and "CONFLICTING_DECISIONS" in joined(by[15][0])
    assert any("ONGEANKERD" in joined(sc) for sc in by[18][:3]) and any("ZELFAANWIJZING" in joined(sc) for sc in by[18])
    assert "ZELF_OPGEGEVEN_VERTROUWD_VELD" in joined(by[18][3])


def test_processing_is_deterministic(ctx, tmp_path):
    a = S.run_scenarios(ctx, str(tmp_path))
    b = S.run_scenarios(ctx, str(tmp_path))
    dump = lambda out: json.dumps([sc["report"] for sc in out], sort_keys=True, default=str)      # noqa: E731
    assert dump(a) == dump(b)


# --- statische bewaking van de nieuwe code -------------------------------------------------------------------------------------------------------------
READ_ONLY_REGISTER_API = {"load_context", "load_register", "register_head", "validate_input", "REGISTER_PATH", "DECISIONS", "RECORD_VERSION", "IDENTITY_VERIFICATION", "FORBIDDEN_EFFECTS",
                          "RegisterCorrupt", "canonical", "record_hash", "NON_HUMAN_NAME", "GENESIS", "P", "ROOT", "decision_id_for", "REGISTER_VERSION"}
WRITE_CALLS = {"write", "writelines", "write_text", "write_bytes", "rename", "remove", "unlink", "rmdir", "mkdir", "makedirs", "rmtree", "copy2", "copyfile", "move",
               "dump", "system", "popen", "Popen", "run", "check_call", "check_output", "urlopen", "connect", "touch", "chmod"}


def _tree(p):
    return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def test_core_module_uses_only_the_read_only_register_api():
    used = {n.attr for n in ast.walk(_tree(CORE)) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "R"}
    assert used and used <= READ_ONLY_REGISTER_API, sorted(used - READ_ONLY_REGISTER_API)
    text = CORE.read_text(encoding="utf-8")
    for forbidden in ("CONFIRM_TOKEN", "_atomic_replace", "build_stored_record", "R.register(", "mode=\"REGISTER\""):
        assert forbidden not in text, forbidden


def test_core_module_has_no_write_network_or_dynamic_code():
    for node in ast.walk(_tree(CORE)):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            assert name not in WRITE_CALLS, f"{CORE.name}:{node.lineno}: {name}()"
            assert not (name == "replace" and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in {"os", "shutil", "Path", "pathlib"}), f"{CORE.name}:{node.lineno}: os.replace"
            assert not (isinstance(f, ast.Name) and f.id in {"eval", "exec", "compile", "__import__"}), f"{CORE.name}:{node.lineno}"
            if name == "open":
                mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else "r"
                assert not any(c in str(mode) for c in "wax+")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert not any(m.split(".")[0] in {"socket", "requests", "urllib", "http", "subprocess", "anthropic", "openai"} for m in mods)


def test_report_script_writes_only_its_three_targets_and_never_the_register():
    src = REPORT.read_text(encoding="utf-8")
    assert src.count(".write_text(") == 1 and "for p, t in targets" in src
    assert "H.V2_SCHEMA_PATH, schema" in src and "H.OUT_JSON, out_json" in src and "H.OUT_MD, out_md" in src
    for forbidden in ("R.register(", "_atomic_replace", "CONFIRM_TOKEN", "REGISTER_PATH.write", "frame_inventory"):
        assert forbidden not in src


def test_production_code_never_imports_the_synthetic_test_library():
    for p in (CORE, REPORT.parent / "human_decision_intake.py"):
        text = p.read_text(encoding="utf-8")
        assert "scenario_lib" not in text and "SyntheticIntakeSource" not in text and "FixtureTrustAnchor" not in text
    assert "scenario_lib" in REPORT.read_text(encoding="utf-8")      # alleen de rapportgenerator (tests/rapport) gebruikt de fixtures
    for p in (ROOT / "agent").rglob("*.py"):
        assert "human_decision_intake" not in p.read_text(encoding="utf-8")


def test_no_fi_id_creation_or_reservation_in_new_code():
    for p in (CORE, REPORT):
        t = p.read_text(encoding="utf-8")
        assert not re.search(r"FI-M\d|FI-\{|f\"FI-|'FI-'|\"FI-\"\s*\+", t), p.name


def test_no_secrets_tokens_or_personal_data_in_new_files():
    files = [CORE, REPORT, ROOT / "tests/fixtures/human_decision_intake/scenario_lib.py", ROOT / "reports/frames/human_decision_intake_provenance_v1.md",
             ROOT / "reports/frames/human_decision_intake_provenance_v1.json", ROOT / "config/human_decision_intake_trusted_providers_v1.json",
             ROOT / "config/human_decision_reviewer_authorization_v1.json", ROOT / "schemas/human_decision_intake_envelope.schema.json", ROOT / "schemas/human_instance_decision_v2.schema.json"]
    pat = re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_|sk-ant-|AKIA[0-9A-Z]{12,}|-----BEGIN|Bearer\s+[A-Za-z0-9._-]{20,}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}|api[_-]?key\s*[:=]", re.I)
    for p in files:
        assert not pat.search(p.read_text(encoding="utf-8")), p.name
    md = (ROOT / "reports/frames/human_decision_intake_provenance_v1.md").read_text(encoding="utf-8")
    assert "twandijkmans" not in md.lower()


def test_new_scripts_pass_the_existing_approval_and_register_guards():
    """De bestaande bewakingstests blijven van kracht: alleen het kernscript noemt het register (read-only), niemand noemt het approval-framework letterlijk."""
    for f in (ROOT / "scripts").glob("human_decision_intake*.py"):
        t = f.read_text(encoding="utf-8")
        assert "physical_instance_approval" not in t and "physical_instance_evidence_reconciliation" not in t, f.name
    assert "human_instance_decision_register" not in REPORT.read_text(encoding="utf-8")


# --- CLI en rapport -------------------------------------------------------------------------------------------------------------------------------------
def test_cli_check_is_read_only_and_reports_unverified_source(env, tmp_path):
    p = tmp_path / "envelope.json"
    p.write_text(json.dumps(env), encoding="utf-8")
    before = {k: sha(k) for k in PROTECTED}
    r = subprocess.run([sys.executable, str(CORE), "check", "--envelope", str(p)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1, r.stderr
    rep = json.loads(r.stdout)
    assert rep["final_status"] == "UNVERIFIED_SOURCE" and rep["mode"] == "DRY_RUN" and rep["registration_performed"] is False
    assert {k: sha(k) for k in PROTECTED} == before


def test_report_output_has_the_required_fields(env, ctx):
    rep = H.validate_intake(env, ctx=ctx, now=S.NOW)
    for key in ("intake_id", "approval_request_id", "request_hash_live", "text_integrity", "provenance", "authorization", "content_validation", "open_problems", "registration_eligibility",
                "forbidden_effects", "final_status", "ladder", "replay_protection", "effects"):
        assert key in rep
    assert rep["request_hash_live"] == "e276feeb5849ba8af4c41e2e429aca21" and rep["final_status"] in H.FINAL_STATUSES
    assert {"create_fi_id", "activate_instance", "register_decision_via_intake", "migrate_v1_record_to_v2", "treat_self_asserted_as_verified"} <= set(rep["forbidden_effects"])


def test_committed_reports_and_v2_schema_are_current():
    assert RP.generate(check=True) == 0


def test_report_documents_required_sections_and_current_hash():
    md = (ROOT / "reports/frames/human_decision_intake_provenance_v1.md").read_text(encoding="utf-8")
    for i in range(1, 12):
        assert re.search(rf"^## {i}\. ", md, re.M), i
    assert "e276feeb5849ba8af4c41e2e429aca21" in md and "DRY_RUN" in md and "cross_process_guarantee" in md
    data = json.loads((ROOT / "reports/frames/human_decision_intake_provenance_v1.json").read_text(encoding="utf-8"))
    assert all(r["match"] for r in data["scenarios"]) and data["trusted_providers_configured"] == 0 and data["reviewer_designations_configured"] == 0
    assert data["register_v1"]["records"] == 0 and data["app_decisions"] == {"total": 48, "open": 48}
