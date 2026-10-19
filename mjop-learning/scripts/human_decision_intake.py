"""Human Decision Intake & Provenance Hardening v1 (uitsluitend DRY_RUN).

Ontvangt een toekomstig menselijk niveau-A-besluit, controleert tekstintegriteit, herkomst, autorisatie en inhoud en retourneert UITSLUITEND een rapport.
Er is bewust GEEN registratieactie: deze module schrijft nooit naar het besluitenregister (ook niet als alles slaagt), maakt geen FI-id, activeert geen instance.

Zeven begrippen die nooit automatisch samenvallen (elk eigen veld in `ladder`):
  1 claim_text            een tekst waarin iemand beweert toestemming te geven
  2 author_id_asserted    een opgegeven auteur-ID (zelf opgegeven)
  3 author_authenticated  een door een systeem geauthenticeerde auteur-ID (alleen via een vertrouwde IntakeSourceProvider)
  4 provenance_verified   controleerbaar herkomstbewijs (SOURCE_VERIFIED): bron + tekst + auteur + tijd + menselijke aanwezigheid kloppen onafhankelijk
  5 valid_level_a_decision  inhoudelijk geldig niveau-A-besluit voor de ACTUELE aanvraag (hergebruikt de v1-registervalidatie)
  6 registered            daadwerkelijk geregistreerd (hier altijd false)
  7 instance_activated    geactiveerde fysieke instance (bestaat niet; altijd false)

Authenticatie (wie leverde het aan?), autorisatie (mag die persoon beslissen?), inhoudsvalidatie (is het besluit geldig?) en registratie (mag het blijvend worden
opgeslagen?) zijn gescheiden. In deze repository bestaat geen geauthenticeerd intakekanaal en geen vertrouwde aanwijzing van reviewers: de standaardconfiguratie
(NullIntakeSourceProvider, NullTrustAnchor, lege config) laat daarom nooit SOURCE_VERIFIED of AUTHORIZED toe.
"""
import copy
import hashlib
import json
import re
import sys
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import human_instance_decision_register as R  # noqa: E402  (alleen-lezen API's; zie tests/test_human_decision_intake.py)

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE_SCHEMA = ROOT / "schemas/human_decision_intake_envelope.schema.json"
TRUSTED_PROVIDERS_PATH = ROOT / "config/human_decision_intake_trusted_providers_v1.json"
AUTHORIZATION_PATH = ROOT / "config/human_decision_reviewer_authorization_v1.json"
OUT_JSON = ROOT / "reports/frames/human_decision_intake_provenance_v1.json"
OUT_MD = ROOT / "reports/frames/human_decision_intake_provenance_v1.md"

INTAKE_VERSION = "human_decision_intake_v1"
ENVELOPE_VERSION = "human_decision_intake_envelope_v1"
TRUSTED_PROVIDERS_VERSION = "human_decision_intake_trusted_providers_v1"
AUTHORIZATION_VERSION = "human_decision_reviewer_authorization_v1"
REPORT_VERSION = "human_decision_intake_report_v1"
MODE = "DRY_RUN"

# --- statuswaarden --------------------------------------------------------------------------------------------------------------
PROV_SELF_ASSERTED, PROV_SOURCE_VERIFIED, PROV_UNVERIFIABLE, PROV_INVALID = "SELF_ASSERTED", "SOURCE_VERIFIED", "UNVERIFIABLE", "INVALID"
PROVENANCE_STATUSES = (PROV_SELF_ASSERTED, PROV_SOURCE_VERIFIED, PROV_UNVERIFIABLE, PROV_INVALID)
AUTH_NOT, AUTH_UNTRUSTED, AUTH_ACCOUNT, AUTH_HUMAN = "NOT_AUTHENTICATED", "SOURCE_UNTRUSTED", "AUTHENTICATED_ACCOUNT_ONLY", "AUTHENTICATED_HUMAN_PRESENCE"
AUTHENTICATION_STATUSES = (AUTH_NOT, AUTH_UNTRUSTED, AUTH_ACCOUNT, AUTH_HUMAN)
FINAL_STATUSES = ("VALIDATED_DRY_RUN", "UNVERIFIED_SOURCE", "UNAUTHORIZED_REVIEWER", "STALE_REQUEST", "INVALID_DECISION", "BLOCKED")
# Precedentie bij meerdere problemen: de ernstigste wint; alle componenten blijven afzonderlijk in het rapport staan.
PRECEDENCE = ("BLOCKED", "STALE_REQUEST", "INVALID_DECISION", "UNVERIFIED_SOURCE", "UNAUTHORIZED_REVIEWER", "VALIDATED_DRY_RUN")
ACTOR_TYPES = ("HUMAN", "BOT", "AUTOMATION", "UNKNOWN")
HUMAN_PRESENCE_METHODS = ("NONE", "WEBAUTHN_USER_VERIFIED", "HARDWARE_KEY_SIGNATURE", "INTERACTIVE_MFA_SESSION_SEPARATE_FROM_AUTOMATION")
TEXT_STATUSES = ("MATCHES_SOURCE_TEXT", "MATCHES_CLAIMED_HASH_SELF_ONLY", "MISMATCH", "INVALID_TEXT")
# Alleen methoden waarvan een provider een CONTROLEERBAAR bewijs per bericht kan leveren tellen als menselijke aanwezigheid. "Een interactieve MFA-sessie los van
# automatisering" is een bewering over een omgeving, geen bewijs per bericht: zo'n account blijft AUTHENTICATED_ACCOUNT_ONLY.
PROVABLE_PRESENCE_METHODS = ("WEBAUTHN_USER_VERIFIED", "HARDWARE_KEY_SIGNATURE")
# Verificatieniveaus van een record in het gecombineerde registerbeeld. REAL_VERIFIED kan deze module nooit toekennen: een bestand kan zijn eigen herkomst niet bewijzen.
VERIFICATION_STATES = ("LEGACY_SELF_ASSERTED", "SCHEMA_VALID_UNPROVEN", "SIMULATED_VERIFICATION", "REAL_VERIFIED")
STATEMENT_HEADER = "MJOP-BESLUIT-V1"

SKEW = timedelta(minutes=5)
TIMESTAMP_FLOOR = datetime(2026, 10, 1, tzinfo=timezone.utc)          # vóór het approval-framework bestond er geen niveau-A-besluit
DECISION_TOKENS = tuple(R.DECISIONS)
MAX_TEXT = 20000
# Alleen de validator mag deze velden afleiden; staan ze in het aangeleverde bestand, dan is dat een poging om vertrouwde metadata mee te leveren.
TRUSTED_ONLY_KEYS = {"author_authentication_status", "authenticated_author_id", "authorized_reviewer_id", "authorization_status", "provenance_verification_status",
                     "received_timestamp", "human_presence_evidence", "attestation", "source_attestation", "trusted_author", "registration_eligible",
                     "registration_eligibility", "verified", "source_verified", "identity_verification", "actor_type", "trust_anchor", "designation", "designations",
                     "allowlist", "authorized_reviewers"}
AI_MARKERS = re.compile(r"generated by claude|claude\.ai/code|co-authored-by:\s*claude|🤖|\bas an ai\b|\bchatgpt\b|\bgpt-\d|\bassistant:|\bai-generated\b|gegenereerd door (een )?(ai|claude)", re.I)
LEVEL_BC_TEXT = re.compile(r"\b(niveau|level)\s*[bc]\b", re.I)
FORBIDDEN_EFFECTS = list(R.FORBIDDEN_EFFECTS) + ["register_decision_via_intake", "write_register_v1", "write_register_v2", "migrate_v1_record_to_v2",
                                                  "treat_self_asserted_as_verified", "treat_text_hash_as_authentication", "trust_embedded_attestation",
                                                  "trust_self_declared_reviewer_list", "persist_replay_state"]


