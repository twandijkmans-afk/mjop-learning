#!/usr/bin/env python3
"""
kengetal_readiness_v1.py - read-only kengetal-readiness analyse voor ALLE candidate groups.

Een candidate group is (candidate key, materiaal), gevormd uit de independent_input observations (alleen die kunnen
volgens kengetallen_rules_v1 regels 2/7 meetellen). Materiaal = vastgesteld materiaal (verified element, bestaande
tekstregel of menselijk materiaalbesluit) of het materiaal dat de bestaande tekstregel zou afleiden (wacht op een
menselijk materiaalbesluit). Observations zonder enig materiaalbewijs vormen per key een groep met materiaal null:
die kunnen volgens regel 12 in geen enkel kengetal meetellen tot een mens het elementmateriaal vastlegt.

Per groep (niets wordt toegepast, niets wordt gescoord):
  - materiaalstatus, observations, onafhankelijke source clusters, ACTIVE human decisions, open reviewfamilies;
  - ontbrekende materiaalgoedkeuringen: record_material_decision.validate (placeholder-reviewer; schrijft niets);
  - de toestand NA alle toelaatbare materiaalgoedkeuringen: record_material_decision.record op een TIJDELIJKE kopie
    (zoals --dry-run), daarna comparability_review_v2.build op die kopie -> de reviewfamilies die een mens dan zou
    beslissen;
  - resterende menselijke acties = materiaalgoedkeuringen (één per observation) + familiebesluiten (één per open
    reviewfamilie) + paarbesluiten buiten de reviewqueue (één per paar; daarvoor bestaat nog geen ketenschakel);
  - kengetal-effect: build_kengetallen.evaluate (bestaande regels) met hypothetische ACTIVE
    COMPARABLE_WITH_CAVEATS-records voor alle ontbrekende cross-cluster paren. Nergens vastgelegd.

Classificatie (in deze volgorde):
  AVAILABLE                  er is een AVAILABLE kengetal voor deze key + dit materiaal
  INSUFFICIENT_CLUSTERS      minder dan 3 potentiële onafhankelijke source clusters, ook na alle stappen
  BLOCKED_OTHER              een andere blocker (geen materiaalbewijs, geweigerde materiaalgoedkeuring, ACTIVE
                             NOT_COMPARABLE, harde regelschending, paren buiten de reviewqueue, of volgens de
                             bestaande regels ook na alle stappen geen AVAILABLE)
  MATERIAL_AND_REVIEW_NEEDED materiaalgoedkeuring(en) en familiebesluit(en)
  MATERIAL_APPROVAL_NEEDED   alleen materiaalgoedkeuring(en)
  READY_AFTER_REVIEW         alleen familiebesluit(en)

    python scripts/kengetal_readiness_v1.py [--check]
"""
import argparse
import copy
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_kengetallen as bk  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import export_human_review_queue as hrq  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import record_material_decision as rmd  # noqa: E402

REPORT_VERSION = "kengetal_readiness_v1"
OUT_JSON = os.path.join("reports", "review", "kengetal_readiness_v1.json")
OUT_MD = os.path.join("reports", "review", "kengetal_readiness_v1.md")
STATUSES = ("AVAILABLE", "READY_AFTER_REVIEW", "MATERIAL_APPROVAL_NEEDED", "MATERIAL_AND_REVIEW_NEEDED",
            "INSUFFICIENT_CLUSTERS", "BLOCKED_OTHER")
REVIEW_BLOCKERS = ("MATERIAL_APPROVAL_NEEDED", "CROSS_CLUSTER_REVIEW_NEEDED")
PLACEHOLDER = {"reviewer": "SIMULATION-NOT-A-DECISION", "reviewed_at": "2000-01-01T00:00:00Z",
               "decision_reason": "simulatie voor de readiness-analyse; geen besluit"}
SIM_NOW = "2000-01-01T00:00:00Z"
DETAIL_COUNT = 5


# ------------------------------------------------------------------ materiaal

