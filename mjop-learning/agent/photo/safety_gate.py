"""External Vision Safety Gate v1: de ENIGE route naar een externe visionaanroep (fail-closed).

Een externe provider mag pas een afbeelding ontvangen nadat `authorize_external_call` ALLE onderstaande controles heeft doorstaan.
Dit module schrijft nooit zelf (het persistente grootboek wordt als object aangeleverd, zie scripts/vision_budget_ledger.py).

1. Providerregister: de provider moet in PROVIDER_APPROVALS met status APPROVED staan. Dat is een menselijk, reviewbaar codebesluit;
   in deze release staat elke externe provider op NOT_APPROVED, dus er kan geen echte aanroep plaatsvinden.
2. Authentiek toestemmingsrecord: schema + HMAC-SHA256 van de menselijke goedkeurder (sleutel in de omgeving, nooit in de repository),
   plus alle inhoudelijke controles uit consent.py (foto/hash, privacy, geldigheid, model, tokens, bestandsgrootte) en de tweede sleutel.
3. Werkelijke afbeeldingscontrole: de bytes zelf worden geinspecteerd (formaat, containerstructuur, metadata, afmetingen, grootte,
   decompressiebom, animatie); niets uit het verzoek wordt op gezag aangenomen.
4. Procesoverstijgende budgetcontrole: een persistent grootboek reserveert de call atomair VOOR verzending; een geweigerde of
   mislukte controle verbruikt niets, een mislukte verzending telt wel (conservatief).
Het resultaat is een eenmalig, aan dit verzoek gebonden `GateAuthorization`; de verzendfunctie weigert alles zonder zo'n token."""
import hashlib
import hmac
import io
import os
import struct
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from agent.photo.consent import consent_problems
from agent.photo.contract import MEDIA_TYPES, ProviderError, canonical_sha256, load_schema, schema_errors, sha256_bytes

ENV_AUTH_KEY = "MJOP_VISION_AUTH_KEY"
MIN_AUTH_KEY_LEN = 32
ABSOLUTE_MAX_FILE_BYTES = 20_000_000            # harde grens, onafhankelijk van elk record
ABSOLUTE_MAX_PIXELS = 25_000_000                # decompressiebom-grens, gecontroleerd vóór decodering

# Menselijk, reviewbaar providerbesluit. NOT_APPROVED = geen enkele externe aanroep, ook niet met een geldig consentrecord.
PROVIDER_APPROVALS = {
    "anthropic": {"status": "NOT_APPROVED",
                  "reason": "definitieve provider- en privacygoedkeuring ontbreekt (verplichte voorwaarde voor de eerste externe Vision-test)"},
}


class GateRefusal(ProviderError):
    """De veiligheidspoort weigert. `reasons` bevat stabiele codes (bv. IMAGE_METADATA_PRESENT, BUDGET_CALLS_EXHAUSTED)."""

    def __init__(self, reasons, details=None):
        reasons = list(reasons)
        super().__init__("GATE_REFUSED", "externe visionaanroep geweigerd door de veiligheidspoort: " + ", ".join(reasons), details or reasons)
        self.reasons = reasons


# --------------------------------------------------------------------------------------------------------------------
# 3. Werkelijke afbeeldingscontrole
# --------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ImageFacts:
    media_type: str
    width_px: int
    height_px: int
    file_bytes: int
    sha256: str


