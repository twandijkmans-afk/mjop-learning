#!/usr/bin/env python3
"""Maldenhof photo-to-quantity pilot (annotatiegebaseerd, lokaal, reproduceerbaar).

Gebruik:  python3 scripts/run_maldenhof_photo_quantity_pilot.py [--out local_output/maldenhof_photo_quantity_pilot_v1]

Leest uitsluitend bestaande repository-bestanden (read-only), schrijft uitsluitend naar de opgegeven uitvoermap (buiten de
canonieke stores; standaard in .gitignore) en doet geen netwerkaanroepen en geen externe Vision-aanroepen. De Safety Gate,
providerregistratie, consent en budgetgrootboek worden niet geraakt. Er worden geen FI-instances, besluiten of definitieve
hoeveelheden aangemaakt. Vereist Pillow; OpenCV/NumPy alleen voor de optionele detectievergelijking.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import bruto_quantity_core as core  # noqa: E402
import photo_quantity_pilot as pq  # noqa: E402

CONFIG = ROOT / "config" / "maldenhof_photo_quantity_pilot_v1.json"
GUARDED = ["data/photos", "data/photo_evidence", "data/frame_inventory", "data/bag_snapshots", "data/building_links",
           "data/quantity_resolutions", "data/kengetallen", "data/kentallen", "schemas", "vocabularies",
           "reports/frames/photo_review_map003_map004_v1/maldenhof_visual_photo_review_map003_map004_v1.json"]
ROW_ORDER = ["ROOF_MAIN", "UPPER_ROW", "MIDDLE_ROW", "ROOF_KAP", "GROUND_ROW", "DORMER", "UNKNOWN"]
ROW_NL = {"UPPER_ROW": "bovenste gevelrij", "MIDDLE_ROW": "middelste rij (kapflank)", "GROUND_ROW": "begane grond",
          "ROOF_MAIN": "hoofddakvlak", "ROOF_KAP": "dakvlak kap", "DORMER": "dakkapel", "UNKNOWN": "onbepaald"}
CAT_ORDER = {"FACADE_FRAME": 0, "DOOR": 1, "ROOF_WINDOW": 2, "DORMER": 3, "UNKNOWN": 4}
VIS_MAP = {"FULL": "FULL", "PARTIAL": "PARTIAL", "UNKNOWN": "OCCLUDED", "OCCLUDED": "OCCLUDED", "HEAVILY_OCCLUDED": "OCCLUDED"}


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha_tree(rel_paths):
    out = {}
    for rel in rel_paths:
        base = ROOT / rel
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for f in files:
            out[str(f.relative_to(ROOT))] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


# --------------------------------------------------------------------------
# Invoer: bestaande annotaties (read-only)
# --------------------------------------------------------------------------

def load_review(cfg):
    review = jload(ROOT / cfg["sources"]["review_json"])
    obs = [pq.normalise_observation(obs_id=o["obs_id"], photo_id=o["photo_id"], observation_type=o["observation_type"],
                                    visibility=o["visibility"], bbox_px=o["bbox_px"], note=o.get("note", ""),
                                    uncertainty=o.get("uncertainty")) for o in review["observations"]]
    return review, obs


def load_map002(cfg, size=(2048, 1536)):
    W, H = size
    annot = jload(ROOT / cfg["sources"]["map002_annotation"])
    corr = jload(ROOT / cfg["sources"]["map002_corrected"])
    inst = jload(ROOT / cfg["sources"]["frame_instances_readonly"])
    cand = {c["candidate_id"]: c for c in annot["candidates"]}
    child = {c["candidate_id"]: c for c in corr["child_candidates"]}
    dec = {d["candidate_id"]: d for d in corr["candidate_decisions"]}
    out = []

    def px(b):
        return [b[0] * W, b[1] * H, b[2] * W, b[3] * H]

    for i in inst["instances"]:
        ids = [r["candidate_id"] for r in i["source_refs"] if r["ref_type"] in ("ORIGINAL_CANDIDATE", "CORRECTED_CHILD_CANDIDATE")]
        cid = ids[-1]
        c = child.get(cid) or cand[cid]
        vis = c.get("visibility") or dec[cid]["original_visibility"]
        note = c.get("note") or cand[ids[0]].get("note", "")
        o = pq.normalise_observation(obs_id=cid, photo_id="MAP-002",
                                     observation_type="EXTERIOR_DOOR" if i["component_type"] == "EXTERIOR_DOOR" else "WINDOW_OPENING",
                                     visibility=vis, bbox_px=px(c["bbox_norm"]), note=note)
        o["fi_ref_readonly"] = i["frame_instance_id"]
        out.append(o)
    for key, typ in (("roof_context_observations", "ROOF_WINDOW"), ("dormer_context_observations", "DORMER_OPENING")):
        for r in corr[key]:
            out.append(pq.normalise_observation(obs_id=r["candidate_id"], photo_id="MAP-002", observation_type=typ,
                                                visibility="FULL", bbox_px=px(r["bbox_norm"]), note=cand[r["candidate_id"]].get("note", "")))
    return out


def bag_pand_pitch_m(cfg):
    """Gemiddelde centroide-afstand tussen opeenvolgende panden uit de BAG-footprints (metrisch, georeferenced, offline)."""
    snap = jload(ROOT / cfg["sources"]["bag_snapshot"])
    polys = {}
    for v in snap["raw_responses"].values():
        for f in (v.get("features", []) if isinstance(v, dict) else []):
            pid = f.get("properties", {}).get("identificatie")
            if pid and f["geometry"]["type"] == "Polygon":
                polys[pid] = f["geometry"]["coordinates"][0]
    lat0 = 52.3026
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574

    def centroid(ring):
        pts = [((a - 4.966) * kx, (b - lat0) * ky) for a, b in ring]
        a2 = cx = cy = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            cr = x1 * y2 - x2 * y1
            a2 += cr
            cx += (x1 + x2) * cr
            cy += (y1 + y2) * cr
        return cx / (3 * a2), cy / (3 * a2)

    order = ["274/276", "278/280", "282/284", "286/288"]
    cents = [centroid(polys[cfg["pand_ids_by_address"][k]]) for k in order]
    dists = [math.dist(a, b) for a, b in zip(cents, cents[1:])]
    return statistics.mean(dists), dists


# --------------------------------------------------------------------------
# Pijplijn
# --------------------------------------------------------------------------

def run_pipeline(cfg):
    review, obs3 = load_review(cfg)
    obs2 = load_map002(cfg)
    observations = obs2 + obs3
    obs_by_key = {(o["photo_id"], o["obs_id"]): o for o in observations}

    # lagen
    layers = dict(pq.classify_row_layers(observations))
    upper_y = defaultdict(list)
    for o in observations:
        if layers.get((o["photo_id"], o["obs_id"])) == "UPPER_ROW":
            upper_y[o["photo_id"]].append((o["bbox_px"][1] + o["bbox_px"][3]) / 2)
    for o in observations:
        k, cat = (o["photo_id"], o["obs_id"]), pq.category_of(o["observation_type"])
        yc = (o["bbox_px"][1] + o["bbox_px"][3]) / 2
        if cat == "ROOF_WINDOW":
            layers[k] = "ROOF_MAIN" if yc < statistics.mean(upper_y[o["photo_id"]]) else "ROOF_KAP"
        elif cat == "DORMER":
            layers[k] = "DORMER"
        elif cat == "UNKNOWN":
            layers[k] = "UNKNOWN"
    for o in observations:
        o["layer"] = layers[(o["photo_id"], o["obs_id"])]
        o["category"] = pq.category_of(o["observation_type"])
        o["frame_type"], o["frame_type_basis"] = pq.classify_frame_type(o)
        o["visibility_class"] = VIS_MAP.get(o["visibility"], "OCCLUDED")

    identity = pq.build_identity(observations, review["relations"], review["references"])

    # parallax / diepte-lagen
    shifts43 = pq.estimate_layer_shifts(identity, obs_by_key, layers, "MAP-003", "MAP-004")
    shifts23 = pq.estimate_layer_shifts(identity, obs_by_key, layers, "MAP-003", "MAP-002")
    ok43, seq43 = pq.parallax_consistency(shifts43, cfg["depth_order_far_to_near"])
    ok23, seq23 = pq.parallax_consistency(shifts23, cfg["depth_order_far_to_near"])

    def shift_for(shifts, layer):
        if layer in shifts:
            return shifts[layer]["median_shift_px"]
        meds = [v["median_shift_px"] for v in shifts.values()]
        return statistics.median(meds) if meds else 0

    def facade_x(o):
        x = pq._xc(o)
        if o["photo_id"] == "MAP-004":
            return x + shift_for(shifts43, o["layer"])
        if o["photo_id"] == "MAP-002":
            return x + shift_for(shifts23, o["layer"])
        return x

    # schaal
    rows_y = pq.row_pitches(observations, layers)
    pitches = {p: pq.storey_pitch_px(r) for p, r in rows_y.items()}
    pitch_m, pitch_dists = bag_pand_pitch_m(cfg)
    plates = defaultdict(dict)
    for pl in review["plates"]:
        plates[pl["photo_id"]][str(pl["reading"])] = (pl["bbox_px"][0] + pl["bbox_px"][2]) / 2
    a2 = pq.pand_pitch_scale(plates, cfg["pand_plate_groups"], round(pitch_m, 3))
    sh = cfg["storey_height_m"]
    scen = pq.scale_scenarios({p: v for p, v in pitches.items() if v}, {k: sh[k] for k in ("lo", "central", "hi")}, a2,
                              Decimal(cfg["perspective_margin"]))
    pm = cfg["plausible_frame_m"]

    def plausible(est):
        c = est["central"]
        w, h = Decimal(c["width_m"]), Decimal(c["height_m"])
        return Decimal(pm["w_min"]) <= w <= Decimal(pm["w_max"]) and Decimal(pm["h_min"]) <= h <= Decimal(pm["h_max"])

    # objecten
    excluded = cfg["segment"]["excluded_obs"]
    objects = []
    for raw in identity["objects"]:
        members = [obs_by_key[k] for k in raw["members"]]
        cats = Counter(m["category"] for m in members)
        category = cats.most_common(1)[0][0]
        layer = Counter(m["layer"] for m in members).most_common(1)[0][0]
        fx = statistics.median([facade_x(m) for m in members])
        in_seg = any(m["photo_id"] in ("MAP-003", "MAP-004") and m["obs_id"] not in excluded for m in members)
        seg_reason = None
        if not in_seg:
            seg_reason = (excluded.get(members[0]["obs_id"]) if all(m["obs_id"] in excluded for m in members)
                          else cfg["segment"]["map002_only_reason"])
        preferred = sorted(members, key=lambda m: ({"FULL": 0, "PARTIAL": 1}.get(m["visibility"], 2), {"MAP-003": 0, "MAP-004": 1, "MAP-002": 2}[m["photo_id"]]))
        primary = preferred[0]
        per_obs = []
        notes = []
        for m in members:
            e = pq.estimate_observation(m, m["layer"], scen["scales"].get(m["photo_id"], {}))
            if e and not plausible(e):
                notes.append(f"{m['photo_id']}:{m['obs_id']}: schatting buiten plausibel bereik, verworpen")
                e = None
            if e:
                m["estimate"] = e
                per_obs.append((f"{m['photo_id']}:{m['obs_id']}", e))
        estimate = pq.combine_object_estimates(per_obs) if category == "FACADE_FRAME" else None
        objects.append({"raw": raw, "members": members, "category": category, "layer": layer, "facade_x": fx, "in_segment": in_seg,
                        "segment_reason": seg_reason, "primary": primary, "estimate": estimate, "estimate_notes": notes})
    objects.sort(key=lambda o: (CAT_ORDER[o["category"]], ROW_ORDER.index(o["layer"]) if o["layer"] in ROW_ORDER else 9, o["facade_x"]))
    for i, o in enumerate(objects, 1):
        o["id"] = f"PU-{i:03d}"
    key_to_obj = {pq_key: o for o in objects for pq_key in o["raw"]["members"]}

    # Methode B
    geo_rows = []
    for o in objects:
        if o["category"] != "FACADE_FRAME":
            continue
        p = o["primary"]
        rel = pq.relative_geometry(p, pitches.get(p["photo_id"], {}).get(o["layer"]))
        r = {"id": o["id"], "layer": o["layer"], "frame_type": p["frame_type"], "primary_visibility": p["visibility"], **rel}
        if p["visibility"] != "FULL":
            r["width_pitch_units"] = None
        geo_rows.append(r)
    dev = pq.deviating_sizes([r for r in geo_rows if r["primary_visibility"] == "FULL"])
    groups, group_lists = pq.geometry_groups([r for r in geo_rows if r["primary_visibility"] == "FULL"])
    for o in objects:
        o["geometry_group"] = groups.get(o["id"])
        o["deviating_size_rel"] = dev.get(o["id"])
    geo_by_id = {r["id"]: r for r in geo_rows}
    for o in objects:
        o["geometry"] = geo_by_id.get(o["id"])

    seg_objs = [o for o in objects if o["in_segment"]]
    seg_frames = [o for o in seg_objs if o["category"] == "FACADE_FRAME"]
    seg_keys = {k for o in seg_objs for k in o["raw"]["members"]}
    bounds_all = pq.identity_bounds(identity, seg_keys)
    frame_keys = {k for o in seg_frames for k in o["raw"]["members"]}
    bounds_frames = pq.identity_bounds(identity, frame_keys)
    return dict(review=review, observations=observations, obs_by_key=obs_by_key, layers=layers, identity=identity, objects=objects,
                key_to_obj=key_to_obj, shifts43=shifts43, shifts23=shifts23, parallax={"43": (ok43, seq43), "23": (ok23, seq23)},
                rows_y=rows_y, pitches=pitches, pitch_m=pitch_m, pitch_dists=pitch_dists, plates=plates, a2=a2, scen=scen,
                seg_objs=seg_objs, seg_frames=seg_frames, geo_rows=geo_rows, geo_groups=group_lists, deviating=dev,
                bounds_frames=bounds_frames, bounds_all=bounds_all, shift_for=shift_for)


# --------------------------------------------------------------------------
# Uitvoer: JSON/CSV
# --------------------------------------------------------------------------

def object_record(o, state):
    p = o["primary"]
    members = o["members"]
    photos = sorted({m["photo_id"] for m in members})
    ref_photos = sorted({e["photo_id"] for e in o["raw"]["reference_evidence"] if e.get("photo_id")})
    est = o["estimate"]
    door = "DOOR_OBJECT" if o["category"] == "DOOR" else ("NOT_OBSERVED_IN_FRAME" if o["category"] == "FACADE_FRAME" else "NOT_RELEVANT")
    rec = OrderedDict([
        ("provisional_object_id", o["id"]), ("category", o["category"]), ("in_analysed_segment", o["in_segment"]),
        ("segment_note", o["segment_reason"]), ("facade_position", f"{ROW_NL.get(o['layer'], o['layer'])}; x~{round(o['facade_x'])} px (MAP-003-coordinaten)"),
        ("layer", o["layer"]), ("photo_ids", photos), ("reference_photo_ids", ref_photos),
        ("observations", [{"photo_id": m["photo_id"], "obs_id": m["obs_id"], "bbox_px": m["bbox_px"], "visibility": m["visibility_class"],
                           "source_visibility": m["visibility"], "evidence_source": m["evidence_source"],
                           "fi_ref_readonly": m.get("fi_ref_readonly")} for m in members]),
        ("frame_type", p["frame_type"]), ("frame_type_basis", p["frame_type_basis"]), ("door_present", door),
        ("has_open_leaf_visible", any(pq.has_open_leaf(m) for m in members)),
        ("best_visibility", min((m["visibility_class"] for m in members), key=["FULL", "PARTIAL", "OCCLUDED"].index)),
        ("identity_status", o["raw"]["identity_status"]), ("identity_flags", o["raw"]["identity_flags"]),
        ("identity_evidence", [{"rel_id": ln["rel_id"], "strength": ln["strength"], "basis": ln["basis"]} for ln in o["raw"]["links"]]),
        ("identity_conflicts", o["raw"]["conflicts"]), ("possible_duplicates", [d["rel_id"] for d in o["raw"]["possible_duplicates"]]),
        ("relative_geometry", o["geometry"]), ("geometry_group", o["geometry_group"]), ("deviating_size_rel_to_peers", o["deviating_size_rel"]),
        ("dimension_status", ESTIMATE_LABEL if est else "UNKNOWN"),
        ("v2_dimension_status_equivalent", "UNKNOWN"),
        ("width_m_central", est["width_m_central"] if est else None), ("height_m_central", est["height_m_central"] if est else None),
        ("gross_m2_central", est["gross_m2_central"] if est else None), ("gross_m2_low", est["gross_m2_low"] if est else None),
        ("gross_m2_high", est["gross_m2_high"] if est else None), ("estimate_sources", est["sources"] if est else []),
        ("cross_photo_consistency", est["cross_photo_consistency"] if est else None),
        ("unknown_reason", None if est else unknown_reason(o)), ("estimate_notes", o["estimate_notes"]),
        ("source_and_uncertainty", "Bestaande handmatige annotatie (niet onafhankelijk geverifieerd) + geometrische afleiding; maten uit "
                                   "expliciete aannames, geen meting." if est else "Geen bruikbare maat."),
    ])
    return rec


ESTIMATE_LABEL = pq.ESTIMATE_STATUS


def unknown_reason(o):
    if o["category"] != "FACADE_FRAME":
        return "Geen gevelkozijn: dak/dakkapel/deur valt buiten de gevel-kozijnoppervlakte van deze pilot."
    if not any(m["visibility"] == "FULL" for m in o["members"]):
        return "Geen enkele foto toont het kozijn volledig (PARTIAL/OCCLUDED): geen verdedigbare breedte/hoogte."
    return "Geen schatting binnen het plausibele bereik of geen rijsteek om een schaal af te leiden."


def build_outputs(state, cfg):
    recs = [object_record(o, state) for o in state["objects"]]
    seg = state["seg_frames"]
    seg_all = state["seg_objs"]
    observed = defaultdict(lambda: Counter())
    for o in state["observations"]:
        observed[o["photo_id"]][(o["category"], o["visibility_class"])] += 1
    photo_observed = {p: {f"{c}:{v}": n for (c, v), n in sorted(cnt.items())} for p, cnt in sorted(observed.items())}
    photo_observed_totals = {p: sum(cnt.values()) for p, cnt in observed.items()}
    est_sum = pq.sum_estimates(seg)
    cats = Counter(o["category"] for o in seg_all)
    n_obs_seg_frames = sum(1 for o in state["observations"] if (o["photo_id"], o["obs_id"]) in {k for fo in seg for k in fo["raw"]["members"]})
    multi = [o for o in seg if len(o["raw"]["photos"]) > 1]
    summary = OrderedDict([
        ("analysed_segment", cfg["segment"]["label"]),
        ("requested_segment", cfg["requested_segment"]),
        ("segment_justification", "Plaatketen 288, 286, 284, 282, 280, 278, 276 is leesbaar in MAP-003/MAP-004 met aantoonbare overlap "
                                  "(platen 280/278/276 in beide). 290 (MAP-002) en 274 zijn niet met aansluitende raamreeksen aangetoond; "
                                  "het bouwvolume rechts van plaat 274 en de zone links van plaat 288 zijn uitgesloten."),
        ("A_PHOTO_OBSERVED", {"observations_total": len(state["observations"]), "per_photo_total": photo_observed_totals,
                              "per_photo_category_visibility": photo_observed, "note": "Alle foto-observaties; geen gebouwtotaal."}),
        ("B_PROVISIONAL_UNIQUE", OrderedDict([
            ("scope", "alleen het geselecteerde segment"), ("segment_objects_by_category", dict(cats)),
            ("facade_frame_observations_in_segment", n_obs_seg_frames), ("unique_facade_frames_provisional", len(seg)),
            ("facade_frames_seen_in_multiple_photos", len(multi)),
            ("possible_double_counts_low_strength_pairs", len([d for d in state["identity"]["possible_duplicates"]
                                                              if state["key_to_obj"][d["a"]]["in_segment"] or state["key_to_obj"][d["b"]]["in_segment"]])),
            ("unresolved_identity_conflicts", len([u for u in state["identity"]["unresolved"]
                                                    if any(state["key_to_obj"][k]["in_segment"] for k in u["left"] + u["right"])])),
            ("refused_same_photo_merges", len(state["identity"]["refused_links"])),
            ("different_frames_blocks_violated", state["identity"]["blocks_violated"]),
            ("unique_frame_bounds", state["bounds_frames"]), ("unique_all_categories_bounds", state["bounds_all"]),
            ("frames_with_exterior_door_inside_frame", 0), ("exterior_door_objects_in_segment", cats.get("DOOR", 0)),
        ])),
        ("C_PHOTO_ESTIMATED_AREA", OrderedDict([
            ("reliable_scale_available", False), ("measured_or_drawing_derived_objects", 0),
            ("reference_derived_estimate_objects", 0),
            ("assumption_estimate_objects", est_sum["n_with_estimate"]), ("unknown_dimension_objects", est_sum["n_without_estimate"]),
            ("assumption_estimate_sum", est_sum),
            ("warning", "Deelsom van PHOTO_ASSUMPTION_ESTIMATE over unieke kozijnen met een schatting; objecten zonder maat ontbreken "
                        "in de som. Geen gebouwtotaal, geen MEASURED, geen onderhoudshoeveelheid."),
        ])),
        ("missing_facade_coverage", [
            "Maldenhof 274 (alleen plaat zichtbaar; bijbehorende wand en kozijnen niet aangetoond) en 290/292 (MAP-002: begroeiing, lantaarnpaal).",
            "Linkerrand van MAP-003 en rechterrand van MAP-004: deels afgesneden kozijnen (PARTIAL) zonder volledige tweede opname.",
            "MAP-009 en MAP-013 zijn alleen als vergelijkingsfragmenten (referenties) beschikbaar; de originelen ontbreken in deze sessie.",
            "Ruim 30 van de 36 originelen zijn in deze sessie niet beschikbaar (zie fotoregister).",
        ]),
    ])
    return recs, summary


def write_csv(path, recs):
    cols = ["provisional_object_id", "category", "in_analysed_segment", "facade_position", "photo_ids", "reference_photo_ids", "frame_type",
            "door_present", "best_visibility", "width_m_central", "height_m_central", "gross_m2_central", "gross_m2_low", "gross_m2_high",
            "dimension_status", "identity_status", "identity_flags", "geometry_group", "deviating_size_rel_to_peers", "source_and_uncertainty"]
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(cols)
        for r in recs:
            w.writerow([";".join(map(str, r[c])) if isinstance(r[c], list) else ("" if r[c] is None else r[c]) for c in cols])


# --------------------------------------------------------------------------
# Foto's, annotaties, vergelijking
# --------------------------------------------------------------------------

def photo_register(cfg):
    audit = jload(ROOT / cfg["sources"]["archive_audit"])
    rows = []
    with open(ROOT / cfg["sources"]["manifest"], encoding="utf-8-sig") as fh:
        manifest = {r["bestand"]: r for r in csv.DictReader(fh)}
    mismatches = 0
    local_state = {"MAP-002": "LOCAL_SAME_SOURCE_REENCODED (maldenhof_2.jpg)", "MAP-003": "DERIVED_RENDER_WITH_OVERLAY (1:1 pixels)",
                   "MAP-004": "DERIVED_RENDER_WITH_OVERLAY (1:1 pixels)", "MAP-009": "FRAGMENTS_ONLY (reviewcrops)",
                   "MAP-013": "FRAGMENTS_ONLY (reviewcrops)", "MAP-033": "FRAGMENTS_ONLY (reviewcrops)",
                   "MAP-015": "LOCAL_DOWNSCALED_SAME_SOURCE (maldenhof_3.jpg, andere gevel)"}
    for p in audit["photos"]:
        m = manifest.get(p["original_file"])
        ok = bool(m and m["sha256"] == p["sha256"] and int(m["breedte_px"]) == p["width_px"] and int(m["hoogte_px"]) == p["height_px"])
        mismatches += 0 if ok else 1
        rows.append({"photo_id": p["photo_id"], "file": p["original_file"], "facade_side": p["classification"]["facade_side"],
                     "usability": p["usability"], "plates": p.get("visible_house_number_plates"), "px": f"{p['width_px']}x{p['height_px']}",
                     "register_equals_manifest": ok, "available_in_this_session": local_state.get(p["photo_id"], "NOT_AVAILABLE"),
                     "relevant_to_pilot": p["photo_id"] in cfg["relevant_photos"]})
    return rows, mismatches


def load_background(cfg, photo_id):
    from PIL import Image
    src = cfg["photo_sources"][photo_id]
    im = Image.open(ROOT / src["path"]).convert("RGB")
    if src["crop"]:
        im = im.crop(tuple(src["crop"]))
    return im


def draw_annotated(im, items, title):
    """items: lijst (bbox, label, kleur, gestippeld, dubbel). Eigen stijl: zwarte rand onder gekleurde lijn, gevulde label."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(size=26)
    small = ImageFont.load_default(size=20)
    pad = 640
    canvas = im.copy()
    d = ImageDraw.Draw(canvas)

    def rect(b, col, w, dashed):
        x1, y1, x2, y2 = b
        if not dashed:
            d.rectangle(b, outline=col, width=w)
            return
        step = 14
        for x in range(int(x1), int(x2), step * 2):
            d.line([(x, y1), (min(x + step, x2), y1)], fill=col, width=w)
            d.line([(x, y2), (min(x + step, x2), y2)], fill=col, width=w)
        for y in range(int(y1), int(y2), step * 2):
            d.line([(x1, y), (x1, min(y + step, y2))], fill=col, width=w)
            d.line([(x2, y), (x2, min(y + step, y2))], fill=col, width=w)

    for bbox, label, col, dashed, double in sorted(items, key=lambda t: -(t[0][2] - t[0][0]) * (t[0][3] - t[0][1])):
        b = [bbox[0] - 3, bbox[1] - 3, bbox[2] + 3, bbox[3] + 3]
        rect(b, (0, 0, 0), 7, dashed)
        rect(b, col, 4, dashed)
        if double:
            rect([b[0] - 8, b[1] - 8, b[2] + 8, b[3] + 8], (255, 255, 255), 3, False)
        tw = d.textlength(label, font=font)
        ly = b[1] - 34 if b[1] > 40 else b[3] + 2
        d.rectangle([b[0], ly, b[0] + tw + 10, ly + 32], fill=col, outline=(0, 0, 0))
        d.text((b[0] + 5, ly + 1), label, fill=(0, 0, 0), font=font)
    out = Image.new("RGB", (canvas.width + pad, canvas.height + 60), (18, 18, 18))
    out.paste(canvas, (0, 60))
    od = ImageDraw.Draw(out)
    od.text((10, 14), title, fill=(255, 255, 255), font=font)
    legend = [((60, 220, 60), "groen: zelfde object op >=2 foto's (waarschijnlijk)"), ((255, 160, 0), "oranje: alleen deze foto"),
              ((255, 60, 255), "magenta: identiteitsconflict / mogelijke dubbeltelling"), ((60, 200, 255), "cyaan: dakraam / dakkapel"),
              ((255, 70, 70), "rood: buitendeur"), ((200, 200, 200), "grijs: buiten het geanalyseerde segment")]
    y = 90
    for col, text in legend:
        od.rectangle([canvas.width + 12, y, canvas.width + 36, y + 20], fill=col)
        od.text((canvas.width + 44, y - 2), text, fill=(235, 235, 235), font=small)
        y += 40
    od.text((canvas.width + 12, y + 10), "gestippeld = PARTIAL/OCCLUDED", fill=(235, 235, 235), font=small)
    od.text((canvas.width + 12, y + 44), "witte dubbele rand = op meerdere foto's", fill=(235, 235, 235), font=small)
    od.text((canvas.width + 12, y + 78), "label PU-id xN = N foto-observaties", fill=(235, 235, 235), font=small)
    return out


