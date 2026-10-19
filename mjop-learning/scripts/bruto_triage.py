"""Quantity Review & Triage v1: deterministische triage op twee onafhankelijke assen (puur, alleen lezen).

As A = identiteit/telling, as B = maatvoering. Klassen: CLEAN_PROVISIONAL < REVIEW_REQUIRED < INSUFFICIENT_EVIDENCE < CONFLICT;
de totaalklasse is de slechtste van beide assen. AI-zekerheid wordt alleen vastgelegd en is nooit regelinvoer. Zonder
gekalibreerde drempels (standaard) is geen enkel object CLEAN_PROVISIONAL. Dit bestand registreert geen besluiten, maakt geen
CONFIRMED-uitvoer, geen FI-id, geen instance-activatie, geen BAG-koppeling en geen definitief totaal; het gebruikt geen netwerk.
"""
import copy
import json
import sys
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bruto_quantity_core as core  # noqa: E402
import bruto_triage_calibration as cal  # noqa: E402
import bruto_triage_contracts as contracts  # noqa: E402

CLASSES = ("CLEAN_PROVISIONAL", "REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE", "CONFLICT")
RANK = {c: i for i, c in enumerate(CLASSES)}
ANCHORS = ("UNIQUE_CONFIGURATION", "PLATE_ANCHOR")
SIMILARITY_ONLY = ("SAME_LAYOUT", "FEATURE_MATCH", "SEQUENCE_ORDER", "PARTIAL_OVERLAP", "OBLIQUE_VIEW", "FACADE_CONTEXT")
BLOCKING = ("REPETITION_RISK", "HIDDEN", "TOO_DARK")
MIN_GROUP_SIZE = 2  # structureel (geen zekerheidsdrempel): een groep van één object is geen groep
RULES = {r["rule_id"]: r for r in contracts.load_rules()["rules"]}
INVARIANTS = OrderedDict([("release_state", "NOT_RELEASED"), ("usable_for_mjop", False), ("decisions_registered", False),
                          ("approvals_simulated", False), ("fi_ids_created", False), ("confirmed_output", False),
                          ("group_release_executed", False), ("ai_confidence_used_in_decision", False), ("final_building_total", None),
                          ("network_used", False), ("clicks_register_decisions", False)])
NOTES = ["Voorlopige review-export; geen definitieve MJOP-hoeveelheid, geen besluit, geen vrijgave.",
         "Scenario's zijn onafhankelijk en overlappen mogelijk; ze mogen niet worden opgeteld.",
         "AI-zekerheid is informatie en niet gebruikt in de classificatie; een goedkeuringsbewering in de invoer is niet geverifieerd."]


def load_default_calibration():
    return json.loads((ROOT / cal.CONFIG_REL).read_text(encoding="utf-8"))


def _reason(rule_id, detail, refs=()):
    r = RULES[rule_id]
    return OrderedDict([("rule_id", rule_id), ("axis", r["axis"]), ("class", r["class"]), ("title", r["title"]),
                        ("detail", detail), ("refs", sorted(set(refs)))])


def _class_of(reasons):
    return max((x["class"] for x in reasons), key=lambda c: RANK[c], default="CLEAN_PROVISIONAL")


def _dec(v):
    return Decimal(v) if v is not None else None


def _unknown_dimension():
    return {"outer_width_m": None, "outer_height_m": None, "dimension_basis": "OUTER_FRAME", "dimension_status": "UNKNOWN",
            "measurement_method": "NONE", "source": {"source_kind": "NONE", "source_id": None, "recorded_at": None, "recorded_by": None,
                                                     "authentication": "NONE_SELF_ASSERTED"},
            "scale_evidence_ref": None, "validated_reference_ref": None, "uncertainty": None, "estimate": None}


def _unique(items, key, code):
    ids = [key(i) for i in items]
    if len(set(ids)) != len(ids):
        raise core.BrutoError(code, "id komt meer dan eens voor")


def _gross(obj):
    """(exact Decimal of None, presented of None). Onbekend blijft None, nooit 0."""
    d = obj["dimension"]
    if d.get("outer_width_m") is None or d.get("outer_height_m") is None or core.dimension_problems(d):
        return None, None
    a = core.gross_area_exact(d["outer_width_m"], d["outer_height_m"], obj["quantity"])
    return a, core.present(a)


