#!/usr/bin/env python3
"""
record_material_decision.py - menselijk materiaalbesluit voor EXACT opgesomde observations vastleggen.

Invoer: een besluitbestand van een mens:

    {
      "reviewer": "twandijkmans",
      "reviewed_at": "2026-09-29T12:00:00Z",
      "decision_reason": "...",
      "approvals": [
        {"observation_id": "PO-DOC-012-P015-L033", "material": "pvc",
         "evidence": {"element_description_original": "Hemelwaterafvoer pvc",
                      "action_text_original": "Vervangen hemelwaterafvoer pvc", "unit_original": "m1"}}
      ]
    }

Controles (anders wordt niets vastgelegd):
  - elke observation bestaat canoniek, heeft een elementkoppeling en nog GEEN materiaal (MATERIAL_UNKNOWN,
    leeg verified-materiaal) en nog geen ACTIVE materiaalbesluit;
  - het opgegeven bewijs is LETTERLIJK gelijk aan de observation (objectomschrijving, actietekst, eenheid);
  - het materiaal staat in vocabularies/material.json en komt als los woord letterlijk in de objectomschrijving
    voor; de objectomschrijving en actietekst noemen geen ander materiaal. Geen fuzzy matching, geen
    afleiding voor andere observations, geen documentbrede scope.

Vastlegging: per observation één record in data/review_decisions/material_decision_records.json
(append-only, schema material_decision_record.schema.json), gebonden aan de sha256 van de bronobservation
en van het brondocument. Daarna worden de genormaliseerde observations, comparability en kengetallen
herbouwd met de bestaande builders. Invarianten: alleen het materiaal van precies deze observations wijzigt;
alle andere observations en beoordelingen, bedragen, paren (observation-sets), source clusters, relaties en
de human decision store blijven gelijk; kengetallen inhoudelijk gelijk. Uitvoering als canonieke ketenschakel
(scripts/canonical_change.py) met rollback.

    python scripts/record_material_decision.py --decision besluit.json [--dry-run]
    python scripts/record_material_decision.py --rollback MATDEC-00001
"""
import argparse
import copy
import glob
import json
import os
import shutil
import sys
import tempfile

import jsonschema

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import canonical_change as cc  # noqa: E402
import document_registry as dr  # noqa: E402
import normalize_price_observations as npo  # noqa: E402
import promote_canonical_batch1 as pcb  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402
import record_relation_decision as rrd  # noqa: E402

STORE = npo.MATERIAL_DECISIONS_PATH
SCHEMA = os.path.join("schemas", "material_decision_record.schema.json")
EVIDENCE_FIELDS = (("element_description_original", ("element", "element_description_original")),
                   ("action_text_original", ("action", "action_text_original")),
                   ("unit_original", ("unit", "unit_original")))
EMPTY_STORE = {"store_version": "material_decisions_v1", "append_only": True,
               "description": "Menselijke materiaalbesluiten voor exacte observations (schema: "
                              "schemas/material_decision_record.schema.json). Append-only; alleen door een mens; "
                              "geen documentbrede scope. Een besluit vervalt als de bronobservation wijzigt.",
               "records": []}


class MaterialDecisionError(RuntimeError):
    pass


def _get(obj, path):
    for k in path:
        obj = obj[k]
    return obj


def load_store(root):
    path = os.path.join(root, STORE)
    return pr.load(path) if os.path.exists(path) else copy.deepcopy(EMPTY_STORE)


