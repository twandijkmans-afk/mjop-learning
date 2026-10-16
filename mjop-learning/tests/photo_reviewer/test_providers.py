import copy
import json
import sys

import pytest

from agent.photo import providers as P
from agent.photo.consent import ENV_CONFIRM, consent_problems
from agent.photo.contract import sha256_bytes
from agent.photo.verifier import verify_or_raise

import photo_support as S

NOW_OK = "2099-01-01T00:00:00Z"


def consent(**over):
    sha = sha256_bytes(S.png())
    rec = {"consent_id": "PCON-00001", "provider": "anthropic", "purpose": "synthetische test", "photos": [
        {"photo_id": "synthetic_facade_v1", "derivative_sha256": sha, "privacy_check": "ALLOW"}],
        "derivative_policy": {"exif_stripped": True, "max_long_edge_px": 1000, "media_type": "image/png", "max_file_bytes": 200000},
        "allowed_models": ["test-model-from-operator"],
        "valid_until": NOW_OK, "budget": {"max_calls": 1, "max_output_tokens": 4000},
        "terms_verified": {"retention_terms_checked": True, "training_use_checked": True, "data_processing_agreement_checked": True,
                           "checked_by": "tester", "checked_at": "2026-10-13T12:00:00Z"},
        "approved_by": {"reviewer_type": "human", "reviewer_id": "tester"}, "approved_at": "2026-10-13T12:00:00Z"}
    rec.update(over)
    return rec


def signed(**over):
    from photo_support import AUTH_KEY
    from agent.photo.safety_gate import sign_consent
    return sign_consent(consent(**over), AUTH_KEY)


class FakeMessages:
    def __init__(self, text, stop="end_turn"):
        self.text, self.stop, self.calls = text, stop, []

    def create(self, **kw):
        self.calls.append(kw)
        class B: type = "text"
        b = B(); b.text = self.text
        class M: pass
        m = M(); m.content = [b]; m.stop_reason = self.stop; m.model = "fake-model-served"
        return m


class FakeClient:
    def __init__(self, text, stop="end_turn"):
        self.messages = FakeMessages(text, stop)


def cfg(**over):
    d = dict(enabled=True, model="test-model-from-operator", max_tokens=2000)
    d.update(over)
    return P.ClaudeVisionConfig(**d)


GOOD_TEXT = json.dumps({"proposals": [{"element_type": "WINDOW_OPENING", "bbox_px": [64, 120, 141, 202], "visibility": "FULL",
                                       "uncertainties": [], "observation": "kozijnopening"}], "hidden_element_hypotheses": []})


# --- ReplayProvider ---------------------------------------------------------------------------------------------
def test_replay_is_reproducible_and_hashes_are_stable():
    a, b = S.proposal_set(), S.proposal_set()
    assert a == b and a["set_id"] == b["set_id"]
    assert a["provider"]["response_sha256"] == b["provider"]["response_sha256"]


def test_replay_without_recording_fails_closed():
    req = S.request()
    with pytest.raises(P.ProviderError) as ei:
        P.ReplayProvider({}).analyze(req)
    assert ei.value.code == "NO_RECORDING"


def test_replay_does_not_need_or_touch_the_image():
    req = S.request()
    req.image_bytes = None
    ps = P.build_proposal_set(req, P.ReplayProvider.from_file(S.FIX + "/synthetic_facade_v1_replay.json").analyze(req))
    verify_or_raise(ps)


def test_replay_result_is_a_copy():
    prov = P.ReplayProvider.from_file(S.FIX + "/synthetic_facade_v1_replay.json")
    req = S.request()
    r = prov.analyze(req)
    r.raw["proposals"].clear()
    assert prov.analyze(req).raw["proposals"]


# --- build_proposal_set: modellen kunnen geen invarianten zetten ---------------------------------------------------
@pytest.mark.parametrize("extra", [{"human_decision": "ACCEPT"}, {"review_status": "ACCEPTED"}, {"is_instance": True},
                                   {"bag_pand_id": "0363100012121455"}, {"cost": 5}])
def test_raw_response_with_forbidden_fields_is_refused(extra):
    req = S.request()
    raw = {"proposals": [{"element_type": "WINDOW_OPENING", "bbox_norm": [0.1, 0.1, 0.3, 0.3], "visibility": "FULL", "uncertainties": [],
                          "observation": "x", **extra}], "hidden_element_hypotheses": []}
    with pytest.raises(P.ProviderError):
        P.build_proposal_set(req, P.ProviderResult(raw, "0" * 64, P.NullProvider().describe() | {"model_served": None, "consent_ref": None, "prompt_id": None}))


