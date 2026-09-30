"""Quantity evidence v1 — contract + resolutie (append-only), zie docs/quantity_foundation_v1.md.

Drie lagen (docs/quantity_engine_feasibility_v1.md §11):

  quantity_evidence            onveranderlijk; één per bron x methode x berekening
  quantity_resolution_record   append-only menselijke beslissing per (building_id, subject_id),
                               zelfde patroon als de human decision records: ACTIVE / SUPERSEDED /
                               REVIEW_REQUIRED, 'supersedes', nooit overschrijven
  maintenance_line.quantity    (later) de waarde uit het ACTIVE resolution record

Harde regels:
- Er wordt NOOIT gemiddeld of anderszins gecombineerd: een resolutie neemt precies één evidence-waarde
  over (ACCEPT_EVIDENCE), legt een eigen waarde vast die zelf als MANUAL-evidence bestaat (USER_VALUE),
  of zegt UNKNOWN. validate_resolution() controleert dat de vastgelegde waarde exact gelijk is aan de
  gekozen evidence.
- Een evidence-record wordt nooit aangepast; een nieuwe berekening is een nieuw record.
- building_id wordt nooit afgeleid uit historische document-ID's: de koppeling "dit historische MJOP gaat
  over dit gebouw" is een menselijke, expliciete stap (building_link_ref).
- Geen scores, geen confidence, geen fuzzy matching.
"""

import copy
import hashlib
import json
from decimal import Decimal, InvalidOperation

CONTRACT_VERSION = "quantity_evidence_v1"
RESOLUTION_STORE_VERSION = "quantity_resolution_v1"
RESOLUTION_RULE_VERSION = "quantity_resolution_rules_v1"

METHOD_CLASSES = ("DIRECT_MEASURED", "SOURCE_REPORTED", "GEOMETRY_DERIVED", "ESTIMATED", "MANUAL")
QUANTITY_KINDS = ("ELEMENT_QUANTITY", "ACTION_QUANTITY", "SHARE_QUANTITY")
SOURCE_TYPES = ("MJOP_ELEMENT_OVERVIEW", "MJOP_JARENPLAN_ROW", "BAG", "3D_BAG", "QUOTE", "DRAWING", "MANUAL")
EVIDENCE_STATUSES = ("PROPOSED", "REVIEW_REQUIRED", "SUPERSEDED")
DECISIONS = ("ACCEPT_EVIDENCE", "USER_VALUE", "UNKNOWN")
RECORD_STATUSES = ("ACTIVE", "SUPERSEDED", "REVIEW_REQUIRED")
ALLOWED_STATUS_TRANSITIONS = {("ACTIVE", "SUPERSEDED"), ("ACTIVE", "REVIEW_REQUIRED"), ("REVIEW_REQUIRED", "SUPERSEDED")}


class QuantityEvidenceError(ValueError):
    pass