def validate(root, decision):
    """Returns de records die vastgelegd zouden worden. Schrijft niets."""
    for k in ("reviewer", "reviewed_at", "decision_reason", "approvals"):
        if not decision.get(k):
            raise MaterialDecisionError(f"besluit mist {k}")
    approvals = decision["approvals"]
    ids = [a["observation_id"] for a in approvals]
    if len(set(ids)) != len(ids):
        raise MaterialDecisionError("dubbele observation_ids in het besluit")
    source = {o["observation_id"]: o for o in pr.load(os.path.join(root, pr.PO_PATH))["observations"]}
    norm = {o["observation_id"]: o for o in pr.load(os.path.join(root, pr.NORM_PO_PATH))["observations"]}
    reg = dr.by_id(dr.load_registry(os.path.join(root, pr.REGISTRY)))
    vocab = npo.load_vocab_utf8(os.path.join(root, "vocabularies"), "material")
    store = load_store(root)
    active = {r["observation_id"] for r in store["records"] if r["status"] == "ACTIVE"}
    n = len(store["records"])
    records = []
    for a in approvals:
        oid = a["observation_id"]
        if oid not in source or oid not in norm:
            raise MaterialDecisionError(f"{oid}: geen canonieke observation")
        obs, nobs = source[oid], norm[oid]
        if obs["document_id"] not in reg:
            raise MaterialDecisionError(f"{oid}: document niet canoniek")
        if not obs["element"]["element_id"]:
            raise MaterialDecisionError(f"{oid}: geen elementkoppeling")
        m = nobs["material"]
        if m["material_status"] != "MATERIAL_UNKNOWN" or m["material_original"] or m["material_from_text"]:
            raise MaterialDecisionError(f"{oid}: heeft al een materiaal ({m['material_status']}); verified is leidend")
        if oid in active:
            raise MaterialDecisionError(f"{oid}: heeft al een ACTIVE materiaalbesluit")
        ev = a.get("evidence") or {}
        for field, path in EVIDENCE_FIELDS:
            if ev.get(field) != _get(nobs, path):
                raise MaterialDecisionError(f"{oid}: bewijs {field} {ev.get(field)!r} is niet letterlijk gelijk aan "
                                            f"de bron {_get(nobs, path)!r}")
        mat = a.get("material") or ""
        key = npo.lookup_key(mat)
        if not vocab.get(key):
            raise MaterialDecisionError(f"{oid}: materiaal {mat!r} staat niet (genormaliseerd) in vocabularies/material.json")
        element_tokens = npo.material_tokens(ev["element_description_original"], vocab)
        if key not in element_tokens:
            raise MaterialDecisionError(f"{oid}: {mat!r} komt niet als los woord voor in de objectomschrijving")
        other = {vocab[t] for t in element_tokens + npo.material_tokens(ev["action_text_original"], vocab)}
        if other != {vocab[key]}:
            raise MaterialDecisionError(f"{oid}: objectomschrijving/actietekst noemen ook ander materiaal: {sorted(other)}")
        p = next(r for r in nobs["source_ref"]["source_representations"] if r["role"] == "primary_financial_row")
        n += 1
        records.append({
            "decision_id": f"MDR-{n:05d}", "observation_id": oid, "document_id": obs["document_id"],
            "element_id": obs["element"]["element_id"], "scope": "EXACT_OBSERVATION",
            "material": {"original_value": key, "normalized_value": vocab[key]},
            "evidence": {"element_description_original": ev["element_description_original"],
                         "action_text_original": ev["action_text_original"], "unit_original": ev["unit_original"],
                         "material_token_in_element_text": key, "source_text": p.get("source_text"),
                         "page": p.get("page"), "line": p.get("line"), "sheet": p.get("sheet"), "row": p.get("row")},
            "source_observation_sha256": npo.observation_fingerprint(obs),
            "source_document_sha256": reg[obs["document_id"]]["sha256"],
            "decision_reason": decision["decision_reason"],
            "reviewer": {"reviewer_id": decision["reviewer"], "reviewer_type": "human"},
            "reviewed_at": decision["reviewed_at"], "status": "ACTIVE", "supersedes": None,
        })
    return records


