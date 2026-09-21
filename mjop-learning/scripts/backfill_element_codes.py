#!/usr/bin/env python3
"""
backfill_element_codes.py  (eenmalige migratie)

De 9 documenten die door onszelf zijn opgesteld (DOC-001,002,003,005,006,
007,008,009,010 - DOC-004 is van Innax en blijft overgeslagen) zijn
geextraheerd VOORDAT element_code aan schemas/element.schema.json is
toegevoegd. Dit script vult dat veld alsnog in data/extracted/*.json, met
twee methodes, in volgorde van betrouwbaarheid:

  A) Het element zelf citeert de code al letterlijk in een
     provenance.text_fragment (bijv. "2110 | Gevelafdekking natuursteen |
     Voorgevels woningen") - dit geldt voor bijna alle elementen in 8 van de
     9 documenten. Puur een regex op een al aanwezig, letterlijk citaat -
     geen nieuwe aanname.

  B) Fallback voor DOC-001 (handmatig opgebouwd vóór provenance-tracking,
     dus geen enkel text_fragment beschikbaar): de brontekst wordt opnieuw
     gescand op "code beschrijving"-regels (dezelfde 'Code Element Locatie
     HvhEhd Conditie'-tabelvorm als de andere 8 documenten) en positioneel
     gekoppeld aan de elements-array. Een koppeling telt alleen als de
     gescande beschrijving begint met element_type.original_value (of
     precies gelijk is) - bij twijfel geen koppeling.

Nooit gegokt: als geen van beide methodes een zekere match oplevert, blijft
element_code.normalized_value null en requires_human_review=True (zie
CLAUDE.md), i.p.v. de meest waarschijnlijke code te raden.

Gebruik:
    python3 scripts/backfill_element_codes.py --apply
(zonder --apply: alleen een dry-run rapport, geen bestanden aangepast)
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import extract_batch  # noqa: E402

CODE_PATTERN = re.compile(r"^\s*(\d{3,5}|ZZZZ)\s*[|]?\s*")

# DOC-004 is Innax, niet van onszelf - blijft buiten de backfill.
DOC_TO_RAW = {
    "DOC-001": ("data/raw/alkmaarstraat-1-83/9543_vvem_mop_14-01-2022_Pro VVEBeheer B.V._626720.pdf", "pdf"),
    "DOC-002": ("data/raw/jp-heijestraat/2026_Meerjarenonderhoudsplan_VvE 9690.pdf", "pdf"),
    "DOC-003": ("data/raw/jp-heijestraat/2026_Overzicht 15 - Jarenplan (Gedetailleerd)_VvE 9690.xls", "xls"),
    "DOC-005": ("data/raw/maldenhof/2026_Meerjarenonderhoudsplan_VvE 9261 Maldenhof 240-296.pdf", "pdf"),
    "DOC-006": ("data/raw/maldenhof/9261_vvem_mop_01-03-2023_Pro VVE Beheer B.V._851361.pdf", "pdf"),
    "DOC-007": ("data/raw/mauritstaete/Actualisatie MOP 2023 met bijlage.pdf", "pdf"),
    "DOC-008": ("data/raw/st-jacobstraat/Hoofd.pdf", "pdf"),
    "DOC-009": ("data/raw/st-jacobstraat/Woningen.pdf", "pdf"),
    "DOC-010": ("data/raw/zomerdijkstraat-14/Meerjarenonderhoudsplan 2023_VvE Zomerdijkstraat 14.pdf", "pdf"),
}

FIELDS_WITH_PROVENANCE = ["element_type", "element_name", "location", "quantity", "material", "unit"]

# DOC-001 handmatige overrides: deze 5 regels wrappen in de brontekst over
# een regeleinde heen (bijv. "...(incl.\nbereikbaarheid)"), waardoor de
# regel-regex ELEMENT_LINE ze mist. De code is per stuk geverifieerd tegen
# de brontekst (data/raw/alkmaarstraat-1-83/...pdf) voordat dit is
# toegevoegd - geen gok, alleen een regex-limiet omzeild.
DOC_001_MANUAL_OVERRIDES = {
    "DOC-001-EL-017": "4111",  # "4111 Gevelafwerking voegwerk platvol (incl.\nbereikbaarheid)"
    "DOC-001-EL-031": "4622",  # "4622 Binnenschilderwerk wanden (lambrisering)...\nstucwerk"
    "DOC-001-EL-054": "9999",  # "9999 Herinspectie (op basis van reeds aanwezige\ngegevens)"
    "DOC-001-EL-055": "9999",  # "9999 Bouwplaatsvoorzieningen en vergunningen t.b.v.\nbinnenschilderwerk"
    "DOC-001-EL-056": "9999",  # "9999 Vaste steiger t.b.v. schilderwerkzaamheden buiten\n(incl. precario en bouwplaatsvoorzieningen)"
}


def load_known_codes(vocab_dir):
    doc = json.load(open(os.path.join(vocab_dir, "element_code.json")))
    return {e["normalized_value"] for e in doc["entries"]}


def find_literal_code(element):
    """Methode A: zoek een al aanwezig, letterlijk code-citaat in een van de
    provenance.text_fragment-velden van dit element."""
    for field in FIELDS_WITH_PROVENANCE:
        f = element.get(field)
        if not isinstance(f, dict):
            continue
        prov = f.get("provenance")
        if not isinstance(prov, dict):
            continue
        tf = prov.get("text_fragment")
        if not tf:
            continue
        m = CODE_PATTERN.match(tf.strip())
        if m:
            return m.group(1), tf
    return None, None


HOOFDGROEP_LINE = re.compile(r"^(\d{2}|ZZ)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ /()\-]{2,60})$")
ELEMENT_LINE = re.compile(r"^(\d{3,5}|ZZZZ)\s+(.+?)\s+([\d.,]+)\s*(m1|m2|m3|st|pst|kg)\s+(\d)$")


def parse_ordered_code_lines(raw_text):
    """Methode B: scant de brontekst opnieuw op 'code beschrijving'-regels,
    in documentvolgorde."""
    rows = []
    for line in raw_text.splitlines():
        line = line.strip()
        m = ELEMENT_LINE.match(line)
        if m:
            rows.append((m.group(1), m.group(2).strip()))
    return rows


def align_positionally(elements, code_rows, window=5):
    """Koppelt elements[i] aan code_rows[j] alleen als code_rows[j]'s
    beschrijving met element_type.original_value begint - binnen een klein
    lookahead-venster, om kleine volgordeverschillen op te vangen zonder
    ooit een onzekere match te forceren."""
    results = {}
    j = 0
    for el in elements:
        et = (el.get("element_type") or {}).get("original_value") or ""
        et_norm = et.strip().lower()
        match_idx = None
        for k in range(j, min(j + window, len(code_rows))):
            code, desc = code_rows[k]
            if desc.strip().lower().startswith(et_norm) and et_norm:
                match_idx = k
                break
        if match_idx is not None:
            code, desc = code_rows[match_idx]
            results[el["element_id"]] = (code, desc)
            j = match_idx + 1
        else:
            results[el["element_id"]] = (None, None)
    return results


def backfill_document(doc_id, rec, known_codes, apply_changes):
    stats = {"literal": 0, "positional": 0, "manual_override": 0, "unmatched": 0}
    details = []

    unmatched_elements = []
    for el in rec.get("elements", []):
        code, source = find_literal_code(el)
        if code:
            stats["literal"] += 1
            details.append((el["element_id"], code, "literal", source))
            if apply_changes:
                set_element_code(el, code, known_codes, source)
        else:
            unmatched_elements.append(el)

    if unmatched_elements and doc_id in DOC_TO_RAW:
        raw_path, ftype = DOC_TO_RAW[doc_id]
        if os.path.exists(raw_path):
            raw_text = (
                extract_batch.extract_pdf_text(raw_path)
                if ftype == "pdf"
                else extract_batch.extract_spreadsheet_text(raw_path, ftype)
            )
            code_rows = parse_ordered_code_lines(raw_text)
            aligned = align_positionally(unmatched_elements, code_rows)
            for el in unmatched_elements:
                code, desc = aligned[el["element_id"]]
                if code:
                    stats["positional"] += 1
                    details.append((el["element_id"], code, "positional", desc))
                    if apply_changes:
                        set_element_code(el, code, known_codes, desc)
                elif el["element_id"] in DOC_001_MANUAL_OVERRIDES:
                    code = DOC_001_MANUAL_OVERRIDES[el["element_id"]]
                    stats["manual_override"] += 1
                    details.append((el["element_id"], code, "manual_override", "geverifieerd tegen brontekst, regel wrapt over regeleinde"))
                    if apply_changes:
                        set_element_code(el, code, known_codes, "manual_override: geverifieerd tegen brontekst")
                else:
                    stats["unmatched"] += 1
                    details.append((el["element_id"], None, "unmatched", (el.get("element_type") or {}).get("original_value")))
                    if apply_changes:
                        set_element_code(el, None, known_codes, None)

    return stats, details


def set_element_code(element, code, known_codes, source_fragment):
    if code is None:
        element["element_code"] = {
            "original_value": None,
            "normalized_value": None,
            "requires_human_review": True,
        }
        return
    normalized = code if code in known_codes else None
    field = {"original_value": code, "normalized_value": normalized}
    if normalized is None:
        field["requires_human_review"] = True
    element["element_code"] = field


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extracted-dir", default="data/extracted")
    ap.add_argument("--vocab-dir", default="vocabularies")
    ap.add_argument("--apply", action="store_true", help="zonder deze vlag: alleen rapporteren, niets wegschrijven")
    args = ap.parse_args()

    known_codes = load_known_codes(args.vocab_dir)

    totals = {"literal": 0, "positional": 0, "manual_override": 0, "unmatched": 0}
    for path in sorted(glob.glob(os.path.join(args.extracted_dir, "*.json"))):
        rec = json.load(open(path))
        doc_id = rec.get("document_id")
        if doc_id == "DOC-004" or doc_id not in DOC_TO_RAW:
            print(f"{doc_id}: overgeslagen (niet van onszelf of onbekend)")
            continue
        stats, details = backfill_document(doc_id, rec, known_codes, args.apply)
        for k in totals:
            totals[k] += stats[k]
        n = len(rec.get("elements", []))
        print(
            f"{doc_id}: {n} elements - literal={stats['literal']} positional={stats['positional']} "
            f"manual_override={stats['manual_override']} unmatched={stats['unmatched']}"
        )
        for eid, code, method, extra in details:
            if method == "unmatched":
                print(f"    ONOPGELOST {eid}: {extra!r} - geen code gevonden, blijft null + requires_human_review")
        if args.apply:
            json.dump(rec, open(path, "w"), ensure_ascii=False, indent=2)

    print()
    print(
        f"TOTAAL: literal={totals['literal']} positional={totals['positional']} "
        f"manual_override={totals['manual_override']} unmatched={totals['unmatched']}"
    )
    if not args.apply:
        print("(dry-run - voeg --apply toe om data/extracted/*.json daadwerkelijk te schrijven)")


if __name__ == "__main__":
    main()
