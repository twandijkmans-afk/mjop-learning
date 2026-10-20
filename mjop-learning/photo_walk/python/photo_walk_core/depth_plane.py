"""Niveau A v2: robuuste LiDAR-meting met meerdere kandidaatvlakken en meerdere onafhankelijke dieptaframes.

Waarom (zie docs/lidar_measurement_v2.md): een enkel RANSAC-vlak door een ring rond het kader mengt wand, dagkanten, kozijnprofiel, vensterbank en glas, en
rekent de hoeken daarna op het WANDvlak uit. Bij een terugliggend kozijn geeft dat een stille, plausibele onderschatting; bij gemengde diepte een kale afwijzing.
Deze module:
  1. verzamelt dieptepunten uit enkele onafhankelijke frames (verschillende camerastandpunten) in een gemeenschappelijk wereldstelsel,
  2. deelt ze in per zijde (boven/rechts/onder/links) in ring (wand), binnenband (kozijnprofiel) en glas,
  3. zoekt in de ring meerdere vlakken (sequentieel RANSAC met ruisafhankelijke drempel) en classificeert ze (WAND / DAGKANT / PARALLELLE STAP),
  4. bepaalt de terugligging van het kozijnvlak t.o.v. de wand uit de binnenband per zijde (groepsconsensus); weigert als dat niet kan,
  5. rekent de hoekstralen uit op het gekozen kozijnvlak en controleert de hoeken onafhankelijk met de gemeten hoekdiepte,
  6. controleert dat elk onafhankelijk frame hetzelfde vlak en dezelfde maat geeft.
Alle drempels zijn PROVISIONAL en volgen een ruismodel sigma(z); ze zijn niet losser gemaakt maar afstandsafhankelijk gemaakt en gecombineerd met extra onafhankelijke controles.
"""
import numpy as np

from . import quality as q
from .config import Config
from .geometry import UP, in_convex_polygon, project, rays_world, scale_polygon, signed_area, unproject_depth
from .plane import ransac_plane_mask

SIDES = ("TOP", "RIGHT", "BOTTOM", "LEFT")


def sigma_at(z, cfg: Config):
    return cfg.lidar_sigma0_m + cfg.lidar_sigma1_per_m * z


def thr_at(z, cfg: Config):
    return cfg.thr_k * sigma_at(z, cfg) + cfg.relief_tol_m


# ------------------------------------------------------------------ punten en gebieden

class Regions:
    """Gebieden rond het kader (in PIXELS van het capture-beeld): ring (wand), binnenband (kozijnprofiel), glas; per zijde."""

    def __init__(self, quad, cfg: Config):
        self.quad = np.asarray(quad, float)
        self.c = self.quad.mean(axis=0)
        self.sgn = 1.0 if signed_area(self.quad) >= 0 else -1.0
        self.edges = [(self.quad[i], self.quad[(i + 1) % 4]) for i in range(4)]
        self.h = []
        for a, b in self.edges:
            self.h.append(max(self._cross_dist(a, b, self.c[None, :])[0], 1e-6))
        self.poly = {k: scale_polygon(self.quad, v) for k, v in
                     (("ring_in", cfg.ring_inner_scale), ("ring_out", cfg.ring_outer_scale), ("band_lo", cfg.band_lo_scale),
                      ("band_hi", cfg.band_hi_scale), ("glass", cfg.glass_scale))}

    def _cross_dist(self, a, b, pts):
        e = b - a
        return ((e[0] * (pts[:, 1] - a[1]) - e[1] * (pts[:, 0] - a[0])) * self.sgn) / max(np.linalg.norm(e), 1e-9)

    def classify(self, uv):
        """kind: 0 buiten, 1 ring, 2 binnenband, 3 glas; side: 0..3 (TOP,RIGHT,BOTTOM,LEFT)."""
        n = len(uv)
        kind = np.zeros(n, int)
        side = np.zeros(n, int)
        if n == 0:
            return kind, side
        in_out = in_convex_polygon(uv, self.poly["ring_out"])
        in_ringin = in_convex_polygon(uv, self.poly["ring_in"])
        ring = in_out & ~in_ringin
        band = in_convex_polygon(uv, self.poly["band_hi"]) & ~in_convex_polygon(uv, self.poly["band_lo"])
        glass = in_convex_polygon(uv, self.poly["glass"])
        kind[ring], kind[band], kind[glass] = 1, 2, 3
        d = np.stack([self._cross_dist(a, b, uv) / h for (a, b), h in zip(self.edges, self.h)], axis=1)
        side = np.argmin(d, axis=1)
        return kind, side


