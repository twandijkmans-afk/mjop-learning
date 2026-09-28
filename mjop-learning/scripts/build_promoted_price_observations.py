#!/usr/bin/env python3
"""
build_promoted_price_observations.py  (CLOUD-ONLY PO-PROMOTIE - uitsluitend batch1_v1)

Batch 1 cloud promotion gebruikt de reeds gevalideerde Xpdf-derived PO values;
het voert geen nieuwe PDF parsing uit.

  - Waardebron (onveranderlijk): de canonieke data/price_observations/price_observations_batch1.json
    (met xpdf 4.06 gebouwd): observation_id, bronpagina/-regel, bronweergaven, bedragen,
    hoeveelheid/eenheid, Stj/Cy, prijspeil/BTW.
  - Koppelbron: de gevalideerde deterministische handoff-laag data/extracted_deterministic/batch1_v1
    (manifest v1.1, --check verplicht groen): extraction_link, element_id, interne elementcode en
    actienormalisatie, via EXACTE koppeling (pagina + brontekst, daarna volledige actietekst +
    hoeveelheid, daarna elementcontext; bewezen identieke rijen blijven een expliciete
    multiset-groep) - zie promotion_v2_dry_run.relink.

Weigert (PromotionError, exitcode 1) als:
  - de handoff-laag ongeldig is (manifest, hashes, source_sha256);
  - een bronbestand van de PO niet overeenkomt met document_registry;
  - het aantal observations != 404 of een observation_id verdwijnt of nieuw is;
  - een bedrag/hoeveelheid/eenheid/Stj/Cy/bronweergave verandert;
  - een observation geen verklaarde koppeling heeft (geen kandidaat, of ambigu zonder bewijs
    dat de kandidaatrijen identiek zijn, of bedragen die afwijken van batch1_v1).

Dit is GEEN generieke extractor voor toekomstige documenten: het werkt alleen voor deze
geversioneerde batch1_v1 en de bijbehorende 404 canonieke observations. Schrijft nooit in
canonieke mappen.

Gebruik:
    python3 scripts/build_promoted_price_observations.py [--out PAD]
"""
import argparse
import copy
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote_deterministic_batch as pdb  # noqa: E402
import promotion_v2_dry_run as pv2  # noqa: E402

TOOL_VERSION = "build_promoted_price_observations_v1.0.0"
EXPECTED_OBSERVATIONS = 404
STATEMENT = ("Batch 1 cloud promotion gebruikt de reeds gevalideerde Xpdf-derived PO values; het voert geen "
             "nieuwe PDF parsing uit.")
DEFAULT_OUT = os.path.join("data", "promotion_v3_dry_run", "batch1_v1", "price_observations_batch1_promoted.json")
# alles wat uit de xpdf-bronlaag komt en niet mag veranderen
IMMUTABLE_FIELDS = ("document_id", "source_file", "unit_original", "unit_normalized", "quantity_as_stated",
                    "quantity_value", "total_as_stated", "total_value", "amount_reconciliation", "total_scope",
                    "occurrences_in_window", "annual_amounts", "planned_years", "execution_window_start",
                    "execution_window_end", "cycle_start_year", "cycle_start_year_as_stated", "cycle_length_years",
                    "cycle_length_as_stated", "price_type", "unit_price_literal", "unit_price_calculated",
                    "calculated_unit_price_basis", "price_level_date", "price_level_basis", "vat_basis", "vat_text",
                    "vat_rate_text", "indexation_statement", "source_representations", "dependency_status",
                    "relation_ids", "document_relation_ids")
IMMUTABLE_ELEMENT_FIELDS = ("element_code_original", "element_description_original", "element_location_original")
EXPLAINED_LINKS = {"unique", "unique_by_action_text", "unique_by_element_context"}


class PromotionError(RuntimeError):
    def __init__(self, message, violations=None):
        super().__init__(message)
        self.violations = violations or []


def check_sources(root, po):
    registry = {d["document_id"]: d for d in pdb.load_json(os.path.join(root, "reports", "document_registry.json"))["documents"]}
    bad = []
    for d in po["documents"]:
        reg = registry.get(d["document_id"])
        if reg is None or reg["sha256"] != d["sha256"] or reg["relative_path"] != d["relative_path"]:
            bad.append(f"{d['document_id']}: PO-bronbestand wijkt af van document_registry")
    for o in po["observations"]:
        if o["source_file"]["sha256"] != registry[o["document_id"]]["sha256"]:
            bad.append(f"{o['observation_id']}: source_file.sha256 wijkt af van document_registry")
    return bad