# --- datamodel voor de bron (adapterinterface) ------------------------------------------------------------------------------------
@dataclass
class SourceAttestation:
    """Wat een vertrouwde bron over EEN bericht verklaart. Komt uitsluitend van een IntakeSourceProvider, nooit uit het besluitbestand."""
    provider_id: str
    authenticated_author_id: str
    author_authentication_method: str
    actor_type: str
    human_presence_evidence: str
    source_message_id: str
    message_text: str
    message_sha256: str
    source_timestamp: str
    retrieved_at: str = ""

    def as_dict(self):
        return {k: getattr(self, k) for k in ("provider_id", "authenticated_author_id", "author_authentication_method", "actor_type", "human_presence_evidence",
                                              "source_message_id", "message_sha256", "source_timestamp", "retrieved_at")}


class IntakeSourceProvider(ABC):
    """Adapter naar een systeem dat een menselijk bericht met geauthenticeerde identiteit kan aanleveren (zie rapport §7 voor de eisen).
    `fetch` vraagt het bronbericht OP BASIS VAN EEN BERICHT-ID bij de bron zelf op; de validator vertrouwt nooit iets uit het besluitbestand."""
    provider_id = "abstract"

    @abstractmethod
    def fetch(self, source_message_id):
        """Retourneert een SourceAttestation of None als de bron het bericht niet kent."""

    def verify_human_presence(self, attestation, message_sha256):
        """Controleert BIJ DE BRON (bv. WebAuthn-assertie met user verification, handtekening van een hardwaresleutel) dat een mens dit exacte bericht (message_sha256)
        heeft bevestigd. Een string `human_presence_evidence` in de attestatie is een bewering en telt niet. Standaard: False (fail-closed)."""
        return False


class NullIntakeSourceProvider(IntakeSourceProvider):
    """Standaardprovider: er is in deze repository geen geauthenticeerd intakekanaal, dus nooit een attestatie."""
    provider_id = "none"

    def fetch(self, source_message_id):
        return None


@dataclass
class AnchorResult:
    verified: bool
    authority_ids: tuple = ()
    reason: str = ""


class TrustAnchor(ABC):
    """Bewijst dat een configuratiebestand (vertrouwde providers, reviewer-aanwijzing) is vastgepind door een gezag BUITEN bereik van de code of een AI,
    bv. een ondertekende beheerdersaanwijzing of een branchbeveiliging met verplichte review door een aangewezen beheerder."""

    @abstractmethod
    def verify_pinned(self, artifact_name, artifact_sha256):
        """Retourneert AnchorResult."""


class NullTrustAnchor(TrustAnchor):
    def verify_pinned(self, artifact_name, artifact_sha256):
        return AnchorResult(False, (), "GEEN_TRUST_ANCHOR_GECONFIGUREERD")


class InMemoryReplayLedger:
    """Replay-/duplicaatdetectie binnen DIT proces en dit object. Niet persistent, niet gedeeld tussen processen of computers: zie `replay_protection` in het rapport."""

    def __init__(self):
        self._by_message = {}
        self._fingerprints = set()

    def check(self, message_key, fingerprint, decision):
        if message_key is None:
            return []
        out = []
        if fingerprint in self._fingerprints:
            out.append("REPLAY_DETECTED (identiek intake-event eerder gezien in dit proces)")
        elif message_key in self._by_message:
            prior = self._by_message[message_key]
            out.append("CONFLICTING_DECISIONS_SAME_SOURCE_EVENT (zelfde bronbericht, ander besluit)" if prior != decision
                       else "DUPLICATE_SOURCE_MESSAGE_ID (zelfde bronbericht, andere inhoud)")
        return out

    def record(self, message_key, fingerprint, decision):
        if message_key is not None:
            self._fingerprints.add(fingerprint)
            self._by_message.setdefault(message_key, decision)


# --- hulpfuncties --------------------------------------------------------------------------------------------------------------------
def canonical_sha256(o):
    return hashlib.sha256(R.canonical(o).encode("utf-8")).hexdigest()


def intake_id_for(envelope):
    return "INT-" + canonical_sha256({k: v for k, v in envelope.items() if k != "intake_id"})[:16]


def text_bytes(text):
    """Canonieke tekstrepresentatie: de exacte UTF-8-bytes van de aangeleverde tekens. GEEN normalisatie van regeleinden, witruimte, hoofdletters of
    Unicode (NFC/NFD): elke betekenisvolle of onzichtbare wijziging verandert de hash. Niet-codeerbare tekst (losse surrogaten) is ongeldig."""
    return text.encode("utf-8")      # kan UnicodeEncodeError geven; de aanroeper vangt dit op


def text_sha256(text):
    return hashlib.sha256(text_bytes(text)).hexdigest()


def suspicious_characters(text):
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat == "Cf" or ch == "\x00" or (cat == "Cc" and ch not in "\n\r\t"):
            out.append(f"U+{ord(ch):04X}")
    return sorted(set(out))


def _parse_ts(s):
    """Strikte ISO 8601 met tijdzone. Retourneert (datetime_utc | None, probleem | None)."""
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})?", s):
        return None, "TIMESTAMP_UNPARSABLE"
    if not re.search(r"(Z|[+-]\d{2}:\d{2})$", s):
        return None, "TIMESTAMP_NO_TIMEZONE"
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None, "TIMESTAMP_UNPARSABLE"
    return t.astimezone(timezone.utc), None


class DuplicateKeyError(ValueError):
    """Een JSON-object met twee keer dezelfde sleutel: json.loads zou stil de laatste waarde nemen (twee lezers kunnen dan iets anders zien)."""


def _no_duplicate_keys(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"DUBBELE_JSON_SLEUTEL {k!r}")
        out[k] = v
    return out


def _reject_constant(name):
    raise ValueError(f"NIET_TOEGESTANE_JSON_CONSTANTE {name}")


def strict_json_loads(text):
    """json.loads zonder stille keuzes: dubbele sleutels (op elk niveau) en NaN/Infinity worden geweigerd."""
    return json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)


def _read_json(path):
    try:
        return strict_json_loads(Path(path).read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}"


# Identiteiten (provider, auteur, bericht, aanwijzer) zijn eenduidige ASCII-tokens ZONDER dubbele punt: `provider:subject` is anders dubbelzinnig
# ("a:b"+"c" en "a"+"b:c" geven dezelfde tekenreeks) en Unicode-/witruimtevarianten kunnen op een andere identiteit lijken.
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@-]{0,127}")


def is_clean_id(v):
    return isinstance(v, str) and ID_RE.fullmatch(v) is not None


def reviewer_key(provider_id, subject_id):
    """Enige toegestane samenstelling van een reviewer-identiteit; alleen voor schone ID's (geen dubbele punt)."""
    if not (is_clean_id(provider_id) and is_clean_id(subject_id)):
        raise ValueError("ID_NIET_EENDUIDIG")
    return provider_id + ":" + subject_id


def _split_reviewer_key(v):
    if not isinstance(v, str) or v.count(":") != 1:
        return None
    a, b = v.split(":")
    return (a, b) if is_clean_id(a) and is_clean_id(b) else None


def load_trusted_providers(path=TRUSTED_PROVIDERS_PATH):
    return _read_json(path)


def load_authorization(path=AUTHORIZATION_PATH):
    return _read_json(path)