def _identity(o, ctx, params, calibrated):
    reasons = []
    refs = o.get("observation_refs", [])
    omap, owners = ctx["omap"], ctx["owners"]
    if o.get("is_physical_instance") is not False or o.get("fi_id") is not None:
        reasons.append(_reason("A-C5", "object is gemarkeerd als instance of heeft een FI-id", [o["object_id"]]))
    if o.get("type_id") is not None:
        t = ctx["tmap"].get(o["type_id"])
        if t is None:
            reasons.append(_reason("A-C5", f"onbekend type {o['type_id']}", [o["object_id"]]))
        elif t["object_category"] != o["object_category"]:
            reasons.append(_reason("A-C5", f"objectcategorie wijkt af van type {o['type_id']}", [o["object_id"], o["type_id"]]))
    if o["object_origin"] == "ESTIMATED_MISSING":
        if refs or o.get("approval_refs") or not o.get("repetition_basis"):
            reasons.append(_reason("A-C5", "geschat ontbrekend object met observaties, goedkeuringsbewering of zonder repetition_basis", [o["object_id"]]))
        if not reasons:
            reasons.append(_reason("A-R7", "afgeleid uit herhaling: " + str(o["repetition_basis"]["reason"]), [o["object_id"]]))
        return reasons
    if not refs:
        reasons.append(_reason("A-C5", "waargenomen object zonder observatie", [o["object_id"]]))
    for r in refs:
        ob = omap.get(r)
        if ob is None:
            reasons.append(_reason("A-C5", f"onbekende observatie {r}", [o["object_id"], r]))
        elif ob["object_category"] != o["object_category"]:
            reasons.append(_reason("A-C5", f"observatie {r} heeft een andere objectcategorie", [o["object_id"], r]))
        if len(owners.get(r, [])) > 1:
            reasons.append(_reason("A-C1", f"observatie {r} hoort bij {', '.join(sorted(owners[r]))}: dubbeltelling", [r] + owners[r]))
    known = [r for r in refs if r in omap]
    per_photo = {}
    for r in known:
        per_photo.setdefault(omap[r]["photo_id"], []).append(r)
    for ph in sorted(per_photo):
        if len(per_photo[ph]) > o["quantity"]:
            reasons.append(_reason("A-C2", f"{len(per_photo[ph])} observaties op foto {ph} voor {o['quantity']} stuk(s)", per_photo[ph]))
    refset = set(known)
    for e in ctx["evidence"]:
        a, b = e["observation_ids"]
        if e["polarity"] == "CONTRADICTS_SAME" and a in refset and b in refset:
            reasons.append(_reason("A-C3", f"bewijs {e['evidence_id']} ({e['evidence_basis']}) zegt dat {a} en {b} niet hetzelfde zijn", [a, b, e["evidence_id"]]))
        if e["polarity"] == "SUPPORTS_SAME" and e["evidence_basis"] in ANCHORS and ((a in refset) != (b in refset)):
            inside, outside = (a, b) if a in refset else (b, a)
            other = [x for x in owners.get(outside, []) if x != o["object_id"]]
            if other:
                reasons.append(_reason("A-C4", f"verankerd bewijs {e['evidence_id']} koppelt {inside} aan {outside} van {', '.join(sorted(other))}", [inside, outside, e["evidence_id"]] + other))
    if any(x["class"] == "CONFLICT" for x in reasons):
        return reasons
    if not any(omap[r]["visibility"] == "FULL" for r in known):
        reasons.append(_reason("A-I1", "geen enkele observatie toont het object volledig", known))
    if o.get("consolidation") is None:
        reasons.append(_reason("A-I2", "geen consolidatievoorstel", [o["object_id"]]))
    anchors_found = 0
    if o["quantity"] == 1 and len(known) >= 2:
        parent = {r: r for r in known}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        srcs = set()
        for e in ctx["evidence"]:
            a, b = e["observation_ids"]
            if e["polarity"] == "SUPPORTS_SAME" and e["evidence_basis"] in ANCHORS and a in refset and b in refset:
                parent[find(a)] = find(b)
                srcs.add(e["source_ref"] or e["evidence_id"])
        anchors_found = len(srcs)
        if len({find(r) for r in known}) > 1:
            reasons.append(_reason("A-I3", "observaties zijn samengevoegd zonder verankerd bewijs (uniek kenmerk of plaatje)", known))
    for e in ctx["evidence"]:
        if e["evidence_basis"] in BLOCKING and refset & set(e["observation_ids"]):
            reasons.append(_reason("A-I4", f"bewijs {e['evidence_id']}: {e['evidence_basis']}", list(e["observation_ids"]) + [e["evidence_id"]]))
    if any(x["class"] == "INSUFFICIENT_EVIDENCE" for x in reasons):
        return reasons
    bad_src = [r for r in known if not omap[r].get("source_ref")]
    bad_src += [e["evidence_id"] for e in ctx["evidence"] if refset & set(e["observation_ids"]) and (not e["source_ref"] or not e["source_sha256"])]
    if bad_src:
        reasons.append(_reason("A-R1", "bronverwijzing of hash ontbreekt", bad_src))
    overlap = []
    for e in ctx["evidence"]:
        a, b = e["observation_ids"]
        if e["polarity"] == "SUPPORTS_SAME" and e["evidence_basis"] in SIMILARITY_ONLY and ((a in refset) != (b in refset)):
            inside, outside = (a, b) if a in refset else (b, a)
            other = sorted(x for x in owners.get(outside, []) if x != o["object_id"])
            if other:
                overlap.append((e, other))
    for e, other in overlap:
        reasons.append(_reason("A-R2", f"alleen gelijkenis ({e['evidence_basis']}, {e['evidence_id']}) met {', '.join(other)}; kan dezelfde opening zijn",
                               list(e["observation_ids"]) + other + [e["evidence_id"]]))
    flagged = [r for r in known if "POSSIBLE_OVERLAP" in ctx["flags"].get(r, ())]
    if flagged:
        reasons.append(_reason("A-R2", "waarnemer markeert mogelijke overlap", flagged))
    deg = [r for r in known if set(ctx["flags"].get(r, ())) & {"LOW_QUALITY", "OBLIQUE_VIEW"}]
    if deg:
        reasons.append(_reason("A-R3", "scheef gezien of lage kwaliteit", deg))
    if o["quantity"] > len(known):
        reasons.append(_reason("A-R4", f"{o['quantity']} stuks maar {len(known)} observatie(s)", [o["object_id"]]))
    if calibrated and o["quantity"] == 1 and len(known) >= 2 and anchors_found < params["min_independent_anchors"]:
        reasons.append(_reason("A-R6", f"{anchors_found} onafhankelijk anker(s), minimum {params['min_independent_anchors']}", known))
    return reasons


