"""Dekking van de controle op dubbel getelde kozijnen (fotoronde -> mjop_scan_proposal_v2). Swift: MJOPIntegration/DuplicateCoverage.swift.

Nul koppelsuggesties is GEEN bewijs dat er geen duplicaten zijn. De automatische suggesties vergelijken alleen waarnemingen met een ruimtelijke
meting (3D-hoeken + vlak) binnen een AR-sessie. Niet gecontroleerd (dus nooit "geen duplicaat"):
* een object zonder vergelijkbare geometrie terwijl er andere objecten zijn;
* een foto met objecten zonder bekende AR-sessie terwijl de objecten op twee of meer foto's staan;
* foto's uit meer dan een AR-sessie.
Gevel: alleen de eigen foto's/objecten (een kozijn dat ook bij een andere gevel staat, is binnen deze gevel geen duplicaat). Gebouw: alles samen.
Een geldige handmatige verklaring ("alle foto's nagelopen") dekt deze open punten; openstaande suggesties moeten altijd apart beoordeeld worden.

    python -m photo_walk_core.duplicate_coverage     # schrijft ios/Tests/MJOPIntegrationTests/Fixtures/duplicate_coverage_cases.json
                                                     # en ios/Tests/PhotoWalkCoreTests/Fixtures/same_frame_overlap_cases.json
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "ios" / "Tests" / "MJOPIntegrationTests" / "Fixtures" / "duplicate_coverage_cases.json"
# de overlapregel zit in PhotoWalkCore (Linking.sameFrameOverlaps): eigen fixture in die testbundel
OUT_OVERLAP = Path(__file__).resolve().parents[2] / "ios" / "Tests" / "PhotoWalkCoreTests" / "Fixtures" / "same_frame_overlap_cases.json"


def evaluate(objects, facade_world_ids, frame_world, duplicates_unresolved, reviewed):
    """objects: lijst {"id", "frame_ids", "duplicate_checkable"}; facade_world_ids: lijst van verzamelingen AR-sessies per gevel in dit bereik;
    frame_world: dict foto -> sessie, of None (niet aangeleverd: alleen de gevelregel); ontbrekende foto = onbekende sessie."""
    photos = sorted({f for o in objects for f in o["frame_ids"]})
    auto_cross = any(len(w) > 1 for w in facade_world_ids)
    unknown_world_photos = 0
    if frame_world is not None:
        if len({frame_world[p] for p in photos if p in frame_world}) > 1:
            auto_cross = True
        unknown_world_photos = sum(1 for p in photos if p not in frame_world)
    world_unknown = unknown_world_photos > 0 and len(photos) >= 2
    unchecked_objects = sum(1 for o in objects if not o["duplicate_checkable"]) if len(objects) >= 2 else 0
    gaps = auto_cross or world_unknown or unchecked_objects > 0
    cross_unchecked = auto_cross and not reviewed
    check_incomplete = (world_unknown or unchecked_objects > 0) and not reviewed
    return {"cross_session_unchecked": cross_unchecked, "unchecked_objects": unchecked_objects, "unknown_world_photos": unknown_world_photos,
            "check_incomplete": check_incomplete, "manual": bool(reviewed and gaps),
            "complete": duplicates_unresolved == 0 and not cross_unchecked and not check_incomplete}


def fingerprint(parts):
    """FNV-1a 64 bit (hex) van de gesorteerde delen; zelfde als DuplicateCoverage.fingerprint (Swift)."""
    h = 0xcbf29ce484222325
    for b in "\n".join(sorted(parts)).encode("utf-8"):
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def same_frame_overlaps(items, min_overlap=0.5):
    """Mogelijke duplicaten op DEZELFDE foto (de ruimtelijke suggesties vergelijken nooit hetzelfde beeld): overlap >= min_overlap van de
    kleinste vierhoek (ook: de een binnen de ander). Pixels, dus ook zonder LiDAR-vlak. items: lijst (id, frame_id, hoeken).
    Zelfde als Linking.sameFrameOverlaps (Swift). PROVISIONAL_UNVALIDATED."""
    from .facade import area, convex_intersection_area
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (ia, fa, ca), (ib, fb, cb) = items[i], items[j]
            if fa != fb or len(ca) < 3 or len(cb) < 3:
                continue
            small = min(area(ca), area(cb))
            if small > 0 and convex_intersection_area(ca, cb) / small >= min_overlap:
                out.append((ia, ib))
    return out


def _o(i, frames, checkable=True):
    return {"id": i, "frame_ids": list(frames), "duplicate_checkable": checkable}


def cases():
    raw = [
        # (naam, objecten, wereld-ids per gevel, foto->sessie of None, open suggesties, verklaard)
        ("same_object_two_photos_no_geometry", [_o("A", ["F0"], False), _o("B", ["F1"], False)], [{"w1"}], {"F0": "w1", "F1": "w1"}, 0, False),
        ("one_object_without_geometry_alone", [_o("A", ["F0"], False)], [{"w1"}], {"F0": "w1"}, 0, False),
        ("one_of_two_without_geometry", [_o("A", ["F0"]), _o("B", ["F1"], False)], [{"w1"}], {"F0": "w1", "F1": "w1"}, 0, False),
        ("facades_each_own_world_building", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1"}, {"w2"}], {"F0": "w1", "F1": "w2"}, 0, False),
        ("facade_alone_single_world", [_o("A", ["F0"]), _o("B", ["F2"])], [{"w1"}], {"F0": "w1", "F2": "w1"}, 0, False),
        ("missing_world_two_photos", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1"}], {"F0": "w1"}, 0, False),
        ("missing_world_single_photo", [_o("A", ["F0"]), _o("B", ["F0"])], [set()], {}, 0, False),
        ("legacy_input_without_frame_world", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1"}], None, 0, False),
        ("legacy_input_cross_session", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1", "w2"}], None, 0, False),
        ("complete_automatic", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1"}], {"F0": "w1", "F1": "w1"}, 0, False),
        ("open_suggestion", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1"}], {"F0": "w1", "F1": "w1"}, 1, False),
        ("reviewed_covers_gaps", [_o("A", ["F0"], False), _o("B", ["F1"])], [{"w1"}, {"w2"}], {"F0": "w1"}, 0, True),
        ("reviewed_does_not_cover_open_suggestion", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1"}], {"F0": "w1", "F1": "w1"}, 2, True),
        ("reviewed_without_gaps_is_not_manual", [_o("A", ["F0"]), _o("B", ["F1"])], [{"w1"}], {"F0": "w1", "F1": "w1"}, 0, True),
        ("no_objects", [], [{"w1", "w2"}], {}, 0, False),
    ]
    out = []
    for name, objs, fw_ids, fw, dups, rev in raw:
        out.append({"name": name, "objects": objs, "facade_world_ids": [sorted(w) for w in fw_ids], "frame_world": fw,
                    "duplicates_unresolved": dups, "reviewed": rev, "expected": evaluate(objs, fw_ids, fw, dups, rev)})
    fps = [["A|F0", "B|F1"], ["B|F1", "A|F0"], ["A|F0", "B|F1", "excluded:F2"], []]
    frame = [(100.0, 100.0), (300.0, 100.0), (300.0, 400.0), (100.0, 400.0)]
    glass = [(120.0, 120.0), (280.0, 120.0), (280.0, 380.0), (120.0, 380.0)]
    shifted = [(110.0, 105.0), (310.0, 105.0), (310.0, 405.0), (110.0, 405.0)]
    beside = [(400.0, 100.0), (600.0, 100.0), (600.0, 400.0), (400.0, 400.0)]
    half = [(220.0, 100.0), (420.0, 100.0), (420.0, 400.0), (220.0, 400.0)]          # 40 % overlap: geen suggestie
    overlap_items = [("O-frame", "F0", frame), ("O-glass", "F0", glass), ("O-shift", "F0", shifted), ("O-beside", "F0", beside),
                     ("O-half", "F0", half), ("O-other-photo", "F1", frame)]
    return {"note": "SYNTHETISCH; gegenereerd door photo_walk_core.duplicate_coverage. Niet met de hand bewerken.",
            "cases": out, "fingerprints": [{"parts": p, "expected": fingerprint(p)} for p in fps],
            "same_frame_overlaps": {"items": [{"id": i, "frame_id": f, "corners": [list(c) for c in q]} for i, f, q in overlap_items],
                                    "expected": [list(x) for x in same_frame_overlaps(overlap_items)]}}


def main():
    c = cases()
    overlap = c.pop("same_frame_overlaps")
    OUT.write_text(json.dumps(c, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    OUT_OVERLAP.write_text(json.dumps(dict(overlap, note=c["note"]), indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    print(OUT, OUT_OVERLAP)


if __name__ == "__main__":
    main()
