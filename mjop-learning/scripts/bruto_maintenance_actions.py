"""Maintenance Actions & Door Treatment v1: onderhoudshoeveelheidsvoorstellen uit een triage-reviewpack (puur, alleen lezen).

Bron is uitsluitend een bruto_review_pack_v2 (read-only; pack_id wordt herberekend). Uitvoer zijn voorlopige, niet-vrijgegeven
hoeveelheidsvoorstellen per onderhoudsactie. Geen prijs, geen kengetal, geen kosten, geen definitieve hoeveelheid, geen besluit, geen
FI-id, geen netwerk, geen eigen schrijfactie. null = onbekend, nooit nul. Binnenschilderwerk wordt nooit uit de buitenhoeveelheid afgeleid.
"""
import argparse
import json
import sys
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bruto_quantity_contracts as bq  # noqa: E402
import bruto_quantity_core as core  # noqa: E402
import bruto_triage as triage  # noqa: E402
import bruto_triage_contracts as tc  # noqa: E402

SCHEMAS = ("bruto_maintenance_request_v2", "bruto_maintenance_action_v2", "bruto_maintenance_pack_v2")
CLASSES = triage.CLASSES
RANK = triage.RANK
ACTIONS_VOCAB = bq.load_vocabulary("bruto_quantity_actions_v2")
VOCAB = bq.load_vocabulary("bruto_maintenance_rules_v2")
RULES = {r["rule_id"]: r for r in VOCAB["rules"]}
VOC_ACTION = {a["action_id"]: a for a in ACTIONS_VOCAB["actions"]}
AREA_ACTIONS = ("EXTERIOR_PAINTING", "INTERIOR_PAINTING", "FRAME_MAINTENANCE", "FRAME_REPLACEMENT")
DOOR_ACTIONS = ("DOOR_MAINTENANCE", "DOOR_REPLACEMENT")
PAIRS = {frozenset(p) for p in VOCAB["overlapping_work_pairs"]}
INVARIANTS = OrderedDict([("release_state", "NOT_RELEASED"), ("usable_for_mjop", False), ("decisions_registered", False), ("approvals_simulated", False),
                          ("fi_ids_created", False), ("confirmed_output", False), ("final_quantities", False), ("price_calculated", False),
                          ("cost_calculated", False), ("kengetal_linked", False), ("combined_total_across_actions", None), ("network_used", False)])
NOTES = ["Voorlopige onderhoudshoeveelheidsvoorstellen; geen prijs, kengetal, kosten, MJOP-regel of definitieve hoeveelheid.",
         "Voorstellen zijn niet optelbaar: overlappende acties delen objecten (overlap_group); er is geen totaal over acties.",
         "Binnenschilderwerk blijft onbekend zolang binnenscope en meetgrondslag niet zijn vastgesteld."]


def _store():
    names = bq.SCHEMA_NAMES + tc.TRIAGE_SCHEMAS + SCHEMAS
    return {f"{n}.schema.json": bq.load_schema(n) for n in names}


def schema_errors(instance, name):
    schema = bq.load_schema(name)
    resolver = jsonschema.RefResolver(base_uri=f"{name}.schema.json", referrer=schema, store=_store())
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}"
                  for e in jsonschema.Draft7Validator(schema, resolver=resolver).iter_errors(instance))


def _finding(rule_id, action_ids, object_ids, detail):
    r = RULES[rule_id]
    return OrderedDict([("finding_id", ""), ("rule_id", rule_id), ("class", r["class"]), ("action_ids", sorted(set(action_ids))),
                        ("object_ids", sorted(set(object_ids))), ("detail", detail)])


def _worst(classes):
    return max(classes, key=lambda c: RANK[c], default="CLEAN_PROVISIONAL")


def _check_pack(pack):
    errs = tc.pack_errors(pack)
    if errs:
        raise core.BrutoError("SOURCE_PACK_INVALID", "; ".join(errs[:3]))
    expect = "BRP-" + core.canonical_sha256({k: v for k, v in pack.items() if k != "pack_id"})[:16]
    if expect != pack["pack_id"]:
        raise core.BrutoError("SOURCE_PACK_TAMPERED", "pack_id komt niet overeen met de inhoud")