def grid_points(view, cfg: Config):
    """Geldige dieptepunten van een frame: (wereldpunten, uv in dit frame, z)."""
    Hd, Wd = view.depth.shape
    sx, sy = view.intrinsics.width / Wd, view.intrinsics.height / Hd
    jj, ii = np.meshgrid(np.arange(Wd), np.arange(Hd))
    uv = np.stack([(jj + 0.5) * sx, (ii + 0.5) * sy], axis=-1).reshape(-1, 2)
    z = view.depth.reshape(-1).astype(float)
    ok = np.isfinite(z) & (z >= cfg.depth_min_range_m) & (z <= cfg.depth_max_range_m)
    X = unproject_depth(view.pose, view.intrinsics, uv[ok], z[ok])
    return X, uv[ok], z[ok]


def select_support_frames(capture, supports, cfg: Config):
    """Kies onafhankelijke ondersteunende frames: tracking NORMAL, diepte aanwezig, voldoende standpuntverschil (translatie of rotatie) t.o.v. alle al gekozen frames.
    Sterk gecorreleerde frames (vrijwel zelfde standpunt) leveren geen onafhankelijke bevestiging en worden NIET gebruikt."""
    chosen = [capture]
    rejected = []
    for v in supports:
        if v.depth is None or v.tracking_state != "NORMAL":
            rejected.append((v.frame_id, "TRACKING_OR_DEPTH"))
            continue
        ok = True
        for c in chosen:
            dt = float(np.linalg.norm(v.pose[:3, 3] - c.pose[:3, 3]))
            cosr = (np.trace(v.pose[:3, :3].T @ c.pose[:3, :3]) - 1) / 2
            rot = float(np.degrees(np.arccos(np.clip(cosr, -1, 1))))
            if dt < cfg.min_baseline_m and rot < cfg.min_rotation_deg:
                ok = False
                break
        if ok and len(chosen) < 1 + cfg.max_support_frames:
            chosen.append(v)
        else:
            rejected.append((v.frame_id, "CORRELATED_OR_LIMIT"))
    return chosen, rejected


# ------------------------------------------------------------------ vlakken

def sequential_planes(P, side, thr, cfg: Config, seed):
    planes, remaining = [], np.ones(len(P), bool)
    for k in range(cfg.max_planes):
        idx = np.where(remaining)[0]
        if len(idx) < cfg.min_plane_points:
            break
        res = ransac_plane_mask(P[idx], thr, cfg.ransac_iterations_v2, seed + 17 * k, cfg.max_ransac_points)
        if res is None:
            break
        n, d, m, rms, ctr = res
        if m.sum() < max(cfg.min_plane_points, cfg.plane_min_fraction * len(P)):
            break
        gidx = idx[m]
        sides = np.bincount(side[gidx], minlength=4)
        Pin = P[gidx]
        spread = float(np.sqrt(np.mean(np.sum((Pin - ctr) ** 2, axis=1) - ((Pin - ctr) @ n) ** 2)))
        planes.append({"n": n, "d": d, "idx": gidx, "rms": rms, "centroid": ctr, "count": int(m.sum()), "sides": sides, "spread": spread})
        remaining[gidx] = False
    return planes, remaining


def _orient(n, d, centroid, cam_pos):
    if n @ (cam_pos - centroid) < 0:
        return -n, -d
    return n, d


def classify_planes(planes, cam_pos, cfg: Config):
    for p in planes:
        p["n"], p["d"] = _orient(p["n"], p["d"], p["centroid"], cam_pos)
        v = p["centroid"] - cam_pos
        v = v / max(np.linalg.norm(v), 1e-9)
        p["facing"] = float(abs(p["n"] @ v))
        p["vertical"] = float(abs(p["n"] @ UP))
        p["role"] = "FACADE_CANDIDATE" if (p["facing"] >= cfg.facade_min_facing and p["vertical"] <= cfg.facade_max_vertical) else "REVEAL_OR_LEDGE"
    return planes


