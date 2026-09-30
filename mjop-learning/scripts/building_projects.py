"""Building projects v1 — logisch building_project (VvE/complex) <-> MEERDERE BAG-panden, alleen door een mens goedgekeurd.

Zie docs/building_projects_v1.md. Bron: het candidate package van Real Building Validation v1
(data/external/building_validation/real_validation_v1, scripts/fetch_real_building_validation.py).

  python scripts/building_projects.py approve --group DOC-005-006 --scope EVEN_ONLY --reviewer twandijkmans \
      --reason "..." --expect pand_count=15 --expect address_count=29 ...
  python scripts/building_projects.py unresolved --group DOC-012 --focus ODD_ONLY --recorded-by ... --reason "..."
  python scripts/building_projects.py check | guard --out DIR

Regels:
- Eén building_project is één logische VvE/complex en verwijst naar alle bijbehorende BAG-panden; geen enkel pand
  is 'het gebouw'. Er is geen veld voor één pand.
- Goedkeuren kan alleen met een menselijke reviewer + reden, alleen voor een STRONG kandidaat waarvan de
  candidate-package-hashes kloppen, en alleen als de door de mens bevestigde feiten (--expect) exact overeenkomen
  met wat het package aantoont. Anders weigert het script.
- 3D BAG blijft evidence (alleen verwijzing + hash); niets wordt vertaald naar hoeveelheden of crosswalk.
- legal_vve wordt niet geschreven tenzij die onafhankelijk uit bestaande data eenduidig bekend is; anders OPEN.
- Niet-opgeloste gevallen krijgen één compact unresolved-case record; er wordt dan geen building_project geschreven.
- Beide stores zijn append-only (scripts/append_only_store.py). De legacy building_link- en crosswalk-stores en
  alle canonical MJOP-/prijsdata blijven onaangeroerd. building_link (legacy) = één document <-> één BAG-pand via een
  BAGSNAP-snapshot; building_project = logisch project met 1..n BAG-panden. Dat zijn verschillende concepten;
  er is bewust geen compatibiliteitslaag.
- Onveranderlijk bewijs: een evidence package (validation_dir) dat door een building_project-record wordt gerefereerd,
  mag nooit meer worden overschreven of verwijderd ('guard' faalt hard). Nieuwe fetches gaan naar een nieuwe
  versiemap (bv. real_validation_v3).
"""

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import append_only_store as aos  # noqa: E402
import fetch_real_building_validation as frbv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VALIDATION_DIR = ROOT / "data" / "external" / "building_validation" / "real_validation_v1"
PROJECT_STORE = ROOT / "data" / "building_projects" / "building_project_records.json"
UNRESOLVED_STORE = ROOT / "data" / "building_projects" / "unresolved_case_records.json"
SUPPORT_STORE = ROOT / "data" / "building_projects" / "supporting_evidence_records.json"
DOC_RELATIONS = ROOT / "data" / "price_observations" / "document_relations.json"

RULE_VERSION = "building_project_rules_v1"
STRONG = "STRONG_BUILDING_PROJECT_CANDIDATE"
SAME_OBJECT_RELATION_TYPES = {"duplicate_source", "version_of_same_mjop", "same_building_other_inspection"}
REQUIRED_EXPECT = ("pand_count", "address_count", "vbo_total", "number_of_units", "construction_year", "missing_addresses",
                   "panden_sharing_numbers_outside_scope")
LEGAL_ID_KEYS = ("kvk", "kvk_number", "kvk_nummer", "legal_vve_id", "rsin")


class ProjectError(RuntimeError):
    pass


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path, root=ROOT):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------
# Stores (append-only)
# --------------------------------------------------------------------------

def new_project_store():
    return {"store_version": "building_project_v1", "append_only": True,
            "description": "Door een mens goedgekeurde logische building_projects (VvE/complex) met alle bijbehorende BAG-panden "
                           "(docs/building_projects_v1.md). Append-only; één ACTIVE record per candidate_id. Geen pand is 'het gebouw'.",
            "records": []}


def new_unresolved_store():
    return {"store_version": "building_project_unresolved_v1", "append_only": True,
            "description": "Compacte records van niet-opgeloste building_project-kandidaten (nog geen link, geen gekozen scope). "
                           "Append-only; één ACTIVE record per case_key.",
            "records": []}


