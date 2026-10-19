"""Pipeline: modus bepalen, waarnemingen meten (A -> B -> C), dubbeltelling voorkomen, resultaat per kozijn samenstellen.

Uitkomst is altijd VOORLOPIG: `quantity_layer = PROVISIONAL`, `approval_state = PENDING_HUMAN_APPROVAL`. Deze module registreert geen
besluit, simuleert geen goedkeuring en maakt geen definitieve hoeveelheid, kosten of kengetal.
"""
from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from . import quality as q
from .association import associate
from .config import DEFAULT, MEASUREMENT_METHOD_VERSION, PROCESSING_VERSION, Config
from .levels import (LevelResult, fuse_results, measure_depth_view, measure_triangulated, measure_with_reference, verify_vio_scale)
from .model import stable_seed

STATUSES = ("MEASURED", "DERIVED", "ESTIMATED", "UNKNOWN")
# adviserende flags die 'MEASURED' uitsluiten
DOWNGRADING = {"GLASS_DEPTH_UNRELIABLE", "CORNER_DEPTH_MISMATCH", "FACADE_NOT_VERTICAL", "SINGLE_VIEWPOINT", "METRIC_SCALE_UNVERIFIED",
               "COPLANARITY_ASSUMED", "REFERENCE_UNCERTAINTY_NOT_PROVIDED", "OBSTRUCTION_REPORTED", "ASSOCIATION_UNVERIFIED",
               "AMBIGUOUS_ASSOCIATION", "VIO_SCALE_MISMATCH"}
INVARIANTS = OrderedDict([("quantity_layer", "PROVISIONAL"), ("approval_state", "PENDING_HUMAN_APPROVAL"), ("is_final", False),
                          ("human_decision_registered", False), ("approvals_simulated", False), ("cost_link", None), ("kengetal_link", None),
                          ("price_link", None), ("external_vision_calls", 0), ("images_uploaded", False)])


def determine_measurement_mode(cap):
    """Bepaalt automatisch de primaire meetroute uit de sensorcapabilities. LiDAR is nooit verplicht."""
    depth = bool(cap.get("scene_depth") or cap.get("lidar") or cap.get("depth_api"))
    world = bool(cap.get("ar_world_tracking"))
    metric = bool(cap.get("metric_tracking"))
    if depth and world:
        return {"primary_level": "A", "mode": "A_METRIC_DEPTH", "fallback_chain": ["A", "B", "C"],
                "reason": "dieptesensor + wereldtracking aanwezig"}
    if world and metric:
        return {"primary_level": "B", "mode": "B_AR_GEOMETRY", "fallback_chain": ["B", "C"], "reason": "geen bruikbare dieptesensor; metrische AR-tracking"}
    return {"primary_level": "C", "mode": "C_REFERENCE", "fallback_chain": ["C"],
            "reason": "geen dieptesensor en geen metrische tracking: referentiemeting door inspecteur nodig"}


