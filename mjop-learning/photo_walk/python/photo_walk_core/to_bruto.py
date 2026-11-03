"""Photo Walk-export -> intake voor het bestaande Bruto Quantity Model v2 (scripts/bruto_quantity_*).

Uitgangspunt: een sensor-/AI-meting is een VOORSTEL en geen menselijke meting. `bruto_dimension_v2` kent voor MEASURED alleen menselijke/tekening-bronnen;
er worden daarom GEEN statussen geforceerd. De objecten worden met dimension_status UNKNOWN aangemaakt (zodat de rekenkern ze als 'nog geen maat' telt en nooit
als bevestigd) en de voorgestelde maten staan in `sensor_proposals`, voor menselijke intake in een latere fase. Dubbeltelling wordt vermeden doordat iedere
waarneming bij precies een object hoort. Geen FI-ids, geen goedkeuringen, geen kosten.

Gebruik: python -m photo_walk_core.to_bruto <photo_walk_record.json> <uit.json>   (uitvoer buiten de repository)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

CATEGORY = {"FRAME": "FRAME", "FRAME_WITH_DOOR": "FRAME_WITH_DOOR", "DOOR": "DOOR", "UNKNOWN": "FRAME"}


def _unknown_dimension():
    return {"outer_width_m": None, "outer_height_m": None, "dimension_basis": "OUTER_FRAME", "dimension_status": "UNKNOWN", "measurement_method": "NONE",
            "source": {"source_kind": "NONE", "source_id": None, "recorded_at": None, "recorded_by": None, "authentication": "NONE_SELF_ASSERTED"},
            "scale_evidence_ref": None, "validated_reference_ref": None, "uncertainty": None, "estimate": None}


def _bqo_id(prov_id):
    return "BQO-PW-" + re.sub(r"[^A-Z0-9-]", "-", prov_id.upper().replace("PROV-", ""))


def convert(record):
    sha = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    obs_frame = {o["observation_id"]: o["frame_id"] for o in record["observations"]}
    observations, objects, proposals = [], [], []
    for o in record["objects"]:
        cat = CATEGORY[o["frame_type"]]
        for ref in o["observation_refs"]:
            observations.append({"observation_id": ref, "photo_id": obs_frame.get(ref, "UNKNOWN-PHOTO"), "object_category": cat, "visibility": "FULL",
                                 "source_ref": f"photo_walk:{record['session_id']}:{obs_frame.get(ref)}"})
        objects.append({"contract_version": "bruto_quantity_object_v2", "object_id": _bqo_id(o["provisional_object_id"]), "object_origin": "OBSERVED",
                        "object_category": cat, "type_id": None, "quantity": 1, "dimension": _unknown_dimension(), "observation_refs": list(o["observation_refs"]),
                        "consolidation": {"proposed_by": "AI_PROPOSAL", "certainty": "UNKNOWN", "basis_refs": list(o["observation_refs"])},
                        "approval_refs": [], "repetition_basis": None, "is_physical_instance": False, "fi_id": None})
        proposals.append({"object_id": _bqo_id(o["provisional_object_id"]), "photo_walk_object_id": o["provisional_object_id"],
                          "proposed_outer_width_m": o["outer_width_m"], "proposed_outer_height_m": o["outer_height_m"], "proposed_gross_area_m2": o["gross_area_m2"],
                          "photo_walk_dimension_status": o["dimension_status"], "measurement_source": o["measurement_source"],
                          "measurement_uncertainty": o["measurement_uncertainty"], "review_required": o["review_required"],
                          "quality_flags": [f["code"] for f in o["quality_flags"]], "corner_sources": o["corner_sources"]})
    return {"contract": "photo_walk_bruto_intake_v1", "source_record_sha256": sha, "source_session_id": record["session_id"], "data_origin": record["data_origin"],
            "validation_level": record["validation_level"], "observations": observations, "objects": objects, "sensor_proposals": proposals,
            "invariants": {"dimension_status_forced": False, "approvals_created": 0, "fi_ids_created": 0, "cost_link": None, "all_dimensions_unknown_until_human_intake": True},
            "notes": ["visibility is niet bepaald en staat standaard op FULL", "voorgestelde maten zijn sensor-/detectorvoorstellen, niet gevalideerd op echte gebouwen"]}


def validate(intake):
    """Valideert tegen de bestaande v2-contracten en bouwt de v2-staat (alleen lezen); geeft de staat terug."""
    import bruto_quantity_contracts as contracts
    return contracts.build_checked_state([], intake["objects"], intake["observations"])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__)
        return 2
    out = Path(argv[1]).resolve()
    if out == ROOT or ROOT in out.parents:
        print("uitvoer binnen de repository is niet toegestaan")
        return 2
    intake = convert(json.load(open(argv[0], encoding="utf-8")))
    state = validate(intake)
    out.write_text(json.dumps(intake, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("geschreven:", out, "| objecten:", len(intake["objects"]), "| v2-laag CONFIRMED leeg:", not state["layers"]["CONFIRMED"]["object_ids"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
