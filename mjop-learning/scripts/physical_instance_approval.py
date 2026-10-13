"""Physical Instance Approval Framework v1 — voorbereiding en controle van een aanvraag tot goedkeuring als fysieke instance.

Hergebruikt (en vervangt niets van): de OIC-kandidaten en -validatie (object_identity_pilot), review-JSON, P1-kwaliteitsreview,
pilotbesluitenregister, het onafhankelijke archiefregister, de bevroren frame-instance-store (alleen lezen), de 48 APP-besluiten
(alleen lezen) en de bewijscontrole met MAP-009.

Een approval request (IAR-*) is GEEN fysieke instance (FI-*). Dit framework heeft bewust geen schrijfpad naar de instance-store,
reserveert geen FI-id, koppelt geen BAG-pand en leidt geen hoeveelheid of kosten af. Fail-closed: elke fout, ontbrekend of
tegenstrijdig gegeven levert nooit een gunstiger uitkomst op dan NEEDS_MORE_EVIDENCE of REJECTED.

Drie strikt gescheiden niveaus (nooit automatisch in elkaar over te laten gaan):
  TECHNISCH GESCHIKT VOOR BEOORDELING  ->  MENSELIJK GOEDGEKEURD (niveau A)  ->  GEACTIVEERDE INSTANCE (bestaat in deze PR niet)
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import object_identity_pilot as OIP  # noqa: E402

PILOT_JSON = OIP.OUT_JSON
EVIDENCE_VERIFICATION_JSON = ROOT / "reports/frames/physical_object_identity_evidence_v1/physical_object_identity_evidence_verification_v1.json"
RECONCILIATION_JSON = ROOT / "reports/frames/physical_instance_approval_v1/physical_instance_evidence_reconciliation_v1.json"
INSTANCE_STORE = ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json"
APP_APPROVAL_MD = ROOT / "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md"
OUT_DIR = ROOT / "reports/frames/physical_instance_approval_v1"
OUT_JSON = ROOT / "reports/frames/physical_instance_approval_framework_v1.json"
OUT_MD = ROOT / "reports/frames/physical_instance_approval_framework_v1.md"
PACK_HTML = OUT_DIR / "IAR-OIC-VR-027_review_pack.html"
FRAMEWORK_VERSION = "physical_instance_approval_framework_v1"

STATUSES = ("DRAFT", "READY_FOR_HUMAN_REVIEW", "NEEDS_MORE_EVIDENCE", "APPROVED_FOR_ACTIVATION", "REJECTED")
TRANSITIONS = {
    "DRAFT": ["READY_FOR_HUMAN_REVIEW", "NEEDS_MORE_EVIDENCE", "REJECTED"],
    "READY_FOR_HUMAN_REVIEW": ["NEEDS_MORE_EVIDENCE", "REJECTED", "APPROVED_FOR_ACTIVATION"],
    "NEEDS_MORE_EVIDENCE": ["DRAFT", "REJECTED"],
    "APPROVED_FOR_ACTIVATION": ["NEEDS_MORE_EVIDENCE", "REJECTED"],   # intrekken of bij gewijzigd bewijs; nooit naar een instance
    "REJECTED": [],
}
STATUS_MEANING = {
    "DRAFT": "Aanvraag opgesteld; nog niet technisch beoordeeld.",
    "READY_FOR_HUMAN_REVIEW": "TECHNISCH GESCHIKT VOOR BEOORDELING. Zegt niets over de identiteit zelf en is geen goedkeuring.",
    "NEEDS_MORE_EVIDENCE": "Technisch niet geschikt: bewijs of menselijk besluit ontbreekt of is onvoldoende. Nieuw bewijs vraagt een nieuwe aanvraag-hash.",
    "APPROVED_FOR_ACTIVATION": "MENSELIJK GOEDGEKEURD voor fysieke identiteit (alleen niveau A). Alleen via een verifieerbaar menselijk besluit; maakt zelf geen instance.",
    "REJECTED": "Afgewezen (menselijk besluit) of geblokkeerd door de technische controle (conflict, vervalsing, beschadigde invoer). Eindstatus voor deze aanvraag-hash.",
}
HUMAN_DECISIONS = ("APPROVE_PHYSICAL_IDENTITY", "REJECT", "NEEDS_MORE_EVIDENCE")
LEVELS = {
    "A": "Fysieke objectidentiteit: tonen de observaties hetzelfde fysieke kozijn?",
    "B": "Pandtoewijzing: bij welk gebouw of BAG-pand hoort het kozijn?",
    "C": "Hoeveelheid, afmeting, onderhoudsactie en kosten van dat onderdeel.",
}
FORBIDDEN_EFFECTS = ["create_or_modify_frame_instance", "reserve_instance_id", "merge_observations", "link_bag_pand", "set_dimensions", "change_building_total",
                     "change_unique_count", "set_quantity", "set_cost", "set_maintenance_action", "change_photo2_inventory", "change_app_decision",
                     "change_pilot_decision", "change_source_observation", "activate_repeat_multiplier", "write_instance_store"]
ALLOWED_EFFECTS = ["produce_draft_request", "produce_human_review_pack", "report_validation_results", "record_human_decision_in_separate_later_register"]
REQUIRED_FIELDS = ["approval_request_id", "candidate_group_id", "observation_ids", "supporting_relation_ids", "evidence_refs", "source_hashes", "candidate_status",
                   "proposed_instance_type", "approval_status", "human_decision", "decision_provenance", "unresolved_questions", "validation_results",
                   "allowed_effects", "forbidden_effects", "decision_levels", "evidence_reconciliation", "request_hash"]
RECON_OUTCOMES = ("COMPATIBLE_DIFFERENT_SCOPE", "GENUINE_EVIDENCE_CONFLICT", "INSUFFICIENT_TO_RECONCILE")
SUPERSEDED_HASHES = ["aa556297be5d6713d298a06fa40492b8", "34c61b5e5f274764e86491a838502ede"]   # eerder gepubliceerde request_hashes (PR #43 head 0483632 en a02f98d); verouderd, nooit gebruikt voor een besluit
STRIP_CORRECTION = "folie rechts (de verticale plakstrook is alleen in MAP-003/004 zichtbaar en in MAP-009 niet verifieerbaar; zie reconciliatierapport)"
FI_PATTERN = re.compile(r"\bFI-[A-Z0-9]")
NON_HUMAN = re.compile(r"claude|\bai\b|assistant|bot|automat", re.I)
ARCHIVE_ALIAS = {"maldenhof_1": None, "maldenhof_2": "MAP-002", "maldenhof_3": "MAP-015"}   # foto-bestandsnaam in de instance-store -> archief-id
EXTRA_QUESTIONS = [
    "De bronfoto's (MAP-003, MAP-004) en de aanvullende foto MAP-009 zijn van dezelfde dag (14-08-2026): onafhankelijk in toestel en hoek, niet in tijd.",
    "De onderscheidende kenmerken (merktekens, gordijn met voorwerpen, folie met plakstrook) zijn deels tijdelijk en bewijzen geen blijvende identiteit van het kozijn.",
    "De MAP-009-beoordeling (PR #42) en de P1-kwaliteitsreview van VR-045 zijn verzoend als COMPATIBLE_DIFFERENT_SCOPE (andere uitsnede en bewijsclaim); dat is een AI-uitleg en geen menselijk besluit, en VR-045 blijft zonder menselijk besluit.",
    "De plakstrook is in MAP-009 niet verifieerbaar; de PR #42-tekst die dat wel stelde is gecorrigeerd. MAP-009 blijft aanvullend en wordt niet als bewijs gebruikt voor de status van het OIC."]
LEVEL_B_C_KEYS = ("bag_pand_id", "quantity", "cost", "dimensions", "maintenance_action", "building_total", "unique_total", "m2")


# ----------------------------------------------------------------------------------------------------------------------------------
def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def request_hash(req):
    """Hash over de inhoud die de identiteitsvraag bepaalt; niet over status, besluit en validatieresultaat."""
    core = {k: req.get(k) for k in ("approval_request_id", "candidate_group_id", "observation_ids", "supporting_relation_ids", "source_hashes", "candidate_status",
                                    "proposed_instance_type", "evidence_refs", "decision_levels", "photo_ids", "relation_strength_in_source", "evidence_class", "unresolved_questions", "evidence_reconciliation", "additional_evidence", "decision_provenance")}
    return digest(core)[:32]


def parse_app_decisions(md_text):
    rows = {}
    for line in md_text.splitlines():
        m = re.match(r"^\| (APP-\d{3}) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (OPEN|[A-Z_]+) \|\s*$", line)
        if m:
            rows[m.group(1)] = {"app_id": m.group(1), "subject": m.group(2), "scope": m.group(3), "question": m.group(4), "status": m.group(6)}
    return rows


def app_kind(row):
    s = row["subject"]
    if s.startswith("Overlap SOC"):
        return "PHOTO_OVERLAP_QUESTION"
    if s.startswith("Plaatlezing"):
        return "PLATE_AND_PAND_LINK_LEVEL_B"
    if s.startswith("Geschiktheid"):
        return "PHOTO_SUITABILITY"
    if s.startswith("Telregel") or s.startswith("Zichtbaarheid"):
        return "COUNTING_RULE"
    if s.startswith("Plaatregel"):
        return "PLATE_RULE_LEVEL_B"
    return "OTHER"


def load_context():
    ctx = OIP.load_context()
    ctx["oic_registry"] = {c["candidate_group_id"]: c for c in _load(PILOT_JSON)["candidates"]}
    ctx["instance_store"] = _load(INSTANCE_STORE)
    ctx["app_decisions"] = parse_app_decisions(APP_APPROVAL_MD.read_text(encoding="utf-8"))
    ctx["verification"] = _load(EVIDENCE_VERIFICATION_JSON)
    ctx["reconciliation"] = _load(RECONCILIATION_JSON)
    ctx["reconciliation_sha256"] = hashlib.sha256(RECONCILIATION_JSON.read_bytes()).hexdigest()
    ctx["human_approvals"] = []   # er bestaat in deze PR geen register van instance-besluiten; bewust leeg
    ctx["other_requests"] = []
    return ctx


# ----------------------------------------------------------------------------------------------------------------------------------
def reconciliation_summary(ctx):
    """Wat de aanvraag over de bewijsverzoening zegt; volledig afgeleid uit het reconciliatierecord (JSON), niets zelf bedacht."""
    rec = ctx["reconciliation"]
    return {"outcome": rec["outcome"], "record": RECONCILIATION_JSON.name, "record_sha256": ctx["reconciliation_sha256"],
            "map009_role": rec["consequences_for_iar_oic_vr_027"]["map009_role"], "oic_depends_on_map009": rec["consequences_for_iar_oic_vr_027"]["oic_depends_on_map009"],
            "vr045_human_decision": rec["vr045_as_reviewed"]["human_decision"], "vr045_modified": rec["effects"]["vr045_modified"],
            "features": {f["id"]: f["class"] for f in rec["features"]}, "corrections": list(rec["corrections_to_pr42_text"]),
            "is_human_decision": False}


def build_request(ctx, oic_id):
    """Maakt een CONCEPT-aanvraag uit een bestaand OIC. Verzint niets: alles komt uit het live geëvalueerde kandidaatverband."""
    rid = oic_id[len("OIC-"):]
    ev = OIP.evaluate_relation(ctx, rid)
    if not ev["creates_identity_link"]:
        raise ValueError("Geen kandidaatverband om aan te vragen: " + "; ".join(ev["reasons"]))
    cand = OIP.to_candidate(ctx, ev)
    verification = ctx.get("verification") or {}
    extra = copy.deepcopy(verification.get("additional_matches", []))
    for m in extra:      # reconciliatie: de plakstrook is in MAP-009 niet verifieerbaar
        m["arguments"] = [a.replace("folie met plakstrook rechts", STRIP_CORRECTION) for a in m.get("arguments", [])]
        m["corrected_by"] = RECONCILIATION_JSON.name
    req = {
        "kind": "PHYSICAL_INSTANCE_APPROVAL_REQUEST",
        "approval_request_id": "IAR-" + cand["candidate_group_id"],
        "candidate_group_id": cand["candidate_group_id"],
        "observation_ids": list(cand["observation_ids"]),
        "photo_ids": list(cand["photo_ids"]),
        "supporting_relation_ids": list(cand["supporting_relation_ids"]),
        "evidence_refs": copy.deepcopy(cand["evidence_refs"]),
        "source_hashes": dict(cand["source_hashes"]),
        "candidate_status": cand["identity_status"],
        "relation_strength_in_source": cand["relation_strength_in_source"],
        "evidence_class": cand["evidence_class"],
        "proposed_instance_type": {"component_type": "EXTERIOR_FRAME", "observation_type": ctx["observations"][cand["observation_ids"][0]].get("observation_type"),
                                   "subtype": "UNKNOWN", "material": "UNKNOWN", "status": "PROPOSED_NOT_DECIDED"},
        "approval_status": "DRAFT",
        "human_decision": None,
        "decision_provenance": {"candidate_decision": cand["decision_refs"], "instance_decision": None,
                                "note": "Het pilotbesluit RV-REL-VR-027 = SAME_PHYSICAL_OBJECT_CANDIDATE (ChatGPT-bevestiging) is geen instance-besluit."},
        "additional_evidence": extra,
        "evidence_reconciliation": reconciliation_summary(ctx),
        "superseded_request_hashes": list(SUPERSEDED_HASHES),
        "unresolved_questions": list(cand["unresolved_questions"]) + EXTRA_QUESTIONS,
        "validation_results": None,
        "allowed_effects": list(ALLOWED_EFFECTS),
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
        "decision_levels": {
            "A": {"question": LEVELS["A"], "status": "NOT_DECIDED", "decided_by_human": False},
            "B": {"question": LEVELS["B"], "status": "NOT_DECIDED", "bag_pand_id": None},
            "C": {"question": LEVELS["C"], "status": "NOT_DECIDED", "quantity": None, "cost": None, "dimensions": None},
        },
        "is_instance": False,
        "frame_instance_id": None,
        "reserved_instance_id": None,
        "request_note": "Een approval request is geen fysieke instance en reserveert geen instance-id.",
    }
    req["request_hash"] = request_hash(req)
    return req


# ----------------------------------------------------------------------------------------------------------------------------------
def _chk(cid, title, result, detail, kind="AUTO_VALIDATED_FACT"):
    """result: PASS | NEEDS_EVIDENCE | BLOCK"""
    return {"id": cid, "title": title, "result": result, "detail": detail, "kind": kind}


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_strings(v)


def _structure_check(req):
    problems = []
    if not isinstance(req, dict):
        return ["AANVRAAG_GEEN_OBJECT"]
    for f in REQUIRED_FIELDS:
        if f not in req:
            problems.append("VELD_ONTBREEKT " + f)
    if problems:
        return problems
    if req["approval_status"] not in STATUSES:
        problems.append("ONBEKENDE_STATUS")
    if not (isinstance(req["approval_request_id"], str) and req["approval_request_id"].startswith("IAR-")):
        problems.append("AANVRAAG_ID_ONGELDIG")
    if not (isinstance(req["observation_ids"], list) and len(req["observation_ids"]) == 2 and all(isinstance(x, str) for x in req["observation_ids"])
            and len(set(req["observation_ids"])) == 2):
        problems.append("OBSERVATIES_ONGELDIG_OF_NIET_EEN_PAAR")
    if not (isinstance(req["supporting_relation_ids"], list) and req["supporting_relation_ids"] and all(isinstance(x, str) for x in req["supporting_relation_ids"])):
        problems.append("RELATIES_ONGELDIG")
    if not (isinstance(req["source_hashes"], dict) and req["source_hashes"] and all(isinstance(v, str) for v in req["source_hashes"].values())):
        problems.append("BRONHASHES_ONGELDIG")
    if not isinstance(req["evidence_refs"], list) or not isinstance(req["unresolved_questions"], list):
        problems.append("BEWIJS_OF_VRAGEN_ONGELDIG")
    if req.get("is_instance") is not False or req.get("frame_instance_id") is not None or req.get("reserved_instance_id") is not None:
        problems.append("AANVRAAG_CLAIMT_INSTANCE_OF_RESERVEERT_ID")
    if any(FI_PATTERN.search(s) for s in _walk_strings(req)):
        problems.append("FI_ID_IN_AANVRAAG")
    if not isinstance(req["forbidden_effects"], list) or not set(FORBIDDEN_EFFECTS) <= set(req["forbidden_effects"]):
        problems.append("VERBODEN_EFFECTEN_ONVOLLEDIG")
    if not isinstance(req["allowed_effects"], list) or req["allowed_effects"] != ALLOWED_EFFECTS:
        problems.append("TOEGESTANE_EFFECTEN_BEVATTEN_VERBODEN_EFFECT")
    lv = req["decision_levels"]
    if not (isinstance(lv, dict) and set(lv) == {"A", "B", "C"} and all(isinstance(v, dict) for v in lv.values())):
        problems.append("BESLUITNIVEAUS_ONGELDIG")
    else:
        if lv["B"].get("bag_pand_id") is not None or lv["B"].get("status") != "NOT_DECIDED":
            problems.append("NIVEAU_B_PANDKOPPELING_NIET_TOEGESTAAN")
        if any(lv["C"].get(k) is not None for k in ("quantity", "cost", "dimensions")) or lv["C"].get("status") != "NOT_DECIDED":
            problems.append("NIVEAU_C_HOEVEELHEID_OF_KOSTEN_NIET_TOEGESTAAN")
        if lv["A"].get("status") != "NOT_DECIDED" or lv["A"].get("decided_by_human") is not False:
            problems.append("NIVEAU_A_BESLUIT_IN_AANVRAAG_ZELF_NIET_TOEGESTAAN")
    for k in LEVEL_B_C_KEYS:
        if req.get(k) not in (None, ""):
            problems.append("NIVEAU_B_OF_C_VELD_IN_AANVRAAG " + k)
    sup = req.get("superseded_request_hashes")
    if sup != SUPERSEDED_HASHES or req["request_hash"] in sup:
        problems.append("VEROUDERDE_HASHES_ONGELDIG_OF_BEVAT_HUIDIGE_HASH")
    if req["approval_status"] != "DRAFT" or req["human_decision"] is not None:
        problems.append("VOORGESTELD_BESLUIT_OF_STATUS_NIET_VERIFIEERBAAR")   # status volgt uit validatie of verifieerbaar besluit, niet uit de aanvraag zelf
    elif request_hash(req) != req["request_hash"]:
        problems.append("AANVRAAG_HASH_KLOPT_NIET")
    return problems


def _live_oic(ctx, oic_id):
    rid = oic_id[len("OIC-"):]
    ev = OIP.evaluate_relation(ctx, rid)
    return ev, (OIP.to_candidate(ctx, ev) if ev["creates_identity_link"] else None)


def _endpoint_has_obs(txt, obs):
    """Waarnemings-id staat als OBS-MAP003-011 of als OBS-MAP003-011/012 (gegroepeerd) in een eindpunt."""
    m = re.match(r"^(OBS-MAP\d{3})-(\d{3})$", obs)
    if not m:
        return obs in txt
    for g in re.finditer(re.escape(m.group(1)) + r"-(\d{3})((?:/\d{3})*)", txt):
        nums = [g.group(1)] + [x for x in g.group(2).split("/") if x]
        if m.group(2) in nums:
            return True
    return False


def _evaluate(ctx, req):
    checks, questions, required = [], [], []
    ok_struct = _structure_check(req)
    if ok_struct:
        checks.append(_chk("S0", "Aanvraagstructuur en verboden velden", "BLOCK", ok_struct))
        return checks, questions, required
    checks.append(_chk("S0", "Aanvraagstructuur en verboden velden", "PASS", "alle verplichte velden, geen FI-id, geen niveau B/C-inhoud, geen voorgesteld besluit"))
    oic_id, obs_ids = req["candidate_group_id"], req["observation_ids"]

    # 1 + 2 OIC bestaat en heeft de vereiste status (live opnieuw bepaald, niet uit de aanvraag overgenomen)
    reg = ctx["oic_registry"].get(oic_id) if isinstance(ctx.get("oic_registry"), dict) else None
    if not isinstance(reg, dict):
        checks.append(_chk("C1", "Het OIC-verband bestaat", "BLOCK", f"{oic_id} staat niet in het OIC-register (pilotrapport)"))
        return checks, questions, required
    checks.append(_chk("C1", "Het OIC-verband bestaat", "PASS", f"{oic_id} staat in het pilotrapport"))
    ev, live = _live_oic(ctx, oic_id)
    if live is None:
        checks.append(_chk("C2", "OIC heeft status SUPPORTED_CANDIDATE", "BLOCK", f"live evaluatie levert geen kandidaatverband: {ev['reasons']}"))
        return checks, questions, required
    if reg.get("identity_status") != live["identity_status"]:
        checks.append(_chk("C2", "OIC heeft status SUPPORTED_CANDIDATE", "BLOCK", f"register zegt {reg.get('identity_status')}, live evaluatie {live['identity_status']}: register wijkt af"))
        return checks, questions, required
    if live["identity_status"] != "SUPPORTED_CANDIDATE" or req["candidate_status"] != "SUPPORTED_CANDIDATE":
        checks.append(_chk("C2", "OIC heeft status SUPPORTED_CANDIDATE", "NEEDS_EVIDENCE", f"live status {live['identity_status']}, aanvraag {req['candidate_status']}"))
    else:
        checks.append(_chk("C2", "OIC heeft status SUPPORTED_CANDIDATE", "PASS", "live status SUPPORTED_CANDIDATE (opnieuw bepaald uit de brondata)"))

    # aanvraag moet exact het live verband beschrijven: alle bewijsclaims worden vergeleken met een vers uit de brondata opgebouwde aanvraag
    try:
        exp = build_request(ctx, oic_id)
    except Exception as exc:   # noqa: BLE001
        exp = None
        checks.append(_chk("C3a", "Aanvraag komt overeen met het live kandidaatverband", "BLOCK", f"verwachte aanvraag niet op te bouwen: {type(exc).__name__}"))
    if exp is not None:
        drift = [k for k in ("observation_ids", "supporting_relation_ids", "source_hashes", "photo_ids", "relation_strength_in_source", "evidence_class", "evidence_refs",
                             "proposed_instance_type", "additional_evidence", "decision_provenance") if req.get(k) != exp[k]]
        if any(q not in req["unresolved_questions"] for q in exp["unresolved_questions"]):
            drift.append("unresolved_questions (onzekerheden mogen niet worden verwijderd)")
        if drift:
            checks.append(_chk("C3a", "Aanvraag komt overeen met het live kandidaatverband", "BLOCK", "afwijking in " + ", ".join(drift)))
        else:
            checks.append(_chk("C3a", "Aanvraag komt overeen met het live kandidaatverband", "PASS",
                               "observaties, foto's, relaties, bronhashes, relatiesterkte, bewijsklasse, bewijsverwijzingen, type, aanvullend bewijs en herkomst identiek aan een vers opgebouwde aanvraag"))

    # 3 observaties geldig; 4 bronhashes (review-bron, archiefregister en bewijsreferenties)
    probs = [p for o in obs_ids for p in [OIP._obs_problem(o, ctx["observations"].get(o))] if p]
    checks.append(_chk("C3", "Alle bronobservaties zijn geldig", "BLOCK" if probs else "PASS", probs or "geldig, geen instance, telt nergens, geen pandkoppeling"))
    bad = []
    for o in obs_ids:
        ob = ctx["observations"].get(o) or {}
        pid, h = ob.get("photo_id"), ob.get("source_sha256")
        if req["source_hashes"].get(pid) != h or ctx["photo_sha"].get(pid) != h or ctx["archive_sha"].get(pid) != h:
            bad.append(f"{o}/{pid}")
        refs = [e for e in req["evidence_refs"] if isinstance(e, dict) and e.get("type") == "original_crop" and e.get("observation_id") == o]
        if not refs or any(e.get("sha256") != h or e.get("sha256_verified") is not True for e in refs):
            bad.append(f"{o}/original_crop")
    checks.append(_chk("C4", "Alle bronhashes komen overeen (review-bron, onafhankelijk archiefregister, bewijsreferentie)", "BLOCK" if bad else "PASS",
                       ("hash wijkt af of ontbreekt: " + ", ".join(bad)) if bad else "SHA256 identiek in alle drie de bronnen"))

    # 5 onderliggende fysieke-objectrelatie
    rel_bad = []
    for rid in req["supporting_relation_ids"]:
        rel, item = ctx["relations"].get(rid), ctx["pack"].get("RV-REL-" + rid)
        sem = (item or {}).get("relation_semantics", {}) if isinstance(item, dict) else {}
        if not isinstance(rel, dict) or rel.get("class") != "POSSIBLY_SAME_PHYSICAL_FRAME" or sem.get("relation_type") != "PHYSICAL_OBJECT":
            rel_bad.append(f"{rid}: geen PHYSICAL_OBJECT-relatie (gevelsectie of onbekend)")
            continue
        ends = {str(rel["left"]).split(":")[-1], str(rel["right"]).split(":")[-1]}
        if ends != set(obs_ids):
            rel_bad.append(f"{rid}: eindpunten {sorted(ends)} zijn niet exact de observaties van de aanvraag")
    checks.append(_chk("C5", "De onderliggende relatie is een geldige fysieke-objectrelatie met exact deze twee eindpunten", "BLOCK" if rel_bad else "PASS",
                       rel_bad or "VR-relatie is PHYSICAL_OBJECT; gevelsectie-relaties (SAME_FACADE_SECTION) tellen niet"))

    # 6 menselijk kandidaatbesluit geldig en herleidbaar
    drefs = req["decision_provenance"].get("candidate_decision") if isinstance(req.get("decision_provenance"), dict) else None
    d_ok = isinstance(drefs, list) and len(drefs) == 1 and isinstance(drefs[0], dict)
    d_probs = []
    if not d_ok:
        d_probs.append("kandidaatbesluit ontbreekt in de aanvraag")
    else:
        dr = drefs[0]
        reg_dec = ctx["decisions"].get(dr.get("review_id")) if isinstance(ctx.get("decisions"), dict) else None
        if not isinstance(reg_dec, dict):
            d_probs.append("besluit niet in het pilotregister")
        else:
            prov = reg_dec.get("provenance") or {}
            if reg_dec.get("decision") != "SAME" or dr.get("decision") != "SAME":
                d_probs.append("besluit is niet SAME")
            if prov.get("decision_source") not in OIP.HUMAN_SOURCES or reg_dec.get("source_ref_hash_validated") is not True:
                d_probs.append("herkomst niet menselijk of bronhash niet gevalideerd")
            if reg_dec.get("source_ref_hash") != dr.get("source_ref_hash") or ctx["pack"].get(dr.get("review_id"), {}).get("ref_hash") != dr.get("source_ref_hash"):
                d_probs.append("besluit-hash komt niet overeen met het pack")
            if dr.get("review_id") != "RV-REL-" + req["supporting_relation_ids"][0]:
                d_probs.append("besluit hoort bij een andere relatie")
    if d_probs:
        checks.append(_chk("C6", "Menselijk kandidaatbesluit (SAME) is geldig en herleidbaar", "NEEDS_EVIDENCE", d_probs))
    else:
        checks.append(_chk("C6", "Menselijk kandidaatbesluit (SAME) is geldig en herleidbaar", "PASS",
                           "RV-REL-%s = SAME, menselijke herkomst (%s), source_ref_hash gevalideerd. Dit is een KANDIDAAT-besluit, geen instance-besluit." % (
                               req["supporting_relation_ids"][0], drefs[0].get("approval_channel"))))

    # 7 onderscheidend bewijs (meer dan louter visuele gelijkenis van het type/de indeling)
    basis = set(live["evidence_basis"])
    anchor, blockers = basis & OIP.ANCHORS, basis & OIP.BLOCKING_BASIS
    if live["evidence_class"] != "STRONG_VISUAL_SUPPORT" or not anchor or blockers:
        checks.append(_chk("C7", "Visuele onderbouwing is onderscheidend (geen louter gelijkende buurwoningen)", "NEEDS_EVIDENCE",
                           f"klasse {live['evidence_class']}, anker {sorted(anchor)}, blokkades {sorted(blockers)}"))
    else:
        checks.append(_chk("C7", "Visuele onderbouwing is onderscheidend (geen louter gelijkende buurwoningen)", "PASS",
                           f"STRONG_VISUAL_SUPPORT met anker {sorted(anchor)}; feature-match is slechts ondersteunend. Let op: alle onderbouwing is visueel; een niet-visueel anker (bv. leesbaar nummer bij dit raam) ontbreekt."))

    # 8 tegenstrijdige of onbeslisbare besluiten, en open gerelateerde relaties
    contra, undecided, open_rel = [], [], []
    for rid, rel in sorted(ctx["relations"].items()):
        if rid in req["supporting_relation_ids"] or not isinstance(rel, dict):
            continue
        txt = f"{rel.get('left')} {rel.get('right')}"
        if not any(_endpoint_has_obs(txt, o) for o in obs_ids):
            continue
        d = (ctx["decisions"].get("RV-REL-" + rid) or {}).get("decision") if isinstance(ctx.get("decisions"), dict) else None
        if d == "DIFFERENT":
            contra.append(rid)
        elif d == "UNDECIDABLE":
            undecided.append(rid)
        elif d is None:
            q = ctx["quality"].get("RV-REL-" + rid, {})
            open_rel.append({"relation_id": rid, "human_decision": None, "claude_proposal": ctx["pack"].get("RV-REL-" + rid, {}).get("claude_proposal"),
                             "quality_finding": q.get("finding"), "quality_evidence_class": q.get("evidence_class")})
    if contra:
        checks.append(_chk("C8", "Geen tegenstrijdige DIFFERENT- of UNDECIDABLE-besluiten genegeerd", "BLOCK", f"menselijk DIFFERENT op {contra}"))
    elif undecided:
        checks.append(_chk("C8", "Geen tegenstrijdige DIFFERENT- of UNDECIDABLE-besluiten genegeerd", "NEEDS_EVIDENCE", f"menselijk UNDECIDABLE op {undecided}"))
    else:
        checks.append(_chk("C8", "Geen tegenstrijdige DIFFERENT- of UNDECIDABLE-besluiten genegeerd", "PASS",
                           "geen menselijk DIFFERENT/UNDECIDABLE op relaties die deze observaties raken; %d gerelateerde relatie(s) zonder besluit blijven zichtbaar open" % len(open_rel)))
    for r in open_rel:
        questions.append(f"Gerelateerde relatie {r['relation_id']} (zonder menselijk besluit) raakt deze observaties; Claude-voorstel {r['claude_proposal']}; kwaliteitsreview: {r['quality_finding']}")
        required.append(f"Besluit over {r['relation_id']} (RV-REL-{r['relation_id']}), of expliciete erkenning dat het open blijft")
    req["_open_relations"] = sorted(r["relation_id"] for r in open_rel)

    # 9 conflict met bestaande instances, andere kandidaten en andere aanvragen
    conflicts, infos = [], []
    store = ctx.get("instance_store") or {}
    inst = list(store.get("instances", [])) + [s.get("instance", {}) for s in store.get("superseded_instances", []) if isinstance(s, dict)]
    mapped = {}
    for i in inst:
        for ref in (i.get("source_refs") or []):
            if isinstance(ref, dict) and ref.get("ref_type") == "PHOTO":
                mapped.setdefault(ARCHIVE_ALIAS.get(ref.get("photo_id"), ref.get("photo_id")), set()).add(i.get("frame_instance_id"))
    blob = canonical(store)
    for o in obs_ids + [oic_id]:
        if o in blob:
            conflicts.append(f"{o} komt al voor in de instance-store")
    for pid in req.get("photo_ids", []):
        if pid in mapped:
            conflicts.append(f"foto {pid} is bron van bestaande instance(s) {sorted(mapped[pid])}")
    for rid, rel in sorted(ctx["relations"].items()):
        txt = f"{rel.get('left')} {rel.get('right')}" if isinstance(rel, dict) else ""
        if any(_endpoint_has_obs(txt, o) for o in obs_ids) and re.search(r"FC-M2|FI-M2|maldenhof_2|MAP-002", txt):
            conflicts.append(f"{rid} koppelt een van de observaties aan foto 2 (bevroren)")
    soc = [s for s in (ctx.get("soc_groups") or []) if set(req.get("photo_ids", [])) & set(s.get("photos", []))]
    for s in soc:
        if set(s.get("photos", [])) & set(mapped):
            infos.append(f"{s['id']}: foto-niveau overlap met bevroren foto {sorted(set(s['photos']) & set(mapped))}; geen kozijn-niveau claim")
    for other_id, other in sorted((ctx.get("oic_registry") or {}).items()):
        if other_id != oic_id and isinstance(other, dict) and set(other.get("observation_ids", [])) & set(obs_ids):
            conflicts.append(f"{other_id} claimt overlappende observaties {sorted(set(other['observation_ids']) & set(obs_ids))}")
    for o_req in ctx.get("other_requests") or []:
        if isinstance(o_req, dict) and o_req.get("approval_request_id") != req["approval_request_id"] and set(o_req.get("observation_ids", [])) & set(obs_ids):
            conflicts.append(f"aanvraag {o_req.get('approval_request_id')} claimt overlappende observaties")
        if isinstance(o_req, dict) and o_req.get("approval_request_id") == req["approval_request_id"] and o_req.get("request_hash") != req["request_hash"]:
            conflicts.append("zelfde aanvraag-id met afwijkende inhoud")
    if conflicts:
        checks.append(_chk("C9", "Geen conflict met bestaande instances, andere kandidaten of eerder goedgekeurde objectidentiteiten", "BLOCK", conflicts))
    else:
        checks.append(_chk("C9", "Geen conflict met bestaande instances, andere kandidaten of eerder goedgekeurde objectidentiteiten", "PASS",
                           ["instance-store: %d actieve + %d vervangen instances, alle foto 2 (maldenhof_2 = MAP-002); geen verwijzing naar deze observaties of foto's" % (
                               len(store.get("instances", [])), len(store.get("superseded_instances", [])))] + infos))

    # 10 relatie met de 48 APP-besluiten expliciet onderzocht
    apps = ctx.get("app_decisions") or {}
    scope_photos = set(req.get("photo_ids", [])) | {a.get("photo_id") for a in req.get("additional_evidence", []) if isinstance(a, dict)}
    related = []
    for a in apps.values():
        if set(re.findall(r"MAP-\d{3}", a["scope"] + " " + a["subject"])) & scope_photos or a["subject"].startswith(("Telregel", "Zichtbaarheid", "Plaatregel")):
            maps = set(re.findall(r"MAP-\d{3}", a["scope"] + " " + a["subject"]))
            req_photos = set(req.get("photo_ids", []))
            direct = app_kind(a) == "PHOTO_OVERLAP_QUESTION" and (req_photos <= maps or (maps & scope_photos and maps & (scope_photos - req_photos)))
            related.append({"app_id": a["app_id"], "subject": a["subject"], "kind": app_kind(a), "status": a["status"], "relevance": "DIRECT" if direct else "INDIRECT"})
    related.sort(key=lambda r: r["app_id"])
    non_open = [r["app_id"] for r in related if r["status"] != "OPEN"]
    if len(apps) != 48 or not related:
        checks.append(_chk("C10", "Relatie met de 48 APP-besluiten expliciet onderzocht", "BLOCK", f"APP-tabel onvolledig ({len(apps)} rijen) of niets gerelateerd"))
    else:
        overlap = [r["app_id"] for r in related if r["relevance"] == "DIRECT"]
        checks.append(_chk("C10", "Relatie met de 48 APP-besluiten expliciet onderzocht", "PASS",
                           f"{len(related)} gerelateerd; direct relevante fotoniveau-overlapvragen {overlap} (de rest indirect: plaat/pand niveau B, geschiktheid, telregel); alle blijven {'OPEN' if not non_open else 'status: ' + str(non_open)}; geen wordt door deze aanvraag beantwoord of gewijzigd"))
        for r in related:
            if r["relevance"] == "DIRECT":
                questions.append(f"{r['app_id']} ({r['subject']}) is een open fotoniveau-vraag over dezelfde foto's; die is niet gelijk aan dit kozijnniveau-verband.")
                required.append(f"{r['app_id']}: antwoorden of expliciet laten openstaan (verplicht te erkennen in het instance-besluit)")
    # 11 bewijsverzoening aanwezig, consistent met de aanvraag, en VR-045 nog zonder menselijk besluit
    rec = ctx.get("reconciliation")
    rp = []
    if not isinstance(rec, dict) or rec.get("outcome") not in RECON_OUTCOMES:
        rp.append("reconciliatierecord ontbreekt of heeft een onbekende uitkomst")
    else:
        try:
            if req["evidence_reconciliation"] != reconciliation_summary(ctx):
                rp.append("aanvraag toont andere bewijsverzoening dan het record (verouderd of gewijzigd)")
            eff = rec["effects"]
            if eff.get("vr045_modified") is not False or eff.get("human_decisions_created") != 0 or eff.get("instances_created") != 0:
                rp.append("record meldt een wijziging van VR-045, een besluit of een instance")
            if rec["consequences_for_iar_oic_vr_027"].get("oic_depends_on_map009") is not False:
                rp.append("OIC mag niet van MAP-009 afhangen")
        except (KeyError, TypeError) as exc:
            rp.append("reconciliatierecord onvolledig: " + type(exc).__name__)
    vr45 = (ctx.get("decisions") or {}).get("RV-REL-VR-045") if isinstance(ctx.get("decisions"), dict) else None
    if rp:
        checks.append(_chk("C11", "Bewijsverzoening (VR-045/MAP-009) consistent met de aanvraag", "BLOCK", rp))
    elif vr45 is not None:
        checks.append(_chk("C11", "Bewijsverzoening (VR-045/MAP-009) consistent met de aanvraag", "NEEDS_EVIDENCE", "er is inmiddels een menselijk besluit over VR-045; de aanvraag moet opnieuw worden opgesteld (verouderd)"))
    else:
        checks.append(_chk("C11", "Bewijsverzoening (VR-045/MAP-009) consistent met de aanvraag", "PASS",
                           f"uitkomst {rec['outcome']} (AI-uitleg, geen menselijk besluit); MAP-009 {rec['consequences_for_iar_oic_vr_027']['map009_role']}; VR-045 zonder menselijk besluit; aanvraag en record komen overeen"))
    req["_related_app_decisions"] = related
    return checks, questions, required


def evaluate_request(ctx, req):
    """Veilige ingang: nooit een uitzondering, nooit gunstiger dan de zwakste check. Geeft de aanvraag terug met validation_results en afgeleide status."""
    out = copy.deepcopy(req) if isinstance(req, dict) else {"approval_request_id": None}
    try:
        checks, questions, required = _evaluate(ctx, out)
    except Exception as exc:   # noqa: BLE001 — fail-closed: beschadigde invoer mag nooit tot goedkeuring leiden
        checks, questions, required = [_chk("S9", "Onverwachte fout bij validatie", "BLOCK", f"{type(exc).__name__}: {str(exc)[:160]}")], [], []
    related = out.pop("_related_app_decisions", [])
    open_relations = out.pop("_open_relations", [])
    results = {c["result"] for c in checks}
    if "BLOCK" in results:
        verdict, status = "BLOCKED", "REJECTED"
    elif "NEEDS_EVIDENCE" in results:
        verdict, status = "NEEDS_MORE_EVIDENCE", "NEEDS_MORE_EVIDENCE"
    else:
        verdict, status = "SUITABLE_FOR_HUMAN_REVIEW", "READY_FOR_HUMAN_REVIEW"
    out["validation_results"] = {
        "technical_verdict": verdict, "checks": checks, "blocked_by": [c["id"] for c in checks if c["result"] == "BLOCK"],
        "needs_evidence_by": [c["id"] for c in checks if c["result"] == "NEEDS_EVIDENCE"], "related_app_decisions": related,
        "open_related_relations": open_relations,
        "meaning": "Technisch geschikt voor beoordeling is NIET: menselijk goedgekeurd, en nooit: geactiveerde instance.",
    }
    out["approval_status"] = status
    out["rejected_by"] = "TECHNICAL_VALIDATION" if status == "REJECTED" else None
    out["derived_open_questions"] = questions     # door de validatie afgeleid; de ingediende unresolved_questions blijven ongewijzigd (hash)
    out["required_human_decisions"] = required
    out["human_decision"] = None
    out["is_instance"] = False
    return out


def process_batch(ctx, requests):
    """Herhaalde verwerking van dezelfde aanvraag levert geen tweede record: identieke duplicaten worden genegeerd, afwijkende botsen (beide geblokkeerd)."""
    seen, out = {}, []
    for r in requests:
        rid = r.get("approval_request_id") if isinstance(r, dict) else None
        if rid in seen:
            if seen[rid]["request_hash"] == r.get("request_hash"):
                continue
            seen[rid]["_conflict"] = True
            r = dict(r, _conflict=True)
        else:
            seen[rid] = dict(r)
        out.append(r)
    res = []
    for r in out:
        c = dict(ctx, other_requests=[x for x in out if x is not r and isinstance(x, dict)])
        e = evaluate_request(c, {k: v for k, v in r.items() if k != "_conflict"})
        if r.get("_conflict") or seen.get(r.get("approval_request_id"), {}).get("_conflict"):
            e["approval_status"] = "REJECTED"
            e["rejected_by"] = "TECHNICAL_VALIDATION"
            e["validation_results"]["technical_verdict"] = "BLOCKED"
            e["validation_results"]["blocked_by"].append("DUBBELE_AANVRAAG_MET_AFWIJKENDE_INHOUD")
        res.append(e)
    return res


# ----------------------------------------------------------------------------------------------------------------------------------
RECORD_KEYS = {"decision_id", "request_id", "request_hash", "decision", "level", "covers_levels", "decided_by", "decision_source", "statement", "acknowledged_app_decisions",
               "acknowledged_open_relations"}


def verify_human_approval(ctx, req, rec):
    """Verifieerbaar menselijk niveau-A-besluit voor deze exacte aanvraag. Retourneert (ok, redenen). Fail-closed; de aanvraag wordt zelf opnieuw beoordeeld
    en een door de aanroeper meegegeven validatieresultaat wordt nooit vertrouwd."""
    p = []
    if not isinstance(rec, dict) or not isinstance(req, dict):
        return False, ["BESLUIT_OF_AANVRAAG_GEEN_OBJECT"]
    missing = sorted(RECORD_KEYS - set(rec))
    extra = sorted(set(rec) - RECORD_KEYS)
    if missing:
        p.append("VELD_ONTBREEKT " + ", ".join(missing))
    if extra:
        p.append("ONBEKENDE_VELDEN_IN_BESLUIT " + ", ".join(extra))
    if p:
        return False, p
    fresh = evaluate_request(ctx, {**req, "approval_status": "DRAFT", "human_decision": None, "validation_results": None})     # nooit het meegegeven resultaat vertrouwen
    if fresh["approval_status"] != "READY_FOR_HUMAN_REVIEW":
        p.append("AANVRAAG_IS_NIET_TECHNISCH_GESCHIKT_VOOR_BEOORDELING")
    if rec["request_id"] != fresh.get("approval_request_id") or rec["request_hash"] != fresh.get("request_hash") or request_hash(fresh) != fresh.get("request_hash"):
        p.append("BESLUIT_HOORT_NIET_BIJ_DEZE_AANVRAAG_OF_INHOUD_GEWIJZIGD")
    if rec["decision"] not in HUMAN_DECISIONS:
        p.append("ONBEKEND_BESLUIT")
    if rec["level"] != "A" or rec["covers_levels"] != ["A"]:
        p.append("BESLUIT_DEKT_MEER_DAN_NIVEAU_A_OF_ANDER_NIVEAU")
    if rec["decision_source"] not in OIP.HUMAN_SOURCES:
        p.append("HERKOMST_NIET_MENSELIJK")
    if not isinstance(rec["decided_by"], str) or not rec["decided_by"].strip() or NON_HUMAN.search(rec["decided_by"]):
        p.append("BESLISSER_NIET_MENSELIJK")
    if not isinstance(rec["statement"], str) or len(rec["statement"].strip()) < 10:
        p.append("VERKLARING_ONTBREEKT")
    if any(rec.get(k) not in (None, "") for k in LEVEL_B_C_KEYS):
        p.append("BESLUIT_BEVAT_NIVEAU_B_OF_C_INHOUD")
    vr = fresh.get("validation_results") or {}
    need = sorted(r["app_id"] for r in vr.get("related_app_decisions", []) if r.get("relevance") == "DIRECT")
    if not isinstance(rec["acknowledged_app_decisions"], list) or not set(need) <= set(rec["acknowledged_app_decisions"]):
        p.append("OPENSTAANDE_APP_OVERLAPVRAGEN_NIET_ERKEND " + str(need))
    need_rel = sorted(vr.get("open_related_relations", []))
    if not isinstance(rec["acknowledged_open_relations"], list) or not set(need_rel) <= set(rec["acknowledged_open_relations"]):
        p.append("OPENSTAANDE_RELATIES_NIET_ERKEND " + str(need_rel))
    reg = [d for d in (ctx.get("human_approvals") or []) if isinstance(d, dict) and d.get("decision_id") == rec["decision_id"]]
    if len(reg) != 1 or canonical(reg[0]) != canonical(rec):
        p.append("BESLUIT_STAAT_NIET_IN_HET_GEREGISTREERDE_BESLUITENREGISTER")
    return (not p), p


def transition(ctx, req, target, human_record=None):
    """Statusovergang als zuivere functie: retourneert een nieuwe aanvraag of een weigering; schrijft niets en maakt nooit een instance."""
    refuse = lambda why: {"ok": False, "refused": why, "request": req}   # noqa: E731
    try:
        cur = req.get("approval_status") if isinstance(req, dict) else None
        if cur not in STATUSES or target not in STATUSES:
            return refuse("ONBEKENDE_STATUS")
        if target not in TRANSITIONS[cur]:
            return refuse(f"OVERGANG_NIET_TOEGESTAAN {cur}->{target}")
        if target == "READY_FOR_HUMAN_REVIEW":
            # alleen via technische validatie, nooit op verzoek
            fresh = evaluate_request(ctx, {**req, "approval_status": "DRAFT", "human_decision": None})
            return {"ok": fresh["approval_status"] == "READY_FOR_HUMAN_REVIEW", "refused": None if fresh["approval_status"] == "READY_FOR_HUMAN_REVIEW" else "VALIDATIE_NIET_GESLAAGD",
                    "request": fresh}
        if target == "APPROVED_FOR_ACTIVATION":
            base = {**req, "approval_status": "DRAFT", "human_decision": None}
            fresh = evaluate_request(ctx, base)      # de technische controle moet op dit moment nog slagen
            if fresh["approval_status"] != "READY_FOR_HUMAN_REVIEW":
                return refuse("TECHNISCHE_VALIDATIE_SLAAGT_NIET_MEER")
            ok, why = verify_human_approval(ctx, fresh, human_record)
            if not ok or human_record["decision"] != "APPROVE_PHYSICAL_IDENTITY":
                return refuse(why or ["BESLUIT_IS_GEEN_GOEDKEURING"])
            out = copy.deepcopy(fresh)
            out["approval_status"] = "APPROVED_FOR_ACTIVATION"
            out["human_decision"] = copy.deepcopy(human_record)
            out["is_instance"] = False          # goedgekeurd is geen instance
            out["activation_performed"] = False
            return {"ok": True, "refused": None, "request": out}
        if target in ("REJECTED", "NEEDS_MORE_EVIDENCE") and cur in ("READY_FOR_HUMAN_REVIEW", "APPROVED_FOR_ACTIVATION"):
            if human_record is not None:
                ok, why = verify_human_approval(ctx, req, human_record)
                if not ok:
                    return refuse(why)
            out = copy.deepcopy(req)
            out["approval_status"] = target
            return {"ok": True, "refused": None, "request": out}
        out = copy.deepcopy(req)
        out["approval_status"] = target
        return {"ok": True, "refused": None, "request": out}
    except Exception as exc:   # noqa: BLE001
        return refuse(f"FOUT {type(exc).__name__}")


# ----------------------------------------------------------------------------------------------------------------------------------
def load_soc_groups():
    a = _load(OIP.ARCHIVE_JSON)
    return [{"id": s.get("group_id") or s.get("id"), "photos": s.get("photo_ids") or s.get("photos") or []} for s in a.get("same_object_candidates", [])]


def build_report():
    ctx = load_context()
    ctx["soc_groups"] = load_soc_groups()
    req = evaluate_request(ctx, build_request(ctx, "OIC-VR-027"))
    ver = ctx["verification"]
    return {
        "framework_version": FRAMEWORK_VERSION, "status": "FRAMEWORK_AND_DRAFT_REQUEST_ONLY_NO_APPROVAL_NO_ACTIVATION",
        "request_model": {"required_fields": REQUIRED_FIELDS, "id_pattern": "IAR-<candidate_group_id>", "is_instance": False, "reserved_instance_id": None,
                          "note": "Een approval request is geen fysieke instance en reserveert geen FI-id."},
        "status_machine": {"statuses": list(STATUSES), "meaning": STATUS_MEANING, "transitions": TRANSITIONS,
                           "rules": ["READY_FOR_HUMAN_REVIEW alleen via de technische validatie, nooit op verzoek.",
                                     "APPROVED_FOR_ACTIVATION alleen met een geregistreerd, verifieerbaar menselijk niveau-A-besluit dat de exacte request_hash noemt.",
                                     "Geen overgang leidt tot een instance; activatie bestaat in dit framework niet.",
                                     "REJECTED door validatie is geen menselijk besluit en is eindstatus voor die request_hash."]},
        "technical_conditions": [{"id": c, "condition": t} for c, t in [
            ("C1", "Het OIC-verband bestaat (OIC-register)"), ("C2", "Status SUPPORTED_CANDIDATE, live opnieuw bepaald"), ("C3", "Alle bronobservaties geldig"),
            ("C4", "Alle bronhashes komen overeen (review-bron, archiefregister, bewijsreferentie)"), ("C5", "Relatie is PHYSICAL_OBJECT met exact deze eindpunten"),
            ("C6", "Menselijk kandidaatbesluit SAME, menselijke herkomst, hash gevalideerd"), ("C7", "Onderscheidend bewijs: STRONG + anker, geen blokkade"),
            ("C8", "Geen genegeerd DIFFERENT/UNDECIDABLE; open gerelateerde relaties zichtbaar"),
            ("C9", "Geen conflict met instances, andere kandidaten of aanvragen"), ("C10", "Relatie met de 48 APP-besluiten expliciet onderzocht"),
            ("C11", "Bewijsverzoening VR-045/MAP-009 consistent met de aanvraag; VR-045 zonder menselijk besluit")]],
        "decision_levels": LEVELS, "allowed_effects": ALLOWED_EFFECTS, "forbidden_effects": FORBIDDEN_EFFECTS,
        "draft_request": req,
        "evidence_reconciliation": {"summary": req["evidence_reconciliation"], "stale_request_hashes": list(SUPERSEDED_HASHES),
                                    "outcome_explanation": ctx["reconciliation"]["outcome_explanation"], "features": ctx["reconciliation"]["features"],
                                    "comparison_table": ctx["reconciliation"]["comparison_table"], "report": "reports/frames/physical_instance_evidence_reconciliation_v1.md",
                                    "note": "AI-verklaring van het verschil; geen menselijk besluit en geen wijziging van VR-045 of de kwaliteitsreview."},
        "photo_evidence_summary": {"conclusion": ver.get("conclusion"), "additional_matches": req["additional_evidence"], "swap_risk": ver.get("swap_risk"),
                                   "feature_match_measurements": ver.get("feature_match_measurements"), "contradictions": ver.get("contradictions"),
                                   "counter_examples": [c for c in ver.get("crops", []) if "COUNTER" in c.get("role", "") or c.get("role") == "NEIGHBOUR"],
                                   "figure": ver.get("figure")},
        "fact_classes": {"AUTO_VALIDATED_FACT": "Door deze code opnieuw uit de brondata gecontroleerd (C1-C10).",
                         "MANUAL_VISUAL_ASSESSMENT": "Handmatige lezing van foto's door Claude (fotobewijs, MAP-009, tegenvoorbeelden); geen menselijk besluit.",
                         "HUMAN_DECISION_NOT_YET_TAKEN": "Instance-besluit niveau A; niveau B en C; APP-012; RV-REL-VR-045."},
        "effects": {"instances_created": 0, "instance_ids_reserved": 0, "instance_store_written": False, "bag_links_created": 0, "merges": 0, "building_totals": None,
                    "quantities": None, "costs": None, "human_decisions_created": 0, "human_decisions_changed": 0, "app_decisions_changed": 0, "pilot_decisions_changed": 0,
                    "source_observations_changed": 0, "photo2_changed": False, "approved_requests": 0},
        "later_activation_phase_proposal": [
            "Een apart register van instance-besluiten (append-only, eigen PR) met het besluit APPROVE_PHYSICAL_IDENTITY, de request_hash en erkenning van de APP-overlapvragen.",
            "Een afzonderlijk, door jou geautoriseerd activatieproces dat alleen een verifieerbaar APPROVED_FOR_ACTIVATION leest, een nieuw FI-id uit de bestaande nummering toekent, de hele instance-store en scope guard opnieuw valideert en dubbele koppeling uitsluit.",
            "Activatie raakt alleen niveau A. Pandkoppeling (B) en hoeveelheid/kosten (C) vragen elk een eigen, later besluit.",
            "Dry-run met diff-rapport vóór elke schrijfactie; terugdraaien via de bestaande append-only store.",
        ],
        "stop": "Stop vóór een menselijk instance-goedkeuringsbesluit, iedere definitieve instance-activatie en het mergen van PR #43.",
    }


def main():
    rep = build_report()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    import physical_instance_approval_report as R   # noqa: E402
    OUT_MD.write_text(R.render_md(rep), encoding="utf-8")
    PACK_HTML.write_text(R.render_pack(rep), encoding="utf-8")
    print("verdict", rep["draft_request"]["validation_results"]["technical_verdict"], "status", rep["draft_request"]["approval_status"])


if __name__ == "__main__":
    main()