def material_class(ctx, oid):
    m = ctx.material(oid)
    if m["value"]:
        return "KNOWN", m["value"], None
    ev = ctx.material_text_evidence(oid) or {}
    if ev.get("would_derive"):
        return "PENDING", ev["would_derive"], ev.get("token")
    return "NONE", None, None


def approval_for(ctx, oid, token):
    n = ctx.norm[oid]
    return {"observation_id": oid, "material": token,
            "evidence": {"element_description_original": n["element"]["element_description_original"],
                         "action_text_original": n["action"]["action_text_original"],
                         "unit_original": n["unit"]["unit_original"]}}


def precheck(root, approval):
    try:
        rmd.validate(root, dict(PLACEHOLDER, approvals=[approval]))
        return None
    except rmd.MaterialDecisionError as e:
        return str(e)


def with_material_decisions(root, approvals, fn):
    """record_material_decision.record op een tijdelijke kopie; fn(tmp) op de toestand daarna."""
    with tempfile.TemporaryDirectory() as tmp:
        for rel in pr.SIMULATION_COPY:
            s, d = os.path.join(root, rel), os.path.join(tmp, rel)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            elif os.path.isfile(s):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
        if approvals:
            rmd.record(tmp, dict(PLACEHOLDER, approvals=approvals), now=SIM_NOW)
        return fn(tmp)


# ------------------------------------------------------------------ simulatie

def simulate(ctx, key, material, members, pair_sets):
    """build_kengetallen.evaluate met hypothetische ACTIVE COMPARABLE_WITH_CAVEATS voor pair_sets. Returns de
    kengetalgroep van deze key + dit materiaal die deze members bevat (of None)."""
    records = copy.deepcopy(ctx.store["records"])
    for n, s in enumerate(sorted(pair_sets, key=sorted)):
        for r in records:
            if frozenset(r["observation_ids"]) == s and r["status"] == "ACTIVE":
                r["status"] = "SUPERSEDED"
        p = ctx.pair_by_set[s]
        records.append({"decision_id": f"SIMULATED-{n + 1:05d}", "pair_id": p["pair_id"],
                        "observation_ids": list(p["observation_ids"]), "decision": "COMPARABLE_WITH_CAVEATS",
                        "status": "ACTIVE", "system_class": p["class"], "decision_caveats": []})
    _, kgs = bk.evaluate(list(ctx.norm.values()), ctx.comp["observations"], records)
    hits = [k for k in kgs if crv.key_str(k["candidate_key"]) == key and (k["material"] or {}).get("normalized")
            == material and set(k["observation_ids"]) & set(members)]
    if not hits:
        return None
    k = max(hits, key=lambda k: (len(set(k["observation_ids"]) & set(members)), k["kengetal_id"]))
    return {"status": k["status"], "insufficient_data_reasons": sorted({r.split(":")[0]
                                                                       for r in k["insufficient_data_reasons"]}),
            "source_cluster_count": k["source_cluster_count"], "source_cluster_ids": k["source_cluster_ids"],
            "simulated_value_display": k["value_display"], "min_display": k["min_display"],
            "max_display": k["max_display"], "observation_ids": k["observation_ids"],
            "mixed_price_level": k["price_levels"]["mixed_price_level"],
            "missing_price_level": k["price_levels"]["missing_price_level"]}


def pair_state(ctx, x, y, queue_family):
    """Status van een cross-cluster paar voor de kengetalregels (regel 2)."""
    p = ctx.pair_by_set.get(frozenset((x, y)))
    recs = [r for r in ctx.records.get(frozenset((x, y)), []) if r["status"] == "ACTIVE"]
    if recs and recs[0]["decision"] in bk.POSITIVE:
        return p, "DECIDED_POSITIVE", recs[0]["decision_id"]
    if recs and recs[0]["decision"] == "NOT_COMPARABLE":
        return p, "NOT_COMPARABLE_ACTIVE", recs[0]["decision_id"]
    if p and p["pair_id"] in queue_family:
        return p, "IN_REVIEW_QUEUE", queue_family[p["pair_id"]]
    if p and p["hard_violations"]:
        return p, "HARD_VIOLATION", ",".join(p["hard_violations"])
    return p, "OUTSIDE_REVIEW_QUEUE", p["class"] if p else None