# --- 1. tekstintegriteit -------------------------------------------------------------------------------------------------------------
def check_text_integrity(env, attestation=None):
    res = {"status": "INVALID_TEXT", "computed_sha256": None, "claimed_sha256": env.get("decision_text_sha256"), "encoding": "UTF-8", "normalization": "NONE",
           "matches_claimed_hash": False, "matches_source_text": None, "proves_author": False, "statement_binding": "NOT_EVALUATED", "problems": []}
    text = env.get("decision_text")
    if not isinstance(text, str) or not text:
        res["problems"].append("TEKST_ONTBREEKT")
        return res
    if len(text) > MAX_TEXT:
        res["problems"].append("TEKST_TE_LANG")
        return res
    try:
        res["computed_sha256"] = text_sha256(text)
    except UnicodeEncodeError:
        res["problems"].append("TEKST_NIET_CODEERBAAR_ALS_UTF8")
        return res
    sus = suspicious_characters(text)
    if sus:
        res["problems"].append("ONZICHTBARE_OF_STUURTEKENS_IN_TEKST " + ", ".join(sus))
    stmt = canonical_statement(env)
    res["statement_binding"] = "EXACT_MATCH" if stmt is not None and text == stmt else "MISMATCH"
    if res["statement_binding"] != "EXACT_MATCH":
        res["problems"].append("TEKST_IS_NIET_EXACT_DE_GEBONDEN_BESLUITVERKLARING (vrije of afwijkende tekst wordt niet geaccepteerd: fail-closed)")
    res["matches_claimed_hash"] = res["computed_sha256"] == env.get("decision_text_sha256")
    if not res["matches_claimed_hash"]:
        res["status"] = "MISMATCH"
        res["problems"].append("TEKST_KOMT_NIET_OVEREEN_MET_OPGEGEVEN_SHA256 (tekst gewijzigd of hash onjuist)")
        return res
    res["status"] = "MATCHES_CLAIMED_HASH_SELF_ONLY"
    if attestation is not None:
        try:
            src_hash = text_sha256(attestation.message_text)
        except (UnicodeEncodeError, AttributeError):
            res["problems"].append("BRONTEKST_NIET_CODEERBAAR")
            res["status"] = "MISMATCH"
            return res
        res["matches_source_text"] = src_hash == res["computed_sha256"] and attestation.message_sha256 == src_hash
        if res["matches_source_text"]:
            res["status"] = "MATCHES_SOURCE_TEXT"
        else:
            res["status"] = "MISMATCH"
            res["problems"].append("TEKST_KOMT_NIET_OVEREEN_MET_HET_BRONBERICHT")
    if sus:
        res["status"] = "INVALID_TEXT" if res["status"] == "MATCHES_CLAIMED_HASH_SELF_ONLY" else res["status"]
    return res


def _decision_tokens_in(text):
    return [t for t in DECISION_TOKENS if t in text]


def canonical_statement(env):
    """De ENIGE tekst die een besluitbericht mag zijn: een vaste, volledig afgeleide verklaring van de exacte besluitinhoud (aanvraag, hash, kandidaat, keuze, niveau,
    erkende APP's/relaties, beoordeeld bewijs). Vrije tekst is niet toegestaan, want vrije tekst kan de inhoud ontkennen of afzwakken ('niet', 'behalve', 'onder voorbehoud').
    Dit bindt tekst aan inhoud; het bewijst NIET dat een mens de tekst las of schreef (dat doet alleen de bron) en is de voorloper van het toekomstige,
    ondertekende DecisionStatement. Retourneert None als de inhoud geen eenduidige verklaring toelaat."""
    try:
        lists = {k: env[k] for k in ("covers_levels", "acknowledged_open_app_ids", "acknowledged_open_relations", "evidence_reviewed")}
        scal = {k: env[k] for k in ("approval_request_id", "request_hash", "candidate_group_id", "decision")}
        if any(not isinstance(v, str) or not v or any(ord(c) < 32 or c in "=;" for c in v) for v in scal.values()):
            return None
        if any(not isinstance(v, list) or any(not isinstance(x, str) or not x or any(ord(c) < 32 or c in ",=;" for c in x) for x in v) or len(set(v)) != len(v)
               for v in lists.values()):
            return None
    except (KeyError, TypeError):
        return None
    lines = [STATEMENT_HEADER] + [f"{k}={v}" for k, v in scal.items()] + [f"{k}={','.join(sorted(v))}" for k, v in lists.items()]
    return "\n".join(lines) + "\n"


# --- 2. herkomst ---------------------------------------------------------------------------------------------------------------------
def _attestation_shape_problems(att):
    need = {"provider_id": str, "authenticated_author_id": str, "author_authentication_method": str, "actor_type": str, "human_presence_evidence": str,
            "source_message_id": str, "message_text": str, "message_sha256": str, "source_timestamp": str}
    if not isinstance(att, SourceAttestation):
        return ["ATTESTATIE_GEEN_SOURCEATTESTATION"]
    p = []
    for k, t in need.items():
        v = getattr(att, k, None)
        if not isinstance(v, t) or not v.strip():
            p.append(f"ATTESTATIE_VELD_ONTBREEKT_OF_ONGELDIG {k}")
    for k in ("provider_id", "authenticated_author_id", "source_message_id"):
        if isinstance(getattr(att, k, None), str) and getattr(att, k).strip() and not is_clean_id(getattr(att, k)):
            p.append(f"ATTESTATIE_ID_DUBBELZINNIG_OF_ONGELDIG {k} (alleen [A-Za-z0-9._@-], geen dubbele punt, geen spaties of Unicode)")
    if att.actor_type not in ACTOR_TYPES:
        p.append("ATTESTATIE_ACTOR_TYPE_ONBEKEND")
    if att.human_presence_evidence not in HUMAN_PRESENCE_METHODS:
        p.append("ATTESTATIE_MENSELIJKE_AANWEZIGHEID_ONBEKEND")
    return p


def _registry_problems(doc):
    if not isinstance(doc, dict) or doc.get("registry_version") != TRUSTED_PROVIDERS_VERSION or set(doc) != {"registry_version", "note", "providers"}:
        return ["TRUSTED_PROVIDERS_REGISTRY_ONGELDIG"]
    if not isinstance(doc["providers"], list):
        return ["TRUSTED_PROVIDERS_REGISTRY_ONGELDIG"]
    for p in doc["providers"]:
        if not isinstance(p, dict) or set(p) != {"provider_id", "provider_kind", "accepted_human_presence_methods", "synthetic"} or not is_clean_id(p.get("provider_id")) \
                or not isinstance(p["accepted_human_presence_methods"], list) or not isinstance(p["synthetic"], bool):
            return ["TRUSTED_PROVIDERS_REGISTRY_ONGELDIG (providerrecord of dubbelzinnig provider_id)"]
    folded = [p["provider_id"].casefold() for p in doc["providers"]]
    if len(set(folded)) != len(folded):
        return ["TRUSTED_PROVIDERS_REGISTRY_ONGELDIG (provider_id dubbel, ook niet op hoofdlettergebruik na)"]
    return []


