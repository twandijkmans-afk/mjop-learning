"""Human Instance Decision Register v1 (niveau A: fysieke objectidentiteit).

Een append-only register waarin een MENSELIJK niveau-A-besluit over een approval request (IAR-*) kan worden vastgelegd. Dit module:

  * bouwt GEEN tweede approval-framework: de aanvraag wordt met `physical_instance_approval.build_request/evaluate_request` live opnieuw opgebouwd en het
    besluit wordt met `physical_instance_approval.verify_human_approval` getoetst (statusmachine, C1-C11, gesloten besluitrecord);
  * maakt, wijzigt of reserveert nooit een instance (FI-*), pandkoppeling, hoeveelheid, afmeting of kosten;
  * genereert nooit zelf een besluit: een besluit komt uitsluitend als apart aangeleverde invoer binnen;
  * schrijft standaard niets (DRY_RUN). SINDS DE BEVEILIGINGS-PR IS HET CANONIEKE v1-REGISTER GESLOTEN: `register()`/CLI `register` kunnen er geen besluit meer in
    schrijven, ook niet met de bevestigingstoken. De token staat in de code en is dus GEEN bewijs van menselijke goedkeuring; hij blijft uitsluitend een
    ongelukkenbeveiliging voor registers op een ander (tijdelijk/test)pad. Er is bewust geen omgevingsvariabele, CLI-optie of configuratiebestand dat de sluiting opheft.

Vier stappen die nooit automatisch samenvallen:
  1. technisch geldige aanvraag (READY_FOR_HUMAN_REVIEW)  2. expliciet menselijk besluit (invoer)
  3. technisch geverifieerd besluit (deze module)         4. daadwerkelijk geactiveerde instance (bestaat NIET in deze module)
"""
import copy
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import physical_instance_approval as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REGISTER_PATH = ROOT / "data/instance_decisions/human_instance_decision_register_v1.jsonl"
SCHEMA_PATH = ROOT / "schemas/human_instance_decision.schema.json"
OUT_DIR = ROOT / "reports/frames/human_instance_decision_register_v1"
OUT_JSON = ROOT / "reports/frames/human_instance_decision_register_v1.json"
OUT_MD = ROOT / "reports/frames/human_instance_decision_register_v1.md"
PACK_HTML = OUT_DIR / "IAR-OIC-VR-027_decision_pack.html"
TEMPLATE_JSON = OUT_DIR / "IAR-OIC-VR-027_decision_input_TEMPLATE.json"
REGISTER_VERSION = "human_instance_decision_register_v1"
RECORD_VERSION = 1
GENESIS = "0" * 64
CONFIRM_TOKEN = "REGISTER_ONE_HUMAN_DECISION_AS_EXPLICITLY_REQUESTED_BY_USER"

DECISIONS = tuple(P.HUMAN_DECISIONS)          # APPROVE_PHYSICAL_IDENTITY | REJECT | NEEDS_MORE_EVIDENCE
MODES = ("DRY_RUN", "REGISTER")
STATUS_DRY_RUN, STATUS_FAILED, STATUS_REGISTERED = "DRY_RUN", "VALIDATION_FAILED", "REGISTERED"
INPUT_KEYS = ["approval_request_id", "request_hash", "candidate_group_id", "decision", "covers_levels", "decision_source", "decided_by", "decision_provenance",
              "decision_timestamp", "acknowledged_open_app_ids", "acknowledged_open_relations", "evidence_reviewed", "reviewer_notes", "record_version"]
REGISTRY_KEYS = ["decision_id", "sequence", "previous_record_hash", "record_hash", "register_version"]
STORED_KEYS = INPUT_KEYS + REGISTRY_KEYS
PROVENANCE_KEYS = ["channel", "entered_by_kind", "source_message_ref", "source_message_text", "identity_verification", "ai_authored_decision"]
CHANNELS = ("CLAUDE_CODE_CHAT", "CHATGPT_CONVERSATION", "HTML_FORM_EXPORT", "FILE_EDITED_BY_HUMAN")
ENTERED_BY = ("HUMAN_DIRECT", "AI_TRANSCRIPTION_OF_HUMAN_MESSAGE")
IDENTITY_VERIFICATION = "NONE_SELF_ASSERTED"      # eerlijk: er is geen cryptografische of anderszins onafhankelijke verificatie van de persoon
MIN_SOURCE_TEXT = 60
MAX_FUTURE = timedelta(minutes=5)
PAND_ID = re.compile(r"\b0\d{15}\b")
FORBIDDEN_EFFECTS = list(P.FORBIDDEN_EFFECTS) + ["create_fi_id", "activate_instance", "write_register_without_confirmation", "overwrite_or_delete_registered_decision",
                                                   "generate_decision_by_code", "treat_ai_recommendation_as_human_decision"]