# ------------------------------------------------------------------ build

def build(root):
    ctx = crv.Context(root)
    review = crv.build(root)
    cur_family = {pid: f for f in review["families"] for pid in f["pair_ids"]}

    # groepen uit independent_input observations
    groups = defaultdict(list)
    info = {}
    excluded_keys = defaultdict(Counter)
    for a in sorted(ctx.comp["observations"], key=lambda a: a["observation_id"]):
        oid, ks = a["observation_id"], crv.key_str(a["candidate_key"])
        if not a["independent_input"]:
            for r in a["independent_input_exclusion_reasons"] or ["NOT_INDEPENDENT_INPUT"]:
                excluded_keys[ks][r] += 1
            continue
        cls, mat, token = material_class(ctx, oid)
        info[oid] = (cls, mat, token)
        groups[(ks, mat)].append(oid)
    independent_keys = {k for k, _ in groups}

    # materiaalgoedkeuringen: precheck per observation, daarna alle toelaatbare samen op een tijdelijke kopie
    refused, approvals = {}, []
    for oid, (cls, mat, token) in sorted(info.items()):
        if cls == "PENDING":
            appr = approval_for(ctx, oid, token or mat)
            reason = precheck(root, appr)
            if reason:
                refused[oid] = reason
            else:
                approvals.append(appr)

    def after(tmp):
        c2 = crv.Context(tmp)
        r2 = crv.build(tmp)
        queue_family = {pid: f["review_family_id"] for f in r2["families"] for pid in f["pair_ids"]
                        if f["current_status"] != "DECIDED_ACTIVE"}
        fam_by_id = {f["review_family_id"]: f for f in r2["families"]}
        out = {}
        for (ks, mat), obs in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1] or "")):
            if mat is None:
                continue
            members = [i for i in obs if i not in refused]
            missing = []
            for x, y in combinations(members, 2):
                if c2.assess[x]["source_cluster"] == c2.assess[y]["source_cluster"]:
                    continue
                p, state, ref = pair_state(c2, x, y, queue_family)
                if state != "DECIDED_POSITIVE":
                    missing.append({"pair_id": p["pair_id"] if p else None, "observation_ids": sorted((x, y)),
                                    "state": state, "ref": ref, "system_class": p["class"] if p else None})
            sim_sets = [frozenset(m["observation_ids"]) for m in missing if m["state"] != "NOT_COMPARABLE_ACTIVE"
                        and frozenset(m["observation_ids"]) in c2.pair_by_set]
            fams = sorted({m["ref"] for m in missing if m["state"] == "IN_REVIEW_QUEUE"})
            out[(ks, mat)] = {
                "members": members, "missing_pairs": missing,
                "review_families_to_decide": [
                    {"review_family_id": fid, "evidence_category": fam_by_id[fid]["evidence_category"],
                     "pair_ids": sorted(m["pair_id"] for m in missing if m["ref"] == fid),
                     "family_pair_ids": fam_by_id[fid]["pair_ids"],
                     "indicative_family_input_sha256": fam_by_id[fid]["family_input_sha256"]} for fid in fams],
                "simulation": simulate(c2, ks, mat, members, sim_sets) if members else None,
            }
        return out

    post = with_material_decisions(root, approvals, after)
    approved = {a["observation_id"] for a in approvals}

    kg_available = {(crv.key_str(k["candidate_key"]), (k["material"] or {}).get("normalized")): k
                    for k in ctx.kg["kengetallen"] if k["status"] == "AVAILABLE"}
    out = []
    for (ks, mat), obs in groups.items():
        code, action, unit = ks.split("|")
        clusters = sorted({ctx.assess[i]["source_cluster"] for i in obs})
        mstat = Counter(info[i][0] for i in obs)
        active = sorted(r["decision_id"] for r in ctx.store["records"] if r["status"] == "ACTIVE"
                        and set(r["observation_ids"]) <= set(obs))
        open_now = sorted({cur_family[p["pair_id"]]["review_family_id"] for x, y in combinations(obs, 2)
                           for p in [ctx.pair_by_set.get(frozenset((x, y)))]
                           if p and p["pair_id"] in cur_family
                           and cur_family[p["pair_id"]]["current_status"] != "DECIDED_ACTIVE"})
        pending = sorted(i for i in obs if info[i][0] == "PENDING" and i in approved)
        g = {"candidate_group": f"{ks}|{mat or 'unknown'}", "candidate_key": ks, "element_code": code,
             "action": action, "unit": unit, "material": mat,
             "material_status": {"known": mstat.get("KNOWN", 0), "pending_approval": mstat.get("PENDING", 0),
                                 "no_evidence": mstat.get("NONE", 0)},
             "observations": len(obs), "observation_ids": obs,
             "independent_source_clusters": {"count": len(clusters), "ids": clusters},
             "active_human_decisions": active,
             "open_review_families_current": open_now,
             "missing_material_approvals": pending,
             "material_approvals_refused": {i: refused[i] for i in obs if i in refused},
             "existing_available_kengetal": None}
        blockers = []
        if mat is None:
            blockers.append("NO_MATERIAL_EVIDENCE")
            potential = len(clusters)
            g.update({"potential_source_clusters_after_steps": {"count": potential, "ids": clusters},
                      "review_families_to_decide": [], "pairs_outside_review_queue": [],
                      "human_actions": {"material_approvals": None, "review_family_decisions": None,
                                        "pair_decisions_outside_review_queue": None, "total": None,
                                        "complete_with_existing_chain": False,
                                        "note": "Geen materiaalbewijs: eerst elementmateriaal door een mens vastleggen "
                                                "(verified element); daarna ontstaat een eigen materiaalgroep."},
                      "expected_kengetal_effect": None, "available_directly_after_steps": False})
            if potential < bk.MIN_SOURCE_CLUSTERS:
                blockers.append("INSUFFICIENT_CLUSTERS")
        else:
            p = post[(ks, mat)]
            m_clusters = sorted({ctx.assess[i]["source_cluster"] for i in p["members"]})
            potential = len(m_clusters)
            by_state = defaultdict(list)
            for mp in p["missing_pairs"]:
                by_state[mp["state"]].append(mp)
            outside = by_state["OUTSIDE_REVIEW_QUEUE"]
            if pending:
                blockers.append("MATERIAL_APPROVAL_NEEDED")
            if by_state["IN_REVIEW_QUEUE"]:
                blockers.append("CROSS_CLUSTER_REVIEW_NEEDED")
            if g["material_approvals_refused"]:
                blockers.append("MATERIAL_APPROVAL_REFUSED")
            if by_state["NOT_COMPARABLE_ACTIVE"]:
                blockers.append("NOT_COMPARABLE_PRESENT")
            if by_state["HARD_VIOLATION"]:
                blockers.append("HARD_VIOLATION")
            if outside:
                blockers.append("PAIRS_OUTSIDE_REVIEW_QUEUE")
            if potential < bk.MIN_SOURCE_CLUSTERS:
                blockers.append("INSUFFICIENT_CLUSTERS")
            sim = p["simulation"]
            if potential >= bk.MIN_SOURCE_CLUSTERS and not (sim and sim["status"] == "AVAILABLE"):
                blockers.append("NOT_AVAILABLE_AFTER_ALL_STEPS")
            complete = not (set(blockers) - set(REVIEW_BLOCKERS))
            n_fam, n_out = len(p["review_families_to_decide"]), len(outside)
            g.update({"potential_source_clusters_after_steps": {"count": potential, "ids": m_clusters},
                      "review_families_to_decide": p["review_families_to_decide"],
                      "pairs_outside_review_queue": [{"pair_id": x["pair_id"], "system_class": x["system_class"]}
                                                     for x in outside],
                      "blocking_pairs": [{"pair_id": x["pair_id"], "state": x["state"], "ref": x["ref"]}
                                         for x in by_state["NOT_COMPARABLE_ACTIVE"] + by_state["HARD_VIOLATION"]],
                      "human_actions": {"material_approvals": len(pending), "review_family_decisions": n_fam,
                                        "pair_decisions_outside_review_queue": n_out,
                                        "total": len(pending) + n_fam + n_out,
                                        "complete_with_existing_chain": complete},
                      "expected_kengetal_effect": sim,
                      "available_directly_after_steps": bool(complete and sim and sim["status"] == "AVAILABLE")})
            kg = kg_available.get((ks, mat))
            if kg:
                g["existing_available_kengetal"] = {"kengetal_id": kg["kengetal_id"],
                                                    "value_display": kg["value_display"],
                                                    "min_display": kg["min_display"], "max_display": kg["max_display"],
                                                    "source_cluster_count": kg["source_cluster_count"]}
        g["blockers"] = blockers
        g["other_blockers"] = [b for b in blockers if b not in REVIEW_BLOCKERS]
        if g["existing_available_kengetal"]:
            status = "AVAILABLE"
        elif "INSUFFICIENT_CLUSTERS" in blockers:
            status = "INSUFFICIENT_CLUSTERS"
        elif g["other_blockers"]:
            status = "BLOCKED_OTHER"
        elif "MATERIAL_APPROVAL_NEEDED" in blockers and "CROSS_CLUSTER_REVIEW_NEEDED" in blockers:
            status = "MATERIAL_AND_REVIEW_NEEDED"
        elif "MATERIAL_APPROVAL_NEEDED" in blockers:
            status = "MATERIAL_APPROVAL_NEEDED"
        elif "CROSS_CLUSTER_REVIEW_NEEDED" in blockers:
            status = "READY_AFTER_REVIEW"
        else:
            status = "BLOCKED_OTHER"   # geen stap open en toch geen AVAILABLE kengetal: nooit stil negeren
            g["blockers"].append("NO_OPEN_STEP_BUT_NOT_AVAILABLE")
            g["other_blockers"].append("NO_OPEN_STEP_BUT_NOT_AVAILABLE")
        g["readiness"] = status
        out.append(g)

    def sort_key(g):
        total = g["human_actions"]["total"]
        return (g["readiness"] != "AVAILABLE", len(g["blockers"]), total if total is not None else 10 ** 9,
                -g["potential_source_clusters_after_steps"]["count"], g["candidate_group"])
    out.sort(key=sort_key)
    for n, g in enumerate(out, 1):
        g["rank"] = n

    # eerstvolgende groepen: niet-AVAILABLE groepen (in sorteervolgorde) waarvoor de bestaande regels na alle
    # menselijke stappen een AVAILABLE kengetal geven; groepen die dat nooit kunnen (te weinig clusters, geen
    # materiaalbewijs) zijn geen "volgende stap"
    nxt = [g for g in out if g["readiness"] != "AVAILABLE" and g["expected_kengetal_effect"]
           and g["expected_kengetal_effect"]["status"] == "AVAILABLE"][:DETAIL_COUNT]
    least = min(nxt, key=lambda g: (g["human_actions"]["total"], g["rank"])) if nxt else None
    ready_with_chain = [g["candidate_group"] for g in out if g["readiness"] in (
        "READY_AFTER_REVIEW", "MATERIAL_APPROVAL_NEEDED", "MATERIAL_AND_REVIEW_NEEDED")]
    return {
        "report_version": REPORT_VERSION,
        "inputs": review["inputs"],
        "note": ("Alleen analyse: geen besluit, geen materiaal, geen kengetal toegepast; geen scoring of confidence. "
                 "Materiaalgoedkeuringen en de toestand daarna zijn gesimuleerd op een tijdelijke kopie; "
                 "reviewfamily-ids en family_input_sha256 na goedkeuring zijn indicatief (het echte familiebesluit "
                 "bindt aan comparability_review_v2.json na het echte materiaalbesluit). Kengetal-effecten komen "
                 "uitsluitend uit build_kengetallen.evaluate (kengetallen_rules_v1) met hypothetische ACTIVE "
                 "COMPARABLE_WITH_CAVEATS-records voor alle ontbrekende cross-cluster paren."),
        "definitions": {
            "candidate_group": "(candidate key, materiaal) uit independent_input observations; materiaal null = geen "
                               "materiaalbewijs",
            "human_actions": "materiaalgoedkeuringen (één per observation) + familiebesluiten (één per open "
                             "reviewfamilie na materiaalgoedkeuring) + paarbesluiten buiten de reviewqueue (één per "
                             "paar; daarvoor bestaat in de huidige keten nog geen schakel)",
            "sort": "AVAILABLE eerst; dan minste blockers; minste menselijke acties; meeste potentiële "
                    "onafhankelijke clusters; candidate group",
            "statuses": list(STATUSES),
        },
        "summary": {
            "candidate_groups": len(out),
            "candidate_keys_with_independent_input": len(independent_keys),
            "by_readiness": {s: sum(1 for g in out if g["readiness"] == s) for s in STATUSES},
            "independent_observations": sum(g["observations"] for g in out),
            "material_approvals_possible": len(approvals), "material_approvals_refused": len(refused),
            "keys_without_independent_input": {
                "count": len(set(excluded_keys) - independent_keys),
                "observations": sum(sum(c.values()) for k, c in excluded_keys.items() if k not in independent_keys),
                "reasons": dict(sorted(sum((c for k, c in excluded_keys.items() if k not in independent_keys),
                                           Counter()).items()))},
        },
        "next_groups": [g["candidate_group"] for g in nxt],
        "next_groups_definition": ("de eerste niet-AVAILABLE groepen in sorteervolgorde waarvoor build_kengetallen "
                                   "na alle menselijke stappen AVAILABLE geeft"),
        "least_work_group": least["candidate_group"] if least else None,
        "groups_reachable_with_existing_chain": ready_with_chain,
        "groups": out,
    }


