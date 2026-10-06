"""Vector Drawing Reader PoC v1 — generieke primitive reader, schaalbewijs, paginatype en conservatieve opening candidates.

Lokaal, deterministisch en gratis: pdfplumber (MIT) + pdfminer.six (MIT), beide al dependencies van de pipeline.
Geen OCR, geen LLM, geen netwerk, geen betaalde API, geen PyMuPDF.

Volgorde (bewust): ruwe primitives bewaren -> schaal/maatvoering onderbouwen -> paginatype uit expliciete labels ->
OPENING CANDIDATES (REVIEW_REQUIRED, nooit canonical frames).

Harde regels:
- Nooit PDF-punten/pixels naar meters zonder schaalbewijs (maatlijn of tekeningschaal + consistente geometrie).
  Zonder bewijs: ScaleError / status UNKNOWN.
- Een rechthoek in een gevel is NIET automatisch een raam: een candidate vraagt gevelvlak EN minstens één van
  herhaling, expliciet label of maatvoering-context. Candidate != confirmed frame.
- SAME_SYMBOL_CANDIDATE != hetzelfde fysieke component tot menselijke bevestiging.
"""
import hashlib
import json
import re
import statistics
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

READER_VERSION = "vector_primitive_reader_v1.0.0"
OBSERVATION_CONTRACT = "drawing_observation_v1"
MM_PER_PT_PAPER = Decimal("25.4") / Decimal("72")
SCALE_TOLERANCE = Decimal("0.02")  # onderlinge afwijking tussen maatlijnen / tussen maatlijn en tekeningschaal
ISO_PAPER_MM = {"A0": (841, 1189), "A1": (594, 841), "A2": (420, 594), "A3": (297, 420), "A4": (210, 297), "A5": (148, 210)}
OBSERVATIONS_DIR = ROOT / "data" / "drawing_observations"

DIM_TEXT_RE = re.compile(r"^(\d{2,5})\s*(mm)?$")
SCALE_RE = re.compile(r"(?:schaal\s*)?\b1\s*:\s*(\d{1,4})\b", re.I)

PAGE_TYPE_LABELS = {
    "FACADE_ELEVATION": re.compile(r"\b(gevelaanzicht|aanzicht)\b", re.I),
    "FLOOR_PLAN": re.compile(r"\bplattegrond\b", re.I),
    "SECTION": re.compile(r"\b(doorsnede|snede)\b", re.I),
    "SCHEDULE": re.compile(r"\b(kozijnstaat|kozijnenstaat|kozijnlijst|kozijnenlijst|deurenstaat|deurstaat)\b", re.I),
    "DETAIL": re.compile(r"\bdetail\b", re.I),
}
SIDE_LABELS = (("FRONT", re.compile(r"voorgevel", re.I)), ("REAR", re.compile(r"achtergevel", re.I)),
               ("LEFT", re.compile(r"linker\s*(zij)?gevel", re.I)), ("RIGHT", re.compile(r"rechter\s*(zij)?gevel", re.I)))
OPENING_LABELS = (("EXTERIOR_DOOR", re.compile(r"\b(deur|deuren)\b", re.I)), ("EXTERIOR_WINDOW", re.compile(r"\b(raam|ramen)\b", re.I)),
                  ("EXTERIOR_FRAME", re.compile(r"kozijn", re.I)))


class ScaleError(RuntimeError):
    """Afmetingen uit punten/pixels zonder aantoonbare schaal zijn verboden."""


def r3(x):
    return round(float(x), 3)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tool_versions():
    import pdfminer
    import pdfplumber
    return {"pdfplumber": pdfplumber.__version__, "pdfminer.six": pdfminer.__version__}


# --------------------------------------------------------------------------
# 1. Ruwe primitives
# --------------------------------------------------------------------------

def _bbox(o):
    return [r3(o["x0"]), r3(o["top"]), r3(o["x1"]), r3(o["bottom"])]


def _color(c):
    return None if c is None else [r3(v) for v in c] if isinstance(c, (tuple, list)) else c