def inplane_std(P, n):
    """(grootste, kleinste) standaardafwijking (m) van punten binnen hun vlak (normaal n). Gesloten vorm; geen basiskeuze nodig."""
    P = np.asarray(P, float)
    if len(P) < 3:
        return 0.0, 0.0
    X = P - P.mean(axis=0)
    X = X - np.outer(X @ n, n)
    C = X.T @ X / len(X)
    tr = float(np.trace(C))
    p2 = float(np.sum(C * C))
    det2 = max((tr * tr - p2) / 2.0, 0.0)
    disc = max(tr * tr / 4.0 - det2, 0.0) ** 0.5
    l1, l2 = tr / 2.0 + disc, max(tr / 2.0 - disc, 0.0)
    return float(max(l1, 0.0) ** 0.5), float(l2 ** 0.5)


def pick_facade(planes, Pr, side, z_med, cfg: Config, quad_diag_m=None):
    """Kies het wandvlak of geef een specifieke weigering. Geeft (plane|None, code|None, detail, assessment).

    Aparte controles (geen versoepeling, wel een zuivere toewijzing van punten):
      1. lokale vlakkwaliteit: rms van de inliers en robuuste spreiding van de punten die bij DIT vlak horen (inliers + niet-toegewezen punten dicht bij het vlak);
         punten van andere herkende vlakken (dagkant, vensterbank, parallelle stap) worden NIET meegeteld;
      2. conflicterende vlakken (parallel of niet-parallel, vergelijkbaar groot) => ambigu;
      3. ondersteuning: aandeel van de niet door andere structuur verklaarde ringpunten + onverklaard aandeel;
      4. ruimtelijke verdeling over de vier zijden (aandeel per zijde, niet alleen een absoluut minimum) en in-vlak omvang."""
    thr = thr_at(z_med, cfg)
    sig = sigma_at(z_med, cfg)
    n_ring = len(Pr)
    A = {"ring_points": int(n_ring), "gate": None, "reasons": [], "representative": False,
         "ring_total_spread_m": None, "note_ring_spread": "alleen diagnostische achtergrondwaarde; geen kwaliteitsgate"}
    cands = sorted([p for p in planes if p["role"] == "FACADE_CANDIDATE"], key=lambda p: -p["count"])
    A["planes"] = [{"role": p["role"], "count": int(p["count"])} for p in planes]
    if not cands:
        A.update(gate="NO_FACADE_PLANE", reasons=["geen verticaal, naar de camera gericht vlak in de ring"])
        return None, "NO_FACADE_PLANE", A["reasons"][0], A
    best = cands[0]
    for p in cands[1:]:
        dot = float(p["n"] @ best["n"])
        parallel = abs(dot) > 0.97
        step = abs((p["d"] if dot > 0 else -p["d"]) - best["d"])
        big = p["count"] >= cfg.ambiguity_ratio * best["count"]
        if parallel and step > 1.5 * thr and big:
            p["role"] = "PARALLEL_STEP"
            A.update(gate="AMBIGUOUS_FACADE_PLANES", reasons=[f"twee grote parallelle vlakken, {step:.2f} m uit elkaar"])
            return None, "AMBIGUOUS_FACADE_PLANES", A["reasons"][0], A
        if not parallel and big:
            A.update(gate="AMBIGUOUS_FACADE_PLANES", reasons=["twee even grote verticale vlakken met verschillende richting (hoek/uitbouw)"])
            return None, "AMBIGUOUS_FACADE_PLANES", A["reasons"][0], A
        if parallel and step > 1.5 * thr:
            p["role"] = "PARALLEL_STEP"
    best["role"] = "FACADE"
    n, d = best["n"], best["d"]
    others = [p for p in planes if p is not best]
    other_idx = np.concatenate([p["idx"] for p in others]) if others else np.zeros(0, int)
    explained_other = sum(p["count"] for p in others if p["role"] in ("REVEAL_OR_LEDGE", "PARALLEL_STEP"))
    own = np.zeros(n_ring, bool)
    own[best["idx"]] = True
    foreign = np.zeros(n_ring, bool)
    foreign[other_idx] = True
    unexplained = ~own & ~foreign
    resid = np.abs(Pr @ n - d)
    A["ring_total_spread_m"] = round(float(1.4826 * np.median(resid)), 4)          # oude maat over ALLE ringpunten: alleen diagnose
    # Lokale populatie: eigen inliers + niet-toegewezen punten + PARALLELLE vlakken dichtbij (een ruw oppervlak kan door RANSAC in schijven
    # worden gesplitst; die schijven zijn geen aparte bouwdelen). Niet-parallelle vlakken (dagkant, vensterbank) en verre lagen blijven buiten.
    foreign_par = np.zeros(n_ring, bool)
    for p in others:
        if abs(float(p["n"] @ n)) > 0.97:
            foreign_par[p["idx"]] = True
    foreign_nonpar = foreign & ~foreign_par
    local = (own | unexplained | foreign_par) & (resid <= cfg.facade_local_band_k * thr) & ~foreign_nonpar
    best["robust_sigma"] = float(1.4826 * np.median(resid[local])) if local.any() else 0.0
    denom = max(n_ring - explained_other, 1)
    best["support"] = float(best["count"] / denom)
    U = int(unexplained.sum())
    A.update(facade_points=int(best["count"]), excluded_other_layer={"count": int(foreign.sum()), "share": round(float(foreign.sum() / max(n_ring, 1)), 4),
                                                                    "planes": [{"role": p["role"], "count": int(p["count"])} for p in others]},
             unexplained={"count": U, "share": round(U / max(n_ring, 1), 4)},
             local={"points": int(local.sum()), "rms_m": round(float(best["rms"]), 4), "robust_sigma_m": round(best["robust_sigma"], 4),
                    "rms_limit_m": round(cfg.facade_rms_k * sig + 0.008, 4), "robust_limit_m": round(2.0 * sig + 0.012, 4)},
             support=round(best["support"], 4))
    best["sides"] = np.asarray(best["sides"])
    shares = best["sides"] / max(best["count"], 1)
    min_pts = max(cfg.side_min_points, int(np.ceil(cfg.side_min_share * best["count"])))
    covered = [int(c) >= min_pts for c in best["sides"]]
    best["sides_covered"] = int(sum(covered))
    maj, mnr = inplane_std(Pr[best["idx"]], n)
    ext_min = cfg.facade_min_extent_ratio * quad_diag_m if quad_diag_m else None
    A.update(sides={"counts": [int(c) for c in best["sides"]], "shares": [round(float(x), 4) for x in shares], "covered": covered, "min_points_per_side": int(min_pts)},
             extent={"major_std_m": round(maj, 4), "minor_std_m": round(mnr, 4), "min_required_m": None if ext_min is None else round(ext_min, 4)})

    def fail(code, why):
        A.update(gate=code, reasons=[why], representative=False)
        return None, code, why, A
    if best["support"] < cfg.facade_support_min:
        return fail("FACADE_NOT_PLANAR", f"wandvlak verklaart slechts {best['support']:.2f} van de ringpunten")
    if best["rms"] > cfg.facade_rms_k * sig + 0.008:
        return fail("FACADE_NOT_PLANAR", f"vlak te ruw: rms {best['rms']:.3f} m")
    if best["robust_sigma"] > 2.0 * sig + 0.012:
        return fail("FACADE_NOT_PLANAR", f"robuuste ruis rond het gekozen vlak {best['robust_sigma']:.3f} m (ruw oppervlak)")
    if U / max(n_ring, 1) > cfg.unexplained_max:
        return fail("FACADE_NOT_PLANAR", f"{U / n_ring:.2f} van de ringpunten hoort bij geen enkel herkend vlak")
    if best["sides_covered"] < 2:
        return fail("FACADE_ONE_SIDED", f"wand slechts aan {best['sides_covered']} zijde(n) gezien (aandeel per zijde {[round(float(x), 2) for x in shares]})")
    if best["sides_covered"] == 2 and not ((covered[0] and covered[2]) or (covered[1] and covered[3])):
        return fail("FACADE_ONE_SIDED", "wand alleen aan twee aangrenzende zijden gezien")
    if ext_min is not None and mnr < ext_min:
        return fail("FACADE_NOT_REPRESENTATIVE", f"vlak te smal: in-vlak spreiding {mnr:.3f} m < {ext_min:.3f} m")
    A.update(representative=True, reasons=["lokale ruis, ondersteuning, zijdeverdeling en omvang voldoen"])
    return best, None, "", A