LADDER = [
    ("1_TECHNICALLY_VALID_REQUEST", "De aanvraag slaagt voor C1-C11 (READY_FOR_HUMAN_REVIEW). Geen oordeel over de identiteit."),
    ("2_EXPLICIT_HUMAN_DECISION", "Een mens heeft apart en expliciet gekozen (invoerbestand/chatbericht). Dit is bewijs-op-gezag, geen verificatie."),
    ("3_TECHNICALLY_VERIFIED_DECISION", "Het besluit is door `verify_human_approval` en de registerregels gecontroleerd en append-only vastgelegd."),
    ("4_ACTIVATED_PHYSICAL_INSTANCE", "Bestaat niet in dit register of deze module; vereist een apart, later door de gebruiker geautoriseerd activatieproces."),
]


class RegisterCorrupt(Exception):
    pass


CANONICAL_CLOSED = ("V1_CANONIEK_REGISTER_GESLOTEN (registratie in data/instance_decisions/human_instance_decision_register_v1.jsonl is uitgeschakeld; de bevestigingstoken "
                    "is geen bewijs van menselijke goedkeuring; geen omgevingsvariabele, optie of configuratie heft dit op)")


def _canonical_register_path():
    """Het productieregister, vast afgeleid van de locatie van dit script (niet van een aanpasbare modulevariabele, omgevingsvariabele of optie)."""
    return Path(__file__).resolve().parents[1] / "data/instance_decisions/human_instance_decision_register_v1.jsonl"


def is_canonical_register(path):
    """True als `path` het canonieke register is of er (via symlink, hardlink, `..` of hoofdletterverschil) naar wijst. Twijfel of fout = True (fail-closed)."""
    try:
        canon = _canonical_register_path()
        p = Path(path)
        if p.resolve(strict=False) == canon.resolve(strict=False):
            return True
        return p.exists() and canon.exists() and os.path.samefile(p, canon)
    except Exception:   # noqa: BLE001 — fail-closed
        return True


def canonical(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha(o):
    return hashlib.sha256(canonical(o).encode("utf-8")).hexdigest()


def record_hash(rec):
    return _sha({k: v for k, v in rec.items() if k != "record_hash"})


def decision_id_for(sequence):
    return f"HID-{sequence:04d}"


# ----------------------------------------------------------------------------------------------------------------------------------
def load_context():
    ctx = P.load_context()
    ctx["soc_groups"] = P.load_soc_groups()
    return ctx


def load_register(path=REGISTER_PATH):
    """Leest en controleert het volledige register. Elke afwijking is RegisterCorrupt (fail-closed); er wordt nooit gerepareerd."""
    path = Path(path)
    if not path.is_file():
        raise RegisterCorrupt("REGISTER_ONTBREEKT")
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise RegisterCorrupt("REGISTER_GEDEELTELIJK_GESCHREVEN (laatste regel zonder regeleinde)")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RegisterCorrupt("REGISTER_GEEN_GELDIG_UTF8")
    records, prev, ids, hashes = [], GENESIS, set(), set()
    for n, line in enumerate(text.splitlines(), 1):
        try:
            rec = json.loads(line)
        except ValueError:
            raise RegisterCorrupt(f"REGEL_{n}_GEEN_JSON")
        if not isinstance(rec, dict) or set(rec) != set(STORED_KEYS):
            raise RegisterCorrupt(f"REGEL_{n}_SCHEMA_ONGELDIG")
        if line != canonical(rec):
            raise RegisterCorrupt(f"REGEL_{n}_NIET_CANONIEK")
        if rec["sequence"] != n or rec["decision_id"] != decision_id_for(n):
            raise RegisterCorrupt(f"REGEL_{n}_VOLGORDE_OF_ID_ONJUIST")
        if rec["previous_record_hash"] != prev or rec["record_hash"] != record_hash(rec):
            raise RegisterCorrupt(f"REGEL_{n}_KETEN_OF_HASH_ONJUIST")
        if rec["decision_id"] in ids or rec["request_hash"] in hashes:
            raise RegisterCorrupt(f"REGEL_{n}_DUBBEL")
        ids.add(rec["decision_id"])
        hashes.add(rec["request_hash"])
        prev = rec["record_hash"]
        records.append(rec)
    return records


def register_head(records):
    return records[-1]["record_hash"] if records else GENESIS


# ----------------------------------------------------------------------------------------------------------------------------------
def _is_str(v, minimum=0):
    return isinstance(v, str) and len(v.strip()) >= minimum


def _scan_strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _scan_strings(k)
            yield from _scan_strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _scan_strings(v)


def to_core_record(inp, decision_id):
    """Afbeelding op het bestaande gesloten besluitrecord van het approval-framework (RECORD_KEYS); de bron van waarheid blijft verify_human_approval."""
    return {"decision_id": decision_id, "request_id": inp["approval_request_id"], "request_hash": inp["request_hash"], "decision": inp["decision"], "level": "A",
            "covers_levels": list(inp["covers_levels"]), "decided_by": inp["decided_by"], "decision_source": inp["decision_source"],
            "statement": inp["decision_provenance"]["source_message_text"], "acknowledged_app_decisions": list(inp["acknowledged_open_app_ids"]),
            "acknowledged_open_relations": list(inp["acknowledged_open_relations"])}


def _parse_ts(s):
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})", s):
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else None


