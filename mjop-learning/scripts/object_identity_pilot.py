"""Physical Object Identity Pilot v1 — voorlopige kandidaat-identiteitsverbanden tussen foto-observaties.

Hergebruikt (en vervangt niets van):
  * review-JSON (observaties OBS-*, relaties VR-*, SOC-groepen),
  * P1-kwaliteitsreview (evidence_class/evidence_basis per relatie),
  * pilotbesluitenregister (menselijke besluiten + source_ref_hash),
  * Decision Pack (ref_hash, evidence_refs, relation_semantics).

Een kandidaatverband (OIC-*) is GEEN frame instance (FI-*), geen samenvoeging, geen BAG-pandkoppeling en
geen telling. Er is bewust geen overgang naar een definitieve instance.
"""
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import register_pilot_decisions as RG  # noqa: E402

BASE = ROOT / "reports/frames/photo_review_map003_map004_v1"
REVIEW_JSON = BASE / "maldenhof_visual_photo_review_map003_map004_v1.json"
QUALITY_JSON = BASE / "maldenhof_p1_visual_quality_review_v1.json"
EVIDENCE_JSON = BASE / "p1_quality_review/p1_feature_match_evidence_v1.json"
REGISTER_JSON = BASE / "pilot_decisions/maldenhof_pilot_decision_register_v1.json"
OUT_JSON = ROOT / "reports/frames/physical_object_identity_pilot_v1.json"
OUT_MD = ROOT / "reports/frames/physical_object_identity_pilot_v1.md"
MODEL_VERSION = "physical_object_identity_candidate_v1"

STATUSES = ("CANDIDATE", "SUPPORTED_CANDIDATE", "UNRESOLVED", "REJECTED")
ANCHORS = {"UNIQUE_CONFIGURATION", "PLATE_ANCHOR"}   # onderscheidend bewijs; vorm/kleur/indeling is dat niet
SIMILARITY_ONLY = {"SAME_LAYOUT", "FEATURE_MATCH", "SEQUENCE_ORDER", "PARTIAL_OVERLAP", "OBLIQUE_VIEW", "FACADE_CONTEXT"}
BLOCKING_BASIS = {"REPETITION_RISK", "HIDDEN", "TOO_DARK"}

CONCEPTS = [
    ("PHOTO_OBSERVATION", "OBS-*", "Wat in één foto zichtbaar is. Buiten de instance-store, telt nergens."),
    ("VISUAL_OVERLAP_RELATION", "VR-*", "Visuele relatie tussen twee observaties of gevelsecties (review-JSON). FACADE_SECTION ≠ PHYSICAL_OBJECT."),
    ("PROVISIONAL_IDENTITY_LINK", "OIC-*", "NIEUW: kandidaat dat twee observaties hetzelfde fysieke object tonen. Geen instance."),
    ("APPROVED_PHYSICAL_INSTANCE", "FI-*", "Bestaat alleen in de instance-store (bevroren); wordt door deze pilot nooit aangemaakt."),
]

