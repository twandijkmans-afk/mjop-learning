"""Zuivere geometrie. Coordinatenstelsels (zie docs/contract_and_coordinates.md):

PIXEL   u naar rechts, v naar beneden, eenheid pixel, oorsprong = linkerbovenhoek van de linkerbovenpixel
        (pixelmiddens liggen op +0.5). Intrinsics (fx, fy, cx, cy) in pixels van HETZELFDE beeld.
CAMERA  OpenCV-conventie: x rechts, y omlaag, z vooruit (optische as). Eenheid meter als de schaal metrisch is.
WERELD  rechtshandig, Y omhoog (zwaartekracht-uitgelijnd), eenheid meter bij metrische tracking.
POSE    camera_to_world 4x4 (rij-hoofdvolgorde): x_wereld = R @ x_camera + t.
DIEPTE  depth_z: afstand LANGS DE OPTISCHE AS (niet de straallengte), in meter; 0/NaN/inf = ongeldig.
VLAK    n . x = d met |n| = 1; vlakcoordinaten (u, v) in meter via plane_basis.
Geen lensvervorming gemodelleerd (zie docs voor de consequenties).
"""
from dataclasses import dataclass

import numpy as np

UP = np.array([0.0, 1.0, 0.0])


@dataclass(frozen=True)
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    @property
    def K(self):
        return np.array([[self.fx, 0, self.cx], [0, self.fy, self.cy], [0, 0, 1.0]])

    def scaled(self, width, height):
        sx, sy = width / self.width, height / self.height
        return Intrinsics(self.fx * sx, self.fy * sy, self.cx * sx, self.cy * sy, width, height)


def make_pose(R, t):
    T = np.eye(4)
    T[:3, :3] = np.asarray(R, float)
    T[:3, 3] = np.asarray(t, float)
    return T


def look_pose(position, yaw_deg=0.0):
    """Camera naar -Z kijkend (OpenCV: z_cam = -Z_wereld), eventueel gedraaid om Y."""
    a = np.radians(yaw_deg)
    Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    return make_pose(Ry @ np.diag([1.0, -1.0, -1.0]), position)


def rays_world(pose, intr, uv):
    """uv: (N,2) pixels. Geeft (origin(3,), dirs(N,3) eenheidsvectoren in wereldcoordinaten)."""
    uv = np.atleast_2d(np.asarray(uv, float))
    d = np.stack([(uv[:, 0] - intr.cx) / intr.fx, (uv[:, 1] - intr.cy) / intr.fy, np.ones(len(uv))], axis=1)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    return pose[:3, 3].copy(), d @ pose[:3, :3].T


def project(pose, intr, Xw):
    """Wereld -> (uv (N,2), depth_z (N,)). depth_z <= 0: achter de camera."""
    Xw = np.atleast_2d(np.asarray(Xw, float))
    Xc = (Xw - pose[:3, 3]) @ pose[:3, :3]
    z = Xc[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = np.stack([intr.fx * Xc[:, 0] / z + intr.cx, intr.fy * Xc[:, 1] / z + intr.cy], axis=1)
    return uv, z


def unproject_depth(pose, intr, uv, depth_z):
    """Pixel + depth_z -> wereldpunt. Dit is een puntmeting op PRECIES die pixel; zie plane/levels voor waarom een hoek
    daarmee niet automatisch betrouwbaar is."""
    uv = np.atleast_2d(np.asarray(uv, float))
    z = np.asarray(depth_z, float).reshape(-1)
    Xc = np.stack([(uv[:, 0] - intr.cx) / intr.fx * z, (uv[:, 1] - intr.cy) / intr.fy * z, z], axis=1)
    return Xc @ pose[:3, :3].T + pose[:3, 3]


def intersect_rays_plane(origin, dirs, n, d):
    """Snijpunten van stralen met n.x = d. Geeft (punten (N,3), t (N,), cos_incidence (N,)); t is NaN bij parallel of achter."""
    denom = dirs @ n
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (d - origin @ n) / denom
    t = np.where((np.abs(denom) < 1e-9) | (t <= 0), np.nan, t)
    return origin + dirs * t[:, None], t, np.abs(denom)


def plane_basis(n):
    """(e_u, e_v) orthonormaal in het vlak; e_v is de projectie van 'omhoog'. Voor een verticaal vlak: e_v = Y."""
    n = np.asarray(n, float) / np.linalg.norm(n)
    v = UP - (UP @ n) * n
    if np.linalg.norm(v) < 1e-6:  # horizontaal vlak: kies willekeurige maar vaste as
        v = np.array([0.0, 0.0, 1.0]) - (n[2]) * n
    v /= np.linalg.norm(v)
    u = np.cross(v, n)
    return u / np.linalg.norm(u), v


def plane_coords(P, n, origin=None):
    eu, ev = plane_basis(n)
    P = np.atleast_2d(P)
    o = np.zeros(3) if origin is None else origin
    return np.stack([(P - o) @ eu, (P - o) @ ev], axis=1)


def signed_plane_distance(P, n, d):
    return np.atleast_2d(P) @ n - d


def in_convex_polygon(pts, poly):
    """Vectorized punt-in-convex-vierhoek (pts (N,2), poly (K,2)); werkt voor beide windingrichtingen."""
    poly = np.asarray(poly, float)
    sign = None
    inside = np.ones(len(pts), bool)
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        cr = (b[0] - a[0]) * (pts[:, 1] - a[1]) - (b[1] - a[1]) * (pts[:, 0] - a[0])
        if sign is None:
            sign = 1.0 if signed_area(poly) >= 0 else -1.0
        inside &= cr * sign >= 0
    return inside


def signed_area(poly):
    p = np.asarray(poly, float)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def scale_polygon(poly, s):
    c = np.mean(poly, axis=0)
    return c + (np.asarray(poly, float) - c) * s


def is_simple_convex_quad(poly, min_rel_area=1e-4, image_area=None):
    """Vierhoek zonder kruising, convex, met consistent winding. Detecteert verwisselde hoeken (vlinderdas)."""
    p = np.asarray(poly, float)
    if p.shape != (4, 2) or not np.all(np.isfinite(p)):
        return False
    s = []
    for i in range(4):
        a, b, c = p[i], p[(i + 1) % 4], p[(i + 2) % 4]
        s.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    s = np.array(s)
    if not (np.all(s > 0) or np.all(s < 0)):
        return False
    return abs(signed_area(p)) > (min_rel_area * (image_area or 1.0))


def angle_between_deg(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = abs(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))