def test_unknown_element_type_in_raw_response_refused():
    req = S.request()
    raw = {"proposals": [{"element_type": "SKYLIGHT", "bbox_norm": [0.1, 0.1, 0.3, 0.3], "visibility": "FULL", "uncertainties": [], "observation": "x"}]}
    with pytest.raises(P.ProviderError) as ei:
        P.build_proposal_set(req, P.ProviderResult(raw, "0" * 64, {"adapter_id": "t", "adapter_version": "1", "provider_name": "replay"}))
    assert ei.value.code == "UNKNOWN_ELEMENT_TYPE"


def test_observation_ids_are_deterministic_regardless_of_input_order():
    prov = P.ReplayProvider.from_file(S.FIX + "/synthetic_facade_v1_replay.json")
    req = S.request()
    r = prov.analyze(req)
    rev = copy.deepcopy(r)
    rev.raw["proposals"].reverse()
    assert P.build_proposal_set(req, r)["proposals"] == P.build_proposal_set(req, rev)["proposals"]


# --- HumanImportProvider --------------------------------------------------------------------------------------------
def test_human_import_of_existing_annotation_keeps_proposals_undecided():
    import os
    from agent.photo.contract import PROJECT_ROOT
    with open(os.path.join(PROJECT_ROOT, "data/photo_evidence/maldenhof_2_frame_annotation_v1.json"), encoding="utf-8") as f:
        doc = json.load(f)
    prov = P.HumanImportProvider.from_frame_annotation(doc)
    sha = "ab" * 32
    req = P.VisionRequest("maldenhof_2", doc["photo"]["sha256"], sha, 2048, 1536, derivative_transform=("MOCK_NO_IMAGE",))
    ps = P.build_proposal_set(req, prov.analyze(req))
    res = verify_or_raise(ps)
    assert res.ok and ps["provider"]["provider_name"] == "human_import"
    assert all(p["human_decision"] is None and p["review_status"] == "PROPOSED" for p in ps["proposals"])
    assert len(ps["proposals"]) == len(doc["candidates"])


def test_human_import_rejects_unknown_candidate_type():
    with pytest.raises(P.ProviderError):
        P.HumanImportProvider.from_frame_annotation({"candidates": [{"candidate_id": "X", "candidate_type": "SPACESHIP", "bbox_norm": [0, 0, 1, 1], "visibility": "FULL"}]})


def test_null_provider_returns_nothing():
    req = S.request()
    ps = P.build_proposal_set(req, P.NullProvider().analyze(req))
    assert ps["proposals"] == [] and verify_or_raise(ps).ok


# --- ClaudeVisionProvider: standaard uit; alle echte controles staan in test_safety_gate.py ----------------------------------
def test_claude_provider_is_disabled_by_default_and_never_imports_sdk():
    sys.modules.pop("anthropic", None)
    with pytest.raises(P.ProviderError) as ei:
        P.ClaudeVisionProvider().analyze(S.request())
    assert ei.value.code == "PROVIDER_DISABLED" and "anthropic" not in sys.modules


def test_claude_provider_has_no_builtin_model_or_limits():
    with pytest.raises(P.ProviderError) as ei:
        P.ClaudeVisionProvider(P.ClaudeVisionConfig(enabled=True), signed()).analyze(S.request())
    assert ei.value.code == "CONFIG_INCOMPLETE" and "model" in ei.value.message + " ".join(ei.value.details)


def test_claude_provider_is_blocked_in_this_release_even_with_everything_else_valid(approved_gate, monkeypatch):
    """Productiestand: de provider staat op NOT_APPROVED; geldig record, sleutels en grootboek helpen niet."""
    from agent.photo import safety_gate as G
    monkeypatch.setitem(G.PROVIDER_APPROVALS, "anthropic", {"status": "NOT_APPROVED", "reason": "x"})
    client = FakeClient(GOOD_TEXT)
    with pytest.raises(G.GateRefusal) as ei:
        P.ClaudeVisionProvider(cfg(), signed(), client, approved_gate).analyze(S.request())
    assert ei.value.reasons == ["PROVIDER_NOT_APPROVED"] and client.messages.calls == []


def test_shipped_provider_register_has_no_approved_external_provider():
    from agent.photo import safety_gate as G
    assert G.PROVIDER_APPROVALS and all(v["status"] == "NOT_APPROVED" for v in G.PROVIDER_APPROVALS.values())