def evaluate_provenance(env, attestation_fetch_error, attestation, trusted_providers, anchor, now, text_res, provider=None):
    provider = provider or NullIntakeSourceProvider()
    claims = env["claims"]
    out = {"status": PROV_UNVERIFIABLE, "authentication_status": AUTH_NOT, "claimed": {k: claims.get(k) for k in ("author_id", "author_identity_source", "source_message_id", "source_timestamp")},
           "attested": None, "provider_trusted": False, "synthetic_source": False, "problems": [], "timestamp_format_problems": [], "invalid": [], "unverifiable": []}
    inv, unv = out["invalid"], out["unverifiable"]
    text = env.get("decision_text") if isinstance(env.get("decision_text"), str) else ""
    # tegenstrijdigheden die los van een bron al bewijs van vervalsing of AI-herkomst zijn
    if AI_MARKERS.search(text) or AI_MARKERS.search(env.get("reviewer_notes") or ""):
        inv.append("AI_HERKOMST_KENMERK_IN_BERICHT (een bericht dat menselijke toestemming claimt maar AI-kenmerken draagt)")
    if claims.get("author_id") and R.NON_HUMAN_NAME(claims["author_id"]):
        inv.append("OPGEGEVEN_AUTEUR_IS_GEEN_MENS")
    if text_res["status"] == "MISMATCH":
        inv.append("TEKST_INTEGRITEIT_GESCHONDEN")
    # tijdstempel van de bewering
    claimed_ts, tprob = (None, None)
    if claims.get("source_timestamp") is not None:
        claimed_ts, tprob = _parse_ts(claims["source_timestamp"])
        if tprob:
            out["timestamp_format_problems"].append(tprob)
        else:
            if claimed_ts > now + SKEW:
                inv.append("TIMESTAMP_IN_FUTURE")
            if claimed_ts < TIMESTAMP_FLOOR:
                inv.append("TIMESTAMP_IMPLAUSIBLY_OLD")
    # bron opvragen
    if attestation_fetch_error:
        unv.append("BRON_NIET_OPVRAAGBAAR " + attestation_fetch_error)
    if attestation is None:
        out["status"] = PROV_INVALID if inv else (PROV_SELF_ASSERTED if claims.get("author_id") else PROV_UNVERIFIABLE)
        if not attestation_fetch_error:
            unv.append("GEEN_GEAUTHENTICEERDE_BRON (geen attestatie van een vertrouwde provider)")
        out["problems"] = inv + unv
        return out
    shape = _attestation_shape_problems(attestation)
    if shape:
        inv.extend(shape)
        out["status"], out["problems"] = PROV_INVALID, inv + unv
        return out
    out["attested"] = attestation.as_dict()
    ptr = env["source_pointer"]
    if attestation.provider_id != ptr.get("provider_id"):
        inv.append("ATTESTATIE_PROVIDER_KOMT_NIET_OVEREEN_MET_VERWIJZING")
    if attestation.source_message_id != ptr.get("source_message_id"):
        inv.append("ATTESTATIE_BERICHT_ID_KOMT_NIET_OVEREEN_MET_VERWIJZING")
    if claims.get("source_message_id") not in (None, attestation.source_message_id):
        inv.append("OPGEGEVEN_BERICHT_ID_WIJKT_AF_VAN_BRON")
    if claims.get("author_id") not in (None, attestation.authenticated_author_id):
        inv.append("OPGEGEVEN_AUTEUR_WIJKT_AF_VAN_GEAUTHENTICEERDE_AUTEUR")
    att_ts, aprob = _parse_ts(attestation.source_timestamp)
    if aprob:
        inv.append("ATTESTATIE_TIJDSTEMPEL_ONGELDIG " + aprob)
    else:
        if att_ts > now + SKEW:
            inv.append("TIMESTAMP_IN_FUTURE")
        if att_ts < TIMESTAMP_FLOOR:
            inv.append("TIMESTAMP_IMPLAUSIBLY_OLD")
        if claimed_ts is not None and claimed_ts != att_ts:
            inv.append("TIMESTAMP_MISMATCH (opgegeven tijd wijkt af van de bron)")
    if text_res["matches_source_text"] is False:
        inv.append("TEKST_KOMT_NIET_OVEREEN_MET_BRONBERICHT")
    if attestation.actor_type in ("BOT", "AUTOMATION"):
        inv.append("GEAUTHENTICEERDE_ACTOR_IS_GEEN_MENS")
    # vertrouwen in de provider: lijst + trust anchor
    reg_problems = _registry_problems(trusted_providers)
    entry = None
    if reg_problems:
        unv.extend(reg_problems)
    else:
        anchored = anchor.verify_pinned("human_decision_intake_trusted_providers_v1", canonical_sha256(trusted_providers))
        if not anchored.verified:
            unv.append("TRUSTED_PROVIDERS_REGISTRY_ONGEANKERD (" + (anchored.reason or "niet vastgepind") + ")")
        else:
            entry = next((p for p in trusted_providers["providers"] if p["provider_id"] == attestation.provider_id), None)
            if entry is None:
                unv.append("PROVIDER_NIET_VERTROUWD")
    out["human_presence"] = {"claimed_method": attestation.human_presence_evidence, "provable_method": attestation.human_presence_evidence in PROVABLE_PRESENCE_METHODS,
                             "accepted_by_registry": False, "verified_by_provider_check": False}
    if entry is not None:
        out["provider_trusted"], out["synthetic_source"] = True, bool(entry["synthetic"])
        hp = out["human_presence"]
        hp["accepted_by_registry"] = attestation.human_presence_evidence in entry["accepted_human_presence_methods"]
        if hp["provable_method"] and hp["accepted_by_registry"]:
            # een bewering van de attestatie volstaat nooit: de provider moet het bewijs voor DIT exacte bericht ter plekke controleren
            try:
                hp["verified_by_provider_check"] = provider.verify_human_presence(attestation, text_res["computed_sha256"]) is True
            except Exception:   # noqa: BLE001 — fail-closed
                hp["verified_by_provider_check"] = False
        if hp["verified_by_provider_check"]:
            out["authentication_status"] = AUTH_HUMAN
        else:
            out["authentication_status"] = AUTH_ACCOUNT
            unv.append("ACCOUNT_GEAUTHENTICEERD_MAAR_MENSELIJKE_AANWEZIGHEID_NIET_BEWEZEN (een bewering in de attestatie telt niet; zelfde account kan door een AI-tool worden gebruikt)")
        if attestation.actor_type == "UNKNOWN":
            unv.append("ACTOR_TYPE_ONBEKEND")
    else:
        out["authentication_status"] = AUTH_UNTRUSTED
    if inv:
        out["status"] = PROV_INVALID
    elif unv or out["authentication_status"] != AUTH_HUMAN:
        out["status"] = PROV_UNVERIFIABLE
    else:
        out["status"] = PROV_SOURCE_VERIFIED
    out["problems"] = inv + unv
    return out


# --- 3. autorisatie -------------------------------------------------------------------------------------------------------------------
def authorization_problems_in_doc(doc):
    if not isinstance(doc, dict) or doc.get("registry_version") != AUTHORIZATION_VERSION or set(doc) != {"registry_version", "note", "designations"} \
            or not isinstance(doc["designations"], list):
        return ["AUTORISATIE_CONFIG_ONGELDIG"]
    keys = {"reviewer_id", "designated_by", "designation_ref", "scope_levels", "approval_request_ids", "valid_from", "valid_until"}
    seen = set()
    for d in doc["designations"]:
        if not isinstance(d, dict) or set(d) != keys:
            return ["AUTORISATIE_CONFIG_ONGELDIG (aanwijzingsrecord)"]
        if _split_reviewer_key(d["reviewer_id"]) is None or not is_clean_id(d["designated_by"]) or not isinstance(d["scope_levels"], list) \
                or not isinstance(d["approval_request_ids"], list):
            return ["AUTORISATIE_CONFIG_ONGELDIG (dubbelzinnige of ongeldige identiteit: reviewer_id moet exact `provider:subject` zijn, designated_by een schoon ID)"]
        ident = (d["reviewer_id"].casefold(), tuple(d["approval_request_ids"]))
        if ident in seen:
            return ["AUTORISATIE_CONFIG_ONGELDIG (dubbele aanwijzing voor dezelfde reviewer en aanvraag, ook niet op hoofdlettergebruik na)"]
        seen.add(ident)
    return []