def new_support_store():
    return {"store_version": "building_project_supporting_evidence_v1", "append_only": True,
            "description": "Machinale controles dat een nieuwer evidence package een bestaand goedgekeurd building_project exact "
                           "reproduceert (rol SUPPORTING_EVIDENCE). Geen goedkeuring; wijzigt nooit een building_project-record. "
                           "Append-only; één ACTIVE record per evidence_key.",
            "records": []}


def load_store(path, factory):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else factory()


def project_store_errors(store):
    errs = aos.invariant_errors(store["records"], "building_project_id", lambda r: r["candidate_id"])
    seen = {}
    for r in store["records"]:
        if r["status"] != "ACTIVE":
            continue
        for pid in r["bag_pand_ids"]:
            if pid in seen and seen[pid] != r["building_project_id"]:
                errs.append(f"pand {pid} zit in meerdere ACTIVE building_projects ({seen[pid]}, {r['building_project_id']})")
            seen[pid] = r["building_project_id"]
    return errs


def unresolved_store_errors(store):
    return aos.invariant_errors(store["records"], "case_id", lambda r: r["case_key"])


def support_store_errors(store):
    return aos.invariant_errors(store["records"], "evidence_id", lambda r: r["evidence_key"])


def write_store(store, path, factory, errors_fn, id_field):
    path = Path(path)
    old = load_store(path, factory)
    errs = errors_fn(store) + aos.append_only_errors(old["records"], store["records"], id_field)
    if errs:
        raise ProjectError("; ".join(errs))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def active_projects(store):
    return [r for r in store["records"] if r["status"] == "ACTIVE"]


# --------------------------------------------------------------------------
# Candidate package inlezen (met hashcontrole)
# --------------------------------------------------------------------------

def load_package(out_dir, group_id, root=ROOT):
    out_dir = Path(out_dir)
    errs = frbv.manifest_errors(out_dir)
    if errs:
        raise ProjectError("candidate package/manifest niet consistent: " + "; ".join(errs))
    pkg_path, man_path = out_dir / "candidates" / f"{group_id}.json", out_dir / "manifest.json"
    if not pkg_path.exists():
        raise ProjectError(f"geen candidate package voor {group_id} in {out_dir}")
    pkg, manifest = json.loads(pkg_path.read_text(encoding="utf-8")), json.loads(man_path.read_text(encoding="utf-8"))
    prov = {"validation_dir": rel(out_dir, root),
            "candidate_package": {"path": rel(pkg_path, root), "sha256": sha_file(pkg_path), "candidate_id": pkg["building_project_candidate"]["candidate_id"],
                                  "package_version": pkg["package_version"], "run_id": pkg["run_id"]},
            "manifest": {"path": rel(man_path, root), "sha256": sha_file(man_path), "run_id": manifest["run_id"], "tool": manifest["tool"]},
            "raw_response_count": sum(1 for r in manifest["requests"] if r["raw_response_path"])}
    return pkg, manifest, prov


def get_hypothesis(pkg, hypothesis_id):
    h = next((x for x in pkg["building_project_candidate"]["scope_hypotheses"] if x["hypothesis_id"] == hypothesis_id), None)
    if h is None:
        raise ProjectError(f"onbekende scope-hypothese {hypothesis_id}")
    return h


def compute_facts(pkg, hyp):
    years = sorted({r["bouwjaar"] for r in hyp["panden"]})
    mjop = pkg["mjop_context"]["combined"]
    return {
        "pand_count": len(hyp["bag_pand_ids"]),
        "address_count": len(hyp["addresses_found"]),
        "vbo_total": hyp["counts"]["vbo_total_bag"],
        "number_of_units": hyp["mjop_number_of_units"],
        "construction_year": years[0] if len(years) == 1 and years[0] == mjop.get("construction_year") else None,
        "missing_addresses": len(hyp["addresses_missing"]),
        "panden_sharing_numbers_outside_scope": sum(1 for r in hyp["panden"] if r["numbers_queried_outside_scope"]),
    }


def related_documents_not_linked(document_ids, relations_path=DOC_RELATIONS):
    if not Path(relations_path).exists():
        return []
    out = []
    for r in json.loads(Path(relations_path).read_text(encoding="utf-8"))["relations"]:
        ids = r.get("document_ids") or [r.get("primary_document_id"), r.get("secondary_document_id")]
        if r["type"] in SAME_OBJECT_RELATION_TYPES and set(ids) & set(document_ids):
            for o in ids:
                if o not in document_ids:
                    out.append({"document_id": o, "relation_id": r["relation_id"], "type": r["type"],
                                "note": "zelfde object volgens documentrelatie; valt buiten dit besluit en is niet gekoppeld"})
    return sorted(out, key=lambda x: (x["document_id"], x["relation_id"]))


