"""Photo-to-Quantity Pilot v1: experimentele, lokale foto-naar-hoeveelheid-laag (annotatiegebaseerd).

Generieke code zonder echte foto-inhoud: alle invoer komt als argumenten binnen. Geen netwerk, geen AI-SDK, geen externe
Vision-aanroep, geen schrijfacties naar canonieke stores, geen FI-instances, geen besluiten.

Drie strikt gescheiden uitkomsten (nooit samengevoegd tot een gebouwtotaal):
  A. PHOTO_OBSERVED      wat per foto is geannoteerd/waargenomen (geen telling van het gebouw)
  B. PROVISIONAL_UNIQUE  voorlopig unieke objecten na vergelijking van foto's (alleen optellen binnen een afgebakend segment)
  C. PHOTO_ESTIMATED_AREA experimentele bruto-m2-schatting. PHOTO_ASSUMPTION_ESTIMATE is een aanname, nooit MEASURED,
     CONFIRMED of APPROVED; de bestaande v2-schema's en -statussen blijven ongewijzigd.

Bruto m2 = buitenbreedte x buitenhoogte x aantal, via de bestaande Decimal-kern (bruto_quantity_core.gross_area_exact).
"""
import re
import statistics
from collections import OrderedDict, defaultdict
from decimal import Decimal

import bruto_quantity_core as core

PILOT_VERSION = "photo_quantity_pilot_v1"
ESTIMATE_STATUS = "PHOTO_ASSUMPTION_ESTIMATE"
FRAME_TYPES_FOR_AREA = ("WINDOW_OPENING",)
INVARIANTS = OrderedDict([
    ("is_instance", False), ("fi_ids_created", False), ("decisions_registered", False), ("approvals_simulated", False),
    ("canonical_stores_modified", False), ("v2_schemas_modified", False), ("external_vision_calls", 0),
    ("measured_or_confirmed_from_photo", False), ("building_total_claimed", False)])
STRENGTH_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


# --------------------------------------------------------------------------
# Verwijzingen en relaties
# --------------------------------------------------------------------------

_OBS_RE = re.compile(r"OBS-MAP(\d{3})-(\d{3})((?:\s*[+/]\s*\d{3})*)")
_FC_RE = re.compile(r"FC-M2-\d{3}(?:-[A-Z]+)?")
_REF_RE = re.compile(r"REF-MAP\d{3}-\d{3}")


def parse_refs(text):
    """Haal observaties (photo, obs_id) en referenties uit een relatietekst. Platen en vrije tekst leveren niets op."""
    obs, refs = [], []
    for m in _OBS_RE.finditer(text):
        photo = f"MAP-{m.group(1)}"
        obs.append((photo, f"OBS-MAP{m.group(1)}-{m.group(2)}"))
        for extra in re.findall(r"\d{3}", m.group(3) or ""):
            obs.append((photo, f"OBS-MAP{m.group(1)}-{extra}"))
    for m in _FC_RE.finditer(text):
        obs.append(("MAP-002", m.group(0)))
    refs = [m.group(0) for m in _REF_RE.finditer(text)]
    return obs, refs


# --------------------------------------------------------------------------
# Observaties
# --------------------------------------------------------------------------

def normalise_observation(*, obs_id, photo_id, observation_type, visibility, bbox_px, note="", uncertainty=None,
                          evidence_source="EXISTING_ANNOTATION"):
    """Uniforme foto-observatie. bbox_px = [x1, y1, x2, y2] in originele pixels van de foto."""
    x1, y1, x2, y2 = [int(round(v)) for v in bbox_px]
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"{obs_id}: lege bbox {bbox_px}")
    return OrderedDict([
        ("obs_id", obs_id), ("photo_id", photo_id), ("observation_type", observation_type), ("visibility", visibility),
        ("bbox_px", [x1, y1, x2, y2]), ("w_px", x2 - x1), ("h_px", y2 - y1), ("note", note), ("uncertainty", uncertainty),
        ("evidence_source", evidence_source)])