def validate_input(ctx, inp, existing, now=None, check_time=True):
    """Alle voorwaarden voor registratie. Retourneert (redenen, waarschuwingen, live_aanvraag). Geen schrijfacties; nooit een uitzondering."""
    why, warn, fresh = [], [], None
    try:
        return _validate(ctx, inp, existing, now, check_time, why, warn)
    except Exception as exc:   # noqa: BLE001 — fail-closed
        return why + [f"ONVERWACHTE_FOUT {type(exc).__name__}: {str(exc)[:120]}"], warn, fresh


def _validate(ctx, inp, existing, now, check_time, why, warn):
    fresh = None
    # 1. gesloten schema -------------------------------------------------------------------------------------------------------
    if not isinstance(inp, dict):
        return ["BESLUIT_GEEN_OBJECT"], warn, fresh
    missing, extra = sorted(set(INPUT_KEYS) - set(inp)), sorted(set(inp) - set(INPUT_KEYS))
    if missing:
        why.append("VELD_ONTBREEKT " + ", ".join(missing))
    if extra:
        why.append("ONBEKENDE_VELDEN_IN_BESLUIT " + ", ".join(extra))
    if missing or extra:
        return why, warn, fresh
    prov = inp["decision_provenance"]
    if not isinstance(prov, dict) or set(prov) != set(PROVENANCE_KEYS):
        return ["HERKOMST_SCHEMA_ONGELDIG (verwacht exact " + ", ".join(PROVENANCE_KEYS) + ")"], warn, fresh
    if any(P.FI_PATTERN.search(s) for s in _scan_strings(inp)):
        why.append("BESLUIT_VERWIJST_NAAR_OF_MAAKT_FI_ID")
    if any(PAND_ID.search(s) for s in _scan_strings(inp)):
        why.append("BESLUIT_BEVAT_PANDGEGEVENS")
    if inp["record_version"] != RECORD_VERSION or isinstance(inp["record_version"], bool):
        why.append("RECORD_VERSION_ONGELDIG")
    for k in ("approval_request_id", "request_hash", "candidate_group_id", "decision", "decision_source", "decided_by", "decision_timestamp"):
        if not _is_str(inp[k]):
            why.append(f"VELD_LEEG_OF_GEEN_TEKST {k}")
    if not isinstance(inp["reviewer_notes"], str):
        why.append("REVIEWER_NOTES_GEEN_TEKST")
    for k in ("acknowledged_open_app_ids", "acknowledged_open_relations", "evidence_reviewed", "covers_levels"):
        if not isinstance(inp[k], list) or any(not _is_str(x) for x in inp[k]) or len(set(inp[k])) != len(inp[k]):
            why.append(f"LIJST_ONGELDIG {k}")
    if why:
        return why, warn, fresh
    # 2. keuze, niveau, herkomst -----------------------------------------------------------------------------------------------
    if inp["decision"] not in DECISIONS:
        why.append("ONBEKEND_BESLUIT (toegestaan: " + ", ".join(DECISIONS) + ")")
    if inp["covers_levels"] != ["A"]:
        why.append("BESLUIT_DEKT_MEER_DAN_NIVEAU_A_OF_GEEN_NIVEAU")
    if inp["decision_source"] not in P.OIP.HUMAN_SOURCES:
        why.append("HERKOMST_NIET_MENSELIJK (decision_source)")
    if NON_HUMAN_NAME(inp["decided_by"]):
        why.append("BESLISSER_NIET_MENSELIJK")
    if prov["channel"] not in CHANNELS:
        why.append("KANAAL_ONBEKEND (toegestaan: " + ", ".join(CHANNELS) + ")")
    if prov["entered_by_kind"] not in ENTERED_BY:
        why.append("INVOERWIJZE_ONBEKEND (toegestaan: " + ", ".join(ENTERED_BY) + ")")
    if prov["identity_verification"] != IDENTITY_VERIFICATION:
        why.append(f"IDENTITEITSVERIFICATIE_MOET_EERLIJK_{IDENTITY_VERIFICATION}_ZIJN")
    if prov["ai_authored_decision"] is not False:
        why.append("AI_OPGESTELD_BESLUIT_TELT_NIET_ALS_MENSELIJK")
    if not _is_str(prov["source_message_ref"], 3):
        why.append("BRONBERICHT_VERWIJZING_ONTBREEKT")
    txt = prov["source_message_text"]
    if not _is_str(txt, MIN_SOURCE_TEXT):
        why.append("LETTERLIJKE_MENSELIJKE_VERKLARING_ONTBREEKT_OF_TE_KORT")
    else:
        for need, label in ((inp["approval_request_id"], "aanvraag-id"), (inp["request_hash"], "request_hash"), (inp["decision"], "gekozen besluit")):
            if need not in txt:
                why.append(f"VERKLARING_NOEMT_{label.upper().replace('-', '_').replace(' ', '_')}_NIET")
    ts = _parse_ts(inp["decision_timestamp"])
    if ts is None:
        why.append("TIJDSTIP_ONGELDIG (ISO 8601 met tijdzone)")
    elif check_time and ts > (now or datetime.now(timezone.utc)) + MAX_FUTURE:
        why.append("TIJDSTIP_LIGT_IN_DE_TOEKOMST")
    if why:
        return why, warn, fresh
    # 3. live opnieuw opgebouwde aanvraag + hash ----------------------------------------------------------------------------------
    cand = inp["candidate_group_id"]
    if inp["approval_request_id"] != "IAR-" + cand or cand not in ctx["oic_registry"]:
        return ["AANVRAAG_ONBEKEND_OF_ID_KOMT_NIET_OVEREEN_MET_KANDIDAAT"], warn, fresh
    try:
        built = P.build_request(ctx, cand)
    except (ValueError, KeyError) as exc:
        return [f"AANVRAAG_KAN_NIET_LIVE_WORDEN_OPGEBOUWD {type(exc).__name__}"], warn, fresh
    fresh = P.evaluate_request(ctx, built)
    if fresh["approval_status"] != "READY_FOR_HUMAN_REVIEW":
        why.append("LIVE_AANVRAAG_IS_NIET_TECHNISCH_GESCHIKT_VOOR_BEOORDELING " + fresh["approval_status"])
    if inp["request_hash"] in P.SUPERSEDED_HASHES:
        why.append("REQUEST_HASH_VEROUDERD (eerder gepubliceerde, vervangen hash)")
    elif inp["request_hash"] != fresh["request_hash"]:
        why.append("REQUEST_HASH_KOMT_NIET_OVEREEN_MET_LIVE_AANVRAAG (verouderd of gewijzigd)")
    if why:
        return why, warn, fresh
    # 4. bewijs, erkenning APP/relaties --------------------------------------------------------------------------------------------
    vr = fresh["validation_results"]
    need_ev = set(fresh["observation_ids"]) | set(fresh["photo_ids"]) | set(fresh["supporting_relation_ids"]) | {a["photo_id"] for a in fresh.get("additional_evidence", [])}
    if not need_ev <= set(inp["evidence_reviewed"]):
        why.append("BEWIJS_NIET_ALS_BEOORDEELD_VERKLAARD " + str(sorted(need_ev - set(inp["evidence_reviewed"]))))
    open_apps = {a for a, r in ctx["app_decisions"].items() if r["status"] == "OPEN"}
    bad_apps = sorted(set(inp["acknowledged_open_app_ids"]) - open_apps)
    if bad_apps:
        why.append("ERKENDE_APP_IS_ONBEKEND_OF_NIET_OPEN " + str(bad_apps))
    need_rel = set(vr["open_related_relations"])
    if set(inp["acknowledged_open_relations"]) - need_rel:
        why.append("ERKENDE_RELATIE_IS_NIET_OPEN_OF_NIET_GERELATEERD " + str(sorted(set(inp["acknowledged_open_relations"]) - need_rel)))
    # 5. bestaand framework: statusmachine, C1-C11, gesloten besluitrecord, APP/relatie-erkenning
    next_seq = len(existing) + 1
    core = to_core_record(inp, decision_id_for(next_seq))
    ok, reasons = P.verify_human_approval({**ctx, "human_approvals": [core]}, built, core)
    if not ok:
        why += ["FRAMEWORK: " + r for r in reasons]
    # 6. duplicaten, conflicten, verouderde eerdere besluiten --------------------------------------------------------------------
    same_hash = [r for r in existing if r["request_hash"] == inp["request_hash"]]
    if same_hash:
        prior = same_hash[0]
        identical = {k: prior[k] for k in INPUT_KEYS} == {k: inp[k] for k in INPUT_KEYS}
        why.append("DUPLICAAT_BESLUIT (identiek aan " + prior["decision_id"] + "; niets geregistreerd)" if identical
                   else "CONFLICTEREND_BESLUIT voor dezelfde request_hash (" + prior["decision_id"] + " " + prior["decision"] + "); nooit overschrijven")
    stale = [r["decision_id"] for r in existing if r["approval_request_id"] == inp["approval_request_id"] and r["request_hash"] != inp["request_hash"]]
    if stale:
        warn.append("Eerdere besluiten voor een andere (verouderde) request_hash blijven bestaan maar gelden niet voor deze aanvraag: " + ", ".join(stale))
    return why, warn, fresh