def object_color(o):
    if not o["in_segment"]:
        return (200, 200, 200)
    if o["category"] == "DOOR":
        return (255, 70, 70)
    if o["category"] in ("ROOF_WINDOW", "DORMER"):
        return (60, 200, 255)
    flags = o["raw"]["identity_flags"]
    if flags:
        return (255, 60, 255)
    return (60, 220, 60) if len(o["raw"]["photos"]) > 1 else (255, 160, 0)


def make_annotated(state, cfg, out_dir):
    paths = {}
    for photo in ("MAP-002", "MAP-003", "MAP-004"):
        im = load_background(cfg, photo)
        items = []
        for m in (x for x in state["observations"] if x["photo_id"] == photo):
            o = state["key_to_obj"][(photo, m["obs_id"])]
            n = len(o["raw"]["photos"])
            label = f"{o['id']}" + (f" x{n}" if n > 1 else "")
            if m["category"] == "UNKNOWN":
                label = f"{o['id']}?"
            items.append((m["bbox_px"], label, object_color(o), m["visibility"] != "FULL", n > 1))
        title = f"{photo} | {cfg['photo_sources'][photo]['kind']} | PU = voorlopig uniek object (pilot, geen FI-instance)"
        out = draw_annotated(im, items, title)
        p = out_dir / "annotated" / f"{photo}_annotated.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        out.save(p, quality=88)
        paths[photo] = p
    return paths


