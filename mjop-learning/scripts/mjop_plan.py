#!/usr/bin/env python3
"""
mjop_plan.py  (DOMEINMODEL: VERSIE VAN EEN NIEUW MJOP, v1)

Model: schemas/mjop_plan.schema.json; documentatie: docs/mjop_plan_v1.md.

Een MJOP (mjop_id) heeft versies (version_id = "{mjop_id}-V{version_number:03d}").
Een versie verwijst naar een vaste set Maintenance Line IDs (Maintenance Line v1,
ongewijzigd, niet embedded). Vanaf IN_REVIEW legt de versie per regel een sha256
vast (line_hashes); bij READY een content_sha256. Wijzigingen worden zo
gedetecteerd; opslag bestaat niet in deze laag.

Status: DRAFT -> IN_REVIEW -> READY -> SUPERSEDED, terugweg IN_REVIEW -> DRAFT,
en READY -> nieuwe DRAFT-versie via create_next_draft. Geen automatische
overgangen; alle overgangen zijn expliciete functieaanroepen.

Alle functies zijn puur: ze geven een nieuwe versie (of nieuwe structuur) terug,
muteren hun invoer niet en valideren het resultaat. Totalen zijn read-only
afgeleid (plan_totals). Geen indexatie, cyclusdoorrekening, reservefonds,
cashflow, planning, opslag, score of confidence.
"""
import copy
import json
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import human_match_review  # noqa: E402  (canonieke hashfunctie)
import mjop_maintenance_line  # noqa: E402

PLAN_MODEL_VERSION = "mjop_plan_v1"
DISPLAY = Decimal("0.01")   # alleen presentatie (ROUND_HALF_EVEN), zelfde als de andere lagen
METADATA_FIELDS = ("name", "address", "building_type", "construction_year", "renovation_year", "number_of_units",
                   "inspection_date")
EDITABLE_FIELDS = METADATA_FIELDS + ("building_id",)
# inhoud die content_sha256 vastlegt (geen status, historie, tijdstempels of afgeleide samenvattingen)
CONTENT_FIELDS = ("plan_model_version", "mjop_id", "version_id", "version_number", "supersedes_version_id",
                  "building_id") + METADATA_FIELDS + ("metadata_source", "plan_start_year", "plan_end_year",
                                                      "maintenance_line_ids", "line_hashes")
FINANCIAL_PRICE_STATUSES = ("HUMAN_ACCEPTED", "HUMAN_ADJUSTED", "MANUALLY_SET")
LAST_EVENT = {"DRAFT": ("CREATED", "RETURNED_TO_DRAFT"), "IN_REVIEW": ("SUBMITTED_FOR_REVIEW",),
              "READY": ("APPROVED",), "SUPERSEDED": ("SUPERSEDED",)}

SCHEMA = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas",
                                     "mjop_plan.schema.json"), encoding="utf-8"))


class PlanError(ValueError):
    """Ongeldige planversie of niet-toegestane bewerking."""


def version_id_for(mjop_id, version_number):
    return f"{mjop_id}-V{version_number:03d}"


def line_hash(line):
    return human_match_review.canonical_sha256(line)


def content_sha256(version):
    return human_match_review.canonical_sha256({f: version[f] for f in CONTENT_FIELDS})


def display(value):
    return format(Decimal(value).quantize(DISPLAY), "f")


def event(name, at, by=None, reason=None):
    return {"event": name, "at": at, "by": by, "reason": reason}


# --------------------------------------------------------------------------
# Validatie
# --------------------------------------------------------------------------

def _horizon_errors(v):
    s, e = v["plan_start_year"], v["plan_end_year"]
    if s is not None and e is not None and s > e:
        return [f"plan_start_year {s} ligt na plan_end_year {e}"]
    return []


def _lines_errors(v, lines):
    errors = []
    ids = [l["maintenance_line_id"] for l in lines]
    if len(ids) != len(set(ids)):
        errors.append("meegegeven regels bevatten dubbele maintenance_line_ids")
    if set(ids) != set(v["maintenance_line_ids"]):
        errors.append("meegegeven regels zijn niet exact de maintenance_line_ids van de versie")
    for l in lines:
        if l["mjop_id"] != v["mjop_id"]:
            errors.append(f"{l['maintenance_line_id']}: hoort bij mjop_id {l['mjop_id']}, niet {v['mjop_id']}")
        errors += [f"{l['maintenance_line_id']}: {e}" for e in mjop_maintenance_line.line_errors(l)]
    return errors