def category_of(observation_type):
    """Telcategorie: kozijnopening (gevel), deur, dakraam of dakkapel. Alleen WINDOW_OPENING telt mee voor gevelkozijnen."""
    t = observation_type
    if t in ("WINDOW_OPENING",):
        return "FACADE_FRAME"
    if t in ("EXTERIOR_DOOR", "DOOR"):
        return "DOOR"
    if t in ("ROOF_WINDOW",):
        return "ROOF_WINDOW"
    if t in ("DORMER_OPENING", "DORMER_WINDOW"):
        return "DORMER"
    return "UNKNOWN"


def classify_row_layers(observations, gap_px=80):
    """Verdeel gevelkozijnen per foto in rijen (boven naar onder) op de verticale beeldpositie. Geeft {obs_id: rij}.
    Rijnamen: UPPER_ROW, MIDDLE_ROW, GROUND_ROW bij drie rijen; anders ROW_1..n. Algoritmisch voorstel, geen bouwlaagbewijs."""
    out = {}
    by_photo = defaultdict(list)
    for o in observations:
        if category_of(o["observation_type"]) in ("FACADE_FRAME", "DOOR"):
            by_photo[o["photo_id"]].append(o)
    for photo, items in by_photo.items():
        items = sorted(items, key=lambda o: (o["bbox_px"][1] + o["bbox_px"][3]) / 2)
        clusters, cur = [], [items[0]]
        for o in items[1:]:
            yc = (o["bbox_px"][1] + o["bbox_px"][3]) / 2
            prev = (cur[-1]["bbox_px"][1] + cur[-1]["bbox_px"][3]) / 2
            if yc - prev > gap_px:
                clusters.append(cur)
                cur = [o]
            else:
                cur.append(o)
        clusters.append(cur)
        names = ["UPPER_ROW", "MIDDLE_ROW", "GROUND_ROW"] if len(clusters) == 3 else [f"ROW_{i + 1}" for i in range(len(clusters))]
        for name, cl in zip(names, clusters):
            for o in cl:
                out[(photo, o["obs_id"])] = name
    return out


def classify_frame_type(obs):
    """Kozijntype uit annotatietekst en geometrie. Geeft (type, bewijs). Een kozijn met meerdere ramen blijft een kozijn."""
    cat = category_of(obs["observation_type"])
    if cat == "DOOR":
        return "EXTERIOR_DOOR", "ANNOTATION_TYPE"
    if cat == "ROOF_WINDOW":
        return "ROOF_WINDOW", "ANNOTATION_TYPE"
    if cat == "DORMER":
        return "DORMER_WINDOW", "ANNOTATION_TYPE"
    note = (obs.get("note") or "").lower()
    if "drie-ruits" in note or "driedelig" in note:
        return "MULTI_PANE_WINDOW", "NOTE_KEYWORD"
    if "tweedelig" in note or note.startswith("hoofdkozijn"):
        return "MULTI_PANE_WINDOW", "NOTE_KEYWORD"
    if "onderpaneel" in note:
        return "WINDOW_WITH_LOWER_PANEL", "NOTE_KEYWORD"
    if note.startswith("smal"):
        return "NARROW_WINDOW", "NOTE_KEYWORD"
    aspect = obs["w_px"] / obs["h_px"]
    if aspect < 0.75:
        return "NARROW_WINDOW", "GEOMETRY_ASPECT"
    if aspect > 1.45:
        return "MULTI_PANE_WINDOW", "GEOMETRY_ASPECT"
    return "WINDOW_STANDARD", "GEOMETRY_ASPECT"


def has_open_leaf(obs):
    note = (obs.get("note") or "").lower()
    return "open vleugel" in note or "geopende" in note or "open vleugels" in note


