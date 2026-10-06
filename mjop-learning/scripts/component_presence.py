"""Component presence v1 — evidence-records, presence-regels en append-only menselijke besluiten.

Building Element Inventory Foundation v1. Keten:

    BUILDING SCOPE -> COMPONENT PRESENCE EVIDENCE -> HUMAN COMPONENT DECISION -> COMPONENT INVENTORY
    -> (later) COMPONENT QUANTITIES -> MAINTENANCE TEMPLATES -> PRICE

Presence is een ANDER concept dan quantity: 'EXTERIOR_FRAME = PRESENT' zegt niets over aantal, oppervlak,
schilderoppervlak of prijs. Regels:

- Stilte is nooit ABSENT. Niet gevonden in een oud MJOP, niet zichtbaar op een foto, niet getekend: dat levert
  GEEN ABSENT-evidence op (en ook geen UNKNOWN-record; het gebouw-onderdeel blijft in de inventaris 'unknown').
- ABSENT vereist expliciet bewijs (een expliciete nulwaarde in een bronveld of een expliciete bronuitspraak),
  heeft altijd status REVIEW_REQUIRED en een 'absence_basis'.
- Een ontbrekend veld is UNKNOWN, nooit ABSENT en nooit 0 (zelfde regel als bag3d_quantity_rules).
- Evidence is content-addressed (CPE-<sha256[:16]>) en wordt afgeleid, niet met de hand aangepast.
- Besluiten zijn menselijk, append-only, zonder meerderheidstem, middeling of automatische winnaar.
"""

import copy
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import append_only_store as aos  # noqa: E402
import bag3d_quantity_rules as rules_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
COMPONENT_TYPES = ROOT / "vocabularies" / "building_component_types_v1.json"
APP_REQUIREMENTS = ROOT / "vocabularies" / "app_element_requirements_v1.json"
PRESENCE_RULES = ROOT / "vocabularies" / "component_presence_rules_v1.json"
DECISIONS = ROOT / "data" / "component_presence" / "component_presence_decision_records.json"

CONTRACT_VERSION = "component_presence_evidence_v1"
RULE_VERSION = "component_presence_rules_v1"
ASSERTIONS = ("PRESENT", "ABSENT", "UNKNOWN")
SOURCE_TYPES = ("3D_BAG", "BAG", "MJOP", "DRAWING", "PHOTO", "MANUAL")
METHOD_CLASSES = ("GEOMETRY_POSITIVE_VALUE", "GEOMETRY_EXPLICIT_ZERO", "GEOMETRY_FIELD_MISSING", "SOURCE_EXPLICIT_ELEMENT",
                  "SOURCE_EXPLICIT_ELEMENT_WITH_INFERENCE", "EXPLICIT_ABSENCE_STATEMENT", "MANUAL_STATEMENT")
ABSENCE_METHOD_CLASSES = ("GEOMETRY_EXPLICIT_ZERO", "EXPLICIT_ABSENCE_STATEMENT", "MANUAL_STATEMENT")
ABSENCE_BASIS_KINDS = ("EXPLICIT_ZERO_VALUE_IN_SOURCE_FIELD", "EXPLICIT_SOURCE_STATEMENT")
STATUSES = ("PROPOSED", "REVIEW_REQUIRED")
DEFAULT_NOT_INTERPRETED_AS = ["MEASURED_QUANTITY", "GEOMETRY_QUANTITY"]


class PresenceError(RuntimeError):
    pass


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def component_type_index(vocab=None):
    vocab = vocab if vocab is not None else load_json(COMPONENT_TYPES)
    return {c["component_type"]: c for c in vocab["component_types"]}


def norm_text(s):
    return re.sub(r"\s+", " ", s).strip().casefold() if isinstance(s, str) else s


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------

def make_evidence(*, building_id, scope_level, bag_pand_id, component_type, assertion, source_type, method_class, source_ref,
                  details=None, absence_basis=None, scope_caveats=(), review_reasons=(), dependency=None, status="PROPOSED",
                  created_by, input_hashes=None):
    body = {
        "contract_version": CONTRACT_VERSION,
        "building_id": building_id,
        "scope_level": scope_level,
        "bag_pand_id": bag_pand_id,
        "component_type": component_type,
        "assertion": assertion,
        "source_type": source_type,
        "method_class": method_class,
        "source_ref": source_ref,
        "details": details or {},
        "absence_basis": absence_basis,
        "scope_caveats": list(scope_caveats),
        "review_reasons": sorted(set(review_reasons)),
        "dependency": dependency or {},
        "requires_human_review": status == "REVIEW_REQUIRED",
        "status": status,
        "created_by": created_by,
        "input_hashes": input_hashes or {},
    }
    errs = evidence_errors(dict(body, evidence_id="CPE-" + "0" * 16))
    if errs:
        raise PresenceError("; ".join(errs))
    body["evidence_id"] = "CPE-" + canonical_sha256(body)[:16]
    return body