def plan_errors(version, lines=None):
    """Schema + invarianten van één versie; met 'lines' ook de regelkoppeling en line_hashes."""
    import jsonschema
    errors = [f"{'/'.join(str(x) for x in e.path) or '(versie)'}: {e.message}"
              for e in jsonschema.Draft7Validator(SCHEMA).iter_errors(version)]
    if errors:
        return errors
    v = version
    if v["version_id"] != version_id_for(v["mjop_id"], v["version_number"]):
        errors.append("version_id past niet bij mjop_id en version_number")
    errors += _horizon_errors(v)
    if v["status_history"][-1]["event"] not in LAST_EVENT[v["plan_status"]]:
        errors.append(f"laatste gebeurtenis {v['status_history'][-1]['event']} past niet bij {v['plan_status']}")
    if v["line_hashes"] is not None and set(v["line_hashes"]) != set(v["maintenance_line_ids"]):
        errors.append("line_hashes dekt niet exact de maintenance_line_ids")
    if v["content_sha256"] is not None and v["content_sha256"] != content_sha256(v):
        errors.append("content_sha256 past niet bij de inhoud (versie gewijzigd)")
    if lines is not None:
        errors += _lines_errors(v, lines)
        if v["line_hashes"] is not None:
            for l in lines:
                if v["line_hashes"].get(l["maintenance_line_id"]) not in (None, line_hash(l)):
                    errors.append(f"{l['maintenance_line_id']}: regel gewijzigd sinds vastleggen (line_hash wijkt af)")
        if v["plan_status"] in ("READY", "SUPERSEDED"):
            errors += [f"{l['maintenance_line_id']}: line_status REVIEW_REQUIRED" for l in lines
                       if l["line_status"] == "REVIEW_REQUIRED"]
    return errors


def validated(version, lines=None):
    errors = plan_errors(version, lines)
    if errors:
        raise PlanError("; ".join(errors))
    return version


def versions_errors(versions):
    """Invarianten over alle versies van één MJOP."""
    errors = []
    if not versions:
        return errors
    if len({v["mjop_id"] for v in versions}) != 1:
        return ["versies horen bij verschillende mjop_ids"]
    numbers = sorted(v["version_number"] for v in versions)
    if numbers != list(range(1, len(versions) + 1)):
        errors.append(f"version_numbers {numbers} zijn niet uniek en aaneengesloten vanaf 1")
    by_id = {v["version_id"]: v for v in versions}
    superseded_by = Counter()
    for v in versions:
        errors += [f"{v['version_id']}: {e}" for e in plan_errors(v)]
        s = v["supersedes_version_id"]
        if s is not None:
            if s not in by_id or by_id[s]["version_number"] >= v["version_number"]:
                errors.append(f"{v['version_id']}: supersedes_version_id {s} is geen eerdere versie")
            superseded_by[s] += 1
    errors += [f"{s}: door meer dan één versie opgevolgd" for s, n in superseded_by.items() if n > 1]
    status = Counter(v["plan_status"] for v in versions)
    if status["READY"] > 1:
        errors.append("meer dan één READY-versie")
    if status["DRAFT"] + status["IN_REVIEW"] > 1:
        errors.append("meer dan één open (DRAFT/IN_REVIEW) versie")
    for v in versions:
        if v["plan_status"] == "SUPERSEDED" and not any(
                w["supersedes_version_id"] == v["version_id"] and w["plan_status"] in ("READY", "SUPERSEDED")
                for w in versions):
            errors.append(f"{v['version_id']}: SUPERSEDED zonder vastgestelde opvolger")
    return errors


# --------------------------------------------------------------------------
# Aanmaken en bewerken (alleen DRAFT)
# --------------------------------------------------------------------------

