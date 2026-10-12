#!/usr/bin/env python3
"""Maldenhof foto 3 human review v1.

Legt de menselijke besluiten over FC-M3-001..010 en REL-M3-001 append-only vast in een
apart besluitenregister en leidt daar een review-staat en rapport uit af. De bestaande
annotatie (maldenhof_3_frame_annotation_v1.json) en het adres/pand-bewijs blijven
ongewijzigd. Er worden GEEN foto-3 frame instances, BAG-koppeling, totalen of
hoeveelheden aangemaakt.

Gebruik: python3 scripts/build_photo3_human_review.py [--check]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANN = ROOT / "data/photo_evidence/maldenhof_3_frame_annotation_v1.json"
STORE = ROOT / "data/photo_evidence/maldenhof_3_candidate_human_decisions_v1.json"
STATE = ROOT / "data/photo_evidence/maldenhof_3_review_state_v1.json"
REPORT = ROOT / "reports/frames/photo_review_rear_v1/maldenhof_3_human_review_v1.md"

REVIEWER = {"reviewer_type": "human", "reviewer_id": "user-approved"}
REVIEWED_AT = "2026-10-12T00:00:00Z"
PHOTO = "maldenhof_3.jpg"

REL_REASON = ("De rode balkondeur en het witte raam vormen één onafgebroken kozijn-/gevelopening. "
              "Er is geen metselwerk of andere bouwkundige scheiding tussen beide; de verticale "
              "scheiding is onderdeel van het kozijn.")
ROOF_REASON = "Dakraam is een fotowaarneming, geen gewoon EXTERIOR_FRAME-gevelkozijn; niet geactiveerd."

# (target_type, target_id, decision, reason, extra)
HUMAN = [
    ("CANDIDATE", "FC-M3-001", "KEEP_UNKNOWN",
     "Te zwaar afgedekt door scherm/planten om een fysieke opening betrouwbaar te bevestigen.", {}),
    ("CANDIDATE", "FC-M3-002", "KEEP_UNKNOWN",
     "Een kozijnrand/dorpel lijkt zichtbaar, maar de fysieke opening is te zwaar afgedekt om "
     "betrouwbaar te classificeren.", {}),
    ("CANDIDATE", "FC-M3-003", "ACCEPT_OBSERVATION",
     "Een fysieke raam-/kozijnopening is zichtbaar, maar gedeeltelijk afgedekt.",
     {"accepted_type": "WINDOW", "accepted_visibility": "PARTIAL"}),
    ("RELATION_GROUP", "REL-M3-001", "SAME_FRAME_OPENING_WINDOW_DOOR_COMBINATION", REL_REASON,
     {"candidate_ids": ["FC-M3-004", "FC-M3-005"],
      "frame_subtype": "WINDOW_DOOR_COMBINATION",
      "physical_frame_openings": 1,
      "semantic_subcomponents": [
          {"component": "WINDOW_SECTION", "source_candidate": "FC-M3-005", "count": 1},
          {"component": "EXTERIOR_DOOR_SECTION", "source_candidate": "FC-M3-004", "count": 1}],
      "future_quantity_contributions": {"FRAME_COUNT": 1, "WINDOW_COUNT": 1, "EXTERIOR_DOOR_COUNT": 1},
      "future_contributions_note": "Alleen semantische toekomstige bijdragen van EEN fysieke opening; "
                                   "geen drie fysieke opening-instances en nu niet geactiveerd.",
      "material": "UNKNOWN",
      "material_note": "Geen visuele WOOD-claim voor de combinatie."}),
    ("CANDIDATE", "FC-M3-006", "ACCEPT_PHOTO_OBSERVATION", ROOF_REASON,
     {"accepted_type": "ROOF_WINDOW", "accepted_visibility": "PARTIAL", "activate_as_exterior_frame": False}),
    ("CANDIDATE", "FC-M3-007", "ACCEPT_PHOTO_OBSERVATION", ROOF_REASON,
     {"accepted_type": "ROOF_WINDOW", "accepted_visibility": "FULL", "activate_as_exterior_frame": False}),
    ("CANDIDATE", "FC-M3-008", "ACCEPT_PHOTO_OBSERVATION", ROOF_REASON,
     {"accepted_type": "ROOF_WINDOW", "accepted_visibility": "FULL", "activate_as_exterior_frame": False}),
    ("CANDIDATE", "FC-M3-009", "ACCEPT_PHOTO_OBSERVATION", ROOF_REASON,
     {"accepted_type": "ROOF_WINDOW", "accepted_visibility": "FULL", "activate_as_exterior_frame": False}),
    ("CANDIDATE", "FC-M3-010", "ACCEPT_PHOTO_OBSERVATION",
     "Dakkapelraam (parent DORMER-M3-001) is een fotowaarneming; het vijfdelige kozijn is één "
     "doorlopende kozijnopening, de interne stijlen zijn geen bouwkundige scheidingen. Nog geen "
     "gewone frame instance.",
     {"accepted_type": "DORMER_WINDOW", "accepted_visibility": "FULL", "parent": "DORMER-M3-001",
      "continuous_frame_openings": 1, "internal_mullions_are_separations": False,
      "activate_as_exterior_frame": False}),
]


def load_ann():
    return json.loads(ANN.read_text())


def build_store(existing):
    """Append-only: bestaande records blijven byte-gelijk; alleen ontbrekende targets worden toegevoegd."""
    store = existing or {
        "store_version": "photo3_candidate_human_decisions_v1",
        "append_only": True,
        "photo": PHOTO,
        "note": "Menselijke besluiten over foto-3 kandidaten en relatiegroepen. Records worden nooit "
                "overschreven; correcties via supersedes.",
        "records": [],
    }
    have = {r["target_id"] for r in store["records"]}
    n = len(store["records"])
    for ttype, tid, dec, reason, extra in HUMAN:
        if tid in have:
            continue
        n += 1
        rec = {"decision_id": f"P3D-{n:05d}", "target_type": ttype, "target_id": tid,
               "decision": dec, "reason": reason, **extra, **REVIEWER,
               "reviewed_at": REVIEWED_AT, "source_photo": PHOTO, "supersedes": None, "status": "ACTIVE"}
        store["records"].append(rec)
    return store


def active(store):
    sup = {r["supersedes"] for r in store["records"] if r.get("supersedes")}
    return {r["target_id"]: r for r in store["records"] if r["decision_id"] not in sup}


def build_state(ann, store):
    dec = active(store)
    cands = []
    for c in ann["candidates"]:
        rel = dec.get(c.get("relation_review") or "")
        d = rel or dec[c["candidate_id"]]
        if d["decision"] == "KEEP_UNKNOWN":
            status, typ, vis = "KEEP_UNKNOWN", "UNKNOWN_OPENING", c["visibility"]
        elif c.get("relation_review"):
            status, typ, vis = "PART_OF_REL_M3_001_FRAME_OPENING", c["candidate_type"], c["visibility"]
        else:
            status, typ, vis = d["decision"], d["accepted_type"], d["accepted_visibility"]
            assert typ == c["candidate_type"] and vis == c["visibility"], c["candidate_id"]
        cands.append({"candidate_id": c["candidate_id"], "review_status": status,
                      "human_decision_id": (rel or d)["decision_id"],
                      "type": typ, "visibility": vis,
                      "is_frame_instance": False, "bag_pand_id": None})
    r = dec["REL-M3-001"]
    return {
        "state_version": "photo3_human_review_state_v1",
        "photo": ann["photo"],
        "bag_pand_id": ann["bag_pand_id"],
        "address_scope": ann["address_scope"],
        "address_scope_note": "Geen pandinferentie uit gelijkenis met foto 2, dakraampatroon, dakkapel, "
                              "kopgevel of camerapositie.",
        "decision_store": str(STORE.relative_to(ROOT)),
        "candidates": cands,
        "relation_review": {
            "group_id": "REL-M3-001", "decision_id": r["decision_id"], "decision": r["decision"],
            "candidate_ids": r["candidate_ids"], "frame_subtype": r["frame_subtype"],
            "physical_frame_openings": r["physical_frame_openings"],
            "semantic_subcomponents": r["semantic_subcomponents"],
            "future_quantity_contributions": r["future_quantity_contributions"],
            "material": r["material"], "instance_created": False},
        "dormer_window": {"candidate_id": "FC-M3-010", "parent": "DORMER-M3-001",
                          "continuous_frame_openings": 1, "internal_mullions_are_separations": False},
        "photo_observation_summary": {
            "count_basis": "REVIEWED_OBSERVATIONS_ON_PHOTO_3", "is_building_total": False,
            "KEEP_UNKNOWN": 2, "ACCEPTED_PARTIAL_WINDOW": 1, "WINDOW_DOOR_COMBINATION_FRAME_OPENINGS": 1,
            "ROOF_WINDOW_OBSERVATIONS": 4, "DORMER_WINDOW_OBSERVATIONS": 1},
        "frame_instances_created": 0,
        "repeat_candidates": {"RC-M3-001": "REPEAT_CANDIDATE", "RC-M3-002": "REPEAT_CANDIDATE",
                              "active": False, "multiplier": None, "user_confirmed_repeat": False},
        "photo_2_unchanged": {"FRAME": 11, "WINDOW": 11, "EXTERIOR_DOOR": 1, "FULL": 9, "PARTIAL": 2},
        "building_total": None, "metric_quantities": None, "quantity_resolutions": 0,
        "comparability_756_80": "NOT_COMPARABLE",
    }


def build_report(state, store):
    L = ["# Maldenhof foto 3: human review v1", "",
         "Menselijke besluiten (reviewer_type human, user-approved) over de 10 kandidaten van "
         "`maldenhof_3.jpg` en relatiegroep REL-M3-001. Append-only register: "
         f"`{state['decision_store']}`. Dit zijn **geen** frame instances.", "",
         "## Status per kandidaat", "", "| Kandidaat | Status | Type | Zichtbaarheid | Besluit |", "|---|---|---|---|---|"]
    for c in state["candidates"]:
        L.append(f"| {c['candidate_id']} | {c['review_status']} | {c['type']} | {c['visibility']} | {c['human_decision_id']} |")
    r = state["relation_review"]
    L += ["", "## REL-M3-001: raam-/deurcombinatie", "",
          f"Besluit {r['decision_id']}: **{r['decision']}**. FC-M3-004 (rode balkondeur) en FC-M3-005 "
          "(wit raam) vormen **één** fysieke kozijnopening van subtype WINDOW_DOOR_COMBINATION; "
          "ze zijn niet als twee frame openings geteld.", "",
          "- Semantische onderdelen: 1 raamsectie + 1 buitendeursectie.",
          "- Toekomstige bijdragen (niet nu geactiveerd): FRAME_COUNT 1, WINDOW_COUNT 1, EXTERIOR_DOOR_COUNT 1. "
          "Dit zijn drie bijdragen van één opening, niet drie fysieke opening-instances.",
          "- Materiaal: UNKNOWN voor de combinatie; geen visuele WOOD-claim.", "",
          "## Dakramen en dakkapel", "",
          "FC-M3-006..009 (dakramen) zijn geaccepteerde fotowaarnemingen en worden niet als gewone "
          "EXTERIOR_FRAME-instances geactiveerd. FC-M3-010 (dakkapelraam, parent DORMER-M3-001): het "
          "vijfdelige kozijn is één doorlopende kozijnopening; interne stijlen scheiden niet. Ook geen instance.", "",
          "## Adres/BAG", "",
          "bag_pand_id blijft `null`, address_scope `NOT_PROVEN`. Geen pandinferentie uit gelijkenis met "
          "foto 2, dakraampatroon, dakkapel, kopgevel of camerapositie.", "",
          "## Niet gedaan", "",
          "- Foto-3 frame instances: 0. Geen gecombineerd gebouwtotaal. Geen hoeveelheidsresolutie.",
          "- Repeat candidates RC-M3-001/002 blijven REPEAT_CANDIDATE (inactief, multiplier null).",
          "- Geen m2, geen painting area, geen BAG-koppeling, geen App-activatie. 756,80 m2 blijft NOT_COMPARABLE.",
          "- Foto 2 ongewijzigd: FRAME 11, WINDOW 11, EXTERIOR_DOOR 1 (9 FULL / 2 PARTIAL).", ""]
    return "\n".join(L)


def render():
    ann = load_ann()
    existing = json.loads(STORE.read_text()) if STORE.exists() else None
    store = build_store(existing)
    state = build_state(ann, store)
    return store, state, build_report(state, store)


def dump(o):
    return json.dumps(o, indent=2, ensure_ascii=False) + "\n"


def main():
    store, state, report = render()
    outs = {STORE: dump(store), STATE: dump(state), REPORT: report}
    if "--check" in sys.argv:
        bad = [str(p) for p, t in outs.items() if not p.exists() or p.read_text() != t]
        if bad:
            print("OUT OF DATE:", *bad, sep="\n  ")
            return 1
        print("OK")
        return 0
    for p, t in outs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(t)
    print("written", *[str(p.relative_to(ROOT)) for p in outs])
    return 0


if __name__ == "__main__":
    sys.exit(main())