def NON_HUMAN_NAME(name):
    return bool(P.NON_HUMAN.search(name or "")) or not (name or "").strip()


# ----------------------------------------------------------------------------------------------------------------------------------
def build_stored_record(inp, existing):
    seq = len(existing) + 1
    rec = {k: copy.deepcopy(inp[k]) for k in INPUT_KEYS}
    rec.update({"decision_id": decision_id_for(seq), "sequence": seq, "previous_record_hash": register_head(existing), "register_version": REGISTER_VERSION})
    rec["record_hash"] = record_hash(rec)
    return rec


def _fsync_dir(path):
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_replace(path, data):
    """Schrijft naar een tijdelijk bestand in dezelfde map, fsync, en vervangt het register in één atomische stap."""
    if is_canonical_register(path):     # laatste verdedigingslinie: ook directe aanroep van deze helper kan het canonieke register niet raken
        raise PermissionError(CANONICAL_CLOSED)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    _fsync_dir(path.parent)


def register(inp, mode="DRY_RUN", confirm=None, path=REGISTER_PATH, ctx=None, now=None):
    """Registratieprocedure. Standaard DRY_RUN: valideert en rapporteert zonder te schrijven. Registratie (mode='REGISTER' én confirm=CONFIRM_TOKEN) werkt alleen
    op een niet-canoniek register (test/tijdelijk); op het canonieke v1-register is elke REGISTER-poging geblokkeerd, met of zonder token.
    Retourneert altijd een rapport met status DRY_RUN | VALIDATION_FAILED | REGISTERED; nooit een uitzondering."""
    path = Path(path)
    rep = {"mode": mode, "status": STATUS_FAILED, "reasons": [], "warnings": [], "decision_id": None, "register_head_before": None, "register_head_after": None,
           "changes": [], "instance_activated": False, "fi_ids_created": 0}
    if mode not in MODES:
        rep["reasons"].append("ONBEKENDE_MODUS")
        return rep
    if mode == "REGISTER" and is_canonical_register(path):
        rep["reasons"].append(CANONICAL_CLOSED)
        return rep
    if mode == "REGISTER" and confirm != CONFIRM_TOKEN:
        rep["reasons"].append("REGISTRATIE_VRAAGT_EXPLICIETE_BEVESTIGING (confirm-token ontbreekt of onjuist)")
        return rep
    lock = path.with_name(path.name + ".lock")
    held = False
    try:
        if mode == "REGISTER":
            try:
                os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                held = True
            except FileExistsError:
                rep["reasons"].append("REGISTER_VERGRENDELD (gelijktijdige of afgebroken registratie; fail-closed, geen automatische ontgrendeling)")
                return rep
            except OSError as exc:
                rep["reasons"].append(f"REGISTER_NIET_VERGRENDELBAAR {type(exc).__name__}")
                return rep
        try:
            old_bytes = path.read_bytes() if path.is_file() else b""
            existing = load_register(path)
        except RegisterCorrupt as exc:
            rep["reasons"].append(f"REGISTER_BESCHADIGD {exc}")
            return rep
        rep["register_head_before"] = register_head(existing)
        ctx = ctx or load_context()
        why, warn, fresh = validate_input(ctx, inp, existing, now=now)
        rep["warnings"] = warn
        if why:
            rep["reasons"] = why
            return rep
        rec = build_stored_record(inp, existing)
        rep["decision_id"], rep["record_preview"] = rec["decision_id"], rec
        if mode == "DRY_RUN":
            rep["status"], rep["register_head_after"] = STATUS_DRY_RUN, rep["register_head_before"]
            return rep
        new_bytes = old_bytes + (canonical(rec) + "\n").encode("utf-8")
        if path.read_bytes() != old_bytes:      # compare-and-swap: het register mocht onder het slot niet veranderen
            rep["reasons"].append("REGISTER_TUSSENTIJDS_GEWIJZIGD")
            return rep
        _atomic_replace(path, new_bytes)
        after = load_register(path)             # nacontrole: de keten moet nog steeds kloppen en het nieuwe record moet erin staan
        if after[:-1] != existing or after[-1] != rec or path.read_bytes()[:len(old_bytes)] != old_bytes:
            rep["reasons"].append("NACONTROLE_MISLUKT (register niet zoals verwacht; geen automatisch herstel)")
            return rep
        rep["status"], rep["register_head_after"], rep["changes"] = STATUS_REGISTERED, register_head(after), [f"append {rec['decision_id']} aan {path.name}"]
        return rep
    except Exception as exc:   # noqa: BLE001 — fail-closed
        rep["status"], rep["reasons"] = STATUS_FAILED, rep["reasons"] + [f"ONVERWACHTE_FOUT {type(exc).__name__}: {str(exc)[:120]}"]
        return rep
    finally:
        if held:
            try:
                lock.unlink()
            except OSError:
                pass