def evaluate_authorization(prov, authz_doc, anchor, approval_request_id, now):
    res = {"status": "NOT_EVALUATED", "reviewer_id": None, "designation_ref": None, "anchor_authority_ids": [], "registry_sha256": None, "problems": []}
    if prov["status"] != PROV_SOURCE_VERIFIED:
        res["problems"].append("NIET_BEOORDEELD: er is geen geauthenticeerde auteur (een opgegeven reviewer-id wordt nooit als bewijs gebruikt)")
        return res
    try:
        reviewer = reviewer_key(prov["attested"]["provider_id"], prov["attested"]["authenticated_author_id"])
    except ValueError:
        res["status"] = "UNAUTHORIZED"
        res["problems"].append("REVIEWER_IDENTITEIT_DUBBELZINNIG (provider/subject niet eenduidig samen te stellen)")
        return res
    res["reviewer_id"] = reviewer
    bad = authorization_problems_in_doc(authz_doc)
    if bad:
        res["status"] = "UNAUTHORIZED"
        res["problems"] += bad
        return res
    res["registry_sha256"] = canonical_sha256(authz_doc)
    anchored = anchor.verify_pinned("human_decision_reviewer_authorization_v1", res["registry_sha256"])
    if not anchored.verified:
        res["status"] = "UNANCHORED"
        res["problems"].append("AUTORISATIELIJST_ONGEANKERD (" + (anchored.reason or "niet vastgepind") + "): fail-closed; een lijst in de repository is geen bewijs van aanwijzing")
        return res
    res["anchor_authority_ids"] = list(anchored.authority_ids)
    mine = [d for d in authz_doc["designations"] if d["reviewer_id"] == reviewer]
    if not mine:
        res["status"] = "UNAUTHORIZED"
        res["problems"].append("GEEN_AANWIJZING_VOOR_DEZE_GEAUTHENTICEERDE_REVIEWER")
        return res
    for d in mine:
        why = []
        if d["designated_by"].casefold() in (reviewer.casefold(), prov["attested"]["authenticated_author_id"].casefold()):
            why.append("ZELFAANWIJZING")
        if d["designated_by"] not in anchored.authority_ids:
            why.append("AANWIJZER_IS_GEEN_GEANKERD_GEZAG")
        if "A" not in d["scope_levels"] or any(l != "A" for l in d["scope_levels"]):
            why.append("SCOPE_DEKT_NIET_UITSLUITEND_NIVEAU_A")
        if d["approval_request_ids"] != [approval_request_id]:
            why.append("AANWIJZING_GELDT_NIET_VOOR_DEZE_AANVRAAG")
        vf, _ = _parse_ts(d["valid_from"])
        vu, _ = _parse_ts(d["valid_until"])
        if vf is None or vu is None or not (vf <= now <= vu):
            why.append("AANWIJZING_NIET_GELDIG_OP_DIT_MOMENT")
        if not why:
            res["status"], res["designation_ref"] = "AUTHORIZED", d["designation_ref"]
            return res
        res["problems"] += [d["designation_ref"] + ": " + w for w in why]
    res["status"] = "UNAUTHORIZED"
    return res


# --- 4. inhoud (hergebruikt de v1-registervalidatie) -------------------------------------------------------------------------------------------
def _content_check_input(env, now):
    """PRIVÉ. Afbeelding op het v1-registerinvoerformaat ALLEEN om de bestaande inhoudsregels te hergebruiken (live aanvraag, hash, bewijs, erkenning APP/relaties,
    niveau A, FI-/pandverbod, duplicaten). Drie velden zijn bewust neutrale stand-ins en GEEN bewijs: decision_source, decided_by en identity_verification
    (identiteit en tijdstip worden uitsluitend door de herkomst- en autorisatiecontrole beoordeeld).
    Dit is GEEN registerinvoer: de uitkomst mag nooit buiten `evaluate_content` komen, want v1 accepteert deze velden als "menselijk besluit". Daarom is de functie privé,
    staat niet in `__all__`, en bewaakt een test dat geen publieke functie van deze module v1-acceptabele invoer teruggeeft."""
    return {"approval_request_id": env["approval_request_id"], "request_hash": env["request_hash"], "candidate_group_id": env["candidate_group_id"],
            "decision": env["decision"], "covers_levels": list(env["covers_levels"]), "decision_source": "HUMAN_CHAT_CONFIRMATION", "decided_by": "intake-content-check",
            "decision_provenance": {"channel": "FILE_EDITED_BY_HUMAN", "entered_by_kind": "HUMAN_DIRECT", "source_message_ref": "intake-content-check",
                                    "source_message_text": env["decision_text"], "identity_verification": R.IDENTITY_VERIFICATION, "ai_authored_decision": False},
            "decision_timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "acknowledged_open_app_ids": list(env["acknowledged_open_app_ids"]),
            "acknowledged_open_relations": list(env["acknowledged_open_relations"]), "evidence_reviewed": list(env["evidence_reviewed"]),
            "reviewer_notes": env["reviewer_notes"], "record_version": R.RECORD_VERSION}


def evaluate_content(env, ctx, existing, now):
    res = {"status": "INVALID", "stale_request": False, "register_conflict": False, "problems": [], "warnings": [], "live_request_hash": None, "live_approval_status": None}
    extra = []
    text = env["decision_text"]
    stmt = canonical_statement(env)
    if stmt is None or text != stmt:
        extra.append("BESLUITTEKST_IS_NIET_EXACT_DE_GEBONDEN_BESLUITVERKLARING (inhoudsbinding mislukt: fail-closed)")
    toks = _decision_tokens_in(text)           # tweede, onafhankelijke vangnet
    if len(toks) != 1 or toks[0] != env["decision"]:
        extra.append("BESLUITTEKST_NOEMT_NIET_PRECIES_DE_GEKOZEN_BESLUITKEUZE " + str(toks))
    if env["reviewer_notes"] != "":
        extra.append("REVIEWER_NOTES_NIET_TOEGESTAAN (vrije tekst is niet gebonden aan de besluitinhoud en kan die ontkennen; fail-closed)")
    if LEVEL_BC_TEXT.search(text) or LEVEL_BC_TEXT.search(env["reviewer_notes"]):
        extra.append("TEKST_CLAIMT_NIVEAU_B_OF_C (fail-closed, ook als disclaimer)")
    inp = _content_check_input(env, now)
    why, warn, fresh = R.validate_input(ctx, inp, existing, now=now)
    res["warnings"] = warn
    if fresh:
        res["live_request_hash"], res["live_approval_status"] = fresh["request_hash"], fresh["approval_status"]
    stale = [w for w in why if w.startswith("REQUEST_HASH")]
    conflict = [w for w in why if w.startswith(("DUPLICAAT_BESLUIT", "CONFLICTEREND_BESLUIT", "REGISTER_"))]
    other = [w for w in why if w not in stale and w not in conflict]
    res["stale_request"], res["register_conflict"] = bool(stale), bool(conflict)
    res["problems"] = stale + conflict + other + extra
    res["status"] = "VALID" if not res["problems"] else "INVALID"
    return res


# --- eindrapport ------------------------------------------------------------------------------------------------------------------------
def _envelope_problems(env):
    """(blokkerend, schemaproblemen). Blokkerend = beveiligingsregel geschonden of niet bruikbaar."""
    import jsonschema
    if not isinstance(env, dict):
        return ["ENVELOPE_GEEN_OBJECT"], []
    block = []

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if str(k).lower() in TRUSTED_ONLY_KEYS:
                    block.append(f"ZELF_OPGEGEVEN_VERTROUWD_VELD {path}/{k} (alleen de validator mag dit afleiden)")
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}/{i}")
    walk(env)
    schema = json.loads(ENVELOPE_SCHEMA.read_text(encoding="utf-8"))
    sp = sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(env))
    return block, sp


def _final(components):
    cands = set()
    if components["blocked"]:
        cands.add("BLOCKED")
    if components["stale"]:
        cands.add("STALE_REQUEST")
    if components["invalid_decision"]:
        cands.add("INVALID_DECISION")
    if components["unverified"]:
        cands.add("UNVERIFIED_SOURCE")
    if components["unauthorized"]:
        cands.add("UNAUTHORIZED_REVIEWER")
    for s in PRECEDENCE:
        if s in cands:
            return s
    return "VALIDATED_DRY_RUN"


def validate_intake(envelope, *, ctx=None, provider=None, trusted_providers=None, authorization=None, anchor=None, ledger=None, now=None, register_path=None):
    """DRY_RUN-intake. Retourneert altijd een rapport (nooit een uitzondering) en schrijft nooit iets."""
    try:
        return _validate_intake(envelope, ctx, provider, trusted_providers, authorization, anchor, ledger, now, register_path)
    except Exception as exc:   # noqa: BLE001 — fail-closed
        return _report(None, None, "BLOCKED", {}, [f"ONVERWACHTE_FOUT {type(exc).__name__}: {str(exc)[:120]}"], now)