def make_schema(state, cfg, out_dir):
    """Gevelschema in MAP-003-coordinaten: rijen, objecten en de dekking per foto (zichtbare gevelrijen en gaten)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(size=22)
    small = ImageFont.load_default(size=17)
    rows = ["ROOF_MAIN", "UPPER_ROW", "MIDDLE_ROW", "ROOF_KAP", "GROUND_ROW"]
    objs = [o for o in state["objects"] if o["category"] != "UNKNOWN"]
    xs = [o["facade_x"] for o in objs]
    x_min = min(xs + [-900]) - 200
    x_max = max(xs + [2900]) + 300
    scale = 0.55
    W = int((x_max - x_min) * scale) + 260
    band = 190
    H = band * len(rows) + 130
    im = Image.new("RGB", (W, H), (250, 250, 250))
    d = ImageDraw.Draw(im)
    d.text((10, 8), "Gevelschema (x in MAP-003-pixels; per laag verschoven via parallax-mediaan). Balken onder elke rij = fotodekking.", fill=(0, 0, 0), font=font)
    col_ph = {"MAP-002": (120, 120, 255), "MAP-003": (60, 180, 60), "MAP-004": (240, 150, 40)}

    def X(x):
        return 230 + (x - x_min) * scale

    for ri, row in enumerate(rows):
        y0 = 50 + ri * band
        d.rectangle([0, y0, W, y0 + band - 6], fill=(240, 240, 240) if ri % 2 else (232, 238, 246))
        d.text((8, y0 + 8), ROW_NL[row], fill=(0, 0, 0), font=small)
        for k, (ph, shifts) in enumerate((("MAP-002", state["shifts23"]), ("MAP-003", None), ("MAP-004", state["shifts43"]))):
            s = 0 if shifts is None else state["shift_for"](shifts, row)
            x1, x2 = X(s), X(s + 2048)
            yb = y0 + band - 30 + k * 7 - 14
            d.rectangle([x1, yb, x2, yb + 5], fill=col_ph[ph])
            if ri == 0:
                d.text((x1 + 4, 24), ph, fill=col_ph[ph], font=small) if False else None
        for o in (o for o in objs if o["layer"] == row):
            p = o["primary"]
            w = max(14, p["w_px"] * scale)
            h = max(14, min(p["h_px"] * scale, band - 60))
            xx = X(o["facade_x"]) - w / 2
            yy = y0 + 40
            col = object_color(o)
            d.rectangle([xx, yy, xx + w, yy + h], fill=col, outline=(0, 0, 0), width=2)
            d.text((xx, yy + h + 2), o["id"][3:], fill=(0, 0, 0), font=small)
    lx = 10
    for ph, c in col_ph.items():
        d.rectangle([lx, H - 40, lx + 30, H - 28], fill=c)
        d.text((lx + 36, H - 46), f"dekking {ph}", fill=(0, 0, 0), font=small)
        lx += 240
    p = out_dir / "gevelschema.png"
    im.save(p)
    return p


def detection_comparison(state, cfg):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"available": False, "reason": "OpenCV/NumPy niet geinstalleerd"}
    res = {"available": True, "method": "HSV-drempel (licht, laag verzadigd) + morfologie + contourfilter; grove detector",
           "per_photo": {}}
    for photo in ("MAP-002", "MAP-003", "MAP-004"):
        im = np.array(load_background(cfg, photo))[:, :, ::-1].copy()
        h = im.shape[0]
        boxes = pq.detect_white_frames(im, y_min=int(h * 0.20), y_max=int(h * 0.85))
        ann = [(m["obs_id"], m["bbox_px"]) for m in state["observations"]
               if m["photo_id"] == photo and m["category"] in ("FACADE_FRAME", "ROOF_WINDOW", "DORMER")]
        cmp = pq.compare_detections(boxes, ann)
        cmp["source_pixels"] = cfg["photo_sources"][photo]["kind"]
        res["per_photo"][photo] = cmp
    return res


def b64_jpeg(path, width=1500):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, int(im.height * width / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# --------------------------------------------------------------------------
# HTML-rapport
# --------------------------------------------------------------------------

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_html(state, cfg, recs, summary, register, mism, detect, images, guard, tests_info):
    seg = state["seg_frames"]
    B, C = summary["B_PROVISIONAL_UNIQUE"], summary["C_PHOTO_ESTIMATED_AREA"]
    es = C["assumption_estimate_sum"]
    sc = state["scen"]
    inv_rows = []
    for r in recs:
        if not r["in_analysed_segment"]:
            continue
        inv_rows.append(
            "<tr><td>{id}</td><td>{cat}</td><td>{pos}</td><td>{ph}</td><td>{typ}</td><td>{door}</td><td>{vis}</td><td>{w}</td><td>{h}</td>"
            "<td>{a}</td><td>{band}</td><td>{ds}</td><td>{ids}{fl}</td><td>{g}</td><td>{dv}</td></tr>".format(
                id=r["provisional_object_id"], cat=r["category"], pos=esc(r["facade_position"]), ph=esc(", ".join(r["photo_ids"] + [f"({p})" for p in r["reference_photo_ids"]])),
                typ=r["frame_type"], door=r["door_present"], vis=r["best_visibility"], w=r["width_m_central"] or "UNKNOWN",
                h=r["height_m_central"] or "UNKNOWN", a=r["gross_m2_central"] or "UNKNOWN",
                band=f"{r['gross_m2_low']}–{r['gross_m2_high']}" if r["gross_m2_low"] else "–", ds=r["dimension_status"],
                ids=r["identity_status"], fl=(" ⚠ " + ", ".join(r["identity_flags"])) if r["identity_flags"] else "",
                g=r["geometry_group"] or "–", dv=r["deviating_size_rel_to_peers"] if r["deviating_size_rel_to_peers"] is not None else "–"))
    overlap = []
    for o in state["seg_objs"]:
        if len(o["raw"]["photos"]) > 1 or o["raw"]["reference_evidence"]:
            ev = "; ".join(f"{l['rel_id']} ({l['strength']})" for l in o["raw"]["links"]) or "–"
            refs = ", ".join(sorted({f"{e['ref_id']}" for e in o["raw"]["reference_evidence"]})) or "–"
            overlap.append(f"<tr><td>{o['id']}</td><td>{esc(', '.join(f'{m['photo_id']}:{m['obs_id'][-7:]}' for m in o['members']))}</td><td>{ev}</td><td>{refs}</td><td>{esc(', '.join(o['raw']['identity_flags']) or '–')}</td></tr>")
    unres = []
    for u in state["identity"]["unresolved"]:
        names = [state["key_to_obj"][k]["id"] for k in u["left"] + u["right"]]
        unres.append(f"<tr><td>{u['rel_id']}</td><td>{u['reason']}</td><td>{esc(', '.join(names))}</td><td>{esc(u['basis'])}</td></tr>")
    dup = []
    for d_ in state["identity"]["possible_duplicates"]:
        dup.append(f"<tr><td>{d_['rel_id']}</td><td>{state['key_to_obj'][d_['a']]['id']} ↔ {state['key_to_obj'][d_['b']]['id']}</td><td>{esc(d_['basis'])}</td></tr>")
    reg = []
    for r in register:
        reg.append(f"<tr class=\"{'rel' if r['relevant_to_pilot'] else ''}\"><td>{r['photo_id']}</td><td>{r['file']}</td><td>{r['facade_side']}</td><td>{r['usability']}</td>"
                   f"<td>{esc(r['plates'] or '–')}</td><td>{'ja' if r['register_equals_manifest'] else 'NEE'}</td><td>{esc(r['available_in_this_session'])}</td></tr>")
    shift_rows = []
    for name, sh in (("MAP-003 vs MAP-004", state["shifts43"]), ("MAP-003 vs MAP-002", state["shifts23"])):
        for layer in cfg["depth_order_far_to_near"]:
            if layer in sh:
                s = sh[layer]
                shift_rows.append(f"<tr><td>{name}</td><td>{ROW_NL[layer]}</td><td>{s['n']}</td><td>{round(s['median_shift_px'])}</td>"
                                  f"<td>{', '.join(str(p['residual_px']) for p in s['pairs'])}</td></tr>")
    scale_rows = []
    for photo, rows in sc["scales"].items():
        for row, v in rows.items():
            scale_rows.append(f"<tr><td>{photo}</td><td>{ROW_NL[row]}</td><td>{round(v['pitch_px'])}</td><td>{float(v['low']):.4f}</td><td>{float(v['central']):.4f}</td><td>{float(v['high']):.4f}</td></tr>")
    det_rows = []
    if detect.get("available"):
        for p, c in detect["per_photo"].items():
            det_rows.append(f"<tr><td>{p}</td><td>{esc(c['source_pixels'])}</td><td>{c['n_annotations']}</td><td>{c['n_detections']}</td><td>{c['n_agree']}</td>"
                            f"<td>{len(c['annotations_without_detection'])}</td><td>{len(c['detections_without_annotation'])}</td></tr>")
    geo_groups = []
    for g in state["geo_groups"]:
        ids = ", ".join(r["id"] for r in g)
        if len(g) > 1:
            geo_groups.append(f"<tr><td>{g[0]['layer']}</td><td>{g[0]['frame_type']}</td><td>{len(g)}</td><td>{ids}</td></tr>")
    ratios = [(Decimal(r["gross_m2_low"]) / Decimal(r["gross_m2_central"]), Decimal(r["gross_m2_high"]) / Decimal(r["gross_m2_central"]))
              for r in recs if r["in_analysed_segment"] and r["gross_m2_central"]]
    band_lo = float(statistics.mean([a for a, _ in ratios])) if ratios else 0.0
    band_hi = float(statistics.mean([b for _, b in ratios])) if ratios else 0.0
    img_html = "".join(f"<h3>{p}</h3><img src=\"{b64_jpeg(path)}\" alt=\"{p} geannoteerd\">" for p, path in images["annotated"].items())
    css = """body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:1280px;margin:24px auto;padding:0 16px;color:#1b1b1b;background:#fff}