def _blank(mjop_id, version_number, supersedes, building_id, at):
    return {"plan_model_version": PLAN_MODEL_VERSION, "mjop_id": mjop_id,
            "version_id": version_id_for(mjop_id, version_number), "version_number": version_number,
            "supersedes_version_id": supersedes, "building_id": building_id,
            **{k: None for k in METADATA_FIELDS}, "metadata_source": "USER_ENTERED",
            "plan_start_year": None, "plan_end_year": None, "plan_status": "DRAFT", "maintenance_line_ids": [],
            "line_hashes": None, "content_sha256": None, "knowledge_basis": None, "readiness_warnings": None,
            "status_history": [], "created_at": at, "updated_at": at}


def new_plan(mjop_id, building_id, *, at, by=None, **metadata):
    """Versie 1 van een nieuw MJOP, status DRAFT. building_id is verplicht en wordt nergens afgeleid."""
    unknown = set(metadata) - set(METADATA_FIELDS)
    if unknown:
        raise PlanError(f"onbekende of niet-bewerkbare velden: {sorted(unknown)}")
    v = _blank(mjop_id, 1, None, building_id, at)
    v.update(metadata)
    v["status_history"] = [event("CREATED", at, by)]
    return validated(v)


def _require_draft(version):
    if version["plan_status"] != "DRAFT":
        raise PlanError(f"alleen een DRAFT-versie kan worden gewijzigd (status {version['plan_status']})")


def update_plan_metadata(version, *, at, **changes):
    _require_draft(version)
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise PlanError(f"onbekende of niet-bewerkbare velden: {sorted(unknown)}")
    v = copy.deepcopy(version)
    v.update(changes)
    v["updated_at"] = at
    return validated(v)


def set_horizon(version, plan_start_year, plan_end_year, *, at):
    _require_draft(version)
    v = copy.deepcopy(version)
    v["plan_start_year"], v["plan_end_year"], v["updated_at"] = plan_start_year, plan_end_year, at
    return validated(v)


def set_line_ids(version, maintenance_line_ids, *, at):
    _require_draft(version)
    ids = list(maintenance_line_ids)
    if len(ids) != len(set(ids)):
        raise PlanError("maintenance_line_ids moeten uniek zijn")
    v = copy.deepcopy(version)
    v["maintenance_line_ids"], v["updated_at"] = ids, at
    return validated(v)


# --------------------------------------------------------------------------
# Statusovergangen
# --------------------------------------------------------------------------

def submit_for_review(version, lines, *, at, by, reason=None):
    """DRAFT -> IN_REVIEW: geldige horizon, regels exact de ID-set, van dit MJOP en geldig.
    Legt line_hashes vast."""
    _require_draft(version)
    if version["plan_start_year"] is None or version["plan_end_year"] is None:
        raise PlanError("horizon (plan_start_year en plan_end_year) is verplicht voor IN_REVIEW")
    errors = _horizon_errors(version) + _lines_errors(version, lines)
    if errors:
        raise PlanError("; ".join(errors))
    v = copy.deepcopy(version)
    v["line_hashes"] = {l["maintenance_line_id"]: line_hash(l) for l in lines}
    v["plan_status"], v["updated_at"] = "IN_REVIEW", at
    v["status_history"].append(event("SUBMITTED_FOR_REVIEW", at, by, reason))
    return validated(v, lines)


def return_to_draft(version, *, at, by, reason):
    """IN_REVIEW -> DRAFT (reden verplicht). De vastgelegde line_hashes vervallen."""
    if version["plan_status"] != "IN_REVIEW":
        raise PlanError("alleen een IN_REVIEW-versie kan terug naar DRAFT")
    if not reason:
        raise PlanError("reden is verplicht bij terugzetten naar DRAFT")
    v = copy.deepcopy(version)
    v["line_hashes"], v["plan_status"], v["updated_at"] = None, "DRAFT", at
    v["status_history"].append(event("RETURNED_TO_DRAFT", at, by, reason))
    return validated(v)


