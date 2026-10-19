"""Bruto Quantity Model v2: zuivere, deterministische rekenkern (fase 2).

Pure functies zonder neveneffecten: geen bestandstoegang, geen netwerk, geen klok, geen willekeur. Alle invoer komt als
argumenten binnen; alle uitvoer is een nieuw dict. Contract: vocabularies/bruto_quantity_concepts_v2.json en
schemas/bruto_*_v2.schema.json (laden en schemavalidatie staan in scripts/bruto_quantity_contracts.py).

Methode GROSS_FRAME_AREA_OUTER_V2: gross_area_m2 = outer_width_m * outer_height_m * quantity. Glas wordt niet afgetrokken,
vaste en draaiende delen vallen binnen de buitenmaat en tellen niet extra. Alleen Decimal; intern altijd exact, afronden
alleen bij presentatie (ROUND_HALF_UP_2DP_LARGEST_REMAINDER_V1).

Wat deze module NIET doet: geen besluit registreren, geen goedkeuring simuleren, geen FI-id aanmaken, geen v1-store lezen of
schrijven, geen prijs-, kengetal- of kostenkoppeling. De staat zet zichzelf nooit op een definitieve status.
"""
import hashlib
import json
from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

MIN_DIMENSION_M = Decimal("0.10")
MAX_DIMENSION_M = Decimal("10")
CENT = Decimal("0.01")
_DEC_PREC = 60

OBJECT_CATEGORIES = ("FRAME", "FRAME_WITH_DOOR", "DOOR")
FRAME_CATEGORIES = ("FRAME", "FRAME_WITH_DOOR")
DIMENSION_STATUSES = ("MEASURED", "DRAWING_DERIVED", "REFERENCE_DERIVED_ESTIMATE", "UNKNOWN")
RELIABLE_REFERENCE_STATUSES = ("MEASURED", "DRAWING_DERIVED")
COMPARABILITY_BASES = ("SAME_TYPE_CLASSIFICATION", "SAME_MATERIAL", "SIMILAR_VISIBLE_PROPORTIONS", "SAME_FACADE_SECTION",
                       "DEMONSTRATED_REPETITION")
PROPOSAL_ORIGINS = ("AI_PROPOSAL", "RULE", "HUMAN_PROPOSAL")
DOOR_TREATMENTS = ("PART_OF_GROSS_FRAME_AREA", "AS_PIECES", "NOT_RELEVANT", "UNDECIDED")
LAYERS = ("PROVISIONAL_UNIQUE", "CONFIRMED", "ESTIMATED", "REVIEW_LOW_CERTAINTY")
CONFIRMED_REQUIRES_LEVELS = ("A", "C")
METHOD = OrderedDict([("method_id", "GROSS_FRAME_AREA_OUTER_V2"),
                      ("formula", "gross_area_m2 = outer_width_m * outer_height_m * quantity"),
                      ("rounding_rule_id", "ROUND_HALF_UP_2DP_LARGEST_REMAINDER_V1"), ("includes_glass", True),
                      ("glass_area_deducted", False), ("movable_parts_added_separately", False)])
INVARIANTS = OrderedDict([("is_instance", False), ("fi_ids_created", False), ("decisions_registered", False),
                          ("approvals_simulated", False), ("price_link", None), ("kengetal_link", None), ("cost_link", None),
                          ("v1_contracts_modified", False)])