def _clusters(s, thr):
    """Dieptaclusters (1D histogram, bin thr/2, pieken): lijst van (offset, steun)."""
    if len(s) == 0:
        return []
    lo, hi = float(s.min()), float(s.max())
    bw = max(thr / 2, 1e-3)
    nb = int(np.ceil((hi - lo) / bw)) + 1
    h = np.bincount(np.clip(((s - lo) / bw).astype(int), 0, nb - 1), minlength=nb).astype(float)
    hs = h + np.pad(h[:-1], (1, 0)) + np.pad(h[1:], (0, 1))
    out, used = [], np.zeros(len(s), bool)
    for _ in range(4):
        k = int(np.argmax(hs))
        if hs[k] <= 0:
            break
        center = lo + (k + 0.5) * bw
        m = (np.abs(s - center) <= thr) & ~used
        if m.sum() == 0:
            hs[max(k - 2, 0):k + 3] = 0
            continue
        out.append((float(np.median(s[m])), int(m.sum())))
        used |= m
        hs[max(k - 2, 0):k + 3] = 0
    return out


def _mode_offset(s, thr, min_share=0.35):
    """Offset van het kozijnprofiel op één zijde: van de clusters met voldoende steun het dichtstbijzijnde (profiel ligt vóór het glas). (offset, steun) of (None, 0)."""
    cl = _clusters(s, thr)
    if not cl:
        return None, 0
    top = max(c[1] for c in cl)
    cand = [c for c in cl if c[1] >= min_share * top]
    best = max(cand, key=lambda c: c[0])                      # grootste s = dichtst bij de camera
    return best


