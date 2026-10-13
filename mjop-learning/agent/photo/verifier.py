"""Verifier voor een PhotoProposalSet: schema, herkomst/hashes, coordinaten, dubbele observaties,
telsemantiek en verboden beslissingen. Fail-closed: elke afwijking is een fout, nooit een stille reparatie."""
import math
import re
from dataclasses import dataclass, field

from agent.photo.contract import (COUNTING_TYPES, DUPLICATE_IOU, MIN_BOX_SIDE, PART_CONTAINMENT, PhotoError,
                                  canonical_sha256, containment, iou, load_schema, schema_errors, set_id_for,
                                  sha256_bytes)

# Velden die in een voorstel nooit mogen voorkomen: ze zouden een besluit, instance, kosten of oppervlak suggereren.
FORBIDDEN_KEYS = {"frame_instance_id", "instance_id", "fi_id", "decision", "accepted", "accept", "cost", "costs", "price",
                  "unit_price", "area_m2", "gross_area_m2", "painting_area", "painting_area_m2", "kengetal", "maintenance_action",
                  "building_total", "width_m", "height_m", "outer_width_m", "outer_height_m"}
# Vrije tekst mag geen vastgestelde feiten, besluiten of kosten claimen.
FORBIDDEN_TEXT = [
    (re.compile(r"\bFI-[A-Za-z0-9]", re.I), "verwijzing naar een instance-id (FI-*)"),
    (re.compile(r"\b(accept(eer|ed|atie)?|goedgekeurd|approved)\b", re.I), "besluit-/goedkeuringstaal"),
    (re.compile(r"(€|\beuro\b|\bkosten\b|\bprijs\b|\bprice\b|\bcost\b)", re.I), "kosten of prijs"),
    (re.compile(r"(m²|\bm2\b|\bvierkante meter\b)", re.I), "oppervlak"),
    (re.compile(r"\bNEN\s*2767\b", re.I), "NEN 2767-claim"),
    (re.compile(r"\b(vastgesteld|bevestigd|geverifieerd|bewezen|confirmed|verified)\b", re.I), "vastgesteld feit"),
    (re.compile(r"(roest|corrosie|schimmel|vocht|scheur|lekkage|rot\b|\brot)", re.I), "gebrek of conditieclaim"),
]


@dataclass
class Finding:
    code: str
    path: str
    message: str

    def __str__(self):
        return f"{self.code} {self.path}: {self.message}"


@dataclass
class VerificationResult:
    ok: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def codes(self):
        return sorted({e.code for e in self.errors})


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}/{k}", k, v
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}/{i}")


def _strings(doc):
    for p in doc.get("proposals", []) if isinstance(doc.get("proposals"), list) else []:
        if isinstance(p, dict):
            if isinstance(p.get("observation"), str):
                yield f"/proposals/{p.get('observation_id')}/observation", p["observation"]
            for u in p.get("uncertainties", []) if isinstance(p.get("uncertainties"), list) else []:
                if isinstance(u, dict) and isinstance(u.get("note"), str):
                    yield f"/proposals/{p.get('observation_id')}/uncertainties/note", u["note"]
    for h in doc.get("hidden_element_hypotheses", []) if isinstance(doc.get("hidden_element_hypotheses"), list) else []:
        if isinstance(h, dict) and isinstance(h.get("reason"), str):
            yield f"/hidden_element_hypotheses/{h.get('hypothesis_id')}/reason", h["reason"]


def _box_ok(box):
    return (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) for v in box))