def _dimension(o, ctx, params, calibrated):
    reasons = []
    d, oid = o["dimension"], o["object_id"]
    probs = core.dimension_problems(d)
    if probs:
        return [_reason("B-C3", "; ".join(probs), [oid])]
    status = d["dimension_status"]
    if status == "UNKNOWN":
        reasons.append(_reason("B-I1", "geen maat; bruto oppervlak onbekend (null)", [oid]))
    rel = status in core.RELIABLE_REFERENCE_STATUSES
    srcs = ctx["dim_evidence"].get(oid, [])
    items = [(s["source_ref"], Decimal(s["outer_width_m"]), Decimal(s["outer_height_m"]), Decimal(s["uncertainty_m"])) for s in srcs]
    if rel:
        unc = Decimal((d.get("uncertainty") or {}).get("absolute_m") or 0)
        items.append(("object-maat", Decimal(d["outer_width_m"]), Decimal(d["outer_height_m"]), unc))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if abs(a[1] - b[1]) > a[3] + b[3] or abs(a[2] - b[2]) > a[3] + b[3]:
                reasons.append(_reason("B-C1", f"{a[0]} ({a[1]}x{a[2]}) en {b[0]} ({b[1]}x{b[2]}) wijken af voorbij de onzekerheid", [oid, a[0], b[0]]))
    if status == "REFERENCE_DERIVED_ESTIMATE":
        est = d["estimate"]
        rt = ctx["tmap"].get(est.get("reference_type_id"))
        if rt is None or rt["object_category"] != o["object_category"]:
            reasons.append(_reason("B-C2", "referentietype ontbreekt of heeft een andere objectcategorie", [oid, str(est.get("reference_type_id"))]))
        else:
            by_id = {r["reference_id"]: r["dimension"] for r in rt["reference_dimensions"]}
            ids = est.get("reference_ids", [])
            if not ids or any(i not in by_id or by_id[i].get("dimension_status") not in core.RELIABLE_REFERENCE_STATUSES for i in ids):
                reasons.append(_reason("B-I2", "referenties ontbreken of zijn niet betrouwbaar (MEASURED/DRAWING_DERIVED)", [oid, rt["type_id"]]))
            elif calibrated:
                spread = Decimal((est.get("uncertainty") or {}).get("spread_width_m") or 0).max(Decimal((est.get("uncertainty") or {}).get("spread_height_m") or 0))
                ok = (len(ids) >= params["estimate_min_references"] and set(est["comparability_basis"]) <= set(params["estimate_allowed_bases"])
                      and spread <= Decimal(params["estimate_max_spread_m"]))
                if not ok:
                    reasons.append(_reason("B-R5", f"{len(ids)} referentie(s), spreiding {spread}", [oid, rt["type_id"]]))
            else:
                reasons.append(_reason("B-R1", "schatting uit vergelijkbaar type; drempels ongekalibreerd", [oid, rt["type_id"]]))
    if rel:
        if d["source"]["source_kind"] == "NONE" or not d["source"].get("source_id"):
            reasons.append(_reason("B-R3", "geen traceerbare maatbron", [oid]))
        if status != "MEASURED" and any("OBLIQUE_VIEW" in ctx["flags"].get(r, ()) for r in o.get("observation_refs", [])):
            reasons.append(_reason("B-R4", "afleiding steunt op een scheef gezien beeld", [oid]))
        dev = ctx["deviating"].get(oid)
        if dev:
            reasons.append(_reason("B-R2", dev, [oid] + ([o["type_id"]] if o.get("type_id") else [])))
    return reasons