_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_ALLOWED = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"sRGB", b"pHYs", b"cHRM", b"sBIT"}
_JPEG_ALLOWED = {0xDB, 0xC4, 0xDD, 0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def detect_media_type(data):
    if data.startswith(_PNG_SIG):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _scan_png(d, bad):
    pos, first, seen_idat = 8, True, False
    while pos < len(d):
        if pos + 12 > len(d):
            bad("IMAGE_CONTAINER_INVALID", "PNG: afgekapt chunk")
            return
        n = struct.unpack(">I", d[pos:pos + 4])[0]
        ctype = d[pos + 4:pos + 8]
        if pos + 12 + n > len(d):
            bad("IMAGE_CONTAINER_INVALID", "PNG: chunklengte wijst voorbij het bestand")
            return
        if zlib.crc32(d[pos + 4:pos + 8 + n]) & 0xFFFFFFFF != struct.unpack(">I", d[pos + 8 + n:pos + 12 + n])[0]:
            bad("IMAGE_CONTAINER_INVALID", f"PNG: CRC-fout in {ctype!r}")
            return
        if first and ctype != b"IHDR":
            bad("IMAGE_CONTAINER_INVALID", "PNG: eerste chunk is geen IHDR")
        first = False
        if ctype not in _PNG_ALLOWED:
            bad("IMAGE_METADATA_PRESENT", f"PNG: niet-toegestane chunk {ctype!r} (tekst-, EXIF-, ICC- of onbekende data)")
        seen_idat |= ctype == b"IDAT"
        pos += 12 + n
        if ctype == b"IEND":
            if pos != len(d):
                bad("IMAGE_TRAILING_DATA", "PNG: data na IEND")
            if not seen_idat:
                bad("IMAGE_CONTAINER_INVALID", "PNG: geen beelddata")
            return
    bad("IMAGE_CONTAINER_INVALID", "PNG: IEND ontbreekt")


def _scan_jpeg(d, bad):
    pos, n = 2, len(d)
    while pos < n:
        if d[pos] != 0xFF:
            bad("IMAGE_CONTAINER_INVALID", "JPEG: marker verwacht")
            return
        while pos < n and d[pos] == 0xFF:
            pos += 1
        if pos >= n:
            break
        m = d[pos]
        pos += 1
        if m == 0xD9:
            if pos != n:
                bad("IMAGE_TRAILING_DATA", "JPEG: data na EOI")
            return
        if m == 0x01 or 0xD0 <= m <= 0xD8 or m == 0x00:
            bad("IMAGE_CONTAINER_INVALID", "JPEG: onverwachte marker")
            return
        if pos + 2 > n:
            bad("IMAGE_CONTAINER_INVALID", "JPEG: afgekapt segment")
            return
        ln = struct.unpack(">H", d[pos:pos + 2])[0]
        if ln < 2 or pos + ln > n:
            bad("IMAGE_CONTAINER_INVALID", "JPEG: ongeldige segmentlengte")
            return
        body = d[pos + 2:pos + ln]
        if m == 0xE0:
            if not body.startswith(b"JFIF\x00"):
                bad("IMAGE_METADATA_PRESENT", "JPEG: APP0 is geen JFIF")
        elif m == 0xEE:
            if not body.startswith(b"Adobe"):
                bad("IMAGE_METADATA_PRESENT", "JPEG: APP14 is geen Adobe-kleurmarker")
        elif m == 0xDA:
            pos += ln                                                    # entropie-gecodeerde data tot de volgende echte marker
            while pos < n - 1:
                if d[pos] == 0xFF and d[pos + 1] not in (0x00,) and not (0xD0 <= d[pos + 1] <= 0xD7) and d[pos + 1] != 0xFF:
                    break
                pos += 1
            continue
        elif m not in _JPEG_ALLOWED:
            bad("IMAGE_METADATA_PRESENT", f"JPEG: niet-toegestaan segment 0x{m:02X} (EXIF/XMP/ICC/commentaar/overig)")
        pos += ln
    bad("IMAGE_CONTAINER_INVALID", "JPEG: EOI ontbreekt")


def _gif_subblocks(d, pos):
    while True:
        if pos >= len(d):
            return None
        ln = d[pos]
        pos += 1
        if ln == 0:
            return pos
        pos += ln


def _scan_gif(d, bad):
    if len(d) < 13:
        bad("IMAGE_CONTAINER_INVALID", "GIF: afgekapt")
        return
    flags = d[10]
    pos = 13 + (3 * (2 << (flags & 7)) if flags & 0x80 else 0)
    images = 0
    while pos < len(d):
        b = d[pos]
        if b == 0x3B:
            if pos + 1 != len(d):
                bad("IMAGE_TRAILING_DATA", "GIF: data na trailer")
            if images != 1:
                bad("IMAGE_ANIMATED_OR_MULTIFRAME", f"GIF: {images} beelden")
            return
        if b == 0x21:
            label = d[pos + 1] if pos + 1 < len(d) else None
            if label != 0xF9:
                bad("IMAGE_METADATA_PRESENT", f"GIF: extensie 0x{(label or 0):02X} (commentaar/applicatie/tekst)")
            pos = _gif_subblocks(d, pos + 2)
        elif b == 0x2C:
            images += 1
            if pos + 10 > len(d):
                bad("IMAGE_CONTAINER_INVALID", "GIF: afgekapt beeld")
                return
            lf = d[pos + 9]
            pos += 10 + (3 * (2 << (lf & 7)) if lf & 0x80 else 0) + 1
            pos = _gif_subblocks(d, pos) if pos < len(d) else None
        else:
            bad("IMAGE_CONTAINER_INVALID", "GIF: onbekend blok")
            return
        if pos is None:
            bad("IMAGE_CONTAINER_INVALID", "GIF: afgekapt blok")
            return
    bad("IMAGE_CONTAINER_INVALID", "GIF: trailer ontbreekt")


def _scan_webp(d, bad):
    if len(d) < 20:
        bad("IMAGE_CONTAINER_INVALID", "WEBP: afgekapt")
        return
    riff = struct.unpack("<I", d[4:8])[0]
    if riff + 8 != len(d):
        bad("IMAGE_TRAILING_DATA" if riff + 8 < len(d) else "IMAGE_CONTAINER_INVALID", "WEBP: RIFF-lengte komt niet overeen met het bestand")
        return
    pos = 12
    while pos < len(d):
        if pos + 8 > len(d):
            bad("IMAGE_CONTAINER_INVALID", "WEBP: afgekapt chunk")
            return
        tag = d[pos:pos + 4]
        ln = struct.unpack("<I", d[pos + 4:pos + 8])[0]
        if tag == b"VP8X":
            if ln < 10 or d[pos + 8] & 0x2E:
                bad("IMAGE_METADATA_PRESENT", "WEBP: VP8X-vlaggen voor ICC/EXIF/XMP/animatie")
        elif tag not in (b"VP8 ", b"VP8L", b"ALPH"):
            bad("IMAGE_METADATA_PRESENT", f"WEBP: niet-toegestane chunk {tag!r}")
        pos += 8 + ln + (ln & 1)
    if pos != len(d):
        bad("IMAGE_CONTAINER_INVALID", "WEBP: chunklengtes sluiten niet aan")


_SCANNERS = {"image/png": _scan_png, "image/jpeg": _scan_jpeg, "image/gif": _scan_gif, "image/webp": _scan_webp}


def inspect_image(data, *, declared_media_type, declared_width, declared_height, max_long_edge_px, max_file_bytes):
    """Inspecteert de werkelijke bytes. Gooit GateRefusal met ALLE gevonden redenen; geeft anders ImageFacts."""
    reasons, details = [], []

    def bad(code, msg):
        if code not in reasons:
            reasons.append(code)
        details.append(f"{code}: {msg}")

    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise GateRefusal(["IMAGE_MISSING"], ["IMAGE_MISSING: geen afbeeldingsbytes"])
    data = bytes(data)
    if len(data) > min(max_file_bytes, ABSOLUTE_MAX_FILE_BYTES):
        bad("IMAGE_TOO_LARGE_BYTES", f"{len(data)} bytes > grens {min(max_file_bytes, ABSOLUTE_MAX_FILE_BYTES)}")
    real = detect_media_type(data)
    if real is None or real not in MEDIA_TYPES:
        bad("IMAGE_FORMAT_UNSUPPORTED", "onbekende of niet-ondersteunde bestandskop")
    elif real != declared_media_type:
        bad("IMAGE_MEDIA_TYPE_MISMATCH", f"bytes zijn {real}, verzoek zegt {declared_media_type}")
    if reasons:
        raise GateRefusal(reasons, details)

    _SCANNERS[real](data, bad)
    width = height = None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            if getattr(img, "is_animated", False) or getattr(img, "n_frames", 1) != 1:
                bad("IMAGE_ANIMATED_OR_MULTIFRAME", "meerdere frames")
            if width < 1 or height < 1 or width * height > ABSOLUTE_MAX_PIXELS:
                bad("IMAGE_TOO_MANY_PIXELS", f"{width}x{height} px (grens {ABSOLUTE_MAX_PIXELS})")
            elif not reasons:
                img.load()                                               # volledige decodering: corrupte of vervalste data faalt hier
                if img.getexif() or {"exif", "xmp", "XML:com.adobe.xmp", "icc_profile", "comment", "photoshop"} & set(img.info):
                    bad("IMAGE_METADATA_PRESENT", "EXIF/XMP/ICC/commentaar aangetroffen na decodering")
    except GateRefusal:
        raise
    except Exception as ex:                                              # noqa: BLE001 - elke decodeerfout is een weigering
        bad("IMAGE_DECODE_FAILED", f"{type(ex).__name__}")
    if width is not None:
        if (width, height) != (declared_width, declared_height):
            bad("IMAGE_DIMENSION_MISMATCH", f"werkelijk {width}x{height}, verzoek {declared_width}x{declared_height}")
        if max(width, height) > max_long_edge_px:
            bad("IMAGE_TOO_LARGE_PIXELS", f"lange zijde {max(width, height)} > {max_long_edge_px}")
    if reasons:
        raise GateRefusal(reasons, details)
    return ImageFacts(real, width, height, len(data), sha256_bytes(data))


# --------------------------------------------------------------------------------------------------------------------
# 2. Authenticiteit van het toestemmingsrecord
# --------------------------------------------------------------------------------------------------------------------
def consent_mac(record, key):
    body = {k: v for k, v in record.items() if k != "authorization"}
    return hmac.new(key.encode("utf-8"), canonical_sha256(body).encode("ascii"), hashlib.sha256).hexdigest()


def sign_consent(record, key):
    """Voor de menselijke goedkeurder (en tests): geeft een kopie met `authorization`. De sleutel verlaat de omgeving niet."""
    if not isinstance(key, str) or len(key) < MIN_AUTH_KEY_LEN:
        raise ValueError(f"sleutel moet minstens {MIN_AUTH_KEY_LEN} tekens zijn")
    out = {k: v for k, v in record.items() if k != "authorization"}
    out["authorization"] = {"alg": "HMAC-SHA256", "mac": consent_mac(out, key)}
    return out


def consent_authentication_problems(record, environ):
    key = environ.get(ENV_AUTH_KEY)
    if not isinstance(key, str) or len(key) < MIN_AUTH_KEY_LEN:
        return [f"omgevingsvariabele {ENV_AUTH_KEY} ontbreekt of is korter dan {MIN_AUTH_KEY_LEN} tekens (sleutel van de menselijke goedkeurder)"]
    auth = record.get("authorization") if isinstance(record, dict) else None
    if not isinstance(auth, dict) or auth.get("alg") != "HMAC-SHA256" or not isinstance(auth.get("mac"), str):
        return ["toestemmingsrecord is niet ondertekend"]
    if not hmac.compare_digest(auth["mac"], consent_mac(record, key)):
        return ["handtekening van het toestemmingsrecord klopt niet (record gewijzigd of met een andere sleutel ondertekend)"]
    return []


# --------------------------------------------------------------------------------------------------------------------
# 4. Persistent grootboek (interface; implementatie schrijft en staat daarom buiten agent/photo)
# --------------------------------------------------------------------------------------------------------------------
class BudgetLedger(ABC):
    """Procesoverstijgend, atomair en tamper-evident. Een implementatie MOET persistent=True en cross_process_safe=True zijn."""
    persistent = False
    cross_process_safe = False

    @abstractmethod
    def reserve(self, *, consent_id, consent_sha256, derivative_sha256, max_calls, max_tokens_total, tokens_per_call, now):
        """Reserveert atomair een call; gooit GateRefusal (BUDGET_*, LEDGER_*) en verbruikt dan niets. Geeft een reservation_id."""

    @abstractmethod
    def settle(self, reservation_id, *, outcome, output_tokens=None):
        """Legt het resultaat van een verzonden call vast (de reservering blijft verbruikt)."""

    @abstractmethod
    def release(self, reservation_id, *, reason):
        """Geeft een reservering vrij die aantoonbaar NIET is verzonden."""


@dataclass
class GateAuthorization:
    """Eenmalig, aan dit verzoek gebonden bewijs dat de poort is gepasseerd. Alleen `authorize_external_call` maakt dit."""
    provider: str
    model: str
    max_tokens: int
    consent_id: str
    photo_id: str
    derivative_sha256: str
    prompt_sha256: str
    image: ImageFacts
    reservation_id: str
    ledger: object = field(repr=False)
    _seal: object = field(default=None, repr=False)
    _state: str = field(default="ISSUED", repr=False)

    def __post_init__(self):
        if self._seal is not _SEAL:
            raise TypeError("GateAuthorization kan alleen door authorize_external_call worden uitgegeven")

    def consume(self):
        """Markeert het token als gebruikt vlak vóór verzending; een tweede gebruik is verboden."""
        if self._state != "ISSUED":
            raise GateRefusal(["AUTHORIZATION_ALREADY_USED"])
        self._state = "SENDING"

    def settle(self, outcome, output_tokens=None):
        if self._state == "SENDING":
            self.ledger.settle(self.reservation_id, outcome=outcome, output_tokens=output_tokens)
            self._state = "SETTLED"

    def release_unsent(self, reason):
        if self._state == "ISSUED":
            self.ledger.release(self.reservation_id, reason=reason)
            self._state = "RELEASED"


_SEAL = object()


def require_authorization(auth, *, provider, model, max_tokens, image_bytes, prompt_sha256):
    """Laatste controle vlak voor de verzending: het token is echt, ongebruikt en hoort bij exact deze bytes, dit model en deze prompt."""
    if not isinstance(auth, GateAuthorization) or auth._seal is not _SEAL:
        raise GateRefusal(["AUTHORIZATION_MISSING"])
    if auth._state != "ISSUED":
        raise GateRefusal(["AUTHORIZATION_ALREADY_USED"])
    if (auth.provider, auth.model, auth.max_tokens, auth.prompt_sha256) != (provider, model, max_tokens, prompt_sha256) \
            or sha256_bytes(image_bytes) != auth.derivative_sha256:
        raise GateRefusal(["AUTHORIZATION_MISMATCH"])


def authorize_external_call(*, provider, request, config, consent, ledger, prompt_sha256, environ=None, now=None):
    """Voert alle controles uit in vaste volgorde; het grootboek wordt als LAATSTE geraakt zodat een eerdere weigering niets verbruikt."""
    env = os.environ if environ is None else environ
    approval = PROVIDER_APPROVALS.get(provider)
    if not approval or approval.get("status") != "APPROVED":
        raise GateRefusal(["PROVIDER_NOT_APPROVED"], ["PROVIDER_NOT_APPROVED: " + (approval or {}).get("reason", "provider onbekend")])
    if not isinstance(ledger, BudgetLedger) or ledger.persistent is not True or ledger.cross_process_safe is not True:
        raise GateRefusal(["LEDGER_NOT_PERSISTENT"], ["LEDGER_NOT_PERSISTENT: een procesoverstijgend persistent grootboek is verplicht"])
    if not isinstance(consent, dict):
        raise GateRefusal(["CONSENT_MISSING"])
    problems = [f"CONSENT_SCHEMA: {e}" for e in schema_errors(consent, load_schema("photo_consent_record.schema.json"))]
    if problems:
        raise GateRefusal(["CONSENT_INVALID"], problems)
    auth_problems = consent_authentication_problems(consent, env)
    if auth_problems:
        raise GateRefusal(["CONSENT_NOT_AUTHENTIC"], ["CONSENT_NOT_AUTHENTIC: " + p for p in auth_problems])
    image = inspect_image(request.image_bytes, declared_media_type=request.media_type, declared_width=request.width_px,
                          declared_height=request.height_px, max_long_edge_px=consent["derivative_policy"]["max_long_edge_px"],
                          max_file_bytes=consent["derivative_policy"]["max_file_bytes"])
    if image.sha256 != request.derivative_sha256:
        raise GateRefusal(["IMAGE_HASH_MISMATCH"], ["IMAGE_HASH_MISMATCH: bytes komen niet overeen met derivative_sha256 van het verzoek"])
    if image.media_type != consent["derivative_policy"]["media_type"]:
        raise GateRefusal(["IMAGE_MEDIA_TYPE_MISMATCH"], ["IMAGE_MEDIA_TYPE_MISMATCH: wijkt af van het consentrecord"])
    problems = consent_problems(consent, provider=provider, photo_id=request.photo_id, derivative_sha256=image.sha256,
                                derivative_long_edge_px=max(image.width_px, image.height_px), media_type=image.media_type,
                                derivative_bytes_len=image.file_bytes, model=config.model, max_tokens=config.max_tokens, now=now, environ=env)
    if problems:
        raise GateRefusal(["CONSENT_REFUSED"], ["CONSENT_REFUSED: " + p for p in problems])
    rid = ledger.reserve(consent_id=consent["consent_id"], consent_sha256=canonical_sha256(consent), derivative_sha256=image.sha256,
                         max_calls=consent["budget"]["max_calls"], max_tokens_total=consent["budget"]["max_output_tokens"],
                         tokens_per_call=config.max_tokens, now=now)
    return GateAuthorization(provider, config.model, config.max_tokens, consent["consent_id"], request.photo_id, image.sha256,
                             prompt_sha256, image, rid, ledger, _seal=_SEAL)