class BrutoError(Exception):
    """Een component weigert expliciet; er wordt nooit een gegokte waarde teruggegeven."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


def canonical_sha256(obj):
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# Decimal-rekenen
# --------------------------------------------------------------------------

def parse_decimal(value, what="waarde"):
    """Strikte Decimal uit een string. Floats, bools, NaN/Infinity en negatieve waarden worden geweigerd."""
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)) or isinstance(value, float):
        raise BrutoError("DECIMAL_REQUIRED", f"{what}: Decimal-string verwacht, kreeg {type(value).__name__}")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError):
        raise BrutoError("DECIMAL_REQUIRED", f"{what}: geen geldige Decimal: {value!r}")
    if not d.is_finite():
        raise BrutoError("DECIMAL_REQUIRED", f"{what}: niet eindig: {value!r}")
    return d


def valid_dimension(width, height):
    """Positieve, realistische buitenmaten (0.10 t/m 10 m). Geeft (Decimal, Decimal) of weigert."""
    w, h = parse_decimal(width, "outer_width_m"), parse_decimal(height, "outer_height_m")
    for name, d in (("outer_width_m", w), ("outer_height_m", h)):
        if not (MIN_DIMENSION_M <= d <= MAX_DIMENSION_M):
            raise BrutoError("DIMENSION_OUT_OF_RANGE", f"{name} {d} valt buiten {MIN_DIMENSION_M}..{MAX_DIMENSION_M} m")
    return w, h


def gross_area_exact(width, height, quantity):
    """gross_area_m2 = outer_width_m * outer_height_m * quantity, exact (geen afronding, geen aftrek van glas)."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise BrutoError("QUANTITY_INVALID", f"quantity moet een geheel getal >= 1 zijn, kreeg {quantity!r}")
    w, h = valid_dimension(width, height)
    with localcontext() as ctx:
        ctx.prec = _DEC_PREC
        return w * h * quantity


def fmt_exact(d):
    """Exacte waarde als canonieke Decimal-string zonder overbodige nullen (1.20 x 1.50 -> '1.8'); geen afronding."""
    return format(d.normalize(), "f")


def present(d):
    """Presentatieafronding van een los bedrag: 2 decimalen, half-up."""
    return format(d.quantize(CENT, rounding=ROUND_HALF_UP), "f")


def allocate_presented(items):
    """items: lijst (sleutel, exacte Decimal) in vaste volgorde. Geeft (totaal_gepresenteerd, {sleutel: gepresenteerd}).

    Het totaal wordt uit de exacte som afgerond; de deelbedragen worden afgerond op centen en met de grootste-restmethode
    zo gecorrigeerd dat ze exact optellen tot het afgeronde totaal. Bij gelijke rest wint de eerste sleutel."""
    with localcontext() as ctx:
        ctx.prec = _DEC_PREC
        total = sum((v for _, v in items), Decimal(0))
        total_c = int((total.quantize(CENT, rounding=ROUND_HALF_UP) / CENT).to_integral_value())
        floors = [(k, int((v / CENT).to_integral_value(rounding="ROUND_FLOOR")), (v / CENT) - (v / CENT).to_integral_value(rounding="ROUND_FLOOR"))
                  for k, v in items]
        short = total_c - sum(f for _, f, _ in floors)
        order = sorted(range(len(floors)), key=lambda i: (-floors[i][2], i))
        extra = {i: 0 for i in range(len(floors))}
        if short < 0 or short > len(floors):
            raise BrutoError("ALLOCATION_ERROR", "afrondingsverdeling niet mogelijk")
        for i in order[:short]:
            extra[i] = 1
        out = {floors[i][0]: present(Decimal(floors[i][1] + extra[i]) * CENT) for i in range(len(floors))}
        return present(Decimal(total_c) * CENT), out


# --------------------------------------------------------------------------
# Maatvoering
# --------------------------------------------------------------------------

def area_class(dim):
    """KNOWN (MEASURED/DRAWING_DERIVED), ESTIMATED (REFERENCE_DERIVED_ESTIMATE) of UNKNOWN."""
    status = dim.get("dimension_status")
    if status in RELIABLE_REFERENCE_STATUSES:
        return "KNOWN"
    if status == "REFERENCE_DERIVED_ESTIMATE":
        return "ESTIMATED"
    if status == "UNKNOWN":
        return "UNKNOWN"
    raise BrutoError("DIMENSION_STATUS_INVALID", f"onbekende dimension_status {status!r}")


