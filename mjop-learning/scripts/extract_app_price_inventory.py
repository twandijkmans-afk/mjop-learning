"""Leg de prijscomponenten van MJOP-App vast als reproduceerbare invoer voor de Kengetal Product Bridge Review.

Leest src/app.js en src/quantity.js van één of meer commits van een lokale MJOP-App-checkout (git show, geen netwerk) en
haalt de prijsliteralen eruit met Node (alleen de letterlijke array/object-literal wordt geëvalueerd, geen app-code):
ELEMENT_LIBRARY (kengetal/basis/perEenheid), KOZ_DEF, KOZ_MATERIAAL, steigertarieven, INDEXATIE_PCT en de CBS-tabel.
Daarnaast een paar feitelijke codecontroles (welke prijsvelden een invoerveld hebben, of offertes in elementCost
gebruikt worden). Er wordt niets aan de app veranderd.

De eerste commit is de referentie; voor elke volgende commit wordt vastgelegd of alle prijswaarden identiek zijn.

    python scripts/extract_app_price_inventory.py --app-repo ../MJOP-App --commits b77909a5 eaeb2568 \
        --out reports/pricing/inputs/mjop_app_price_inventory.json
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "reports" / "pricing" / "inputs" / "mjop_app_price_inventory.json"
LIBRARY_FIELDS = ("key", "naam", "categorie", "sfb", "type", "cyclus", "kengetal", "basis", "perEenheid", "bron",
                  "benadering", "optioneel", "aanbevolen")


def git_show(repo, commit, path):
    return subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], check=True, capture_output=True).stdout.decode("utf-8")


def full_sha(repo, commit):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", commit], check=True, capture_output=True, text=True).stdout.strip()


def literal(src, name, opener):
    """De letterlijke waarde van `var <name> = <opener>…;` (haakjes gebalanceerd, strings genegeerd)."""
    m = re.search(r"var " + re.escape(name) + r" = \s*" + re.escape(opener), src)
    if not m:
        raise ValueError(f"{name} niet gevonden")
    i, depth, quote = m.end() - 1, 0, None
    closer = {"[": "]", "{": "}"}[opener]
    for j in range(i, len(src)):
        c = src[j]
        if quote:
            if c == "\\":
                continue
            if c == quote and src[j - 1] != "\\":
                quote = None
        elif c in "'\"":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                assert c == closer
                return src[i:j + 1]
    raise ValueError(f"{name}: geen einde")


def js_eval(lit):
    out = subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(eval('(' + require('fs').readFileSync(0, 'utf8') + ')')))"],
                         input=lit.encode("utf-8"), check=True, capture_output=True).stdout
    return json.loads(out)


def number(src, pattern):
    m = re.search(pattern, src)
    if not m:
        raise ValueError(f"patroon {pattern!r} niet gevonden")
    return float(m.group(1)) if "." in m.group(1) else int(m.group(1))


def string(src, name):
    m = re.search(r"var " + re.escape(name) + r" = '([^']*)'", src)
    if not m:
        raise ValueError(f"{name} niet gevonden")
    return m.group(1)


def extract(repo, commit):
    app, qty = git_show(repo, commit, "src/app.js"), git_show(repo, commit, "src/quantity.js")
    lib = js_eval(literal(app, "ELEMENT_LIBRARY", "["))
    cost_fn = app[app.index("function elementCost("):app.index("function elementMeta(")]
    prices = {
        "element_library": [{k: d.get(k) for k in LIBRARY_FIELDS if k in d} for d in lib],
        "koz_def": js_eval(literal(app, "KOZ_DEF", "[")),
        "koz_materiaal": js_eval(literal(app, "KOZ_MATERIAAL", "{")),
        "scaffold": {"rate_low_eur_per_m2": number(qty, r"SCAFFOLD_RATE_LOW = (\d+)"),
                     "rate_high_eur_per_m2": number(qty, r"SCAFFOLD_RATE_HIGH = (\d+)"),
                     "height_threshold_m": number(qty, r"SCAFFOLD_HEIGHT_THRESHOLD = (\d+)")},
        "indexation": {"fallback_rate_per_year": number(app, r"var INDEXATIE_PCT = ([\d.]+)"),
                       "cbs_table": string(app, "CBS_TABEL"), "cbs_field": string(app, "CBS_VELD")},
    }
    facts = {
        "kengetal_input_handler": "'el-kengetal'" in app,
        "koz_eigen_tarief_handler": "'koz-tarief'" in app,
        "custom_bedrag_and_basisjaar_handlers": "'el-bedrag'" in app and "'el-basisjaar'" in app,
        "basis_or_per_eenheid_input_handler": bool(re.search(r"'el-(basis|pereenheid|perEenheid)'", app)),
        "werkhoogte_input_handler": "'el-werkhoogte'" in app,
        "offers_used_in_element_cost": bool(re.search(r"offerte", cost_fn, re.I)),
        "offers_stored_per_element": "offertes: {}" in app,
        "offer_comparison_fills_missing_lines_with_average": "Ontbrekende regels bijgevuld met het gemiddelde" in app,
        "library_costs_indexed_per_year": bool(re.search(r"case '(dak|gevel|per-unit|vast-variabel|steiger)'.*indexeerBedrag", cost_fn)),
        "custom_costs_indexed_from_basisjaar": "case 'custom': return indexeerBedrag(el.bedrag, el.basisjaar" in cost_fn,
        "ui_claims_offer_overrides_tariff": "een offerte overschrijft het tarief" in app,
        "ui_claims_current_year_price_level": "prijspeil ' + CURRENT_YEAR" in app,
        "ui_calls_defaults_kengetallen": "Kengetallen zijn indicatieve richtprijzen" in app,
        "ui_price_note_says_app_estimate": "app-schattingen" in app,
    }
    return {"commit": full_sha(repo, commit),
            "src_sha256": {"src/app.js": hashlib.sha256(app.encode("utf-8")).hexdigest(),
                           "src/quantity.js": hashlib.sha256(qty.encode("utf-8")).hexdigest()},
            "prices": prices, "price_values_sha256": hashlib.sha256(json.dumps(prices, sort_keys=True).encode()).hexdigest(),
            "code_facts": facts}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--app-repo", required=True)
    ap.add_argument("--commits", nargs="+", required=True)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    snaps = [extract(Path(a.app_repo), c) for c in a.commits]
    ref = snaps[0]
    out = {"inventory_version": "mjop_app_price_inventory_v1", "app_repository": "twandijkmans-afk/MJOP-App",
           "reference_commit": ref["commit"], "latest_commit": snaps[-1]["commit"],
           "price_values_identical_across_commits": all(s["price_values_sha256"] == ref["price_values_sha256"] for s in snaps),
           "snapshots": snaps}
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(snaps)} commits -> {p}; prijswaarden identiek: {out['price_values_identical_across_commits']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