# --------------------------------------------------------------------------
# Identiteit: dezelfde fysieke kozijnen op meerdere foto's
# --------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, keys, photo_of):
        self.parent = {k: k for k in keys}
        self.photos = {k: {photo_of[k]} for k in keys}

    def find(self, k):
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return "ALREADY"
        if self.photos[ra] & self.photos[rb]:
            return "SAME_PHOTO_CONFLICT"
        self.parent[rb] = ra
        self.photos[ra] |= self.photos[rb]
        return "MERGED"


def build_identity(observations, relations, references=()):
    """Voorlopige unieke objecten uit foto-observaties en relaties. Strikte regels:
    - alleen 1-op-1-relaties POSSIBLY_SAME_PHYSICAL_FRAME met zekerheid HIGH/MEDIUM voegen samen;
    - LOW wordt een mogelijke dubbeltelling (niet samengevoegd, wel zichtbaar);
    - UNDETERMINABLE en veel-op-een-relaties blijven een niet-opgelost identiteitsconflict (niet samengevoegd);
    - een samenvoeging die twee observaties van dezelfde foto zou verenigen wordt geweigerd en als conflict vastgelegd;
    - DIFFERENT_FRAMES wordt als blokkade bewaard en gecontroleerd;
    - gelijkenis alleen is nooit een reden om samen te voegen."""
    by_key = {(o["photo_id"], o["obs_id"]): o for o in observations}
    photo_of = {k: k[0] for k in by_key}
    uf = _UnionFind(list(by_key), photo_of)
    ref_index = {r["ref_id"]: r for r in references}
    links, possible_dup, unresolved, blocks, refused, ref_links = [], [], [], [], [], defaultdict(list)
    conflict_of = defaultdict(list)

    parsed = []
    for rel in relations:
        l_obs, l_refs = parse_refs(rel["left"])
        r_obs, r_refs = parse_refs(rel["right"])
        l_obs = [k for k in l_obs if k in by_key]
        r_obs = [k for k in r_obs if k in by_key]
        parsed.append((rel, l_obs, l_refs, r_obs, r_refs))

    # eerst sterke relaties, zodat een zwakkere nooit een sterkere verdringt
    def _rank(item):
        return -STRENGTH_RANK.get(item[0].get("strength"), 0)

    for rel, l_obs, l_refs, r_obs, r_refs in sorted(parsed, key=_rank):
        cls, strength = rel["class"], rel.get("strength")
        if cls == "DIFFERENT_FRAMES":
            blocks.append({"rel_id": rel["rel_id"], "left": l_obs, "right": r_obs, "basis": rel["basis"]})
            continue
        if cls == "UNDETERMINABLE":
            unresolved.append({"rel_id": rel["rel_id"], "left": l_obs, "right": r_obs, "reason": "UNDETERMINABLE",
                               "basis": rel["basis"]})
            for k in l_obs + r_obs:
                conflict_of[k].append(rel["rel_id"])
            continue
        if cls != "POSSIBLY_SAME_PHYSICAL_FRAME":
            continue  # SAME_FACADE_SECTION e.d.: bewijs voor dezelfde gevelsectie, nooit een objectkoppeling
        # referentiefoto's (geen observaties): bewijs voor een bestaand object
        if (l_obs and r_refs and not r_obs) or (r_obs and l_refs and not l_obs):
            anchor, refs = (l_obs, r_refs) if l_obs else (r_obs, l_refs)
            for k in anchor:
                for rid in refs:
                    ref_links[k].append({"rel_id": rel["rel_id"], "ref_id": rid, "strength": strength,
                                         "photo_id": ref_index.get(rid, {}).get("photo_id")})
            continue
        for rid in l_refs + r_refs:
            for k in l_obs + r_obs:
                ref_links[k].append({"rel_id": rel["rel_id"], "ref_id": rid, "strength": strength,
                                     "photo_id": ref_index.get(rid, {}).get("photo_id")})
        if not l_obs or not r_obs:
            continue
        if len(l_obs) != 1 or len(r_obs) != 1:
            unresolved.append({"rel_id": rel["rel_id"], "left": l_obs, "right": r_obs, "reason": "MANY_TO_ONE",
                               "basis": rel["basis"]})
            for k in l_obs + r_obs:
                conflict_of[k].append(rel["rel_id"])
            continue
        a, b = l_obs[0], r_obs[0]
        if strength == "LOW":
            possible_dup.append({"rel_id": rel["rel_id"], "a": a, "b": b, "basis": rel["basis"]})
            continue
        result = uf.union(a, b)
        if result == "SAME_PHOTO_CONFLICT":
            refused.append({"rel_id": rel["rel_id"], "a": a, "b": b, "reason": "SAME_PHOTO_CONFLICT"})
            for k in (a, b):
                conflict_of[k].append(rel["rel_id"])
        else:
            links.append({"rel_id": rel["rel_id"], "a": a, "b": b, "strength": strength, "basis": rel["basis"]})

    clusters = defaultdict(list)
    for k in by_key:
        clusters[uf.find(k)].append(k)
    objects = []
    for members in clusters.values():
        members.sort()
        objects.append({"members": members})
    # contradictie-controle: een DIFFERENT_FRAMES-blokkade mag nooit binnen een cluster zitten
    root_of = {k: uf.find(k) for k in by_key}
    violated = [b["rel_id"] for b in blocks if any(root_of[x] == root_of[y] for x in b["left"] for y in b["right"])]
    link_strength = defaultdict(list)
    for ln in links:
        link_strength[root_of[ln["a"]]].append(ln["strength"])
    pd_by_root = defaultdict(list)
    for d in possible_dup:
        pd_by_root[root_of[d["a"]]].append(d)
        pd_by_root[root_of[d["b"]]].append(d)
    for obj in objects:
        root = root_of[obj["members"][0]]
        photos = sorted({k[0] for k in obj["members"]})
        strengths = link_strength.get(root, [])
        flags = []
        if any(conflict_of.get(k) for k in obj["members"]):
            flags.append("UNRESOLVED_IDENTITY_CONFLICT")
        if pd_by_root.get(root):
            flags.append("POSSIBLE_DOUBLE_COUNT")
        if len(photos) == 1:
            status = "SINGLE_PHOTO"
        elif strengths and all(s == "HIGH" for s in strengths):
            status = "CROSS_PHOTO_PROBABLE_HIGH"
        else:
            status = "CROSS_PHOTO_PROBABLE_MEDIUM"
        obj.update({"photos": photos, "identity_status": status, "identity_flags": flags,
                    "links": [ln for ln in links if root_of[ln["a"]] == root],
                    "possible_duplicates": pd_by_root.get(root, []),
                    "conflicts": sorted({r for k in obj["members"] for r in conflict_of.get(k, [])}),
                    "reference_evidence": [e for k in obj["members"] for e in ref_links.get(k, [])]})
    return {"objects": objects, "links": links, "possible_duplicates": possible_dup, "unresolved": unresolved,
            "blocks": blocks, "blocks_violated": violated, "refused_links": refused}