def _deviations(objects, tmap, tol):
    """Per object met betrouwbare maat: afwijking van referenties/varianten of (zonder die) van de rest van de typegroep."""
    out = {}
    by_type = {}
    for o in objects:
        d = o["dimension"]
        if o.get("type_id") in tmap and d["dimension_status"] in core.RELIABLE_REFERENCE_STATUSES and not core.dimension_problems(d):
            by_type.setdefault(o["type_id"], []).append(o)

    def near(o, w, h):
        return abs(Decimal(o["dimension"]["outer_width_m"]) - Decimal(w)) <= tol and abs(Decimal(o["dimension"]["outer_height_m"]) - Decimal(h)) <= tol
    for tid, members in sorted(by_type.items()):
        t = tmap[tid]
        refs = [r["dimension"] for r in t["reference_dimensions"] if r["dimension"].get("dimension_status") in core.RELIABLE_REFERENCE_STATUSES]
        refs += [v["dimension"] for v in t["variants"] if v["dimension"].get("dimension_status") in core.RELIABLE_REFERENCE_STATUSES]
        if refs:
            for o in members:
                if not any(near(o, r["outer_width_m"], r["outer_height_m"]) for r in refs):
                    out[o["object_id"]] = f"maat {o['dimension']['outer_width_m']}x{o['dimension']['outer_height_m']} komt niet overeen met referenties of varianten van {tid}"
        else:
            keys = {}
            for o in members:
                keys.setdefault((o["dimension"]["outer_width_m"], o["dimension"]["outer_height_m"]), []).append(o)
            if len(keys) > 1:
                top = max(len(v) for v in keys.values())
                modes = [k for k, v in keys.items() if len(v) == top]
                for k, v in sorted(keys.items()):
                    if len(modes) > 1 or k not in modes:
                        for o in v:
                            out[o["object_id"]] = f"maat {k[0]}x{k[1]} wijkt af binnen typegroep {tid}"
    return out


def _uf_groups(sets):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for s in sets:
        s = list(s)
        for x in s:
            find(x)
        for x in s[1:]:
            parent[find(x)] = find(s[0])
    comps = {}
    for x in parent:
        comps.setdefault(find(x), set()).add(x)
    return {x: "OG-" + min(c) for c in comps.values() for x in c}


