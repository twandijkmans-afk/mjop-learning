"""Gevelopbouw: rollen van contouren op één gevelfoto en de hoeveelheden die daaruit volgen.

Referentie-implementatie (Python) van PhotoWalkCore/FacadeRoles.swift, ContourOrganizer.swift, OuterFrameSearch.swift en
FacadeComposition.swift. De Swift-tests vergelijken hun uitkomsten met `facade_parity_cases.json` (gemaakt door `build_parity_cases`).

Rollen (zie docs/facade_composition_v1.md):
  FACADE_GROSS  bruto gevelvlak (door de gebruiker getekend)
  OPENING       raam-/deuropening in de gevel; hier gelijkgesteld aan de buitenmaat van het kozijn (aanname, dagkant niet gemeten)
  FRAME_OUTER   buitencontour van het kozijn (buitenmaat)
  GLASS_PANE    één glasvlak binnen een kozijn; telt NOOIT als kozijn

Uitgangspunten:
- Een losse rechthoek kan glas of kozijn zijn: status UNVERIFIED, geen kozijnmaat tot de gebruiker de buitencontour bevestigt.
- Een vergroting van glas naar buitenkozijn is altijd een VOORSTEL (PROPOSED_EXPANSION), nooit vanzelf een maat.
- Ook een automatisch gevonden buitencontour rond glas (DETECTED_ENCLOSING_PANES) is alleen indicatief tot bevestiging.
- Meerdere glasvlakken binnen één kozijn vormen één opening (nooit meerdere kozijnen).
- Zonder betrouwbare schaal geen m² (UNKNOWN). Het onderhouds-/schilderoppervlak van een kozijn wordt NIET afgeleid
  (niet gelijk aan buitenkozijn min glas).
Alle drempels zijn PROVISIONAL_UNVALIDATED: niet getoetst op echte gevels.
"""
import math
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

import numpy as np

ROLES = ("FACADE_GROSS", "OPENING", "FRAME_OUTER", "GLASS_PANE")
OUTER_STATUSES = ("LEGACY", "MANUAL", "USER_CONFIRMED", "DETECTED_ENCLOSING_PANES", "UNVERIFIED", "PROPOSED_EXPANSION")
# ALLE automatisch herkende buitencontouren blijven voorlopig (alleen indicatief) tot de gebruiker bevestigt; LEGACY/MANUAL/USER_CONFIRMED niet.
AREA_BLOCKING_STATUSES = ("DETECTED_ENCLOSING_PANES", "UNVERIFIED", "PROPOSED_EXPANSION")
STATUS_ORDER = {"UNKNOWN": 0, "ESTIMATED": 1, "DERIVED": 2, "MEASURED": 3}

MAINTAINABLE_FRAME_NOTE = ("Niet afgeleid: buitenkozijn min glas is niet het onderhouds- of schilderoppervlak (profieldiepte, dagkanten, "
                           "roeden, glaslatten en binnen-/buitenzijde ontbreken). Meet of schat dit apart.")
OPENING_ASSUMPTION = "Aanname: opening = buitenmaat van het kozijn (dagkant/sponning niet gemeten)."


@dataclass(frozen=True)
class ContourConfig:
    """PROVISIONAL_UNVALIDATED."""
    min_rel_area: float = 0.0015          # t.o.v. het hele beeld
    max_rel_area: float = 0.9            # close-up van één kozijn mag groot zijn; het hele beeld niet
    duplicate_iou: float = 0.8            # vrijwel dezelfde vierhoek van twee detectoren
    contain_fraction: float = 0.85        # deel van de kleine vierhoek dat binnen de grote ligt
    contain_min_area_ratio: float = 1.15  # de grote moet duidelijk groter zijn
    min_glass_coverage: float = 0.30      # glas/buitenmaat; daaronder is de omsluitende vierhoek twijfelachtig (bv. deur met klein glas)
    pane_overlap: float = 0.6             # overlap langs de gedeelde as (deel van de kleinste)
    pane_max_gap: float = 0.35            # tussenruimte (stijl/tussenregel) t.o.v. de kleinste afmeting langs de andere as
    pane_size_ratio: float = 0.6          # afmeting langs de gedeelde as moet vergelijkbaar zijn


DEFAULT_CONTOUR = ContourConfig()


# ---------------------------------------------------------------- polygonen (pixels, (u, v))

