"""Modelonafhankelijke vision-interface.

- ReplayProvider: reproduceerbare, opgeslagen antwoorden (geen netwerk, geen afbeelding nodig).
- HumanImportProvider: bestaande handmatige annotaties als voorstellen (besluiten worden NIET overgenomen).
- NullProvider: levert niets.
- ClaudeVisionProvider: optionele adapter, standaard UITGESCHAKELD; vereist toestemmingsrecord (consent.py).

Elke provider levert een RUW antwoord; `build_proposal_set` zet dat deterministisch om en dwingt alle invarianten af
(PROPOSED, geen besluit, geen instance, geen pandkoppeling). Een model kan die velden dus niet zelf zetten."""
import copy
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from agent.photo.contract import (COUNTING_TYPES, ELEMENT_TYPES, MEDIA_TYPES, VISIBILITIES, PhotoError, ProviderError,
                                  canonical_sha256, sha256_bytes)
from agent.photo.safety_gate import GateRefusal, authorize_external_call, require_authorization
from agent.photo.verifier import seal_set

ADAPTER_VERSION = "0.1.0"
PROMPT_ID = "photo_openings_v1"

PROMPT = """You analyse one photo of a building facade. Report only what is clearly visible.
Return ONLY a JSON object with this shape and no other text:
{"proposals":[{"element_type":"WINDOW_OPENING|EXTERIOR_DOOR|BALCONY_DOOR|BALCONY_STRUCTURE|BALCONY_RAILING|ROOF_WINDOW|DORMER_OPENING|UNKNOWN_OPENING",
"bbox_px":[x1,y1,x2,y2],"visibility":"FULL|PARTIAL|OCCLUDED","parts_visible":1,
"uncertainties":[{"code":"OCCLUDED_BY_OBJECT|OCCLUDED_BY_VEGETATION|OBLIQUE_ANGLE|LOW_RESOLUTION|BACKLIT|CROPPED_AT_EDGE|AMBIGUOUS_COUNTING_UNIT|AMBIGUOUS_TYPE|REFLECTION_OR_GLARE|OTHER","level":"LOW|MEDIUM|HIGH"}],
"observation":"short neutral description"}],
"hidden_element_hypotheses":[{"element_type":"...","reason":"why an element may exist but is not visible"}]}
Rules: bbox_px are pixel coordinates in the image as sent (origin top-left). One physical opening is ONE proposal, even if it has
several fixed or turning sashes (use parts_visible for the number of sashes). Do not box individual sashes or glass panes.
Roof windows and dormers are separate types. Do not report materials, condition, defects, costs, areas, addresses or people.
If unsure, use visibility PARTIAL/OCCLUDED or AMBIGUOUS_* uncertainties instead of guessing. Hidden elements go only in
hidden_element_hypotheses, never in proposals."""
PROMPT_SHA256 = sha256_bytes(PROMPT.encode("utf-8"))

_RAW_PROPOSAL_KEYS = {"element_type", "bbox_norm", "visibility", "parts_visible", "uncertainties", "observation", "note"}
_RAW_HYPOTHESIS_KEYS = {"element_type", "reason", "region_hint"}


@dataclass
class VisionRequest:
    photo_id: str
    source_sha256: str
    derivative_sha256: str
    width_px: int
    height_px: int
    image_bytes: bytes = None
    media_type: str = "image/png"
    derivative_transform: tuple = ("NONE",)
    prompt_id: str = PROMPT_ID


@dataclass
class ProviderResult:
    raw: dict
    response_sha256: str
    provider: dict = field(default_factory=dict)


class VisionProvider(ABC):
    """Basisklasse. Een provider met `data_egress == "EXTERNAL"` mag `analyze` NIET zelf overschrijven: de basisklasse draait dan
    eerst de centrale veiligheidspoort (safety_gate.authorize_external_call) en roept pas daarna `_analyze_authorized` aan."""
    data_egress = "NONE"

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if cls.data_egress != "NONE":
            if "analyze" in cls.__dict__:
                raise TypeError(f"{cls.__name__}: een externe provider mag analyze niet overschrijven (centrale veiligheidspoort)")
            if "_analyze_authorized" not in cls.__dict__ and not any("_analyze_authorized" in b.__dict__ for b in cls.__mro__[1:]):
                raise TypeError(f"{cls.__name__}: een externe provider moet _analyze_authorized implementeren")

    @abstractmethod
    def describe(self):
        """{adapter_id, adapter_version, provider_name, data_egress}"""

    def analyze(self, request: VisionRequest) -> ProviderResult:
        """Levert een RUW antwoord {proposals:[...], hidden_element_hypotheses:[...]} (bbox_norm), nooit een besluit."""
        if self.data_egress == "NONE":
            return self._analyze_local(request)
        auth = self._authorize(request)
        return self._analyze_authorized(request, auth)

    def _analyze_local(self, request):
        raise NotImplementedError

    def _authorize(self, request):
        raise NotImplementedError