# ----------------------------------------------------------------------------------------------------------------------------------
def audit_register(ctx, path=REGISTER_PATH, now=None):
    """Controleert elk geregistreerd besluit opnieuw tegen de LIVE aanvraag. Een besluit voor een verouderde hash is STALE en geldt niet."""
    recs = load_register(path)
    out = []
    for i, r in enumerate(recs):
        inp = {k: r[k] for k in INPUT_KEYS}
        why, _, fresh = validate_input(ctx, inp, recs[:i], now=now, check_time=False)
        live = fresh["request_hash"] if fresh else None
        stale = any(w.startswith("REQUEST_HASH") for w in why)
        out.append({"decision_id": r["decision_id"], "decision": r["decision"], "state": "STALE_REQUEST_CHANGED" if stale else ("VERIFIED" if not why else "INVALID"),
                    "reasons": why, "live_request_hash": live, "counts_as_instance": False, "instance_activated": False})
    return out


def decision_state(ctx, candidate_group_id, path=REGISTER_PATH):
    req = P.evaluate_request(ctx, P.build_request(ctx, candidate_group_id))
    recs = load_register(path)
    mine = [a for a, r in zip(audit_register(ctx, path), recs) if r["approval_request_id"] == req["approval_request_id"]]
    verified = [a for a in mine if a["state"] == "VERIFIED"]
    return {"approval_request_id": req["approval_request_id"], "request_hash": req["request_hash"],
            "step_1_technically_valid_request": req["approval_status"] == "READY_FOR_HUMAN_REVIEW",
            "step_2_explicit_human_decision_registered": bool(mine), "step_3_technically_verified_decision": bool(verified),
            "step_4_instance_activated": False, "decisions": mine, "level_A": "NOT_DECIDED" if not verified else verified[0]["decision"],
            "level_B": "NOT_DECIDED", "level_C": "NOT_DECIDED"}