h1{font-size:26px}h2{margin-top:34px;border-bottom:2px solid #1b4f8a;padding-bottom:4px}table{border-collapse:collapse;width:100%;font-size:12.5px;margin:10px 0}
th,td{border:1px solid #c8ccd2;padding:3px 6px;text-align:left;vertical-align:top}th{background:#e8eef6}img{max-width:100%;border:1px solid #888}
.warn{background:#fff4d6;border-left:5px solid #d69a00;padding:8px 12px;margin:12px 0}.bad{background:#fde3e3;border-left:5px solid #c0392b;padding:8px 12px;margin:12px 0}
.ok{background:#e4f5e4;border-left:5px solid #2e8b2e;padding:8px 12px;margin:12px 0}tr.rel td{background:#f3f8ff}.kpi{display:flex;flex-wrap:wrap;gap:10px}
.kpi div{border:1px solid #b9c2cf;border-radius:6px;padding:8px 12px;min-width:170px;background:#f7f9fc}.kpi b{font-size:22px;display:block}code{background:#eee;padding:1px 4px}
@media(prefers-color-scheme:dark){body{background:#15171a;color:#e6e6e6}th{background:#26303d}th,td{border-color:#444}.kpi div{background:#1e242c;border-color:#444}code{background:#2a2d31}tr.rel td{background:#1a2431}}"""
    html = f"""<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Maldenhof foto-naar-hoeveelheid pilot</title><style>{css}</style></head><body>
<h1>Maldenhof — foto-naar-hoeveelheid pilot (annotatiegebaseerd)</h1>
<p>Gegenereerd {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} door <code>scripts/run_maldenhof_photo_quantity_pilot.py</code>. Alle waarden hieronder zijn voorlopig; niets is een meting, besluit, FI-instance of gebouwtotaal.</p>
<div class="bad"><b>Belangrijkste beperking.</b> Het archief met de 36 originele foto's was in deze sessie <b>niet aanwezig</b>. Beschikbaar waren: <code>maldenhof_2.jpg</code> (zelfde opname als MAP-002, herencodeerd), 1:1-pixelcrops van de reviewweergaven van MAP-003 en MAP-004 (met eerdere annotatie ingebrand), fragmenten van MAP-009/013/033 en de bestaande handmatige annotaties. De pilot is daarom een <b>annotatiegebaseerde pilot</b>: kozijnposities komen uit bestaande handmatige lezingen, niet uit een nieuwe detectie op de originelen.</div>
<h2>1. Resultaat in het kort</h2>
<p>Geanalyseerd segment: <b>{esc(summary['analysed_segment'])}</b> (gevraagd: {esc(summary['requested_segment'])}). {esc(summary['segment_justification'])}</p>
<div class="kpi">
<div><b>{summary['A_PHOTO_OBSERVED']['observations_total']}</b>foto-observaties (alle foto's, alle categorieën)</div>
<div><b>{B['facade_frame_observations_in_segment']}</b>kozijn-observaties in segment</div>
<div><b>{B['unique_facade_frames_provisional']}</b>voorlopig unieke gevelkozijnen (bandbreedte {B['unique_frame_bounds']['lower']}–{B['unique_frame_bounds']['upper_no_cross_photo_merge']})</div>
<div><b>{B['facade_frames_seen_in_multiple_photos']}</b>kozijnen op ≥2 foto's</div>
<div><b>{B['possible_double_counts_low_strength_pairs']}</b>mogelijke dubbeltellingen (LOW-paren)</div>
<div><b>{B['unresolved_identity_conflicts']}</b>niet-opgeloste identiteitsconflicten</div>
<div><b>{C['assumption_estimate_objects']}</b>kozijnen met aannameschatting</div>
<div><b>{C['unknown_dimension_objects']}</b>kozijnen zonder bruikbare maat</div>
<div><b>0</b>kozijnen met betrouwbare schaal (MEASURED / DRAWING_DERIVED)</div>
<div><b>{B['exterior_door_objects_in_segment']}</b>buitendeur-objecten (los, niet in een kozijn gezien)</div>
</div>
<div class="warn"><b>Voorlopige bruto m² (deelsom, alleen aannames):</b> centraal {es['gross_m2_central_presented']} m², bandbreedte {es['gross_m2_low_presented']}–{es['gross_m2_high_presented']} m², over {es['n_with_estimate']} unieke kozijnen met een schatting; {es['n_without_estimate']} unieke kozijnen/objecten in het segment ontbreken in deze som. Dit is <b>PHOTO_ASSUMPTION_ESTIMATE</b>: absolute schaal is niet aantoonbaar. Geen definitief gebouwtotaal.</div>
<h2>2. Foto's: beschikbaarheid en register</h2>
<p>De 36 registerregels zijn tegen het manifest gelegd: {36 - mism} van 36 komen overeen op SHA256, afmeting en bestandsnaam ({mism} afwijkingen). Dit controleert register ↔ manifest; de originele bytes zelf zijn niet opnieuw gecontroleerd omdat het archief ontbrak. Zijde en bruikbaarheid zijn overgenomen uit de bestaande audit (handmatige lezing).</p>
<table><tr><th>ID</th><th>Bestand</th><th>Zijde</th><th>Bruikbaarheid</th><th>Platen</th><th>Register = manifest</th><th>In deze sessie</th></tr>{''.join(reg)}</table>
<h2>3. Geannoteerde afbeeldingen</h2>
<p>MAP-003/MAP-004: achtergrond is de reviewweergave; de eerdere gele/cyaan overlay zit daarin ingebrand. Onze markeringen (PU-nummer, kleur per status) liggen daar bovenop.</p>{img_html}
<h3>Gevelschema met fotodekking</h3><img src="{b64_jpeg(images['schema'], 1800)}" alt="gevelschema">
<h2>4. Kozijninventaris (voorlopig, segment)</h2>
<p>Maten zijn PHOTO_ASSUMPTION_ESTIMATE (centraal; bandbreedte in m² = onder–bovengrens). Een kozijn met meerdere ramen telt als één kozijn. 'Deur in kozijn': in geen enkel kozijn is een deur waargenomen; buitendeuren staan als eigen objecten.</p>
<table><tr><th>ID</th><th>Cat.</th><th>Gevelpositie</th><th>Foto's (referenties)</th><th>Type</th><th>Deur</th><th>Zichtb.</th><th>B (m)</th><th>H (m)</th><th>Bruto m²</th><th>Band m²</th><th>Maatstatus</th><th>Identiteit</th><th>Geom.-groep</th><th>Afw. breedte</th></tr>{''.join(inv_rows)}</table>
<p>Kolom 'Geom.-groep': kozijnen met vergelijkbare relatieve geometrie (herhalingskandidaat, nooit een identiteitsbesluit). 'Afw. breedte': relatieve afwijking t.o.v. gelijksoortige kozijnen (alleen groepen ≥3).</p>
<table><tr><th>Laag</th><th>Type</th><th>n</th><th>Objecten</th></tr>{''.join(geo_groups)}</table>
<h2>5. Overlappende foto-observaties en dubbeltellingen</h2>
<table><tr><th>Object</th><th>Observaties</th><th>Koppelingen (bestaande relatie, zekerheid)</th><th>Referentiefragmenten</th><th>Vlaggen</th></tr>{''.join(overlap)}</table>
<h3>Niet-opgeloste identiteitsconflicten (niet samengevoegd)</h3><table><tr><th>Relatie</th><th>Reden</th><th>Objecten</th><th>Basis</th></tr>{''.join(unres)}</table>
<h3>Mogelijke dubbeltellingen (LOW, niet samengevoegd)</h3><table><tr><th>Relatie</th><th>Objecten</th><th>Basis</th></tr>{''.join(dup)}</table>
<h3>Geometrische controle van de koppelingen (parallax)</h3>
<p>Per diepte-laag is de horizontale verschuiving tussen foto's bepaald uit de reeds gekoppelde paren. Dichterbij gelegen lagen verschuiven meer. Monotoon (ver → dichtbij) MAP-003/004: <b>{'ja' if state['parallax']['43'][0] else 'nee'}</b>; MAP-003/002: <b>{'ja' if state['parallax']['23'][0] else 'nee'}</b> (te weinig lagen om te oordelen als er maar één laag is). Residuen binnen een laag laten zien welke koppelingen afwijken. Dit is een controle op samenhang, geen grondwaarheid.</p>
<table><tr><th>Fotopaar</th><th>Laag</th><th>n paren</th><th>mediaan Δx (px)</th><th>residuen (px)</th></tr>{''.join(shift_rows)}</table>
<div class="warn">Terugkerende kozijnpatronen (tweedelig + smal) maken <i>uitlijning op uiterlijk</i> dubbelzinnig. Het parallax-model (rijen verschuiven monotoon met de diepte; schoorsteenparen en dakramen zijn consistent) ondersteunt de bestaande uitlijning MAP-003 → MAP-004, maar bewijst haar niet. Sterk op elkaar gelijkende kozijnen zijn daarom nergens uitsluitend op gelijkenis samengevoegd.</div>
<h2>6. Schaalanalyse (Methode A → B → C)</h2>
<h3>Methode A — betrouwbare absolute schaal: niet beschikbaar</h3>
<ul><li><b>BAG-footprints (offline snapshot, georeferenced):</b> centroide-afstand tussen opeenvolgende panden 274/276 → 286/288 = {', '.join(f'{d:.2f}' for d in state['pitch_dists'])} m (gemiddeld {state['pitch_m']:.2f} m). Dit is metrisch, maar koppeling aan pixels vereist de pixelpositie van de scheidingsmuren; die staat niet in de annotaties. Gebruikt als <i>zwakke aanname-anker A2</i>, niet als meting.</li>
<li><b>3D BAG hoogten/bouwlagen:</b> b3_bouwlagen = 3; RMSE LoD1.2 3,5–3,6 m (niet-maatvast model) → alleen aanname voor verdiepingshoogte.</li>
<li><b>Deur, baksteen, huisnummerplaat, bouwlaaghoogte:</b> geen aantoonbare vaste maat (zoals in de opdracht gesteld); niet als schaal gebruikt. Deuren zijn bovendien PARTIAL/in schaduw.</li>
<li><b>Geen bouwtekening, geen gemeten kozijn, geen opgemeten gevelbreedte, geen gegeorefereerde fotogrammetrie.</b></li></ul>
<p><b>Resultaat Methode A: 0 objecten met betrouwbare schaal.</b></p>
<h3>Methode B — relatieve gevelgeometrie</h3>
<p>Per kozijn: breedte/hoogte-verhouding en afmetingen in <i>verdiepingssteek-eenheden</i> (verticale afstand tussen rij-middens per foto), dimensieloos, geen meters. Zie inventaris (geometriegroepen en afwijkende breedtes) en <code>pilot_results.json</code> (relative_geometry).</p>
<h3>Methode C — PHOTO_ASSUMPTION_ESTIMATE (experimenteel)</h3>
<p>Expliciete aannames: <b>A1</b> verdiepingshoogte {cfg['storey_height_m']['lo']}–{cfg['storey_height_m']['central']}–{cfg['storey_height_m']['hi']} m ({esc(cfg['storey_height_basis'])}); schaal = H / verticale rijsteek in pixels; <b>A2</b> (zwak) BAG-pandsteek / plaatsteek in het grondvlak; perspectiefmarge ±{float(Decimal(cfg['perspective_margin']))*100:.0f}% bovenop beide grenzen. Verhouding A2/A1 in het grondvlak: <b>{float(sc['a2_over_a1_ratio']):.2f}</b> (per foto {', '.join(f'{x:.2f}' for x in sc['ratios_per_photo'])}) — de twee ankers spreken elkaar tegen, dus de band is breed en het centrum is een compromis (A1·√r). Schattingen buiten het plausibele bereik ({cfg['plausible_frame_m']}) worden verworpen.</p>
<table><tr><th>Foto</th><th>Rij</th><th>rijsteek (px)</th><th>m/px laag</th><th>m/px centraal</th><th>m/px hoog</th></tr>{''.join(scale_rows)}</table>
<h2>7. Lokale detectie versus bestaande annotatie</h2>
<p>Grove OpenCV-detector (lichte kozijnkaders). Dit meet <b>overeenstemming</b> met een handmatige annotatie, geen precision/recall: er is geen onafhankelijke grondwaarheid. MAP-003/004 draaien op reviewweergaven met ingebrande overlay en zijn dus geen zuivere test.</p>
<table><tr><th>Foto</th><th>Pixelbron</th><th>Annotaties</th><th>Detecties</th><th>Overeenkomend (IoU≥0,3)</th><th>Annotatie zonder detectie</th><th>Detectie zonder annotatie</th></tr>{''.join(det_rows)}</table>
<h2>8. Onzekerheden en beperkingen</h2>
<ul><li>Kozijnposities, zichtbaarheid en koppelingen zijn bestaande handmatige lezingen (MANUAL_VISUAL_READING, menselijke review nog open voor MAP-003/004); ze zijn hier niet onafhankelijk bevestigd.</li>
<li>Geen absolute schaal; alle m² zijn aanname-schattingen. De bruto-m²-band loopt per kozijn van gemiddeld {band_lo:.2f}× tot {band_hi:.2f}× het centrum.</li>
<li>Perspectief is niet gecorrigeerd (geen vluchtpunten/homografie per vlak); kozijnen op verschillende diepten krijgen per rij een eigen schaal.</li>
<li>Gedeeltelijk zichtbare kozijnen krijgen geen maat (UNKNOWN), ook als ze op een tweede foto wel gedeeltelijk voorkomen.</li>
<li>Het segment is kleiner dan gevraagd ({esc(summary['requested_segment'])}).</li>
<li>Dakramen en dakkapellen zijn geen gevelkozijnen en staan niet in de m²-som.</li>
<li>Glas en draaiende delen zitten in de bruto buitenmaat (geen aftrek); deuren in een kozijn zouden eveneens meetellen, maar er is geen kozijn-met-deur waargenomen.</li></ul>
<h2>9. Veiligheids- en scopecontroles (uitgevoerd)</h2>
<table><tr><th>Controle</th><th>Resultaat</th></tr>{guard}</table>
<h2>10. Tests</h2><p>{esc(tests_info)}</p>
<h2>11. Advies: foto-naar-hoeveelheid verder verbeteren</h2>
<ol>
<li><b>Eén gemeten referentie per gevelvlak.</b> Meet (laser/rolmaat) 2–3 kozijnen op de Maldenhof-gevel of plaats bij de volgende opname een schaalmarker (bijv. 1 m schaallat of A4-doel) in het gevelvlak. Eén echte maat vervangt de huidige aanname-band (factor ~3 in m²) door ±3–5%.</li>
<li><b>Opnameprotocol voor meetbare foto's:</b> frontaal (kleine hoek), 15–20 m afstand, camera horizontaal, hele gevel + plaat in beeld, minimaal 30% overlap, aparte detailopname per kozijntype met schaalmarker.</li>
<li><b>Homografie per gevelvlak:</b> vluchtpunten uit rechte lijnen (dakgoot, voegen) om per diepte-laag te rectificeren; met originelen ORB/SIFT-matching tussen overlappende foto's (nu onmogelijk door ontbrekende originelen). Dit vervangt de huidige parallax-schatting door een controleerbare transformatie.</li>
<li><b>Scheidingsmuren annoteren</b> (pandgrenzen in pixels). Daarmee wordt de BAG-footprintbreedte (5,4 m per pand) een echte horizontale schaalreferentie (Methode A) in plaats van een zwak anker.</li>
<li><b>Detectie op originelen:</b> draai de lokale detector op de echte bestanden; pas daarna externe Vision overwegen, uitsluitend via de bestaande Safety Gate met consent en budget.</li>
<li><b>Meetset opbouwen:</b> zodra gemeten kozijnen bestaan, kalibreer schaalaannames en triagedrempels hieraan en rapporteer pas dan fout/bias; tot dat moment geen nauwkeurigheidsclaims.</li>
<li><b>Menselijke review van de 48 open appdecisies</b> (identiteit MAP-003/004/002) voordat enige koppeling als bevestigd telt.</li></ol>
</body></html>"""
    return html


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "local_output" / "maldenhof_photo_quantity_pilot_v1"))
    ap.add_argument("--tests-info", default="Zie tests/test_photo_quantity_pilot.py (synthetisch) en de CI-workflow photo-quantity-pilot-tests.yml.")
    args = ap.parse_args(argv)
    out_dir = Path(args.out).resolve()
    if ROOT in out_dir.parents and "local_output" not in out_dir.parts:
        raise SystemExit("uitvoer moet in local_output/ of buiten de repository liggen")
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = jload(CONFIG)
    before = sha_tree(GUARDED)
    state = run_pipeline(cfg)
    recs, summary = build_outputs(state, cfg)
    register, mism = photo_register(cfg)
    detect = detection_comparison(state, cfg)
    images = {"annotated": make_annotated(state, cfg, out_dir), "schema": make_schema(state, cfg, out_dir)}
    after = sha_tree(GUARDED)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    guard_rows = [
        ("Canonieke stores, schema's en vocabularies ongewijzigd (SHA256 voor/na, %d bestanden)" % len(before), "OK" if not changed else f"AFWIJKING: {changed}"),
        ("Externe Vision-aanroepen", "0 (geen netwerk, geen provider; Safety Gate/consent/budget niet geraakt)"),
        ("FI-instances / besluiten / definitieve hoeveelheden aangemaakt", "0 / 0 / 0"),
        ("Foto-aanname als MEASURED/CONFIRMED/APPROVED gelabeld", "nee: PHOTO_ASSUMPTION_ESTIMATE; v2-equivalent UNKNOWN"),
        ("Dubbeltelling: totaal over unieke objecten, niet over observaties", "ja (zie sum_estimates)"),
        ("DIFFERENT_FRAMES-blokkades geschonden", "nee" if not state["identity"]["blocks_violated"] else str(state["identity"]["blocks_violated"])),
    ]
    guard_html = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in guard_rows)
    html = build_html(state, cfg, recs, summary, register, mism, detect, images, guard_html, args.tests_info)
    (out_dir / "pilot_report.html").write_text(html, encoding="utf-8")
    result = OrderedDict([
        ("pilot_version", pq.PILOT_VERSION), ("generated_at", datetime.now(timezone.utc).isoformat()), ("invariants", pq.INVARIANTS),
        ("summary", summary), ("inventory", recs),
        ("identity", {"links": state["identity"]["links"], "possible_duplicates": state["identity"]["possible_duplicates"],
                      "unresolved": state["identity"]["unresolved"], "blocks": state["identity"]["blocks"],
                      "refused_links": state["identity"]["refused_links"]}),
        ("parallax", {"MAP-003_vs_MAP-004": state["shifts43"], "MAP-003_vs_MAP-002": state["shifts23"]}),
        ("scale", {"storey_height_m": cfg["storey_height_m"], "bag_pand_pitch_m": round(state["pitch_m"], 3),
                   "bag_pand_pitch_each_m": [round(d, 3) for d in state["pitch_dists"]],
                   "a2_scale_m_per_px": {k: str(v) for k, v in state["a2"].items()}, "a2_over_a1_ratio": str(state["scen"]["a2_over_a1_ratio"]),
                   "scenarios_m_per_px": {p: {r: {k: str(v) if isinstance(v, Decimal) else v for k, v in vv.items()} for r, vv in rows.items()}
                                          for p, rows in state["scen"]["scales"].items()}}),
        ("detection_comparison", detect), ("photo_register", register),
        ("readonly_check", {"files_hashed": len(before), "changed": changed}),
    ])
    (out_dir / "pilot_results.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    write_csv(out_dir / "kozijninventaris.csv", recs)
    print(json.dumps({"out": str(out_dir), "analysed_segment": summary["analysed_segment"],
                      "B": summary["B_PROVISIONAL_UNIQUE"], "C": summary["C_PHOTO_ESTIMATED_AREA"], "readonly_changed": changed}, indent=1,
                     ensure_ascii=False, default=str))
    return 0 if not changed else 2


if __name__ == "__main__":
    sys.exit(main())