def legal_vve_status(document_ids, root=ROOT, relations_path=DOC_RELATIONS):
    """legal_vve blijft OPEN tenzij een juridische identifier (KvK/RSIN) onafhankelijk in bestaande data staat."""
    found = {}
    for layer in ("verified", "extracted", "normalized"):
        for d in document_ids:
            p = Path(root) / "data" / layer / f"{d}.json"
            if p.exists():
                text = p.read_text(encoding="utf-8").lower()
                for k in LEGAL_ID_KEYS:
                    if f'"{k}"' in text:
                        found.setdefault(d, []).append(k)
    excerpts = []
    if Path(relations_path).exists():
        for r in json.loads(Path(relations_path).read_text(encoding="utf-8"))["relations"]:
            ids = r.get("document_ids") or [r.get("primary_document_id"), r.get("secondary_document_id")]
            if r["type"] == "version_of_same_mjop" and set(ids) <= set(document_ids):
                excerpts.append({"relation_id": r["relation_id"], "evidence": r.get("evidence")})
    if found:
        raise ProjectError(f"juridische identifier gevonden in bestaande data ({found}); legal_vve-koppeling vereist een apart besluit")
    return {"status": "OPEN", "linked_legal_vve_id": None,
            "reason": "Geen juridische VvE-identifier (KvK/RSIN) in bestaande data; alleen de objectnaam en administratieve codes uit het MJOP "
                      "(klantcode, objectcode) zijn bekend. Dat zijn codes van de opsteller van het MJOP, geen juridische identifiers.",
            "identifiers_seen_are_not_legal": excerpts}


# --------------------------------------------------------------------------
# Goedkeuren
# --------------------------------------------------------------------------