def _result(raw, info):
    return ProviderResult(copy.deepcopy(raw), canonical_sha256(raw), info)


class NullProvider(VisionProvider):
    def describe(self):
        return {"adapter_id": "null", "adapter_version": ADAPTER_VERSION, "provider_name": "null_provider", "data_egress": "NONE"}

    def _analyze_local(self, request):
        return _result({"proposals": [], "hidden_element_hypotheses": []},
                       {**self.describe(), "model_served": None, "consent_ref": None, "prompt_id": None})


class ReplayProvider(VisionProvider):
    """Speelt opgeslagen antwoorden terug, gesleuteld op derivative_sha256. Geen netwerk, leest de afbeelding niet."""

    def __init__(self, recordings):
        self._rec = copy.deepcopy(recordings)

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def describe(self):
        return {"adapter_id": "replay", "adapter_version": ADAPTER_VERSION, "provider_name": "replay", "data_egress": "NONE"}

    def _analyze_local(self, request):
        if request.derivative_sha256 not in self._rec:
            raise ProviderError("NO_RECORDING", f"geen opgenomen antwoord voor derivative_sha256 {request.derivative_sha256[:12]}...")
        return _result(self._rec[request.derivative_sha256],
                       {**self.describe(), "model_served": None, "consent_ref": None, "prompt_id": request.prompt_id})


_CANDIDATE_TYPE_MAP = {"WINDOW": "WINDOW_OPENING", "EXTERIOR_DOOR": "EXTERIOR_DOOR", "ROOF_WINDOW": "ROOF_WINDOW",
                       "UNKNOWN_OPENING": "UNKNOWN_OPENING", "DORMER_WINDOW": "DORMER_OPENING"}
_VISIBILITY_MAP = {"FULL": "FULL", "PARTIAL": "PARTIAL", "HEAVILY_OCCLUDED": "OCCLUDED", "OCCLUDED": "OCCLUDED"}


class HumanImportProvider(VisionProvider):
    """Voert bestaande handmatige annotaties in als voorstellen. Menselijke besluiten worden bewust NIET overgenomen:
    het resultaat blijft PROPOSED met human_decision = null en dient hooguit als startpunt of vergelijking."""

    def __init__(self, annotations):
        self._ann = copy.deepcopy(annotations)

    @classmethod
    def from_frame_annotation(cls, doc):
        """Leest het bestaande formaat maldenhof_*_frame_annotation_v1 (candidates met candidate_type/bbox_norm/visibility)."""
        out = []
        for c in doc["candidates"]:
            et = _CANDIDATE_TYPE_MAP.get(c["candidate_type"])
            vis = _VISIBILITY_MAP.get(c["visibility"])
            if et is None or vis is None:
                raise ProviderError("UNKNOWN_IMPORT_VALUE", f"onbekend type/zichtbaarheid in {c.get('candidate_id')}")
            u = [] if vis == "FULL" else [{"code": "OCCLUDED_BY_OBJECT", "level": "HIGH" if vis == "OCCLUDED" else "MEDIUM"}]
            out.append({"element_type": et, "bbox_norm": c["bbox_norm"], "visibility": vis, "uncertainties": u,
                        "observation": "handmatig geannoteerd element"})
        return cls(out)

    def describe(self):
        return {"adapter_id": "human_import", "adapter_version": ADAPTER_VERSION, "provider_name": "human_import", "data_egress": "NONE"}

    def _analyze_local(self, request):
        return _result({"proposals": self._ann, "hidden_element_hypotheses": []},
                       {**self.describe(), "model_served": None, "consent_ref": None, "prompt_id": None})


class ClaudeVisionConfig:
    """Alle waarden komen van de operator; er zijn bewust geen standaard modelnaam of limieten ingebouwd. Afmetings- en
    bestandslimieten komen uit het (ondertekende) toestemmingsrecord, niet uit deze configuratie."""

    def __init__(self, enabled=False, model=None, max_tokens=None):
        self.enabled, self.model, self.max_tokens = enabled, model, max_tokens


