#!/usr/bin/env python3
"""
extract_batch.py  (SKELETON - stap 6 van de pipeline: RAW -> EXTRACTED)

Dit script is nog GEEN werkende LLM-extractie. Het zet de structuur en
bestandsvorm neer zodat een latere sessie (met jouw goedkeuring) de
TODO-blokken kan invullen met echte LLM-calls, zonder dat de architectuur
opnieuw bedacht hoeft te worden.

Wat dit script WEL al doet:
  - leest reports/document_inventory.json (output van inventory_documents.py)
  - maakt voor elk document in de batch een extracted-bestand aan in
    data/extracted/<document_id>.json met status "pending_extraction"
  - vult GEEN inhoudelijke velden - er wordt niets verzonnen (CLAUDE.md)

Wat hier NIET hoort (bewust niet geimplementeerd):
  - de daadwerkelijke LLM-call die tekst/tabellen omzet naar building/element/
    observation/maintenance_action-records volgens de schemas in schemas/
  - dat hoort hier te komen, met per record:
      * de brontekst/pagina die is gebruikt (-> provenance, zie
        schemas/_provenance.schema.json)
      * confidence-score van het model
      * requires_human_review=True zodra het model zelf onzeker is of een
        conflict signaleert (twee waarden voor hetzelfde gegeven)
    en NIET met:
      * een deterministische berekening door het taalmodel laten doen
        (kosten/indexatie hoort in normalize_batch.py, zie CLAUDE.md)
      * een aanname als een feit wegschrijven (ontbrekend -> null)

Gebruik:
    python3 scripts/extract_batch.py --batch batch_1
"""
import argparse
import json
import os


EXTRACTED_RECORD_TEMPLATE = {
    "status": "pending_extraction",
    "document_id": None,
    "building": None,           # -> vult building.schema.json in zodra geimplementeerd
    "elements": [],             # -> lijst van element.schema.json records
    "observations": [],         # -> lijst van observation.schema.json records
    "maintenance_actions": [],  # -> lijst van maintenance_action.schema.json records
    "extraction_notes": (
        "TODO: implementeer de LLM-extractiestap hier. Zie prompts/ voor de "
        "extractieprompt (aan te maken/te verfijnen samen met de gebruiker). "
        "Elk veld moet een ExtractedValue zijn (schemas/_extracted_value.schema.json) "
        "met provenance en confidence - nooit een los primitief veld."
    ),
}


def load_inventory(reports_dir):
    path = os.path.join(reports_dir, "document_inventory.json")
    if not os.path.exists(path):
        # val terug op het eerder aangeleverde batch1-overzicht als de
        # volledige inventory nog niet (opnieuw) is gedraaid
        alt = os.path.join(reports_dir, "mjop_inventaris.json")
        if os.path.exists(alt):
            return json.load(open(alt))
        raise SystemExit(
            f"Geen inventaris gevonden in {reports_dir}. Draai eerst "
            "scripts/inventory_documents.py."
        )
    return json.load(open(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="batch_1")
    ap.add_argument("--reports-dir", default="reports")
    ap.add_argument("--out-dir", default="data/extracted")
    args = ap.parse_args()

    inventory = load_inventory(args.reports_dir)
    os.makedirs(args.out_dir, exist_ok=True)

    created = 0
    for doc in inventory:
        doc_id = doc.get("document_id")
        if not doc_id:
            continue
        rec = dict(EXTRACTED_RECORD_TEMPLATE)
        rec["document_id"] = doc_id
        rec["batch"] = args.batch
        out_path = os.path.join(args.out_dir, f"{doc_id}.json")
        if os.path.exists(out_path):
            continue  # niet overschrijven - een mens of eerdere run kan hier al iets in hebben staan
        json.dump(rec, open(out_path, "w"), ensure_ascii=False, indent=2)
        created += 1

    print(f"{created} placeholder-extractiebestanden aangemaakt in {args.out_dir}/")
    print("LET OP: dit script bevat nog geen echte extractie (zie TODO's in dit bestand).")


if __name__ == "__main__":
    main()
