"""Voorkomen van dubbeltelling: koppel waarnemingen van hetzelfde fysieke kozijn over meerdere beelden.

Koppeling gebeurt alleen op harde geometrische gronden (zelfde vlak, nabije wereldpositie, vergelijkbare maat, nooit twee waarnemingen uit
hetzelfde beeld in een cluster) of op expliciete gebruikerskoppeling. Waarnemingen zonder wereldpositie blijven apart en krijgen
ASSOCIATION_UNVERIFIED: dubbeltelling is dan niet uitgesloten en dat wordt gemeld, niet verzwegen.
"""
import numpy as np

from .config import Config
from .geometry import angle_between_deg


def _compatible(a, b, cfg: Config):
    na, nb = a["plane_n"], b["plane_n"]
    if na is None or nb is None:
        return False
    if angle_between_deg(na, nb) > cfg.assoc_normal_angle_deg:
        return False
    s = 1.0 if na @ nb >= 0 else -1.0
    if abs(a["plane_d"] - s * b["plane_d"]) > cfg.assoc_plane_offset_m:
        return False
    ra = max(a["w"], b["w"]) / max(min(a["w"], b["w"]), 1e-9)
    rb = max(a["h"], b["h"]) / max(min(a["h"], b["h"]), 1e-9)
    return ra < 1.5 and rb < 1.5


def associate(items, cfg: Config, explicit_links=()):
    """items: lijst dicts {obs_id, frame_id, center_w|None, plane_n|None, plane_d|None, w|None, h|None}.
    Geeft (clusters: lijst van lijsten indices, notes: {index: [codes]})."""
    n = len(items)
    parent = list(range(n))
    members = {i: {i} for i in range(n)}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j, force=False):
        ri, rj = find(i), find(j)
        if ri == rj:
            return True
        fi = {items[k]["frame_id"] for k in members[ri]}
        fj = {items[k]["frame_id"] for k in members[rj]}
        if fi & fj and not force:
            return False
        parent[rj] = ri
        members[ri] |= members.pop(rj)
        return True

    idx = {it["obs_id"]: i for i, it in enumerate(items)}
    for grp in explicit_links:
        ids = [idx[o] for o in grp if o in idx]
        for a, b in zip(ids, ids[1:]):
            union(a, b, force=True)
    notes = {i: [] for i in range(n)}
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = items[i], items[j]
            if a["frame_id"] == b["frame_id"] or a["center_w"] is None or b["center_w"] is None or not _compatible(a, b, cfg):
                continue
            dist = float(np.linalg.norm(np.asarray(a["center_w"]) - np.asarray(b["center_w"])))
            gate = cfg.assoc_center_gate_factor * min(a["w"], a["h"], b["w"], b["h"])
            if dist <= gate:
                pairs.append((dist, i, j))
    pairs.sort()
    # onduidelijk: een waarneming heeft in dezelfde andere frame twee kandidaten van vergelijkbare afstand
    best = {}
    for dist, i, j in pairs:
        for x, y in ((i, j), (j, i)):
            best.setdefault((x, items[y]["frame_id"]), []).append(dist)
    amb = set()
    for (x, fr), ds in best.items():
        if len(ds) >= 2 and sorted(ds)[1] < 1.5 * sorted(ds)[0]:
            amb.add(x)
    for dist, i, j in pairs:
        if i in amb or j in amb:
            continue
        union(i, j)
    for i in amb:
        notes[i].append("AMBIGUOUS_ASSOCIATION")
    multi_frame = len({it["frame_id"] for it in items}) > 1
    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    out = [sorted(v) for _, v in sorted(clusters.items(), key=lambda kv: min(kv[1]))]
    for c in out:
        if len(c) == 1 and multi_frame and items[c[0]]["center_w"] is None and not any(items[c[0]]["obs_id"] in g for g in explicit_links):
            notes[c[0]].append("ASSOCIATION_UNVERIFIED")
    return out, notes
