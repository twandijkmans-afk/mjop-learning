"""Range-based building project discovery — read-only rapportage over een Real Building Validation-package.

Zie docs/building_projects_v1.md ("Range discovery v2"). Leest:
  - data/external/building_validation/<versie>/candidates/*.json (hash-gecontroleerd via manifest_errors)
  - data/building_projects/{building_project_records,unresolved_case_records,supporting_evidence_records}.json
  - data/verified/DOC-005.json / DOC-006.json (alleen voor de Maldenhof-dakreview)

Schrijft alleen rapporten:
  reports/building_projects/range_discovery_v2.{json,md}   (package real_validation_v2)
  reports/building_projects/range_discovery_v3.{json,md}   (package real_validation_v3, engine v1.4.0)
  reports/building_projects/vechtstraat_confirmation_v1.json      (bevestigingsverzoek; GEEN approval)
  reports/building_projects/alkmaarstraat_candidate_evidence_v1.json
  reports/building_projects/groetstraat_vbo_review_v1.json
  reports/building_projects/st_jacobsstraat_unit_mismatch_v1.json
  reports/quantity/maldenhof_roof_scope_review_v1.{json,md}  (v2)
  reports/quantity/maldenhof_roof_validation_v2.json         (v3, LoD2.2-dakvlakken)

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
V3_DIR = ROOT / "data" / "external" / "building_validation" / "real_validation_v3"
OUT_JSON = ROOT / "reports" / "building_projects" / "range_discovery_v2.json"
OUT_MD = ROOT / "reports" / "building_projects" / "range_discovery_v2.md"
BP_REPORTS = ROOT / "reports" / "building_projects"
DOC001_PDF = ROOT / "data" / "raw" / "alkmaarstraat-1-83" / "9543_vvem_mop_14-01-2022_Pro VVEBeheer B.V._626720.pdf"
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
        "construction_year_class": h.get("construction_year_class"),
        "caveats": h.get("caveats") or [],
        "vbo_detail": h.get("vbo_detail"),
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


def build_discovery(out_dir=VALIDATION_DIR, root=ROOT, report_version=REPORT_VERSION):
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
    return {"report_version": report_version,
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
    L = ["# Range discovery " + rep["report_version"].rsplit("_", 1)[-1], "",
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
            for c in h.get("caveats") or []:
                L.append(f"| ↳ caveat {_md(h['hypothesis_id'])}: `{c}` | | | | | | | | | |")
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


# --- v3: gerichte rapporten ------------------------------------------------------------------------------------

def _pkg(out_dir, gid):
    out_dir = Path(out_dir)
    errs = frbv.manifest_errors(out_dir)
    if errs:
        raise bp.ProjectError("package/manifest niet consistent: " + "; ".join(errs))
    path = out_dir / "candidates" / f"{gid}.json"
    return json.loads(path.read_text(encoding="utf-8")), {
        "validation_dir": bp.rel(out_dir), "candidate_package": {"path": bp.rel(path), "sha256": bp.sha_file(path)},
        "manifest": {"path": bp.rel(out_dir / "manifest.json"), "sha256": bp.sha_file(out_dir / "manifest.json")}}


def _hyp(pkg, hid):
    return next(h for h in pkg["building_project_candidate"]["scope_hypotheses"] if h["hypothesis_id"] == hid)


def _mjop_provenance(pkg):
    return [{"document_id": d["document_id"], "number_of_units": d.get("number_of_units"), "construction_year": d.get("construction_year"),
             "provenance": {k: d["provenance"].get(k) for k in ("number_of_units", "construction_year", "address")},
             "source_sha256": d.get("source_sha256")} for d in pkg["mjop_context"]["documents"]]


def _pand_rows(pkg, hyp):
    tb = {p["bag_pand_id"]: p.get("threedbag") or {} for p in pkg["candidate_panden"]}
    return [{"bag_pand_id": r["bag_pand_id"], "bouwjaar_bag": r["bouwjaar"], "addresses_in_scope": r["addresses_in_scope"],
             "vbo_active": r["aantal_verblijfsobjecten_bag"], "vbo_fully_covered_by_scope": r["vbo_fully_covered_by_scope"],
             "threedbag_ref": {"http_status": tb[r["bag_pand_id"]].get("http_status"),
                               "raw_response_sha256": tb[r["bag_pand_id"]].get("raw_response_sha256")}} for r in hyp["panden"]]


def _expect_args(facts):
    out = []
    for k in list(bp.REQUIRED_EXPECT) + ["construction_year_class"]:
        if k in facts:
            v = facts[k]
            out.append(f"--expect {k}={'none' if v is None else v}")
    return out


def build_vechtstraat_confirmation(out_dir=V3_DIR):
    pkg, prov = _pkg(out_dir, "DOC-013")
    hyp = _hyp(pkg, "REQUESTED_NUMBERS")
    facts = bp.compute_facts(pkg, hyp)
    projects = bp.load_store(bp.PROJECT_STORE, bp.new_project_store)
    return {
        "report_version": "vechtstraat_confirmation_v1",
        "record_type": "BUILDING_PROJECT_CONFIRMATION_REQUEST",
        "status": "PENDING_HUMAN_CONFIRMATION",
        "approval_created": False,
        "building_project_linked": bool(bp.project_for_document(projects, "DOC-013")),
        "candidate_id": pkg["building_project_candidate"]["candidate_id"],
        "document_ids": pkg["document_ids"], "label": pkg["label"],
        "scope_hypothesis_id": hyp["hypothesis_id"], "strength": hyp["strength"],
        "caveats": hyp["caveats"], "construction_year_class": hyp["construction_year_class"],
        "identity_evidence": {
            "mjop_units": hyp["mjop_number_of_units"], "bag_addresses": hyp["counts"]["exact_bag_matches"],
            "bag_addresses_exact_number": hyp["counts"]["exact_number_matches"], "bag_addresses_toevoeging": hyp["counts"]["toevoeging_matches"],
            "vbo_active": hyp["counts"]["vbo_total_bag"], "vbo_gebruiksdoel": hyp["vbo_detail"]["active_gebruiksdoel_counts"],
            "bag_panden": hyp["counts"]["unique_bag_panden"], "geographic_extent_m": hyp["geographic_extent_m"],
            "threedbag_coverage": hyp["threedbag_coverage"], "checks": hyp["checks"]},
        "confirmed_facts_if_approved": facts,
        "panden": _pand_rows(pkg, hyp),
        "addresses": [{"weergavenaam": a["weergavenaam"], "match_kind": a["match_kind"], "nummeraanduiding_id": a["nummeraanduiding_id"],
                       "adresseerbaarobject_id": a["adresseerbaarobject_id"], "bag_pand_ids": a["bag_pand_ids"]} for a in hyp["addresses_found"]],
        "mjop_sources": _mjop_provenance(pkg),
        "questions_for_reviewer": [
            "Accepteer je het bouwjaarverschil 1921 (MJOP) vs 1923 (BAG, alle 3 panden) als niet-conflicterend voor dit project?",
            "Vormen de 3 BAG-panden (Vechtstraat 13, 15+17, 19) samen de VvE van DOC-013?"],
        "approve_command": " ".join(["python scripts/building_projects.py approve --group DOC-013 --scope REQUESTED_NUMBERS",
                                     f"--dir {prov['validation_dir']}", "--reviewer <naam> --reason \"...\" --decision-source \"...\""]
                                    + _expect_args(facts)),
        "provenance": prov,
    }


UNIT_TERMS = ("appartement", "woning", "eenhe", "units", "vhe", "adressen", "breukde", "leden", "appartementsrecht", "omvang")


def scan_pdf_for_unit_terms(path=DOC001_PDF):
    """Zoekt in de volledige tekstlaag van het MJOP naar termen die een aantal eenheden kunnen aangeven.
    Rapporteert alleen letterlijke regels; leidt niets af."""
    import re
    import pdfplumber
    hits = []
    with pdfplumber.open(str(path)) as pdf:
        n = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            for line in (page.extract_text() or "").splitlines():
                low = line.lower()
                if any(t in low for t in UNIT_TERMS) and line.strip() not in {h["line"] for h in hits}:
                    hits.append({"page": i, "line": line.strip(),
                                 "states_a_count": bool(re.search(r"\d+\s*(appartement|woning|eenhe|units|vhe|adressen|leden)", low))})
    return {"pages_scanned": n, "terms": list(UNIT_TERMS), "distinct_lines_with_terms": hits,
            "hits": [h for h in hits if h["states_a_count"]]}


def build_alkmaarstraat_evidence(out_dir=V3_DIR):
    pkg, prov = _pkg(out_dir, "DOC-001")
    bpc = pkg["building_project_candidate"]
    best = bpc["best_supported_hypothesis_id"]
    hyp = _hyp(pkg, best)
    scan = scan_pdf_for_unit_terms()
    explicit = scan["hits"]
    return {
        "report_version": "alkmaarstraat_candidate_evidence_v1",
        "record_type": "BUILDING_PROJECT_CANDIDATE_EVIDENCE", "approval_created": False, "selected_scope": None,
        "candidate_id": bpc["candidate_id"], "document_ids": pkg["document_ids"], "label": pkg["label"],
        "most_supported_hypothesis": {"hypothesis_id": best, "strength": hyp["strength"], "description": hyp["description"],
                                      "addresses": hyp["counts"]["exact_bag_matches"], "vbo_active": hyp["counts"]["vbo_total_bag"],
                                      "vbo_gebruiksdoel": hyp["vbo_detail"]["active_gebruiksdoel_counts"],
                                      "bag_panden": hyp["bag_pand_ids"], "bouwjaren_bag": hyp["bouwjaren_bag"],
                                      "construction_year_class": hyp["construction_year_class"], "checks": hyp["checks"],
                                      "panden": _pand_rows(pkg, hyp)},
        "why_moderate": "MJOP noemt geen aantal eenheden; zonder die identiteitscontrole is STRONG niet mogelijk.",
        "parity_distinction": bpc["parity_distinction"],
        "unit_count_search": {"source": {"path": bp.rel(DOC001_PDF), "sha256": bp.sha_file(DOC001_PDF)}, **scan,
                              "explicit_unit_count_found": bool(explicit),
                              "conclusion": ("Geen expliciet aantal eenheden in de bron; niets afgeleid." if not explicit
                                             else "Expliciete vermelding(en) gevonden; menselijke controle vereist, niets overgenomen.")},
        "indirect_context_not_used": [
            {**h, "note": "Aantal installaties (ventilatie-units), geen aantal woningen/eenheden. Valt samen met het aantal BAG-panden "
                          "in de meest ondersteunde scope (%d), maar wordt NIET als eenhedentelling of pand-telling gebruikt." % len(hyp["bag_pand_ids"])}
            for h in scan["distinct_lines_with_terms"] if "ventilatieunits" in h["line"].lower()],
        "other_hypotheses": {h["hypothesis_id"]: h["strength"] for h in bpc["scope_hypotheses"]},
        "provenance": prov,
    }


def build_groetstraat_vbo_review(out_dir=V3_DIR):
    pkg, prov = _pkg(out_dir, "DOC-015")
    hyp = _hyp(pkg, "ALL_NUMBERS")
    inactive, non_res = [], []
    for r in hyp["panden"]:
        vs = r["vbo_summary"] or {}
        for v in vs.get("inactive_vbos", []):
            inactive.append({"bag_pand_id": r["bag_pand_id"], **v,
                             "type_indication": "voormalige woning (woonfunctie, ingetrokken)" if v["gebruiksdoel"] == "woonfunctie" else "onbekend"})
        for v in vs.get("active_non_woonfunctie", []):
            non_res.append({"bag_pand_id": r["bag_pand_id"], **v,
                            "type_indication": "geen woning; BAG legt niet vast of het een berging, technische ruimte of bedrijfsruimte is"})
    incl = sum(r["aantal_verblijfsobjecten_bag_incl_inactive"] or 0 for r in hyp["panden"])
    return {
        "report_version": "groetstraat_vbo_review_v1", "approval_created": False,
        "candidate_id": pkg["building_project_candidate"]["candidate_id"], "document_ids": pkg["document_ids"],
        "scope_hypothesis_id": "ALL_NUMBERS", "strength_v3": hyp["strength"],
        "counts": {"bag_addresses": hyp["counts"]["exact_bag_matches"], "vbo_bag_incl_inactive": incl,
                   "vbo_active": hyp["counts"]["vbo_total_bag"], "vbo_inactive": len(inactive),
                   "vbo_active_gebruiksdoel": hyp["vbo_detail"]["active_gebruiksdoel_counts"]},
        "explanation": f"31 adressen != {incl} VBO's: pand.aantal_verblijfsobjecten telt ook {len(inactive)} INGETROKKEN VBO's mee "
                       "(Groetstraat 116, 116A en 116B: splitsing en weer samenvoeging; het huidige 116 is een nieuw VBO). "
                       f"Actieve VBO's = {hyp['counts']['vbo_total_bag']} = adressen.",
        "the_three_vbos_without_address": inactive,
        "active_non_residential_vbos_in_scope": non_res,
        "still_open": ["MJOP DOC-015 noemt geen aantal eenheden en geen bouwjaar: geen STRONG mogelijk.",
                       f"{len(non_res)} actieve niet-woonfunctie(s) met adres in scope: horen die bij de VvE?"],
        "parity_distinction": pkg["building_project_candidate"]["parity_distinction"],
        "provenance": prov,
    }


def build_st_jacobsstraat_mismatch(out_dir=V3_DIR):
    pkg, prov = _pkg(out_dir, "DOC-009")
    hyp = _hyp(pkg, "ODD_ONLY")
    found = hyp["addresses_found"]
    ids = [a["adresseerbaarobject_id"] for a in found]
    multi = sorted({i for i in ids if i and ids.count(i) > 1})
    non_res, inactive_all = [], []
    for r in hyp["panden"]:
        vs = r["vbo_summary"] or {}
        non_res += [{"bag_pand_id": r["bag_pand_id"], **v} for v in vs.get("active_non_woonfunctie", [])]
    for p in pkg["candidate_panden"]:
        for v in p.get("verblijfsobjecten") or []:
            if (v.get("properties") or {}).get("status") in frbv.INACTIVE_VBO_STATUSES:
                inactive_all.append({"bag_pand_id": p["bag_pand_id"], "verblijfsobject_id": v["verblijfsobject_id"],
                                     "huisnummer": v["properties"].get("huisnummer"), "status": v["properties"].get("status"),
                                     "in_odd_scope": p["bag_pand_id"] in hyp["bag_pand_ids"]})
    woon = hyp["vbo_detail"]["active_gebruiksdoel_counts"].get("woonfunctie", 0)
    units = hyp["mjop_number_of_units"]
    return {
        "report_version": "st_jacobsstraat_unit_mismatch_v1", "approval_created": False,
        "candidate_id": pkg["building_project_candidate"]["candidate_id"], "document_ids": pkg["document_ids"],
        "scope_hypothesis_id": "ODD_ONLY", "strength_v3": hyp["strength"],
        "street_alias": next((a["street_alias"] for a in pkg["address_results"] if a.get("street_alias")), None),
        "mismatch": {"bag_addresses": len(found), "mjop_units": units, "difference": len(found) - units if units is not None else None},
        "checked": {
            "toevoegingen": hyp["counts"]["toevoeging_matches"],
            "non_residential_vbos": {"count": len(non_res), "items": non_res},
            "multiple_addresses_per_vbo": multi,
            "split_or_merged_units_inactive_vbos": [x for x in inactive_all if x["in_odd_scope"]],
            "inactive_vbos_outside_odd_scope": [x for x in inactive_all if not x["in_odd_scope"]],
            "woonfunctie_vbos": woon,
        },
        "finding": (f"{woon} woonfunctie-VBO's = {units} MJOP-eenheden; de {len(non_res)} overige adressen zijn niet-woonfuncties "
                    "(winkel/industrie/bijeenkomst)." if units is not None and woon == units else
                    "Aantal woonfunctie-VBO's verklaart het verschil niet volledig."),
        "classification": ("MISMATCH_EXPLAINED_BY_NON_RESIDENTIAL_UNITS_PENDING_REVIEW" if units is not None and woon == units
                           else "UNEXPLAINED_UNIT_MISMATCH"),
        "not_decided": ["Vallen de niet-woonfuncties (bedrijfsruimten op de begane grond) buiten de VvE 'Woningen' (DOC-009)?",
                        "DOC-008 ('Hoofddak', zelfde complex) noemt geen plaats of aantal; relatie tot deze scope is open."],
        "other_conflicts": [f for f in hyp["flags"] if f.startswith("CONSTRUCTION_YEAR")],
        "construction_year_class": hyp["construction_year_class"],
        "bouwjaren_per_pand": {r["bag_pand_id"]: r["bouwjaar"] for r in hyp["panden"]},
        "provenance": prov,
    }


# --- Maldenhof: dakvalidatie v2 met LoD2.2-dakvlakken ---------------------------------------------------------------

FLAT_SLOPE_DEG = 5  # alleen voor de indeling in dit rapport; 3D BAG's eigen grens wordt apart getoond (niet aangenomen)


def roof_surfaces(raw, pid):
    """LoD2.2-RoofSurfaces uit een ruwe 3D BAG-respons: oppervlakte (m², 3D), helling (°), hoogte t.o.v. het laagste punt."""
    import math
    f = raw["feature"]
    V, t = f["vertices"], raw["metadata"]["transform"]
    sc, tr = t["scale"], t["translate"]
    out = []
    for co in f["CityObjects"].values():
        for g in co.get("geometry") or []:
            if g["type"] != "Solid" or str(g["lod"]) != "2.2":
                continue
            sem = g["semantics"]
            for si, face in enumerate(g["boundaries"][0]):
                st = sem["values"][0][si]
                if st is None or sem["surfaces"][st]["type"] != "RoofSurface":
                    continue
                ring = [[V[i][k] * sc[k] + tr[k] for k in range(3)] for i in face[0]]
                nx = ny = nz = 0.0
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    nx += (a[1] - b[1]) * (a[2] + b[2])
                    ny += (a[2] - b[2]) * (a[0] + b[0])
                    nz += (a[0] - b[0]) * (a[1] + b[1])
                area = 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
                slope = math.degrees(math.acos(min(1.0, abs(nz) / (2 * area)))) if area else 0.0
                out.append({"area_m2": round(area, 2), "slope_deg": round(slope, 1),
                            "z_min": round(min(p[2] for p in ring), 2), "z_max": round(max(p[2] for p in ring), 2)})
    return sorted(out, key=lambda x: (x["z_min"], x["area_m2"]))


def _raw(out_dir, rel):
    return json.loads((Path(out_dir) / rel).read_text(encoding="utf-8"))


def _centroid(geom):
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    pts = ring[:-1]
    return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))


def _dist_m(a, b):
    import math
    return math.hypot((a[0] - b[0]) * 111320 * math.cos(math.radians((a[1] + b[1]) / 2)), (a[1] - b[1]) * 110540)


def _roof_actions(root):
    """Onderhoudsacties in DOC-005/006 waarvan het element code 4711 of 4712 heeft (letterlijk, met provenance)."""
    def v(x):
        if isinstance(x, dict):
            return x.get("value", x.get("original_value"))
        return x

    def frag(x):
        pr = (x or {}).get("provenance") if isinstance(x, dict) else None
        return {"page": pr.get("page"), "block_id": pr.get("block_id"), "text_fragment": pr.get("text_fragment")} if pr else None
    out = []
    for d in ("DOC-005", "DOC-006"):
        j = json.loads((Path(root) / "data" / "verified" / f"{d}.json").read_text(encoding="utf-8"))
        codes = {e["element_id"]: e["element_code"]["original_value"] for e in j["elements"]}
        for a in j["maintenance_actions"]:
            code = codes.get(a.get("element_id"))
            if code in ("4711", "4712"):
                out.append({"document_id": d, "action_id": a["action_id"], "element_id": a["element_id"], "element_code": code,
                            "action": v(a.get("action")), "quantity": v(a.get("quantity")), "unit": v(a.get("unit")),
                            "planned_year": v(a.get("planned_year")), "provenance": frag(a.get("action"))})
    return out


def build_roof_validation(out_dir=V3_DIR, root=ROOT):
    pkg, prov = _pkg(out_dir, "DOC-005-006")
    hyp = _hyp(pkg, "EVEN_ONLY")
    cand = {p["bag_pand_id"]: p for p in pkg["candidate_panden"]}
    per_pand, s_plat, s_schuin, lod_flat, lod_sloped = [], Decimal(0), Decimal(0), Decimal(0), Decimal(0)
    for pid in hyp["bag_pand_ids"]:
        tb = cand[pid]["threedbag"]
        a = tb["attributes"] or {}
        surf = roof_surfaces(_raw(out_dir, tb["raw_response_path"]), pid)
        flat = [x for x in surf if x["slope_deg"] < FLAT_SLOPE_DEG]
        s_plat += _dec(a.get("b3_opp_dak_plat"))
        s_schuin += _dec(a.get("b3_opp_dak_schuin"))
        lod_flat += sum((Decimal(str(x["area_m2"])) for x in flat), Decimal(0))
        lod_sloped += sum((Decimal(str(x["area_m2"])) for x in surf if x["slope_deg"] >= FLAT_SLOPE_DEG), Decimal(0))
        per_pand.append({"bag_pand_id": pid, "house_numbers": next(r["numbers_in_scope"] for r in hyp["panden"] if r["bag_pand_id"] == pid),
                         "b3_opp_dak_plat": a.get("b3_opp_dak_plat"), "b3_opp_dak_schuin": a.get("b3_opp_dak_schuin"),
                         "b3_dak_type": a.get("b3_dak_type"), "lod22_roof_surfaces": surf,
                         "low_flat_parts_m2": str(sum((Decimal(str(x["area_m2"])) for x in flat if x["z_max"] < 6), Decimal(0))),
                         "high_flat_parts_m2": str(sum((Decimal(str(x["area_m2"])) for x in flat if x["z_max"] >= 6), Decimal(0))),
                         "raw_response_sha256": tb["raw_response_sha256"]})
    # context: panden zonder adres; indicatieve toewijzing aan het dichtstbijzijnde kandidaat-pand (GEEN eigendom)
    ctx = pkg.get("context_panden_without_vbo") or {"panden": []}
    man = json.loads((Path(out_dir) / "manifest.json").read_text(encoding="utf-8"))
    req = next(r for r in man["requests"] if r["request_id"] == ctx.get("bag_request_id"))
    cen = {f["properties"]["identificatie"]: _centroid(f["geometry"]) for f in _raw(out_dir, req["raw_response_path"])["features"]}
    even = set(hyp["bag_pand_ids"])
    ctx_rows, near_even = [], Decimal(0)
    for c in ctx["panden"]:
        a = (c.get("threedbag") or {}).get("attributes") or {}
        near = min((x for x in cand if x in cen), key=lambda x: _dist_m(cen[c["bag_pand_id"]], cen[x]))
        side = "EVEN_ONLY" if near in even else "OTHER"
        if side == "EVEN_ONLY" and a.get("b3_opp_dak_plat") is not None:
            near_even += _dec(a["b3_opp_dak_plat"])
        ctx_rows.append({"bag_pand_id": c["bag_pand_id"], "bouwjaar": c["bag_properties"]["bouwjaar"],
                         "b3_opp_dak_plat": a.get("b3_opp_dak_plat"), "b3_opp_dak_schuin": a.get("b3_opp_dak_schuin"),
                         "threedbag_http_status": (c.get("threedbag") or {}).get("http_status"),
                         "nearest_candidate_pand": near, "nearest_is_in_even_scope": side == "EVEN_ONLY",
                         "distance_m": round(_dist_m(cen[c["bag_pand_id"]], cen[near]), 1)})
    ctx_plat = sum((_dec(r["b3_opp_dak_plat"]) for r in ctx_rows if r["b3_opp_dak_plat"] is not None), Decimal(0))
    ctx_schuin = sum((_dec(r["b3_opp_dak_schuin"]) for r in ctx_rows if r["b3_opp_dak_schuin"] is not None), Decimal(0))
    elements = _element_facts(root)
    actions = _roof_actions(root)
    hist = {code: sorted({e["quantity"] for e in elements if e["element_code"] == code}) for code in ("4711", "4712")}
    h_schuin, h_plat = Decimal(hist["4712"][0]), Decimal(hist["4711"][0])

    def pct(a, b):
        return str(((a - b) / b * 100).quantize(Decimal("0.1")))
    return {
        "report_version": "maldenhof_roof_validation_v2", "pilot": "quantity_validation_pilot_1",
        "building_project_id": "BPRJ-00001", "scope": "EVEN_ONLY", "corrections_applied": False,
        "rule": "Geen correctie van historische hoeveelheid of 3D BAG. Classificatie per onderwerp: "
                "GEOMETRY_SUPPORTS_HISTORICAL_QUANTITY | SCOPE_MISMATCH | DEFINITION_MISMATCH | UNRESOLVED.",
        "A_sloped_roof": {
            "mjop": {"elements": [e for e in elements if e["element_code"] == "4712"],
                     "actions": [a for a in actions if a["element_code"] == "4712"],
                     "actions_note": "Geen onderhoudsacties met element 4712 in DOC-005/DOC-006 (binnen het planvenster).",
                     "element_description": "4712 Dakpan beton", "location": "Hellend dak", "material": "beton (dakpan), uit elementnaam",
                     "quantity_m2": str(h_schuin)},
            "threedbag": {"b3_opp_dak_schuin_sum_m2": str(s_schuin), "lod22_surfaces_ge_%d_deg_sum_m2" % FLAT_SLOPE_DEG: str(lod_sloped),
                          "contributing_panden": len(per_pand), "context_panden_without_address_sloped_m2": str(ctx_schuin)},
            "difference_m2": str(h_schuin - s_schuin), "difference_pct_of_3dbag": pct(h_schuin, s_schuin),
            "classification": "GEOMETRY_SUPPORTS_HISTORICAL_QUANTITY",
            "basis": ["Zelfde onderwerp en eenheid (hellend dak, m2).",
                      "Alle 15 panden dragen bij (steile dakvlakken ~52°); panden zonder adres in de omgeving hebben 0 m2 hellend dak, "
                      "dus er is geen hellend dak buiten de scope dat het MJOP kan bevatten.",
                      "MJOP ligt 4,9% hoger dan 3D BAG; mogelijke oorzaken (dakoverstek, meetmethode) zijn niet geverifieerd."],
        },
        "B_flat_roof": {
            "mjop": {"elements": [e for e in elements if e["element_code"] == "4711"],
                     "actions": [a for a in actions if a["element_id"].endswith("EL-025")],
                     "related_actions_same_code": [a for a in actions if a["element_code"] == "4711" and not a["element_id"].endswith("EL-025")],
                     "element_description": "4711 Dakbedekking APP", "location": "Platte dak (verzamellocatie)",
                     "material": "APP (bitumineus), uit elementnaam", "quantity_m2": str(h_plat)},
            "threedbag": {"b3_opp_dak_plat_sum_15_panden_m2": str(s_plat),
                          "lod22_surfaces_lt_%d_deg_sum_m2" % FLAT_SLOPE_DEG: str(lod_flat),
                          "context_panden_without_address": {"count": len(ctx_rows), "b3_opp_dak_plat_sum_m2": str(ctx_plat),
                                                             "nearest_to_even_scope_count": sum(1 for r in ctx_rows if r["nearest_is_in_even_scope"]),
                                                             "nearest_to_even_scope_plat_m2": str(near_even),
                                                             "assignment": "INDICATIVE_NEAREST_PAND_NOT_OWNERSHIP"}},
            "scenarios_m2": {"15_panden_only": str(s_plat), "15_panden_plus_nearest_even_outbuildings": str(s_plat + near_even),
                             "15_panden_plus_all_outbuildings": str(s_plat + ctx_plat)},
            "components": {
                "SCOPE_MISMATCH": "aannemelijk maar onbewezen: bergingen zonder adres (aparte BAG-panden, 1981, plat) vallen buiten de "
                                  "adresgedreven scope; toewijzing aan de VvE onbekend.",
                "DEFINITION_MISMATCH": "klein: 3D BAG rekent flauwe vlakken (~3,7-3,9°) tot schuin; de platte delen van de woningen liggen "
                                       "laag (aanbouw/luifel ~1,2-1,7 m en ~4,4 m), op één pand na geen dakkapel-achtige platte delen hoog in het dak.",
            },
            "classification": "UNRESOLVED",
            "basis": [f"Ook met alle nabije bergingen aan de even kant ({s_plat + near_even} m2) blijft {h_plat - s_plat - near_even} m2 onverklaard.",
                      "De MJOP-post specificeert niet welke platte daken erin zitten."],
        },
        "context_elements": [e for e in _element_facts_all_roof(root) if e["element_code"] not in ("4711", "4712")],
        "per_pand": per_pand, "context_panden": ctx_rows,
        "open_questions": ["Welke platte daken omvat 4711 (woningen, bergingen, luifels, galerij)? Vraag de opsteller/inspectietekening.",
                           "Horen de bergingen zonder adres tot de VvE (splitsingsakte)?"],
        "provenance": prov,
    }


def _element_facts_all_roof(root):
    out = []
    for d in ("DOC-005",):
        j = json.loads((Path(root) / "data" / "verified" / f"{d}.json").read_text(encoding="utf-8"))
        for e in j["elements"]:
            loc = (e.get("location") or {}).get("value") or ""
            if "dak" in loc.lower():
                prov = e["element_code"]["provenance"]
                out.append({"element_id": e["element_id"], "element_code": e["element_code"]["original_value"],
                            "element_name": e["element_name"]["value"], "location": loc,
                            "quantity": (e.get("quantity") or {}).get("value"), "text_fragment": prov["text_fragment"], "page": prov["page"]})
    return out


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def outputs(out_dir=VALIDATION_DIR, root=ROOT):
    disc = build_discovery(out_dir, root)
    roof = build_roof_review(out_dir, root)
    d3 = build_discovery(V3_DIR, root, report_version="range_discovery_v3")
    return {OUT_JSON: _dump(disc), OUT_MD: render_discovery(disc), ROOF_JSON: _dump(roof), ROOF_MD: render_roof(roof),
            BP_REPORTS / "range_discovery_v3.json": _dump(d3), BP_REPORTS / "range_discovery_v3.md": render_discovery(d3),
            BP_REPORTS / "vechtstraat_confirmation_v1.json": _dump(build_vechtstraat_confirmation()),
            BP_REPORTS / "alkmaarstraat_candidate_evidence_v1.json": _dump(build_alkmaarstraat_evidence()),
            BP_REPORTS / "groetstraat_vbo_review_v1.json": _dump(build_groetstraat_vbo_review()),
            BP_REPORTS / "st_jacobsstraat_unit_mismatch_v1.json": _dump(build_st_jacobsstraat_mismatch()),
            ROOT / "reports" / "quantity" / "maldenhof_roof_validation_v2.json": _dump(build_roof_validation(V3_DIR, root))}


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