STATUS_MODEL = {
    "CANDIDATE": {
        "voorwaarden": "Relatie is PHYSICAL_OBJECT; observaties bestaan, verschillende foto's, bronhashes kloppen. Nog geen (voldoende) menselijk SAME of onderscheidend bewijs.",
        "beslissing_nodig": "Menselijke beoordeling van de relatie (SAME / DIFFERENT / UNDECIDABLE).",
        "toegestaan": ["bewijs verzamelen", "door mens laten beoordelen", "betere foto vragen"],
        "verboden": ["instance maken", "samenvoegen", "BAG-koppelen", "tellen", "hoeveelheid of kosten afleiden"],
    },
    "SUPPORTED_CANDIDATE": {
        "voorwaarden": "Geregistreerd menselijk SAME met kloppende source_ref_hash voor een PHYSICAL_OBJECT-relatie, evidence_class STRONG met onderscheidend anker (UNIQUE_CONFIGURATION of PLATE_ANCHOR), geen REPETITION_RISK/HIDDEN/TOO_DARK.",
        "beslissing_nodig": "Een afzonderlijk, expliciet menselijk besluit voor elke verdere stap (instance, BAG-koppeling).",
        "toegestaan": ["als kandidaat tonen in review en rapport", "extra onafhankelijke foto's zoeken", "vervolgbesluit voorbereiden"],
        "verboden": ["automatisch instance maken", "samenvoegen", "BAG-pand koppelen", "unieke telling aanpassen", "hoeveelheden/kosten afleiden", "transitief uitbreiden naar andere observaties"],
    },
    "UNRESOLVED": {
        "voorwaarden": "Menselijk besluit UNDECIDABLE (of bewijs onvoldoende/repetitief). Er wordt GEEN identiteitsverband gemaakt.",
        "beslissing_nodig": "Betere foto of nieuw menselijk besluit.",
        "toegestaan": ["bewaren als open vraag", "betere foto aanvragen"],
        "verboden": ["identiteit afleiden uit gelijkenis", "samenvoegen", "tellen", "BAG-koppelen"],
    },
    "REJECTED": {
        "voorwaarden": "Menselijk besluit DIFFERENT, of de relatie is geen objectrelatie (gevelsectie) of botst met de regels (zelfde foto).",
        "beslissing_nodig": "Geen; herbeoordeling kan alleen met nieuw bewijs en nieuw besluit.",
        "toegestaan": ["vastleggen waarom afgewezen"],
        "verboden": ["alsnog samenvoegen", "als kandidaat blijven tonen"],
    },
}
TRANSITIONS = {
    "(geen)": ["CANDIDATE", "UNRESOLVED", "REJECTED", "SUPPORTED_CANDIDATE"],
    "CANDIDATE": ["SUPPORTED_CANDIDATE", "UNRESOLVED", "REJECTED"],
    "SUPPORTED_CANDIDATE": ["UNRESOLVED", "REJECTED"],
    "UNRESOLVED": ["CANDIDATE", "REJECTED"],
    "REJECTED": [],
    "NOOIT_AUTOMATISCH": "Geen enkele overgang leidt naar een definitieve fysieke instance; die stap bestaat in deze pilot niet.",
}

NEVER = {"is_instance": False, "counts_in_any_total": False, "merged": False, "bag_pand_id": None, "same_physical_frame_proven": False,
         "frame_instance_id": None, "quantity": None, "cost": None}


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_context():
    """Alle gebruikte brondata; als gewone dict zodat tests er synthetische varianten van kunnen maken."""
    review, quality, evidence, register = _load(REVIEW_JSON), _load(QUALITY_JSON), _load(EVIDENCE_JSON), _load(REGISTER_JSON)
    pack = RG.load_pack()
    return {
        "observations": {o["obs_id"]: o for o in review["observations"]},
        "relations": {r["rel_id"]: r for r in review["relations"]},
        "quality": {r["review_id"]: r for r in quality["records"]},
        "feature": {r["relation_id"]: r for r in evidence["relations"]},
        "decisions": {d["review_id"]: d for d in register["decisions"]},
        "pack": {i["review_id"]: i for i in pack["items"]},
        "photo_sha": {s["photo_id"]: s["sha256_register"] for s in review["sources"]},
        "register_provenance": register["approval"],
    }


def _result(status, relation_id, reasons, **kw):
    return {"relation_id": relation_id, "identity_status": status, "creates_identity_link": False, "reasons": reasons, **kw}