def identity_bounds(identity, subset=None):
    """Ondergrens/bovengrens voor het aantal unieke objecten.
    lower: alle kandidaat-koppelingen (LOW, UNDETERMINABLE, veel-op-een) alsnog samenvoegen waar dat zonder twee observaties
           van dezelfde foto kan; upper: geen enkele fotoverbinding (aantal observaties).
    subset: optionele verzameling observatiesleutels (foto, id) waarop de grenzen worden bepaald."""
    objs = identity["objects"]
    idx = {}
    for i, o in enumerate(objs):
        for k in o["members"]:
            idx[k] = i
    keep = [i for i, o in enumerate(objs) if subset is None or any(k in subset for k in o["members"])]
    photos = {i: {k[0] for k in objs[i]["members"] if subset is None or k in subset} for i in keep}
    parent = {i: i for i in keep}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs = [(d["a"], d["b"]) for d in identity["possible_duplicates"]]
    for u in identity["unresolved"]:
        pairs += [(a, b) for a in u["left"] for b in u["right"]]
    for a, b in pairs:
        if a not in idx or b not in idx or idx[a] not in parent or idx[b] not in parent:
            continue
        ra, rb = find(idx[a]), find(idx[b])
        if ra != rb and not (photos[ra] & photos[rb]):
            parent[rb] = ra
            photos[ra] |= photos[rb]
    lower = len({find(i) for i in keep})
    upper = sum(len([k for k in objs[i]["members"] if subset is None or k in subset]) for i in keep)
    return {"lower": lower, "provisional": len(keep), "upper_no_cross_photo_merge": upper}