def read_page(page, page_number, optional_content_present=False):
    """Ruwe primitives van één pdfplumber-pagina. Coördinaten: PDF-punten, oorsprong linksboven (x rechts, y naar beneden).
    Geen classificatie."""
    lines = [{"id": f"L{i:04d}", "bbox": _bbox(o), "p0": [r3(o["pts"][0][0]), r3(o["pts"][0][1])], "p1": [r3(o["pts"][-1][0]), r3(o["pts"][-1][1])],
              "linewidth": r3(o.get("linewidth") or 0), "stroking_color": _color(o.get("stroking_color")), "mcid": o.get("mcid"), "tag": o.get("tag")}
             for i, o in enumerate(page.lines, 1)]
    rects = [{"id": f"R{i:04d}", "bbox": _bbox(o), "fill": bool(o.get("fill")), "stroke": bool(o.get("stroke")), "linewidth": r3(o.get("linewidth") or 0),
              "stroking_color": _color(o.get("stroking_color")), "non_stroking_color": _color(o.get("non_stroking_color")), "mcid": o.get("mcid"), "tag": o.get("tag")}
             for i, o in enumerate(page.rects, 1)]
    curves = [{"id": f"C{i:04d}", "bbox": _bbox(o), "points": [[r3(x), r3(y)] for x, y in o["pts"]], "fill": bool(o.get("fill")), "stroke": bool(o.get("stroke")),
               "linewidth": r3(o.get("linewidth") or 0), "mcid": o.get("mcid"), "tag": o.get("tag")} for i, o in enumerate(page.curves, 1)]
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False, extra_attrs=["fontname", "size"])
    spans = [{"id": f"T{i:04d}", "text": w["text"], "bbox": _bbox(w), "fontname": w["fontname"], "size": r3(w["size"])} for i, w in enumerate(words, 1)]
    images = [{"id": f"I{i:04d}", "bbox": _bbox(o)} for i, o in enumerate(page.images, 1)]
    return {"page": page_number, "width_pt": r3(page.width), "height_pt": r3(page.height), "units": "pdf_points_origin_top_left",
            "raw_counts": {"lines": len(lines), "rects": len(rects), "curves": len(curves), "text_spans": len(spans), "images": len(images)},
            "layers": {"optional_content_present": bool(optional_content_present),
                       "note": "pdfplumber geeft geen laag-toewijzing per object; alleen de aanwezigheid van optional content wordt gemeld"},
            "lines": lines, "rects": rects, "curves": curves, "text_spans": spans, "images": images}