def _dec(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise QuantityEvidenceError(f"geen geldig decimaal getal: {value!r}")


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Onderwerp (quantity subject)
# --------------------------------------------------------------------------

def make_subject_id(building_id, element_code_internal, location_scope, unit_normalized, quantity_kind):
    """Deterministische ID voor 'welke hoeveelheid van welk gebouw'. Geen vrije tekst in de sleutel,
    zodat bronnen met een andere omschrijving (3D BAG, MJOP, tekening) naar hetzelfde onderwerp kunnen
    verwijzen. De omschrijving staat los in quantity_subject.subject_text."""
    if not building_id:
        raise QuantityEvidenceError("building_id is verplicht")
    if quantity_kind not in QUANTITY_KINDS:
        raise QuantityEvidenceError(f"onbekende quantity_kind {quantity_kind!r}")
    key = [building_id, element_code_internal, location_scope, unit_normalized, quantity_kind]
    return "QS-" + canonical_sha256(key)[:16]


def make_building_subject_id(building_id, subject_key, unit_normalized, quantity_kind="ELEMENT_QUANTITY"):
    """Onderwerp-ID voor een gebouwbreed hoeveelheidsonderwerp uit vocabularies/quantity_subjects_v1.json
    (bijv. ROOF_FLAT_AREA). Deterministisch, zonder vrije tekst."""
    if not building_id or not subject_key:
        raise QuantityEvidenceError("building_id en subject_key zijn verplicht")
    if quantity_kind not in QUANTITY_KINDS:
        raise QuantityEvidenceError(f"onbekende quantity_kind {quantity_kind!r}")
    return "QS-" + canonical_sha256(["building_subject", building_id, subject_key, unit_normalized, quantity_kind])[:16]


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------

def make_evidence(*, building_id, subject, value, unit_normalized, method_class, source_type, source_ref,
                  created_by, calculation=None, dependency=None, scope_caveats=(), review_reasons=(),
                  input_hashes=None):
    if method_class not in METHOD_CLASSES:
        raise QuantityEvidenceError(f"onbekende method_class {method_class!r}")
    if source_type not in SOURCE_TYPES:
        raise QuantityEvidenceError(f"onbekende source_type {source_type!r}")
    if subject.get("quantity_kind") not in QUANTITY_KINDS:
        raise QuantityEvidenceError("quantity_subject.quantity_kind is verplicht")
    if method_class == "GEOMETRY_DERIVED" and not calculation:
        raise QuantityEvidenceError("GEOMETRY_DERIVED vereist een calculation (regel + formule + invoer)")
    v = _dec(value)
    if v is not None and v < 0:
        raise QuantityEvidenceError("negatieve hoeveelheid")
    review_reasons = sorted(set(review_reasons))
    body = {
        "contract_version": CONTRACT_VERSION,
        "building_id": building_id,
        "quantity_subject": dict(subject),
        "value": None if v is None else str(value),
        "unit_normalized": unit_normalized,
        "method_class": method_class,
        "source_type": source_type,
        "source_ref": source_ref,
        "calculation": calculation,
        "dependency": dependency or {"source_cluster": None, "same_object_document_ids": []},
        "scope_caveats": sorted(set(scope_caveats)),
        "review_reasons": review_reasons,
        "requires_human_review": bool(review_reasons),
        "status": "REVIEW_REQUIRED" if review_reasons else "PROPOSED",
        "created_by": created_by,
        "input_hashes": input_hashes or {},
    }
    body["evidence_id"] = "QE-" + canonical_sha256(body)[:16]
    return body


def evidence_from_quantity_observation(qo, *, building_id, subject_id, building_link_ref, input_hashes=None,
                                       subject_key=None, mapping_ref=None):
    """Mapt een historische elementhoeveelheid (quantity observation) naar evidence voor een concreet gebouw.

    building_link_ref: verwijzing naar de menselijke beslissing dat dit document over dit gebouw gaat
    (tenant-/bronscheiding: nooit automatisch). Zonder die verwijzing geen evidence."""
    if not building_link_ref:
        raise QuantityEvidenceError("building_link_ref ontbreekt: de koppeling document -> gebouw is een menselijke stap")
    if qo.get("quantity_kind") != "ELEMENT_QUANTITY":
        raise QuantityEvidenceError("alleen ELEMENT_QUANTITY observations kunnen elementhoeveelheid-evidence worden")
    el = qo["element"]
    subject = {
        "subject_id": subject_id,
        "element_code_internal": el.get("element_code_internal"),
        "subject_text": el.get("element_description_original"),
        "location_scope": el.get("location_original"),
        "material_normalized": el.get("material_normalized"),
        "quantity_kind": "ELEMENT_QUANTITY",
    }
    if subject_key:
        subject["subject_key"] = subject_key
    reasons = list(qo.get("review_reasons", []))
    if not qo.get("measurable"):
        reasons.append("NOT_A_MEASURED_QUANTITY")
    return make_evidence(
        building_id=building_id, subject=subject, value=qo["quantity_value"], unit_normalized=qo["unit_normalized"],
        method_class="SOURCE_REPORTED", source_type="MJOP_ELEMENT_OVERVIEW",
        source_ref={"document_id": qo["document_id"], "quantity_observation_id": qo["quantity_observation_id"],
                    "source_sha256": (qo.get("source_file") or {}).get("sha256"), "provenance": qo.get("provenance"),
                    "quantity_as_stated": qo.get("quantity_as_stated"), "building_link_ref": building_link_ref,
                    "subject_mapping_ref": mapping_ref},
        dependency={"source_cluster": qo.get("source_cluster"),
                    "same_object_document_ids": (qo.get("dependency") or {}).get("same_object_document_ids", []),
                    "identical_in_same_object_documents": (qo.get("dependency") or {}).get("identical_in_same_object_documents", [])},
        scope_caveats=qo.get("caveats", []), review_reasons=reasons,
        created_by="build_quantity_observations/" + str(qo.get("extraction_method")), input_hashes=input_hashes,
    )


def evidence_errors(ev):
    errors = []
    body = {k: v for k, v in ev.items() if k != "evidence_id"}
    if ev.get("evidence_id") != "QE-" + canonical_sha256(body)[:16]:
        errors.append(f"{ev.get('evidence_id')}: evidence_id past niet bij de inhoud (record aangepast?)")
    if ev.get("method_class") not in METHOD_CLASSES:
        errors.append(f"{ev.get('evidence_id')}: onbekende method_class")
    return errors


# --------------------------------------------------------------------------
# Resolutie (append-only)
# --------------------------------------------------------------------------

def new_store():
    return {"store_version": RESOLUTION_STORE_VERSION,
            "description": ("Append-only menselijke beslissingen over hoeveelheden per (building_id, subject_id). "
                            "Nooit gemiddeld; zie docs/quantity_foundation_v1.md."),
            "append_only": True, "records": []}


def _next_id(store):
    n = max([int(r["resolution_id"].split("-")[1]) for r in store["records"]] + [0])
    return f"QRR-{n + 1:05d}"


def validate_resolution(record, evidence_index):
    """Controleert één record tegen de evidence. Bewaakt 'nooit middelen': de vastgelegde waarde is
    exact de waarde van precies één evidence-record."""
    errors = []
    rid = record.get("resolution_id", "?")
    dec_ = record.get("decision")
    considered = record.get("considered_evidence_ids") or []
    for eid in considered:
        ev = evidence_index.get(eid)
        if ev is None:
            errors.append(f"{rid}: onbekende evidence {eid}")
        elif (ev["building_id"], ev["quantity_subject"]["subject_id"]) != (record["building_id"], record["subject_id"]):
            errors.append(f"{rid}: evidence {eid} hoort bij een ander gebouw/onderwerp")
    if dec_ == "ACCEPT_EVIDENCE":
        sel = record.get("selected_evidence_id")
        ev = evidence_index.get(sel)
        if ev is None:
            errors.append(f"{rid}: selected_evidence_id ontbreekt of is onbekend")
        else:
            if sel not in considered:
                errors.append(f"{rid}: gekozen evidence staat niet in considered_evidence_ids")
            if _dec(record.get("resolved_value")) != _dec(ev["value"]) or record.get("resolved_unit") != ev["unit_normalized"]:
                errors.append(f"{rid}: resolved_value/unit wijkt af van de gekozen evidence (middelen/combineren is niet toegestaan)")
        if record.get("manual_evidence_id"):
            errors.append(f"{rid}: ACCEPT_EVIDENCE heeft geen manual_evidence_id")
    elif dec_ == "USER_VALUE":
        mev = evidence_index.get(record.get("manual_evidence_id"))
        if mev is None or mev["method_class"] != "MANUAL":
            errors.append(f"{rid}: USER_VALUE vereist een MANUAL-evidence (manual_evidence_id)")
        elif _dec(record.get("resolved_value")) != _dec(mev["value"]) or record.get("resolved_unit") != mev["unit_normalized"]:
            errors.append(f"{rid}: resolved_value/unit wijkt af van de MANUAL-evidence")
        if record.get("selected_evidence_id"):
            errors.append(f"{rid}: USER_VALUE heeft geen selected_evidence_id")
    elif dec_ == "UNKNOWN":
        if record.get("resolved_value") is not None or record.get("selected_evidence_id") or record.get("manual_evidence_id"):
            errors.append(f"{rid}: UNKNOWN legt geen waarde en geen evidence vast")
    else:
        errors.append(f"{rid}: onbekende decision {dec_!r}")
    if not (record.get("decision_reason") or "").strip():
        errors.append(f"{rid}: decision_reason is verplicht")
    if (record.get("reviewer") or {}).get("reviewer_type") != "human":
        errors.append(f"{rid}: reviewer_type moet 'human' zijn")
    return errors


def store_invariant_errors(store, evidence_index=None):
    """Unieke resolution_id; per (building_id, subject_id) hoogstens één ACTIVE; 'supersedes' verwijst naar
    een bestaand SUPERSEDED record van hetzelfde onderwerp; elk SUPERSEDED record is door precies één
    later record vervangen."""
    errors, by_id = [], {}
    for r in store["records"]:
        if r["resolution_id"] in by_id:
            errors.append(f"{r['resolution_id']}: resolution_id komt meer dan eens voor")
        by_id[r["resolution_id"]] = r
    active, superseded_by = {}, {}
    for r in store["records"]:
        key = (r["building_id"], r["subject_id"])
        if r["status"] == "ACTIVE":
            active.setdefault(key, []).append(r["resolution_id"])
        if r["supersedes"]:
            old = by_id.get(r["supersedes"])
            if old is None:
                errors.append(f"{r['resolution_id']}: supersedes verwijst naar onbekende {r['supersedes']}")
            elif (old["building_id"], old["subject_id"]) != key or old["status"] != "SUPERSEDED":
                errors.append(f"{r['resolution_id']}: vervangen record {old['resolution_id']} moet hetzelfde onderwerp hebben en SUPERSEDED zijn")
            superseded_by.setdefault(r["supersedes"], []).append(r["resolution_id"])
    for r in store["records"]:
        if r["status"] == "SUPERSEDED" and len(superseded_by.get(r["resolution_id"], [])) != 1:
            errors.append(f"{r['resolution_id']}: SUPERSEDED record moet door precies één later record vervangen zijn")
    errors += [f"{k[0]} / {k[1]}: meer dan één ACTIVE record ({', '.join(ids)})" for k, ids in sorted(active.items()) if len(ids) > 1]
    if evidence_index is not None:
        for r in store["records"]:
            errors += validate_resolution(r, evidence_index)
    return errors


def append_only_errors(old_store, new_store_):
    new = {r["resolution_id"]: r for r in new_store_["records"]}
    errors = []
    for r in old_store["records"]:
        n = new.get(r["resolution_id"])
        if n is None:
            errors.append(f"{r['resolution_id']}: record verwijderd")
            continue
        if {k: v for k, v in n.items() if k != "status"} != {k: v for k, v in r.items() if k != "status"}:
            errors.append(f"{r['resolution_id']}: record overschreven")
        if n["status"] != r["status"] and (r["status"], n["status"]) not in ALLOWED_STATUS_TRANSITIONS:
            errors.append(f"{r['resolution_id']}: statuswijziging {r['status']} -> {n['status']} niet toegestaan")
    return errors


def record_resolution(store, *, building_id, subject_id, decision, considered_evidence_ids, decision_reason,
                      reviewer_id, reviewed_at, evidence_index, selected_evidence_id=None, manual_evidence_id=None,
                      notes=None):
    """Voegt een menselijke beslissing toe (pure functie: geeft een nieuwe store terug). Een bestaand
    ACTIVE record voor hetzelfde onderwerp wordt SUPERSEDED; er wordt niets verwijderd of overschreven.
    De waarde komt uitsluitend uit de gekozen evidence of de MANUAL-evidence — nooit berekend."""
    out = copy.deepcopy(store)
    resolved_value = resolved_unit = None
    if decision == "ACCEPT_EVIDENCE":
        ev = evidence_index.get(selected_evidence_id)
        if ev is None:
            raise QuantityEvidenceError("selected_evidence_id onbekend")
        resolved_value, resolved_unit = ev["value"], ev["unit_normalized"]
    elif decision == "USER_VALUE":
        ev = evidence_index.get(manual_evidence_id)
        if ev is None:
            raise QuantityEvidenceError("manual_evidence_id onbekend")
        resolved_value, resolved_unit = ev["value"], ev["unit_normalized"]
    # Het geldende record (ACTIVE, of REVIEW_REQUIRED na gewijzigde invoer) wordt vervangen, niet verwijderd.
    previous = [r for r in out["records"] if r["building_id"] == building_id and r["subject_id"] == subject_id
                and r["status"] in ("ACTIVE", "REVIEW_REQUIRED")]
    if len(previous) > 1:
        raise QuantityEvidenceError(f"meer dan één geldend record voor {building_id} / {subject_id}")
    considered = sorted(set(considered_evidence_ids))
    record = {
        "resolution_id": _next_id(out),
        "building_id": building_id,
        "subject_id": subject_id,
        "decision": decision,
        "selected_evidence_id": selected_evidence_id if decision == "ACCEPT_EVIDENCE" else None,
        "manual_evidence_id": manual_evidence_id if decision == "USER_VALUE" else None,
        "resolved_value": resolved_value,
        "resolved_unit": resolved_unit,
        "considered_evidence_ids": considered,
        "decision_reason": decision_reason,
        "reviewer": {"reviewer_id": reviewer_id, "reviewer_type": "human"},
        "reviewed_at": reviewed_at,
        "rule_version": RESOLUTION_RULE_VERSION,
        "input_hashes": {"considered_evidence_sha256": canonical_sha256([evidence_index[e] for e in considered if e in evidence_index])},
        "notes": notes,
        "supersedes": previous[0]["resolution_id"] if previous else None,
        "status": "ACTIVE",
    }
    errors = validate_resolution(record, evidence_index)
    if errors:
        raise QuantityEvidenceError("; ".join(errors))
    for r in previous:
        r["status"] = "SUPERSEDED"
    out["records"].append(record)
    errors = store_invariant_errors(out, evidence_index) + append_only_errors(store, out)
    if errors:
        raise QuantityEvidenceError("; ".join(errors))
    return out


def mark_review_required(store, resolution_id):
    """Invoer veranderd (bijv. nieuwe evidence-versie): ACTIVE -> REVIEW_REQUIRED, record blijft bewaard."""
    out = copy.deepcopy(store)
    for r in out["records"]:
        if r["resolution_id"] == resolution_id:
            if r["status"] != "ACTIVE":
                raise QuantityEvidenceError(f"{resolution_id} is niet ACTIVE")
            r["status"] = "REVIEW_REQUIRED"
            return out
    raise QuantityEvidenceError(f"{resolution_id} onbekend")


def active_resolution(store, building_id, subject_id):
    act = [r for r in store["records"] if r["building_id"] == building_id and r["subject_id"] == subject_id
           and r["status"] == "ACTIVE"]
    return act[0] if act else None
