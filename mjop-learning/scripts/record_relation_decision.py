#!/usr/bin/env python3
"""
record_relation_decision.py - een MENSELIJK relatiebesluit vastleggen in document_relations.json.

Invoer: het reviewpakket van scripts/prepare_relation_review.py (sha256-gebonden) en het besluit van een mens
(optie uit dat pakket, bijv. DUPLICATE_OTHER_BYTES). Het besluit wordt vertaald naar het BESTAANDE relatietype
van die optie (DUPLICATE_OTHER_BYTES -> duplicate_source); er komen geen nieuwe relatietypen bij.

Controles (het bewijs mag het besluit niet tegenspreken, anders wordt niets vastgelegd):
  - het pakket is ongewijzigd (sha256) en gaat over precies dit document en deze tegenhanger;
  - de tegenhanger is canoniek; er bestaat nog geen relatie tussen beide;
  - DUPLICATE_OTHER_BYTES: andere bytes, alle objectmetadata gelijk, elementen en condities gelijk,
    alle price-observation-rijen exact gelijk (geen gedeeltelijke of unieke rijen), gelijke sommen.
  - een relatie die al logisch volgt (bijv. X duplicate_source B en B version_of_same_mjop C) wordt NIET
    apart toegevoegd; ze staat alleen als afgeleide verwijzing bij het besluit.

Uitvoering als canonieke ketenschakel (scripts/canonical_change.py): snapshot, wijziging, invarianten,
rollback mogelijk. Na de wijziging worden comparability en kengetallen herbouwd met de bestaande builders;
invarianten: price observations (bron en genormaliseerd) byte-gelijk, paren/observation-beoordelingen/
source clusters gelijk, decision store ongewijzigd, kengetallen inhoudelijk gelijk.

    python scripts/record_relation_decision.py --document DOC-014 --primary DOC-006 \\
        --option DUPLICATE_OTHER_BYTES --reviewer twandijkmans --reason "..." \\
        [--package reports/review/relation_review_DOC-014.json] [--dry-run]
    python scripts/record_relation_decision.py --rollback RELDEC-DREL-005
"""
import argparse
import copy
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_comparability as bc  # noqa: E402
import build_kengetallen as bk  # noqa: E402
import canonical_change as cc  # noqa: E402
import document_registry as dr  # noqa: E402
import prepare_relation_review as rr  # noqa: E402
import promote_canonical_batch1 as pcb  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402

RELATIONS_PATH = os.path.join("data", "price_observations", "document_relations.json")
OPTION_TO_TYPE = {o["option"]: o["existing_relation_type"] for o in rr.OPTIONS}
SUPPORTED_OPTIONS = ("DUPLICATE_OTHER_BYTES",)          # v1: alleen wat nu besloten wordt
METADATA_FIELDS = rr.META_DOC + rr.META_BUILDING


class DecisionError(RuntimeError):
    pass