def evidence_errors(ev, component_ids=None):
    errors, eid = [], ev.get("evidence_id")
    body = {k: v for k, v in ev.items() if k != "evidence_id"}
    if not str(eid).startswith("CPE-") or (eid != "CPE-" + "0" * 16 and eid != "CPE-" + canonical_sha256(body)[:16]):
        errors.append(f"{eid}: evidence_id past niet bij de inhoud (record aangepast?)")
    if ev.get("assertion") not in ASSERTIONS:
        errors.append(f"{eid}: onbekende assertion {ev.get('assertion')!r}")
    if ev.get("source_type") not in SOURCE_TYPES:
        errors.append(f"{eid}: onbekend source_type {ev.get('source_type')!r}")
    if ev.get("method_class") not in METHOD_CLASSES:
        errors.append(f"{eid}: onbekende method_class {ev.get('method_class')!r}")
    if ev.get("status") not in STATUSES:
        errors.append(f"{eid}: status moet PROPOSED of REVIEW_REQUIRED zijn")
    if component_ids is not None and ev.get("component_type") not in component_ids:
        errors.append(f"{eid}: onbekend component_type {ev.get('component_type')!r}")
    if not ev.get("source_ref"):
        errors.append(f"{eid}: source_ref (provenance) ontbreekt")
    if ev.get("scope_level") == "PAND" and not ev.get("bag_pand_id"):
        errors.append(f"{eid}: PAND-evidence vereist bag_pand_id")
    if ev.get("scope_level") == "BUILDING_SCOPE" and ev.get("bag_pand_id") is not None:
        errors.append(f"{eid}: een scope-evidence wordt nooit aan één pand toegeschreven")
    if ev.get("assertion") == "ABSENT":
        ab = ev.get("absence_basis")
        if not ab or ab.get("kind") not in ABSENCE_BASIS_KINDS or not ab.get("statement"):
            errors.append(f"{eid}: ABSENT vereist een expliciete absence_basis (afwezigheid uit stilte is verboden)")
        if ev.get("method_class") not in ABSENCE_METHOD_CLASSES:
            errors.append(f"{eid}: method_class {ev.get('method_class')!r} kan geen ABSENT dragen")
        if ev.get("status") != "REVIEW_REQUIRED":
            errors.append(f"{eid}: ABSENT-evidence is altijd REVIEW_REQUIRED")
    elif ev.get("absence_basis"):
        errors.append(f"{eid}: absence_basis hoort alleen bij ABSENT")
    if ev.get("assertion") == "PRESENT" and ev.get("method_class") in ("GEOMETRY_FIELD_MISSING", "GEOMETRY_EXPLICIT_ZERO"):
        errors.append(f"{eid}: method_class {ev.get('method_class')} kan geen PRESENT dragen")
    if ev.get("assertion") == "UNKNOWN" and ev.get("method_class") not in ("GEOMETRY_FIELD_MISSING",):
        errors.append(f"{eid}: UNKNOWN-evidence is alleen toegestaan voor een ontbrekend bronveld")
    if ev.get("source_type") in ("MJOP", "PHOTO", "DRAWING") and ev.get("assertion") == "ABSENT" \
            and ev.get("method_class") != "EXPLICIT_ABSENCE_STATEMENT":
        errors.append(f"{eid}: {ev.get('source_type')} levert alleen ABSENT via een expliciete uitspraak, nooit uit stilte")
    return errors


# --------------------------------------------------------------------------
# 3D BAG presence rules
# --------------------------------------------------------------------------