def _validate_intake(envelope, ctx, provider, trusted_providers, authorization, anchor, ledger, now, register_path):
    now = now or datetime.now(timezone.utc)
    provider = provider or NullIntakeSourceProvider()
    anchor = anchor or NullTrustAnchor()
    if trusted_providers is None:
        trusted_providers, err = load_trusted_providers()
        if err:
            trusted_providers = {"registry_version": "ONLEESBAAR"}
    if authorization is None:
        authorization, err = load_authorization()
        if err:
            authorization = {"registry_version": "ONLEESBAAR"}
    block, schema_problems = _envelope_problems(envelope)
    comp = {"blocked": list(block), "stale": [], "invalid_decision": [], "unverified": [], "unauthorized": []}
    if not isinstance(envelope, dict) or schema_problems:
        comp["invalid_decision"] += ["ENVELOPE_SCHEMA " + s for s in schema_problems]
        if not isinstance(envelope, dict):
            comp["blocked"].append("ENVELOPE_ONBRUIKBAAR")
        return _report(envelope if isinstance(envelope, dict) else None, None, None, comp, None, now)
    env = envelope
    iid = intake_id_for(env)
    if "intake_id" in env and env["intake_id"] != iid:
        comp["blocked"].append("INTAKE_ID_KOMT_NIET_OVEREEN_MET_INHOUD")
    if env["decision"] not in DECISION_TOKENS:
        comp["invalid_decision"].append("ONBEKEND_BESLUIT (toegestaan: " + ", ".join(DECISION_TOKENS) + ")")
    # bron ophalen: alleen op basis van de verwijzing; nooit iets uit het bestand overnemen
    attestation, fetch_error = None, None
    ptr = env["source_pointer"]
    for k in ("provider_id", "source_message_id"):
        if ptr[k] is not None and not is_clean_id(ptr[k]):
            comp["blocked"].append(f"BRONVERWIJZING_ID_DUBBELZINNIG_OF_ONGELDIG {k}")
            ptr = {**ptr, k: None}
    if ptr["provider_id"] and ptr["source_message_id"]:
        try:
            attestation = provider.fetch(ptr["source_message_id"])
        except Exception as exc:   # noqa: BLE001
            fetch_error = type(exc).__name__
    text_res = check_text_integrity(env, attestation if isinstance(attestation, SourceAttestation) else None)
    prov = evaluate_provenance(env, fetch_error, attestation, trusted_providers, anchor, now, text_res, provider)
    if text_res["problems"]:
        comp["invalid_decision"] += ["TEKST " + p for p in text_res["problems"] if not p.startswith("TEKST_KOMT_NIET") and not p.startswith("BRONTEKST")]
    comp["invalid_decision"] += ["TIJDSTEMPEL " + p for p in prov["timestamp_format_problems"]]
    if prov["status"] == PROV_INVALID:
        comp["blocked"] += ["HERKOMST_INVALID " + p for p in prov["invalid"]]
    elif prov["status"] != PROV_SOURCE_VERIFIED:
        comp["unverified"] += ["HERKOMST_" + prov["status"] + " " + p for p in prov["unverifiable"]]
    # inhoud + actuele aanvraag (alleen-lezen)
    from_register = None
    try:
        existing = R.load_register(register_path or R.REGISTER_PATH)
    except R.RegisterCorrupt as exc:
        existing, from_register = [], f"REGISTER_BESCHADIGD {exc}"
        comp["blocked"].append(from_register)
    ctx = ctx or R.load_context()
    content = evaluate_content(env, ctx, existing, now)
    if content["stale_request"]:
        comp["stale"] += [p for p in content["problems"] if p.startswith("REQUEST_HASH")]
    if content["register_conflict"]:
        comp["blocked"] += [p for p in content["problems"] if p.startswith(("DUPLICAAT_BESLUIT", "CONFLICTEREND_BESLUIT"))]
    comp["invalid_decision"] += [p for p in content["problems"] if not p.startswith(("REQUEST_HASH", "DUPLICAAT_BESLUIT", "CONFLICTEREND_BESLUIT"))]
    # autorisatie (alleen zinvol met een geauthenticeerde auteur)
    authz = evaluate_authorization(prov, authorization, anchor, env["approval_request_id"], now)
    if prov["status"] == PROV_SOURCE_VERIFIED and authz["status"] != "AUTHORIZED":
        comp["unauthorized"] += ["AUTORISATIE_" + authz["status"] + " " + p for p in authz["problems"]]
    # replay / duplicaten (procesgebonden)
    fingerprint = canonical_sha256({k: v for k, v in env.items() if k != "intake_id"})       # identiek event = volledig identieke envelope
    message_key = (ptr["provider_id"], ptr["source_message_id"]) if ptr["provider_id"] and ptr["source_message_id"] else None
    replay = {"ledger_provided": ledger is not None, "scope": "PROCESS_LOCAL_MEMORY" if ledger is not None else "NONE", "persistent": False, "cross_process_guarantee": False,
              "problems": [], "note": ("Replay wordt alleen binnen dit ledger-object gedetecteerd; niet over processen, sessies of computers. De enige persistente bescherming is het "
                                       "bestaande register (geen besluit voor dezelfde request_hash); dat is nu leeg en wordt hier niet beschreven.")}
    if ledger is not None:
        replay["problems"] = ledger.check(message_key, fingerprint, env["decision"])
        comp["blocked"] += replay["problems"]
    rep = _report(env, iid, None, comp, None, now, text_res=text_res, prov=prov, authz=authz, content=content, replay=replay, ctx=ctx, register_path=register_path)
    if ledger is not None and not replay["problems"]:
        ledger.record(message_key, fingerprint, env["decision"])    # ook een afgewezen poging claimt het bericht-id binnen dit proces
    return rep