def frame_offset(P_band, side_band, facade, z_med, cfg: Config):
    """Terugligging van het kozijnvlak t.o.v. de wand, per zijde uit de binnenband. s > 0: naar de camera toe; s < 0: terugliggend.
    Geeft dict met mode FLUSH | RECESSED | PROTRUDING | UNDETERMINED | INCONSISTENT, offset en per-zijde-info."""
    thr = thr_at(z_med, cfg)
    s_all = P_band @ facade["n"] - facade["d"]
    per = {}
    for k, name in enumerate(SIDES):
        s = s_all[(side_band == k) & (np.abs(s_all) <= cfg.frame_search_m)]
        off, sup = _mode_offset(s, thr, cfg.band_cluster_min_share)
        per[name] = {"offset_m": off if sup >= cfg.frame_side_min_points else None, "support": sup}
    vals = [(n, per[n]["offset_m"]) for n in SIDES if per[n]["offset_m"] is not None]
    out = {"per_side": per, "thr": thr}
    if len(vals) < 2:
        out.update(mode="UNDETERMINED", offset_m=None, group=[])
        return out
    # grootste groep zijden die onderling binnen frame_group_tol_k * thr overeenkomen
    best = []
    for n0, v0 in vals:
        grp = [(n, v) for n, v in vals if abs(v - v0) <= cfg.frame_group_tol_k * thr]
        if len(grp) > len(best):
            best = grp
    rest = [x for x in vals if x not in best]
    if len(best) < 2 or (len(best) == 2 and len(rest) == 2 and abs(np.median([v for _, v in best]) - np.median([v for _, v in rest])) > cfg.frame_group_tol_k * thr):
        out.update(mode="INCONSISTENT" if len(best) >= 2 or len(vals) >= 3 else "UNDETERMINED", offset_m=None, group=[n for n, _ in best])
        return out
    off = float(np.median([v for _, v in best]))
    flush = max(0.015, cfg.flush_tol_k * sigma_at(z_med, cfg))
    mode = "FLUSH" if abs(off) <= flush else ("RECESSED" if off < 0 else "PROTRUDING")
    out.update(mode=mode, offset_m=0.0 if mode == "FLUSH" else off, group=[n for n, _ in best], raw_offset_m=off,
               ledge=[n for n, _ in rest] if rest else [])
    return out


def corner_values(view, uv, r=2):
    """Alle geldige dieptewaarden in een (2r+1)^2-venster rond een hoekpixel. Op een diepte-sprong (terugliggend kozijn) zitten daar zowel wand- als kozijnwaarden in."""
    Hd, Wd = view.depth.shape
    sx, sy = view.intrinsics.width / Wd, view.intrinsics.height / Hd
    j, i = min(max(int(uv[0] / sx), 0), Wd - 1), min(max(int(uv[1] / sy), 0), Hd - 1)
    patch = view.depth[max(i - r, 0):i + r + 1, max(j - r, 0):j + r + 1].ravel()
    return patch[np.isfinite(patch) & (patch > 0)].astype(float)