# --------------------------------------------------------------------------
# Geometrische controle (algoritmisch voorstel, geen grondwaarheid)
# --------------------------------------------------------------------------

def _xc(o):
    return (o["bbox_px"][0] + o["bbox_px"][2]) / 2


def estimate_layer_shifts(identity, obs_by_key, layers, ref_photo, other_photo):
    """Horizontale verschuiving ref - other per diepte-laag uit samengevoegde paren. Parallax: dichterbij gelegen lagen
    verschuiven meer. Geeft {laag: {n, median_shift, residuals}} en de residuen per link."""
    pairs = defaultdict(list)
    for obj in identity["objects"]:
        for ln in obj["links"]:
            a, b = obs_by_key[ln["a"]], obs_by_key[ln["b"]]
            if {a["photo_id"], b["photo_id"]} != {ref_photo, other_photo}:
                continue
            ra, rb = (a, b) if a["photo_id"] == ref_photo else (b, a)
            layer = layers.get((ra["photo_id"], ra["obs_id"])) or category_of(ra["observation_type"])
            pairs[layer].append((ln["rel_id"], _xc(ra) - _xc(rb), ra["obs_id"], rb["obs_id"]))
    out = {}
    for layer, items in pairs.items():
        shifts = [s for _, s, _, _ in items]
        med = statistics.median(shifts)
        out[layer] = {"n": len(items), "median_shift_px": med,
                      "pairs": [{"rel_id": r, "shift_px": round(s, 1), "residual_px": round(s - med, 1), "a": a, "b": b}
                                for r, s, a, b in items]}
    return out


def parallax_consistency(shifts, depth_order):
    """Controleer of |verschuiving| monotoon toeneemt met de diepte-volgorde (ver -> dichtbij). Geeft (ok, detail)."""
    seq = [(layer, abs(shifts[layer]["median_shift_px"])) for layer in depth_order if layer in shifts]
    ok = all(seq[i][1] <= seq[i + 1][1] for i in range(len(seq) - 1))
    return ok, seq


# --------------------------------------------------------------------------
# Relatieve geometrie (Methode B) en schaal (Methode A/C)
# --------------------------------------------------------------------------

def row_pitches(observations, layers):
    """Mediaan van de verticale middens per foto en rij (alleen volledig zichtbare gevelkozijnen) -> {foto: {rij: yc}}."""
    acc = defaultdict(lambda: defaultdict(list))
    for o in observations:
        if category_of(o["observation_type"]) != "FACADE_FRAME" or o["visibility"] != "FULL":
            continue
        layer = layers.get((o["photo_id"], o["obs_id"]))
        if layer:
            acc[o["photo_id"]][layer].append((o["bbox_px"][1] + o["bbox_px"][3]) / 2)
    return {p: {r: statistics.median(v) for r, v in rows.items()} for p, rows in acc.items()}


def storey_pitch_px(rows):
    """Verticale afstand tussen opeenvolgende rij-middens: {rij: pitch tot de rij erboven/onder} voor drie rijen."""
    names = [n for n in ("UPPER_ROW", "MIDDLE_ROW", "GROUND_ROW") if n in rows]
    if len(names) < 2:
        return {}
    up_mid = rows["MIDDLE_ROW"] - rows["UPPER_ROW"] if {"UPPER_ROW", "MIDDLE_ROW"} <= set(rows) else None
    mid_gr = rows["GROUND_ROW"] - rows["MIDDLE_ROW"] if {"MIDDLE_ROW", "GROUND_ROW"} <= set(rows) else None
    out = {}
    if up_mid:
        out["UPPER_ROW"] = up_mid
    if up_mid and mid_gr:
        out["MIDDLE_ROW"] = (up_mid + mid_gr) / 2
    elif up_mid or mid_gr:
        out["MIDDLE_ROW"] = up_mid or mid_gr
    if mid_gr:
        out["GROUND_ROW"] = mid_gr
    return out