def _validate_request(r, objs):
    t, basis = r["action_type"], r["measurement_basis"]
    if t == "INTERIOR_PAINTING" and basis in ("GROSS_FRAME_AREA_OUTER", "DOOR_PIECES"):
        raise core.BrutoError("INTERIOR_FROM_EXTERIOR_FORBIDDEN", f"{r['action_id']}: binnenschilderwerk mag niet op buitenoppervlak of stuks worden gegrond")
    if t in DOOR_ACTIONS and basis in ("GROSS_FRAME_AREA_OUTER",):
        raise core.BrutoError("BASIS_ACTION_MISMATCH", f"{r['action_id']}: deuractie met m2-grondslag is niet toegestaan")
    if t in AREA_ACTIONS and basis == "DOOR_PIECES":
        raise core.BrutoError("BASIS_ACTION_MISMATCH", f"{r['action_id']}: kozijnactie met stuksgrondslag voor deuren is niet toegestaan")
    if basis == "HISTORICAL_SOURCE_BASIS" and not r["basis_source_ref"]:
        raise core.BrutoError("BASIS_SOURCE_MISSING", f"{r['action_id']}: historische grondslag vereist basis_source_ref")
    for oid in r["object_ids"]:
        o = objs.get(oid)
        if o is None:
            raise core.BrutoError("SCOPE_OBJECT_UNKNOWN", f"{r['action_id']}: object {oid} staat niet in het bronpack")
        if t in DOOR_ACTIONS and o["object_category"] == "FRAME":
            raise core.BrutoError("SCOPE_CATEGORY_MISMATCH", f"{r['action_id']}: deuractie op kozijn zonder deur ({oid})")


def _doors(o):
    return o["quantity"] if o["object_category"] in ("DOOR", "FRAME_WITH_DOOR") else 0


def _area(o):
    d = o["dimension"]
    return Decimal(d["gross_area_m2_exact"]) if d["gross_area_m2_exact"] is not None else None