def plane_geometry(capture, corners_px, n, d_plane):
    o, D = rays_world(capture.pose, capture.intrinsics, corners_px)
    den = D @ n
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (d_plane - o @ n) / den
    t = np.where((np.abs(den) < 1e-9) | (t <= 0), np.nan, t)
    return o + D * t[:, None], t, np.abs(den)


# ------------------------------------------------------------------ analyse van een puntenset

def analyze_points(capture, X, kind, side, cfg: Config, seed, z_hint=None, quad_diag_px=None):
    """Meervlaks-analyse op een set punten (al in de gebieden ingedeeld). Geeft dict met flags, facade, frame, planes, stats."""
    res = {"flags": [], "planes": [], "facade": None, "frame": None, "stats": {}}
    ring = kind == 1
    Pr, sr = X[ring], side[ring]
    cam = capture.pose[:3, 3]
    z_med = z_hint if z_hint is not None else (float(np.median(np.linalg.norm(Pr - cam, axis=1))) if len(Pr) else 3.0)
    thr = thr_at(z_med, cfg)
    res["stats"].update(ring_points=int(len(Pr)), range_median_m=z_med, sigma_m=sigma_at(z_med, cfg), threshold_m=thr)
    if len(Pr) < cfg.min_plane_points:
        res["flags"].append(q.flag("DEPTH_COVERAGE_LOW", f"{len(Pr)} ringpunten"))
        return res
    planes, remaining = sequential_planes(Pr, sr, thr, cfg, seed)
    classify_planes(planes, cam, cfg)
    quad_diag_m = None if not quad_diag_px else quad_diag_px * z_med / capture.intrinsics.fx
    facade, code, detail, assess = pick_facade(planes, Pr, sr, z_med, cfg, quad_diag_m)
    res["assessment"] = assess
    res["planes"] = [{"role": p["role"], "count": p["count"], "rms_m": p["rms"], "facing": p["facing"], "vertical": p["vertical"],
                      "normal": [float(x) for x in p["n"]], "offset": float(p["d"]), "sides": [int(x) for x in p["sides"]]} for p in planes]
    if facade is None:
        res["flags"].append(q.flag(code, detail))
        return res
    res["facade"] = facade
    res["stats"].update(facade_support=facade["support"], facade_rms_m=facade["rms"], facade_sides=facade.get("sides_covered"),
                        facade_inlier_ratio=float(facade["count"] / len(Pr)))
    if facade["vertical"] > 0.2:
        res["flags"].append(q.flag("FACADE_NOT_VERTICAL", f"|n.up|={facade['vertical']:.2f}"))
    if facade.get("sides_covered", 4) < 4:
        res["flags"].append(q.flag("LIMITED_SIDE_COVERAGE", f"{facade.get('sides_covered')} van 4 zijden gedekt"))
    band = kind == 2
    res["frame"] = frame_offset(X[band], side[band], facade, z_med, cfg)
    return res


def edge_alignment(view, corners_px, cfg: Config, max_shift=8):
    """Indicatieve controle op uitlijning dieptekaart <-> beeld: zoek de verschuiving (in dieptepixels) waarbij de diepte-sprong over de kaderrand maximaal is.
    Alleen zinvol als er een sprong is (terugliggend kozijn/dagkant). Geeft (best_dx, best_dy, score_best, score_0) of None."""
    Hd, Wd = view.depth.shape
    sx, sy = view.intrinsics.width / Wd, view.intrinsics.height / Hd
    quad = np.asarray(corners_px, float) / np.array([sx, sy])            # in dieptepixels
    sgn = 1.0 if signed_area(quad) >= 0 else -1.0
    pts_in, pts_out = [], []
    for i in range(4):
        a, b = quad[i], quad[(i + 1) % 4]
        e = b - a
        L = np.linalg.norm(e)
        nin = np.array([-e[1], e[0]]) / max(L, 1e-9) * sgn          # inwaartse normaal (zelfde conventie als in_convex_polygon)
        ts = np.linspace(0.15, 0.85, max(int(L / 2), 4))
        base = a[None, :] + ts[:, None] * e[None, :]
        pts_in.append(base + 2.5 * nin)
        pts_out.append(base - 2.5 * nin)
    pin, pout = np.vstack(pts_in), np.vstack(pts_out)
    Z = view.depth

    def sample(p, dx, dy):
        j = np.clip(np.round(p[:, 0] - 0.5 + dx).astype(int), 0, Wd - 1)
        i = np.clip(np.round(p[:, 1] - 0.5 + dy).astype(int), 0, Hd - 1)
        return Z[i, j]

    def score(dx, dy):
        zi, zo = sample(pin, dx, dy), sample(pout, dx, dy)
        ok = np.isfinite(zi) & np.isfinite(zo)
        return float(np.mean(np.abs(zi[ok] - zo[ok]))) if ok.sum() > 20 else None
    s0 = score(0, 0)
    best = (0, 0, s0)
    for dx in range(-max_shift, max_shift + 1):
        for dy in range(-max_shift, max_shift + 1):
            s = score(dx, dy)
            if s is not None and (best[2] is None or s > best[2]):
                best = (dx, dy, s)
    return best[0], best[1], best[2], s0