def invariant_violations(old_po, new_po, link_info, expected=EXPECTED_OBSERVATIONS):
    v = []
    old = {o["observation_id"]: o for o in old_po["observations"]}
    new = {o["observation_id"]: o for o in new_po["observations"]}
    if len(old_po["observations"]) != expected or len(new_po["observations"]) != expected:
        v.append(f"observation count {len(old_po['observations'])}/{len(new_po['observations'])} != {expected}")
    if set(old) - set(new):
        v.append(f"observation_id verdwenen: {sorted(set(old) - set(new))}")
    if set(new) - set(old):
        v.append(f"observation_id nieuw: {sorted(set(new) - set(old))}")
    for oid in sorted(set(old) & set(new)):
        a, b = old[oid], new[oid]
        changed = [f for f in IMMUTABLE_FIELDS if a.get(f) != b.get(f)]
        changed += [f"element.{f}" for f in IMMUTABLE_ELEMENT_FIELDS if a["element"].get(f) != b["element"].get(f)]
        if a["action"]["action_text_original"] != b["action"]["action_text_original"]:
            changed.append("action.action_text_original")
        if changed:
            v.append(f"{oid}: bronwaarden veranderd {changed}")
        li = link_info.get(oid) or {}
        if li.get("link") in EXPLAINED_LINKS:
            if li.get("amounts_equal") is not True:
                v.append(f"{oid}: bedragen wijken af van batch1_v1")
        elif li.get("link") == "ambiguous":
            if not (li.get("identical_rows") and li.get("amounts_equal")):
                v.append(f"{oid}: ambigue koppeling zonder bewijs van identieke rijen")
        else:
            v.append(f"{oid}: geen verklaarde koppeling ({li.get('link')})")
    return v


def build_promoted(root):
    """Returns (promoted_po, link_info, normalized, verified, accept_simulation). Schrijft niets."""
    check = pdb.check_handoff(root)
    if not check["ok"]:
        raise PromotionError("handoff-laag ongeldig", check["errors"])
    new_records = {d: pdb.load_json(os.path.join(root, pdb.BATCH_DIR, f"{d}.json")) for d in pdb.EXPECTED_PASS}
    old_po = pdb.load_json(os.path.join(root, pv2.PO_PATH))
    bad = check_sources(root, old_po)
    if bad:
        raise PromotionError("bronbestanden van de canonieke PO kloppen niet", bad)
    normalized, _ = pv2.build_normalized(root, new_records)
    verified, accept_sim = pv2.simulate_verified(root, normalized, new_records)
    new_po, link_info = pv2.relink(old_po, verified, new_records)
    violations = invariant_violations(old_po, new_po, link_info)
    if violations:
        raise PromotionError(f"{len(violations)} invariant(en) geschonden", violations)
    new_po = copy.deepcopy(new_po)
    new_po["promotion"] = {
        "tool_version": TOOL_VERSION, "statement": STATEMENT, "scope": "uitsluitend batch1_v1 (geen generieke extractor)",
        "value_source": pv2.PO_PATH.replace(os.sep, "/"),
        "value_source_sha256": pdb.sha256_file(os.path.join(root, pv2.PO_PATH)),
        "link_source": pdb.BATCH_DIR.replace(os.sep, "/"), "manifest_version": check["manifest"]["manifest_version"],
        "manifest_sha256": pdb.sha256_file(os.path.join(root, pdb.BATCH_DIR, "manifest.json")),
        "link_method": pv2.LINK_METHOD, "observations": len(new_po["observations"]),
        "link_counts": dict(sorted(Counter(i["link"] for i in link_info.values()).items())),
    }
    return new_po, link_info, normalized, verified, accept_sim


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    out = os.path.join(args.root, args.out)
    for d in ("extracted", "normalized", "verified", "price_observations", "comparability", "kengetallen"):
        if os.path.realpath(out).startswith(os.path.realpath(os.path.join(args.root, "data", d)) + os.sep):
            print(f"WEIGERING: {args.out} ligt in een canonieke map (canonieke promotie is een aparte stap)")
            return 2
    try:
        po, _, _, _, _ = build_promoted(args.root)
    except PromotionError as e:
        print(f"GEWEIGERD: {e}")
        for v in e.violations[:50]:
            print(f"  - {v}")
        return 1
    pdb.write_json(out, po)
    print(f"{STATEMENT}\n{po['promotion']['observations']} observations -> {args.out}  links: {po['promotion']['link_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