def approve_building_project(store, *, out_dir, group_id, hypothesis_id, reviewer_id, reason, decided_at, expect,
                             decision_source, root=ROOT, relations_path=DOC_RELATIONS):
    """Pure functie: geeft een nieuwe store terug met één extra ACTIVE building_project. Weigert zonder menselijke
    reviewer/reden, bij niet-STRONG of gewijzigde kandidaat, bij afwijkende bevestigde feiten en bij pand-overlap."""
    if not reviewer_id or not str(reviewer_id).strip():
        raise ProjectError("reviewer is verplicht (goedkeuren is altijd een menselijk besluit)")
    if not reason or not str(reason).strip():
        raise ProjectError("reden is verplicht")
    missing_keys = [k for k in REQUIRED_EXPECT if k not in (expect or {})]
    if missing_keys:
        raise ProjectError("bevestigde feiten ontbreken: " + ", ".join(missing_keys))
    pkg, manifest, prov = load_package(out_dir, group_id, root)
    bpc = pkg["building_project_candidate"]
    if pkg["status"] != "CANDIDATE_UNREVIEWED" or pkg["approval"]["building_link_approved"] or bpc["canonical_building_project_written"]:
        raise ProjectError("candidate package is niet meer in de ongereviewde uitgangstoestand")
    hyp = get_hypothesis(pkg, hypothesis_id)
    if hyp["strength"] != STRONG:
        raise ProjectError(f"scope {hypothesis_id} is {hyp['strength']}; alleen {STRONG} kan worden goedgekeurd")
    facts = compute_facts(pkg, hyp)
    diffs = {k: (expect[k], facts[k]) for k in REQUIRED_EXPECT if expect[k] != facts[k]}
    if diffs:
        raise ProjectError("bevestigde feiten wijken af van het candidate package: " + json.dumps(diffs))
    out = copy.deepcopy(store)
    previous = [r for r in out["records"] if r["candidate_id"] == bpc["candidate_id"] and r["status"] in ("ACTIVE", "REVIEW_REQUIRED")]
    if len(previous) > 1:
        raise ProjectError("meer dan één geldend record voor deze kandidaat")
    prev_ids = {r["building_project_id"] for r in previous}
    for r in out["records"]:
        if r["status"] == "ACTIVE" and r["building_project_id"] not in prev_ids:
            clash = sorted(set(r["bag_pand_ids"]) & set(hyp["bag_pand_ids"]))
            if clash:
                raise ProjectError(f"panden {clash} horen al bij building_project {r['building_project_id']}")
    threed = {p["bag_pand_id"]: p["threedbag"] for p in pkg["candidate_panden"]}
    panden = []
    for r in hyp["panden"]:
        tb = threed.get(r["bag_pand_id"]) or {}
        panden.append({"bag_pand_id": r["bag_pand_id"], "house_numbers": r["numbers_in_scope"],
                       "aantal_verblijfsobjecten_bag": r["aantal_verblijfsobjecten_bag"], "bouwjaar_bag": r["bouwjaar"],
                       "threedbag_evidence_ref": {"evidence_only": True, "http_status": tb.get("http_status"),
                                                  "raw_response_path": tb.get("raw_response_path"),
                                                  "raw_response_sha256": tb.get("raw_response_sha256")}})
    mjop = pkg["mjop_context"]["combined"]
    addresses = [{"house_number": a["number"], "weergavenaam": a["weergavenaam"], "nummeraanduiding_id": a["nummeraanduiding_id"],
                  "adresseerbaarobject_id": a["adresseerbaarobject_id"], "bag_pand_id": a["bag_pand_ids"][0]} for a in hyp["addresses_found"]]
    record = {
        "building_project_id": aos.next_id(out["records"], "building_project_id", "BPRJ"),
        "candidate_id": bpc["candidate_id"],
        "project_status": "APPROVED",
        "selected_scope": hypothesis_id,
        "label": pkg["label"],
        "document_ids": pkg["document_ids"],
        "scope": {"hypothesis_id": hypothesis_id, "description": hyp["description"], "basis": hyp["basis"],
                  "street": pkg["address_results"][0]["street"], "city": mjop.get("city"), "postcode_of_document_address": mjop.get("postcode"),
                  "house_numbers": hyp["requested_numbers"]},
        "bag_pand_ids": sorted(hyp["bag_pand_ids"]),
        "bag_pand_count": len(hyp["bag_pand_ids"]),
        "panden": panden,
        "addresses": addresses,
        "totals": {"addresses": facts["address_count"], "vbo_total_bag": facts["vbo_total"], "bag_panden": facts["pand_count"],
                   "mjop_number_of_units": facts["number_of_units"]},
        "mjop_context": {"address": mjop.get("address"), "object_name": mjop.get("object_name"), "number_of_units": mjop.get("number_of_units"),
                         "construction_year": mjop.get("construction_year"), "postcode": mjop.get("postcode"), "city": mjop.get("city"),
                         "documents": [{"document_id": d["document_id"], "source_sha256": d.get("source_sha256"),
                                        "source_relative_path": d.get("source_relative_path")} for d in pkg["mjop_context"]["documents"]]},
        "approval": {"decision": "APPROVED", "scope_hypothesis_id": hypothesis_id,
                     "reviewer": {"reviewer_id": reviewer_id, "reviewer_type": "human"}, "decided_at": decided_at,
                     "decision_reason": reason, "decision_source": decision_source, "confirmed_facts": facts},
        "legal_vve": legal_vve_status(pkg["document_ids"], root, relations_path),
        "evidence_policy": {"threedbag": "EVIDENCE_ONLY", "translated_to_quantities": False, "crosswalk_written": False,
                            "legacy_building_link_store_written": False},
        "provenance": prov,
        "related_documents_not_linked": related_documents_not_linked(pkg["document_ids"], relations_path),
        "rule_version": RULE_VERSION,
        "supersedes": previous[0]["building_project_id"] if previous else None,
        "status": "ACTIVE",
    }
    for r in previous:
        r["status"] = "SUPERSEDED"
    out["records"].append(record)
    errs = project_store_errors(out) + aos.append_only_errors(store["records"], out["records"], "building_project_id")
    if errs:
        raise ProjectError("; ".join(errs))
    return out


# --------------------------------------------------------------------------
# Supporting evidence: nieuwer package reproduceert een goedgekeurd project
# --------------------------------------------------------------------------

