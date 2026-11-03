"""Verticale workflow voor EEN kozijn (stappen 1-11 van de opdracht), op gesimuleerde data."""
import numpy as np

from .config import DEFAULT
from .contract import build_record
from .model import correct_corner
from .pipeline import process_session
from .simulate import annotate, make_view, standard_facade

SESSION = {"session_id": "SYN-SINGLE-001", "building_id": "BLD-SYNTHETIC", "facade_id": "FACADE-A", "platform": "SIMULATION",
           "device_model": "synthetic-lidar-phone", "data_origin": "SIMULATION", "validation_level": "SIMULATED",
           "capabilities": {"lidar": True, "scene_depth": True, "depth_api": False, "ar_world_tracking": True, "metric_tracking": True,
                            "camera_intrinsics_available": True}}


def single_frame_workflow(bad_corner_offset_px=(14.0, -10.0), two_viewpoints=True):
    f = standard_facade()
    frame = f.frames[0]
    steps = ["1 sessie gestart", "2 kozijn K1 geselecteerd (handmatige hoeken, label: semi-automatisch)"]
    views = [make_view(f, "F000", [1.6, 1.6, 4.0], seed=1)]
    if two_viewpoints:
        views.append(make_view(f, "F001", [0.4, 1.6, 4.0], yaw_deg=8, seed=2))
    obs = [annotate(frame, v, seed=11 + i) for i, v in enumerate(views)]
    # een bewust slecht geplaatste hoek in beeld 1 (rechtsonder), zoals een inspecteur kan misklikken
    first = obs[0]
    bad = correct_corner(first, 2, first.corners_px[2] + np.array(bad_corner_offset_px), "inspecteur-synthetisch", "2026-01-01T00:00:00Z", "misklik (gesimuleerd)")
    bad.revisions.clear()
    bad.original_corners_px = bad.corners_px.copy()
    bad.corner_source = "MANUAL"
    steps += ["3 vier buitenhoeken gekozen", "4 camera- en dieptegegevens verzameld", "5-6 buitenmaat gereconstrueerd, breedte en hoogte berekend"]
    before = process_session(SESSION, views, [bad] + obs[1:])
    fixed = correct_corner(bad, 2, first.corners_px[2], "inspecteur-synthetisch", "2026-01-01T00:01:00Z", "hoek rechtsonder gecorrigeerd")
    steps += ["7 bruto m2 = breedte x hoogte", "8 bron en onzekerheid getoond", "9 gebruiker corrigeert hoek", "10 opnieuw berekend; origineel behouden"]
    after = process_session(SESSION, views, [fixed] + obs[1:])
    rec = build_record(SESSION, views, [fixed] + obs[1:], [], after)
    steps.append("11 exportrecord opgebouwd")
    return {"truth": {"width_m": frame.width, "height_m": frame.height, "area_m2": frame.width * frame.height},
            "before": before, "after": after, "record": rec, "steps": steps, "original_preserved": bool(np.allclose(fixed.original_corners_px, bad.corners_px))}
