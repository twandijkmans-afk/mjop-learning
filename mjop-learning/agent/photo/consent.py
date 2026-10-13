"""Toestemmings- en privacypoort voor externe visionproviders (fail-closed).

Een echte providercall is alleen mogelijk met (1) een geldig menselijk PCON-record dat exact deze afgeleide afbeelding
noemt en (2) een afzonderlijke bevestiging via de omgevingsvariabele MJOP_PHOTO_EXTERNAL_CONSENT_ID die gelijk moet zijn aan
het consent_id (dubbele sleutel). Dit module leest alleen; opslag van records is een zaak van de mens (privé-opslag)."""
import datetime as _dt
import os

from agent.photo.contract import ProviderError, load_schema, schema_errors

ENV_CONFIRM = "MJOP_PHOTO_EXTERNAL_CONSENT_ID"


def _parse_utc(s):
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)


def consent_problems(record, *, provider, photo_id, derivative_sha256, derivative_long_edge_px, media_type,
                     derivative_bytes_len=None, calls_used=0, now=None, environ=None):
    """Lijst met redenen waarom de call NIET mag; leeg = toegestaan."""
    env = os.environ if environ is None else environ
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if not isinstance(record, dict):
        return ["geen toestemmingsrecord opgegeven"]
    problems = list(schema_errors(record, load_schema("photo_consent_record.schema.json")))
    if problems:
        return ["toestemmingsrecord ongeldig: " + p for p in problems]
    if record["provider"] != provider:
        problems.append(f"record geldt voor provider {record['provider']}, niet {provider}")
    entry = next((p for p in record["photos"] if p["photo_id"] == photo_id and p["derivative_sha256"] == derivative_sha256), None)
    if entry is None:
        problems.append("deze foto/afgeleide hash staat niet in het toestemmingsrecord")
    else:
        if entry["privacy_check"] == "DENY":
            problems.append("privacycontrole voor deze foto is DENY")
        if entry["privacy_check"] == "ALLOW_WITH_REDACTION" and not entry.get("redaction_applied"):
            problems.append("privacycontrole eist redactie, maar redaction_applied is niet true")
    if now > _parse_utc(record["valid_until"]):
        problems.append("toestemmingsrecord is verlopen")
    if calls_used >= record["budget"]["max_calls"]:
        problems.append("aantal toegestane calls is bereikt")
    pol = record["derivative_policy"]
    if derivative_long_edge_px > pol["max_long_edge_px"]:
        problems.append("afgeleide afbeelding is groter dan de toegestane lange zijde in het record")
    if media_type != pol["media_type"]:
        problems.append("mediatype wijkt af van het record")
    if env.get(ENV_CONFIRM) != record["consent_id"]:
        problems.append(f"omgevingsvariabele {ENV_CONFIRM} is niet gelijk aan het consent_id (tweede sleutel ontbreekt)")
    return problems


def require_consent(record, **kwargs):
    problems = consent_problems(record, **kwargs)
    if problems:
        raise ProviderError("CONSENT_REQUIRED", "externe visionaanroep geweigerd", problems)
    return record["consent_id"]