def _canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def reproduction_diff(project, hyp):
    """Vergelijkt een goedgekeurd building_project met een scope-hypothese uit een (nieuwer) package.
    -> dict met per onderdeel (gelijk, oud, nieuw); leeg 'differences' = exacte reproductie."""
    old_addr = sorted((a["house_number"], a["nummeraanduiding_id"], a["adresseerbaarobject_id"], a["bag_pand_id"]) for a in project["addresses"])
    new_addr = sorted((a["number"], a["nummeraanduiding_id"], a["adresseerbaarobject_id"], (a["bag_pand_ids"] or [None])[0])
                      for a in hyp["addresses_found"])
    old_pp = {r["bag_pand_id"]: sorted(r["house_numbers"]) for r in project["panden"]}
    new_pp = {r["bag_pand_id"]: sorted(str(n) for n in r["numbers_in_scope"]) for r in hyp["panden"]}
    parts = {
        "bag_pand_ids": (sorted(project["bag_pand_ids"]), sorted(hyp["bag_pand_ids"])),
        "addresses": (old_addr, new_addr),
        "house_numbers_per_pand": (old_pp, new_pp),
        "vbo_total_bag": (project["totals"]["vbo_total_bag"], hyp["counts"]["vbo_total_bag"]),
        "scope_house_numbers": (sorted(project["scope"]["house_numbers"]), sorted(str(n) for n in hyp["requested_numbers"])),
    }
    return {"compared": {k: v[0] == v[1] for k, v in parts.items()},
            "differences": {k: {"approved": v[0], "new": v[1]} for k, v in parts.items() if v[0] != v[1]}}


def record_reproduction(store, *, project_store, building_project_id, out_dir, group_id, hypothesis_id, recorded_by, recorded_at,
                        decision_source, root=ROOT):
    """Pure functie: legt vast dat een nieuwer candidate package het goedgekeurde building_project EXACT reproduceert
    (rol SUPPORTING_EVIDENCE). Weigert (ProjectError met het verschil) bij elk verschil: geen stille supersede, geen
    nieuwe approval, en het building_project-record wordt nooit gewijzigd."""
    if not recorded_by or not str(recorded_by).strip():
        raise ProjectError("recorded_by is verplicht")
    project = next((r for r in project_store["records"] if r["building_project_id"] == building_project_id), None)
    if project is None:
        raise ProjectError(f"onbekend building_project {building_project_id}")
    if project["status"] != "ACTIVE":
        raise ProjectError(f"{building_project_id} is niet ACTIVE ({project['status']})")
    if project["selected_scope"] != hypothesis_id:
        raise ProjectError(f"{building_project_id} heeft scope {project['selected_scope']}, niet {hypothesis_id}")
    pkg, manifest, prov = load_package(out_dir, group_id, root)
    if prov["validation_dir"] == project["provenance"]["validation_dir"]:
        raise ProjectError("dit is het evidence package van de goedkeuring zelf, geen nieuw bewijs")
    if pkg["building_project_candidate"]["candidate_id"] != project["candidate_id"] or sorted(pkg["document_ids"]) != sorted(project["document_ids"]):
        raise ProjectError("package hoort bij een andere kandidaat of andere documenten")
    hyp = get_hypothesis(pkg, hypothesis_id)
    diff = reproduction_diff(project, hyp)
    if diff["differences"]:
        raise ProjectError(f"nieuwe resolver reproduceert {building_project_id} NIET exact; niets vastgelegd: " + json.dumps(diff["differences"]))
    key = f"{building_project_id}:{prov['validation_dir']}:{hypothesis_id}"
    if any(r["evidence_key"] == key and r["status"] == "ACTIVE" for r in store["records"]):
        raise ProjectError(f"reproductie {key} is al vastgelegd")
    record = {
        "evidence_id": aos.next_id(store["records"], "evidence_id", "BPEV"),
        "evidence_key": key,
        "building_project_id": building_project_id,
        "candidate_id": project["candidate_id"],
        "document_ids": project["document_ids"],
        "evidence_role": "SUPPORTING_EVIDENCE",
        "result": "REPRODUCES_APPROVED_SCOPE",
        "scope_hypothesis_id": hypothesis_id,
        "candidate_strength_in_new_package": hyp["strength"],
        "compared": diff["compared"],
        "project_record_sha256": _canonical_sha(project),
        "approval_changed": False,
        "new_approval_created": False,
        "resolver": {"tool": manifest["tool"], "run_id": manifest["run_id"]},
        "provenance": prov,
        "recorded_by": {"recorder_id": recorded_by, "recorder_type": "claude_code"},
        "recorded_at": recorded_at,
        "decision_source": decision_source,
        "rule_version": RULE_VERSION,
        "supersedes": None,
        "status": "ACTIVE",
    }
    out = copy.deepcopy(store)
    out["records"].append(record)
    errs = support_store_errors(out) + aos.append_only_errors(store["records"], out["records"], "evidence_id")
    if errs:
        raise ProjectError("; ".join(errs))
    return out


# --------------------------------------------------------------------------
# Unresolved case
# --------------------------------------------------------------------------

def _req(manifest, request_id):
    return next((r for r in manifest["requests"] if r["request_id"] == request_id), None)


