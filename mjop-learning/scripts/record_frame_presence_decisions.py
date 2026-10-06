"""Legt de twee door de gebruiker goedgekeurde EXTERIOR_FRAME-presence-besluiten vast in de append-only decision store.

Milestone Frame Inventory Foundation v1: ALLEEN EXTERIOR_FRAME = PRESENT voor Maldenhof (DOC-005/006) en DOC-012 (Meppelweg).
Geen van de andere 28 inventory-besluiten wordt hier afgehandeld. Het besluit zegt niets over aantal, oppervlak, afmetingen,
ramen/deuren of schilderoppervlak; material_as_reported = hout blijft evidence-detail.

Idempotent: een bestaand ACTIVE besluit voor dezelfde sleutel wordt nooit overschreven of dubbel toegevoegd.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_component_inventory as bci  # noqa: E402
import component_presence as cp  # noqa: E402

REVIEWER_ID = "user-approved"
REVIEWED_AT = "2026-10-06T08:01:12Z"
REASON = ("Het historische MJOP noemt expliciet 'Kozijn buiten hout'. Dit is voldoende bewijs dat buitenkozijnen aanwezig zijn. "
          "Dit besluit zegt niets over aantal, oppervlak, afmetingen, ramen/deuren of schilderoppervlak.")
COMPONENT = "EXTERIOR_FRAME"
TARGET_DOCS = ("DOC-005", "DOC-012")  # DOC-005 en DOC-006 vormen één gebouw (Maldenhof); DOC-012 = Meppelweg


def target_buildings(evidence):
    """building_id's waarvoor EXTERIOR_FRAME-evidence uit TARGET_DOCS bestaat."""
    out = {}
    for e in evidence:
        if e["component_type"] == COMPONENT and e["source_ref"].get("document_id") in TARGET_DOCS + ("DOC-006",):
            out.setdefault(e["building_id"], []).append(e["evidence_id"])
    return out


def apply(store, evidence):
    index = {e["evidence_id"]: e for e in evidence}
    ids = sorted(target_buildings(evidence).items(), key=lambda kv: kv[0])
    if len(ids) != 2:
        raise cp.PresenceError(f"verwacht precies 2 gebouwen met EXTERIOR_FRAME-evidence, gevonden {len(ids)}")
    active = cp.active_decisions(store)
    added = []
    for building_id, _ in ids:
        if (building_id, None, COMPONENT) in active:
            continue
        every = sorted(e["evidence_id"] for e in evidence if e["building_id"] == building_id and e["component_type"] == COMPONENT)
        store, rec = cp.record_decision(store, building_id=building_id, component_type=COMPONENT, decision="PRESENT", reason=REASON,
                                        reviewer_id=REVIEWER_ID, reviewed_at=REVIEWED_AT, considered_evidence_ids=every, evidence_index=index)
        added.append(rec)
    return store, added


def main():
    built = bci.build(decisions_store=cp.load_store())
    store, added = apply(cp.load_store(), built["evidence_store"]["evidence"])
    if added:
        Path(cp.DECISIONS).write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(added)} besluit(en) toegevoegd: {[r['decision_id'] for r in added]}")


if __name__ == "__main__":
    main()