def _mid(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def dimension_texts(page_obs):
    """Numerieke tekstspans (2-5 cijfers, optioneel 'mm') + koppeling aan de dichtstbijzijnde horizontale/verticale lijn waarvan het
    midden binnen 20 pt ligt en waarvan de uitgestrekte as de tekst overspant. Eenheid wordt aangenomen mm; dat is een aanname
    van de maatlijn-conventie (NL bouwtekeningen), vandaar dat het bewijs alleen telt mét gekoppelde lijn."""
    out = []
    for t in page_obs["text_spans"]:
        m = DIM_TEXT_RE.match(t["text"].strip())
        if not m:
            continue
        cx, cy = _mid(t["bbox"])
        best = None
        for ln in page_obs["lines"]:
            (x0, y0), (x1, y1) = ln["p0"], ln["p1"]
            horiz, vert = abs(y1 - y0) < 0.5 and abs(x1 - x0) >= 5, abs(x1 - x0) < 0.5 and abs(y1 - y0) >= 5
            if horiz and min(x0, x1) <= cx <= max(x0, x1):
                d = abs(cy - (y0 + y1) / 2)
                orient, length = "H", abs(x1 - x0)
            elif vert and min(y0, y1) <= cy <= max(y0, y1):
                d = abs(cx - (x0 + x1) / 2)
                orient, length = "V", abs(y1 - y0)
            else:
                continue
            if d <= 20 and (best is None or (d, ln["id"]) < (best[0], best[1]["id"])):
                best = (d, ln, orient, length)
        out.append({"id": f"D{len(out) + 1:04d}", "text": t["text"], "text_span_ref": t["id"], "value_mm": int(m.group(1)), "bbox": t["bbox"],
                    "line_ref": best[1]["id"] if best else None, "line_length_pt": r3(best[3]) if best else None, "orientation": best[2] if best else None})
    return out


def read_document(pdf_path, drawing_id, pages=None, *, is_test_fixture=False, repo_root=ROOT):
    import pdfplumber
    pdf_path = Path(pdf_path)
    try:
        rel = str(pdf_path.resolve().relative_to(Path(repo_root).resolve()))
    except ValueError:
        rel = pdf_path.name
    with pdfplumber.open(pdf_path) as pdf:
        oc = "OCProperties" in (pdf.doc.catalog or {})
        wanted = pages or list(range(1, len(pdf.pages) + 1))
        out_pages = []
        for n in wanted:
            po = read_page(pdf.pages[n - 1], n, oc)
            po["dimension_texts"] = dimension_texts(po)
            out_pages.append(po)
    return {"contract_version": OBSERVATION_CONTRACT, "drawing_id": drawing_id, "is_test_fixture": bool(is_test_fixture),
            "source": {"file": rel, "sha256": sha256_file(pdf_path)},
            "extraction": {"method": "pdfplumber.page.{lines,rects,curves,images,extract_words}", "reader_version": READER_VERSION, **tool_versions()},
            "interpretation": "RAW_PRIMITIVES_ONLY (geen objectclassificatie)", "pages": out_pages}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


# --------------------------------------------------------------------------
# 2. Schaal / maatvoering
# --------------------------------------------------------------------------

def iso_paper(width_pt, height_pt, tol_mm=1.5):
    wmm, hmm = float(width_pt) * 25.4 / 72, float(height_pt) * 25.4 / 72
    for name, (a, b) in ISO_PAPER_MM.items():
        if (abs(wmm - a) <= tol_mm and abs(hmm - b) <= tol_mm) or (abs(wmm - b) <= tol_mm and abs(hmm - a) <= tol_mm):
            return name
    return None


def _fmt(d):
    return format(d.quantize(Decimal("0.000001")), "f")


def determine_scale(page_obs):
    """Schaalbewijs per pagina. Retourneert {status, scale_source, scale_value (mm werkelijkheid per PDF-punt), dimension_evidence_refs, ...}.
    A. maatlijnen (voorkeur): value_mm / lijnlengte; meerdere moeten binnen 2% overeenstemmen.
    B. tekeningschaal '1:N' (precies één verschillende N) + standaard ISO-papierformaat (PDF niet geschaald); is er ook een maatlijn,
       dan moet die binnen 2% kloppen.
    Anders UNKNOWN: dimensions blijven UNKNOWN."""
    unknown = {"status": "UNKNOWN", "scale_source": None, "scale_value": None, "scale_unit": "mm_real_per_pdf_point", "ratio": None,
               "dimension_evidence_refs": [], "reason": None}
    dims = [d for d in page_obs.get("dimension_texts", []) if d["line_ref"] and d["line_length_pt"] and d["line_length_pt"] > 0]
    scales = [(Decimal(d["value_mm"]) / Decimal(str(d["line_length_pt"])), d) for d in dims]
    label_ratios = sorted({int(m.group(1)) for t in page_obs["text_spans"] for m in [SCALE_RE.search(t["text"])] if m and int(m.group(1)) in (5, 10, 20, 25, 50, 100, 200, 500)})
    paper = iso_paper(page_obs["width_pt"], page_obs["height_pt"])
    label_scale = (Decimal(label_ratios[0]) * MM_PER_PT_PAPER) if len(label_ratios) == 1 and paper else None
    if scales:
        vals = [s for s, _ in scales]
        if max(vals) / min(vals) - 1 > SCALE_TOLERANCE:
            return dict(unknown, reason="CONFLICTING_DIMENSION_EVIDENCE: maatlijnen op deze pagina geven verschillende schalen (meerdere tekeningen/schalen op één blad?)")
        med = Decimal(str(statistics.median(vals)))
        res = {"status": "KNOWN", "scale_source": "DIMENSION_LINE", "scale_value": _fmt(med), "scale_unit": "mm_real_per_pdf_point",
               "ratio": None, "dimension_evidence_refs": [d["id"] for _, d in scales], "reason": None}
        if label_scale is not None:
            res["drawing_scale_label"] = f"1:{label_ratios[0]}"
            res["label_consistent"] = abs(label_scale / med - 1) <= SCALE_TOLERANCE
        return res
    if len(label_ratios) > 1:
        return dict(unknown, reason=f"AMBIGUOUS_SCALE_LABELS: meerdere schalen op de pagina {label_ratios}")
    if label_ratios and not paper:
        return dict(unknown, reason="SCALE_LABEL_WITHOUT_STANDARD_PAPER: geen standaard ISO-papierformaat, PDF-geometrie mogelijk geschaald; geen onderbouwde schaal")
    if label_scale is not None:
        return {"status": "KNOWN", "scale_source": "DRAWING_SCALE_LABEL", "scale_value": _fmt(label_scale), "scale_unit": "mm_real_per_pdf_point",
                "ratio": label_ratios[0], "paper_size": paper, "dimension_evidence_refs": [], "reason": None}
    return dict(unknown, reason="NO_SCALE_EVIDENCE: geen maatlijn met gekoppelde maattekst en geen expliciete tekeningschaal")


def to_meters(length_pt, scale):
    """Punten -> meters; alleen met aantoonbare schaal. Zonder bewijs: ScaleError."""
    if not scale or scale.get("status") != "KNOWN" or not scale.get("scale_value"):
        raise ScaleError("geen aantoonbare schaal: afmetingen blijven UNKNOWN (nooit uit punten/pixels naar meters zonder bewijs)")
    return (Decimal(str(length_pt)) * Decimal(scale["scale_value"]) / Decimal(1000))


def fmt_m(d):
    return format(d.quantize(Decimal("0.001")), "f")


# --------------------------------------------------------------------------
# 3. Paginatype (alleen expliciete labels)
# --------------------------------------------------------------------------

def _label_lines(page_obs):
    """Tekst per regel (spans op nagenoeg dezelfde y bijeengevoegd). Een label telt alleen in een KORTE regel (<= 8 woorden), zoals een
    tekeningtitel; zinnen uit tabellen/lopende tekst tellen niet."""
    rows = {}
    for t in page_obs["text_spans"]:
        rows.setdefault(round(t["bbox"][1] / 3), []).append(t)
    out = []
    for key in sorted(rows):
        spans = sorted(rows[key], key=lambda t: t["bbox"][0])
        # splits op grote horizontale gaten (>= 25 pt) zodat losse titelblokken geen zin vormen
        cur = [spans[0]]
        for s in spans[1:]:
            if s["bbox"][0] - cur[-1]["bbox"][2] >= 25:
                out.append(cur)
                cur = [s]
            else:
                cur.append(s)
        out.append(cur)
    return [(" ".join(s["text"] for s in grp), [s["id"] for s in grp]) for grp in out if len(grp) <= 8]


def classify_page_type(page_obs):
    """FACADE_ELEVATION | FLOOR_PLAN | SECTION | DETAIL | SCHEDULE | UNKNOWN. Geen LLM, geen fuzzy match: expliciete labels in korte
    titel-regels. Meerdere verschillende typen -> UNKNOWN. 'voorgevel' alleen is geen paginatype (staat ook in MJOP-tabellen);
    het wordt wel als facade_side-aanwijzing bewaard. DETAIL vereist tevens een expliciete tekeningschaal."""
    found, refs = {}, {}
    lines = _label_lines(page_obs)
    has_scale = any(SCALE_RE.search(t["text"]) for t in page_obs["text_spans"])
    for text, ids in lines:
        for ptype, rx in PAGE_TYPE_LABELS.items():
            if rx.search(text) and not (ptype == "DETAIL" and not has_scale):
                found.setdefault(ptype, []).append(text)
                refs.setdefault(ptype, []).extend(ids)
    side, side_refs = "UNKNOWN", []
    for text, ids in lines:
        for name, rx in SIDE_LABELS:
            if rx.search(text):
                side, side_refs = name, ids
    if len(found) == 1:
        ptype = next(iter(found))
        return {"page_type": ptype, "facade_side": side if ptype == "FACADE_ELEVATION" else "UNKNOWN", "label_refs": sorted(set(refs[ptype])),
                "labels": sorted(set(found[ptype])), "reason": "EXPLICIT_LABEL"}
    reason = "NO_EXPLICIT_LABEL" if not found else "MIXED_LABELS: " + ", ".join(sorted(found))
    return {"page_type": "UNKNOWN", "facade_side": "UNKNOWN", "label_refs": [], "labels": [], "reason": reason, "side_hint": side if side != "UNKNOWN" else None}


# --------------------------------------------------------------------------
# 4. Opening candidates + symbol repetition (alleen op een FACADE_ELEVATION)
# --------------------------------------------------------------------------

def _w(b):
    return b[2] - b[0]


def _h(b):
    return b[3] - b[1]


def _inside(inner, outer, tol=0.5):
    return inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol


def _closed_rect_curve(c):
    pts = c["points"]
    if len(pts) not in (4, 5):
        return False
    xs, ys = sorted({round(p[0], 1) for p in pts}), sorted({round(p[1], 1) for p in pts})
    return len(xs) == 2 and len(ys) == 2


def _boxes(page_obs):
    """(ref, bbox) voor rechthoeken en rechthoekige gesloten paden."""
    out = [(r["id"], r["bbox"]) for r in page_obs["rects"]]
    out += [(c["id"], c["bbox"]) for c in page_obs["curves"] if _closed_rect_curve(c)]
    return out


def _contained_primitives(page_obs, bbox):
    refs = [ln["id"] for ln in page_obs["lines"] if _inside(ln["bbox"], bbox)]
    refs += [rid for rid, b in _boxes(page_obs) if _inside(b, bbox) and b != bbox]
    refs += [c["id"] for c in page_obs["curves"] if _inside(c["bbox"], bbox) and not _closed_rect_curve(c)]
    return sorted(refs)


def symbol_signature(page_obs, bbox):
    """Genormaliseerde vectorstructuur binnen een bbox (relatief aan de linkerbovenhoek, 1 pt afgerond) + afmeting."""
    by_id = {p["id"]: p for k in ("lines", "rects", "curves") for p in page_obs[k]}
    parts = []
    for ref in _contained_primitives(page_obs, bbox):
        b = by_id[ref]["bbox"]
        parts.append((ref[0], round(b[0] - bbox[0]), round(b[1] - bbox[1]), round(b[2] - bbox[0]), round(b[3] - bbox[1])))
    sig = {"size": [round(_w(bbox)), round(_h(bbox))], "parts": sorted(parts)}
    return hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:16]