def dimension_problems(dim):
    """Semantische controle bovenop het schema. Lege lijst = geldig."""
    errs = []
    status = dim.get("dimension_status")
    if status not in DIMENSION_STATUSES:
        return [f"dimension_status {status!r} niet toegestaan"]
    w, h = dim.get("outer_width_m"), dim.get("outer_height_m")
    if status == "UNKNOWN":
        if w is not None or h is not None:
            errs.append("UNKNOWN vereist outer_width_m en outer_height_m = null")
        if dim.get("estimate") is not None:
            errs.append("UNKNOWN mag geen estimate bevatten")
        return errs
    try:
        valid_dimension(w, h)
    except BrutoError as e:
        errs.append(e.message)
    if status == "DRAWING_DERIVED" and not dim.get("scale_evidence_ref"):
        errs.append("DRAWING_DERIVED vereist scale_evidence_ref")
    est = dim.get("estimate")
    if status == "REFERENCE_DERIVED_ESTIMATE":
        if not isinstance(est, dict):
            errs.append("REFERENCE_DERIVED_ESTIMATE vereist een estimate-blok")
        else:
            if est.get("estimate_status") != "ESTIMATED":
                errs.append("estimate_status moet ESTIMATED zijn")
            if est.get("validated_measure") is not False:
                errs.append("een schatting is nooit een gevalideerde maat")
            if not est.get("comparability_reason") or len(est["comparability_reason"]) < 10:
                errs.append("comparability_reason ontbreekt")
            if not est.get("original_measure_sources"):
                errs.append("original_measure_sources ontbreekt")
            if not est.get("reference_type_id") or not est.get("reference_ids"):
                errs.append("verwijzing naar het referentietype ontbreekt")
    elif est is not None:
        errs.append("estimate alleen toegestaan bij REFERENCE_DERIVED_ESTIMATE")
    return errs