def _ref(manifest, request_id):
    r = _req(manifest, request_id) or {}
    return {"request_id": request_id, "raw_response_path": r.get("raw_response_path"), "raw_response_sha256": r.get("raw_response_sha256")}


def record_unresolved_case(store, *, out_dir, group_id, focus_hypothesis_id, recorded_by, reason, recorded_at, decision_source,
                           projects_store=None, root=ROOT):
    """Pure functie: één compact unresolved-case record. Kiest geen scope en schrijft geen building_project."""
    if not recorded_by or not reason or not str(reason).strip():
        raise ProjectError("recorded_by en reden zijn verplicht")
    pkg, manifest, prov = load_package(out_dir, group_id, root)
    bpc = pkg["building_project_candidate"]
    if any(set(pkg["document_ids"]) & set(r["document_ids"]) for r in active_projects(projects_store or new_project_store())):
        raise ProjectError("document is al aan een building_project gekoppeld; geen unresolved case")
    hyp = get_hypothesis(pkg, focus_hypothesis_id)
    mjop = pkg["mjop_context"]["combined"]
    obs = {o["field"]: o for o in pkg["mjop_context"]["source_observations"]}
    ar = {a["number"]: a for a in pkg["address_results"]}
    points = []
    for n in hyp["addresses_missing"]:
        points.append({"point_id": "ADDRESS_MISSING_IN_BAG", "statement": f"Huisnummer {n} ligt in het MJOP-bereik maar heeft geen exact adres in de BAG.",
                       "evidence": {"number": n, "locatieserver": _ref(manifest, ar[n]["pdok_request_id"])}})
    for r in hyp["panden"]:
        extra = [d for d in (r["vbo_without_matched_address_details"] or []) if d.get("outside_requested_number_range")]
        if extra:
            nums = sorted(int(n) for n in r["numbers_in_scope"])
            points.append({"point_id": "PAND_SPANS_BEYOND_RANGE",
                           "statement": f"Pand {r['bag_pand_id']} bevat {len(nums)} adressen in scope ({nums[0]}-{nums[-1]}, {focus_hypothesis_id}) plus "
                                        f"VBO(s) buiten het bereik: " + ", ".join(f"{d['huisnummer']}{d['huisletter'] or ''} ({d['postcode']})" for d in extra),
                           "evidence": {"bag_pand_id": r["bag_pand_id"], "aantal_verblijfsobjecten_bag": r["aantal_verblijfsobjecten_bag"],
                                        "vbo_outside_range": [{"huisnummer": d["huisnummer"], "postcode": d["postcode"], "verblijfsobject_id": d["verblijfsobject_id"],
                                                               "raw_response_sha256": d["raw_response_sha256"]} for d in extra]}})
    if mjop.get("number_of_units") is None:
        points.append({"point_id": "MJOP_UNIT_COUNT_MISSING", "statement": "MJOP noemt geen aantal eenheden (en geen pariteit van het huisnummerbereik).",
                       "evidence": obs.get("unit_count")})
    years = sorted({r["bouwjaar"] for r in hyp["panden"]})
    if mjop.get("construction_year") is not None and years != [mjop["construction_year"]]:
        points.append({"point_id": "CONSTRUCTION_YEAR_MISMATCH",
                       "statement": f"Bouwjaar MJOP {mjop['construction_year']} versus BAG {', '.join(map(str, years))}.",
                       "evidence": {"mjop_construction_year": mjop["construction_year"], "bag_bouwjaar": years}})
    opd = obs.get("opdrachtgever_naam")
    if opd and opd.get("value") and norm_name(opd["value"]) != norm_name(mjop.get("object_name")):
        points.append({"point_id": "OBJECT_NAME_CONFLICT",
                       "statement": f"Objectnaam '{mjop.get('object_name')}' versus opdrachtgevernaam '{opd['value']}'.",
                       "evidence": {"object_name": mjop.get("object_name"), "opdrachtgever_naam": opd, "object_code": obs.get("object_code")}})
    record = {
        "case_id": aos.next_id(store["records"], "case_id", "UCASE"),
        "case_key": f"{group_id}:BUILDING_PROJECT_SCOPE",
        "document_ids": pkg["document_ids"],
        "candidate_id": bpc["candidate_id"],
        "case_status": "REVIEW_REQUIRED",
        "candidate_status": pkg["status"],
        "candidate_strength": bpc["strength"],
        "selected_scope": None,
        "building_project_linked": False,
        "legal_vve_linked": False,
        "hypotheses": {h["hypothesis_id"]: {"strength": h["strength"], "addresses_found": len(h["addresses_found"]),
                                            "addresses_missing": h["addresses_missing"], "bag_pand_ids": h["bag_pand_ids"],
                                            "vbo_total_bag": h["counts"]["vbo_total_bag"]}
                       for h in bpc["scope_hypotheses"]},
        "open_points": points,
        "decisions_needed": [
            "Welke huisnummers vormen de VvE (alleen oneven of alle) en hoort pand-verblijfsobject 885 er wel of niet bij?",
            "Is het ontbreken van 801 in de BAG verwacht (bestaat niet) of een registratieverschil?",
            "Wat is het aantal eenheden van de VvE (MJOP noemt er geen)?",
            "Is bouwjaar 1956 (MJOP) of 1957 (BAG) leidend, of is het verschil irrelevant?",
            "Is 'VvE Meppelweg 801-803' een typfout voor '801-883'?"],
        "note": "Onderzoek is afgerond en hoeft niet opnieuw: raadpleeg evidence-verwijzingen (raw responses + sha256) in dit record en het candidate package. "
                "Er is geen scope gekozen en geen building_project of legal_vve geschreven.",
        "provenance": prov,
        "recorded_by": {"recorder_id": recorded_by, "recorder_type": "claude_code"},
        "recorded_at": recorded_at,
        "decision_source": decision_source,
        "decision_reason": reason,
        "rule_version": RULE_VERSION,
        "supersedes": None,
        "status": "ACTIVE",
    }
    prev = [r for r in store["records"] if r["case_key"] == record["case_key"] and r["status"] == "ACTIVE"]
    out = copy.deepcopy(store)
    if prev:
        record["supersedes"] = prev[0]["case_id"]
        for r in out["records"]:
            if r["case_id"] == prev[0]["case_id"]:
                r["status"] = "SUPERSEDED"
    out["records"].append(record)
    errs = unresolved_store_errors(out) + aos.append_only_errors(store["records"], out["records"], "case_id")
    if errs:
        raise ProjectError("; ".join(errs))
    return out