def blank_template(req):
    """Invulsjabloon: alle beslisvelden leeg; geen vooraf gekozen optie. Alleen verwijzingen naar de aanvraag zijn ingevuld."""
    return {"approval_request_id": req["approval_request_id"], "request_hash": req["request_hash"], "candidate_group_id": req["candidate_group_id"],
            "decision": "", "covers_levels": [], "decision_source": "", "decided_by": "",
            "decision_provenance": {"channel": "", "entered_by_kind": "", "source_message_ref": "", "source_message_text": "", "identity_verification": "",
                                    "ai_authored_decision": None},
            "decision_timestamp": "", "acknowledged_open_app_ids": [], "acknowledged_open_relations": [], "evidence_reviewed": [], "reviewer_notes": "",
            "record_version": RECORD_VERSION}


def json_schema():
    str_ne = {"type": "string", "minLength": 1}
    prov = {"type": "object", "additionalProperties": False, "required": PROVENANCE_KEYS,
            "properties": {"channel": {"enum": list(CHANNELS)}, "entered_by_kind": {"enum": list(ENTERED_BY)}, "source_message_ref": {"type": "string", "minLength": 3},
                           "source_message_text": {"type": "string", "minLength": MIN_SOURCE_TEXT,
                                                  "description": "Letterlijke verklaring van de mens; noemt aanvraag-id, request_hash en gekozen besluit."},
                           "identity_verification": {"const": IDENTITY_VERIFICATION, "description": "Er is geen cryptografische verificatie van de persoon."},
                           "ai_authored_decision": {"const": False}}}
    props = {"approval_request_id": {"type": "string", "pattern": r"^IAR-OIC-"}, "request_hash": {"type": "string", "pattern": r"^[0-9a-f]{32}$"},
             "candidate_group_id": {"type": "string", "pattern": r"^OIC-"}, "decision": {"enum": list(DECISIONS)}, "covers_levels": {"const": ["A"]},
             "decision_source": {"enum": sorted(P.OIP.HUMAN_SOURCES)}, "decided_by": str_ne, "decision_provenance": prov,
             "decision_timestamp": {"type": "string", "format": "date-time"},
             "acknowledged_open_app_ids": {"type": "array", "items": {"type": "string", "pattern": r"^APP-\d{3}$"}, "uniqueItems": True},
             "acknowledged_open_relations": {"type": "array", "items": {"type": "string", "pattern": r"^VR-\d{3}$"}, "uniqueItems": True},
             "evidence_reviewed": {"type": "array", "items": str_ne, "uniqueItems": True}, "reviewer_notes": {"type": "string"}, "record_version": {"const": RECORD_VERSION}}
    stored = dict(props)
    stored.update({"decision_id": {"type": "string", "pattern": r"^HID-\d{4}$"}, "sequence": {"type": "integer", "minimum": 1},
                   "previous_record_hash": {"type": "string", "pattern": r"^[0-9a-f]{64}$"}, "record_hash": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
                   "register_version": {"const": REGISTER_VERSION}})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "human_instance_decision.schema.json",
            "title": "Menselijk niveau-A-besluit over fysieke objectidentiteit (invoer en opgeslagen record)",
            "description": "Gesloten schema. Invoer = INPUT_KEYS; opgeslagen record = invoer + registerveld(en). Semantische controles (live aanvraag, hash, bewijs, "
                           "duplicaten) staan in scripts/human_instance_decision_register.py en zijn niet in JSON Schema uit te drukken.",
            "oneOf": [{"title": "input", "type": "object", "additionalProperties": False, "required": INPUT_KEYS, "properties": props},
                      {"title": "stored", "type": "object", "additionalProperties": False, "required": STORED_KEYS, "properties": stored}]}