def _median(values):
    vals = sorted(values)
    n = len(vals)
    with localcontext() as ctx:
        ctx.prec = _DEC_PREC
        return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def derive_estimate(reference_type, *, target_category, comparability_basis, comparability_reason, proposal_origin,
                    reference_ids=None, target_type=None):
    """Leidt een geschatte maat af van betrouwbare referentiematen van een vergelijkbaar kozijntype.

    Alleen referenties met status MEASURED/DRAWING_DERIVED tellen (geen schatting van een schatting). Weigert zonder
    betrouwbare referentie, zonder onderbouwde vergelijkbaarheid of bij een categorie-/materiaal-/classificatieconflict.
    Eén referentie: COPY_SINGLE_REFERENCE_V1. Meerdere: MEDIAN_OF_REFERENCES_V1 (mediaan per maat, spreiding bewaard).
    Resultaat: dimension-record met status REFERENCE_DERIVED_ESTIMATE; nooit een gevalideerde maat."""
    if proposal_origin not in PROPOSAL_ORIGINS:
        raise BrutoError("ESTIMATE_PROPOSAL_ORIGIN_INVALID", f"proposal_origin {proposal_origin!r}")
    bases = list(comparability_basis or [])
    if not bases or len(set(bases)) != len(bases) or any(b not in COMPARABILITY_BASES for b in bases):
        raise BrutoError("ESTIMATE_COMPARABILITY_MISSING", "geldige comparability_basis (uniek, uit het vocabulaire) is verplicht")
    if not isinstance(comparability_reason, str) or len(comparability_reason.strip()) < 10:
        raise BrutoError("ESTIMATE_COMPARABILITY_MISSING", "comparability_reason (minimaal 10 tekens) is verplicht")
    if reference_type.get("object_category") != target_category:
        raise BrutoError("ESTIMATE_CATEGORY_MISMATCH", "referentietype heeft een andere objectcategorie dan het doelobject")
    if target_type is not None:
        if "SAME_TYPE_CLASSIFICATION" in bases and reference_type.get("type_classification") != target_type.get("type_classification"):
            raise BrutoError("ESTIMATE_COMPARABILITY_CONFLICT", "SAME_TYPE_CLASSIFICATION opgegeven maar classificaties verschillen")
        if "SAME_MATERIAL" in bases:
            m1, m2 = reference_type.get("material"), target_type.get("material")
            if "UNKNOWN" in (m1, m2) or m1 != m2:
                raise BrutoError("ESTIMATE_COMPARABILITY_CONFLICT", "SAME_MATERIAL opgegeven maar materiaal onbekend of verschillend")
    elif "SAME_TYPE_CLASSIFICATION" in bases or "SAME_MATERIAL" in bases:
        raise BrutoError("ESTIMATE_COMPARABILITY_CONFLICT", "SAME_TYPE_CLASSIFICATION/SAME_MATERIAL vereist het doeltype")
    refs = reference_type.get("reference_dimensions", [])
    by_id = {r["reference_id"]: r for r in refs}
    wanted = list(reference_ids) if reference_ids is not None else [r["reference_id"] for r in refs
                                                                   if r["dimension"].get("dimension_status") in RELIABLE_REFERENCE_STATUSES]
    if len(set(wanted)) != len(wanted):
        raise BrutoError("ESTIMATE_REFERENCE_INVALID", "reference_ids bevat dubbelen")
    if not wanted:
        raise BrutoError("ESTIMATE_NO_RELIABLE_REFERENCE", "geen betrouwbare referentiemaat (MEASURED/DRAWING_DERIVED) beschikbaar")
    picked = []
    for rid in wanted:
        r = by_id.get(rid)
        if r is None:
            raise BrutoError("ESTIMATE_REFERENCE_INVALID", f"referentie {rid} bestaat niet in het referentietype")
        d = r["dimension"]
        if d.get("dimension_status") not in RELIABLE_REFERENCE_STATUSES:
            raise BrutoError("ESTIMATE_NO_RELIABLE_REFERENCE", f"referentie {rid} is niet betrouwbaar (status {d.get('dimension_status')}); geen schattingsketens")
        probs = dimension_problems(d)
        if probs:
            raise BrutoError("ESTIMATE_REFERENCE_INVALID", f"referentie {rid}: {'; '.join(probs)}")
        picked.append((rid, d))
    ws = [parse_decimal(d["outer_width_m"]) for _, d in picked]
    hs = [parse_decimal(d["outer_height_m"]) for _, d in picked]
    if len(picked) == 1:
        method, w, h = "COPY_SINGLE_REFERENCE_V1", ws[0], hs[0]
    else:
        method, w, h = "MEDIAN_OF_REFERENCES_V1", _median(ws), _median(hs)
    w, h = valid_dimension(format(w, "f"), format(h, "f"))
    spread_w, spread_h = max(ws) - min(ws), max(hs) - min(hs)
    sources = []
    for _, d in picked:
        if d["source"] not in sources:
            sources.append(json.loads(json.dumps(d["source"])))
    return OrderedDict([
        ("outer_width_m", format(w, "f")), ("outer_height_m", format(h, "f")), ("dimension_basis", "OUTER_FRAME"),
        ("dimension_status", "REFERENCE_DERIVED_ESTIMATE"), ("measurement_method", "TYPE_REFERENCE_DERIVATION"),
        ("source", OrderedDict([("source_kind", "TYPE_REFERENCE"), ("source_id", reference_type["type_id"]), ("recorded_at", None),
                                ("recorded_by", None), ("authentication", "NONE_SELF_ASSERTED")])),
        ("scale_evidence_ref", None), ("validated_reference_ref", None),
        ("uncertainty", OrderedDict([("absolute_m", format(max(spread_w, spread_h), "f")), ("note", "spreiding tussen referenties")])),
        ("estimate", OrderedDict([
            ("estimate_status", "ESTIMATED"), ("proposal_origin", proposal_origin), ("reference_type_id", reference_type["type_id"]),
            ("reference_ids", [rid for rid, _ in picked]), ("original_measure_sources", sources),
            ("comparability_basis", bases), ("comparability_reason", comparability_reason.strip()), ("derivation_method", method),
            ("uncertainty", OrderedDict([("reference_count", len(picked)), ("spread_width_m", format(spread_w, "f")),
                                         ("spread_height_m", format(spread_h, "f")), ("note", None)])),
            ("deviations", []), ("validated_measure", False)]))])


