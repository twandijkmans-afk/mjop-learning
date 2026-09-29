#!/usr/bin/env python3
"""
comparability_review_v2.py - reviewpakket v2: van losse paren naar reviewfamilies (alleen lezen).

Invoer (alleen lezen): comparability, genormaliseerde price observations, de human decision store,
document_relations.json, relation_proposals.json, kengetallen, verified-elementen en vocabularies.
Uitvoer (deterministisch, geen tijdstempels):
    reports/review/comparability_review_v2.json   machineleesbaar
    reports/review/comparability_review_v2.md     menselijk leesbaar overzicht

1. REVIEWQUEUE: exact de selectie van queue v1 (export_human_review_queue.select_pairs).

2. REVIEWFAMILIES: paren worden alleen samengevoegd als ze EXACT dezelfde reviewvraag stellen. Sleutel:
   - candidate key (elementcode, genormaliseerde actie, genormaliseerde eenheid);
   - per kant: objectomschrijving en actietekst als woordtokens ZONDER de vaste, goedgekeurde gevelzijde-woorden
     (build_kengetallen.FACADE_SIDE_WORDS; verder geen enkele tekstnormalisatie), eenheid zoals in de bron,
     materiaal (waarde + bron uit comparability F8) en de inhoudelijke observation-caveats;
   - of de gevelzijde-woorden verschillen, of er een QUANTITY_SCALE_DIFFERENCE is en of er een relatierisico is.
   Alleen document, source cluster, hoeveelheid, prijs en prijspeil mogen binnen een familie verschillen; die
   staan per paar in het pakket. Geen fuzzy matching, geen score, geen confidence, geen rangschikking.

3. BEWIJSCATEGORIE per familie (uit bestaande velden, in deze volgorde):
     SOURCE_RELATION_RISK        de documenten hebben een (voorgestelde) relatie of afhankelijkheid
     UNIT_DIFFERENCE             eenheid in de bron verschilt
     OTHER_REVIEW_REQUIRED       inhoudelijke observation-caveat (UPGRADE, COMBINED_EXECUTION, PARTIAL_SCOPE, ...)
     OBJECT_TEXT_VARIANT         objectomschrijving verschilt (GENERIC_VS_SPECIFIC_OBJECT)
     ACTION_TEXT_VARIANT         actietekst verschilt (ook: alleen gevelzijde-woorden)
     MATERIAL_DIFFERENCE_ONLY    beide materialen bekend en verschillend, verder gelijk
     MATERIAL_EVIDENCE_ONE_SIDE  alleen één kant heeft een vastgesteld materiaal, verder gelijk
     QUANTITY_SCALE_DIFFERENCE   verder gelijk, hoeveelheden verschillen sterk
     EXACT_SAME_SEMANTIC_INPUT   objectomschrijving, actietekst, eenheid en materiaal gelijk

4. KANDIDAATGROEPEN: per candidate key alle observations, clusters, materiaalbewijs en de concrete
   beslissingen die nog ontbreken voordat een groep volgens docs/kengetallen_rules_v1.md een kengetal kan zijn.
   Er wordt GEEN kengetal berekend en er worden GEEN beslissingen aangemaakt.

Het materiaal 'volgens de bestaande tekstregel' (normalize_price_observations.normalize_material) wordt alleen
als BEWIJS getoond voor documenten buiten de goedgekeurde MATERIAL_FROM_TEXT-scope; het wordt niet toegepast.

    python scripts/comparability_review_v2.py [--check]
"""
import argparse
import copy
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import build_kengetallen as bk  # noqa: E402
import export_human_review_queue as hrq  # noqa: E402
import normalize_price_observations as npo  # noqa: E402
import promotion_ledger as pl  # noqa: E402

REVIEW_VERSION = "comparability_review_v2"
OUT_JSON = os.path.join("reports", "review", "comparability_review_v2.json")
OUT_MD = os.path.join("reports", "review", "comparability_review_v2.md")
COMP = os.path.join("data", "comparability", "comparability_batch1.json")
NORM = os.path.join("data", "price_observations", "price_observations_batch1_normalized.json")
SOURCE = os.path.join("data", "price_observations", "price_observations_batch1.json")
STORE = os.path.join("data", "review_decisions", "human_decision_records.json")
RELATIONS = os.path.join("data", "price_observations", "document_relations.json")
PROPOSALS = os.path.join("data", "price_observations", "relation_proposals.json")
KG = os.path.join("data", "kengetallen", "kengetallen_batch1.json")

# inhoudelijke observation-caveats (comparability O-regels); MATERIAL_UNKNOWN, PRICE_LEVEL_ABSENT en
# CODE_LABEL_MISMATCH zijn documentcontext en staan per paar
SEMANTIC_OBSERVATION_CAVEATS = ("UPGRADE", "COMBINED_EXECUTION", "PARTIAL_SCOPE", "FRACTIONAL_PIECE_COUNT",
                                "MIXED_MATERIAL")
CATEGORY_ORDER = ("SOURCE_RELATION_RISK", "UNIT_DIFFERENCE", "OTHER_REVIEW_REQUIRED", "OBJECT_TEXT_VARIANT",
                  "ACTION_TEXT_VARIANT", "MATERIAL_DIFFERENCE_ONLY", "MATERIAL_EVIDENCE_ONE_SIDE",
                  "QUANTITY_SCALE_DIFFERENCE", "EXACT_SAME_SEMANTIC_INPUT")
# prioriteit van de gebruiker; daarna de overige groepen met >= 3 clusters in deze volgorde
PRIORITY_GROUPS = [("4645", "exterior_painting", "m2"), ("5211", "replace", "m1")]
FOCUS_GROUPS = PRIORITY_GROUPS + [("4621", "exterior_painting", "m2"), ("4622", "interior_painting", "m2"),
                                  ("4631", "exterior_painting", "m2"), ("4711", "replace", "m1"),
                                  ("4628", "exterior_painting", "m2"), ("4634", "exterior_painting", "m2"),
                                  ("6311", "replace", "piece")]