def bag3d_presence(presence_rule, quantity_rule, attributes):
    """(assertion, method_class, absence_basis, quantity_result). Pure; gebruikt exact dezelfde veld/missing-regels als
    bag3d_quantity_rules.apply_rule: ontbrekend veld -> UNKNOWN (nooit ABSENT, nooit 0)."""
    res = rules_mod.apply_rule(quantity_rule, attributes)
    if res["status"] == "OK":
        value = Decimal(res["value"])
        if value > 0:
            return "PRESENT", "GEOMETRY_POSITIVE_VALUE", None, res
        if value == 0:
            return "ABSENT", "GEOMETRY_EXPLICIT_ZERO", {
                "kind": "EXPLICIT_ZERO_VALUE_IN_SOURCE_FIELD",
                "statement": f"3D BAG-veld {', '.join(quantity_rule['fields'])} is expliciet aanwezig met waarde 0 "
                             f"(geometry-absence in het 3D-model; geen bewijs voor alle fysieke varianten)"}, res
    return "UNKNOWN", "GEOMETRY_FIELD_MISSING", None, res


# --------------------------------------------------------------------------
# Historische MJOP-presence regels (exacte match)
# --------------------------------------------------------------------------

def rule_matches(rule, element):
    if rule.get("status") != "ACTIVE":
        return False
    if element.get("element_code_internal") != rule["element_code_internal"]:
        return False
    descs = {norm_text(d) for d in rule["element_description_original_exact"]}
    if norm_text(element.get("element_description_original")) not in descs:
        return False
    locs = rule.get("location_original_exact")
    if locs is not None and norm_text(element.get("location_original")) not in {norm_text(x) for x in locs}:
        return False
    return True


def matching_rules(rules, element):
    return [r for r in rules if rule_matches(r, element)]


# --------------------------------------------------------------------------
# Menselijke besluiten (append-only)
# --------------------------------------------------------------------------

def new_store():
    return {"store_version": "component_presence_decision_v1", "append_only": True,
            "description": "Menselijke besluiten over componentaanwezigheid (scripts/component_presence.py). Append-only.",
            "records": []}


def load_store(path=DECISIONS):
    path = Path(path)
    return load_json(path) if path.exists() else new_store()


def decision_key(r):
    return (r["building_id"], r.get("bag_pand_id"), r["component_type"])


def store_errors(store):
    return aos.invariant_errors(store["records"], "decision_id", decision_key)


def active_decisions(store):
    return {decision_key(r): r for r in store["records"] if r["status"] == "ACTIVE"}


def record_decision(store, *, building_id, component_type, decision, reason, reviewer_id, reviewed_at, considered_evidence_ids,
                    evidence_index, bag_pand_id=None, component_ids=None):
    """Voegt een menselijk besluit toe (append-only). Alleen voor gebruik door een mens/menselijke review; de
    builder en de tests van deze milestone schrijven GEEN besluiten naar het canonieke bestand."""
    if decision not in ASSERTIONS:
        raise PresenceError("decision moet PRESENT, ABSENT of UNKNOWN zijn")
    if not reviewer_id or not reason:
        raise PresenceError("reviewer en reden zijn verplicht")
    if component_ids is not None and component_type not in component_ids:
        raise PresenceError(f"onbekend component_type {component_type}")
    considered = sorted(set(considered_evidence_ids))
    if decision in ("PRESENT", "ABSENT") and not considered:
        raise PresenceError(f"{decision} vereist minstens één overwogen evidence-id (MANUAL-evidence voor menselijke kennis)")
    for cid in considered:
        ev = evidence_index.get(cid)
        if ev is None:
            raise PresenceError(f"onbekende evidence {cid}")
        if (ev["building_id"], ev["component_type"]) != (building_id, component_type):
            raise PresenceError(f"evidence {cid} hoort niet bij {building_id} / {component_type}")
    out = copy.deepcopy(store)
    previous = [r for r in out["records"] if decision_key(r) == (building_id, bag_pand_id, component_type)
                and r["status"] in ("ACTIVE", "REVIEW_REQUIRED")]
    rec = {
        "decision_id": aos.next_id(out["records"], "decision_id", "CPD"),
        "building_id": building_id, "bag_pand_id": bag_pand_id, "component_type": component_type,
        "decision": decision, "decision_reason": reason, "considered_evidence_ids": considered,
        "reviewer": {"reviewer_id": reviewer_id, "reviewer_type": "human"},
        "reviewed_at": reviewed_at, "rule_version": RULE_VERSION,
        "supersedes": previous[0]["decision_id"] if previous else None, "status": "ACTIVE",
    }
    for r in previous:
        r["status"] = "SUPERSEDED"
    out["records"].append(rec)
    errs = store_errors(out) + aos.append_only_errors(store["records"], out["records"], "decision_id")
    if errs:
        raise PresenceError("; ".join(errs))
    return out, rec