def _proposal(r, objs, pack):
    t, tr = r["action_type"], r["door_treatment"]
    va = VOC_ACTION[VOCAB["action_types"][t]["vocabulary_action_id"]]
    scope = [objs[i] for i in sorted(r["object_ids"])]
    finds = []
    aid = r["action_id"]
    # meetgrondslag
    basis, bstatus, unit = va["measurement_basis"], va["measurement_basis_status"], va["quantity_unit"]
    if r["measurement_basis"] is not None:
        basis, bstatus = r["measurement_basis"], "REQUESTED"
        unit = {"GROSS_FRAME_AREA_OUTER": "m2", "DOOR_PIECES": "stuks"}.get(basis)
    prov = OrderedDict([("derivation", ""), ("per_object", []), ("area_classes", []), ("triage_calibration_status", pack["calibration"]["effective_status"]), ("source_class", "CLEAN_PROVISIONAL")])
    qty, status, door_area, door_pcs = None, "UNKNOWN", False, None
    ids = [o["object_id"] for o in scope]
    axis = "identity_axis" if unit == "stuks" else None
    cls = [(o["identity_axis"]["class"] if axis else o["overall_class"]) for o in scope]
    prov["source_class"] = _worst(cls)
    if "CONFLICT" in cls:
        finds.append(_finding("M-C2", [aid], [o["object_id"] for o, c in zip(scope, cls) if c == "CONFLICT"], "bronobject door de triage geblokkeerd"))
        status, prov["derivation"] = "BLOCKED_BY_CONFLICT", "geen hoeveelheid: bronconflict"
    elif unit is None:
        finds.append(_finding("M-I1", [aid], ids, f"meetgrondslag {basis}; hoeveelheid niet berekenbaar"))
        prov["derivation"] = "geen hoeveelheid: meetgrondslag niet vastgesteld"
    elif unit == "stuks":
        if tr == "UNDECIDED" or tr == "PART_OF_GROSS_FRAME_AREA":
            finds.append(_finding("M-R3", [aid], ids, f"deurbehandeling {tr} past niet bij een stuksactie; geen onderhoudshoeveelheid"))
            door_pcs = sum(_doors(o) for o in scope)
            prov["derivation"] = "deuren worden alleen in stuks geregistreerd; geen onderhoudshoeveelheid"
            status = "UNKNOWN"
        elif tr == "NOT_RELEVANT":
            prov["derivation"] = "deuren niet relevant voor deze actie; geen hoeveelheid"
        elif "INSUFFICIENT_EVIDENCE" in cls:
            finds.append(_finding("M-I3", [aid], [o["object_id"] for o, c in zip(scope, cls) if c == "INSUFFICIENT_EVIDENCE"], "telling onvoldoende onderbouwd"))
            prov["derivation"] = "geen hoeveelheid: identiteit onvoldoende"
        else:
            n = sum(_doors(o) for o in scope)
            door_pcs = n
            qty = (Decimal(n), "stuks")
            prov["derivation"] = "aantal deuren: som van quantity van deur- en kozijn-met-deurobjecten"
            prov["per_object"] = [OrderedDict([("object_id", o["object_id"]), ("counted", _doors(o) > 0), ("pieces", _doors(o))]) for o in scope]
            status = "KNOWN_SUPPORTED" if _worst(cls) == "CLEAN_PROVISIONAL" else "PROVISIONAL_CALCULATED"
    else:
        counted, notes = [], []
        for o in scope:
            if o["object_category"] == "DOOR":
                if tr == "PART_OF_GROSS_FRAME_AREA":
                    counted.append(o)
                    door_area = True
                else:
                    notes.append((o["object_id"], False, f"losse deur niet in m2 bij behandeling {tr}"))
            else:
                counted.append(o)
                if o["object_category"] == "FRAME_WITH_DOOR":
                    door_area = True
        door_objs = [o["object_id"] for o in scope if o["object_category"] in ("DOOR", "FRAME_WITH_DOOR")]
        if door_objs and tr == "UNDECIDED":
            finds.append(_finding("M-R3", [aid], door_objs, "deurbehandeling UNDECIDED terwijl de scope deuren bevat"))
        if tr == "AS_PIECES" and any(o["object_category"] == "FRAME_WITH_DOOR" for o in scope):
            finds.append(_finding("M-R4", [aid], [o["object_id"] for o in scope if o["object_category"] == "FRAME_WITH_DOOR"], "deur zit in het bruto m2 maar wordt in stuks gevraagd"))
        if any(c == "INSUFFICIENT_EVIDENCE" for c in [o["identity_axis"]["class"] for o in counted]):
            finds.append(_finding("M-I3", [aid], [o["object_id"] for o in counted if o["identity_axis"]["class"] == "INSUFFICIENT_EVIDENCE"], "telling onvoldoende onderbouwd"))
            prov["derivation"] = "geen hoeveelheid: identiteit onvoldoende"
        elif any(_area(o) is None for o in counted):
            finds.append(_finding("M-I2", [aid], [o["object_id"] for o in counted if _area(o) is None], "bruto oppervlak onbekend (null)"))
            prov["derivation"] = "geen hoeveelheid: minstens één bruto oppervlak onbekend; onbekend is niet nul"
        else:
            total = sum((_area(o) for o in counted), Decimal(0))
            qty = (total, "m2")
            acls = sorted({o["dimension"]["area_class"] for o in counted})
            prov["area_classes"] = acls
            prov["derivation"] = "som van eigen bruto buitenoppervlak per object (breedte x hoogte x aantal); glas niet afgetrokken, draaiende delen niet apart; typemaat nooit gebruikt"
            prov["per_object"] = [OrderedDict([("object_id", o["object_id"]), ("counted", True), ("area_class", o["dimension"]["area_class"]),
                                               ("gross_area_m2_exact", o["dimension"]["gross_area_m2_exact"])]) for o in counted]
            prov["per_object"] += [OrderedDict([("object_id", i), ("counted", c), ("note", n)]) for i, c, n in notes]
            if "ESTIMATED" in acls:
                status = "ESTIMATED"
                finds.append(_finding("M-N1", [aid], [o["object_id"] for o in counted if o["dimension"]["area_class"] == "ESTIMATED"], "geschat bruto oppervlak, niet bevestigd"))
            else:
                status = "KNOWN_SUPPORTED" if _worst(cls) == "CLEAN_PROVISIONAL" else "PROVISIONAL_CALCULATED"
        for o in scope:
            if any(x["rule_id"] == "B-R2" for x in o["dimension_axis"]["reasons"]):
                finds.append(_finding("M-N3", [aid], [o["object_id"]], "eigen maat gebruikt; afwijking van typegroep"))
    if status in ("UNKNOWN", "BLOCKED_BY_CONFLICT"):
        qty = None
    if prov["source_class"] != "CLEAN_PROVISIONAL" and qty is not None:
        finds.append(_finding("M-R6", [aid], [o["object_id"] for o, c in zip(scope, cls) if c != "CLEAN_PROVISIONAL"], "brontriage is niet CLEAN_PROVISIONAL"))
        if status == "KNOWN_SUPPORTED":
            status = "PROVISIONAL_CALCULATED"
    # pieces-actie: area_classes leeg; dimensies spelen geen rol
    q = None
    if qty is not None:
        q = OrderedDict([("value_exact", core.fmt_exact(qty[0])), ("value_presented", core.present(qty[0]) if qty[1] == "m2" else str(int(qty[0]))), ("unit", qty[1])])
    return OrderedDict([
        ("contract_version", "bruto_maintenance_action_v2"), ("action_id", aid), ("action_type", t), ("vocabulary_action_id", va["action_id"]),
        ("element_category", va["object_scope"]), ("quantity_unit", unit), ("measurement_basis", basis), ("measurement_basis_status", bstatus),
        ("door_treatment", tr), ("scope", OrderedDict([("object_ids", ids), ("door_area_included", door_area and unit == "m2" and q is not None),
                                                      ("door_pieces_registered", door_pcs)])),
        ("source_quantity_ref", OrderedDict([("source_contract", "bruto_review_pack_v2"), ("pack_id", pack["pack_id"]),
                                             ("baseline_state_id", pack["baseline_state"]["state_id"]), ("object_ids", ids)])),
        ("source_quantity_status", status), ("proposed_quantity", q), ("quantity_provenance", prov), ("review_status", "CLEAN_PROVISIONAL"),
        ("finding_ids", []), ("overlap_group", ""), ("additive", False), ("release_state", "NOT_RELEASED"), ("is_final_quantity", False),
        ("usable_for_mjop", False), ("price_link", None), ("kengetal_link", None)]), finds