def approve(version, lines, *, at, by, reason, previous_ready=None):
    """IN_REVIEW -> READY door een expliciete menselijke actie (by en reason verplicht).
    Regels ongewijzigd sinds indienen; geen REVIEW_REQUIRED-regel. Heeft de versie een
    supersedes_version_id, dan moet die READY-versie worden meegegeven en wordt die SUPERSEDED.
    Geeft (goedgekeurde versie, opgevolgde versie of None)."""
    if version["plan_status"] != "IN_REVIEW":
        raise PlanError("alleen een IN_REVIEW-versie kan READY worden")
    if not by or not reason:
        raise PlanError("goedkeuren vereist een reviewer (by) en een reden")
    errors = plan_errors(version, lines)
    blocking = [l["maintenance_line_id"] for l in lines if l["line_status"] == "REVIEW_REQUIRED"]
    if blocking:
        errors.append(f"regels met line_status REVIEW_REQUIRED blokkeren READY: {sorted(blocking)}")
    superseded = None
    if version["supersedes_version_id"] is not None:
        if previous_ready is None or previous_ready["version_id"] != version["supersedes_version_id"] \
                or previous_ready["plan_status"] != "READY":
            errors.append(f"de op te volgen READY-versie {version['supersedes_version_id']} moet worden meegegeven")
        else:
            errors += [f"{previous_ready['version_id']}: {e}" for e in plan_errors(previous_ready)]
    elif previous_ready is not None:
        errors.append("previous_ready meegegeven maar deze versie volgt geen versie op")
    if errors:
        raise PlanError("; ".join(errors))
    v = copy.deepcopy(version)
    totals = plan_totals(v, lines)
    c = totals["counts"]
    v["readiness_warnings"] = {k: c[k] for k in ("no_amount", "rejected", "amount_without_total", "outside_horizon",
                                                   "without_planned_year")}
    v["knowledge_basis"] = knowledge_basis(lines)
    v["plan_status"], v["updated_at"] = "READY", at
    v["status_history"].append(event("APPROVED", at, by, reason))
    v["content_sha256"] = content_sha256(v)
    if previous_ready is not None:
        superseded = copy.deepcopy(previous_ready)
        superseded["plan_status"], superseded["updated_at"] = "SUPERSEDED", at
        superseded["status_history"].append(event("SUPERSEDED", at, by, f"opgevolgd door {v['version_id']}"))
        validated(superseded)
    return validated(v, lines), superseded


def create_next_draft(ready_version, *, at, by=None):
    """READY -> nieuwe DRAFT-versie (version_number + 1, supersedes_version_id gezet), met dezelfde
    metadata, horizon en ID-set. Ongewijzigde regels mogen worden hergebruikt; een regel die
    inhoudelijk wijzigt krijgt een nieuw maintenance_line_id (set_line_ids)."""
    if ready_version["plan_status"] != "READY":
        raise PlanError("een nieuwe versie wordt alleen vanaf een READY-versie gemaakt")
    validated(ready_version)
    r = ready_version
    v = _blank(r["mjop_id"], r["version_number"] + 1, r["version_id"], r["building_id"], at)
    for k in METADATA_FIELDS + ("plan_start_year", "plan_end_year"):
        v[k] = r[k]
    v["maintenance_line_ids"] = list(r["maintenance_line_ids"])
    v["status_history"] = [event("CREATED", at, by, f"nieuwe versie na {r['version_id']}")]
    return validated(v)


# --------------------------------------------------------------------------
# Afgeleide gegevens: totalen en knowledge basis
# --------------------------------------------------------------------------