# --------------------------------------------------------------------------
# Goedkeuringsverificatie (geen simulatie)
# --------------------------------------------------------------------------

class NullApprovalVerifier:
    """Standaard: er bestaat geen geauthenticeerde goedkeuringsbron; elke goedkeuring is niet geverifieerd."""
    name = "NullApprovalVerifier"
    provides_verified_approvals = False

    def verify(self, obj, level):
        return False


def _verified(verifier, obj, level):
    claims = [a for a in obj.get("approval_refs", []) if a.get("level") == level]
    if not claims:
        return False
    try:
        return verifier.verify(obj, level) is True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Lagen
# --------------------------------------------------------------------------

def classify_layer(obj, verifier=None):
    """Afgeleide laag van een object. Het record zelf kan zijn laag niet opgeven.

    ESTIMATED_MISSING -> ESTIMATED (nooit CONFIRMED). OBSERVED: CONFIRMED alleen als de verifier goedkeuring A en C bevestigt;
    anders PROVISIONAL_UNIQUE bij voorgestelde consolidatie met zekerheid HIGH; anders REVIEW_LOW_CERTAINTY."""
    verifier = verifier or NullApprovalVerifier()
    if obj["object_origin"] == "ESTIMATED_MISSING":
        return "ESTIMATED"
    if getattr(verifier, "provides_verified_approvals", False) is True and all(
            _verified(verifier, obj, lv) for lv in CONFIRMED_REQUIRES_LEVELS):
        return "CONFIRMED"
    cons = obj.get("consolidation")
    if cons and cons.get("certainty") == "HIGH":
        return "PROVISIONAL_UNIQUE"
    return "REVIEW_LOW_CERTAINTY"


def object_area_class(obj, layer):
    """Bewijsplafond van de oppervlakte: nooit hoger dan identiteit, telling en maatvoering rechtvaardigen."""
    cls = area_class(obj["dimension"])
    if layer == "ESTIMATED" and cls == "KNOWN":
        return "ESTIMATED"   # een geschat object heeft geen bekende oppervlakte
    return cls


def _check_inputs(types, objects, observations):
    ids = [t["type_id"] for t in types]
    if len(set(ids)) != len(ids):
        raise BrutoError("DUPLICATE_TYPE_ID", "type_id komt meer dan eens voor")
    tmap = {t["type_id"]: t for t in types}
    oids = [o["observation_id"] for o in observations]
    if len(set(oids)) != len(oids):
        raise BrutoError("DUPLICATE_OBSERVATION_ID", "observation_id komt meer dan eens voor")
    omap = {o["observation_id"]: o for o in observations}
    seen_obj, claimed = set(), {}
    for ob in objects:
        oid = ob["object_id"]
        if oid in seen_obj:
            raise BrutoError("DUPLICATE_OBJECT_ID", f"object_id {oid} komt meer dan eens voor")
        seen_obj.add(oid)
        if ob.get("is_physical_instance") is not False or ob.get("fi_id") is not None:
            raise BrutoError("INSTANCE_NOT_ALLOWED", f"{oid}: v2-objecten zijn geen instances en krijgen geen FI-id")
        probs = dimension_problems(ob["dimension"])
        if probs:
            raise BrutoError("DIMENSION_INVALID", f"{oid}: {'; '.join(probs)}")
        tid = ob.get("type_id")
        if tid is not None:
            if tid not in tmap:
                raise BrutoError("UNKNOWN_TYPE", f"{oid}: type {tid} onbekend")
            if tmap[tid]["object_category"] != ob["object_category"]:
                raise BrutoError("TYPE_CATEGORY_MISMATCH", f"{oid}: objectcategorie wijkt af van type {tid}")
        for ref in ob.get("observation_refs", []):
            if ref not in omap:
                raise BrutoError("UNKNOWN_OBSERVATION", f"{oid}: observatie {ref} onbekend")
            if ref in claimed:
                raise BrutoError("OBSERVATION_DOUBLE_CLAIM", f"observatie {ref} hoort bij zowel {claimed[ref]} als {oid}: dubbeltelling")
            claimed[ref] = oid
            if omap[ref]["object_category"] != ob["object_category"]:
                raise BrutoError("OBSERVATION_CATEGORY_MISMATCH", f"{oid}: observatie {ref} heeft een andere categorie")
        if ob["object_origin"] == "ESTIMATED_MISSING" and (ob.get("observation_refs") or ob.get("approval_refs") or not ob.get("repetition_basis")):
            raise BrutoError("ESTIMATED_OBJECT_INVALID", f"{oid}: geschat ontbrekend object vereist repetition_basis en heeft geen observaties of goedkeuringen")
        if ob["object_origin"] == "OBSERVED" and not ob.get("observation_refs"):
            raise BrutoError("OBSERVED_OBJECT_WITHOUT_OBSERVATION", f"{oid}: waargenomen object zonder observatie")
    return tmap, omap, claimed