def evaluate_relation(ctx, rid, decision_override=None):
    """Beoordeelt één relatie. Geeft een kandidaatverband (alleen CANDIDATE/SUPPORTED_CANDIDATE) of een weigering."""
    rel = ctx["relations"].get(rid)
    if rel is None:
        return _result("REJECTED", rid, ["ONBEKENDE_RELATIE"])
    review_id = "RV-REL-" + rid
    item, qual = ctx["pack"].get(review_id), ctx["quality"].get(review_id)
    reasons = []
    if item is None or qual is None:
        return _result("REJECTED", rid, ["ONTBREKENDE_BRONVERWIJZING_PACK_OF_KWALITEITSREVIEW"])
    if item["relation_semantics"]["relation_type"] != "PHYSICAL_OBJECT":
        return _result("REJECTED", rid, ["GEVELSECTIE_IS_GEEN_FYSIEK_OBJECT: SAME_FACADE_SECTION kan geen objectidentiteit worden"],
                       relation_type=item["relation_semantics"]["relation_type"], human_decision=(ctx["decisions"].get(review_id) or {}).get("decision"))
    ends = [rel["left"], rel["right"]]
    obs = []
    for e in ends:
        oid = e.split(":", 1)[1] if ":" in e else e
        o = ctx["observations"].get(oid)
        if o is None:
            return _result("REJECTED", rid, [f"ONBEKENDE_OBSERVATIE {oid}"])
        if ctx["photo_sha"].get(o["photo_id"]) != o["source_sha256"]:
            return _result("REJECTED", rid, [f"BRONHASH_KLOPT_NIET {oid}"])
        obs.append(o)
    if obs[0]["photo_id"] == obs[1]["photo_id"]:
        return _result("REJECTED", rid, ["ZELFDE_FOTO: twee observaties in één foto zijn verschillende openingen"])
    if item["ref_hash"] != ctx["decisions"].get(review_id, {}).get("source_ref_hash", item["ref_hash"]):
        return _result("REJECTED", rid, ["BESLUIT_HASH_KLOPT_NIET_MET_PACK"])
    dec = ctx["decisions"].get(review_id)
    d = decision_override if decision_override is not None else (dec["decision"] if dec else None)
    basis = set(qual["evidence_basis"])
    strong = qual["evidence_class"] == "STRONG_VISUAL_SUPPORT"
    anchored = bool(basis & ANCHORS)
    blockers = sorted(basis & BLOCKING_BASIS)
    base = {"relation_type": "PHYSICAL_OBJECT", "evidence_class": qual["evidence_class"], "evidence_basis": sorted(basis), "human_decision": d}
    if d == "DIFFERENT":
        return _result("REJECTED", rid, ["MENSELIJK_BESLUIT_DIFFERENT"], **base)
    if d == "UNDECIDABLE":
        return _result("UNRESOLVED", rid, ["MENSELIJK_BESLUIT_UNDECIDABLE: geen identiteit afleiden uit gelijkenis"] + [f"BEWIJSBLOKKADE {b}" for b in blockers], **base)
    if blockers or not strong or not anchored:
        why = [f"BEWIJSBLOKKADE {b}" for b in blockers]
        if not anchored:
            why.append("GEEN_ONDERSCHEIDEND_ANKER: vorm/kleur/indeling/feature-match alleen is onvoldoende")
        if not strong:
            why.append("BEWIJS_NIET_STERK")
        if blockers:   # repetitie/verborgen/te donker: ook een SAME-besluit maakt hier geen identiteitsverband
            return _result("UNRESOLVED", rid, why + ["BEWIJSBLOKKADE: geen identiteitsverband, ook niet bij SAME"], **base)
        if d == "SAME":
            return {**_result("CANDIDATE", rid, why + ["SAME zonder voldoende bewijs: hooguit kandidaat, nooit SUPPORTED"], **base), "creates_identity_link": True,
                    "_obs": obs, "_decision": dec}
        return _result("CANDIDATE", rid, why or ["GEEN_MENSELIJK_BESLUIT"], **base)
    if d == "SAME":
        return {**_result("SUPPORTED_CANDIDATE", rid, ["MENSELIJK_SAME + STERK BEWIJS + ONDERSCHEIDEND ANKER"], **base), "creates_identity_link": True,
                "_obs": obs, "_decision": dec}
    return {**_result("CANDIDATE", rid, ["GEEN_MENSELIJK_BESLUIT: alleen visueel bewijs"], **base), "creates_identity_link": True, "_obs": obs, "_decision": dec}


UNRESOLVED_VR027 = [
    "Bewijst de visuele combinatie (stickers, merktekens, gordijn) het fysieke object, of staan er identieke woningen met dezelfde inrichting? Alleen een derde onafhankelijke foto of een unieke afwijking kan dat beslissen.",
    "Beide observaties liggen in dezelfde gevelreeks (SOC-002); die groep is een foto-niveau-kandidaat (confidence MEDIUM), geen bewijs voor het kozijn.",
    "Geen van beide observaties heeft een bewezen pand (pand_status NOT_PROVEN); een objectidentiteit zegt niets over het BAG-pand.",
    "De bronrelatie noemt sterkte MEDIUM, de kwaliteitsreview STRONG_VISUAL_SUPPORT; het verschil is niet menselijk opgelost.",
    "De pilot-SAME is bevestigd via ChatGPT, niet via het HTML-formulier; er is geen instance-besluit gegeven.",
]