def _report(env, iid, final, comp, problems, now, text_res=None, prov=None, authz=None, content=None, replay=None, ctx=None, register_path=None):
    final = final or _final(comp)
    now = now or datetime.now(timezone.utc)
    recs_head = None
    try:
        recs = R.load_register(register_path or R.REGISTER_PATH)
        recs_head = R.register_head(recs)
        n_recs = len(recs)
    except R.RegisterCorrupt:
        n_recs = None
    synthetic = bool(prov and prov.get("synthetic_source"))
    ladder = {
        "1_claim_text": {"present": bool(env and isinstance(env.get("decision_text"), str) and env.get("decision_text")), "decision_claimed": env.get("decision") if env else None,
                         "meaning": "tekst waarin iemand beweert toestemming te geven; bewijst niets"},
        "2_author_id_asserted": {"present": bool(env and env.get("claims", {}).get("author_id")), "meaning": "zelf opgegeven auteur-ID; geen authenticatie"},
        "3_author_authenticated_by_system": {"present": bool(prov and prov["authentication_status"] == AUTH_HUMAN),
                                             "status": prov["authentication_status"] if prov else AUTH_NOT,
                                             "meaning": "geauthenticeerd door een vertrouwde bron met bewezen menselijke aanwezigheid"},
        "4_provenance_verified": {"present": bool(prov and prov["status"] == PROV_SOURCE_VERIFIED), "status": prov["status"] if prov else PROV_UNVERIFIABLE,
                                  "meaning": "bron, tekst, auteur, tijd en menselijke aanwezigheid onafhankelijk gecontroleerd"},
        "5_valid_level_a_decision": {"present": bool(content and content["status"] == "VALID" and text_res and text_res["status"] in ("MATCHES_SOURCE_TEXT", "MATCHES_CLAIMED_HASH_SELF_ONLY")),
                                     "meaning": "inhoudelijk geldig voor de actuele aanvraag; zegt niets over wie het schreef"},
        "6_registered": {"present": False, "meaning": "daadwerkelijk geregistreerd; niet mogelijk in deze intake (DRY_RUN)"},
        "7_instance_activated": {"present": False, "meaning": "geactiveerde fysieke instance; bestaat niet"},
    }
    confirmed_via_source = bool(prov and prov["status"] == PROV_SOURCE_VERIFIED and text_res and text_res.get("matches_source_text") and text_res.get("statement_binding") == "EXACT_MATCH")
    field_state = ("BOUND_TO_VERIFIED_SOURCE_STATEMENT (inhoud staat in een door een geverifieerde bron aangeleverde verklaring; alleen een mens met bewezen aanwezigheid kan dat bevestigen)"
                   if confirmed_via_source else "NOT_PROVEN_HUMAN_CONFIRMED (veld is alleen aangeleverd/gebonden aan tekst; niemand heeft aantoonbaar bevestigd dat een mens het las of koos)")
    human_confirmation = {k: field_state for k in ("covers_levels", "acknowledged_open_app_ids", "acknowledged_open_relations", "evidence_reviewed")}
    eligible = final == "VALIDATED_DRY_RUN" and not synthetic
    return {
        "report_version": REPORT_VERSION, "intake_version": INTAKE_VERSION, "mode": MODE, "final_status": final,
        "intake_id": iid, "approval_request_id": env.get("approval_request_id") if env else None,
        "request_hash_claimed": env.get("request_hash") if env else None, "request_hash_live": content["live_request_hash"] if content else None,
        "request_current": bool(content and content["live_request_hash"] and env and env.get("request_hash") == content["live_request_hash"] and not content["stale_request"]),
        "live_approval_status": content["live_approval_status"] if content else None,
        "received_timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text_integrity": text_res or {"status": "INVALID_TEXT"},
        "provenance": {"status": prov["status"] if prov else PROV_UNVERIFIABLE, "authentication_status": prov["authentication_status"] if prov else AUTH_NOT,
                       "claimed": prov["claimed"] if prov else None, "attested": prov["attested"] if prov else None, "provider_trusted": bool(prov and prov["provider_trusted"]),
                       "synthetic_source": synthetic, "problems": prov["problems"] if prov else []},
        "authorization": authz or {"status": "NOT_EVALUATED", "problems": []},
        "content_validation": content or {"status": "NOT_EVALUATED", "problems": []},
        "replay_protection": replay or {"ledger_provided": False, "scope": "NONE", "persistent": False, "cross_process_guarantee": False, "problems": [], "note": "niet beoordeeld"},
        "open_problems": sorted(set((problems or []) + (comp.get("blocked", []) + comp.get("stale", []) + comp.get("invalid_decision", []) + comp.get("unverified", []) + comp.get("unauthorized", [])))),
        "component_status": {"blocked": bool(comp.get("blocked")), "stale": bool(comp.get("stale")), "invalid_decision": bool(comp.get("invalid_decision")),
                             "unverified": bool(comp.get("unverified")), "unauthorized": bool(comp.get("unauthorized"))},
        "ladder": ladder, "human_confirmation_of_fields": human_confirmation,
        "registration_eligibility": "ELIGIBLE_FOR_FUTURE_REGISTRATION_STEP" if eligible else ("NOT_ELIGIBLE_SYNTHETIC_SOURCE" if final == "VALIDATED_DRY_RUN" and synthetic else "NOT_ELIGIBLE"),
        "registration_performed": False, "registration_possible_in_this_intake": False,
        "register_state": {"records": n_recs, "head": recs_head, "written": False},
        "effects": {"decisions_registered": 0, "register_written": False, "instances_created": 0, "fi_ids_created": 0, "instance_store_written": False, "bag_links_created": 0,
                    "quantities": None, "costs": None, "app_decisions_changed": 0, "pilot_decisions_changed": 0, "source_observations_changed": 0, "photo2_changed": False},
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
    }


def validate_batch(envelopes, **kwargs):
    """Verwerkt envelopes in volgorde met een EIGEN vers ledger: duplicaten en conflicten binnen de batch worden altijd gevonden (deterministisch, procesgebonden)."""
    ledger = InMemoryReplayLedger()
    return [validate_intake(e, ledger=ledger, **kwargs) for e in envelopes]


# --- v1/v2-compatibiliteit (alleen lezen; geen migratie) -------------------------------------------------------------------------------------
V2_REGISTER_VERSION = "human_instance_decision_register_v2"
V2_RECORD_VERSION = 2
V2_SCHEMA_PATH = ROOT / "schemas/human_instance_decision_v2.schema.json"
V2_KEYS = ["approval_request_id", "request_hash", "candidate_group_id", "decision", "covers_levels", "acknowledged_open_app_ids", "acknowledged_open_relations",
           "evidence_reviewed", "reviewer_notes", "record_version", "intake_id", "decision_text", "decision_text_sha256", "text_encoding", "text_normalization",
           "provenance", "authorization", "source_message_key", "v1_register_head", "decision_id", "sequence", "previous_record_hash", "record_hash", "register_version"]


def v1_record_as_legacy_view(rec):
    """Een v1-record blijft wat het was: een zelf opgegeven, niet-geauthenticeerde verklaring. Nooit sterker, ook niet als het record velden claimt."""
    return {"schema_version": 1, "decision_id": rec["decision_id"], "approval_request_id": rec["approval_request_id"], "request_hash": rec["request_hash"], "decision": rec["decision"],
            "provenance_verification_status": PROV_SELF_ASSERTED, "authentication_status": AUTH_NOT, "authorization_status": "NOT_ASSESSED_LEGACY_V1",
            "legacy_v1": True, "schema_valid": True, "verification_state": "LEGACY_SELF_ASSERTED", "counts_as_verified_v2": False, "instance_activated": False}


def load_register_v2(path, v1_head):
    """Leest en controleert een toekomstig v2-register (gesloten schema, hashketen die begint bij de kop van het v1-register). Schrijft niets en repareert niets."""
    import jsonschema
    p = Path(path)
    if not p.is_file():
        return []
    raw = p.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise R.RegisterCorrupt("V2_GEDEELTELIJK_GESCHREVEN")
    schema = strict_json_loads(V2_SCHEMA_PATH.read_text(encoding="utf-8"))
    recs, prev, keys = [], v1_head, set()
    for n, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        try:
            rec = strict_json_loads(line)
        except ValueError:
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_GEEN_JSON")
        if list(jsonschema.Draft7Validator(schema).iter_errors(rec)):
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_SCHEMA_ONGELDIG")
        if line != R.canonical(rec) or rec["sequence"] != n or rec["v1_register_head"] != v1_head:
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_NIET_CANONIEK_OF_VOLGORDE_OF_V1_KOP")
        if rec["previous_record_hash"] != prev or rec["record_hash"] != R.record_hash(rec):
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_KETEN_OF_HASH_ONJUIST")
        pv, az = rec["provenance"], rec["authorization"]
        if not (is_clean_id(pv["provider_id"]) and is_clean_id(pv["authenticated_author_id"]) and is_clean_id(pv["source_message_id"])):
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_ID_DUBBELZINNIG")
        if rec["source_message_key"] != pv["provider_id"] + ":" + pv["source_message_id"] or az["reviewer_id"] != pv["provider_id"] + ":" + pv["authenticated_author_id"]:
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_IDENTITEITSVELDEN_TEGENSTRIJDIG")
        stmt = canonical_statement(rec)
        if stmt is None or rec["decision_text"] != stmt or rec["decision_text_sha256"] != text_sha256(rec["decision_text"]) or rec["reviewer_notes"] != "":
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_TEKST_NIET_GEBONDEN_AAN_BESLUITINHOUD")
        if rec["source_message_key"] in keys:
            raise R.RegisterCorrupt(f"V2_REGEL_{n}_DUBBEL_BRONBERICHT")
        keys.add(rec["source_message_key"])
        prev = rec["record_hash"]
        recs.append(rec)
    return recs