def relative_geometry(obs, pitch_px):
    """Methode B: dimensieloze verhoudingen. Geen meters. Breedte/hoogte in storey-pitch-eenheden (alleen bij pitch)."""
    rec = OrderedDict([("aspect_w_over_h", round(obs["w_px"] / obs["h_px"], 3))])
    if pitch_px:
        rec["width_pitch_units"] = round(obs["w_px"] / pitch_px, 3)
        rec["height_pitch_units"] = round(obs["h_px"] / pitch_px, 3)
    return rec


def pand_pitch_scale(plate_px_by_photo, pand_plate_groups, pand_pitch_m):
    """Schaalanker A2 (zwak): BAG-footprint-steek per pand gedeeld door de plaatafstand in pixels (grondvlak).
    plate_px_by_photo = {foto: {plaatnummer(str): x_midden_px}}. Geeft {foto: m/px} voor foto's met >= 2 volledige pandparen.
    Aanname: de platen van een pand liggen gemiddeld in het midden van dat pand; dit is GEEN meting (zie rapport)."""
    out = {}
    for photo, plates in plate_px_by_photo.items():
        centres = []
        for group in pand_plate_groups:
            xs = [plates[p] for p in group if p in plates]
            centres.append(statistics.mean(xs) if len(xs) == len(group) else None)
        spacings = []
        for i in range(len(centres) - 1):
            if centres[i] is not None and centres[i + 1] is not None:
                spacings.append(abs(centres[i + 1] - centres[i]))
        if spacings:
            out[photo] = Decimal(str(pand_pitch_m)) / Decimal(str(statistics.median(spacings)))
    return out


def scale_scenarios(pitches_by_photo, storey_height_m, a2_by_photo=None, perspective=Decimal("0.10")):
    """Methode C: scenario-schaal (m/px) per foto en rij uit EXPLICIETE aannames.
    A1 (aanname): verdiepingshoogte H in [lo, centraal, hi] / verticale rijsteek in pixels.
    A2 (aanname, zwak): BAG-pandsteek / plaatsteek in het grondvlak (alleen waar beschikbaar).
    De verhouding r = A2/A1 in het grondvlak is de zichtbare onenigheid tussen de ankers; ze verbreedt de band en vormt
    een gedeeltelijke verzoening (centraal = A1 * sqrt(r)). Perspectiefmarge geldt bovenop beide grenzen."""
    lo, c, hi = (Decimal(str(storey_height_m[k])) for k in ("lo", "central", "hi"))
    ratios = []
    out = {}
    for photo, pitches in pitches_by_photo.items():
        a2 = (a2_by_photo or {}).get(photo)
        if a2 is not None and "GROUND_ROW" in pitches:
            a1_ground = c / Decimal(str(pitches["GROUND_ROW"]))
            ratios.append(a2 / a1_ground)
    r = Decimal(str(statistics.median([float(x) for x in ratios]))) if ratios else Decimal(1)
    sqrt_r = r.sqrt()
    for photo, pitches in pitches_by_photo.items():
        rows = {}
        for row, pitch in pitches.items():
            p = Decimal(str(pitch))
            low = lo / p * min(Decimal(1), r) * (1 - perspective)
            high = hi / p * max(Decimal(1), r) * (1 + perspective)
            central = c / p * sqrt_r
            rows[row] = {"low": low, "central": central, "high": high, "pitch_px": float(pitch)}
        out[photo] = rows
    return {"scales": out, "a2_over_a1_ratio": r, "ratios_per_photo": [float(x) for x in ratios]}