def to_candidate(ctx, ev):
    rid = ev["relation_id"]
    rel, review_id = ctx["relations"][rid], "RV-REL-" + rid
    item, qual, dec, obs = ctx["pack"][review_id], ctx["quality"][review_id], ev["_decision"], ev["_obs"]
    fm = ctx["feature"].get(rid)
    evrefs = [dict(e) for e in item["evidence_refs"]]
    if fm:
        evrefs.append({"type": "feature_match_support_only", "inliers": fm["inliers"], "good_matches": fm["good_matches"], "best_other_inliers_row": fm["best_other_inliers_row"],
                       "best_other_inliers_col": fm["best_other_inliers_col"], "note": "SIFT/RANSAC is alleen ondersteunend: niet-partners halen tot 24 inliers."})
    return {
        "candidate_group_id": "OIC-" + rid, "kind": "PROVISIONAL_IDENTITY_LINK", "identity_status": ev["identity_status"],
        "observation_ids": [o["obs_id"] for o in obs], "photo_ids": [o["photo_id"] for o in obs],
        "supporting_relation_ids": [rid], "relation_class": rel["class"], "relation_strength_in_source": rel["strength"],
        "evidence_class": qual["evidence_class"], "evidence_basis": sorted(qual["evidence_basis"]), "evidence_strength": qual["evidence_class"],
        "evidence_refs": evrefs,
        "decision_refs": [{"review_id": dec["review_id"], "decision": dec["decision"], "decision_label": dec["decision_label"], "source_ref_hash": dec["source_ref_hash"],
                           "register": REGISTER_JSON.name, "decision_source": dec["provenance"]["decision_source"], "approval_channel": dec["provenance"]["approval_channel"],
                           "meaning": "SAME_PHYSICAL_OBJECT_CANDIDATE: kandidaat, niet bewezen, niet samengevoegd"}] if dec else [],
        "source_hashes": {o["photo_id"]: o["source_sha256"] for o in obs},
        "unresolved_questions": UNRESOLVED_VR027 if rid == "VR-027" else ["Nog niet beoordeeld in deze pilot."],
        "reasons": ev["reasons"], **NEVER,
    }


def resolve_groups(pair_candidates):
    """Niet-transitief: een groep van >2 observaties bestaat alleen als ELK paar direct ondersteund is (clique).
    Anders blijven de paren los en wordt de keten als UNRESOLVED_CHAIN gemeld; er wordt niets afgeleid."""
    pairs = {frozenset(c["observation_ids"]) for c in pair_candidates if c["identity_status"] == "SUPPORTED_CANDIDATE"}
    adj = {}
    for p in pairs:
        a, b = tuple(p)
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen, groups, chains = set(), [], []
    for start in sorted(adj):
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(adj[n] - comp)
        seen |= comp
        members = sorted(comp)
        missing = [sorted(p) for p in combinations(members, 2) if frozenset(p) not in pairs]
        if len(members) == 2:
            groups.append(members)
        elif not missing:
            groups.append(members)
        else:
            chains.append({"observation_ids": members, "status": "UNRESOLVED_CHAIN", "missing_direct_pairs": missing, "transitive_merge_performed": False})
    return {"groups": groups, "chains": chains, "pairs_kept_separate": sorted(sorted(p) for p in pairs) if chains else []}