def quad_extent(view, corners_px, n, d_plane, z_med, cfg: Config):
    """Omvat het kader de buitenrand van het kozijn? Loodrecht op elke kaderrand wordt de diepte-afwijking t.o.v. het gekozen vlak naar binnen en naar buiten gevolgd.
    d_in: afstand (m) tot de eerste diepte-sprong BINNEN het kader; d_out: idem BUITEN het kader. Geeft per zijde dicts en de afgeleide vlaggen."""
    Hd, Wd = view.depth.shape
    sx, sy = view.intrinsics.width / Wd, view.intrinsics.height / Hd
    quad = np.asarray(corners_px, float)
    sgn = 1.0 if signed_area(quad) >= 0 else -1.0
    c = quad.mean(axis=0)
    thr = thr_at(z_med, cfg)
    mpp = z_med * sx / view.intrinsics.fx
    out = []
    for i in range(4):
        a, b = quad[i], quad[(i + 1) % 4]
        e = (b - a)
        L = np.linalg.norm(e)
        nin = np.array([-e[1], e[0]]) / max(L, 1e-9) * sgn                   # inwaarts, in beeldpixels
        hdep = abs(float((c - a) @ nin)) / sx
        K = int(min(max(hdep * 0.8, 8), 60))
        base = a[None, :] + np.linspace(0.2, 0.8, 7)[:, None] * e[None, :]
        prof = []
        for k in range(-K, K + 1):                                            # k > 0: naar binnen
            p = base + (k * sx) * nin[None, :]
            jj = np.clip((p[:, 0] / sx).astype(int), 0, Wd - 1)
            ii = np.clip((p[:, 1] / sy).astype(int), 0, Hd - 1)
            z = view.depth[ii, jj].astype(float)
            ok = np.isfinite(z) & (z > 0) & (p[:, 0] >= 0) & (p[:, 0] < view.intrinsics.width) & (p[:, 1] >= 0) & (p[:, 1] < view.intrinsics.height)
            if ok.sum() < 3:
                prof.append(None)
                continue
            Xp = unproject_depth(view.pose, view.intrinsics, p[ok], z[ok])
            prof.append(float(np.median(Xp @ n - d_plane)))

        def first(rng_k):
            run = 0
            for k in rng_k:
                v = prof[k + K]
                if v is not None and abs(v) > 1.2 * thr:
                    run += 1
                    if run >= 2:
                        return (k - 1) if k > 0 else (k + 1), v
                else:
                    run = 0
            return None, None
        kin, vin = first(range(1, K + 1))
        kout, vout = first(range(-1, -K - 1, -1))
        out.append({"side": SIDES[i], "d_in_m": None if kin is None else round(abs(kin) * mpp, 3), "s_in_m": None if vin is None else round(vin, 3),
                    "d_out_m": None if kout is None else round(abs(kout) * mpp, 3), "s_out_m": None if vout is None else round(vout, 3)})
    larger = sum(1 for s in out if s["d_in_m"] is not None and s["d_in_m"] > 0.12 and s["s_in_m"] < 0)
    inside = sum(1 for s in out if s["d_out_m"] is not None and s["d_out_m"] > 0.12 and s["s_out_m"] > 0)
    return out, larger, inside