def find_opening_candidates(page_obs, page_info, scale, drawing_id="DRAWING"):
    """Conservatieve geometrische opening candidates. Alleen als page_type == FACADE_ELEVATION. Retourneert (candidates, symbol_groups,
    diagnostics). Candidate-status is altijd REVIEW_REQUIRED; nooit een canonical frame."""
    diag = {"considered_boxes": 0, "rejected_not_inside_facade_plane": 0, "rejected_no_supporting_evidence": 0, "suppressed_nested": 0, "facade_plane_ref": None}
    if page_info.get("page_type") != "FACADE_ELEVATION":
        diag["skipped"] = "page_type is geen FACADE_ELEVATION; geen candidates"
        return [], [], diag
    page_area = page_obs["width_pt"] * page_obs["height_pt"]
    boxes = sorted(_boxes(page_obs), key=lambda rb: -_w(rb[1]) * _h(rb[1]))
    planes = [(rid, b) for rid, b in boxes if _w(b) * _h(b) >= 0.1 * page_area and _w(b) * _h(b) <= 0.9 * page_area]
    if not planes:
        diag["skipped"] = "geen gevelvlak (grote buitencontour) gevonden"
        return [], [], diag
    plane_ref, plane = planes[0]
    diag["facade_plane_ref"] = plane_ref
    plane_area = _w(plane) * _h(plane)
    dims = [d for d in page_obs.get("dimension_texts", []) if d["line_ref"]]
    line_by_id = {ln["id"]: ln for ln in page_obs["lines"]}
    pool = []
    for rid, b in boxes:
        if rid == plane_ref or _w(b) < 5 or _h(b) < 5:
            continue
        diag["considered_boxes"] += 1
        if not (0.2 <= _w(b) / _h(b) <= 5) or _w(b) * _h(b) > 0.25 * plane_area:
            continue
        if not _inside(b, plane):
            diag["rejected_not_inside_facade_plane"] += 1
            continue
        pool.append((rid, b))
    # herhaling: >= 3 boxes met dezelfde afmeting (2 pt tolerantie)
    def same_size(a, b):
        return abs(_w(a) - _w(b)) <= 2 and abs(_h(a) - _h(b)) <= 2
    cands, texts = [], page_obs["text_spans"]
    for rid, b in pool:
        reps = sum(1 for _, o in pool if same_size(b, o))
        near = [t for t in texts if t["bbox"][2] >= b[0] - 30 and t["bbox"][0] <= b[2] + 30 and t["bbox"][3] >= b[1] - 30 and t["bbox"][1] <= b[3] + 30]
        label_type = None
        for ctype, rx in OPENING_LABELS:
            if any(rx.search(t["text"]) for t in near):
                label_type = ctype
                break
        dim_ctx = []
        for d in dims:
            ln = line_by_id[d["line_ref"]]
            lb = ln["bbox"]
            # maatlijn die (bijna) langs een rand van de box loopt en de breedte/hoogte overspant
            if d["orientation"] == "H" and abs(abs(ln["p1"][0] - ln["p0"][0]) - _w(b)) <= 2 and b[0] - 2 <= min(ln["p0"][0], ln["p1"][0]) <= b[0] + 2 \
                    and (abs(lb[1] - b[3]) <= 25 or abs(lb[1] - b[1]) <= 25):
                dim_ctx.append(("W", d))
            if d["orientation"] == "V" and abs(abs(ln["p1"][1] - ln["p0"][1]) - _h(b)) <= 2 and b[1] - 2 <= min(ln["p0"][1], ln["p1"][1]) <= b[1] + 2 \
                    and (abs(lb[0] - b[0]) <= 25 or abs(lb[0] - b[2]) <= 25):
                dim_ctx.append(("H", d))
        evidence = {"inside_facade_plane": True, "repetition": reps >= 3, "explicit_label": label_type is not None, "dimension_context": bool(dim_ctx)}
        if not (evidence["repetition"] or evidence["explicit_label"] or evidence["dimension_context"]):
            diag["rejected_no_supporting_evidence"] += 1
            continue
        cands.append({"rid": rid, "bbox": b, "evidence": evidence, "label_type": label_type, "near": near, "dims": dim_ctx, "reps": reps})
    # geneste candidates (bv. beglazing in kozijn) onderdrukken: alleen de buitenste
    keep = []
    for c in cands:
        if any(o is not c and _inside(c["bbox"], o["bbox"]) and o["bbox"] != c["bbox"] for o in cands):
            diag["suppressed_nested"] += 1
        else:
            keep.append(c)
    keep.sort(key=lambda c: (round(c["bbox"][1]), c["bbox"][0], c["rid"]))
    out = []
    for i, c in enumerate(keep, 1):
        b = c["bbox"]
        item = {"candidate_id": f"OC-{drawing_id}-p{page_obs['page']}-{i:03d}", "page": page_obs["page"], "bbox": b,
                "facade_side": page_info.get("facade_side", "UNKNOWN"), "possible_type": c["label_type"] or "UNKNOWN",
                "width_m": None, "height_m": None, "dimension_basis": "UNKNOWN", "scale_ref": None,
                "dimension_evidence_refs": sorted(d["id"] for _, d in c["dims"]),
                "nearby_labels": [{"text_span_ref": t["id"], "text": t["text"]} for t in sorted(c["near"], key=lambda t: t["id"])],
                "evidence": c["evidence"], "source_primitive_refs": sorted([c["rid"]] + _contained_primitives(page_obs, b)),
                "status": "REVIEW_REQUIRED", "is_confirmed_frame": False,
                "note": "Geometrische opening candidate; geen canoniek kozijn, raam of deur zonder menselijke bevestiging."}
        if scale and scale.get("status") == "KNOWN":
            item["width_m"], item["height_m"] = fmt_m(to_meters(_w(b), scale)), fmt_m(to_meters(_h(b), scale))
            item["scale_ref"] = {"scale_source": scale["scale_source"], "scale_value": scale["scale_value"]}
            item["dimension_basis"] = "DRAWING_DIMENSION" if c["dims"] else "UNKNOWN"
        out.append(item)
    groups = {}
    for it in out:
        groups.setdefault(symbol_signature(page_obs, it["bbox"]), []).append(it["candidate_id"])
    sym = [{"symbol_group_id": f"SSC-{drawing_id}-p{page_obs['page']}-{sig[:8]}", "signature": sig, "member_candidate_ids": ids, "count": len(ids),
            "status": "SAME_SYMBOL_CANDIDATE", "same_physical_component": False,
            "note": "Zelfde vectorstructuur en afmeting; geen bewijs voor hetzelfde fysieke component tot menselijke bevestiging."}
           for sig, ids in sorted(groups.items()) if len(ids) >= 2]
    return out, sym, diag


