"""Vector Drawing Source Audit v1 — onderzoekt alle PDF's in de repo op ECHTE vector-tekeninginhoud.

Per pagina: lijn-/rechthoek-/curve-primitives, niet-orthogonale lijnen, afbeeldingsdekking, en tekstlabels (gevel, voorgevel,
achtergevel, zijgevel, aanzicht, doorsnede, plattegrond, kozijn, raam, deur, maatvoering, schaal). Classificatie:

  VECTOR_DRAWING_CANDIDATE  sterk tekeninglabel (aanzicht/plattegrond/doorsnede/kozijnstaat/schaal 1:N/maatvoering) in een korte
                            titelregel EN voldoende vector-primitives, waarvan een deel niet-orthogonaal of curve (geen tabelrasters)
  RASTER_DRAWING_CANDIDATE  pagina gedomineerd door een afbeelding (>= 60%) met vrijwel geen tekst, of met sterk tekeninglabel
  MJOP_REPORT_ONLY          pagina uit een MJOP-/onderhoudsplan-document zonder tekeninginhoud (tabellen, foto's, grafieken)
  NO_DRAWING_FOUND          overige pagina's

'voorgevel'/'achtergevel'/'kozijn' komen in elke MJOP voor als tabeltekst en zijn dus geen tekening-bewijs. Geen OCR,
geen LLM, geen netwerk. Deterministisch: zelfde input -> byte-identieke output.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vector_drawing_reader as vdr  # noqa: E402

AUDIT_VERSION = "vector_drawing_source_audit_v1.0.0"
OUT_JSON = ROOT / "reports" / "drawing" / "vector_drawing_source_audit_v1.json"
OUT_MD = ROOT / "reports" / "drawing" / "vector_drawing_source_audit_v1.md"
REGISTRY = ROOT / "reports" / "document_registry.json"

TERMS = {
    "gevel": r"(?<![a-z])gevels?\b", "voorgevel": r"voorgevels?", "achtergevel": r"achtergevels?", "zijgevel": r"zijgevels?",
    "aanzicht": r"aanzichten?", "doorsnede": r"doorsnedes?|doorsneden", "plattegrond": r"plattegronden?|plattegrond",
    "kozijn": r"kozijn", "raam": r"\b(raam|ramen)\b", "deur": r"\b(deur|deuren)\b", "maatvoering": r"maatvoering", "schaal": r"\bschaal\b",
}
STRONG_RX = re.compile(r"aanzicht|plattegrond|doorsnede|doorsneden|tekening|maatvoering|kozijnstaat|kozijnenstaat|\bschaal\s*1\s*:\s*\d+|\b1\s*:\s*(20|50|100|200)\b", re.I)
MJOP_RX = re.compile(r"onderhoudsplan|meerjaren|\bMJOP\b|\bMOP\b|VvE", re.I)
NON_PDF_EXT = {".dwg", ".dxf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".svg", ".bmp", ".gif", ".ifc"}
MIN_VECTOR_PRIMITIVES = 30
MIN_NONORTHOGONAL_OR_CURVES = 10


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def find_pdfs(root=ROOT):
    return sorted(p for p in Path(root).rglob("*.pdf") if ".git" not in p.parts and "tests" not in p.relative_to(root).parts)


def find_non_pdf_drawing_like_files(root=ROOT):
    own = Path(root) / "reports" / "drawing"  # eigen uitvoer (overlays van de test-fixture) telt niet als bron
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*") if p.is_file() and p.suffix.lower() in NON_PDF_EXT and ".git" not in p.parts
                  and "tests" not in p.relative_to(root).parts and own not in p.parents)


def audit_page(page, number):
    text = page.extract_text() or ""
    lines = page.lines
    nonortho = sum(1 for ln in lines if abs(ln["x0"] - ln["x1"]) > 1 and abs(ln["top"] - ln["bottom"]) > 1)
    nonortho += sum(1 for c in page.curves if len(c.get("pts", [])) > 5 or not vdr_closed_rect(c))
    img_area = sum((im["x1"] - im["x0"]) * (im["bottom"] - im["top"]) for im in page.images) / (page.width * page.height)
    hits = {k: len(re.findall(rx, text, re.I)) for k, rx in TERMS.items()}
    hits = {k: v for k, v in hits.items() if v}
    strong = sorted({m.group(0).lower() for m in STRONG_RX.finditer(text)})
    prims = len(lines) + len(page.rects) + len(page.curves)
    return {"page": number, "width_pt": round(float(page.width), 2), "height_pt": round(float(page.height), 2),
            "vector_primitives": {"lines": len(lines), "rects": len(page.rects), "curves": len(page.curves), "total": prims,
                                  "non_orthogonal_lines_or_complex_curves": nonortho},
            "images": len(page.images), "image_area_ratio": round(img_area, 3), "chars": len(page.chars),
            "label_hits": hits, "strong_drawing_labels": strong,
            "_text_head": text[:600]}


def vdr_closed_rect(c):
    return vdr._closed_rect_curve({"points": [[x, y] for x, y in c["pts"]]})


def classify_page(a, doc_is_mjop):
    p, reasons = a["vector_primitives"], []
    strong = bool(a["strong_drawing_labels"])
    vector = strong and p["total"] >= MIN_VECTOR_PRIMITIVES and p["non_orthogonal_lines_or_complex_curves"] >= MIN_NONORTHOGONAL_OR_CURVES
    if vector:
        return "VECTOR_DRAWING_CANDIDATE", ["strong_label", f"{p['total']} vector primitives", f"{p['non_orthogonal_lines_or_complex_curves']} niet-orthogonaal/complex"]
    if a["image_area_ratio"] >= 0.6 and a["chars"] <= 60:
        return "RASTER_DRAWING_CANDIDATE", ["pagina bijna volledig afbeelding, vrijwel geen tekst (handmatig controleren: kan ook een scan of foto zijn)"]
    if a["image_area_ratio"] >= 0.4 and strong:
        return "RASTER_DRAWING_CANDIDATE", ["grote afbeelding + sterk tekeninglabel"]
    if strong:
        reasons.append("sterk label maar onvoldoende/orthogonale vector-primitives (tabelraster): geen tekening")
    if doc_is_mjop and a["chars"] >= 20:
        return "MJOP_REPORT_ONLY", reasons or ["tabel-/tekstpagina van een onderhoudsplan"]
    if a["chars"] < 20 and p["total"] == 0 and a["images"] == 0:
        return "NO_DRAWING_FOUND", ["lege pagina"]
    return "NO_DRAWING_FOUND", reasons or ["geen tekeninginhoud"]


def registry_ids(sha):
    if not REGISTRY.exists():
        return []
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return sorted(d["document_id"] for d in reg["documents"] if d.get("sha256") == sha)


def audit(root=ROOT):
    import pdfplumber
    by_sha = {}
    for p in find_pdfs(root):
        by_sha.setdefault(sha256_file(p), []).append(str(p.relative_to(root)))
    docs = []
    for sha in sorted(by_sha, key=lambda s: by_sha[s][0]):
        paths = sorted(by_sha[sha])
        with pdfplumber.open(Path(root) / paths[0]) as pdf:
            first_text = " ".join((pg.extract_text() or "") for pg in pdf.pages[:3])
            is_mjop = bool(MJOP_RX.search(first_text))
            pages, counts = [], {}
            for i, pg in enumerate(pdf.pages, 1):
                a = audit_page(pg, i)
                a["classification"], a["reasons"] = classify_page(a, is_mjop)
                a.pop("_text_head")
                counts[a["classification"]] = counts.get(a["classification"], 0) + 1
                pages.append(a)
        order = ["VECTOR_DRAWING_CANDIDATE", "RASTER_DRAWING_CANDIDATE", "MJOP_REPORT_ONLY", "NO_DRAWING_FOUND"]
        doc_class = next(c for c in order if counts.get(c))
        docs.append({"sha256": sha, "paths": paths, "registry_document_ids": registry_ids(sha), "page_count": len(pages), "looks_like_mjop_report": is_mjop,
                     "classification": doc_class, "page_classification_counts": {k: counts[k] for k in order if k in counts},
                     "pages_with_images_ge_15pct": [p["page"] for p in pages if p["image_area_ratio"] >= 0.15],
                     "max_non_orthogonal_per_page": max(p["vector_primitives"]["non_orthogonal_lines_or_complex_curves"] for p in pages),
                     "pages": pages})
    summary = {"unique_pdfs": len(docs), "total_pdf_paths": sum(len(d["paths"]) for d in docs), "total_pages": sum(d["page_count"] for d in docs),
               "by_document_classification": {c: sum(1 for d in docs if d["classification"] == c) for c in
                                              ("VECTOR_DRAWING_CANDIDATE", "RASTER_DRAWING_CANDIDATE", "MJOP_REPORT_ONLY", "NO_DRAWING_FOUND")},
               "pages_with_strong_drawing_label": sum(1 for d in docs for pg in d["pages"] if pg["strong_drawing_labels"]),
               "pages_with_vector_primitives_ge_30": sum(1 for d in docs for pg in d["pages"] if pg["vector_primitives"]["total"] >= MIN_VECTOR_PRIMITIVES),
               "vector_drawing_candidate_pages": sum(d["page_classification_counts"].get("VECTOR_DRAWING_CANDIDATE", 0) for d in docs),
               "raster_drawing_candidate_pages": sum(d["page_classification_counts"].get("RASTER_DRAWING_CANDIDATE", 0) for d in docs)}
    real_world = "REAL_WORLD_POC_POSSIBLE" if summary["vector_drawing_candidate_pages"] else "REAL_WORLD_POC_BLOCKED_NO_DRAWING"
    return {"audit_version": AUDIT_VERSION, "tools": vdr.tool_versions(),
            "method": "pdfplumber primitives + tekstlabels; thresholds: sterk label + >= %d primitives + >= %d niet-orthogonale lijnen/complexe curves" %
                      (MIN_VECTOR_PRIMITIVES, MIN_NONORTHOGONAL_OR_CURVES),
            "non_pdf_drawing_like_files": find_non_pdf_drawing_like_files(root), "summary": summary, "real_world_status": real_world, "documents": docs}


def render_md(a):
    s = a["summary"]
    L = ["# Vector Drawing Source Audit v1", "",
         f"Status: **{a['real_world_status']}**" + ("" if a["real_world_status"] == "REAL_WORLD_POC_POSSIBLE" else
                                                    " — er staat geen bruikbare vector bouw-/geveltekening in de repo."), "",
         f"- Unieke PDF's: {s['unique_pdfs']} ({s['total_pdf_paths']} bestandspaden; duplicaten via sha256 samengevoegd), {s['total_pages']} pagina's onderzocht",
         f"- VECTOR_DRAWING_CANDIDATE pagina's: {s['vector_drawing_candidate_pages']}", f"- RASTER_DRAWING_CANDIDATE pagina's: {s['raster_drawing_candidate_pages']}",
         f"- Pagina's met een sterk tekeninglabel (aanzicht/plattegrond/doorsnede/tekening/maatvoering/schaal 1:N): {s['pages_with_strong_drawing_label']}",
         f"- Pagina's met >= {MIN_VECTOR_PRIMITIVES} vector-primitives (vrijwel allemaal tabelrasters/grafieken): {s['pages_with_vector_primitives_ge_30']}",
         f"- Niet-PDF tekeningachtige bestanden (dwg/dxf/png/jpg/svg/ifc...): {len(a['non_pdf_drawing_like_files'])} (alleen de review-sheets van de eerdere public-image facade-PoC; foto's, geen tekeningen)",
         "- Methode: " + a["method"], "- Tools: " + ", ".join(f"{k} {v}" for k, v in a["tools"].items()), "",
         "Interpretatie: 'voorgevel'/'achtergevel'/'kozijn' staan in elke MJOP als tabeltekst en zijn geen tekeningbewijs. De rechthoeken en "
         "lijnen in de MJOP-PDF's zijn tabelrasters, grafieken en logo's; geen enkele pagina draagt een tekeninglabel of een schaal/maatvoering. Afbeeldingen zijn omslag- en conditiefoto's (steekproef visueel gecontroleerd: een omslagpagina en een conditiefoto-pagina).", "",
         "## Per document", "", "| Document (eerste pad) | registry | pagina's | classificatie | pagina's per klasse | max niet-orthogonale lijnen/complexe curves per pagina | pagina's met afbeelding >= 15% |", "|---|---|---|---|---|---|---|"]
    for d in a["documents"]:
        L.append(f"| {d['paths'][0]}{' (+' + str(len(d['paths']) - 1) + ' duplicaat)' if len(d['paths']) > 1 else ''} | {', '.join(d['registry_document_ids']) or '—'} | "
                 f"{d['page_count']} | {d['classification']} | {json.dumps(d['page_classification_counts'])} | {d['max_non_orthogonal_per_page']} | "
                 f"{', '.join(map(str, d['pages_with_images_ge_15pct'])) or '—'} |")
    L += ["", "## Niet-PDF tekeningachtige bestanden", ""] + ([f"- {p}" for p in a["non_pdf_drawing_like_files"]] or ["Geen."])
    L += ["", "Paginagegevens (primitive-aantallen, labelhits, redenen) per pagina staan in het JSON-rapport."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    a = audit()
    js, md = json.dumps(a, ensure_ascii=False, indent=1) + "\n", render_md(a)
    if args.check:
        ok = OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("actueel" if ok else "VERSCHIL")
        return 0 if ok else 1
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(a["real_world_status"], a["summary"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
