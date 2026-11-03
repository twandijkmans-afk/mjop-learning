"""Invoertypen van de meetkern (in-memory; beelden en dieptekaarten worden nooit in de repository opgeslagen)."""
import copy
import hashlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .geometry import Intrinsics

TRACKING_NORMAL = "NORMAL"
TRACKING_STATES = ("NORMAL", "LIMITED_INITIALIZING", "LIMITED_EXCESSIVE_MOTION", "LIMITED_INSUFFICIENT_FEATURES",
                   "LIMITED_RELOCALIZING", "NOT_AVAILABLE")
CORNER_SOURCES = ("MANUAL", "AUTO_DETECTED_UNCONFIRMED", "AUTO_DETECTED_CONFIRMED", "MANUAL_CORRECTED")
CORNER_ORDER = ("TOP_LEFT", "TOP_RIGHT", "BOTTOM_RIGHT", "BOTTOM_LEFT")


@dataclass
class View:
    """Een keyframe. depth: (Hd, Wd) float, depth_z in meter (NaN/0 = ongeldig), of None."""
    frame_id: str
    intrinsics: Intrinsics
    pose: np.ndarray                       # camera_to_world 4x4, OpenCV-cameraconventie
    tracking_state: str = TRACKING_NORMAL
    depth: Optional[np.ndarray] = None
    timestamp: str = "1970-01-01T00:00:00Z"
    image_ref: Optional[str] = None        # opake lokale verwijzing; geen pad naar de repo, geen upload
    depth_ref: Optional[str] = None
    pose_valid: bool = True                # False: geen AR-tracking; pose is identiteit en wereldcoordinaten zijn niet betekenisvol


@dataclass
class Observation:
    """Een waarneming van een kozijn in een beeld: vier buitenhoeken in PIXELS (TL, TR, BR, BL)."""
    observation_id: str
    frame_id: str
    corners_px: np.ndarray
    corner_source: str = "MANUAL"
    obstruction_reported: bool = False
    revisions: list = field(default_factory=list)
    original_corners_px: Optional[np.ndarray] = None

    def __post_init__(self):
        self.corners_px = np.asarray(self.corners_px, float).reshape(4, 2)
        if self.original_corners_px is None:
            self.original_corners_px = self.corners_px.copy()
        if self.corner_source not in CORNER_SOURCES:
            raise ValueError(f"corner_source {self.corner_source!r} onbekend")


def correct_corner(obs, index, new_uv, edited_by, edited_at, reason=None):
    """Menselijke hoekcorrectie: geeft een NIEUWE waarneming terug; `original_corners_px` en de eerdere revisies blijven intact."""
    if not 0 <= index < 4:
        raise ValueError("hoekindex 0..3")
    new = copy.deepcopy(obs)
    c = new.corners_px.copy()
    before = c[index].tolist()
    c[index] = np.asarray(new_uv, float)
    new.revisions.append({"revision": len(obs.revisions) + 1, "corner_index": index, "corner_name": CORNER_ORDER[index],
                          "before_px": before, "after_px": c[index].tolist(), "edited_by": edited_by,
                          "edited_at": edited_at, "reason": reason})
    new.corners_px = c
    new.corner_source = "MANUAL_CORRECTED"
    return new


def stable_seed(*parts):
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:4], "big")