DETAILED_GROUPS = PRIORITY_GROUPS
CHOICES = {
    "COMPARABLE": "Vergelijkbaar zonder voorbehoud.",
    "COMPARABLE_WITH_CAVEATS": "Vergelijkbaar, met de gekozen voorbehouden (decision_caveats).",
    "NOT_COMPARABLE": "Niet vergelijkbaar.",
    "UNKNOWN": "Niet te beoordelen met het beschikbare bewijs.",
}


def sha256_file(path):
    return hrq.sha256_file(path)


def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def load(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return json.load(f)


def key_str(key):
    return "|".join(str(k) for k in key)


def text_tokens(text):
    return [t for t in bk.tokens(text) if t not in bk.FACADE_SIDE_WORDS]


def facade_words(text):
    return sorted({t for t in bk.tokens(text) if t in bk.FACADE_SIDE_WORDS})


def primary(norm_obs):
    return bk.primary_repr(norm_obs)


# ------------------------------------------------------------------ context

class Context:
    def __init__(self, root):
        self.root = root
        self.comp = load(root, COMP)
        self.norm = {o["observation_id"]: o for o in load(root, NORM)["observations"]}
        self.source = {o["observation_id"]: o for o in load(root, SOURCE)["observations"]}
        self.assess = {a["observation_id"]: a for a in self.comp["observations"]}
        self.store = load(root, STORE)
        self.relations = load(root, RELATIONS)["relations"]
        self.proposals = load(root, PROPOSALS)["proposals"] if os.path.exists(os.path.join(root, PROPOSALS)) else []
        self.kg = load(root, KG)
        self.pairs = {p["pair_id"]: p for p in self.comp["pairs"]}
        self.pair_by_set = {frozenset(p["observation_ids"]): p for p in self.comp["pairs"]}
        self.records = defaultdict(list)
        for r in self.store["records"]:
            self.records[frozenset(r["observation_ids"])].append(r)
        self.promoted_docs = set(pl.promoted_document_ids(root))
        vdir = os.path.join(root, "data", "verified")
        self.verified_elements = {e["element_id"]: e for name in sorted(os.listdir(vdir)) if name.endswith(".json")
                                  for e in load(root, os.path.join("data", "verified", name))["elements"]}
        self.material_vocab = npo.load_vocab_utf8(os.path.join(root, "vocabularies"), "material")

    def inputs(self):
        return {"comparability_sha256": sha256_file(os.path.join(self.root, COMP)),
                "normalized_observations_sha256": sha256_file(os.path.join(self.root, NORM)),
                "human_decisions_sha256": sha256_file(os.path.join(self.root, STORE)),
                "document_relations_sha256": sha256_file(os.path.join(self.root, RELATIONS)),
                "kengetallen_sha256": sha256_file(os.path.join(self.root, KG)),
                "comparability_rules_version": self.comp["rules_version"],
                "kengetallen_rules_version": bk.RULES_VERSION}

    # -------------------------------------------------------------- per observation

    def material(self, oid):
        m = self.assess[oid].get("material") or {}
        return {"value": m.get("normalized") or m.get("original"), "source": m.get("source")}

    def material_text_evidence(self, oid):
        """Wat de BESTAANDE tekstregel zou afleiden als het document in de goedgekeurde scope viel.
        Alleen bewijs voor de reviewer; wordt niet toegepast."""
        if self.material(oid)["value"]:
            return None
        obs = self.source[oid]
        saved = npo.MATERIAL_FROM_TEXT_DOCUMENTS
        npo.MATERIAL_FROM_TEXT_DOCUMENTS = saved | {obs["document_id"]}
        try:
            r = npo.normalize_material(obs, self.verified_elements, self.material_vocab)
        finally:
            npo.MATERIAL_FROM_TEXT_DOCUMENTS = saved
        mft = r.get("material_from_text") or {}
        return {"rule": "normalize_price_observations.normalize_material (tekstregel, NIET toegepast)",
                "document_in_approved_scope": obs["document_id"] in saved,
                "would_derive": mft.get("normalized_value"), "token": mft.get("original_value"),
                "not_derived_reason": r.get("material_not_derived_reason") if not mft else None}

    def side_signature(self, oid):
        n, a = self.norm[oid], self.assess[oid]
        m = self.material(oid)
        return {"element_description": " ".join(text_tokens(n["element"]["element_description_original"])),
                "action_text": " ".join(text_tokens(n["action"]["action_text_original"])),
                "unit_original": n["unit"]["unit_original"],
                "material": m["value"], "material_source": m["source"],
                "semantic_caveats": sorted(set(a["caveats"]) & set(SEMANTIC_OBSERVATION_CAVEATS))}

    def observation_view(self, oid):
        n, a = self.norm[oid], self.assess[oid]
        p = primary(n)
        d = a["derived_unit_price_per_execution"] or {}
        return {"observation_id": oid, "document_id": n["document_id"], "source_cluster": a["source_cluster"],
                "new_in_testbatch01": n["document_id"] in self.promoted_docs,
                "page": p.get("page"), "line": p.get("line"), "sheet": p.get("sheet"), "row": p.get("row"),
                "source_text": p.get("source_text"),
                "object_description": n["element"]["element_description_original"],
                "action_text": n["action"]["action_text_original"],
                "quantity": n["price"]["quantity_value"], "unit_original": n["unit"]["unit_original"],
                "derived_price_per_execution": d.get("value"), "executions_in_window": d.get("executions_in_window"),
                "price_level_date": n["price"]["price_level_date"], "vat_basis": n["price"]["vat_basis"],
                "material": self.material(oid), "material_text_evidence": self.material_text_evidence(oid),
                "eligibility": a["eligibility"], "independent_input": a["independent_input"],
                "independent_input_exclusion_reasons": a["independent_input_exclusion_reasons"],
                "dependency_status": a["dependency_status"], "caveats": a["caveats"]}

    # -------------------------------------------------------------- per paar

    def relation_risk(self, pair):
        docs = {self.norm[i]["document_id"] for i in pair["observation_ids"]}
        out = []
        for r in self.relations:
            members = set(r.get("document_ids", [])) | {r.get("primary_document_id"), r.get("secondary_document_id")}
            if docs <= members:
                out.append(f"{r['relation_id']}:{r['type']}")
        for p in self.proposals:
            if docs <= set(p.get("document_ids", [])):
                out.append(f"PROPOSAL:{p.get('kind')}")
        for i in pair["observation_ids"]:
            if self.assess[i]["dependency_status"] == "POSSIBLY_DEPENDENT":
                out.append(f"POSSIBLY_DEPENDENT:{i}")
        return sorted(out)

    def existing_records(self, pair):
        return [{"decision_id": r["decision_id"], "status": r["status"], "decision": r["decision"],
                 "reviewed_at": r["reviewed_at"], "supersedes": r["supersedes"]}
                for r in sorted(self.records.get(frozenset(pair["observation_ids"]), []),
                                key=lambda r: r["decision_id"])]

    def pair_status(self, pair):
        recs = self.records.get(frozenset(pair["observation_ids"]), [])
        if any(r["status"] == "ACTIVE" for r in recs):
            return "ACTIVE_DECISION"
        if recs:
            return "PREVIOUS_DECISION_REVIEW_REQUIRED"
        return "NO_DECISION"


# ------------------------------------------------------------------ families

def family_key(ctx, pair):
    a, b = pair["observation_ids"]
    sides = sorted([ctx.side_signature(a), ctx.side_signature(b)], key=lambda s: json.dumps(s, sort_keys=True))
    na, nb = ctx.norm[a], ctx.norm[b]
    facade = (facade_words(na["action"]["action_text_original"]) + facade_words(na["element"]["element_description_original"])) != \
             (facade_words(nb["action"]["action_text_original"]) + facade_words(nb["element"]["element_description_original"]))
    return {"candidate_key": list(pair["candidate_key"]), "sides": sides,
            "facade_side_words_differ": facade,
            "quantity_scale_difference": "QUANTITY_SCALE_DIFFERENCE" in pair["pair_caveats"],
            "source_relation_risk": bool(ctx.relation_risk(pair))}


def evidence_flags(key):
    s1, s2 = key["sides"]
    flags = []
    if key["source_relation_risk"]:
        flags.append("SOURCE_RELATION_RISK")
    if s1["unit_original"] != s2["unit_original"]:
        flags.append("UNIT_DIFFERENCE")
    if s1["semantic_caveats"] or s2["semantic_caveats"]:
        flags.append("OTHER_REVIEW_REQUIRED")
    if s1["element_description"] != s2["element_description"]:
        flags.append("OBJECT_TEXT_VARIANT")
    if s1["action_text"] != s2["action_text"] or key["facade_side_words_differ"]:
        flags.append("ACTION_TEXT_VARIANT")
    if s1["material"] and s2["material"] and s1["material"] != s2["material"]:
        flags.append("MATERIAL_DIFFERENCE_ONLY")
    if bool(s1["material"]) != bool(s2["material"]):
        flags.append("MATERIAL_EVIDENCE_ONE_SIDE")
    if key["quantity_scale_difference"]:
        flags.append("QUANTITY_SCALE_DIFFERENCE")
    if not flags:
        flags.append("EXACT_SAME_SEMANTIC_INPUT")
    return flags


def family_id(key):
    return f"RF-{key['candidate_key'][0]}-{canonical_sha(key)[:10]}"


def kengetal_blockers(ctx, obs_ids):
    """Regels uit kengetallen_rules_v1 die OOK na een positieve menselijke beslissing nog blokkeren."""
    out = []
    mats = {ctx.material(i)["value"] for i in obs_ids}
    unknown = sorted(i for i in obs_ids if not ctx.material(i)["value"])
    if unknown:
        out.append({"rule": "12 (materiaal)", "blocker": "MATERIAL_UNKNOWN", "observation_ids": unknown})
    if len(mats - {None}) > 1:
        out.append({"rule": "12 (materiaal)", "blocker": "MATERIAL_DIFFERS", "materials": sorted(mats - {None})})
    dep = sorted(i for i in obs_ids if not ctx.assess[i]["independent_input"])
    if dep:
        out.append({"rule": "2/7 (independent_input)", "blocker": "NOT_INDEPENDENT_INPUT", "observation_ids": dep})
    return out


def _kg_view(k):
    return {"kengetal_id": k["kengetal_id"], "status": k["status"], "source_cluster_count": k["source_cluster_count"],
            "observations": len(k["observation_ids"]),
            "insufficient_data_reasons": sorted({r.split(":")[0] for r in k["insufficient_data_reasons"]})}


def kengetal_effect(ctx, pair_obs_sets, decision):
    """Wat build_kengetallen (bestaande regels, zonder wijziging) zou opleveren als dit besluit voor deze paren
    ACTIVE werd. Alleen status/clusters/redenen - er wordt GEEN waarde getoond of vastgelegd."""
    records = copy.deepcopy(ctx.store["records"])
    for n, obs_ids in enumerate(pair_obs_sets):
        for r in records:
            if frozenset(r["observation_ids"]) == frozenset(obs_ids) and r["status"] == "ACTIVE":
                r["status"] = "SUPERSEDED"
        p = ctx.pair_by_set[frozenset(obs_ids)]
        records.append({"decision_id": f"HYPOTHETICAL-{n + 1:05d}", "pair_id": p["pair_id"],
                        "observation_ids": list(obs_ids), "decision": decision, "status": "ACTIVE",
                        "system_class": p["class"], "decision_caveats": []})
    norm = list(ctx.norm.values())
    _, before = bk.evaluate(norm, ctx.comp["observations"], ctx.store["records"])
    _, after = bk.evaluate(norm, ctx.comp["observations"], records)
    b = {k["kengetal_id"]: _kg_view(k) for k in before}
    a = {k["kengetal_id"]: _kg_view(k) for k in after}
    lost = sorted(i for i, k in b.items() if k["status"] == "AVAILABLE" and (a.get(i) or {}).get("status") != "AVAILABLE")
    new_available = sorted(i for i, k in a.items() if k["status"] == "AVAILABLE" and
                           (b.get(i) or {}).get("status") != "AVAILABLE")
    return {"removed_or_changed": [b[i] for i in sorted(b) if b[i] != a.get(i)],
            "resulting_groups": [a[i] for i in sorted(a) if a[i] != b.get(i)],
            "available_kengetallen_lost": lost, "new_available_kengetallen": new_available,
            "acknowledgement_required": sorted(set(lost) | set(new_available)),
            "note": "Simulatie met de bestaande kengetalregels; geen waarden. Een AVAILABLE kengetal dat verdwijnt of "
                    "nieuw ontstaat moet bij het toepassen expliciet worden bevestigd (acknowledged_kengetal_effects)."}


def choice_effects(ctx, fam):
    obs_ids = sorted({i for p in fam["pairs"] for i in p["observation_ids"]})
    blockers = kengetal_blockers(ctx, obs_ids)
    sup = sorted(r["decision_id"] for p in fam["pairs"] for r in p["existing_decisions"]
                 if r["status"] in ("ACTIVE", "REVIEW_REQUIRED"))
    common = (f"Eén nieuw ACTIVE HDR-record per opgesomd paar ({len(fam['pair_ids'])}), met verwijzing naar dit "
              f"familiebesluit" + (f"; bestaande records {sup} worden SUPERSEDED" if sup else "") + ".")
    positive = common + " Telt voor de cross-cluster-reviewregel (kengetallen regel 2) van groep " \
        f"{fam['candidate_group']}." + (" Een kengetal blijft daarna nog geblokkeerd door: " + "; ".join(
            f"{b['blocker']} ({b['rule']})" for b in blockers) + "." if blockers else
            " Of er een kengetal ontstaat bepaalt build_kengetallen volgens de bestaande regels (o.a. volledige "
            "cross-cluster review en >= 3 source clusters).")
    sets = [p["observation_ids"] for p in fam["pairs"]]
    pos_effect = kengetal_effect(ctx, sets, "COMPARABLE_WITH_CAVEATS")
    return [
        {"choice": "COMPARABLE", "meaning": CHOICES["COMPARABLE"], "effect": positive, "kengetal_effect": pos_effect},
        {"choice": "COMPARABLE_WITH_CAVEATS", "meaning": CHOICES["COMPARABLE_WITH_CAVEATS"], "effect": positive,
         "suggested_caveats_from_system": sorted({c for p in fam["pairs"] for c in p["pair_caveats"]}),
         "kengetal_effect": pos_effect},
        {"choice": "NOT_COMPARABLE", "meaning": CHOICES["NOT_COMPARABLE"],
         "effect": common + " Binnen een kandidaatgroep met beide observations -> INSUFFICIENT_DATA "
                            "(NOT_COMPARABLE_WITHIN_GROUP); anders wordt de buitenstaander uitgesloten.",
         "kengetal_effect": kengetal_effect(ctx, sets, "NOT_COMPARABLE")},
        {"choice": "UNKNOWN", "meaning": CHOICES["UNKNOWN"],
         "effect": common + " Telt niet als positieve beslissing; de paren blijven een ontbrekende review.",
         "kengetal_effect": kengetal_effect(ctx, sets, "UNKNOWN")},
    ]


def build_families(ctx, queue):
    groups = defaultdict(list)
    keys = {}
    for p in queue:
        k = family_key(ctx, p)
        fid = family_id(k)
        keys[fid] = k
        groups[fid].append(p)
    families = []
    for fid, pairs in groups.items():
        k = keys[fid]
        flags = evidence_flags(k)
        category = next(c for c in CATEGORY_ORDER if c in flags)
        pair_views = []
        for p in sorted(pairs, key=lambda p: p["pair_id"]):
            a, b = p["observation_ids"]
            na, nb = ctx.norm[a], ctx.norm[b]
            pair_views.append({
                "pair_id": p["pair_id"], "observation_ids": p["observation_ids"],
                "document_ids": [na["document_id"], nb["document_id"]], "source_clusters": p["source_clusters"],
                "system_class": p["class"], "pair_caveats": p["pair_caveats"],
                "hard_violations": p["hard_violations"], "unknown_reasons": p["unknown_reasons"],
                "observation_caveats": p["observation_caveats"], "checks": p["checks"],
                "facade_side_words": [facade_words(na["action"]["action_text_original"]),
                                      facade_words(nb["action"]["action_text_original"])],
                "action_texts": [na["action"]["action_text_original"], nb["action"]["action_text_original"]],
                "object_descriptions": [na["element"]["element_description_original"],
                                        nb["element"]["element_description_original"]],
                "quantities": [na["price"]["quantity_value"], nb["price"]["quantity_value"]],
                "derived_price_per_execution": [(ctx.assess[i]["derived_unit_price_per_execution"] or {}).get("value")
                                                for i in (a, b)],
                "price_level_dates": [na["price"]["price_level_date"], nb["price"]["price_level_date"]],
                "relation_risk": ctx.relation_risk(p),
                "status": ctx.pair_status(p),
                "existing_decisions": ctx.existing_records(p),
            })
        statuses = Counter(pv["status"] for pv in pair_views)
        if set(statuses) == {"ACTIVE_DECISION"}:
            status = "DECIDED_ACTIVE"
        elif set(statuses) == {"NO_DECISION"}:
            status = "OPEN_NO_DECISION"
        elif "ACTIVE_DECISION" not in statuses and "NO_DECISION" not in statuses:
            status = "OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED"
        else:
            status = "OPEN_MIXED"
        obs_ids = sorted({i for pv in pair_views for i in pv["observation_ids"]})
        fam = {
            "review_family_id": fid,
            "candidate_group": key_str(k["candidate_key"]),
            "evidence_category": category,
            "evidence_flags": flags,
            "family_key": k,
            "pair_ids": [pv["pair_id"] for pv in pair_views],
            "document_ids": sorted({d for pv in pair_views for d in pv["document_ids"]}),
            "source_clusters": sorted({c for pv in pair_views for c in pv["source_clusters"]}),
            "evidence": {
                "sides": k["sides"],
                "materials": sorted({str(ctx.material(i)["value"]) for i in obs_ids}),
                "action_texts": sorted({t for pv in pair_views for t in pv["action_texts"]}),
                "object_descriptions": sorted({t for pv in pair_views for t in pv["object_descriptions"]}),
                "units": sorted({ctx.norm[i]["unit"]["unit_original"] or "" for i in obs_ids}),
                "quantities": sorted({ctx.norm[i]["price"]["quantity_value"] for i in obs_ids},
                                     key=lambda q: float(q) if q else -1),
                "derived_price_per_execution": {i: (ctx.assess[i]["derived_unit_price_per_execution"] or {}).get("value")
                                                for i in obs_ids},
            },
            "differences": {
                "within_family_only": ["document", "source_cluster", "quantity", "price", "price_level"],
                "pair_caveats": dict(sorted(Counter(c for pv in pair_views for c in pv["pair_caveats"]).items())),
                "observation_caveats": dict(sorted(Counter(c for pv in pair_views for side in ("a", "b")
                                                           for c in pv["observation_caveats"][side]).items())),
                "price_levels": sorted({str(d) for pv in pair_views for d in pv["price_level_dates"]}),
            },
            "current_status": status,
            "pair_status_counts": dict(sorted(statuses.items())),
            "existing_decisions": sorted({r["decision_id"] for pv in pair_views for r in pv["existing_decisions"]}),
            "kengetal_blockers_even_after_positive_decision": kengetal_blockers(ctx, obs_ids),
            "pairs": pair_views,
        }
        fam["allowed_human_choices"] = choice_effects(ctx, fam)
        fam["family_input_sha256"] = family_input_sha(ctx, fam)
        families.append(fam)
    order = {key_str(g): n for n, g in enumerate(FOCUS_GROUPS)}
    families.sort(key=lambda f: (order.get(f["candidate_group"], len(order)), f["candidate_group"],
                                 f["current_status"] == "DECIDED_ACTIVE", -len(f["pair_ids"]), f["review_family_id"]))
    return families


def family_input_sha(ctx, fam):
    """Alles waarop een familiebesluit berust. Wijzigt er iets aan een paar, een observation of de bestaande
    beslissingen van deze paren, dan wijzigt deze hash en vervalt een eerder voorbereid familiebesluit."""
    obs_ids = sorted({i for p in fam["pairs"] for i in p["observation_ids"]})
    return canonical_sha({
        "review_version": REVIEW_VERSION,
        "review_family_id": fam["review_family_id"],
        "family_key": fam["family_key"],
        "pairs": [{k: p[k] for k in ("pair_id", "observation_ids", "source_clusters", "system_class", "pair_caveats",
                                     "hard_violations", "unknown_reasons", "observation_caveats", "checks",
                                     "existing_decisions")} for p in fam["pairs"]],
        "observations": {i: {"normalized": ctx.norm[i], "assessment": ctx.assess[i]} for i in obs_ids},
    })


# ------------------------------------------------------------------ kandidaatgroepen

def group_review(ctx, key, families):
    ks = key_str(key)
    obs = sorted((a["observation_id"] for a in ctx.comp["observations"] if key_str(a["candidate_key"]) == ks))
    views = [ctx.observation_view(i) for i in obs]
    indep = [v for v in views if v["independent_input"]]
    pairs = [p for p in ctx.comp["pairs"] if key_str(p["candidate_key"]) == ks]
    active = [r for r in ctx.store["records"] if r["status"] == "ACTIVE" and key_str(r["candidate_key"]) == ks]
    kengetallen = [{"kengetal_id": k["kengetal_id"], "status": k["status"], "value_display": k["value_display"],
                    "source_cluster_count": k["source_cluster_count"], "material": k["material"],
                    "observation_ids": k["observation_ids"], "decision_ids": k["decision_ids"]}
                   for k in ctx.kg["kengetallen"] if key_str(k["candidate_key"]) == ks]

    # materiaalbewijs per onafhankelijke observation
    def mclass(v):
        if v["material"]["value"]:
            return f"KNOWN:{v['material']['value']}"
        ev = v["material_text_evidence"] or {}
        if ev.get("would_derive"):
            return f"TEXT_EVIDENCE_PENDING_APPROVAL:{ev['would_derive']}"
        return "NO_MATERIAL_EVIDENCE"
    by_class = defaultdict(list)
    for v in indep:
        by_class[mclass(v)].append(v["observation_id"])

    # per materiaal: wat ontbreekt voor een geldige kandidaat (regels 2, 7, 12)
    materials = sorted({c.split(":", 1)[1] for c in by_class if ":" in c})
    requirements = []
    queue_family = {pid: f["review_family_id"] for f in families for pid in f["pair_ids"]}
    for m in materials:
        members = sorted(by_class.get(f"KNOWN:{m}", []) + by_class.get(f"TEXT_EVIDENCE_PENDING_APPROVAL:{m}", []))
        clusters = sorted({ctx.assess[i]["source_cluster"] for i in members})
        missing_pairs, nc = [], []
        for x, y in combinations(members, 2):
            if ctx.assess[x]["source_cluster"] == ctx.assess[y]["source_cluster"]:
                continue
            recs = [r for r in ctx.records.get(frozenset((x, y)), []) if r["status"] == "ACTIVE"]
            p = ctx.pair_by_set.get(frozenset((x, y)))
            if recs and recs[0]["decision"] == "NOT_COMPARABLE":
                nc.append(recs[0]["decision_id"])
            if not recs or recs[0]["decision"] not in bk.POSITIVE:
                missing_pairs.append({"pair_id": p["pair_id"] if p else None, "observation_ids": sorted((x, y)),
                                      "system_class": p["class"] if p else None,
                                      "review_family_id": queue_family.get(p["pair_id"]) if p else None,
                                      "in_review_queue": bool(p and p["pair_id"] in queue_family),
                                      "current_record": ctx.pair_status(p) if p else None})
        pending_material = sorted(by_class.get(f"TEXT_EVIDENCE_PENDING_APPROVAL:{m}", []))
        steps = []
        if pending_material:
            steps.append({"step": "MATERIAL_APPROVAL", "observation_ids": pending_material,
                          "documents": sorted({ctx.norm[i]["document_id"] for i in pending_material}),
                          "what": f"Materiaal '{m}' is alleen afleidbaar uit de elementtekst (bestaande tekstregel); "
                                  f"dat is voor deze documenten niet goedgekeurd (MATERIAL_FROM_TEXT-scope). Een mens "
                                  f"moet dit goedkeuren of het materiaal via het verified-element vastleggen."})
        if missing_pairs:
            steps.append({"step": "CROSS_CLUSTER_HUMAN_DECISIONS", "count": len(missing_pairs),
                          "pairs": missing_pairs,
                          "what": "Elke combinatie tussen verschillende source clusters heeft een ACTIVE "
                                  "COMPARABLE/COMPARABLE_WITH_CAVEATS nodig (regel 2, geen transitiviteit)."})
        if nc:
            steps.append({"step": "NOT_COMPARABLE_PRESENT", "decision_ids": sorted(set(nc)),
                          "what": "Een ACTIVE NOT_COMPARABLE binnen de set blokkeert de groep."})
        if len(clusters) < bk.MIN_SOURCE_CLUSTERS:
            steps.append({"step": "INSUFFICIENT_CLUSTERS", "clusters": len(clusters),
                          "what": f"Minder dan {bk.MIN_SOURCE_CLUSTERS} onafhankelijke source clusters; ook met alle "
                                  f"beslissingen blijft dit INSUFFICIENT_DATA."})
        existing = [k for k in kengetallen if (k["material"] or {}).get("normalized") == m
                    and k["status"] == "AVAILABLE"]
        requirements.append({
            "material": m, "observation_ids": members, "source_clusters": clusters,
            "potential_source_clusters": len(clusters),
            "existing_available_kengetal": [k["kengetal_id"] for k in existing],
            "status": "READY_FOR_KENGETAL_BUILD" if not steps else "REQUIRES_HUMAN_STEPS",
            "missing_steps": steps,
            "note": "Er is hier niets berekend. Pas na deze menselijke stappen bepaalt build_kengetallen volgens de "
                    "bestaande regels of er een (nieuwe versie van een) kengetal ontstaat.",
        })
    no_evidence = sorted(by_class.get("NO_MATERIAL_EVIDENCE", []))
    return {
        "candidate_group": ks,
        "priority": ([key_str(g) for g in PRIORITY_GROUPS].index(ks) + 1) if key in PRIORITY_GROUPS else None,
        "observations": len(views),
        "independent_input_observations": len(indep),
        "source_clusters_all": sorted({v["source_cluster"] for v in views}),
        "source_clusters_potentially_available": sorted({v["source_cluster"] for v in indep}),
        "not_independent": [{"observation_id": v["observation_id"],
                             "reasons": v["independent_input_exclusion_reasons"]} for v in views
                            if not v["independent_input"]],
        "material_evidence": {c: sorted(ids) for c, ids in sorted(by_class.items())},
        "observations_without_material_evidence": {
            "observation_ids": no_evidence,
            "note": "Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke "
                    "verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel "
                    "kengetal meetellen." if no_evidence else None},
        "pairs": {"total": len(pairs), "by_class": dict(sorted(Counter(p["class"] for p in pairs).items())),
                  "in_review_queue": sum(1 for p in pairs if p["pair_id"] in queue_family)},
        "review_families": [{"review_family_id": f["review_family_id"], "evidence_category": f["evidence_category"],
                             "pairs": len(f["pair_ids"]), "current_status": f["current_status"]}
                            for f in families if f["candidate_group"] == ks],
        "active_decisions": sorted(r["decision_id"] for r in active),
        "existing_kengetallen": kengetallen,
        "knowledge_candidate_requirements": requirements,
        "observation_details": views if key in DETAILED_GROUPS else None,
    }


def classify_new_5211(ctx, group):
    """5211 replace m1: nieuwe observations (Testbatch 01) t.o.v. de pvc-semantiek van het bestaande kengetal."""
    out = defaultdict(list)
    for v in group["observation_details"] or []:
        if not v["new_in_testbatch01"]:
            continue
        ev = v["material_text_evidence"] or {}
        mat = v["material"]["value"] or ev.get("would_derive")
        if not v["independent_input"]:
            cls = "NOT_INDEPENDENT_INPUT"
        elif v["material"]["value"] == "pvc":
            cls = "PVC_EXACT_SEMANTICS"
        elif ev.get("would_derive") == "pvc":
            cls = "PVC_BY_ELEMENT_TEXT_PENDING_MATERIAL_APPROVAL"
        elif mat:
            cls = f"OTHER_MATERIAL:{mat}"
        else:
            cls = "INSUFFICIENT_EVIDENCE"
        out[cls].append({"observation_id": v["observation_id"], "document_id": v["document_id"],
                         "object_description": v["object_description"], "action_text": v["action_text"],
                         "quantity": v["quantity"], "derived_price_per_execution": v["derived_price_per_execution"],
                         "price_level_date": v["price_level_date"]})
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ build

def build(root):
    ctx = Context(root)
    queue = hrq.select_pairs(ctx.comp)
    families = build_families(ctx, queue)
    groups = [group_review(ctx, g, families) for g in FOCUS_GROUPS]
    g5211 = next(g for g in groups if g["candidate_group"] == "5211|replace|m1")
    kg5211 = [k for k in ctx.kg["kengetallen"] if k["kengetal_id"].startswith("KG-5211-replace-m1-pvc")]
    g5211["pvc_review"] = {
        "existing_kengetal": [{"kengetal_id": k["kengetal_id"], "status": k["status"], "value_display": k["value_display"],
                               "source_cluster_count": k["source_cluster_count"], "decision_ids": k["decision_ids"],
                               "observation_ids": k["observation_ids"]} for k in kg5211],
        "statement": "Het bestaande kengetal blijft ongewijzigd tot er nieuwe geldige ACTIVE decisions zijn; dit "
                     "pakket wijzigt het niet.",
        "new_observations_by_semantics": classify_new_5211(ctx, g5211),
    }
    status_counts = Counter(ctx.pair_status(p) for p in queue)
    open_families = [f for f in families if f["current_status"] != "DECIDED_ACTIVE"]
    return {
        "review_version": REVIEW_VERSION,
        "inputs": ctx.inputs(),
        "note": ("Reviewpakket, geen beslissing. Er worden geen ACTIVE decisions, geen COMPARABLE/NOT_COMPARABLE, "
                 "geen scores en geen kengetallen aangemaakt. Een familiebesluit wordt alleen toegepast via "
                 "scripts/apply_family_decision.py op de exact opgesomde pair_ids, gebonden aan "
                 "family_input_sha256."),
        "family_rules": {
            "grouping": "candidate key + per kant (objectomschrijving en actietekst als woordtokens zonder de vaste "
                        "gevelzijde-woorden, eenheid in de bron, materiaal + bron, inhoudelijke observation-caveats) "
                        "+ gevelzijde-woorden verschillen + QUANTITY_SCALE_DIFFERENCE + relatierisico",
            "facade_side_words": sorted(bk.FACADE_SIDE_WORDS),
            "category_order": list(CATEGORY_ORDER),
            "no_fuzzy_matching": True,
        },
        "queue": {"selection": hrq.SELECTION, "pairs": len(queue),
                  "by_pair_status": dict(sorted(status_counts.items())),
                  "open_pairs": sum(v for k, v in status_counts.items() if k != "ACTIVE_DECISION")},
        "summary": {
            "review_families": len(families),
            "open_review_families": len(open_families),
            "families_by_status": dict(sorted(Counter(f["current_status"] for f in families).items())),
            "families_by_category": dict(sorted(Counter(f["evidence_category"] for f in families).items())),
            "pairs_by_category": dict(sorted(Counter(f["evidence_category"] for f in families
                                                     for _ in f["pair_ids"]).items())),
            "multi_pair_families": sum(1 for f in families if len(f["pair_ids"]) > 1),
        },
        "families": families,
        "candidate_groups": groups,
    }


# ------------------------------------------------------------------ markdown

def _fmt_list(xs):
    return ", ".join(str(x) for x in xs) if xs else "-"


def render_md(pkg):
    q, s = pkg["queue"], pkg["summary"]
    lines = ["# Comparability review v2", "",
             "Reviewpakket: **er is niets besloten**. Geen ACTIVE decisions, geen automatische COMPARABLE of "
             "NOT_COMPARABLE, geen scores, geen nieuw kengetal. Een familiebesluit wordt alleen toegepast via "
             "`scripts/apply_family_decision.py` op exact opgesomde `pair_ids`, gebonden aan `family_input_sha256`.",
             "", f"Invoer: comparability `{pkg['inputs']['comparability_sha256'][:12]}`, genormaliseerd "
                 f"`{pkg['inputs']['normalized_observations_sha256'][:12]}`, beslissingen "
                 f"`{pkg['inputs']['human_decisions_sha256'][:12]}`, relaties "
                 f"`{pkg['inputs']['document_relations_sha256'][:12]}`.", "",
             "## Reviewqueue vóór en na groepering", "",
             "| | aantal |", "|---|---|",
             f"| paren in de queue (selectie v1) | {q['pairs']} |"]
    for k, v in q["by_pair_status"].items():
        lines.append(f"| paren met status {k} | {v} |")
    lines += [f"| reviewfamilies | {s['review_families']} |",
              f"| open reviewfamilies | {s['open_review_families']} |",
              f"| families met meer dan één paar | {s['multi_pair_families']} |", "",
              "Families per bewijscategorie (families / paren):", ""]
    for c in CATEGORY_ORDER:
        if c in s["families_by_category"]:
            lines.append(f"- `{c}`: {s['families_by_category'][c]} / {s['pairs_by_category'][c]}")
    lines += ["", "Groepering: " + pkg["family_rules"]["grouping"] + ". Gevelzijde-woorden: "
              + ", ".join(pkg["family_rules"]["facade_side_words"]) + ".", ""]

    for g in pkg["candidate_groups"]:
        fams = [f for f in pkg["families"] if f["candidate_group"] == g["candidate_group"]]
        title = f"## {g['candidate_group']}" + (f" (prioriteit {g['priority']})" if g["priority"] else "")
        lines += [title, "",
                  f"- observations: {g['observations']} (independent_input: {g['independent_input_observations']})",
                  f"- source clusters (alle): {len(g['source_clusters_all'])}; potentieel beschikbaar "
                  f"(independent_input): {len(g['source_clusters_potentially_available'])} - "
                  f"{_fmt_list(g['source_clusters_potentially_available'])}",
                  f"- paren: {g['pairs']['total']} ({_fmt_list(f'{k} {v}' for k, v in g['pairs']['by_class'].items())}); "
                  f"in de reviewqueue: {g['pairs']['in_review_queue']}",
                  f"- ACTIVE decisions: {_fmt_list(g['active_decisions'])}",
                  f"- bestaande kengetallen: " + (_fmt_list(f"{k['kengetal_id']} {k['status']} {k['value_display']} "
                                                            f"({k['source_cluster_count']} clusters)"
                                                            for k in g["existing_kengetallen"]) or "-"),
                  "- materiaalbewijs (independent_input): " + _fmt_list(
                      f"{c}: {len(ids)}" for c, ids in g["material_evidence"].items()), ""]
        if g["observations_without_material_evidence"]["observation_ids"]:
            lines += [f"Zonder materiaalbewijs: {_fmt_list(g['observations_without_material_evidence']['observation_ids'])}. "
                      + g["observations_without_material_evidence"]["note"], ""]
        if g.get("pvc_review"):
            pv = g["pvc_review"]
            lines += ["### PVC-semantiek en het bestaande kengetal", ""]
            for k in pv["existing_kengetal"]:
                lines.append(f"- `{k['kengetal_id']}`: {k['status']} {k['value_display']}, {k['source_cluster_count']} "
                             f"clusters, decisions {_fmt_list(k['decision_ids'])}")
            lines += ["- " + pv["statement"], "", "Nieuwe observations (Testbatch 01):", ""]
            for cls, items in pv["new_observations_by_semantics"].items():
                for it in items:
                    lines.append(f"- `{cls}`: {it['observation_id']} - {it['object_description']} / {it['action_text']} "
                                 f"({it['quantity']}, prijs per uitvoering {it['derived_price_per_execution']}, "
                                 f"prijspeil {it['price_level_date']})")
            lines.append("")
        lines += ["### Wat ontbreekt voor een geldige knowledge candidate", ""]
        if not g["knowledge_candidate_requirements"]:
            lines += ["Geen enkel materiaal is vastgesteld of afleidbaar; eerst materiaal via verified-element "
                      "vastleggen (regel 12).", ""]
        for r in g["knowledge_candidate_requirements"]:
            lines.append(f"- materiaal **{r['material']}**: {len(r['observation_ids'])} observations, "
                         f"{r['potential_source_clusters']} potentiële clusters, status `{r['status']}`"
                         + (f", bestaand kengetal {_fmt_list(r['existing_available_kengetal'])}"
                            if r["existing_available_kengetal"] else ""))
            for st in r["missing_steps"]:
                if st["step"] == "CROSS_CLUSTER_HUMAN_DECISIONS":
                    in_q = sum(1 for p in st["pairs"] if p["in_review_queue"])
                    fams_needed = sorted({p["review_family_id"] for p in st["pairs"] if p["review_family_id"]})
                    lines.append(f"  - {st['count']} cross-cluster paren zonder ACTIVE positieve beslissing "
                                 f"({in_q} in de queue; families {_fmt_list(fams_needed)}; niet in de queue: "
                                 f"{_fmt_list(p['pair_id'] for p in st['pairs'] if not p['in_review_queue'])})")
                elif st["step"] == "MATERIAL_APPROVAL":
                    lines.append(f"  - materiaalgoedkeuring nodig voor {_fmt_list(st['documents'])}: "
                                 f"{_fmt_list(st['observation_ids'])}")
                elif st["step"] == "INSUFFICIENT_CLUSTERS":
                    lines.append(f"  - {st['what']}")
                else:
                    lines.append(f"  - {st['step']}: {st['what']}")
        lines += ["", "### Reviewfamilies", "",
                  "| familie | categorie | paren | status | documenten | bestaande beslissingen |",
                  "|---|---|---|---|---|---|"]
        for f in fams:
            lines.append(f"| `{f['review_family_id']}` | {f['evidence_category']} | {len(f['pair_ids'])} | "
                         f"{f['current_status']} | {_fmt_list(f['document_ids'])} | {_fmt_list(f['existing_decisions'])} |")
        lines.append("")
        for f in fams:
            s1, s2 = f["evidence"]["sides"]
            lines += [f"#### {f['review_family_id']} - {f['evidence_category']} ({len(f['pair_ids'])} paren)", "",
                      f"- kant 1: {s1['element_description']} / {s1['action_text']} / {s1['unit_original']} / "
                      f"materiaal {s1['material'] or 'onbekend'}",
                      f"- kant 2: {s2['element_description']} / {s2['action_text']} / {s2['unit_original']} / "
                      f"materiaal {s2['material'] or 'onbekend'}",
                      f"- bewijs: {_fmt_list(f['evidence_flags'])}; paarcaveats {f['differences']['pair_caveats'] or '-'}",
                      f"- actieteksten: {_fmt_list(f['evidence']['action_texts'])}",
                      f"- hoeveelheden: {_fmt_list(f['evidence']['quantities'])}; prijspeilen: "
                      f"{_fmt_list(f['differences']['price_levels'])}",
                      f"- pair_ids: {_fmt_list(f['pair_ids'])}",
                      f"- family_input_sha256: `{f['family_input_sha256']}`"]
            eff = next(c for c in f["allowed_human_choices"] if c["choice"] == "COMPARABLE_WITH_CAVEATS")["kengetal_effect"]
            if eff["available_kengetallen_lost"]:
                lines.append("- **LET OP**: een positief besluit over alle paren maakt volgens de bestaande regels "
                             f"het AVAILABLE kengetal {_fmt_list(eff['available_kengetallen_lost'])} ongeldig "
                             "(de groep wordt " + _fmt_list(f"{g['status']} {g['insufficient_data_reasons']}"
                                                            for g in eff["resulting_groups"]) + "); vereist expliciete "
                             "bevestiging bij het toepassen")
            if eff["new_available_kengetallen"]:
                lines.append(f"- een positief besluit maakt een nieuw AVAILABLE kengetal mogelijk: "
                             f"{_fmt_list(eff['new_available_kengetallen'])} (expliciete bevestiging vereist)")
            if f["kengetal_blockers_even_after_positive_decision"]:
                lines.append("- blijft ook na een positieve beslissing blokkeren: " + _fmt_list(
                    f"{b['blocker']}" for b in f["kengetal_blockers_even_after_positive_decision"]))
            lines.append("")
    lines += ["## Overige families (buiten de 9 kandidaatgroepen)", "",
              "| familie | groep | categorie | paren | status |", "|---|---|---|---|---|"]
    focus = {key_str(g) for g in FOCUS_GROUPS}
    for f in pkg["families"]:
        if f["candidate_group"] not in focus:
            lines.append(f"| `{f['review_family_id']}` | {f['candidate_group']} | {f['evidence_category']} | "
                         f"{len(f['pair_ids'])} | {f['current_status']} |")
    lines += ["", "## Toegestane keuzes (bestaand model)", ""]
    for c, m in CHOICES.items():
        lines.append(f"- `{c}`: {m}")
    lines += ["", "Het effect per keuze staat per familie in `comparability_review_v2.json` "
              "(`allowed_human_choices`).", ""]
    return "\n".join(lines)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root, pkg=None):
    pkg = pkg or build(root)
    os.makedirs(os.path.join(root, "reports", "review"), exist_ok=True)
    with open(os.path.join(root, OUT_JSON), "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(pkg))
    with open(os.path.join(root, OUT_MD), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(pkg))
    return pkg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="controleer of het pakket actueel is (schrijft niets)")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pkg = build(root)
    if args.check:
        cur = open(os.path.join(root, OUT_JSON), encoding="utf-8").read() if os.path.exists(os.path.join(root, OUT_JSON)) else None
        ok = cur == dump(pkg)
        print("ACTUEEL" if ok else "NIET ACTUEEL")
        return 0 if ok else 1
    write(root, pkg)
    print(f"{pkg['queue']['pairs']} paren -> {pkg['summary']['review_families']} families "
          f"({pkg['summary']['open_review_families']} open)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