def _q(d, places="0.0001"):
    return Decimal(d).quantize(Decimal(places))


def estimate_observation(obs, layer, scale_rows):
    """PHOTO_ASSUMPTION_ESTIMATE voor een volledig zichtbaar gevelkozijn. Geeft None als er geen verdedigbare schatting is."""
    if category_of(obs["observation_type"]) != "FACADE_FRAME" or obs["visibility"] != "FULL":
        return None
    sc = (scale_rows or {}).get(layer)
    if not sc:
        return None
    rec = OrderedDict()
    for key in ("low", "central", "high"):
        w = _q(sc[key] * obs["w_px"])
        h = _q(sc[key] * obs["h_px"])
        try:
            area = core.gross_area_exact(str(w), str(h), 1)
        except core.BrutoError:
            return None  # buiten het realistische bereik van de kern: geen schatting, geen gok
        rec[key] = {"width_m": str(w), "height_m": str(h), "gross_m2": core.fmt_exact(area)}
    return rec


def combine_object_estimates(per_obs):
    """Eén fysiek object telt eenmaal: centraal = mediaan van de centrale waarden over de FULL-observaties,
    band = ruimste onder- en bovengrens. Geeft ook de spreiding tussen foto's (consistentiecontrole, geen nauwkeurigheid)."""
    if not per_obs:
        return None
    ests = [e for _, e in per_obs]
    def med(key, field):
        return Decimal(str(statistics.median([float(Decimal(e[key][field])) for e in ests])))
    central_w, central_h = _q(med("central", "width_m")), _q(med("central", "height_m"))
    area_c = core.gross_area_exact(str(central_w), str(central_h), 1)
    lo = min(Decimal(e["low"]["gross_m2"]) for e in ests)
    hi = max(Decimal(e["high"]["gross_m2"]) for e in ests)
    spread = None
    if len(ests) >= 2:
        ws = [float(Decimal(e["central"]["width_m"])) for e in ests]
        hs = [float(Decimal(e["central"]["height_m"])) for e in ests]
        spread = {"width_rel_spread": round((max(ws) - min(ws)) / statistics.mean(ws), 3),
                  "height_rel_spread": round((max(hs) - min(hs)) / statistics.mean(hs), 3), "n_observations": len(ests)}
    return OrderedDict([
        ("status", ESTIMATE_STATUS), ("width_m_central", str(central_w)), ("height_m_central", str(central_h)),
        ("gross_m2_central", core.fmt_exact(area_c)), ("gross_m2_low", core.fmt_exact(lo)), ("gross_m2_high", core.fmt_exact(hi)),
        ("sources", [k for k, _ in per_obs]), ("cross_photo_consistency", spread)])


def sum_estimates(objects):
    """Optelling over UNIEKE objecten met schatting (Decimal, exact). Objecten zonder schatting tellen niet mee en worden
    afzonderlijk geteld; het resultaat is daarmee een ondergrens-achtige deelsom, nooit een gebouwtotaal."""
    c = lo = hi = Decimal(0)
    n_est = n_unknown = 0
    for o in objects:
        e = o.get("estimate")
        if e:
            c += Decimal(e["gross_m2_central"])
            lo += Decimal(e["gross_m2_low"])
            hi += Decimal(e["gross_m2_high"])
            n_est += 1
        else:
            n_unknown += 1
    return OrderedDict([("n_with_estimate", n_est), ("n_without_estimate", n_unknown), ("gross_m2_central_exact", core.fmt_exact(c)),
                        ("gross_m2_low_exact", core.fmt_exact(lo)), ("gross_m2_high_exact", core.fmt_exact(hi)),
                        ("gross_m2_central_presented", core.present(c)), ("gross_m2_low_presented", core.present(lo)),
                        ("gross_m2_high_presented", core.present(hi)),
                        ("incomplete", n_unknown > 0)])