class ClaudeVisionProvider(VisionProvider):
    """Optionele Anthropic-adapter. STANDAARD UITGESCHAKELD en bovendien geblokkeerd door de centrale veiligheidspoort
    (safety_gate.py): providerregister (NOT_APPROVED), ondertekend toestemmingsrecord, inspectie van de werkelijke bytes en een
    procesoverstijgend persistent budgetgrootboek. De SDK wordt pas na de poort geimporteerd (of een `client` wordt geinjecteerd,
    bv. een mock in tests). API-sleutel: uitsluitend via de omgeving van de SDK; nooit gelogd.
    Geen tracing, geen sampling-parameters, geen thinking-/tool-opties: alleen een image- en een tekstblok."""
    data_egress = "EXTERNAL"

    def __init__(self, config=None, consent=None, client=None, ledger=None):
        self.config = config or ClaudeVisionConfig()
        self.consent, self._client, self.ledger = consent, client, ledger

    def describe(self):
        return {"adapter_id": "claude_vision", "adapter_version": ADAPTER_VERSION, "provider_name": "anthropic", "data_egress": "EXTERNAL"}

    def _authorize(self, request):
        c = self.config
        if not c.enabled:
            raise ProviderError("PROVIDER_DISABLED", "ClaudeVisionProvider is standaard uitgeschakeld")
        missing = [n for n in ("model", "max_tokens") if getattr(c, n) in (None, 0, "")]
        if missing:
            raise ProviderError("CONFIG_INCOMPLETE", "ontbrekende configuratie (geen ingebouwde standaardwaarden): " + ", ".join(missing))
        return authorize_external_call(provider="anthropic", request=request, config=c, consent=self.consent, ledger=self.ledger,
                                       prompt_sha256=PROMPT_SHA256)

    def _analyze_authorized(self, request, auth):
        try:
            client = self._client
            if client is None:
                try:
                    import anthropic
                except ImportError as ex:
                    raise ProviderError("SDK_MISSING", "de anthropic-SDK is niet geinstalleerd") from ex
                client = anthropic.Anthropic()
            require_authorization(auth, provider="anthropic", model=self.config.model, max_tokens=self.config.max_tokens,
                                  image_bytes=request.image_bytes, prompt_sha256=PROMPT_SHA256)
        except Exception:
            auth.release_unsent("PRE_SEND_FAILURE")                      # aantoonbaar niets verzonden: reservering vrijgeven
            raise
        auth.consume()
        try:
            message = _send_authorized(client, auth, request, self.config, PROMPT)
        except Exception:
            auth.settle("SEND_FAILED")                                   # onzeker of de provider iets ontving: telt als verbruikt
            raise
        tokens = getattr(getattr(message, "usage", None), "output_tokens", None)
        if getattr(message, "stop_reason", None) in ("refusal", "max_tokens"):
            auth.settle("UNUSABLE_" + str(message.stop_reason).upper(), tokens)
            raise ProviderError("UNUSABLE_RESPONSE", f"stop_reason={message.stop_reason}; geen herstel of aanvulling")
        auth.settle("OK", tokens)
        text = "".join(getattr(b, "text", "") for b in message.content if getattr(b, "type", None) == "text")
        try:
            parsed = json.loads(text)
        except ValueError as ex:
            raise ProviderError("UNUSABLE_RESPONSE", "antwoord is geen geldige JSON") from ex
        raw = _px_to_norm(parsed, request.width_px, request.height_px)
        info = {**self.describe(), "model_served": getattr(message, "model", None), "consent_ref": auth.consent_id, "prompt_id": PROMPT_ID}
        res = _result(raw, info)
        res.response_sha256 = sha256_bytes(text.encode("utf-8"))      # hash van het ruwe antwoord zoals ontvangen
        return res


def _send_authorized(client, auth, request, config, prompt):
    """De ENIGE plek in het pakket waar afbeeldingsdata naar een externe client gaat; weigert zonder geldig, ongebruikt poorttoken."""
    import base64
    if not auth._state == "SENDING":
        raise GateRefusal(["AUTHORIZATION_MISSING"])
    content = [{"type": "image", "source": {"type": "base64", "media_type": request.media_type,
                                            "data": base64.standard_b64encode(request.image_bytes).decode("ascii")}},
               {"type": "text", "text": prompt}]
    return client.messages.create(model=config.model, max_tokens=config.max_tokens, messages=[{"role": "user", "content": content}])


