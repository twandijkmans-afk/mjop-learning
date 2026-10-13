import copy

import pytest

from agent.photo.contract import PhotoError, load_schema, set_id_for
from agent.photo.verifier import verify_or_raise, verify_proposal_set

import photo_support as S


def codes(doc, **kw):
    return verify_proposal_set(doc, **kw).codes()


def mutate(fn):
    d = S.fresh()
    fn(d)
    return S.reseal(d)


def test_schemas_are_valid_draft7():
    import jsonschema
    for n in ("photo_proposal_set", "photo_quantity_state", "photo_dimension_input", "photo_consent_record"):
        jsonschema.Draft7Validator.check_schema(load_schema(n + ".schema.json"))


def test_valid_set_passes_with_full_provenance():
    d = S.proposal_set()
    res = verify_proposal_set(d, image_bytes=S.png(), image_size=(640, 480), source_registry={d["photo"]["photo_id"]: d["photo"]["source_sha256"]})
    assert res.ok, [str(e) for e in res.errors]
    assert d["set_id"] == set_id_for(d)
    assert all(p["review_status"] == "PROPOSED" and p["human_decision"] is None and p["is_instance"] is False
               and p["counts_in_any_total"] is False and p["bag_pand_id"] is None for p in d["proposals"])


@pytest.mark.parametrize("field,value", [("source_sha256", "abc"), ("derivative_sha256", "G" * 64), ("source_sha256", "A" * 64)])
def test_invalid_hash_formats_rejected(field, value):
    assert "SCHEMA" in codes(mutate(lambda d: d["photo"].__setitem__(field, value)))


def test_derivative_hash_must_match_image_bytes():
    assert "HASH_MISMATCH" in codes(S.proposal_set(), image_bytes=b"niet de afbeelding")


def test_source_registry_mismatch_and_unknown_photo():
    d = S.proposal_set()
    assert "PROVENANCE" in codes(d, source_registry={d["photo"]["photo_id"]: "0" * 64})
    assert "PROVENANCE" in codes(d, source_registry={})


def test_tampered_content_detected_by_set_id():
    d = S.fresh()
    d["proposals"][0]["observation"] = "aangepast na het verzegelen"
    assert "SET_ID_MISMATCH" in codes(d)


@pytest.mark.parametrize("box", [[0.5, 0.5, 0.4, 0.6], [0.1, 0.1, 0.1, 0.5], [-0.1, 0.1, 0.3, 0.3], [0.1, 0.1, 1.2, 0.3],
                                 [0.1, 0.1, 0.3], [0.1, 0.1, 0.1005, 0.3], [0.1, 0.1, float("nan"), 0.3]])
def test_bounding_box_validation(box):
    d = mutate(lambda x: x["proposals"][0].__setitem__("bbox_norm", box))
    assert {"BBOX", "SCHEMA"} & set(codes(d))


def test_duplicate_observation_id_and_duplicate_box():
    d = mutate(lambda x: x["proposals"][1].__setitem__("observation_id", x["proposals"][0]["observation_id"]))
    assert "DUPLICATE_OBSERVATION_ID" in codes(d)
    d = S.fresh()
    clone = copy.deepcopy(d["proposals"][0])
    clone["observation_id"] = "PO-099"
    clone["bbox_norm"] = [v + 0.002 for v in clone["bbox_norm"]]
    d["proposals"].append(clone)
    assert "DUPLICATE_BOX" in codes(S.reseal(d))


def test_sash_inside_opening_is_flagged_as_double_count():
    """Telsemantiek: een vast/draaiend deel binnen een kozijnopening is geen tweede opening."""
    d = S.fresh()
    big = d["proposals"][0]["bbox_norm"]
    w = big[2] - big[0]
    sash = copy.deepcopy(d["proposals"][0])
    sash.update(observation_id="PO-098", bbox_norm=[big[0] + 0.005, big[1] + 0.005, big[0] + w / 2, big[3] - 0.005])
    d["proposals"].append(sash)
    assert "PART_OF_OPENING" in codes(S.reseal(d))