def make_apply(decision, now):
    def apply_fn(root):
        fixed = {rel: pl.sha256_file(os.path.join(root, rel))
                 for rel in (pr.PO_PATH, pr.DECISIONS_PATH, rrd.RELATIONS_PATH)}
        records = validate(root, decision)
        targets = {r["observation_id"] for r in records}
        store = load_store(root)
        old_ids = [r["decision_id"] for r in store["records"]]
        store["records"].extend(records)
        schema = json.load(open(os.path.join(root, SCHEMA), encoding="utf-8"))
        errs = [e.message for e in jsonschema.Draft7Validator(schema).iter_errors(store)]
        if errs or [r["decision_id"] for r in store["records"][:len(old_ids)]] != old_ids:
            raise MaterialDecisionError(f"materiaalopslag ongeldig: {errs[:3]}")
        path = os.path.join(root, STORE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

        # genormaliseerd: alleen het materiaal van precies deze observations
        old_norm = {o["observation_id"]: o for o in pr.load(os.path.join(root, pr.NORM_PO_PATH))["observations"]}
        norm = npo.normalize(root, os.path.join(root, pr.PO_PATH))
        errs = npo.validate_output(norm, os.path.join(root, "schemas", "price_observation_normalized.schema.json"))
        if errs:
            raise MaterialDecisionError(f"normalized schemafouten: {errs[:3]}")
        new_norm = {o["observation_id"]: o for o in pcb.pv2.as_json(norm)["observations"]}
        if set(new_norm) != set(old_norm):
            raise MaterialDecisionError("INVARIANT: set observations gewijzigd")
        for oid, o in old_norm.items():
            n = new_norm[oid]
            if oid in targets:
                if {k: v for k, v in n.items() if k != "material"} != {k: v for k, v in o.items() if k != "material"}:
                    raise MaterialDecisionError(f"INVARIANT: {oid} wijzigt buiten het materiaal")
                if n["material"]["material_status"] != "MATERIAL_FROM_HUMAN_DECISION":
                    raise MaterialDecisionError(f"{oid}: materiaalbesluit niet toegepast")
            elif n != o:
                raise MaterialDecisionError(f"INVARIANT: andere observation gewijzigd: {oid}")
        pcb.write_json_lf(os.path.join(root, pr.NORM_PO_PATH), pcb.pv2.as_json(norm))

        # comparability: alleen de beoordeling van deze observations en hun paren
        old_comp = pr.load(os.path.join(root, pr.COMP_PATH))
        comp = bc.build(root)
        errs = bc.validate_output(comp, os.path.join(root, "schemas", "comparability.schema.json"))
        if errs:
            raise MaterialDecisionError(f"comparability schemafouten: {errs[:3]}")
        comp = pcb.pv2.as_json(comp)
        for key in ("source_clusters", "duplicate_documents", "same_source_links"):
            if comp[key] != old_comp[key]:
                raise MaterialDecisionError(f"INVARIANT: comparability '{key}' gewijzigd")
        old_pairs = {frozenset(p["observation_ids"]): p for p in old_comp["pairs"]}
        new_pairs = {frozenset(p["observation_ids"]): p for p in comp["pairs"]}
        if set(old_pairs) != set(new_pairs) or any(new_pairs[k]["pair_id"] != p["pair_id"] for k, p in old_pairs.items()):
            raise MaterialDecisionError("INVARIANT: paren (observation-sets / pair_ids) gewijzigd")
        changed_pairs = []
        for k, p in old_pairs.items():
            if k & targets:
                if new_pairs[k] != p:
                    changed_pairs.append({"pair_id": p["pair_id"], "class": [p["class"], new_pairs[k]["class"]],
                                          "observation_caveats": [p["observation_caveats"],
                                                                  new_pairs[k]["observation_caveats"]],
                                          "material_check": [p["checks"]["material"], new_pairs[k]["checks"]["material"]]})
            elif new_pairs[k] != p:
                raise MaterialDecisionError(f"INVARIANT: paar zonder doel-observation gewijzigd: {p['pair_id']}")
        old_a = {a["observation_id"]: a for a in old_comp["observations"]}
        new_a = {a["observation_id"]: a for a in comp["observations"]}
        for oid, a in old_a.items():
            if oid not in targets and pr._assess_without_derived(new_a[oid]) != pr._assess_without_derived(a):
                raise MaterialDecisionError(f"INVARIANT: beoordeling van andere observation gewijzigd: {oid}")
        for oid in targets:
            if "MATERIAL_UNKNOWN" in new_a[oid]["caveats"] or new_a[oid]["material"]["source"] != "human_material_decision":
                raise MaterialDecisionError(f"{oid}: MATERIAL_UNKNOWN niet opgeheven")
        pcb.write_json_lf(os.path.join(root, pr.COMP_PATH), comp)

        kg = rrd.supersede_kengetallen(root, now, expect_unchanged=True)
        for rel, sha in fixed.items():
            if pl.sha256_file(os.path.join(root, rel)) != sha:
                raise MaterialDecisionError(f"INVARIANT: {rel} gewijzigd")
        return {"material_decisions": [{k: r[k] for k in ("decision_id", "observation_id", "document_id",
                                                          "element_id", "material")} for r in records],
                "normalized_observations_changed": sorted(targets),
                "assessments_changed": {oid: {"material": [old_a[oid]["material"], new_a[oid]["material"]],
                                              "caveats": [old_a[oid]["caveats"], new_a[oid]["caveats"]]}
                                        for oid in sorted(targets)},
                "pairs_changed": changed_pairs,
                "tariff_groups_changed": comp["tariff_groups"] != old_comp["tariff_groups"],
                "price_observations": {"count": len(new_norm), "source_file_unchanged": True},
                "source_clusters": len(comp["source_clusters"]),
                "kengetallen": kg}
    return apply_fn


def next_change_id(root):
    n = len(glob.glob(os.path.join(root, pl.HISTORY_ROOT, "MATDEC-*"))) + 1
    return cc.unique_change_id(root, f"MATDEC-{n:05d}")


def record(root, decision, now=None):
    now = now or pr.now_utc()
    validate(root, decision)
    return cc.apply_change(root, next_change_id(root), "material_decision", make_apply(decision, now),
                           {"material_decision": decision}, now=now)


def dry_run(root, decision):
    with tempfile.TemporaryDirectory() as tmp:
        for rel in pr.SIMULATION_COPY:
            s, d = os.path.join(root, rel), os.path.join(tmp, rel)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            elif os.path.isfile(s):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
        return record(tmp, decision, now="2000-01-01T00:00:00Z")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        if args.rollback:
            print(cc.rollback(root, args.rollback))
            return 0
        if not args.decision:
            ap.error("--decision is verplicht")
        with open(args.decision, encoding="utf-8") as f:
            decision = json.load(f)
        state = (dry_run if args.dry_run else record)(root, decision)
        print(json.dumps(state["summary"], ensure_ascii=False, indent=2))
        print(("DRY-RUN OK " if args.dry_run else "VASTGELEGD ") + state["promotion_id"])
        return 0
    except (MaterialDecisionError, cc.ChangeError) as e:
        print(f"GEWEIGERD: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