def plan_totals(version, lines):
    """Read-only totalen. Financieel alleen: definitieve price_status, effective_total aanwezig,
    planned_year aanwezig en binnen de horizon. Elke uitsplitsing per VAT-basis; inclusive en
    exclusive worden nooit samengevoegd. Exact Decimal; geen indexatie of cycli."""
    errors = _lines_errors(version, lines)
    if errors:
        raise PlanError("; ".join(errors))
    start, end = version["plan_start_year"], version["plan_end_year"]
    horizon = start is not None and end is not None
    per_vat, per_year, per_action, per_code = (defaultdict(Decimal), defaultdict(lambda: defaultdict(Decimal)),
                                               defaultdict(lambda: defaultdict(Decimal)),
                                               defaultdict(lambda: defaultdict(Decimal)))
    n_vat, n_year, n_action, n_code = (Counter(), defaultdict(Counter), defaultdict(Counter), defaultdict(Counter))
    counts = Counter()
    kengetal_years, mixed, missing, manual_levels = set(), False, False, set()
    for l in lines:
        f, py = l["financial"], l["planned_year"]
        counts["lines_total"] += 1
        counts["no_amount"] += l["price_status"] == "NO_AMOUNT"
        counts["system_proposed"] += l["price_status"] == "SYSTEM_PROPOSED"
        counts["rejected"] += l["price_status"] == "REJECTED"
        counts["review_required"] += l["line_status"] == "REVIEW_REQUIRED"
        definitive = l["price_status"] in FINANCIAL_PRICE_STATUSES
        counts["amount_without_total"] += definitive and f["effective_total"] is None
        counts["without_planned_year"] += py is None
        outside = py is not None and horizon and not (start <= py <= end)
        counts["outside_horizon"] += outside
        if not (definitive and f["effective_total"] is not None and py is not None and horizon and not outside):
            continue
        counts["in_financial_totals"] += 1
        amount, vat = Decimal(f["effective_total"]), f["vat_basis"] or "unknown"
        per_vat[vat] += amount
        n_vat[vat] += 1
        for table, counter, key in ((per_year, n_year, str(py)), (per_action, n_action, l["action_normalized"] or "unknown"),
                                    (per_code, n_code, l["element_code_internal"] or "unknown")):
            table[key][vat] += amount
            counter[key][vat] += 1
        pl = f["price_level"] or {}
        if "manual_price_level" in pl:
            manual_levels.add(pl["manual_price_level"] or "unknown")
        else:
            kengetal_years.update(pl.get("years", []))
            mixed |= bool(pl.get("mixed_price_level"))
            missing |= bool(pl.get("missing_price_level"))

    def leaf(total, n):
        return {"total_exact": format(total, "f"), "total_display": display(total), "lines": n}

    def nested(table, counter):
        return {k: {vat: leaf(t, counter[k][vat]) for vat, t in sorted(sub.items())} for k, sub in sorted(table.items())}

    return {
        "mjop_id": version["mjop_id"], "version_id": version["version_id"],
        "horizon": {"plan_start_year": start, "plan_end_year": end, "set": horizon},
        "per_vat_basis": {vat: leaf(t, n_vat[vat]) for vat, t in sorted(per_vat.items())},
        "per_planned_year": nested(per_year, n_year),
        "per_action": nested(per_action, n_action),
        "per_element_code": nested(per_code, n_code),
        "counts": {k: counts[k] for k in ("lines_total", "in_financial_totals", "no_amount", "system_proposed",
                                          "review_required", "rejected", "amount_without_total", "outside_horizon",
                                          "without_planned_year")},
        "price_levels": {"kengetal_price_level_years": sorted(kengetal_years), "any_mixed_price_level": mixed,
                         "any_missing_price_level": missing, "manual_price_levels": sorted(manual_levels),
                         "indexation": "none",
                         "note": "Historische, niet-geïndexeerde bedragen; totalen zijn geen prijs van één specifiek jaar."},
    }


def knowledge_basis(lines):
    """Samenvatting van de bestaande provenance van de regels (geen eigen herkomstsysteem)."""
    kengetallen, normalized, stores, rules = set(), set(), set(), defaultdict(set)
    sources, without = Counter(), 0
    for l in lines:
        src = l["financial"]["amount_source"]
        sources[src or "none"] += 1
        p = l["provenance"]
        if p is None:
            without += 1
            continue
        kengetallen.add(p["input_hashes"]["kengetallen_output_sha256"])
        normalized.add(p["input_hashes"]["normalized_observations_sha256"])
        stores.add(p["decision_store_sha256"])
        for k, val in p["rule_versions"].items():
            rules[k].add(val)
    return {"kengetallen_output_sha256": sorted(kengetallen), "normalized_observations_sha256": sorted(normalized),
            "decision_store_sha256": sorted(stores), "rule_versions": {k: sorted(v) for k, v in sorted(rules.items())},
            "amount_sources": dict(sorted(sources.items())), "lines_without_provenance": without}