def mm(x):
    return Decimal(repr(float(x))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def gross_area_exact(width_m: Decimal, height_m: Decimal, quantity=1):
    """gross_area_m2 = buitenbreedte x buitenhoogte x aantal; glas niet afgetrokken, draaiende/vaste delen niet apart (regel 1-3)."""
    return width_m * height_m * quantity


def _s(d, places=4):
    return format(Decimal(d).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "f")


def _fmt_point(p):
    return [round(float(x), 4) for x in p]


def _status_from(result, kind, n_views, verified):
    if result is None or not result.ok:
        return "UNKNOWN"
    adv = {f["code"] for f in q.advisory(result.flags)}
    if kind == "A":
        if n_views >= 2 and not (adv & DOWNGRADING):
            return "MEASURED"
        return "ESTIMATED"
    if kind == "B":
        return "DERIVED" if verified else "ESTIMATED"
    return "DERIVED"          # C


def process_session(session, views, observations, references=(), cfg: Config = DEFAULT, explicit_links=(), frame_meta=None,
                    plane_ids=None, facade_extent_uv=None):
    """session: {session_id, capabilities, ...}. views: lijst View. observations: lijst Observation.
    references: lijst dicts (zie levels.measure_with_reference) + 'frame_id'. frame_meta: {obs_id: {frame_type, parts}}.
    plane_ids: {obs_id: plane_id} (voor referentievlak-controle). Geeft dict met 'objects', 'mode', 'summary'."""
    mode = determine_measurement_mode(session["capabilities"])
    vmap = {v.frame_id: v for v in views}
    frame_meta = frame_meta or {}
    plane_ids = plane_ids or {}
    seed0 = stable_seed(session["session_id"])
    # 1. voorlopige per-waarneming resultaten voor associatie (niveau A als diepte beschikbaar)
    per_obs = {}
    items = []
    for ob in observations:
        v = vmap[ob.frame_id]
        ra = None
        if "A" in mode["fallback_chain"] and v.depth is not None:
            ra = measure_depth_view(v, ob.corners_px, cfg, seed=stable_seed(seed0, ob.observation_id), obstruction=ob.obstruction_reported)
        per_obs[ob.observation_id] = ra
        ok = ra is not None and ra.ok
        items.append({"obs_id": ob.observation_id, "frame_id": ob.frame_id, "center_w": ra.center_w if ok else None,
                      "plane_n": ra.plane_n if ok else None, "plane_d": ra.plane_d if ok else None,
                      "w": ra.width_m if ok else None, "h": ra.height_m if ok else None})
    links, auto_linked = list(explicit_links), set()
    if "B" in mode["fallback_chain"]:
        for a, b in _triangulation_links(observations, items, vmap, cfg, bool(session["capabilities"].get("metric_tracking"))):
            links.append((a, b))
            auto_linked.update((a, b))
    clusters, notes = associate(items, cfg, links)
    for i, it in enumerate(items):
        if it["obs_id"] in auto_linked:
            notes[i].append("ASSOCIATION_UNVERIFIED")
    obs_by_id = {o.observation_id: o for o in observations}
    objects = []
    for ci, cl in enumerate(clusters, start=1):
        obs_list = [observations[i] for i in cl]
        extra = [f for i in cl for code in notes[i] for f in [q.flag(code)]]
        objects.append(_measure_cluster(ci, obs_list, per_obs, vmap, mode, references, cfg, session, seed0, extra, frame_meta, plane_ids))
    return {"mode": mode, "objects": objects, "summary": summarize(objects), "invariants": dict(INVARIANTS)}


def _triangulation_links(observations, items, vmap, cfg, metric):
    """Koppel waarnemingen ZONDER diepte via triangulatie (kleine herprojectiefout). Alleen eenduidige paren; altijd ASSOCIATION_UNVERIFIED."""
    cand = {}
    for i, a in enumerate(observations):
        for j in range(i + 1, len(observations)):
            b = observations[j]
            if not (vmap[a.frame_id].pose_valid and vmap[b.frame_id].pose_valid):
                continue
            if a.frame_id == b.frame_id or items[i]["center_w"] is not None or items[j]["center_w"] is not None:
                continue
            r = measure_triangulated([vmap[a.frame_id], vmap[b.frame_id]], [a.corners_px, b.corners_px], cfg, seed=0, metric_scale_trusted=metric)
            if r.corners_w is not None and not [f for f in q.blocking(r.flags) if f["code"] != "NO_METRIC_SCALE"]:
                cand.setdefault((a.observation_id, b.frame_id), []).append(b.observation_id)
                cand.setdefault((b.observation_id, a.frame_id), []).append(a.observation_id)
    out = []
    for (oid, _), partners in sorted(cand.items()):
        if len(partners) == 1 and len(cand.get((partners[0], next(o.frame_id for o in observations if o.observation_id == oid)), [])) == 1:
            pair = tuple(sorted((oid, partners[0])))
            if pair not in out:
                out.append(pair)
    return out


def _measure_cluster(ci, obs_list, per_obs, vmap, mode, references, cfg, session, seed0, extra_flags, frame_meta, plane_ids):
    oid = f"PROV-{session['session_id']}-{ci:03d}"
    flags = list(extra_flags)
    attempts = []
    final, kind, verified, n_views = None, None, False, 0
    ob_views = [vmap[o.frame_id] for o in obs_list]
    # A
    if "A" in mode["fallback_chain"]:
        ras = [per_obs[o.observation_id] for o in obs_list if per_obs.get(o.observation_id) is not None]
        if ras:
            fused = fuse_results(ras, cfg) if len(ras) > 1 else ras[0]
            attempts.append(("A", fused))
            if fused.ok:
                final, kind, n_views = fused, "A", len(fused.view_ids)
            elif any(f["code"] == "VIEWS_INCONSISTENT" for f in fused.flags):
                final, kind = fused, "A"      # inconsistent: geen terugval die de inconsistentie verbergt
    # B
    if final is None and "B" in mode["fallback_chain"] and len({v.frame_id for v in ob_views if v.pose_valid}) >= 2:
        rb = measure_triangulated(ob_views, [o.corners_px for o in obs_list], cfg, seed=stable_seed(seed0, oid, "B"),
                                  metric_scale_trusted=bool(session["capabilities"].get("metric_tracking")))
        attempts.append(("B", rb))
        if rb.ok:
            refs = [r for r in references if r["frame_id"] in {v.frame_id for v in ob_views}]
            for r in refs:
                ratio = verify_vio_scale(rb, vmap[r["frame_id"]], r, cfg)
                if ratio is not None:
                    rb.diagnostics["scale_ratio_vs_reference"] = float(ratio)
                    if abs(ratio - 1) <= cfg.scale_verify_tol:
                        verified = True
                        rb.flags = [f for f in rb.flags if f["code"] != "METRIC_SCALE_UNVERIFIED"]
                        rb.scale_evidence.update(kind="AR_VIO_METRIC_VERIFIED_BY_REFERENCE", verified_by_reference=True, reference_id=r.get("reference_id"))
                    else:
                        rb.flags.append(q.flag("VIO_SCALE_MISMATCH", f"verhouding {ratio:.3f}"))
                    break
            if "VIO_SCALE_MISMATCH" not in {f["code"] for f in rb.flags}:
                final, kind, n_views = rb, "B", len({v.frame_id for v in ob_views})
    # C
    if final is None and "C" in mode["fallback_chain"]:
        for o in obs_list:
            for r in references:
                if r["frame_id"] == o.frame_id:
                    rr = dict(r)
                    rr["target_plane_id"] = plane_ids.get(o.observation_id)
                    rc = measure_with_reference(vmap[o.frame_id], o.corners_px, rr, cfg, seed=stable_seed(seed0, o.observation_id, "C"),
                                                anchor_px=r.get("anchor_px"))
                    attempts.append(("C", rc))
                    if rc.ok:
                        final, kind, n_views = rc, "C", 1
                        break
            if final is not None:
                break
    if final is None:
        # niets bruikbaars: neem de meest informatieve mislukte poging mee (geen waarde), bewaar alle flags
        final = attempts[-1][1] if attempts else LevelResult("C", "NONE")
        kind = attempts[-1][0] if attempts else None
        if not attempts or not q.blocking(final.flags):
            final.flags.append(q.flag("NO_METRIC_SCALE"))
    for _, r in attempts:
        if r is not final:
            flags += [dict(f, detail=f"[{_}] {f.get('detail')}") for f in r.flags if f["severity"] == q.BLOCKING]
    flags += final.flags
    if len(obs_list) == 1 and kind == "A" and final.ok:
        flags.append(q.flag("SINGLE_VIEWPOINT"))
    for o in obs_list:
        if o.corner_source in ("MANUAL", "AUTO_DETECTED_UNCONFIRMED"):
            flags.append(q.flag("MANUAL_CORNERS") if o.corner_source == "MANUAL" else q.flag("MANUAL_CORNERS", "automatisch voorstel, niet bevestigd"))
        if o.corner_source == "MANUAL_CORRECTED":
            flags.append(q.flag("HUMAN_CORRECTED_CORNERS"))
        if o.obstruction_reported:
            flags.append(q.flag("OBSTRUCTION_REPORTED"))
    flags = q.dedupe_flags(flags)
    final_ok = final.ok
    status = _status_from(final if final_ok else None, kind, n_views, verified)
    if final_ok and any(f["code"] in DOWNGRADING for f in flags) and status == "MEASURED":
        status = "ESTIMATED"
    meta = {}
    for o in obs_list:
        meta.update(frame_meta.get(o.observation_id, {}))
    obj = build_object(oid, obs_list, final if final_ok else None, kind, status, flags, meta, cfg)
    obj["_attempts"] = [(k, r.level) for k, r in attempts]
    return obj


def build_object(oid, obs_list, res, kind, status, flags, meta, cfg):
    d = OrderedDict()
    d["provisional_object_id"] = oid
    d["observation_refs"] = [o.observation_id for o in obs_list]
    d["frame_type"] = meta.get("frame_type", "UNKNOWN")
    d["parts"] = {"fixed_parts": meta.get("fixed_parts"), "movable_parts": meta.get("movable_parts"),
                  "note": "informatief; heeft geen invloed op het bruto oppervlak (regel 2)"}
    d["detection_method"] = "SEMI_AUTOMATIC" if any(o.corner_source in ("MANUAL", "MANUAL_CORRECTED") for o in obs_list) else "AUTOMATIC_CANDIDATE"
    d["corner_sources"] = sorted({o.corner_source for o in obs_list})
    d["corner_order"] = ["TOP_LEFT", "TOP_RIGHT", "BOTTOM_RIGHT", "BOTTOM_LEFT"]
    if res is not None and res.corners_w is not None:
        d["outer_corner_coordinates"] = {"coordinate_system": "WORLD_M_Y_UP", "unit": "m", "points": [_fmt_point(p) for p in res.corners_w]}
    else:
        d["outer_corner_coordinates"] = None
    d["corner_pixels"] = [{"observation_ref": o.observation_id, "frame_id": o.frame_id, "unit": "px",
                           "points": [[round(float(x), 2) for x in p] for p in o.corners_px],
                           "original_points": [[round(float(x), 2) for x in p] for p in o.original_corners_px],
                           "revisions": o.revisions} for o in obs_list]
    if res is not None:
        w, h = mm(res.width_m), mm(res.height_m)
        area = gross_area_exact(w, h, 1)
        d["outer_width_m"], d["outer_height_m"] = format(w, "f"), format(h, "f")
        d["gross_area_m2"] = format(area, "f")
        d["gross_area_m2_presented"] = format(area.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
        d["measurement_uncertainty"] = {"model": "MONTE_CARLO_PIXEL_PLANE_NOISE_V1", "validated": False, "samples": cfg.mc_samples,
                                        "width_sigma_m": _s(res.sigma_w), "height_sigma_m": _s(res.sigma_h), "area_sigma_m2": _s(res.sigma_area),
                                        "note": "1-sigma van een ruismodel met provisional parameters; geen gevalideerde tolerantie."}
        d["measurement_source"] = {"level": kind, "scale_method": res.scale_method, "views": list(res.view_ids), "scale_evidence": res.scale_evidence}
    else:
        d["outer_width_m"] = d["outer_height_m"] = d["gross_area_m2"] = d["gross_area_m2_presented"] = None
        d["measurement_uncertainty"] = None
        d["measurement_source"] = {"level": None, "scale_method": "NONE", "views": [], "scale_evidence": {}}
    d["dimension_status"] = status
    adv = q.advisory(flags)
    d["review_required"] = bool(status != "MEASURED" or adv or q.blocking(flags))
    d["quality_flags"] = flags
    d["next_steps_nl"] = [f["instruction_nl"] for f in flags if f["severity"] == q.BLOCKING or f["code"] in DOWNGRADING]
    d["quantity_layer"] = "PROVISIONAL"
    d["approval_state"] = "PENDING_HUMAN_APPROVAL"
    return d


def summarize(objects):
    """Totalen per status APART (nooit samengeteld over statussen heen) en tellingen."""
    out = {"object_count": len(objects), "by_status": {}, "review_required": sum(1 for o in objects if o["review_required"])}
    for s in STATUSES:
        sel = [o for o in objects if o["dimension_status"] == s]
        tot = sum((Decimal(o["gross_area_m2"]) for o in sel if o["gross_area_m2"]), Decimal(0))
        out["by_status"][s] = {"count": len(sel), "gross_area_m2": format(tot, "f") if s != "UNKNOWN" else None}
    out["note"] = "Totalen zijn voorlopig en per status gescheiden; ze mogen niet worden opgeteld tot een definitieve hoeveelheid."
    return out