def build_report():
    ctx = load_context()
    ev27 = evaluate_relation(ctx, "VR-027")
    cand = to_candidate(ctx, ev27)
    controls = []

    def ctl(code, title, rid, expect, override=None, note=None):
        r = evaluate_relation(ctx, rid, override)
        passed = (not r["creates_identity_link"]) if expect == "NO_LINK" else (r["identity_status"] != "SUPPORTED_CANDIDATE")
        controls.append({"control": code, "title": title, "relation_id": rid, "human_decision": ctx["decisions"].get("RV-REL-" + rid, {}).get("decision"),
                         "assumed_decision_hypothetical": override,
                         "result_status": r["identity_status"], "creates_identity_link": r["creates_identity_link"], "reasons": r["reasons"], "passed": bool(passed), "note": note})

    ctl("A", "Gevelsectie is geen fysiek kozijn", "VR-020", "NO_LINK")
    ctl("B", "Onvoldoende bewijs (UNDECIDABLE)", "VR-026", "NO_LINK")
    ctl("C", "Matig bewijs (UNDECIDABLE)", "VR-024", "NO_LINK")
    ctl("C2", "Hypothetisch: VR-024 met SAME maakt nog geen identiteitsverband", "VR-024", "NO_LINK", override="SAME",
        note="Met REPETITION_RISK en zonder onderscheidend anker volstaat zelfs een SAME-besluit niet.")
    ctl("D1", "Repeterende woningen, te donker (VR-022), hypothetisch SAME", "VR-022", "NO_LINK", override="SAME")
    ctl("D2", "Groepseindpunt met herhaling (VR-044) wordt geweigerd, ook bij hypothetisch SAME", "VR-044", "NO_LINK", override="SAME")
    ctl("D3", "Alleen gelijke indeling/feature-match: VR-025", "VR-025", "NOT_SUPPORTED", override="SAME")
    # E: A~B, B~C, A en C niet vergelijkbaar
    mk = lambda a, b: {"observation_ids": [a, b], "identity_status": "SUPPORTED_CANDIDATE"}
    chain = resolve_groups([mk("A", "B"), mk("B", "C")])
    clique = resolve_groups([mk("A", "B"), mk("B", "C"), mk("A", "C")])
    controls.append({"control": "E", "title": "Niet-transitief A~B, B~C, A≁C", "result": chain, "passed": chain["groups"] == [] and len(chain["chains"]) == 1
                     and chain["chains"][0]["missing_direct_pairs"] == [["A", "C"]], "note": "Geen groep van drie; keten blijft UNRESOLVED_CHAIN."})
    controls.append({"control": "E2", "title": "Alleen volledig ondersteunde clique A,B,C wordt één kandidaatgroep", "result": clique,
                     "passed": clique["groups"] == [["A", "B", "C"]] and clique["chains"] == []})
    own = [o for o in ctx["observations"].values() if o["photo_id"] == "MAP-003"][:2]
    synth = dict(ctx)
    synth["relations"] = dict(ctx["relations"], **{"VR-SELF": {"rel_id": "VR-SELF", "left": "MAP-003:" + own[0]["obs_id"], "right": "MAP-003:" + own[1]["obs_id"], "class": "POSSIBLY_SAME_PHYSICAL_FRAME", "strength": "MEDIUM"}})
    synth["pack"] = dict(ctx["pack"], **{"RV-REL-VR-SELF": ctx["pack"]["RV-REL-VR-027"]})
    synth["quality"] = dict(ctx["quality"], **{"RV-REL-VR-SELF": ctx["quality"]["RV-REL-VR-027"]})
    rs = evaluate_relation(synth, "VR-SELF", "SAME")
    controls.append({"control": "F", "title": "Twee observaties in dezelfde foto kunnen nooit hetzelfde object zijn", "relation_id": "VR-SELF (synthetisch)", "result_status": rs["identity_status"],
                     "creates_identity_link": rs["creates_identity_link"], "reasons": rs["reasons"], "passed": not rs["creates_identity_link"]})
    other = {r: ctx["feature"][r]["inliers"] for r in ("VR-027",)}
    return {
        "model_version": MODEL_VERSION, "status": "PILOT_PROPOSAL_NO_INSTANCE_ACTIVATION",
        "concepts": [{"name": n, "id_pattern": p, "meaning": m} for n, p, m in CONCEPTS],
        "status_model": STATUS_MODEL, "transitions": TRANSITIONS,
        "candidates": [cand], "negative_controls": controls,
        "repetition_risk": {"feature_match_vr027_inliers": other["VR-027"], "best_non_partner_inliers_vr027": ctx["feature"]["VR-027"]["best_other_inliers_col"],
                            "note": "Niet-partners halen tot 24 inliers: gelijkenis tussen buurwoningen is meetbaar hoog. Feature-match is alleen ondersteunend."},
        "inputs": {"review_json_sha256": sha(REVIEW_JSON), "quality_json_sha256": sha(QUALITY_JSON), "register_sha256": sha(REGISTER_JSON), "evidence_json_sha256": sha(EVIDENCE_JSON),
                   "register_provenance": ctx["register_provenance"]["channel"]},
        "effects": {"instances_created": 0, "bag_links_created": 0, "merges": 0, "building_totals": None, "quantities": None, "costs": None,
                    "new_observations": 0, "human_decisions_changed": 0, "app_decisions_changed": 0, "photo2_changed": False, "definitive_instance_transition_exists": False},
        "stop": "Stop vóór het activeren van een definitieve fysieke instance of het mergen van PR #42.",
    }


