"""Range-based building project discovery — read-only rapportage over een Real Building Validation-package.

Zie docs/building_projects_v1.md ("Range discovery v2"). Leest:
  - data/external/building_validation/<versie>/candidates/*.json (hash-gecontroleerd via manifest_errors)
  - data/building_projects/{building_project_records,unresolved_case_records,supporting_evidence_records}.json
  - data/verified/DOC-005.json / DOC-006.json (alleen voor de Maldenhof-dakreview)

Schrijft alleen rapporten:
  reports/building_projects/range_discovery_v2.{json,md}
  reports/quantity/maldenhof_roof_scope_review_v1.{json,md}

Kiest nooit een pariteit, keurt niets goed, wijzigt geen store en corrigeert geen hoeveelheid.

    python scripts/building_project_discovery_report.py [--check]
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import building_projects as bp  # noqa: E402
import fetch_real_building_validation as frbv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VALIDATION_DIR = ROOT / "data" / "external" / "building_validation" / "real_validation_v2"
OUT_JSON = ROOT / "reports" / "building_projects" / "range_discovery_v2.json"
OUT_MD = ROOT / "reports" / "building_projects" / "range_discovery_v2.md"
ROOF_JSON = ROOT / "reports" / "quantity" / "maldenhof_roof_scope_review_v1.json"
ROOF_MD = ROOT / "reports" / "quantity" / "maldenhof_roof_scope_review_v1.md"
REPORT_VERSION = "range_discovery_v2"
RANK = frbv.STRENGTH_ORDER

CLASSES = {
    "APPROVED_PROJECT": "document zit in een ACTIVE building_project; dit package is alleen ondersteunend bewijs",
    "STRONG_CANDIDATE": "minstens één STRONG hypothese; sterk bewijs, maar geen goedkeuring (alleen een mens via 'approve')",
    "MODERATE_CANDIDATE": "beste hypothese is MODERATE (bijv. MJOP noemt geen aantal eenheden); menselijke beoordeling nodig",
    "REVIEW_CASE": "geen hypothese voldoende bevestigd, of tegenstrijdig bewijs; zie blokkerende checks",
}


def _dec(x):
    return None if x is None else Decimal(str(x))


def hypothesis_row(h, pkg):
    threed = {p["bag_pand_id"]: (p.get("threedbag") or {}).get("attributes") or {} for p in pkg["candidate_panden"]}
    extra = []
    for r in h["panden"]:
        for d in r.get("vbo_without_matched_address_details") or []:
            extra.append({"bag_pand_id": r["bag_pand_id"], "huisnummer": d["huisnummer"], "huisletter": d["huisletter"],
                          "toevoeging": d["toevoeging"], "status": d["status"], "outside_requested_number_range": d["outside_requested_number_range"]})
    sums = {}
    for k in ("b3_opp_dak_plat", "b3_opp_dak_schuin", "b3_opp_buitenmuur"):
        vals = [_dec(threed.get(pid, {}).get(k)) for pid in h["bag_pand_ids"]]
        sums[k] = str(sum(v for v in vals if v is not None)) if vals and all(v is not None for v in vals) else None
    return {
        "hypothesis_id": h["hypothesis_id"],
        "description": h["description"],
        "strength": h["strength"],
        "unique_addresses": h["counts"]["unique_bag_addresses"],
        "exact_number_matches": h["counts"].get("exact_number_matches"),
        "toevoeging_matches": h["counts"].get("toevoeging_matches"),
        "vbo_total_bag": h["counts"]["vbo_total_bag"],
        "bag_panden": h["counts"]["unique_bag_panden"],
        "bag_pand_ids": h["bag_pand_ids"],
        "bouwjaren_bag": h.get("bouwjaren_bag"),
        "threedbag_coverage": h.get("threedbag_coverage"),
        "threedbag_sums_evidence_only": sums,
        "mjop_number_of_units": h["mjop_number_of_units"],
        "missing_numbers": h["addresses_missing"],
        "extra_vbo_without_matched_address": extra,
        "panden_sharing_numbers_outside_scope": {r["bag_pand_id"]: r["numbers_queried_outside_scope"] for r in h["panden"] if r["numbers_queried_outside_scope"]},
        "toevoegingen": h.get("toevoegingen") or [],
        "geographic_extent_m": h.get("geographic_extent_m"),
        "failing_checks": sorted(k for k, v in h["checks"].items() if v is False),
        "unknown_checks": sorted(k for k, v in h["checks"].items() if v is None),
        "flags": h["flags"],
    }


def classify(pkg, rows, projects, unresolved, support):
    docs = set(pkg["document_ids"])
    proj = [r for r in projects["records"] if r["status"] == "ACTIVE" and docs & set(r["document_ids"])]
    ucase = [r["case_id"] for r in unresolved["records"] if r["status"] == "ACTIVE" and docs & set(r["document_ids"])]
    top = max((RANK[r["strength"]] for r in rows), default=0)
    best = [r["hypothesis_id"] for r in rows if RANK[r["strength"]] == top] if top >= RANK["MODERATE_BUILDING_PROJECT_CANDIDATE"] else []
    if proj:
        cls = "APPROVED_PROJECT"
    elif top == RANK["STRONG_BUILDING_PROJECT_CANDIDATE"]:
        cls = "STRONG_CANDIDATE"
    elif top == RANK["MODERATE_BUILDING_PROJECT_CANDIDATE"] and len(best) == 1:
        cls = "MODERATE_CANDIDATE"
    else:
        cls = "REVIEW_CASE"
    ev = [r["evidence_id"] for r in support["records"] if r["status"] == "ACTIVE" and proj
          and r["building_project_id"] in {p["building_project_id"] for p in proj}]
    return {"candidate_class": cls, "most_supported_hypotheses": best,
            "selected_scope": None, "approved_building_project_ids": [p["building_project_id"] for p in proj],
            "supporting_evidence_ids": ev, "unresolved_case_ids": ucase}


def build_discovery(out_dir=VALIDATION_DIR, root=ROOT):
    out_dir = Path(out_dir)
    errs = frbv.manifest_errors(out_dir)
    if errs:
        raise bp.ProjectError("package/manifest niet consistent: " + "; ".join(errs))
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    projects = bp.load_store(bp.PROJECT_STORE, bp.new_project_store)
    unresolved = bp.load_store(bp.UNRESOLVED_STORE, bp.new_unresolved_store)
    support = bp.load_store(bp.SUPPORT_STORE, bp.new_support_store)
    groups = []
    for gid in sorted(manifest["candidate_packages"]):
        pkg = json.loads((out_dir / manifest["candidate_packages"][gid]["path"]).read_text(encoding="utf-8"))
        bpc = pkg["building_project_candidate"]
        rows = [hypothesis_row(h, pkg) for h in bpc["scope_hypotheses"]]
        groups.append({
            "group_id": gid, "document_ids": pkg["document_ids"], "label": pkg["label"],
            "segments": pkg.get("segments"), "mjop": pkg["mjop_context"]["combined"],
            "document_address_key": pkg["mjop_context"].get("document_address_key"),
            "classification": classify(pkg, rows, projects, unresolved, support),
            "parity_distinction": bpc.get("parity_distinction"),
            "group_flags": [f for f in pkg["review_flags"] if not f.startswith("[")],
            "hypotheses": rows,
        })
    return {"report_version": REPORT_VERSION,
            "note": "Read-only. Kiest geen pariteit en keurt niets goed; goedkeuren kan alleen via 'building_projects.py approve' door een mens.",
            "classes": CLASSES,
            "input": {"validation_dir": bp.rel(out_dir, root), "manifest_sha256": bp.sha_file(out_dir / "manifest.json"),
                      "run_id": manifest["run_id"], "tool": manifest["tool"],
                      "project_store_sha256": bp._canonical_sha(projects), "unresolved_store_sha256": bp._canonical_sha(unresolved),
                      "support_store_sha256": bp._canonical_sha(support)},
            "groups": groups}


def _md(x):
    return str(x).replace("|", "\\|")


def render_discovery(rep):
    L = ["# Range discovery v2", "",
         "Read-only rapport over `" + rep["input"]["validation_dir"] + "` (" + rep["input"]["tool"] + "). "
         "Er wordt geen pariteit gekozen en niets goedgekeurd. 3D BAG-sommen zijn evidence, geen onderhoudshoeveelheden.", "",
         "| Groep | Documenten | Klasse | Meest ondersteund | Goedgekeurd / bewijs / unresolved |", "|---|---|---|---|---|"]
    for g in rep["groups"]:
        c = g["classification"]
        L.append(f"| {g['group_id']} | {', '.join(g['document_ids'])} | {c['candidate_class']} | {_md(', '.join(c['most_supported_hypotheses'])) or '—'} | "
                 f"{', '.join(c['approved_building_project_ids'] + c['supporting_evidence_ids'] + c['unresolved_case_ids']) or '—'} |")
    for g in rep["groups"]:
        m = g["mjop"]
        L += ["", f"## {g['group_id']} — {g['label']}", "",
              f"- MJOP: eenheden {m.get('number_of_units') if m.get('number_of_units') is not None else '— (niet in bron)'}, "
              f"bouwjaar {m.get('construction_year') or '—'}, postcode {m.get('postcode') or '—'}, plaats {m.get('city') or '—'}; documentadres `{g['document_address_key']}`",
              f"- Klasse: **{g['classification']['candidate_class']}** — {CLASSES[g['classification']['candidate_class']]}"]
        pdist = g["parity_distinction"] or {}
        if pdist:
            L.append(f"- Pariteit onderscheidend op pandniveau: {'ja' if pdist.get('parity_distinguishes_at_pand_level') else 'nee'}"
                     + "".join(f"; {st}: {'ja' if d['parity_distinguishes_at_pand_level'] else 'nee'}" for st, d in (pdist.get("per_street") or {}).items()))
        for f in g["group_flags"]:
            L.append(f"- `{f}`")
        L += ["", "| Hypothese | Sterkte | Adressen (exact+toev.) | VBO | Panden | Bouwjaren | 3D BAG | Ontbrekend | Extra VBO | Falende checks |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for h in g["hypotheses"]:
            L.append(f"| {_md(h['hypothesis_id'])} | {h['strength'].replace('_BUILDING_PROJECT_CANDIDATE', '')} | {h['unique_addresses']} "
                     f"({h['exact_number_matches']}+{h['toevoeging_matches']}) | {h['vbo_total_bag']} | {h['bag_panden']} | "
                     f"{', '.join(map(str, h['bouwjaren_bag'] or [])) or '—'} | {h['threedbag_coverage']['panden_with_attributes']}/{h['threedbag_coverage']['panden']} | "
                     f"{len(h['missing_numbers'])} | {len(h['extra_vbo_without_matched_address'])} | {', '.join(h['failing_checks']) or '—'} |")
        toev = sorted({t for h in g["hypotheses"] for t in h["toevoegingen"]})
        if toev:
            L.append("")
            L.append("Toevoegingen in scope: " + ", ".join(toev))
    L.append("")
    return "\n".join(L)


# --- Maldenhof: 3D BAG vs historisch dak (classificatie, geen correctie) ------------------------------------

ROOF_ELEMENTS = ("DOC-005-EL-025", "DOC-005-EL-027", "DOC-006-EL-025", "DOC-006-EL-027")
EXPLORATORY_OUTBUILDINGS = {
    "status": "EXPLORATORY_NOT_EVIDENCE",
    "retrieved_at": "2026-09-30",
    "method": "BAG OGC pand-items in de omhullende (±0,0004° lon, ±0,0003° lat) van de EVEN_ONLY-adrespunten; panden 'in gebruik' "
              "zonder verblijfsobject en buiten BPRJ-00001; 3D BAG per pand. Niet als evidence package vastgelegd.",
    "panden": 18, "bouwjaar": 1981, "b3_opp_dak_plat_sum_m2": "94.80", "b3_opp_dak_schuin_sum_m2": "0.0",
    "note": "18 kleine panden van ~5 m² (vermoedelijk bergingen) met plat dak. Welke bij de VvE horen (even kant) is onbekend; "
            "ook opgeteld (190.65 + 94.80 = 285.45 m²) verklaren ze 425.80 m² niet volledig.",
}


def _element_facts(root):
    out = []
    for d in ("DOC-005", "DOC-006"):
        j = json.loads((Path(root) / "data" / "verified" / f"{d}.json").read_text(encoding="utf-8"))
        for e in j["elements"]:
            if e["element_id"] not in ROOF_ELEMENTS:
                continue
            prov = e["element_code"]["provenance"]
            out.append({"element_id": e["element_id"], "document_id": d, "element_code": e["element_code"]["original_value"],
                        "element_name": e["element_name"]["value"], "location": e["location"]["value"],
                        "quantity": (e.get("quantity") or {}).get("value"), "unit": ((e.get("unit") or {}).get("original_value")),
                        "provenance": {"page": prov["page"], "block_id": prov["block_id"], "text_fragment": prov["text_fragment"]}})
    return out


def build_roof_review(out_dir=VALIDATION_DIR, root=ROOT):
    pkg = json.loads((Path(out_dir) / "candidates" / "DOC-005-006.json").read_text(encoding="utf-8"))
    h = next(x for x in pkg["building_project_candidate"]["scope_hypotheses"] if x["hypothesis_id"] == "EVEN_ONLY")
    threed = {p["bag_pand_id"]: (p.get("threedbag") or {}) for p in pkg["candidate_panden"]}
    per_pand, plat, schuin = [], Decimal(0), Decimal(0)
    for pid in h["bag_pand_ids"]:
        a = threed[pid].get("attributes") or {}
        per_pand.append({"bag_pand_id": pid, "b3_dak_type": a.get("b3_dak_type"), "b3_opp_dak_plat": a.get("b3_opp_dak_plat"),
                         "b3_opp_dak_schuin": a.get("b3_opp_dak_schuin"), "raw_response_sha256": threed[pid].get("raw_response_sha256")})
        plat += _dec(a.get("b3_opp_dak_plat"))
        schuin += _dec(a.get("b3_opp_dak_schuin"))
    elements = _element_facts(root)
    hist_plat = sorted({e["quantity"] for e in elements if e["element_code"] == "4711"})
    hist_schuin = sorted({e["quantity"] for e in elements if e["element_code"] == "4712"})
    comparisons = []
    for label, hist, b3 in (("plat dak (4711 Dakbedekking APP vs b3_opp_dak_plat)", hist_plat, plat),
                            ("hellend dak (4712 Dakpan beton vs b3_opp_dak_schuin)", hist_schuin, schuin)):
        hv = Decimal(hist[0]) if len(hist) == 1 else None
        comparisons.append({"subject": label, "historical_m2": hist[0] if len(hist) == 1 else hist, "threedbag_m2": str(b3),
                            "difference_m2": str(hv - b3) if hv is not None else None,
                            "difference_pct_of_3dbag": str((((hv - b3) / b3) * 100).quantize(Decimal("0.1"))) if hv is not None and b3 else None})
    return {
        "report_version": "maldenhof_roof_scope_review_v1",
        "building_project_id": "BPRJ-00001", "scope": "EVEN_ONLY",
        "classification": "SCOPE_OR_DEFINITION_MISMATCH_REVIEW",
        "not_a_verdict": "Het verschil is GEEN bewijs dat het MJOP of 3D BAG fout is. Er wordt niets gecorrigeerd: historische "
                         "hoeveelheden en 3D BAG-waarden blijven ongewijzigd en naast elkaar staan.",
        "historical_elements": elements,
        "historical_documents_note": "DOC-005 (2026) en DOC-006 (2023) noemen identieke dakhoeveelheden; afhankelijke bronnen "
                                     "(DREL-002), dus geen onafhankelijke bevestiging.",
        "threedbag_scope": {"bag_pand_count": len(h["bag_pand_ids"]), "b3_opp_dak_plat_sum_m2": str(plat),
                            "b3_opp_dak_schuin_sum_m2": str(schuin), "per_pand": per_pand,
                            "validation_dir": bp.rel(out_dir, root)},
        "comparisons": comparisons,
        "investigated": {
            "element_description": "4711 'Dakbedekking APP', locatie 'Platte dak', eenheid m2 (DOC-005 p7 P07-L013). Eén post voor alle "
                                   "platte daken; het MJOP specificeert niet welke dakdelen (hoofddak, dakkapellen, bergingen, luifels).",
            "location": "'Platte dak' is een verzamellocatie, geen pand- of dakvlakverwijzing.",
            "quantity_unit": "Beide m2; geen eenheidsverschil.",
            "which_roof_parts": "Onbekend uit de bron. Een hellend dak met platte delen (dakkapellen, kopse overgangen) en losse "
                                "bergingen kunnen in één 4711-post zitten.",
            "threedbag_scope": "3D BAG telt per BAG-pand; panden zonder adres (bergingen) vallen buiten de adresgedreven scope van "
                               "BPRJ-00001. De grens plat/schuin in 3D BAG volgt de hellingshoek van gereconstrueerde dakvlakken "
                               "(definitie te verifiëren), niet de dakbedekking.",
            "multiple_roof_types_in_one_post": "Mogelijk; het hellende dak (4712) ligt dicht bij 3D BAG (~5%), het platte dak niet.",
            "exploratory_outbuildings": EXPLORATORY_OUTBUILDINGS,
        },
        "open_questions": [
            "Welke dakdelen omvat post 4711 (425,80 m2): alleen de platte delen van de woningen, ook bergingen/aanbouwen, luifels?",
            "Horen de bergingen zonder adres (aparte BAG-panden) tot de VvE, en zo ja welke (even kant)?",
            "Hoe definieert 3D BAG de grens tussen b3_opp_dak_plat en b3_opp_dak_schuin voor dakkapellen en flauwe dakvlakken?",
        ],
        "corrections_applied": False,
    }


def render_roof(r):
    L = ["# Maldenhof — dak: 3D BAG vs historisch MJOP (v1)", "",
         f"Classificatie: **{r['classification']}**. {r['not_a_verdict']}", "",
         "| Onderwerp | MJOP (m²) | 3D BAG, 15 panden EVEN_ONLY (m²) | Verschil (m²) | % t.o.v. 3D BAG |", "|---|---|---|---|---|"]
    for c in r["comparisons"]:
        L.append(f"| {c['subject']} | {c['historical_m2']} | {c['threedbag_m2']} | {c['difference_m2']} | {c['difference_pct_of_3dbag']} |")
    L += ["", "## Onderzocht", ""]
    for k, v in r["investigated"].items():
        if isinstance(v, dict):
            L.append(f"- **{k}** ({v['status']}): {v['panden']} panden, bouwjaar {v['bouwjaar']}, plat {v['b3_opp_dak_plat_sum_m2']} m². {v['note']}")
        else:
            L.append(f"- **{k}**: {v}")
    L += ["", "## Bron-elementen", ""]
    for e in r["historical_elements"]:
        L.append(f"- {e['element_id']}: `{e['provenance']['text_fragment']}` (p{e['provenance']['page']}, {e['provenance']['block_id']})")
    L += ["", "## Open vragen", ""] + [f"- {q}" for q in r["open_questions"]] + ["", "Er is niets gecorrigeerd.", ""]
    return "\n".join(L)


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def outputs(out_dir=VALIDATION_DIR, root=ROOT):
    disc = build_discovery(out_dir, root)
    roof = build_roof_review(out_dir, root)
    return {OUT_JSON: _dump(disc), OUT_MD: render_discovery(disc), ROOF_JSON: _dump(roof), ROOF_MD: render_roof(roof)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Range discovery v2 (read-only rapportage)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    outs = outputs()
    if args.check:
        stale = [bp.rel(p) for p, c in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != c]
        print("range discovery reports up-to-date" if not stale else "VEROUDERD: " + ", ".join(stale))
        return 1 if stale else 0
    for p, c in outs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(c, encoding="utf-8", newline="\n")
    print("\n".join(bp.rel(p) for p in outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