def norm_name(s):
    return " ".join((s or "").lower().split())


# --------------------------------------------------------------------------
# Bescherming van goedgekeurde provenance
# --------------------------------------------------------------------------

def locked_validation_dirs(root=ROOT, project_store=None, support_store=None):
    """Evidence packages die door een building_project-record of een supporting-evidence-record (elke status, ook
    SUPERSEDED: de geschiedenis moet verifieerbaar blijven) worden gerefereerd, zijn onveranderlijk."""
    ps = project_store if project_store is not None else load_store(Path(root) / "data/building_projects/building_project_records.json", new_project_store)
    ss = support_store if support_store is not None else load_store(Path(root) / "data/building_projects/supporting_evidence_records.json", new_support_store)
    return sorted({r["provenance"]["validation_dir"] for r in ps["records"]} | {r["provenance"]["validation_dir"] for r in ss["records"]})


def is_locked(out_dir, root=ROOT, **kw):
    return rel(out_dir, root) in locked_validation_dirs(root, **kw)


def project_for_document(store, document_id):
    """ACTIEVE building_project_id('s) waarin dit document zit."""
    return [r["building_project_id"] for r in active_projects(store) if document_id in r["document_ids"]]


def provenance_errors(root=ROOT, project_path=PROJECT_STORE, unresolved_path=UNRESOLVED_STORE, support_path=SUPPORT_STORE):
    """Klopt de vastgelegde provenance (sha256 van package + manifest + alle raw responses) nog met de bestanden op schijf?"""
    errs, dirs = [], set()
    for path, factory, idf in ((project_path, new_project_store, "building_project_id"), (unresolved_path, new_unresolved_store, "case_id"),
                               (support_path, new_support_store, "evidence_id")):
        for r in load_store(path, factory)["records"]:
            if idf == "case_id" and r["status"] != "ACTIVE":
                continue  # oude unresolved cases mogen door een nieuwer record zijn vervangen
            p = r["provenance"]
            for key in ("candidate_package", "manifest"):
                f = Path(root) / p[key]["path"]
                if not f.exists() or sha_file(f) != p[key]["sha256"]:
                    errs.append(f"{r[idf]}: {key} komt niet meer overeen met provenance")
            dirs.add(p["validation_dir"])
    for d in sorted(dirs):
        if not (Path(root) / d / "manifest.json").exists():
            errs.append(f"{d}: evidence package ontbreekt")
        else:
            errs += [f"{d}: {e}" for e in frbv.manifest_errors(Path(root) / d)]
    return errs


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_expect(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[k] = int(v)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Building projects v1")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("approve")
    a.add_argument("--group", required=True)
    a.add_argument("--scope", required=True)
    a.add_argument("--reviewer", required=True)
    a.add_argument("--reason", required=True)
    a.add_argument("--decision-source", required=True)
    a.add_argument("--expect", action="append", default=[], help="bevestigd feit, bv. pand_count=15 (alle verplichte feiten opgeven)")
    a.add_argument("--dir", default=str(VALIDATION_DIR))
    u = sub.add_parser("unresolved")
    u.add_argument("--group", required=True)
    u.add_argument("--focus", required=True)
    u.add_argument("--recorded-by", required=True)
    u.add_argument("--reason", required=True)
    u.add_argument("--decision-source", required=True)
    u.add_argument("--dir", default=str(VALIDATION_DIR))
    rp = sub.add_parser("reproduce", help="leg vast dat een nieuwer package een goedgekeurd project exact reproduceert")
    rp.add_argument("--project", required=True)
    rp.add_argument("--group", required=True)
    rp.add_argument("--scope", required=True)
    rp.add_argument("--recorded-by", required=True)
    rp.add_argument("--decision-source", required=True)
    rp.add_argument("--dir", required=True)
    sub.add_parser("check")
    g = sub.add_parser("guard")
    g.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "approve":
            store = approve_building_project(load_store(PROJECT_STORE, new_project_store), out_dir=args.dir, group_id=args.group,
                                             hypothesis_id=args.scope, reviewer_id=args.reviewer, reason=args.reason, decided_at=now_utc(),
                                             expect=parse_expect(args.expect), decision_source=args.decision_source)
            write_store(store, PROJECT_STORE, new_project_store, project_store_errors, "building_project_id")
            r = store["records"][-1]
            print(f"{r['building_project_id']}: {r['bag_pand_count']} BAG-panden, {r['totals']['addresses']} adressen, legal_vve {r['legal_vve']['status']}")
        elif args.cmd == "unresolved":
            store = record_unresolved_case(load_store(UNRESOLVED_STORE, new_unresolved_store), out_dir=args.dir, group_id=args.group,
                                           focus_hypothesis_id=args.focus, recorded_by=args.recorded_by, reason=args.reason, recorded_at=now_utc(),
                                           decision_source=args.decision_source, projects_store=load_store(PROJECT_STORE, new_project_store))
            write_store(store, UNRESOLVED_STORE, new_unresolved_store, unresolved_store_errors, "case_id")
            r = store["records"][-1]
            print(f"{r['case_id']}: {r['case_key']} {r['case_status']}, {len(r['open_points'])} open punten, selected_scope={r['selected_scope']}")
        elif args.cmd == "reproduce":
            store = record_reproduction(load_store(SUPPORT_STORE, new_support_store), project_store=load_store(PROJECT_STORE, new_project_store),
                                        building_project_id=args.project, out_dir=args.dir, group_id=args.group, hypothesis_id=args.scope,
                                        recorded_by=args.recorded_by, recorded_at=now_utc(), decision_source=args.decision_source)
            write_store(store, SUPPORT_STORE, new_support_store, support_store_errors, "evidence_id")
            r = store["records"][-1]
            print(f"{r['evidence_id']}: {r['building_project_id']} {r['result']} ({r['evidence_role']}); approval ongewijzigd")
        elif args.cmd == "check":
            errs = (project_store_errors(load_store(PROJECT_STORE, new_project_store)) +
                    unresolved_store_errors(load_store(UNRESOLVED_STORE, new_unresolved_store)) +
                    support_store_errors(load_store(SUPPORT_STORE, new_support_store)) + provenance_errors())
            print("OK" if not errs else "\n".join(errs))
            return 1 if errs else 0
        elif args.cmd == "guard":
            if is_locked(args.out):
                print(f"FOUT: {args.out} bevat goedgekeurd bewijs (gerefereerd door een building_project-record) en is onveranderlijk; "
                      "niet overschrijven of verwijderen. Haal nieuwe data op in een NIEUWE versiemap (bv. real_validation_v3).", file=sys.stderr)
                return 1
            print(f"{args.out}: vrij (niet gerefereerd door een goedgekeurd building_project)")
    except ProjectError as e:
        print(f"FOUT: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