def propose(pack, requests_doc):
    """Geeft het onderhoudsvoorstelpack (dict). Deterministisch; wijzigt de invoer niet."""
    _check_pack(pack)
    errs = schema_errors(requests_doc, "bruto_maintenance_request_v2")
    if errs:
        raise core.BrutoError("REQUEST_SCHEMA_INVALID", "; ".join(errs[:3]))
    reqs = sorted(requests_doc["requests"], key=lambda r: r["action_id"])
    if len({r["action_id"] for r in reqs}) != len(reqs):
        raise core.BrutoError("DUPLICATE_ACTION_ID", "action_id komt meer dan eens voor")
    objs = {o["object_id"]: o for o in pack["objects"]}
    for r in reqs:
        _validate_request(r, objs)
    built = [_proposal(r, objs, pack) for r in reqs]
    props = [b[0] for b in built]
    finds = [f for b in built for f in b[1]]
    # overlap tussen acties
    for i in range(len(reqs)):
        for j in range(i + 1, len(reqs)):
            a, b = reqs[i], reqs[j]
            shared = sorted(set(a["object_ids"]) & set(b["object_ids"]))
            if not shared:
                continue
            ids = [a["action_id"], b["action_id"]]
            if a["action_type"] == b["action_type"]:
                if set(a["object_ids"]) == set(b["object_ids"]):
                    finds.append(_finding("M-C1", ids, shared, f"{a['action_type']} twee keer met dezelfde scope"))
                else:
                    finds.append(_finding("M-R1", ids, shared, f"{a['action_type']} met gedeeltelijk overlappende scope"))
            elif frozenset((a["action_type"], b["action_type"])) in PAIRS:
                finds.append(_finding("M-R2", ids, shared, f"{a['action_type']} en {b['action_type']} kunnen hetzelfde werk insluiten"))
            else:
                finds.append(_finding("M-N2", ids, shared, f"{a['action_type']} en {b['action_type']}: geldige aparte registraties voor verschillend werk"))
    # mogelijk dubbele objecten (uit de triage-scenario's)
    for s in pack["scenarios"]:
        if s["kind"] != "DUPLICATE_PAIR_IF_SAME_OBJECT":
            continue
        for r in reqs:
            if set(s["object_ids"]) <= set(r["object_ids"]):
                finds.append(_finding("M-R5", [r["action_id"]], s["object_ids"], "twee objecten in de scope kunnen hetzelfde fysieke object zijn"))
    # ontdubbelen en nummeren
    uniq = {}
    for f in finds:
        uniq[(f["rule_id"], tuple(f["action_ids"]), tuple(f["object_ids"]), f["detail"])] = f
    finds = sorted(uniq.values(), key=lambda f: (f["rule_id"], f["action_ids"], f["object_ids"], f["detail"]))
    for n, f in enumerate(finds, 1):
        f["finding_id"] = f"MF-{n:03d}"
    # gevolgen van bevindingen op voorstellen
    for p in props:
        mine = [f for f in finds if p["action_id"] in f["action_ids"]]
        p["finding_ids"] = [f["finding_id"] for f in mine]
        classes = [p["quantity_provenance"]["source_class"]] + [f["class"] for f in mine if f["class"] != "INFO"]
        p["review_status"] = _worst(classes)
        if any(f["class"] == "CONFLICT" for f in mine):
            p["source_quantity_status"], p["proposed_quantity"] = "BLOCKED_BY_CONFLICT", None
            p["scope"]["door_area_included"] = False
        if p["source_quantity_status"] == "KNOWN_SUPPORTED" and p["review_status"] != "CLEAN_PROVISIONAL":
            p["source_quantity_status"] = "PROVISIONAL_CALCULATED"
    # overlapgroepen (niet optelbaar)
    og = triage._uf_groups([r["object_ids"] for r in reqs])
    for p, r in zip(props, reqs):
        p["overlap_group"] = og[sorted(r["object_ids"])[0]]
    cnt = lambda key, vals: OrderedDict((v, sum(1 for p in props if p[key] == v)) for v in vals)  # noqa: E731
    out = OrderedDict([
        ("contract_version", "bruto_maintenance_pack_v2"), ("pack_id", ""),
        ("source", OrderedDict([("pack_id", pack["pack_id"]), ("baseline_state_id", pack["baseline_state"]["state_id"]),
                                ("calibration_effective_status", pack["calibration"]["effective_status"]),
                                ("request_sha256", core.canonical_sha256({"requests": reqs}))])),
        ("invariants", OrderedDict(INVARIANTS)), ("proposals", props), ("findings", finds),
        ("summary", OrderedDict([("proposal_count", len(props)), ("by_review_status", cnt("review_status", CLASSES)),
                                 ("by_source_quantity_status", cnt("source_quantity_status", ("KNOWN_SUPPORTED", "PROVISIONAL_CALCULATED", "ESTIMATED", "UNKNOWN", "BLOCKED_BY_CONFLICT"))),
                                 ("finding_count", len(finds))])),
        ("notes", list(NOTES))])
    out = json.loads(json.dumps(out))
    out["pack_id"] = "BMP-" + core.canonical_sha256({k: v for k, v in out.items() if k != "pack_id"})[:16]
    perrs = schema_errors(out, "bruto_maintenance_pack_v2")
    if perrs:
        raise core.BrutoError("MAINTENANCE_PACK_SCHEMA_INVALID", "; ".join(perrs[:3]))
    return out


def pack_json(pack):
    return json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bouw onderhoudsvoorstellen uit een reviewpack-JSON en een verzoekbestand. Schrijft nooit in de repository.")
    ap.add_argument("review_pack")
    ap.add_argument("requests")
    ap.add_argument("--out-dir")
    a = ap.parse_args(argv)
    pack = json.loads(Path(a.review_pack).read_text(encoding="utf-8"))
    res = propose(pack, json.loads(Path(a.requests).read_text(encoding="utf-8")))
    if not a.out_dir:
        sys.stdout.write(pack_json(res))
        return 0
    out = Path(a.out_dir).resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit("weigert te schrijven binnen de repository")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{res['pack_id']}.json").write_text(pack_json(res), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