def _normalized_input(inp):
    """Volgorde-onafhankelijke vorm van de invoer, zodat de hash niet van de lijstvolgorde afhangt."""
    keys = {"types": lambda x: x["type_id"], "objects": lambda x: x["object_id"], "observations": lambda x: x["observation_id"],
            "identity_evidence": lambda x: x["evidence_id"], "observation_flags": lambda x: x["observation_id"],
            "dimension_evidence": lambda x: x["object_id"], "ai_confidence_info": lambda x: x["object_id"]}
    out = {k: (sorted(v, key=keys[k]) if k in keys else v) for k, v in inp.items()}
    out["observation_flags"] = [{**f, "flags": sorted(f["flags"])} for f in out["observation_flags"]]
    return out


def triage(inp, calibration_config=None, *, door_treatment=None, allow_synthetic_calibration=False):
    """Geeft het review-pack (dict). Deterministisch: dezelfde invoer en kalibratie geven byte-identieke uitvoer."""
    errs = contracts.input_errors(inp)
    if errs:
        raise core.BrutoError("INPUT_SCHEMA_INVALID", "; ".join(errs[:5]))
    config = calibration_config if calibration_config is not None else load_default_calibration()
    cerrs = contracts.calibration_errors(config)
    calib = cal.effective(config, allow_synthetic=allow_synthetic_calibration) if not cerrs else \
        {"declared_status": config.get("status"), "effective_status": "UNCALIBRATED", "conservative_fallback": True,
         "problems": sorted("SCHEMA: " + e for e in cerrs), "parameters": {k: None for k in cal.PARAM_KEYS}}
    calibrated = calib["effective_status"] == "CALIBRATED"
    params = calib["parameters"]
    types, objects, observations = (sorted(inp["types"], key=lambda t: t["type_id"]), sorted(inp["objects"], key=lambda o: o["object_id"]),
                                    sorted(inp["observations"], key=lambda o: o["observation_id"]))
    evidence = sorted(inp["identity_evidence"], key=lambda e: e["evidence_id"])
    _unique(types, lambda t: t["type_id"], "DUPLICATE_TYPE_ID")
    _unique(objects, lambda o: o["object_id"], "DUPLICATE_OBJECT_ID")
    _unique(observations, lambda o: o["observation_id"], "DUPLICATE_OBSERVATION_ID")
    _unique(evidence, lambda e: e["evidence_id"], "DUPLICATE_EVIDENCE_ID")
    omap = {o["observation_id"]: o for o in observations}
    oids = {o["object_id"] for o in objects}
    for e in evidence:
        if any(x not in omap for x in e["observation_ids"]) or e["observation_ids"][0] == e["observation_ids"][1]:
            raise core.BrutoError("EVIDENCE_REFERENCE_INVALID", f"bewijs {e['evidence_id']} verwijst naar onbekende of dubbele observaties")
    for key, ids in (("observation_flags", [f["observation_id"] for f in inp["observation_flags"]]),
                     ("dimension_evidence", [f["object_id"] for f in inp["dimension_evidence"]]),
                     ("ai_confidence_info", [f["object_id"] for f in inp["ai_confidence_info"]])):
        if len(set(ids)) != len(ids) or any(i not in (omap if key == "observation_flags" else oids) for i in ids):
            raise core.BrutoError("SIDE_INPUT_INVALID", f"{key}: dubbele of onbekende verwijzing")
    owners = {}
    for o in objects:
        for r in o.get("observation_refs", []):
            owners.setdefault(r, []).append(o["object_id"])
    ctx = {"tmap": {t["type_id"]: t for t in types}, "omap": omap, "owners": owners, "evidence": evidence,
           "flags": {f["observation_id"]: tuple(sorted(f["flags"])) for f in inp["observation_flags"]},
           "dim_evidence": {f["object_id"]: f["sources"] for f in inp["dimension_evidence"]}}
    tol = Decimal(params["dimension_deviation_tolerance_m"]) if calibrated else Decimal(0)
    ctx["deviating"] = _deviations(objects, ctx["tmap"], tol)
    ai = {f["object_id"]: f["value"] for f in inp["ai_confidence_info"]}

    res = {}
    for o in objects:
        ir = _identity(o, ctx, params, calibrated)
        iclass = _class_of(ir)
        would_be_clean = False
        if iclass == "CLEAN_PROVISIONAL" and not calibrated:
            ir.append(_reason("A-R5", "geen gekalibreerde bewijsdrempel; conservatief beoordelen", [o["object_id"]]))
            iclass, would_be_clean = "REVIEW_REQUIRED", True
        dr = _dimension(o, ctx, params, calibrated)
        dclass = _class_of(dr)
        overall = max(iclass, dclass, key=lambda c: RANK[c])
        res[o["object_id"]] = {"ir": ir, "ic": iclass, "dr": dr, "dc": dclass, "oc": overall, "wbc": would_be_clean}

    # basisstand uit niet-conflicterende objecten; onvoldoende identiteit telt niet als voorlopig-uniek
    eff = []
    for o in objects:
        r = res[o["object_id"]]
        if r["ic"] == "CONFLICT" or r["dc"] == "CONFLICT":
            continue
        e = copy.deepcopy(o)
        if r["ic"] == "INSUFFICIENT_EVIDENCE" and e.get("consolidation"):
            e["consolidation"]["certainty"] = "UNKNOWN"
        if r["dc"] == "INSUFFICIENT_EVIDENCE" and e["dimension"]["dimension_status"] != "UNKNOWN":
            e["dimension"] = _unknown_dimension()
        eff.append(e)
    try:
        state = core.build_state(types, eff, observations, door_treatment=door_treatment)
    except core.BrutoError as ex:
        raise core.BrutoError("BASELINE_FAILED", str(ex))
    treatment = state["areas"]["door_treatment"]
    layer_of = {e["object_id"]: core.classify_layer(e) for e in eff}
    area_cls_of = {e["object_id"]: core.object_area_class(e, layer_of[e["object_id"]]) for e in eff}

    # prioriteit
    omap_obj = {o["object_id"]: o for o in objects}
    order = sorted((oid for oid in res if res[oid]["oc"] != "CLEAN_PROVISIONAL"),
                   key=lambda oid: (-RANK[res[oid]["oc"]], -(_gross(omap_obj[oid])[0] or Decimal(0)), oid))
    priority = {oid: i + 1 for i, oid in enumerate(order)}

    # groepen (alleen voorbereid, nooit uitgevoerd)
    clean_ids = sorted(oid for oid in res if res[oid]["oc"] == "CLEAN_PROVISIONAL")
    groups = []
    if calibrated and len(clean_ids) >= MIN_GROUP_SIZE:
        hashes = [(oid, core.canonical_sha256(omap_obj[oid])) for oid in clean_ids]
        sample = cal.audit_sample(hashes, calib["audit_sample"]["seed"], min(calib["audit_sample"]["size"], len(clean_ids)))
        gh = core.canonical_sha256({"members": hashes, "calibration": calib})
        groups.append(OrderedDict([("group_id", "GRP-" + gh[:12]), ("member_object_ids", clean_ids), ("status", "PREPARED_NOT_RELEASED"),
                                   ("release_executed", False), ("audit_sample_object_ids", sample), ("content_sha256", gh),
                                   ("exception_list_object_ids", sorted(set(res) - set(clean_ids))),
                                   ("criteria", "alle leden CLEAN_PROVISIONAL onder gekalibreerde drempels; overige objecten blijven buiten de groep")]))
    in_group = {m for g in groups for m in g["member_object_ids"]}

    def work_state(oid):
        c = res[oid]["oc"]
        if c in ("CONFLICT", "INSUFFICIENT_EVIDENCE"):
            return "BLOCKED"
        if c == "REVIEW_REQUIRED":
            return "INDIVIDUAL_REVIEW"
        return "READY_FOR_GROUP_REVIEW" if oid in in_group else "AUTO_PROVISIONAL"

    # objecten voor het pack
    objs = []
    for o in objects:
        oid, r = o["object_id"], res[o["object_id"]]
        d = o["dimension"]
        exact, pres = _gross(o)
        try:
            acls = core.area_class(d)
        except core.BrutoError:
            acls = "UNKNOWN"
        reasons = r["ir"] + r["dr"]
        mine = set(o.get("observation_refs", []))
        if r["oc"] == "CONFLICT":
            eff_txt = {"in_baseline": False, "layer": None, "area_class": None, "counted_in_area": False,
                       "text": "Niet in de basisstand: geblokkeerd door conflict; zie conflictscenario."}
        else:
            lay, ac = layer_of[oid], area_cls_of[oid]
            counted = (o["object_category"] != "DOOR" or treatment == "PART_OF_GROSS_FRAME_AREA") and lay != "REVIEW_LOW_CERTAINTY" and ac != "UNKNOWN"
            txt = f"Basisstand: laag {lay}; oppervlakklasse {ac}" + ("; telt mee in oppervlak." if counted else "; telt niet mee in oppervlak.")
            if o["object_category"] == "DOOR" and treatment != "PART_OF_GROSS_FRAME_AREA":
                txt += f" Deur: alleen in stuks (behandeling {treatment})."
            eff_txt = {"in_baseline": True, "layer": lay, "area_class": ac, "counted_in_area": counted, "text": txt}
        objs.append(OrderedDict([
            ("object_id", oid), ("provisional_object_id", oid), ("object_origin", o["object_origin"]), ("object_category", o["object_category"]),
            ("type_id", o.get("type_id")), ("quantity", o["quantity"]),
            ("observations", [OrderedDict([("observation_id", x), ("photo_id", omap[x]["photo_id"]), ("visibility", omap[x]["visibility"]),
                                           ("source_ref", omap[x].get("source_ref")), ("flags", list(ctx["flags"].get(x, ())))])
                              for x in sorted(mine) if x in omap]),
            ("identity_evidence", [OrderedDict([("evidence_id", e["evidence_id"]), ("observation_ids", e["observation_ids"]), ("evidence_basis", e["evidence_basis"]),
                                                ("polarity", e["polarity"]), ("source_ref", e["source_ref"]), ("source_sha256", e["source_sha256"])])
                                   for e in evidence if mine & set(e["observation_ids"])]),
            ("dimension", OrderedDict([("dimension_status", d["dimension_status"]), ("outer_width_m", d.get("outer_width_m")), ("outer_height_m", d.get("outer_height_m")),
                                       ("source_kind", d["source"]["source_kind"]), ("source_id", d["source"].get("source_id")), ("area_class", acls),
                                       ("gross_area_m2_exact", core.fmt_exact(exact) if exact is not None else None), ("gross_area_m2_presented", pres)])),
            ("identity_axis", OrderedDict([("class", r["ic"]), ("would_be_clean_if_calibrated", r["wbc"]), ("reasons", r["ir"])])),
            ("dimension_axis", OrderedDict([("class", r["dc"]), ("reasons", r["dr"])])),
            ("overall_class", r["oc"]), ("work_state", work_state(oid)), ("review_priority", priority.get(oid)),
            ("review_reasons", [OrderedDict([("rule_id", x["rule_id"]), ("axis", x["axis"]), ("class", x["class"]), ("title", x["title"]), ("detail", x["detail"])]) for x in reasons]),
            ("contradictions", [OrderedDict([("rule_id", x["rule_id"]), ("detail", x["detail"]), ("refs", x["refs"])]) for x in reasons if x["class"] == "CONFLICT"]),
            ("effect_on_provisional_quantities", eff_txt),
            ("ai_confidence", OrderedDict([("value", ai.get(oid)), ("used_in_decision", False), ("calibrated", False)])),
            ("info_flags", [OrderedDict([("flag", "APPROVAL_CLAIM_UNVERIFIED"), ("effect", "GEEN_EFFECT_OP_KLASSE")])] if o.get("approval_refs") else []),
            ("released", False)]))

    # scenario's (onafhankelijk, niet optelbaar, geen eindhoeveelheid)
    scen = []
    seen_pairs = set()
    for o in objects:
        for x in res[o["object_id"]]["ir"]:
            if x["rule_id"] != "A-R2":
                continue
            others = [i for i in x["refs"] if i in omap_obj and i != o["object_id"]]
            for other in others:
                pair = tuple(sorted((o["object_id"], other)))
                if pair in seen_pairs or res[other]["oc"] == "CONFLICT":
                    continue
                seen_pairs.add(pair)
                a, b = _gross(omap_obj[pair[0]])[0], _gross(omap_obj[pair[1]])[0]
                q1 = omap_obj[pair[0]]["quantity"] == 1 and omap_obj[pair[1]]["quantity"] == 1
                rng = None
                if q1 and a is not None and b is not None:
                    rng = OrderedDict([("min_m2_exact", "-" + core.fmt_exact(max(a, b))), ("max_m2_exact", "-" + core.fmt_exact(min(a, b)))])
                scen.append(OrderedDict([("kind", "DUPLICATE_PAIR_IF_SAME_OBJECT"), ("object_ids", list(pair)),
                                         ("statement", f"Als {pair[0]} en {pair[1]} hetzelfde fysieke object zijn, vervalt één van beide."),
                                         ("effect", OrderedDict([("piece_change", -1 if q1 else None), ("area_change_range", rng)]))]))
    for o in objects:
        oid, r = o["object_id"], res[o["object_id"]]
        if any(x["rule_id"] == "B-I1" for x in r["dr"]) and r["ic"] != "CONFLICT":
            est, why = None, "GEEN_TYPE"
            t = ctx["tmap"].get(o.get("type_id"))
            if t is not None:
                try:
                    dd = core.derive_estimate(t, target_category=o["object_category"], comparability_basis=["SAME_TYPE_CLASSIFICATION"],
                                              comparability_reason="schatting uit eigen typegroep, uitsluitend ter beoordeling", proposal_origin="RULE", target_type=t)
                    est = core.fmt_exact(core.gross_area_exact(dd["outer_width_m"], dd["outer_height_m"], o["quantity"]))
                    why = None
                except core.BrutoError as ex:
                    why = ex.code
            scen.append(OrderedDict([("kind", "MISSING_DIMENSION_POTENTIAL_ESTIMATE"), ("object_ids", [oid]),
                                     ("statement", f"{oid} heeft geen betrouwbare maat; een schatting uit het eigen type is " + ("mogelijk (niet gevalideerd)." if est else "niet mogelijk.")),
                                     ("effect", OrderedDict([("potential_estimated_area_m2_exact", est), ("reason_code_if_none", why), ("validated", False)]))]))
        if r["oc"] == "CONFLICT":
            ex_ = _gross(o)[0]
            scen.append(OrderedDict([("kind", "CONFLICT_AREA_AT_STAKE"), ("object_ids", [oid]),
                                     ("statement", f"{oid} is geblokkeerd door een conflict en zit niet in de basisstand."),
                                     ("effect", OrderedDict([("pieces_at_stake", o["quantity"]), ("area_m2_exact_at_stake", core.fmt_exact(ex_) if ex_ is not None else None),
                                                             ("rule_ids", sorted({x["rule_id"] for x in r["ir"] + r["dr"] if x["class"] == "CONFLICT"}))]))]))
    og = _uf_groups([s["object_ids"] for s in scen])
    scen.sort(key=lambda s: (s["kind"], s["object_ids"]))
    for i, s in enumerate(scen, 1):
        s["scenario_id"] = f"SCN-{i:03d}"
        s["additive"], s["is_final_quantity"] = False, False
        s["overlap_group"] = og[s["object_ids"][0]]
        s["note"] = "voorlopig reviewscenario; geen definitieve MJOP-hoeveelheid; niet optellen"
    scen = [OrderedDict(sorted(s.items())) for s in scen]

    cnt = lambda key, vals: OrderedDict((v, sum(1 for x in objs if x[key] == v)) for v in vals)  # noqa: E731
    pack = OrderedDict([
        ("contract_version", "bruto_review_pack_v2"), ("pack_id", ""), ("input_sha256", core.canonical_sha256(_normalized_input(inp))),
        ("calibration", calib), ("invariants", OrderedDict(INVARIANTS)),
        ("summary", OrderedDict([("object_count", len(objs)), ("by_overall_class", cnt("overall_class", CLASSES)),
                                 ("by_work_state", cnt("work_state", ("AUTO_PROVISIONAL", "INDIVIDUAL_REVIEW", "BLOCKED", "READY_FOR_GROUP_REVIEW"))),
                                 ("by_identity_class", OrderedDict((c, sum(1 for x in objs if x["identity_axis"]["class"] == c)) for c in CLASSES)),
                                 ("by_dimension_class", OrderedDict((c, sum(1 for x in objs if x["dimension_axis"]["class"] == c)) for c in CLASSES)),
                                 ("complete", True)])),
        ("objects", objs), ("work_queue", order), ("groups", groups), ("scenarios", scen),
        ("baseline_state", state), ("notes", list(NOTES))])
    pack = json.loads(json.dumps(pack))
    pack["pack_id"] = "BRP-" + core.canonical_sha256({k: v for k, v in pack.items() if k != "pack_id"})[:16]
    perrs = contracts.pack_errors(pack)
    if perrs:
        raise core.BrutoError("PACK_SCHEMA_INVALID", "; ".join(perrs[:5]))
    return pack


def pack_json(pack):
    return json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