def build_report(path=REGISTER_PATH):
    ctx = load_context()
    req = P.evaluate_request(ctx, P.build_request(ctx, "OIC-VR-027"))
    template = blank_template(req)
    recs = load_register(path)
    dry = register(template, mode="DRY_RUN", path=path, ctx=ctx)
    apps = ctx["app_decisions"]
    return {
        "register_version": REGISTER_VERSION, "status": "REGISTER_FRAMEWORK_ONLY_EMPTY_REGISTER_NO_DECISION_NO_ACTIVATION",
        "register_file": str(Path(path).relative_to(ROOT)) if Path(path).is_relative_to(ROOT) else str(path), "schema_file": "schemas/human_instance_decision.schema.json",
        "records_registered": len(recs), "register_head": register_head(recs), "default_mode": "DRY_RUN", "canonical_register_closed": True,
        "ladder": [{"step": s, "meaning": m} for s, m in LADDER], "decisions_supported": list(DECISIONS), "input_keys": INPUT_KEYS, "stored_keys": STORED_KEYS,
        "provenance_keys": PROVENANCE_KEYS, "channels": list(CHANNELS), "entered_by_kinds": list(ENTERED_BY), "identity_verification_literal": IDENTITY_VERIFICATION,
        "forbidden_effects": FORBIDDEN_EFFECTS,
        "request": {"approval_request_id": req["approval_request_id"], "candidate_group_id": req["candidate_group_id"], "observation_ids": req["observation_ids"],
                    "approval_status": req["approval_status"], "request_hash": req["request_hash"], "superseded_request_hashes": list(P.SUPERSEDED_HASHES),
                    "technical_verdict": req["validation_results"]["technical_verdict"], "open_related_relations": req["validation_results"]["open_related_relations"],
                    "related_app_decisions": req["validation_results"]["related_app_decisions"], "required_human_decisions": req["required_human_decisions"]},
        "decision_state": decision_state(ctx, "OIC-VR-027", path),
        "template_dry_run": {"status": dry["status"], "reasons": dry["reasons"]},
        "app_decisions": {"total": len(apps), "open": sum(1 for a in apps.values() if a["status"] == "OPEN")},
        "effects": {"decisions_registered": len(recs), "instances_created": 0, "fi_ids_created": 0, "instance_store_written": False, "bag_links_created": 0,
                    "quantities": None, "costs": None, "app_decisions_changed": 0, "pilot_decisions_changed": 0, "source_observations_changed": 0, "photo2_changed": False},
        "later_registration_action": [
            "De gebruiker levert zelf (of bevestigt in een apart bericht) één besluit over IAR-OIC-VR-027 met de actuele request_hash.",
            "Een thread zet dat letterlijk in een invoerbestand (entered_by_kind AI_TRANSCRIPTION_OF_HUMAN_MESSAGE, bronbericht-ID en letterlijke tekst) of de gebruiker vult het zelf in.",
            "Eerst `python scripts/human_instance_decision_register.py check --decision <bestand>` (DRY_RUN) en het resultaat tonen.",
            "Registratie in het canonieke v1-register is GESLOTEN (fail-closed); een nieuw, apart door de gebruiker goedgekeurd registratiepad met echte authenticatie is vereist.",
            "Activatie van een instance blijft een nog later, apart door de gebruiker geautoriseerd proces.",
        ],
        "template": template,
    }


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("generate", help="schrijft schema, rapporten, beslispakket en leeg invulsjabloon (geen register-schrijfactie)")
    c = sub.add_parser("check", help="DRY_RUN van een apart aangeleverd besluit; schrijft niets")
    c.add_argument("--decision", required=True)
    r = sub.add_parser("register", help="GESLOTEN: stopt altijd fail-closed op het canonieke v1-register (--confirm is geen bewijs van goedkeuring)")
    r.add_argument("--decision", required=True)
    r.add_argument("--confirm", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "register":     # sluit voordat het invoerbestand wordt gelezen; het CLI heeft geen padoptie, dus altijd het canonieke register
        res = register({}, mode="REGISTER", confirm=a.confirm)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 1
    if a.cmd == "check":
        inp = json.loads(Path(a.decision).read_text(encoding="utf-8"))
        res = register(inp, mode="DRY_RUN")
        res.pop("record_preview", None) if res["status"] == STATUS_FAILED else None
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["status"] in (STATUS_DRY_RUN, STATUS_REGISTERED) else 1
    rep = build_report()
    import human_instance_decision_register_report as R   # noqa: E402
    _write(SCHEMA_PATH, json.dumps(json_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    _write(OUT_JSON, json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    _write(OUT_MD, R.render_md(rep))
    _write(TEMPLATE_JSON, json.dumps(rep["template"], indent=2, ensure_ascii=False) + "\n")
    _write(PACK_HTML, R.render_pack(rep))
    print("records", rep["records_registered"], "request", rep["request"]["request_hash"], "template_dry_run", rep["template_dry_run"]["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