def _load(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return json.load(f)


def _pair_relations(relations, a, b):
    return [r for r in relations if {a, b} <= set(r.get("document_ids", [])) |
            {r.get("primary_document_id"), r.get("secondary_document_id")} - {None}]


def evidence_errors(package, document, primary):
    """Tegenspreekt het pakket DUPLICATE_OTHER_BYTES? Lijst met redenen (leeg = consistent)."""
    comp = package["comparisons"].get(f"{document}_vs_{primary}")
    if comp is None:
        return [f"pakket vergelijkt {document} niet met {primary}"]
    errs = []
    if comp["same_bytes"]:
        errs.append("zelfde bytes: dat is een exacte duplicate, geen DUPLICATE_OTHER_BYTES")
    for f in METADATA_FIELDS:
        vals = package["metadata"].get(f, {})
        if (vals.get(document) or {}).get("value") != (vals.get(primary) or {}).get("value"):
            errs.append(f"metadata {f} verschilt")
    el = comp["elements"]
    if el["only_first"] or el["only_second"] or el["condition_differences"]:
        errs.append("elementen of condities verschillen")
    po = comp["price_observations"]
    if po["partial_matches"] or po["only_first"] or po["only_second"] or \
            po["exact_matches"] != po["count"][0] or po["count"][0] != po["count"][1] or not po["exact_matches"]:
        errs.append("price-observation-rijen niet allemaal exact gelijk")
    if po["sum_totals"][0] != po["sum_totals"][1]:
        errs.append("sommen verschillen")
    return errs


def evidence_text(package, document, primary):
    comp = package["comparisons"][f"{document}_vs_{primary}"]
    m = package["metadata"]
    v = lambda f: (m[f].get(primary) or {}).get("value")  # noqa: E731
    po, el, tl = comp["price_observations"], comp["elements"], comp["text_layer"]
    return (f"Menselijk besluit op reviewpakket {package['review_version']}: zelfde object "
            f"{v('object_name')}, {v('address')}, {v('object_postcode')} {v('object_city')}; bouwjaar "
            f"{v('construction_year')}, {v('number_of_units')} eenheden; prijspeil {v('price_level_date')}, "
            f"inspectiedatum {v('inspection_date')}; BTW- en indexatietekst gelijk. Elementen {el['common']}/"
            f"{el['count'][1]} gelijk, 0 conditieverschillen. Price-observation-rijen {po['exact_matches']}/"
            f"{po['count'][1]} exact gelijk (elementcode, actie, hoeveelheid, eenheid, Stj, Cy, jaarbedragen); "
            f"som {po['sum_totals'][0]} = {po['sum_totals'][1]}. Bytes verschillen "
            f"({package['sources'][document]['sha256'][:12]} vs {package['sources'][primary]['sha256'][:12]}); "
            f"tekstlaag: {tl['lines_only_first']}/{tl['lines_only_second']} regels alleen in één van beide "
            f"(weergave/rendering).")


def build_relation(root, package_rel, document, primary, option, reviewer, reason, now):
    package_path = os.path.join(root, package_rel)
    package = _load(root, package_rel)
    rel_doc = _load(root, RELATIONS_PATH)
    relations = rel_doc["relations"]
    if option not in SUPPORTED_OPTIONS:
        raise DecisionError(f"optie {option!r} wordt door deze tool (v1) niet vastgelegd; ondersteund: "
                            f"{list(SUPPORTED_OPTIONS)}")
    rtype = OPTION_TO_TYPE[option]
    if rtype not in rel_doc["relation_types"]:
        raise DecisionError(f"relatietype {rtype} bestaat niet in document_relations.json")
    if package.get("document") != document or primary not in package.get("against", []):
        raise DecisionError("reviewpakket gaat niet over dit document / deze tegenhanger")
    if package.get("decision") is not None:
        raise DecisionError("reviewpakket bevat al een besluit")
    reg = dr.by_id(dr.load_registry(os.path.join(root, pr.REGISTRY)))
    if primary not in reg:
        raise DecisionError(f"{primary} is niet canoniek")
    if document in reg:
        raise DecisionError(f"{document} is al canoniek; een duplicate_source-secundair document hoort geen "
                            f"zelfstandige canonieke bron te zijn")
    if package["sources"][primary]["sha256"] != reg[primary]["sha256"]:
        raise DecisionError(f"pakket verwijst naar andere bytes van {primary} dan het register")
    if _pair_relations(relations, document, primary):
        raise DecisionError(f"er bestaat al een relatie tussen {document} en {primary}")
    if any(r.get("secondary_document_id") == document for r in relations):
        raise DecisionError(f"{document} is al secundair document van een andere relatie")
    errs = evidence_errors(package, document, primary)
    if errs:
        raise DecisionError(f"het bewijs spreekt {option} tegen: {errs}")
    rid = f"DREL-{max(int(r['relation_id'].split('-')[1]) for r in relations) + 1:03d}"
    implied = []
    for other in package["against"]:
        if other == primary:
            continue
        via = _pair_relations(relations, primary, other)
        if via:
            implied.append({"document_id": other, "via": [rid] + [r["relation_id"] for r in via],
                            "note": f"{document} is duplicate_source van {primary}; de relatie met {other} volgt "
                                    f"daaruit en wordt niet apart vastgelegd."})
    relation = {
        "relation_id": rid,
        "type": rtype,
        "primary_document_id": primary,
        "secondary_document_id": document,
        "confidence": "certain",
        "evidence": evidence_text(package, document, primary),
        "row_level_verification": (f"rij-voor-rij geverifieerd: "
                                   f"{package['comparisons'][f'{document}_vs_{primary}']['price_observations']['exact_matches']}"
                                   f" exacte rijen, 0 gedeeltelijk, 0 uniek (prepare_relation_review.py)"),
        "decision": {
            "option": option,
            "decided_by": {"reviewer_id": reviewer, "reviewer_type": "human"},
            "decided_at": now,
            "decision_reason": reason,
            "review_package": package_rel.replace(os.sep, "/"),
            "review_package_sha256": pl.sha256_file(package_path),
            "source_batch_id": package.get("batch_id"),
            "secondary_sha256": package["sources"][document]["sha256"],
            "primary_sha256": package["sources"][primary]["sha256"],
            "implied_relations": implied,
            "effect": "Het secundaire document levert GEEN eigen price observations, telt niet als onafhankelijke "
                      "bron, krijgt geen eigen source cluster en wordt niet als zelfstandige canonieke "
                      "observation-bron gepromoveerd.",
        },
    }
    return relation


def _relations_text(root, relation):
    """Voegt de relatie tekstueel toe (bestaande opmaak blijft byte-gelijk) en controleert de inhoud."""
    path = os.path.join(root, RELATIONS_PATH)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    old = json.loads(text)
    tail = "\n  ]\n}"
    stripped = text.rstrip("\n")
    if not stripped.endswith(tail):
        raise DecisionError("onverwachte opmaak van document_relations.json")
    body = json.dumps(relation, ensure_ascii=False, indent=2)
    body = "\n".join("    " + line for line in body.split("\n"))
    new_text = stripped[: -len(tail)] + ",\n" + body + tail + "\n"
    expected = copy.deepcopy(old)
    expected["relations"].append(relation)
    if json.loads(new_text) != expected:
        raise DecisionError("tekstuele toevoeging wijkt af van de verwachte inhoud")
    return new_text


def supersede_kengetallen(root, now, expect_unchanged):
    kg_path = os.path.join(root, pr.KG_PATH)
    kg_before = pr.load(kg_path)
    kg_new = bk.build(root, generated_at=now)
    errs = bk.validate_output(kg_new, os.path.join(root, "schemas", "kengetal.schema.json"))
    if errs:
        raise DecisionError(f"kengetallen schemafouten: {errs[:3]}")
    changed = (kg_new["kengetallen"], kg_new["summary"]) != (kg_before["kengetallen"], kg_before["summary"])
    if expect_unchanged and changed:
        raise DecisionError("INVARIANT: kengetallen inhoudelijk gewijzigd")
    old_sha = pl.sha256_file(kg_path)
    hist = os.path.join(os.path.dirname(kg_path), "history",
                        os.path.basename(kg_path).replace(".json", f".{old_sha[:12]}.json"))
    os.makedirs(os.path.dirname(hist), exist_ok=True)
    shutil.copyfile(kg_path, hist)
    kg_new["supersedes"] = {"file": os.path.relpath(hist, root).replace("\\", "/"), "sha256": old_sha}
    with open(kg_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(bk.dump(kg_new))
    return {"before": pr._kg_summary(kg_before), "after": pr._kg_summary(kg_new), "content_changed": changed}


def make_apply(relation, now):
    def apply_fn(root):
        fixed = {rel: pl.sha256_file(os.path.join(root, rel)) for rel in (pr.PO_PATH, pr.NORM_PO_PATH, pr.DECISIONS_PATH)}
        old_comp = pr.load(os.path.join(root, pr.COMP_PATH))
        new_text = _relations_text(root, relation)
        with open(os.path.join(root, RELATIONS_PATH), "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)
        comp = bc.build(root)
        errs = bc.validate_output(comp, os.path.join(root, "schemas", "comparability.schema.json"))
        if errs:
            raise DecisionError(f"comparability schemafouten: {errs[:3]}")
        for key in ("summary", "source_clusters", "observations", "pairs", "same_source_links", "tariff_groups"):
            if comp[key] != old_comp[key]:
                raise DecisionError(f"INVARIANT: comparability '{key}' gewijzigd door het relatiebesluit")
        added = [d for d in comp["duplicate_documents"] if d not in old_comp["duplicate_documents"]]
        if [d for d in old_comp["duplicate_documents"] if d not in comp["duplicate_documents"]] or \
                [d["document_id"] for d in added] != [relation["secondary_document_id"]]:
            raise DecisionError("INVARIANT: duplicate_documents wijzigt anders dan alleen het nieuwe duplicaat")
        pcb.write_json_lf(os.path.join(root, pr.COMP_PATH), comp)
        kg = supersede_kengetallen(root, now, expect_unchanged=True)
        for rel, sha in fixed.items():
            if pl.sha256_file(os.path.join(root, rel)) != sha:
                raise DecisionError(f"INVARIANT: {rel} gewijzigd")
        po = pr.load(os.path.join(root, pr.PO_PATH))
        return {"relation": {k: relation[k] for k in ("relation_id", "type", "primary_document_id",
                                                     "secondary_document_id")},
                "price_observations": {"before": len(po["observations"]), "added": 0,
                                       "after": len(po["observations"]),
                                       "of_secondary_document": sum(o["document_id"] == relation["secondary_document_id"]
                                                                    for o in po["observations"])},
                "source_clusters": {"before": len(old_comp["source_clusters"]), "after": len(comp["source_clusters"])},
                "duplicate_documents_added": added,
                "kengetallen": kg,
                "note": "price_observations_batch1.json is ongewijzigd (inclusief de ingebedde document_relations-"
                        "momentopname van de bronlaag): het secundaire document is niet canoniek en levert geen "
                        "observations; de relatie werkt via document_relations.json in comparability (source "
                        "clusters/duplicaten) en in de incoming-promotie (SKIPPED_DUPLICATE)."}
    return apply_fn


def record(root, document, primary, option, reviewer, reason, package_rel=None, now=None):
    now = now or pr.now_utc()
    package_rel = package_rel or os.path.join("reports", "review", f"relation_review_{document}.json")
    relation = build_relation(root, package_rel, document, primary, option, reviewer, reason, now)
    change_id = cc.unique_change_id(root, f"RELDEC-{relation['relation_id']}")
    return cc.apply_change(root, change_id, "relation_decision", make_apply(relation, now),
                           {"relation": relation}, now=now)


def dry_run(root, document, primary, option, reviewer, reason, package_rel=None):
    """Volledige uitvoering op een tijdelijke kopie; het echte repo blijft onaangeroerd."""
    with tempfile.TemporaryDirectory() as tmp:
        for rel in pr.SIMULATION_COPY + ("reports/review",):
            s, d = os.path.join(root, rel), os.path.join(tmp, rel)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            elif os.path.isfile(s):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
        return record(tmp, document, primary, option, reviewer, reason, package_rel, now="2000-01-01T00:00:00Z")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--document")
    ap.add_argument("--primary")
    ap.add_argument("--option", choices=list(OPTION_TO_TYPE))
    ap.add_argument("--reviewer")
    ap.add_argument("--reason")
    ap.add_argument("--package")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        if args.rollback:
            print(cc.rollback(root, args.rollback))
            return 0
        if not all((args.document, args.primary, args.option, args.reviewer, args.reason)):
            ap.error("--document, --primary, --option, --reviewer en --reason zijn verplicht")
        fn = dry_run if args.dry_run else record
        state = fn(root, args.document, args.primary, args.option, args.reviewer, args.reason, args.package)
        print(json.dumps(state["summary"], ensure_ascii=False, indent=2))
        print(("DRY-RUN OK " if args.dry_run else "VASTGELEGD ") + state["promotion_id"])
        return 0
    except (DecisionError, cc.ChangeError) as e:
        print(f"GEWEIGERD: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