def deviating_sizes(rows, key=lambda r: (r["layer"], r["frame_type"]), tol=0.25, min_group=3):
    """Afwijkende maten t.o.v. gelijksoortige kozijnen (zelfde laag en type), op relatieve breedte. Alleen een signaal."""
    groups = defaultdict(list)
    for r in rows:
        if r.get("width_pitch_units") is not None:
            groups[key(r)].append(r)
    flagged = {}
    for g, items in groups.items():
        if len(items) < min_group:
            continue
        med = statistics.median([i["width_pitch_units"] for i in items])
        for i in items:
            dev = (i["width_pitch_units"] - med) / med
            if abs(dev) > tol:
                flagged[i["id"]] = round(dev, 3)
    return flagged


def geometry_groups(rows, tol_aspect=0.12, tol_width=0.15):
    """Groepeer kozijnen met vergelijkbare relatieve geometrie (zelfde laag/type). Dit is herhaling-KANDIDAAT, nooit een
    identiteitsbesluit: gelijkende kozijnen worden niet samengevoegd."""
    groups, out = [], {}
    for r in sorted(rows, key=lambda r: (r["layer"], r["frame_type"], r.get("width_pitch_units") or 0)):
        if r.get("width_pitch_units") is None:
            continue
        for g in groups:
            ref = g[0]
            if (ref["layer"], ref["frame_type"]) == (r["layer"], r["frame_type"]) and \
                    abs(r["aspect_w_over_h"] - ref["aspect_w_over_h"]) <= tol_aspect * ref["aspect_w_over_h"] and \
                    abs(r["width_pitch_units"] - ref["width_pitch_units"]) <= tol_width * ref["width_pitch_units"]:
                g.append(r)
                break
        else:
            groups.append([r])
    for i, g in enumerate(groups, 1):
        for r in g:
            out[r["id"]] = f"GEOM-{i:02d}"
    return out, groups


# --------------------------------------------------------------------------
# Lokale beeldanalyse (optioneel: OpenCV/NumPy)
# --------------------------------------------------------------------------

def detect_white_frames(img_bgr, y_min=0, y_max=None, min_w=28, min_h=28, max_w=420, max_h=260):
    """Algoritmisch voorstel: lichte, ongekleurde kozijnkaders tegen donker metselwerk. Grove detector, geen semantiek:
    geen onderscheid tussen kozijnen, vleugels of reflecties. Bedoeld om de bestaande annotatie te vergelijken."""
    import cv2
    import numpy as np
    h, w = img_bgr.shape[:2]
    y_max = y_max or h
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 2] > 170) & (hsv[:, :, 1] < 60)).astype("uint8") * 255
    mask[:y_min] = 0
    mask[y_max:] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw < min_w or bh < min_h or bw > max_w or bh > max_h:
            continue
        fill = cv2.contourArea(c) / float(bw * bh)
        if fill < 0.35:
            continue
        boxes.append([x, y, x + bw, y + bh])
    return boxes


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def compare_detections(detections, annotations, thr=0.3):
    """Overeenstemming tussen algoritmisch voorstel en bestaande annotatie (greedy op IoU). GEEN precision/recall t.o.v.
    grondwaarheid: de annotatie is zelf een handmatige lezing."""
    used, matched = set(), []
    for ann_id, box in annotations:
        best, best_i = 0.0, None
        for i, d in enumerate(detections):
            if i in used:
                continue
            v = iou(box, d)
            if v > best:
                best, best_i = v, i
        if best_i is not None and best >= thr:
            used.add(best_i)
            matched.append({"annotation": ann_id, "iou": round(best, 3), "detection": detections[best_i]})
    return {"n_annotations": len(annotations), "n_detections": len(detections), "n_agree": len(matched),
            "annotations_without_detection": [a for a, _ in annotations if a not in {m["annotation"] for m in matched}],
            "detections_without_annotation": [d for i, d in enumerate(detections) if i not in used], "matches": matched,
            "note": "Overeenstemming met een handmatige annotatie; geen onafhankelijke grondwaarheid, dus geen nauwkeurigheidsscore."}