# ------------------------------------------------------------------ markdown

def _sim_line(s):
    if not s:
        return "geen kengetalgroep"
    return (f"{s['status']}" + (f" {s['simulated_value_display']}" if s["simulated_value_display"] else "")
            + f" ({s['source_cluster_count']} clusters"
            + (f"; min {s['min_display']}, max {s['max_display']}" if s["min_display"] else "")
            + (", gemengde prijspeilen" if s["mixed_price_level"] else "")
            + (", ontbrekend prijspeil" if s["missing_price_level"] else "")
            + (f"; redenen {', '.join(s['insufficient_data_reasons'])}" if s["insufficient_data_reasons"] else "") + ")")


def render_md(rep):
    s = rep["summary"]
    L = ["# Kengetal-readiness v1", "",
         "Alleen analyse: niets toegepast, geen scoring of confidence. " + rep["definitions"]["human_actions"] + ".", "",
         "## Samenvatting", "",
         f"- candidate groups: **{s['candidate_groups']}** ({s['candidate_keys_with_independent_input']} candidate keys "
         f"met independent_input, {s['independent_observations']} observations)",
         f"- materiaalgoedkeuringen mogelijk via record_material_decision: {s['material_approvals_possible']}; "
         f"geweigerd: {s['material_approvals_refused']}",
         f"- candidate keys zonder independent_input (geen candidate group): {s['keys_without_independent_input']['count']} "
         f"({s['keys_without_independent_input']['observations']} observations; redenen "
         + ", ".join(f"{k} {v}" for k, v in s["keys_without_independent_input"]["reasons"].items()) + ")", "",
         "| readiness | groepen |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in s["by_readiness"].items()]
    lw = next((g for g in rep["groups"] if g["candidate_group"] == rep["least_work_group"]), None)
    L += ["", "Groepen die met de bestaande ketenschakels (record_material_decision + apply_family_decision) volledig "
          "af te ronden zijn: " + (", ".join(rep["groups_reachable_with_existing_chain"]) or "**geen**") + ".", "",
          f"Minste werk onder de eerstvolgende groepen: **{rep['least_work_group'] or '-'}**"
          + (f" ({lw['human_actions']['total']} menselijke acties; blockers {', '.join(lw['blockers'])})" if lw else "")
          + ".", "",
          f"## Eerstvolgende {len(rep['next_groups'])} niet-AVAILABLE groepen", "",
          f"Definitie: {rep['next_groups_definition']}.", ""]
    by = {g["candidate_group"]: g for g in rep["groups"]}
    for name in rep["next_groups"]:
        g = by[name]
        h = g["human_actions"]
        L += [f"### {g['rank']}. {name} - {g['readiness']}", "",
              f"- observations: {', '.join(g['observation_ids'])}",
              f"- clusters nu {g['independent_source_clusters']['count']}; na afronding "
              f"{g['potential_source_clusters_after_steps']['count']} "
              f"({', '.join(g['potential_source_clusters_after_steps']['ids'])})",
              f"- materiaalreview nodig: {', '.join(g['missing_material_approvals']) or '-'}"
              + (f"; geweigerd: {', '.join(g['material_approvals_refused'])}" if g["material_approvals_refused"] else ""),
              f"- open reviewfamilies nu: {', '.join(g['open_review_families_current']) or '-'}",
              "- te beslissen families na materiaalgoedkeuring: " + (", ".join(
                  f"{f['review_family_id']} ({', '.join(f['pair_ids'])})" for f in g["review_families_to_decide"]) or "-"),
              f"- paren buiten de reviewqueue: {', '.join(p['pair_id'] for p in g['pairs_outside_review_queue']) or '-'}",
              f"- blockers: {', '.join(g['blockers']) or '-'}",
              f"- menselijke acties: {h['total'] if h['total'] is not None else 'n.v.t.'}"
              + (f" (materiaal {h['material_approvals']}, families {h['review_family_decisions']}, paren buiten queue "
                 f"{h['pair_decisions_outside_review_queue']})" if h["total"] is not None else f" ({h.get('note')})"),
              f"- verwacht kengetal-effect: {_sim_line(g['expected_kengetal_effect'])}",
              f"- direct AVAILABLE na deze stappen: {'ja' if g['available_directly_after_steps'] else 'nee'}", ""]
    L += ["## Alle candidate groups", "",
          "| # | candidate group | readiness | materiaal (bekend/wacht/geen) | obs | clusters nu -> na | ACTIVE besluiten "
          "| open families nu | materiaalgoedkeuring | overige blockers | acties | direct AVAILABLE |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in rep["groups"]:
        ms, h = g["material_status"], g["human_actions"]
        L.append(f"| {g['rank']} | {g['candidate_group']} | {g['readiness']} | {ms['known']}/{ms['pending_approval']}/"
                 f"{ms['no_evidence']} | {g['observations']} | {g['independent_source_clusters']['count']} -> "
                 f"{g['potential_source_clusters_after_steps']['count']} | {len(g['active_human_decisions'])} | "
                 f"{len(g['open_review_families_current'])} | {len(g['missing_material_approvals'])} | "
                 f"{', '.join(g['other_blockers']) or '-'} | {h['total'] if h['total'] is not None else '-'} | "
                 f"{'ja' if g['available_directly_after_steps'] else 'nee'} |")
    L += ["", rep["note"], ""]
    return "\n".join(L)


def write(root):
    rep = build(root)
    with open(os.path.join(root, OUT_JSON), "w", encoding="utf-8", newline="\n") as f:
        f.write(crv.dump(rep))
    with open(os.path.join(root, OUT_MD), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(rep))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.check:
        ok = open(os.path.join(root, OUT_JSON), encoding="utf-8").read() == crv.dump(build(root))
        print("ACTUEEL" if ok else "NIET ACTUEEL")
        return 0 if ok else 1
    rep = write(root)
    print(f"{rep['summary']['candidate_groups']} candidate groups: {rep['summary']['by_readiness']}")
    print(f"volgende: {rep['next_groups']}; minste werk: {rep['least_work_group']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