def test_visible_quantity_other_than_one_rejected_with_semantics_message():
    d = mutate(lambda x: x["proposals"][0].__setitem__("visible_quantity", 2))
    res = verify_proposal_set(d)
    assert "COUNT_SEMANTICS" in res.codes()
    assert any("parts_visible" in e.message for e in res.errors)


def test_two_sashes_remain_one_opening():
    d = S.proposal_set()
    two = [p for p in d["proposals"] if p.get("parts_visible") == 2]
    assert len(two) == 1 and two[0]["visible_quantity"] == 1


def test_unknown_element_type_rejected():
    assert "SCHEMA" in codes(mutate(lambda d: d["proposals"][0].__setitem__("element_type", "SKYLIGHT")))


@pytest.mark.parametrize("field,value,code", [
    ("review_status", "ACCEPTED", "FORBIDDEN_DECISION"), ("human_decision", "ACCEPT", "FORBIDDEN_DECISION"),
    ("is_instance", True, "FORBIDDEN_DECISION"), ("counts_in_any_total", True, "FORBIDDEN_DECISION"),
    ("bag_pand_id", "0363100012121455", "FORBIDDEN_DECISION"), ("frame_instance_id", "FI-M2-099", "FORBIDDEN_FIELD"),
    ("cost", "120", "FORBIDDEN_FIELD"), ("gross_area_m2", "1.00", "FORBIDDEN_FIELD"), ("outer_width_m", "1.2", "FORBIDDEN_FIELD")])
def test_forbidden_decisions_and_fields_rejected(field, value, code):
    d = mutate(lambda x: x["proposals"][0].__setitem__(field, value))
    assert code in codes(d)


@pytest.mark.parametrize("text", ["goedgekeurd door beheerder", "kozijn FI-M2-001", "kosten €120", "oppervlak 1,2 m²", "houtrot zichtbaar",
                                  "NEN 2767 conditie 2", "vastgesteld als kozijn", "bevestigd"])
def test_forbidden_claims_in_free_text_rejected(text):
    assert "FORBIDDEN_CLAIM" in codes(mutate(lambda d: d["proposals"][0].__setitem__("observation", text)))


def test_partial_and_occluded_require_uncertainty():
    def f(d):
        p = next(x for x in d["proposals"] if x["visibility"] == "PARTIAL")
        p["uncertainties"] = []
    assert "UNCERTAINTY_REQUIRED" in codes(mutate(f))

    def g(d):
        p = next(x for x in d["proposals"] if x["visibility"] == "OCCLUDED")
        p["uncertainties"] = [{"code": "OTHER", "level": "LOW"}]
    assert "UNCERTAINTY_REQUIRED" in codes(mutate(g))


def test_hidden_hypotheses_never_count():
    d = mutate(lambda x: x["hidden_element_hypotheses"][0].__setitem__("visible_quantity", 1))
    assert {"HYPOTHESIS_COUNTS", "SCHEMA"} & set(codes(d))
    d = mutate(lambda x: x["hidden_element_hypotheses"][0].__setitem__("counts_in_any_total", True))
    assert {"HYPOTHESIS_COUNTS", "SCHEMA"} & set(codes(d))


def test_external_provider_requires_consent_ref_and_replay_must_not_claim_a_model():
    assert "PROVENANCE" in codes(mutate(lambda d: d["provider"].update(provider_name="anthropic", consent_ref=None, model_served="x")))
    assert "PROVENANCE" in codes(mutate(lambda d: d["provider"].update(model_served="claude-x")))


def test_verify_or_raise_lists_all_errors():
    d = S.fresh()
    d["proposals"][0]["human_decision"] = "ACCEPT"
    with pytest.raises(PhotoError) as ei:
        verify_or_raise(d)
    assert ei.value.code == "INVALID_PROPOSAL_SET" and any("FORBIDDEN_DECISION" in x for x in ei.value.details)


def test_non_dict_and_missing_sections_do_not_crash():
    assert not verify_proposal_set([]).ok
    assert not verify_proposal_set({}).ok