def test_claude_provider_with_full_authorization_uses_injected_client_only(approved_gate):
    client = FakeClient(GOOD_TEXT)
    prov = P.ClaudeVisionProvider(cfg(), signed(), client, approved_gate)
    req = S.request()
    res = prov.analyze(req)
    call = client.messages.calls[0]
    assert call["model"] == "test-model-from-operator" and call["max_tokens"] == 2000
    assert set(call) == {"model", "max_tokens", "messages"}                       # geen sampling/thinking/tools/tracing
    block = call["messages"][0]["content"][0]
    assert block["type"] == "image" and block["source"]["type"] == "base64" and block["source"]["media_type"] == "image/png"
    assert "addres" in P.PROMPT.lower() and "FI-" not in P.PROMPT                  # prompt bevat geen identiteitscontext
    ps = P.build_proposal_set(req, res)
    assert ps["provider"]["provider_name"] == "anthropic" and ps["provider"]["consent_ref"] == "PCON-00001"
    assert ps["provider"]["model_served"] == "fake-model-served"
    assert ps["proposals"][0]["bbox_norm"] == [0.1, 0.25, 0.2203, 0.4208]         # pixels -> genormaliseerd
    verify_or_raise(ps)
    assert approved_gate.usage("PCON-00001") == {"calls": 1, "tokens": 2000}


def test_claude_provider_consent_policy_cases(monkeypatch):
    monkeypatch.setenv(ENV_CONFIRM, "PCON-00001")
    req = S.request()
    kw = dict(provider="anthropic", photo_id=req.photo_id, derivative_sha256=req.derivative_sha256, derivative_long_edge_px=640,
              media_type="image/png", derivative_bytes_len=len(S.png()), model="test-model-from-operator", max_tokens=2000)
    assert consent_problems(signed(), **kw) == []
    assert consent_problems(signed(valid_until="2020-01-01T00:00:00Z"), **kw)
    deny = signed(); deny["photos"][0]["privacy_check"] = "DENY"
    assert consent_problems(deny, **kw)
    red = signed(); red["photos"][0]["privacy_check"] = "ALLOW_WITH_REDACTION"
    assert consent_problems(red, **kw)
    assert consent_problems(signed(), **dict(kw, derivative_sha256="0" * 64))
    assert consent_problems(signed(approved_by={"reviewer_type": "model", "reviewer_id": "x"}), **kw)
    unchecked = signed(); unchecked["terms_verified"]["training_use_checked"] = False
    assert consent_problems(unchecked, **kw)
    assert consent_problems(signed(), **dict(kw, model="ander-model"))
    assert consent_problems(signed(), **dict(kw, max_tokens=999_999))
    assert consent_problems(signed(), **dict(kw, derivative_bytes_len=10 ** 9))
    assert consent_problems(signed(), **dict(kw, derivative_bytes_len=None))
    dup = signed(); dup["photos"].append({"photo_id": "synthetic_facade_v1", "derivative_sha256": dup["photos"][0]["derivative_sha256"], "privacy_check": "DENY"})
    assert consent_problems(dup, **kw)                                              # DENY mag niet door een ALLOW-regel worden verborgen
    other = signed(); other["photos"].append({"photo_id": "andere_foto", "derivative_sha256": other["photos"][0]["derivative_sha256"], "privacy_check": "ALLOW"})
    assert consent_problems(other, **kw)


@pytest.mark.parametrize("text,stop", [("geen json", "end_turn"), (GOOD_TEXT, "refusal"), (GOOD_TEXT, "max_tokens"),
                                       (json.dumps({"proposals": [{"element_type": "WINDOW_OPENING"}]}), "end_turn")])
def test_unusable_responses_are_never_repaired(approved_gate, text, stop):
    with pytest.raises(P.ProviderError) as ei:
        P.ClaudeVisionProvider(cfg(), signed(), FakeClient(text, stop), approved_gate).analyze(S.request())
    assert ei.value.code == "UNUSABLE_RESPONSE"
    assert approved_gate.usage("PCON-00001")["calls"] == 1                          # verzonden call blijft verbruikt


def test_real_sdk_path_cannot_connect_in_tests(approved_gate, monkeypatch):
    """Zonder geinjecteerde client en zonder netwerk faalt de poging hard; bij ontbrekende SDK wordt de reservering vrijgegeven."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        with pytest.raises(P.ProviderError) as ei:
            P.ClaudeVisionProvider(cfg(), signed(), None, approved_gate).analyze(S.request())
        assert ei.value.code == "SDK_MISSING" and approved_gate.usage("PCON-00001")["calls"] == 0
    else:
        with pytest.raises(Exception):
            P.ClaudeVisionProvider(cfg(), signed(), None, approved_gate).analyze(S.request())


def test_documented_media_types_only():
    from agent.photo.contract import MEDIA_TYPES
    assert set(MEDIA_TYPES) == {"image/jpeg", "image/png", "image/gif", "image/webp"}