def verify_proposal_set(doc, *, image_bytes=None, image_size=None, source_registry=None):
    """Controleert een voorstelset. Optioneel: `image_bytes` (hash van de geanalyseerde afgeleide kopie),
    `image_size` (breedte, hoogte) en `source_registry` ({photo_id: source_sha256} uit het fotoregister)."""
    errors, warnings = [], []

    def err(code, path, msg):
        errors.append(Finding(code, path, msg))

    if not isinstance(doc, dict):
        return VerificationResult(False, [Finding("SCHEMA", "<root>", "voorstelset moet een object zijn")])

    # 1. Verboden velden en besluiten, vooraf voor een duidelijke foutcode (naast het strikte schema).
    for path, key, value in _walk(doc):
        if key.lower() in FORBIDDEN_KEYS:
            err("FORBIDDEN_FIELD", path, f"veld '{key}' is niet toegestaan in een voorstel")
    for p in doc.get("proposals", []) if isinstance(doc.get("proposals"), list) else []:
        if isinstance(p, dict):
            loc = f"/proposals/{p.get('observation_id')}"
            if p.get("human_decision") is not None:
                err("FORBIDDEN_DECISION", loc + "/human_decision", "human_decision moet null zijn: een voorstel bevat geen besluit")
            if p.get("review_status") != "PROPOSED":
                err("FORBIDDEN_DECISION", loc + "/review_status", f"review_status moet PROPOSED zijn, niet {p.get('review_status')!r}")
            if p.get("is_instance") is not False:
                err("FORBIDDEN_DECISION", loc + "/is_instance", "is_instance moet false zijn: geen automatische instance-activatie")
            if p.get("counts_in_any_total") is not False:
                err("FORBIDDEN_DECISION", loc + "/counts_in_any_total", "counts_in_any_total moet false zijn")
            if p.get("bag_pand_id") is not None:
                err("FORBIDDEN_DECISION", loc + "/bag_pand_id", "bag_pand_id moet null zijn: geen pandkoppeling door een voorstel")
            if "visible_quantity" in p and p["visible_quantity"] != 1:
                err("COUNT_SEMANTICS", loc + "/visible_quantity",
                    "een fysieke kozijnopening blijft 1 opening, ook met meerdere vaste of draaiende delen; "
                    "gebruik parts_visible voor het aantal delen")
    for path, text in _strings(doc):
        for rx, label in FORBIDDEN_TEXT:
            if rx.search(text):
                err("FORBIDDEN_CLAIM", path, f"vrije tekst bevat {label}")

    # 2. Strikt schema.
    for e in schema_errors(doc, load_schema("photo_proposal_set.schema.json")):
        err("SCHEMA", "", e)
    if errors and any(e.code == "SCHEMA" for e in errors) and not isinstance(doc.get("proposals"), list):
        return VerificationResult(False, errors, warnings)

    # 3. Set-id (herkomst/integriteit van de inhoud).
    if "set_id" in doc and doc["set_id"] != set_id_for(doc):
        err("SET_ID_MISMATCH", "/set_id", "set_id komt niet overeen met de inhoud (voorstelset is gewijzigd)")

    # 4. Hashes en herkomst.
    photo = doc.get("photo") if isinstance(doc.get("photo"), dict) else {}
    if image_bytes is not None and photo.get("derivative_sha256") != sha256_bytes(image_bytes):
        err("HASH_MISMATCH", "/photo/derivative_sha256", "hash van de geanalyseerde afbeelding komt niet overeen")
    if image_size is not None and (photo.get("width_px"), photo.get("height_px")) != tuple(image_size):
        err("DIMENSION_MISMATCH", "/photo", f"afmetingen {image_size} wijken af van de voorstelset")
    if source_registry is not None:
        expected = source_registry.get(photo.get("photo_id"))
        if expected is None:
            err("PROVENANCE", "/photo/photo_id", "foto staat niet in het fotoregister")
        elif expected != photo.get("source_sha256"):
            err("PROVENANCE", "/photo/source_sha256", "source_sha256 wijkt af van het fotoregister")
    prov = doc.get("provider") if isinstance(doc.get("provider"), dict) else {}
    if prov.get("provider_name") == "anthropic" and not prov.get("consent_ref"):
        err("PROVENANCE", "/provider/consent_ref", "een externe provider vereist een consent_ref")
    if prov.get("provider_name") in ("replay", "human_import", "null_provider") and (prov.get("model_served") or prov.get("consent_ref")):
        err("PROVENANCE", "/provider", "replay/human_import/null_provider hebben geen model_served of consent_ref")

    # 5. Per voorstel: coordinaten, uniekheid, consistentie.
    props = [p for p in doc.get("proposals", []) if isinstance(p, dict)]
    seen = {}
    for p in props:
        oid = p.get("observation_id")
        loc = f"/proposals/{oid}"
        if oid in seen:
            err("DUPLICATE_OBSERVATION_ID", loc, "observation_id komt meer dan eens voor")
        seen[oid] = p
        box = p.get("bbox_norm")
        if not _box_ok(box):
            err("BBOX", loc + "/bbox_norm", "bbox_norm moet 4 eindige getallen bevatten")
            continue
        x1, y1, x2, y2 = box
        if not all(0 <= v <= 1 for v in box):
            err("BBOX", loc + "/bbox_norm", "coordinaten moeten binnen 0..1 liggen")
        if not (x1 < x2 and y1 < y2):
            err("BBOX", loc + "/bbox_norm", "verwacht x1<x2 en y1<y2")
        elif (x2 - x1) < MIN_BOX_SIDE or (y2 - y1) < MIN_BOX_SIDE:
            err("BBOX", loc + "/bbox_norm", f"zijde kleiner dan {MIN_BOX_SIDE}")
        unc = p.get("uncertainties") if isinstance(p.get("uncertainties"), list) else []
        if p.get("visibility") in ("PARTIAL", "OCCLUDED") and not unc:
            err("UNCERTAINTY_REQUIRED", loc + "/uncertainties", "PARTIAL en OCCLUDED vereisen minstens een onzekerheid")
        if p.get("visibility") == "OCCLUDED" and not any(isinstance(u, dict) and u.get("level") == "HIGH" for u in unc):
            err("UNCERTAINTY_REQUIRED", loc + "/uncertainties", "OCCLUDED vereist een onzekerheid met level HIGH")
        if "parts_visible" in p and p.get("element_type") not in COUNTING_TYPES:
            warnings.append(Finding("PARTS_IGNORED", loc, "parts_visible heeft geen betekenis voor dit type"))

    # 6. Dubbeltelling: zelfde type met bijna identiek vak, of een deel binnen een grotere opening.
    ordered = [p for p in props if _box_ok(p.get("bbox_norm")) and p["bbox_norm"][0] < p["bbox_norm"][2] and p["bbox_norm"][1] < p["bbox_norm"][3]]
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            ba, bb = a["bbox_norm"], b["bbox_norm"]
            overlap = iou(ba, bb)
            if a.get("element_type") == b.get("element_type"):
                if overlap >= DUPLICATE_IOU:
                    err("DUPLICATE_BOX", f"/proposals/{a['observation_id']}+{b['observation_id']}",
                        f"zelfde type en IoU {overlap:.2f}: dubbele observatie")
                    continue
                if a.get("element_type") in COUNTING_TYPES:
                    area_a = (ba[2] - ba[0]) * (ba[3] - ba[1])
                    area_b = (bb[2] - bb[0]) * (bb[3] - bb[1])
                    small, big = (ba, bb) if area_a <= area_b else (bb, ba)
                    if containment(small, big) >= PART_CONTAINMENT:
                        err("PART_OF_OPENING", f"/proposals/{a['observation_id']}+{b['observation_id']}",
                            "een vak ligt (bijna) volledig binnen een ander vak van hetzelfde type: waarschijnlijk een vast of "
                            "draaiend deel van een opening dat afzonderlijk is geteld")
            elif overlap >= 0.5:
                warnings.append(Finding("OVERLAPPING_TYPES", f"/proposals/{a['observation_id']}+{b['observation_id']}",
                                        f"verschillende typen overlappen sterk (IoU {overlap:.2f})"))

    # 7. Hypothesen mogen nooit tellen.
    for h in doc.get("hidden_element_hypotheses", []) if isinstance(doc.get("hidden_element_hypotheses"), list) else []:
        if isinstance(h, dict) and (h.get("visible_quantity") is not None or h.get("counts_in_any_total") is not False):
            err("HYPOTHESIS_COUNTS", f"/hidden_element_hypotheses/{h.get('hypothesis_id')}", "een hypothese heeft geen aantal en telt niet mee")

    # Foutdubbelingen (strikt schema + vooraf-scan) samenvoegen.
    uniq, out = set(), []
    for e in errors:
        key = (e.code, e.path, e.message)
        if key not in uniq:
            uniq.add(key)
            out.append(e)
    return VerificationResult(not out, out, warnings)


def verify_or_raise(doc, **kwargs):
    res = verify_proposal_set(doc, **kwargs)
    if not res.ok:
        raise PhotoError("INVALID_PROPOSAL_SET", "voorstelset is afgewezen", [str(e) for e in res.errors])
    return res


def seal_set(doc):
    """Zet de content-addressed set_id op een voorstelset (alleen voor sets die door deze code zijn opgebouwd)."""
    out = dict(doc)
    out["set_id"] = set_id_for(out)
    return out


def set_sha256(doc):
    return canonical_sha256(doc)