def _empty_layer():
    return {"object_ids": [], "piece": 0}


def build_state(types, objects, observations, *, door_treatment=None, approval_verifier=None):
    """Bouwt de gescheiden hoeveelhedenlagen. Deterministisch: dezelfde invoer geeft byte-identieke uitvoer.

    door_treatment: None/UNDECIDED (deuren alleen in stuks), AS_PIECES, NOT_RELEVANT of PART_OF_GROSS_FRAME_AREA."""
    treatment = door_treatment or "UNDECIDED"
    if treatment not in DOOR_TREATMENTS:
        raise BrutoError("DOOR_TREATMENT_INVALID", f"onbekende deurbehandeling {treatment!r}")
    verifier = approval_verifier or NullApprovalVerifier()
    types, objects, observations = (sorted(types, key=lambda t: t["type_id"]), sorted(objects, key=lambda o: o["object_id"]),
                                    sorted(observations, key=lambda o: o["observation_id"]))
    _check_inputs(types, objects, observations)
    door_area = treatment == "PART_OF_GROSS_FRAME_AREA"

    layer_of = {o["object_id"]: classify_layer(o, verifier) for o in objects}
    frames = [o for o in objects if o["object_category"] in FRAME_CATEGORIES]
    doors = [o for o in objects if o["object_category"] == "DOOR"]

    layers = {lay: _empty_layer() for lay in LAYERS}
    for o in frames:
        L = layers[layer_of[o["object_id"]]]
        L["object_ids"].append(o["object_id"])
        L["piece"] += o["quantity"]
    door_pieces = {lay: 0 for lay in LAYERS}
    for o in doors:
        door_pieces[layer_of[o["object_id"]]] += o["quantity"]

    # Oppervlakten per laag en klasse (REVIEW_LOW_CERTAINTY heeft geen oppervlakten).
    counted = frames + (doors if door_area else [])
    areas, unknown_ids = {}, []
    for lay in ("PROVISIONAL_UNIQUE", "CONFIRMED", "ESTIMATED"):
        cls_members = {"KNOWN": [], "ESTIMATED": [], "UNKNOWN": []}
        for o in counted:
            if layer_of[o["object_id"]] == lay:
                cls_members[object_area_class(o, lay)].append(o)
        entry = {}
        for cls in ("KNOWN", "ESTIMATED"):
            mem = cls_members[cls]
            if not mem:
                entry[cls.lower()] = {"area_m2_exact": None, "area_m2_presented": None, "object_ids": [], "by_type_group": []}
                continue
            groups = OrderedDict()
            for o in mem:
                with localcontext() as ctx:
                    ctx.prec = _DEC_PREC
                    groups.setdefault(o.get("type_id") or "UNTYPED", Decimal(0))
                    groups[o.get("type_id") or "UNTYPED"] += gross_area_exact(o["dimension"]["outer_width_m"], o["dimension"]["outer_height_m"], o["quantity"])
            items = sorted(groups.items())
            total_p, parts_p = allocate_presented(items)
            with localcontext() as ctx:
                ctx.prec = _DEC_PREC
                total_exact = sum((v for _, v in items), Decimal(0))
            entry[cls.lower()] = {"area_m2_exact": fmt_exact(total_exact), "area_m2_presented": total_p,
                                  "object_ids": [o["object_id"] for o in mem],
                                  "by_type_group": [OrderedDict([("group_key", k), ("area_m2_exact", fmt_exact(v)), ("area_m2_presented", parts_p[k])]) for k, v in items]}
        unk = cls_members["UNKNOWN"]
        entry["unknown"] = {"object_count": len(unk), "piece_count": sum(o["quantity"] for o in unk),
                            "object_ids": [o["object_id"] for o in unk], "area_m2": None}
        unknown_ids += [o["object_id"] for o in unk]
        areas[lay] = entry

    confirmed_ids = layers["CONFIRMED"]["object_ids"]
    claimed_by_unique = {r for o in objects if layer_of[o["object_id"]] in ("PROVISIONAL_UNIQUE", "CONFIRMED") for r in o.get("observation_refs", [])}
    by_cat, by_vis = OrderedDict(), OrderedDict()
    for ob in observations:
        by_cat[ob["object_category"]] = by_cat.get(ob["object_category"], 0) + 1
        by_vis[ob["visibility"]] = by_vis.get(ob["visibility"], 0) + 1

    def layer_out(lay):
        L = layers[lay]
        return OrderedDict([("object_count", len(L["object_ids"])), ("piece_count", L["piece"]), ("object_ids", L["object_ids"])])

    provides = getattr(verifier, "provides_verified_approvals", False) is True
    state = OrderedDict([
        ("contract_version", "bruto_quantity_state_v2"), ("state_id", ""), ("status", "PROPOSED"), ("release_status", "NOT_RELEASED"),
        ("usable_for_mjop", False), ("method", dict(METHOD)),
        ("input_sha256", canonical_sha256({"types": types, "objects": objects, "observations": observations, "door_treatment": treatment})),
        ("approval_verifier", OrderedDict([("name", str(getattr(verifier, "name", type(verifier).__name__))), ("provides_verified_approvals", provides)])),
        ("observed", OrderedDict([("layer", "OBSERVED"), ("observation_count", len(observations)), ("by_category", dict(by_cat)),
                                  ("by_visibility", dict(by_vis)),
                                  ("unconsolidated_observation_ids", [o["observation_id"] for o in observations if o["observation_id"] not in claimed_by_unique]),
                                  ("is_unique_count", False)])),
        ("layers", OrderedDict([("PROVISIONAL_UNIQUE", layer_out("PROVISIONAL_UNIQUE")),
                                ("CONFIRMED", OrderedDict([("layer_status", "OPEN_WITH_VERIFIED_APPROVALS" if provides else "BLOCKED_NO_VERIFIED_APPROVAL_SOURCE"),
                                                           ("object_count", len(confirmed_ids)), ("object_ids", confirmed_ids),
                                                           ("piece_count", layers["CONFIRMED"]["piece"])])),
                                ("ESTIMATED", layer_out("ESTIMATED")), ("REVIEW_LOW_CERTAINTY", layer_out("REVIEW_LOW_CERTAINTY")),
                                ("sum_across_layers", None)])),
        ("areas", OrderedDict([("PROVISIONAL_UNIQUE", areas["PROVISIONAL_UNIQUE"]), ("CONFIRMED", areas["CONFIRMED"]),
                               ("ESTIMATED", areas["ESTIMATED"]), ("combined_total_m2", None), ("door_area_included", door_area),
                               ("door_treatment", treatment)])),
        ("doors", OrderedDict([("registered_in_pieces", door_pieces), ("maintenance_quantities_created", False)])),
        ("unknown", OrderedDict([("layer", "UNKNOWN"), ("unknown_area_object_ids", sorted(unknown_ids)), ("unknown_is_zero", False)])),
        ("building_total", OrderedDict([("status", "UNKNOWN"), ("value", None)])),
        ("invariants", dict(INVARIANTS))])
    state = json.loads(json.dumps(state))
    state["state_id"] = "BQS-" + canonical_sha256({k: v for k, v in state.items() if k != "state_id"})[:16]
    return state