def signed_area(p):
    s = 0.0
    n = len(p)
    for i in range(n):
        j = (i + 1) % n
        s += p[i][0] * p[j][1] - p[j][0] * p[i][1]
    return 0.5 * s


def area(p):
    return abs(signed_area(p))


def is_simple_convex_quad(p, image_area=1.0, min_rel_area=1e-4):
    if len(p) != 4 or not all(np.isfinite(c) for q in p for c in q):
        return False
    pos = neg = 0
    for i in range(4):
        a, b, c = p[i], p[(i + 1) % 4], p[(i + 2) % 4]
        s = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if s > 0:
            pos += 1
        elif s < 0:
            neg += 1
    return (pos == 4 or neg == 4) and area(p) > min_rel_area * image_area


def _ccw(p):
    return list(p) if signed_area(p) >= 0 else list(reversed(p))


def convex_intersection_area(a, b):
    """Oppervlak van de doorsnede van twee convexe polygonen (Sutherland-Hodgman)."""
    out = _ccw(a)
    clip = _ccw(b)
    for i in range(len(clip)):
        if not out:
            return 0.0
        c1, c2 = clip[i], clip[(i + 1) % len(clip)]
        inp, out = out, []

        def inside(p):
            return (c2[0] - c1[0]) * (p[1] - c1[1]) - (c2[1] - c1[1]) * (p[0] - c1[0]) >= 0

        def cross_pt(p, q):
            dx1, dy1 = q[0] - p[0], q[1] - p[1]
            dx2, dy2 = c2[0] - c1[0], c2[1] - c1[1]
            den = dx1 * dy2 - dy1 * dx2
            if abs(den) < 1e-12:
                return q
            t = ((c1[0] - p[0]) * dy2 - (c1[1] - p[1]) * dx2) / den
            return (p[0] + t * dx1, p[1] + t * dy1)

        for k in range(len(inp)):
            cur, prev = inp[k], inp[k - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(cross_pt(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross_pt(prev, cur))
    return area(out) if len(out) >= 3 else 0.0


def polygon_iou(a, b):
    inter = convex_intersection_area(a, b)
    uni = area(a) + area(b) - inter
    return inter / uni if uni > 0 else 0.0


def bounds(p):
    us = [q[0] for q in p]
    vs = [q[1] for q in p]
    return min(us), min(vs), max(us), max(vs)


def centroid(p):
    return (sum(q[0] for q in p) / len(p), sum(q[1] for q in p) / len(p))


def point_in_convex(pt, poly):
    sign = 1.0 if signed_area(poly) >= 0 else -1.0
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if ((b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])) * sign < 0:
            return False
    return True


# ---------------------------------------------------------------- contouren ordenen

@dataclass
class QuadCandidate:
    corners: list              # 4 x (u, v), TL, TR, BR, BL
    detector: str = ""
    score: float = 0.0


@dataclass
class OpeningGroup:
    outer: list                # voorgestelde of gedetecteerde buitencontour (4 x (u, v))
    outer_detected: bool       # True: de buitencontour is zelf een gedetecteerde vierhoek
    panes: list                # glasvlakken (lijst van 4 x (u, v)); leeg = onbekend
    evidence: str              # NESTED_PANES | PANE_GROUP | SINGLE
    status: str                # DETECTED_ENCLOSING_PANES | UNVERIFIED | PROPOSED_EXPANSION
    detector: str = ""
    score: float = 0.0
    glass_coverage: float = None


@dataclass
class IgnoredCandidate:
    corners: list
    detector: str
    reason: str                # INVALID_SHAPE | TOO_SMALL | TOO_LARGE | DUPLICATE | CONTAINS_OPENINGS


def _contains(big, small, cfg):
    ab, as_ = area(big), area(small)
    if as_ <= 0 or ab < cfg.contain_min_area_ratio * as_:
        return False
    return convex_intersection_area(big, small) / as_ >= cfg.contain_fraction


def _adjacent(a, b, cfg):
    """Twee glasvlakken naast/boven elkaar binnen één kozijn: overlap langs de ene as, kleine tussenruimte langs de andere."""
    ax0, ay0, ax1, ay1 = bounds(a)
    bx0, by0, bx1, by1 = bounds(b)
    for (a0, a1, b0, b1, c0, c1, d0, d1) in ((ay0, ay1, by0, by1, ax0, ax1, bx0, bx1), (ax0, ax1, bx0, bx1, ay0, ay1, by0, by1)):
        ha, hb = a1 - a0, b1 - b0                     # afmetingen langs de gedeelde as
        if min(ha, hb) <= 0 or min(ha, hb) / max(ha, hb) < cfg.pane_size_ratio:
            continue
        overlap = min(a1, b1) - max(a0, b0)
        if overlap < cfg.pane_overlap * min(ha, hb):
            continue
        wa, wb = c1 - c0, d1 - d0                     # afmetingen langs de andere as
        gap = max(d0 - c1, c0 - d1)                   # negatief = overlappend
        if -0.05 * min(wa, wb) <= gap <= cfg.pane_max_gap * min(wa, wb):
            return True
    return False


def _bbox_quad(polys):
    us = [q[0] for p in polys for q in p]
    vs = [q[1] for p in polys for q in p]
    u0, v0, u1, v1 = min(us), min(vs), max(us), max(vs)
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def organize(candidates, image_width, image_height, cfg=DEFAULT_CONTOUR):
    """Ordent kandidaat-vierhoeken (uit Vision-rechthoeken en -contouren) tot openingen met buitencontour en glasvlakken.

    Deterministisch. Geeft (groups, ignored)."""
    total = float(image_width) * float(image_height)
    ignored = []
    valid = []
    for c in candidates:
        corners = [tuple(map(float, p)) for p in c.corners]
        if not is_simple_convex_quad(corners, total):
            ignored.append(IgnoredCandidate(corners, c.detector, "INVALID_SHAPE"))
            continue
        a = area(corners)
        if a < cfg.min_rel_area * total:
            ignored.append(IgnoredCandidate(corners, c.detector, "TOO_SMALL"))
            continue
        if a > cfg.max_rel_area * total:
            ignored.append(IgnoredCandidate(corners, c.detector, "TOO_LARGE"))
            continue
        valid.append(QuadCandidate(corners, c.detector, float(c.score)))
    # dubbelingen (twee detectoren vinden dezelfde vierhoek): hoogste score, dan grootste, blijft
    valid.sort(key=lambda c: (-c.score, -area(c.corners), bounds(c.corners)))
    uniq = []
    for c in valid:
        if any(polygon_iou(k.corners, c.corners) > cfg.duplicate_iou for k in uniq):
            ignored.append(IgnoredCandidate(c.corners, c.detector, "DUPLICATE"))
        else:
            uniq.append(c)
    uniq.sort(key=lambda c: (-area(c.corners), bounds(c.corners)))
    n = len(uniq)
    parent = [None] * n
    for i in range(n):                                # kleinste omsluitende vierhoek is de ouder
        best = None
        for j in range(n):
            if i != j and _contains(uniq[j].corners, uniq[i].corners, cfg):
                if best is None or area(uniq[j].corners) < area(uniq[best].corners):
                    best = j
        parent[i] = best
    children = [[k for k in range(n) if parent[k] == i] for i in range(n)]
    has_children = [bool(children[i]) for i in range(n)]
    groups = []
    roots = []                                         # vierhoeken die zelf op het hoogste niveau tellen
    for i in range(n):
        if not has_children[i]:
            continue
        if any(has_children[k] for k in children[i]):
            # omsluit zelf openingen (bv. een gevelvlak of een groot paneel): geen kozijn
            ignored.append(IgnoredCandidate(uniq[i].corners, uniq[i].detector, "CONTAINS_OPENINGS"))
            continue
        panes = sorted((uniq[k].corners for k in children[i]), key=lambda p: (bounds(p)[1], bounds(p)[0]))
        cov = min(1.0, sum(area(p) for p in panes) / area(uniq[i].corners))
        groups.append(OpeningGroup(outer=uniq[i].corners, outer_detected=True, panes=panes, evidence="NESTED_PANES",
                                   status="DETECTED_ENCLOSING_PANES" if cov >= cfg.min_glass_coverage else "UNVERIFIED",
                                   detector=uniq[i].detector, score=uniq[i].score, glass_coverage=round(cov, 6)))
    for i in range(n):
        if has_children[i]:
            continue
        p = parent[i]
        if p is not None and not any(has_children[k] for k in children[p]):
            continue                                   # glasvlak van een kozijn dat hierboven al een groep is
        roots.append(i)
    # losse vierhoeken die naast elkaar liggen: één kozijn met meerdere glasvlakken (voorstel)
    comp = {i: i for i in roots}

    def find(x):
        while comp[x] != x:
            comp[x] = comp[comp[x]]
            x = comp[x]
        return x

    for a_i in range(len(roots)):
        for b_i in range(a_i + 1, len(roots)):
            ia, ib = roots[a_i], roots[b_i]
            if _adjacent(uniq[ia].corners, uniq[ib].corners, cfg):
                ra, rb = find(ia), find(ib)
                if ra != rb:
                    comp[max(ra, rb)] = min(ra, rb)
    members = {}
    for i in roots:
        members.setdefault(find(i), []).append(i)
    for key in sorted(members):
        ms = members[key]
        if len(ms) == 1:
            c = uniq[ms[0]]
            groups.append(OpeningGroup(outer=c.corners, outer_detected=True, panes=[], evidence="SINGLE", status="UNVERIFIED",
                                       detector=c.detector, score=c.score))
        else:
            panes = sorted((uniq[k].corners for k in ms), key=lambda p: (bounds(p)[1], bounds(p)[0]))
            best = max(ms, key=lambda k: (uniq[k].score, -k))
            groups.append(OpeningGroup(outer=_bbox_quad(panes), outer_detected=False, panes=panes, evidence="PANE_GROUP",
                                       status="PROPOSED_EXPANSION", detector=uniq[best].detector, score=uniq[best].score))
    groups.sort(key=lambda g: (bounds(g.outer)[1], bounds(g.outer)[0]))
    return groups, ignored


# ---------------------------------------------------------------- voorstel: van glas naar buitenkozijn (randzoeker)

@dataclass(frozen=True)
class ExpansionConfig:
    """PROVISIONAL_UNVALIDATED."""
    samples: int = 24                 # meetpunten langs elke zijde
    side_margin: float = 0.15         # uiteinden van de zijde overslaan (hoeken, aansluitingen)
    min_offset_px: float = 4.0        # binnen deze afstand ligt nog de rand glas/kozijn zelf
    max_offset_rel: float = 0.30      # maximaal zoeken tot dit deel van de aangrenzende afmeting
    min_edge_strength: float = 6.0    # minimale gemiddelde grijswaardesprong (0..255)
    rel_to_inner_edge: float = 0.35   # t.o.v. de rand bij de vierhoek zelf
    min_consistency: float = 0.7      # deel van de meetpunten met hetzelfde teken


DEFAULT_EXPANSION = ExpansionConfig()


def _sample(img, u, v):
    """Bilineaire grijswaarde; img[v, u], pixelmiddens op +0.5 (zelfde conventie als de app)."""
    h, w = img.shape
    x, y = u - 0.5, v - 0.5
    x0, y0 = int(np.floor(x)), int(np.floor(y))
    fx, fy = x - x0, y - y0

    def px(xx, yy):
        return float(img[min(max(yy, 0), h - 1), min(max(xx, 0), w - 1)])

    top = (1 - fx) * px(x0, y0) + fx * px(x0 + 1, y0)            # zelfde rekenvolgorde als Swift (pariteit)
    bottom = (1 - fx) * px(x0, y0 + 1) + fx * px(x0 + 1, y0 + 1)
    return (1 - fy) * top + fy * bottom


def _line_intersection(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + t * d[0], p[1] + t * d[1])


def edge_profile(img, quad, side, cfg=DEFAULT_EXPANSION):
    """Randsterkte als functie van de afstand naar buiten voor één zijde; geeft (offsets, strengths, consistencies)."""
    c = centroid(quad)
    a, b = quad[side], quad[(side + 1) % 4]
    du, dv = b[0] - a[0], b[1] - a[1]
    length = (du * du + dv * dv) ** 0.5
    nu, nv = -dv / length, du / length
    mu, mv = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if (mu - c[0]) * nu + (mv - c[1]) * nv < 0:
        nu, nv = -nu, -nv
    prev, nxt = quad[(side + 3) % 4], quad[(side + 2) % 4]
    adj = 0.5 * (math.hypot(a[0] - prev[0], a[1] - prev[1]) + math.hypot(b[0] - nxt[0], b[1] - nxt[1]))
    t_max = int(np.floor(cfg.max_offset_rel * adj))
    offsets, strengths, consist = [], [], []
    for t in range(0, max(t_max, 0) + 1):
        g = []
        for k in range(cfg.samples):
            s = cfg.side_margin + (1 - 2 * cfg.side_margin) * (k + 0.5) / cfg.samples
            pu, pv = a[0] + du * s + nu * t, a[1] + dv * s + nv * t
            g.append(_sample(img, pu + nu, pv + nv) - _sample(img, pu - nu, pv - nv))
        mean = sum(g) / len(g)
        sign = 1.0 if mean >= 0 else -1.0
        same = sum(1 for x in g if x * sign > 0) / len(g)
        offsets.append(float(t))
        strengths.append(abs(mean))
        consist.append(same)
    return offsets, strengths, consist, (nu, nv)


def propose_outer(img, quad, cfg=DEFAULT_EXPANSION):
    """Zoekt per zijde de eerste duidelijke evenwijdige rand buiten de vierhoek (rand kozijn/muur) en geeft de vergrote vierhoek.

    ALTIJD een voorstel (PROPOSED_EXPANSION); None als een zijde geen duidelijke rand heeft (dan tekent de gebruiker zelf)."""
    quad = [tuple(map(float, p)) for p in quad]
    shifts = []
    for side in range(4):
        offs, st, co, n = edge_profile(img, quad, side, cfg)
        if len(st) < 3:
            return None
        inner = max(st[: int(cfg.min_offset_px) + 1]) if st else 0.0
        threshold = max(cfg.min_edge_strength, cfg.rel_to_inner_edge * inner)
        chosen = None
        for i in range(1, len(st) - 1):
            if offs[i] < cfg.min_offset_px:
                continue
            if st[i] >= threshold and co[i] >= cfg.min_consistency and st[i] >= st[i - 1] and st[i] >= st[i + 1]:
                chosen = (offs[i], st[i])
                break
        if chosen is None:
            return None
        shifts.append((chosen[0], n, chosen[1]))
    lines = []
    for side in range(4):
        a, b = quad[side], quad[(side + 1) % 4]
        t, (nu, nv), _ = shifts[side]
        lines.append(((a[0] + nu * t, a[1] + nv * t), (b[0] - a[0], b[1] - a[1])))
    out = []
    for i in range(4):                                  # hoek i = snijpunt van zijde i-1 en zijde i
        p = _line_intersection(lines[(i + 3) % 4][0], lines[(i + 3) % 4][1], lines[i][0], lines[i][1])
        if p is None:
            return None
        out.append((round(p[0], 6), round(p[1], 6)))
    if not is_simple_convex_quad(out):
        return None
    return {"quad": out, "offsets_px": [s[0] for s in shifts], "strengths": [round(s[2], 6) for s in shifts]}


# ---------------------------------------------------------------- hoeveelheden

def _mm3(x):
    """m² afronden op 0,001 (half-up), als Decimal."""
    return Decimal(str(x)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def worst_status(statuses):
    if not statuses:
        return "UNKNOWN"
    return min(statuses, key=lambda s: STATUS_ORDER[s])


def planar_polygon_area_m2(pixels, pose, intr, n, d):
    """Oppervlak (m²) van een pixelpolygoon geprojecteerd op het vlak n.x = d. pose = (R, t) camera->wereld; intr = (fx, fy, cx, cy)."""
    R, t = pose
    fx, fy, cx, cy = intr
    n = np.asarray(n, float)
    pts = []
    for (u, v) in pixels:
        ray = np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
        ray = ray / np.linalg.norm(ray)
        dw = np.asarray(R, float) @ ray
        den = float(dw @ n)
        if abs(den) < 1e-9:
            return None
        s = (d - float(np.asarray(t, float) @ n)) / den
        if s <= 0:
            return None
        pts.append(np.asarray(t, float) + dw * s)
    acc = np.zeros(3)
    for i in range(len(pts)):
        acc += np.cross(pts[i], pts[(i + 1) % len(pts)])
    return abs(float(acc @ n)) / 2.0


@dataclass
class OpeningInput:
    id: str
    outer_px: list
    area_m2: Decimal = None           # bruto buitenmaat uit de bestaande kozijnmeting (None = geen betrouwbare maat)
    status: str = "UNKNOWN"
    plane_n: tuple = None             # vlak van de kozijnmeting (voor het projecteren van glasvlakken)
    plane_d: float = None
    panes_px: list = field(default_factory=list)


def _q(value, status, basis, missing=None, partial=None):
    return {"value_m2": None if value is None else str(value), "status": status, "basis": basis,
            "missing": list(missing or []), "partial_value_m2": None if partial is None else str(partial)}


def compose(openings, pose=None, intr=None, facade_px=None, facade_plane=None, facade_plane_status="UNKNOWN"):
    """Gevelopbouw van één foto. Rekent alleen met betrouwbare schaal; anders UNKNOWN met de ontbrekende onderdelen."""
    flags = []
    if facade_px is not None:
        inside = [o for o in openings if point_in_convex(centroid(o.outer_px), facade_px)]
    else:
        inside = list(openings)
    # bruto gevel
    if facade_px is None:
        gross = _q(None, "UNKNOWN", "Geen gevelvlak getekend.", ["FACADE_POLYGON"])
    elif facade_plane is None or facade_plane_status == "UNKNOWN" or pose is None:
        gross = _q(None, "UNKNOWN", "Geen betrouwbaar gevelvlak (schaal) voor deze foto.", ["FACADE_PLANE"])
    else:
        a = planar_polygon_area_m2(facade_px, pose, intr, facade_plane[0], facade_plane[1])
        gross = (_q(_mm3(a), facade_plane_status, "Getekend gevelvlak geprojecteerd op het gevelvlak.") if a is not None
                 else _q(None, "UNKNOWN", "Projectie op het gevelvlak mislukt.", ["FACADE_PLANE"]))
    # buitenkozijnen (= openingen, aanname)
    known = [o for o in inside if o.area_m2 is not None and o.status != "UNKNOWN"]
    missing_frames = [o.id for o in inside if o not in known]
    part = sum((Decimal(str(o.area_m2)) for o in known), Decimal("0"))
    if not inside:
        # geen herkende kozijnen is GEEN bewijs dat er geen openingen zijn (herkenning kan ze missen): onbekend, nooit 0
        frame_outer = _q(None, "UNKNOWN", "Geen kozijnen herkend of aangegeven in dit gevelvlak; dat betekent niet dat er geen openingen zijn.",
                         ["NO_FRAMES_IN_FACADE"])
    elif missing_frames:
        frame_outer = _q(None, "UNKNOWN", "Niet alle kozijnen hebben een betrouwbare buitenmaat.", missing_frames, part if known else None)
    else:
        frame_outer = _q(part, worst_status([o.status for o in known]), "Som van de bruto buitenmaten (breedte x hoogte) van de kozijnen.")
    openings_q = dict(frame_outer)
    openings_q["basis"] = OPENING_ASSUMPTION + " " + frame_outer["basis"]
    # glas
    glass_known, glass_missing, glass_status = Decimal("0"), [], []
    for o in inside:
        if not o.panes_px:
            glass_missing.append(o.id + ":GEEN_GLASVLAKKEN")
            continue
        if o.plane_n is None or o.plane_d is None or o.status == "UNKNOWN" or pose is None:
            glass_missing.append(o.id + ":GEEN_SCHAAL")
            continue
        s = Decimal("0")
        ok = True
        for p in o.panes_px:
            a = planar_polygon_area_m2(p, pose, intr, o.plane_n, o.plane_d)
            if a is None:
                ok = False
                break
            s += _mm3(a)
        if not ok:
            glass_missing.append(o.id + ":PROJECTIE")
            continue
        glass_known += s
        glass_status.append("ESTIMATED" if o.status == "MEASURED" else o.status)
    if glass_missing:
        glass = _q(None, "UNKNOWN", "Niet van alle kozijnen zijn de glasvlakken met schaal bekend.", glass_missing,
                   glass_known if glass_status else None)
    elif not inside:
        glass = _q(None, "UNKNOWN", "Geen kozijnen in dit gevelvlak.", [])
    else:
        glass = _q(glass_known, worst_status(glass_status), "Som van de glasvlakken, geprojecteerd op het vlak van het eigen kozijn.")
    # netto gesloten gevel
    if gross["value_m2"] is None or frame_outer["value_m2"] is None:
        net = _q(None, "UNKNOWN", "Bruto gevel en alle openingen zijn nodig.",
                 (gross["missing"] or []) + (frame_outer["missing"] or []))
    else:
        g, o = Decimal(gross["value_m2"]), Decimal(frame_outer["value_m2"])
        if o > g:
            flags.append("OPENINGS_EXCEED_FACADE")
            net = _q(None, "UNKNOWN", "De openingen zijn groter dan het getekende gevelvlak; controleer de contouren.", ["CONSISTENT_CONTOURS"])
        else:
            net = _q(g - o, worst_status([gross["status"], frame_outer["status"]]), "Bruto gevel min openingen (buitenmaat kozijnen).")
    maintainable = _q(None, "UNKNOWN", MAINTAINABLE_FRAME_NOTE, ["NOT_DERIVED"])
    return {"facade_gross": gross, "openings": openings_q, "frame_outer": frame_outer, "glass": glass, "closed_facade_net": net,
            "maintainable_frame_surface": maintainable, "flags": flags, "openings_in_facade": [o.id for o in inside]}


def plausibility_3dbag(facade_gross_total_m2, b3_opp_buitenmuur_m2):
    """Alleen een aanvullende controle: nooit bewijs dat een fotometing klopt. Geeft adviescodes."""
    if facade_gross_total_m2 is None or b3_opp_buitenmuur_m2 is None:
        return []
    if Decimal(str(facade_gross_total_m2)) > Decimal(str(b3_opp_buitenmuur_m2)) * Decimal("1.05"):
        return ["FACADE_GROSS_EXCEEDS_3DBAG_WALL_AREA"]
    return []


# ---------------------------------------------------------------- synthetisch testbeeld (identiek in Swift: SyntheticFacade.swift)

def synthetic_facade_gray(width, height, windows, wall=118, mortar=196, frame=236, glass=58, brick_h=24, brick_w=60):
    """Grijswaardenbeeld (uint8, [v, u]): metselwerk met voegen en assen-rechte kozijnen.

    windows: lijst van dicts {outer: (u0, v0, u1, v1), profile: px, mullions: n verticale tussenstijlen, transom: bool}.
    Geen ruis, geen randomness: dezelfde invoer geeft exact hetzelfde beeld (ook in Swift). Alleen voor tests; GEEN foto."""
    img = np.full((height, width), wall, dtype=np.uint8)
    for v in range(height):
        row = v // brick_h
        if v % brick_h in (0, 1):
            img[v, :] = mortar
            continue
        off = 0 if row % 2 == 0 else brick_w // 2
        for u in range(width):
            if (u + off) % brick_w in (0, 1):
                img[v, u] = mortar
    for w in windows:
        u0, v0, u1, v1 = w["outer"]
        prof = w["profile"]
        img[v0:v1, u0:u1] = frame
        iu0, iv0, iu1, iv1 = u0 + prof, v0 + prof, u1 - prof, v1 - prof
        n = int(w.get("mullions", 0))
        bar = max(2, prof // 2)
        cols = []
        inner_w = iu1 - iu0
        edges = [iu0 + round(inner_w * k / (n + 1)) for k in range(n + 2)]
        for k in range(n + 1):
            a = edges[k] + (bar // 2 if k > 0 else 0)
            b = edges[k + 1] - (bar - bar // 2 if k < n else 0)
            cols.append((a, b))
        rows = [(iv0, iv1)]
        if w.get("transom"):
            mid = iv0 + (iv1 - iv0) // 3
            rows = [(iv0, mid - bar // 2), (mid + bar - bar // 2, iv1)]
        for (a, b) in cols:
            for (c, d) in rows:
                img[c:d, a:b] = glass
    return img


def synthetic_truth(windows):
    """Ware buitencontour en glasvlakken (pixels) van synthetic_facade_gray, in dezelfde volgorde."""
    out = []
    for w in windows:
        u0, v0, u1, v1 = w["outer"]
        prof = w["profile"]
        iu0, iv0, iu1, iv1 = u0 + prof, v0 + prof, u1 - prof, v1 - prof
        n = int(w.get("mullions", 0))
        bar = max(2, prof // 2)
        inner_w = iu1 - iu0
        edges = [iu0 + round(inner_w * k / (n + 1)) for k in range(n + 2)]
        cols = [(edges[k] + (bar // 2 if k > 0 else 0), edges[k + 1] - (bar - bar // 2 if k < n else 0)) for k in range(n + 1)]
        rows = [(iv0, iv1)]
        if w.get("transom"):
            mid = iv0 + (iv1 - iv0) // 3
            rows = [(iv0, mid - bar // 2), (mid + bar - bar // 2, iv1)]
        panes = [[(a, c), (b, c), (b, d), (a, d)] for (a, b) in cols for (c, d) in rows]
        out.append({"outer": [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], "panes": panes})
    return out