def _px_to_norm(parsed, w, h):
    if not isinstance(parsed, dict) or set(parsed) - {"proposals", "hidden_element_hypotheses"}:
        raise ProviderError("UNUSABLE_RESPONSE", "onverwachte structuur")
    out = {"proposals": [], "hidden_element_hypotheses": list(parsed.get("hidden_element_hypotheses", []))}
    for p in parsed.get("proposals", []):
        if not isinstance(p, dict) or "bbox_px" not in p:
            raise ProviderError("UNUSABLE_RESPONSE", "voorstel zonder bbox_px")
        q = {k: v for k, v in p.items() if k != "bbox_px"}
        b = p["bbox_px"]
        if not (isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)):
            raise ProviderError("UNUSABLE_RESPONSE", "ongeldige bbox_px")
        q["bbox_norm"] = [round(b[0] / w, 4), round(b[1] / h, 4), round(b[2] / w, 4), round(b[3] / h, 4)]
        out["proposals"].append(q)
    return out


def build_proposal_set(request, result):
    """Zet een ruw providerantwoord deterministisch om in een PhotoProposalSet. Onbekende velden, besluiten of typen in het
    ruwe antwoord leiden tot een fout (geen stille filtering). Invarianten worden hier gezet, niet door het model."""
    raw = result.raw
    if not isinstance(raw, dict) or set(raw) - {"proposals", "hidden_element_hypotheses"}:
        raise ProviderError("UNUSABLE_RESPONSE", "ruw antwoord heeft een onverwachte structuur")
    items = raw.get("proposals", [])
    for p in items:
        extra = set(p) - _RAW_PROPOSAL_KEYS
        if extra:
            raise ProviderError("UNUSABLE_RESPONSE", f"onverwachte velden in voorstel: {sorted(extra)}")
        if p.get("element_type") not in ELEMENT_TYPES:
            raise ProviderError("UNKNOWN_ELEMENT_TYPE", f"onbekend type {p.get('element_type')!r}")
        if p.get("visibility") not in VISIBILITIES:
            raise ProviderError("UNUSABLE_RESPONSE", f"onbekende zichtbaarheid {p.get('visibility')!r}")
    ordered = sorted(items, key=lambda p: (round(p["bbox_norm"][0], 4), round(p["bbox_norm"][1], 4), p["element_type"]))
    proposals = []
    for i, p in enumerate(ordered, 1):
        row = {"observation_id": f"PO-{i:03d}", "element_type": p["element_type"], "bbox_norm": [float(v) for v in p["bbox_norm"]],
               "visibility": p["visibility"], "visible_quantity": 1, "uncertainties": copy.deepcopy(p.get("uncertainties", [])),
               "observation": p.get("observation") or p.get("note") or "zichtbaar element",
               "review_status": "PROPOSED", "human_decision": None, "is_instance": False, "counts_in_any_total": False, "bag_pand_id": None}
        if "parts_visible" in p:
            row["parts_visible"] = p["parts_visible"]
        proposals.append(row)
    hyps = []
    for i, h in enumerate(raw.get("hidden_element_hypotheses", []), 1):
        extra = set(h) - _RAW_HYPOTHESIS_KEYS
        if extra or h.get("element_type") not in ELEMENT_TYPES:
            raise ProviderError("UNUSABLE_RESPONSE", "ongeldige hypothese")
        row = {"hypothesis_id": f"PH-{i:03d}", "element_type": h["element_type"], "reason": h["reason"], "visible_quantity": None,
               "counts_in_any_total": False, "hypothesis_only": True}
        if "region_hint" in h:
            row["region_hint"] = h["region_hint"]
        hyps.append(row)
    info = result.provider
    doc = {"contract_version": "photo_proposal_set_v1",
           "photo": {"photo_id": request.photo_id, "source_sha256": request.source_sha256, "derivative_sha256": request.derivative_sha256,
                     "width_px": request.width_px, "height_px": request.height_px, "derivative_transform": list(request.derivative_transform)},
           "provider": {"adapter_id": info["adapter_id"], "adapter_version": info["adapter_version"], "provider_name": info["provider_name"],
                        "model_served": info.get("model_served"), "consent_ref": info.get("consent_ref"),
                        "response_sha256": result.response_sha256, "prompt_id": info.get("prompt_id")},
           "policy": {"count_basis": "PHOTO_VISIBLE_ONLY", "is_building_total": False},
           "proposals": proposals, "hidden_element_hypotheses": hyps}
    return seal_set(doc)