def render_md(rep, ctx):
    c = rep["candidates"][0]
    o = [ctx["observations"][i] for i in c["observation_ids"]]
    L = ["# Physical Object Identity Pilot v1", "",
         "Status: **voorstel/pilot**. Er is geen instance, samenvoeging, BAG-koppeling, telling, hoeveelheid of kostenpost aangemaakt. "
         "Dit rapport en `physical_object_identity_pilot_v1.json` worden gegenereerd door `scripts/object_identity_pilot.py` (deterministisch).", "",
         "## 1. Gegevensmodel (hergebruik, geen tweede model)", "",
         "Bestaand en hergebruikt: observaties `OBS-*` en relaties `VR-*` (review-JSON), `SOC-*` (foto-niveau kandidaatgroepen uit de fotoarchief-audit), "
         "evidence_class/evidence_basis (P1-kwaliteitsreview), menselijke pilotbesluiten (register) en `FI-*` frame instances (bevroren store, onaangeroerd). "
         "`component_repeat_groups_v1.json` (herhaalde elementen) is een ander concept en blijft leeg.", "",
         "Wat ontbrak: een observatie-niveau-verband dat relatie, bewijs en menselijk besluit samenbrengt zonder instance te zijn. Dat is het enige nieuwe concept: `OIC-*`.", "",
         "| Concept | ID | Betekenis |", "|---|---|---|"]
    L += [f"| {x['name']} | `{x['id_pattern']}` | {x['meaning']} |" for x in rep["concepts"]]
    L += ["", "Velden van een kandidaatverband: `candidate_group_id`, `observation_ids`, `photo_ids`, `supporting_relation_ids`, `evidence_refs`, `evidence_strength`, `evidence_basis`, "
          "`decision_refs`, `identity_status`, `unresolved_questions`, `source_hashes`, en vaste vlaggen `is_instance=false`, `merged=false`, `counts_in_any_total=false`, "
          "`bag_pand_id=null`, `same_physical_frame_proven=false`, `frame_instance_id=null`.", "",
          "## 2. Onderzochte relatie VR-027", "",
          f"- Klasse in de bron: `{c['relation_class']}`, sterkte in de bron: {c['relation_strength_in_source']} (kwaliteitsreview: {c['evidence_class']}).",
          f"- Basis: {ctx['relations']['VR-027']['basis']}", "",
          "## 3. Relevante foto-observaties", "", "| Observatie | Foto | Bestand | Uitsnede (px) | Zichtbaarheid | Onzekerheid | Pand |", "|---|---|---|---|---|---|---|"]
    L += [f"| {x['obs_id']} | {x['photo_id']} | {x['source_file']} | {x['bbox_px']} | {x['visibility']} | {x['uncertainty']} | {x['pand_status']} |" for x in o]
    fm = rep["repetition_risk"]
    L += ["", "## 4. Exacte bewijsverwijzingen", "",
          *[f"- Foto {k}: sha256 `{v}`" for k, v in c["source_hashes"].items()],
          f"- Bewijsbasis: {', '.join(c['evidence_basis'])}. Visueel overzicht: `p1_quality_review/QREL-sheet-2.jpg` en `C1_MAP-003_vs_MAP-004_upper_facade.jpg` (map `photo_review_map003_map004_v1`).",
          f"- Kenmerkmatch (alleen ondersteunend): {fm['feature_match_vr027_inliers']} inliers; beste niet-partner: {fm['best_non_partner_inliers_vr027']} inliers.",
          "- Besluit: `RV-REL-VR-027` = SAME, bevestigd door de gebruiker via ChatGPT (niet via het HTML-formulier), source_ref_hash `b4c272b4bf256bba`, "
          "betekenis `SAME_PHYSICAL_OBJECT_CANDIDATE`: kandidaat, niet bewezen, niet samengevoegd.", "",
          "## 5. Voorlopige identiteitsstatus", "",
          f"`{c['candidate_group_id']}`: **{c['identity_status']}** (observaties {', '.join(c['observation_ids'])}). Dit is een kandidaat, geen instance en geen telling.", "",
          "Onzekerheden die blijven:"] + [f"- {q}" for q in c["unresolved_questions"]]
    L += ["", "## 6. Negatieve controles", "", "| Controle | Relatie | Menselijk besluit | Uitkomst | Identiteitsverband? | Geslaagd |", "|---|---|---|---|---|---|"]
    for k in rep["negative_controls"]:
        if "result_status" in k:
            L.append(f"| {k['control']} {k['title']} | {k['relation_id']} | {k.get('human_decision') or '-'}{' (hypothetisch: ' + k['assumed_decision_hypothetical'] + ')' if k.get('assumed_decision_hypothetical') else ''} | {k['result_status']} | {'ja (kandidaat)' if k['creates_identity_link'] else 'nee'} | {'ja' if k['passed'] else 'NEE'} |")
        else:
            L.append(f"| {k['control']} {k['title']} | synthetisch | - | groepen {k['result']['groups']}, ketens {len(k['result']['chains'])} | n.v.t. | {'ja' if k['passed'] else 'NEE'} |")
    L += ["", "Toelichting: VR-020 heeft SAME maar alleen als `SAME_FACADE_SECTION`; VR-024 en VR-026 zijn UNDECIDABLE; zonder onderscheidend anker (UNIQUE_CONFIGURATION of PLATE_ANCHOR) "
          "of met REPETITION_RISK/HIDDEN/TOO_DARK ontstaat geen identiteitsverband, ook niet bij een hypothetisch SAME. Relaties met groepseindpunten of foto-2-ID's (FC-M2/FI-M2) worden geweigerd. "
          "Identiteit is niet-transitief: een groep van meer dan twee observaties bestaat alleen als elk paar direct ondersteund is.", "",
          "## 7. Risico bij identieke naastgelegen woningen", "",
          f"De Maldenhof-woningen zijn grotendeels identiek. Niet-partners halen tot {fm['best_non_partner_inliers_vr027']} inliers (partner: {fm['feature_match_vr027_inliers']}). "
          "Vorm, kleur, raamindeling en feature-match bewijzen daarom nooit identiteit; alleen een uniek anker (hier de combinatie stickers/merktekens/gordijn) of een leesbare plaat doet dat, "
          "en dan nog uitsluitend als kandidaat.", "",
          "## 8. Ontbrekend voor een definitieve instance", "",
          "- Een afzonderlijk menselijk besluit om het kandidaatverband als fysieke instance te activeren (bestaat niet en wordt niet voorgesteld door deze pilot).",
          "- Een tweede onafhankelijke foto/hoek of unieke afwijking die buurwoningen uitsluit.",
          "- Een leesbaar huisnummer/plaat of ander bewijs voor het pand (BAG-koppeling is een aparte stap).",
          "- Beslissing over de relatie met de 48 OPEN APP-besluiten, tel- en hoeveelheidsregels.", "",
          "## 9. Statusmodel", ""]
    for st, m in rep["status_model"].items():
        L += [f"### {st}", f"- Voorwaarden: {m['voorwaarden']}", f"- Beslissing nodig: {m['beslissing_nodig']}", f"- Toegestaan: {'; '.join(m['toegestaan'])}", f"- Verboden: {'; '.join(m['verboden'])}", ""]
    L += ["Overgangen: " + "; ".join(f"{a} → {', '.join(b) if b else '(eindstatus)'}" for a, b in rep["transitions"].items() if a != "NOOIT_AUTOMATISCH"), "", rep["transitions"]["NOOIT_AUTOMATISCH"], "",
          "## 10. Aanbeveling voor de volgende stap", "",
          "Laat de gebruiker beoordelen of OIC-VR-027 als kandidaat blijft staan, en vraag een tweede onafhankelijke foto of detail van dit kozijn. "
          "Pas daarna kan een afzonderlijk besluit over instance-activatie worden voorbereid. Pas het model niet op andere relaties toe voordat dit besluit er is."]
    return "\n".join(L) + "\n"


def main():
    rep = build_report()
    OUT_JSON.write_text(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(rep, load_context()), encoding="utf-8")
    print("OIC:", [c["candidate_group_id"] + ":" + c["identity_status"] for c in rep["candidates"]], "controles:", [(c["control"], c["passed"]) for c in rep["negative_controls"]])


if __name__ == "__main__":
    main()