def unified_register_view(v1_path=None, v2_path=None):
    """Eén logisch register, twee bestandsformaten. Drie begrippen blijven gescheiden: `schema_valid` (het bestand voldoet aan schema, keten en consistentiecontroles),
    `verification_state` (LEGACY_SELF_ASSERTED | SCHEMA_VALID_UNPROVEN | SIMULATED_VERIFICATION) en echte verificatie. Echte verificatie (REAL_VERIFIED) kent deze leesfunctie
    NOOIT toe: een bestand kan zijn eigen herkomst en autorisatie niet bewijzen, en deze module heeft geen trust anchor om de bron opnieuw te controleren.
    `counts_as_verified_v2` is daarom altijd False."""
    v1 = R.load_register(v1_path or R.REGISTER_PATH)
    for r in v1:                 # een v1-record blijft een v1-record: geen ander versienummer, geen ander registerlabel
        if r.get("record_version") != R.RECORD_VERSION or isinstance(r.get("record_version"), bool) or r.get("register_version") != R.REGISTER_VERSION:
            raise R.RegisterCorrupt("V1_RECORD_CLAIMT_ANDERE_VERSIE")
    head = R.register_head(v1)
    v2 = load_register_v2(v2_path, head) if v2_path else []
    entries = [v1_record_as_legacy_view(r) for r in v1]
    for r in v2:
        synthetic = r["provenance"]["synthetic_source"]
        entries.append({"schema_version": 2, "decision_id": r["decision_id"], "approval_request_id": r["approval_request_id"], "request_hash": r["request_hash"], "decision": r["decision"],
                        "recorded_provenance_claim": r["provenance"]["provenance_verification_status"], "recorded_authentication_claim": r["provenance"]["authentication_status"],
                        "recorded_authorization_claim": r["authorization"]["status"], "legacy_v1": False, "schema_valid": True,
                        "verification_state": "SIMULATED_VERIFICATION" if synthetic else "SCHEMA_VALID_UNPROVEN", "counts_as_verified_v2": False, "instance_activated": False})
    return {"v1_records": len(v1), "v2_records": len(v2), "v1_head": head, "entries": entries}


def v2_schema():
    str_ne = {"type": "string", "minLength": 1}
    h64 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    prov = {"type": "object", "additionalProperties": False,
            "required": ["provenance_verification_status", "authentication_status", "provider_id", "trust_registry_sha256", "attestation_sha256", "authenticated_author_id",
                         "author_authentication_method", "human_presence_evidence", "source_message_id", "source_timestamp", "received_timestamp", "synthetic_source"],
            "properties": {"provenance_verification_status": {"const": PROV_SOURCE_VERIFIED}, "authentication_status": {"const": AUTH_HUMAN}, "provider_id": str_ne,
                           "trust_registry_sha256": h64, "attestation_sha256": h64, "authenticated_author_id": str_ne, "author_authentication_method": str_ne,
                           "human_presence_evidence": {"enum": list(PROVABLE_PRESENCE_METHODS)}, "source_message_id": str_ne,
                           "source_timestamp": str_ne, "received_timestamp": str_ne, "synthetic_source": {"type": "boolean"}}}
    authz = {"type": "object", "additionalProperties": False, "required": ["status", "registry_sha256", "anchor_authority_ids", "designation_ref", "reviewer_id"],
             "properties": {"status": {"const": "AUTHORIZED"}, "registry_sha256": h64, "anchor_authority_ids": {"type": "array", "minItems": 1, "items": str_ne},
                            "designation_ref": str_ne, "reviewer_id": str_ne}}
    props = {"approval_request_id": {"type": "string", "pattern": "^IAR-OIC-"}, "request_hash": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
             "candidate_group_id": {"type": "string", "pattern": "^OIC-"}, "decision": {"enum": list(DECISION_TOKENS)}, "covers_levels": {"const": ["A"]},
             "acknowledged_open_app_ids": {"type": "array", "items": {"type": "string", "pattern": "^APP-\\d{3}$"}, "uniqueItems": True},
             "acknowledged_open_relations": {"type": "array", "items": {"type": "string", "pattern": "^VR-\\d{3}$"}, "uniqueItems": True},
             "evidence_reviewed": {"type": "array", "items": str_ne, "uniqueItems": True}, "reviewer_notes": {"type": "string"}, "record_version": {"const": V2_RECORD_VERSION},
             "intake_id": {"type": "string", "pattern": "^INT-[0-9a-f]{16}$"}, "decision_text": str_ne, "decision_text_sha256": h64, "text_encoding": {"const": "UTF-8"},
             "text_normalization": {"const": "NONE"}, "provenance": prov, "authorization": authz,
             "source_message_key": {"type": "string", "pattern": "^.+:.+$", "description": "provider_id:source_message_id; uniek in het register (persistente replaybescherming bij registratie)."},
             "v1_register_head": h64, "decision_id": {"type": "string", "pattern": "^HID-\\d{4}$"}, "sequence": {"type": "integer", "minimum": 1},
             "previous_record_hash": h64, "record_hash": h64, "register_version": {"const": V2_REGISTER_VERSION}}
    return {"$schema": "http://json-schema.org/draft-07/schema#", "$id": "human_instance_decision_v2.schema.json", "title": "Menselijk niveau-A-besluit, registerversie 2 (opgeslagen record)",
            "description": "ONTWERP/LEESFORMAAT. Een v2-record beschrijft een besluit met SOURCE_VERIFIED herkomst en AUTHORIZED reviewer, zoals de schrijver het VERKLAARDE; het bestand bewijst dat zelf niet. Schemageldigheid is geen verificatie "
                           "(`synthetic_source` true => `SIMULATED_VERIFICATION`, nooit meetellend). Het schema is gesloten. v1-records worden nooit omgezet: het v1-bestand blijft ongewijzigd en de v2-keten begint bij de kop van v1 "
                           "(`v1_register_head`). In deze PR bestaat geen v2-bestand en schrijft niets naar een register.",
            "type": "object", "additionalProperties": False, "required": V2_KEYS, "properties": props}


# --- CLI --------------------------------------------------------------------------------------------------------------------------------------------
# Bewust geen `to_content_input`/`_content_check_input` in de publieke API.
__all__ = ["validate_intake", "validate_batch", "check_text_integrity", "canonical_statement", "strict_json_loads", "DuplicateKeyError", "unified_register_view",
           "load_register_v2", "v2_schema", "text_sha256", "SourceAttestation", "IntakeSourceProvider", "NullIntakeSourceProvider", "TrustAnchor", "NullTrustAnchor",
           "AnchorResult", "InMemoryReplayLedger", "is_clean_id", "reviewer_key", "main"]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="DRY_RUN van een aangeleverd besluitbericht (envelope); schrijft niets")
    c.add_argument("--envelope", required=True)
    g = sub.add_parser("generate", help="schrijft v2-schema en rapporten (geen register-schrijfactie)")
    g.add_argument("--check", action="store_true", help="controleert alleen of de rapporten actueel zijn")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        try:
            env = strict_json_loads(Path(a.envelope).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:         # ook DuplicateKeyError en UnicodeDecodeError: weigeren, niet raden
            rep = validate_intake(None)
            rep["open_problems"] = sorted(set(rep["open_problems"]) | {f"ENVELOPE_ONLEESBAAR_OF_ONTOELAATBAAR_JSON {type(exc).__name__}: {str(exc)[:120]}"})
            print(json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True))
            return 1
        rep = validate_intake(env)       # standaardconfiguratie: geen provider, geen anchor => nooit SOURCE_VERIFIED
        print(json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if rep["final_status"] == "VALIDATED_DRY_RUN" else 1
    import human_decision_intake_report as RP   # noqa: E402
    return RP.generate(check=a.check)


if __name__ == "__main__":
    sys.exit(main())
