"""Gedeelde constanten, schema-laadhulp en foutklasse van de Photo Reviewer (alleen lezen)."""
import hashlib
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_DIR = os.path.join(PROJECT_ROOT, "schemas")

ELEMENT_TYPES = ("WINDOW_OPENING", "EXTERIOR_DOOR", "BALCONY_DOOR", "BALCONY_STRUCTURE", "BALCONY_RAILING",
                 "ROOF_WINDOW", "DORMER_OPENING", "UNKNOWN_OPENING")
# Soorten die als kozijnopening/deur in de PHOTO_VISIBLE-aantallen meetellen (bestaande telregel: dakramen en
# dakkapellen tellen niet mee in kozijnaantallen).
COUNTING_TYPES = ("WINDOW_OPENING", "EXTERIOR_DOOR", "BALCONY_DOOR")
AREA_TYPES = COUNTING_TYPES
VISIBILITIES = ("FULL", "PARTIAL", "OCCLUDED")

MIN_BOX_SIDE = 0.004            # genormaliseerd; kleiner is geen geloofwaardige opening
DUPLICATE_IOU = 0.85            # zelfde type en IoU >= drempel: dubbele observatie
PART_CONTAINMENT = 0.90         # klein vak (>= 90% binnen een groter vak van hetzelfde type): onderdeel, geen opening
MIN_DIMENSION_M = "0.10"        # plausibiliteitsgrenzen voor INVOER van maten (geen AI-schatting)
MAX_DIMENSION_M = "10"

MEDIA_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")   # providerdocumentatie, gecontroleerd 2026-10-13


class PhotoError(Exception):
    """Een component weigert expliciet; er wordt nooit een gegokte waarde teruggegeven."""

    def __init__(self, code, message, details=None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.details = code, message, list(details or [])


class ProviderError(PhotoError):
    """Fout in of rond een visionprovider (ook een geweigerde toestemming)."""


def canonical_sha256(obj):
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load_schema(name):
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def schema_errors(instance, schema):
    import jsonschema
    validator = jsonschema.Draft7Validator(schema)
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}"
                  for e in validator.iter_errors(instance))


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def containment(small, big):
    """Aandeel van het oppervlak van `small` dat binnen `big` valt."""
    ix = max(0.0, min(small[2], big[2]) - max(small[0], big[0]))
    iy = max(0.0, min(small[3], big[3]) - max(small[1], big[1]))
    area = (small[2] - small[0]) * (small[3] - small[1])
    return (ix * iy) / area if area > 0 else 0.0


def set_id_for(doc):
    body = {k: v for k, v in doc.items() if k != "set_id"}
    return "PPS-" + canonical_sha256(body)[:16]