# --------------------------------------------------------------------------
# 5. Review-overlay (SVG, reproduceerbaar uit de ruwe primitives)
# --------------------------------------------------------------------------

def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_overlay_svg(page_obs, candidates, dimension_texts_=None, title=""):
    w, h = page_obs["width_pt"], page_obs["height_pt"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
           f'<title>{_esc(title)}</title>', f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>', '<g stroke="#888" fill="none" stroke-width="0.7">']
    for ln in page_obs["lines"]:
        out.append(f'<line x1="{ln["p0"][0]}" y1="{ln["p0"][1]}" x2="{ln["p1"][0]}" y2="{ln["p1"][1]}"/>')
    for r in page_obs["rects"]:
        b = r["bbox"]
        out.append(f'<rect x="{b[0]}" y="{b[1]}" width="{r3(_w(b))}" height="{r3(_h(b))}"/>')
    for c in page_obs["curves"]:
        out.append('<polyline points="' + " ".join(f"{x},{y}" for x, y in c["points"]) + '"/>')
    out.append('</g><g font-family="Helvetica,Arial,sans-serif" fill="#444">')
    for t in page_obs["text_spans"]:
        out.append(f'<text x="{t["bbox"][0]}" y="{t["bbox"][3] - 1}" font-size="{t["size"]}">{_esc(t["text"])}</text>')
    out.append('</g><g fill="none" stroke="#1a7f37" stroke-width="1.2">')
    for d in dimension_texts_ or []:
        b = d["bbox"]
        out.append(f'<rect x="{b[0] - 1}" y="{b[1] - 1}" width="{r3(_w(b) + 2)}" height="{r3(_h(b) + 2)}"><title>{_esc(d["id"])} {d["value_mm"]} mm</title></rect>')
    out.append('</g><g fill="none" stroke="#d1242f" stroke-width="1.6" font-family="Helvetica,Arial,sans-serif" font-size="9" fill-opacity="0">')
    for c in candidates:
        b = c["bbox"]
        out.append(f'<rect x="{b[0]}" y="{b[1]}" width="{r3(_w(b))}" height="{r3(_h(b))}"/>'
                   f'<text x="{b[0]}" y="{b[1] - 2}" fill="#d1242f" stroke="none">{_esc(c["candidate_id"].rsplit("-", 1)[1])}</text>')
    out.append('</g></svg>')
    return "\n".join(out) + "\n"
