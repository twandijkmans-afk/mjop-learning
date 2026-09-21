#!/usr/bin/env python3
"""
extract_batch.py  (stap 6 van de pipeline: RAW -> EXTRACTED)

Leest een brondocument uit data/raw/ (tekst + tabellen, paginagewijs), stuurt
dat naar een LLM via tool-use met een schema-afgeleid input-schema, en
valideert de output tegen de echte JSON-schemas in schemas/ voordat er iets
wordt weggeschreven naar data/extracted/<document_id>.json.

Ontwerp (afgestemd met de gebruiker voordat dit is geimplementeerd, zie
CLAUDE.md sectie "Architectuurkeuzes met grote gevolgen"):

  - Per document: paginagewijze tekst + tabellen (pdfplumber voor pdf,
    openpyxl/xlrd voor xls/xlsx) met expliciete pagina-/tabelmarkers, zodat
    het model kan citeren met paginanummer/tabelindex voor provenance.
  - Tool-use met een input-schema dat elk veld verplicht in ExtractedValue-
    vorm afdwingt (value, confidence, requires_human_review, provenance) -
    geen los primitief veld mogelijk. Dit is een HANDGESCHREVEN, op zichzelf
    staand schema (geen externe $ref's, dat ondersteunt de Claude tool-API
    niet) - de ECHTE poort is de validatie tegen schemas/*.schema.json erna.
  - Na ontvangst: schema-validatie tegen de echte schemas (jsonschema). Bij
    een schemafout (vorm, geen feiten) 1 herhaling met de foutmelding
    teruggekoppeld; faalt het opnieuw -> status "extraction_failed",
    requires_human_review=True, geen placeholder-data.
  - Deterministische ondergrens (enforce_review_floor): requires_human_review
    wordt ALTIJD True als confidence < 0.6, source_confidence == "low", of
    conflict == True - los van wat het model zelf claimt. Bubbelt omhoog naar
    het dichtstbijzijnde niveau dat een requires_human_review-veld heeft
    (bijv. van unit_cost.provenance naar maintenance_action).
  - strip_normalization forceert normalized_value=None voor elk
    original/normalized-paar, ONGEACHT wat het model teruggeeft: de
    daadwerkelijke vocabulaire-mapping gebeurt uitsluitend, deterministisch,
    in normalize_batch.py.
  - Vocabularies worden alleen als CONTEXT meegegeven in de prompt (bekende
    categorieen + notities zoals gemeenschappelijk/prive niet samenvoegen),
    nooit als mapping-stap in dit script.
  - Berekeningen (direct_cost_calculated, indexatie) worden hier NIET gedaan
    - dat blijft in normalize_batch.py (CLAUDE.md: nooit door het
      taalmodel laten uitrekenen).
  - AI-output wordt geversioneerd: extraction_model, extraction_prompt_version,
    extracted_at, temperature staan in elk extracted-bestand.

Gebruik:
    python3 scripts/extract_batch.py --batch batch_1
    Vereist ANTHROPIC_API_KEY in de omgeving voor echte extractie; zonder key
    (of met --dry-run) worden alleen placeholders aangemaakt, zoals voorheen.
"""
import argparse
import copy
import json
import os
from datetime import datetime, timezone

import jsonschema

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_VERSION = "v1"
DEFAULT_MODEL = os.environ.get("MJOP_EXTRACTION_MODEL", "claude-opus-5")
REVIEW_THRESHOLD = 0.6


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


# ---------------------------------------------------------------------------
# Documenttekst inlezen (pdf / xls / xlsx), paginagewijs met tabelmarkers
# ---------------------------------------------------------------------------

def extract_pdf_text(path):
    import pdfplumber

    pages_out = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages_out.append(f"--- PAGINA {page_num} ---\n{text}")
            for table_index, table in enumerate(page.extract_tables()):
                rows = "\n".join(
                    " | ".join("" if cell is None else str(cell) for cell in row)
                    for row in table
                )
                pages_out.append(f"[TABEL {table_index} OP PAGINA {page_num}]\n{rows}")
    return "\n\n".join(pages_out)


def extract_spreadsheet_text(path, file_type):
    sheets_out = []
    if file_type == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(path, data_only=True)
        for sheet in wb.worksheets:
            rows = [
                " | ".join("" if cell is None else str(cell) for cell in row)
                for row in sheet.iter_rows(values_only=True)
            ]
            sheets_out.append(f"--- TABBLAD {sheet.title} ---\n" + "\n".join(rows))
    else:  # xls
        import xlrd

        wb = xlrd.open_workbook(path)
        for sheet in wb.sheets():
            rows = [
                " | ".join(str(v) for v in sheet.row_values(r))
                for r in range(sheet.nrows)
            ]
            sheets_out.append(f"--- TABBLAD {sheet.name} ---\n" + "\n".join(rows))
    return "\n\n".join(sheets_out)


def build_document_text(doc_meta, raw_dir):
    relative_path = doc_meta.get("relative_path")
    file_type = doc_meta.get("file_type")
    if not relative_path or not file_type:
        raise ValueError(
            f"Document {doc_meta.get('document_id')} mist relative_path/file_type "
            "in de inventaris - kan geen brontekst opbouwen."
        )
    path = os.path.join(raw_dir, relative_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Brondocument niet gevonden: {path}")
    if file_type == "pdf":
        return extract_pdf_text(path)
    if file_type in ("xls", "xlsx"):
        return extract_spreadsheet_text(path, file_type)
    raise ValueError(
        f"Bestandstype '{file_type}' wordt nog niet ondersteund door extract_batch.py "
        "(alleen pdf/xls/xlsx) - sla dit document over, verzin geen inhoud."
    )


def load_vocabulary_context(vocab_dir):
    parts = []
    for name in (
        "element_code", "element_type", "material", "defect_type", "condition_score",
        "severity", "maintenance_action", "priority", "status", "unit",
    ):
        path = os.path.join(vocab_dir, f"{name}.json")
        if not os.path.exists(path):
            continue
        doc = json.load(open(path))
        entries = doc.get("entries", [])
        labels = [str(e.get("label_nl") or e.get("normalized_value")) for e in entries]
        notes = [e["notes"] for e in entries if e.get("notes")]
        block = (
            f"## {name}\nBekende categorieen (ALLEEN ter context, NIET om zelf te "
            f"mappen - dat gebeurt in een latere, deterministische stap): "
            + ", ".join(labels)
        )
        if notes:
            block += "\nLet op: " + " ".join(notes)
        parts.append(block)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Tool-schema voor de LLM-call (zelfstandig, geen externe $ref's)
# ---------------------------------------------------------------------------

PROVENANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "document_id": {"type": "string"},
        "page": {"type": ["integer", "null"]},
        "table_index": {"type": ["integer", "null"]},
        "text_fragment": {"type": ["string", "null"], "description": "Kort letterlijk citaat als onderbouwing."},
        "source_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["document_id", "source_confidence"],
}

EXTRACTED_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"description": "De waarde, of null als niet in het document gevonden - nooit gokken."},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "requires_human_review": {"type": "boolean"},
        "conflict": {"type": "boolean"},
        "possible_values": {
            "type": "array",
            "description": "Bij conflict: alle gevonden kandidaten met eigen provenance, in plaats van er automatisch 1 kiezen.",
            "items": {
                "type": "object",
                "properties": {"value": {}, "provenance": PROVENANCE_SCHEMA},
                "required": ["value", "provenance"],
            },
        },
        "provenance": PROVENANCE_SCHEMA,
    },
    "required": ["value", "confidence", "requires_human_review", "provenance"],
}


def _pair_schema(extra_properties=None):
    props = {
        "original_value": {"type": ["string", "null"]},
        "normalized_value": {
            "type": "null",
            "description": "Altijd null - de vocabulaire-mapping gebeurt in normalize_batch.py, niet hier.",
        },
    }
    if extra_properties:
        props.update(extra_properties)
    return {"type": "object", "properties": props, "required": ["original_value", "normalized_value"]}


BUILDING_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "construction_year": EXTRACTED_VALUE_SCHEMA,
        "number_of_units": EXTRACTED_VALUE_SCHEMA,
        "building_type": EXTRACTED_VALUE_SCHEMA,
        "address": EXTRACTED_VALUE_SCHEMA,
        "inspection_date": EXTRACTED_VALUE_SCHEMA,
        "mjop_period": EXTRACTED_VALUE_SCHEMA,
    },
    "required": [
        "construction_year", "number_of_units", "building_type",
        "address", "inspection_date", "mjop_period",
    ],
}

ELEMENT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "element_id": {"type": "string", "description": "Lokale referentie binnen dit document, bijv. 'el-1'."},
        "element_code": _pair_schema(),
        "element_type": _pair_schema(),
        "element_name": EXTRACTED_VALUE_SCHEMA,
        "location": EXTRACTED_VALUE_SCHEMA,
        "material": _pair_schema(),
        "quantity": EXTRACTED_VALUE_SCHEMA,
        "unit": _pair_schema(),
        "construction_year": EXTRACTED_VALUE_SCHEMA,
        "gemeenschappelijk_of_prive": {"type": ["string", "null"], "enum": ["gemeenschappelijk", "prive", None]},
    },
    "required": ["element_id", "element_type"],
}

OBSERVATION_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "observation_id": {"type": "string", "description": "Lokale referentie binnen dit document."},
        "element_id": {"type": "string", "description": "Moet overeenkomen met een element_id hierboven."},
        "description": EXTRACTED_VALUE_SCHEMA,
        "defect": _pair_schema(),
        "condition_score": _pair_schema({"scale": {"type": ["string", "null"]}}),
        "severity": _pair_schema(),
        "source": PROVENANCE_SCHEMA,
        "requires_human_review": {"type": "boolean"},
    },
    "required": ["observation_id", "element_id", "source", "requires_human_review"],
}

MAINTENANCE_ACTION_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action_id": {"type": "string", "description": "Lokale referentie binnen dit document."},
        "element_id": {"type": "string", "description": "Moet overeenkomen met een element_id hierboven."},
        "action": _pair_schema(),
        "planned_year": EXTRACTED_VALUE_SCHEMA,
        "quantity": EXTRACTED_VALUE_SCHEMA,
        "unit": _pair_schema(),
        "unit_cost": {
            "type": "object",
            "properties": {
                "value": {"type": ["string", "null"], "description": "Decimal als string, bijv. '125.50' - nooit float."},
                "is_estimated": {"type": "boolean", "description": "true als dit een kental/normraming is i.p.v. een documentwaarde."},
                "provenance": PROVENANCE_SCHEMA,
            },
            "required": ["value", "is_estimated", "provenance"],
        },
        "cost_year": {"type": ["integer", "null"]},
        "total_cost_as_stated": {"type": ["string", "null"], "description": "Totaalbedrag zoals letterlijk vermeld, indien aanwezig - nooit zelf uitrekenen."},
        "requires_human_review": {"type": "boolean"},
        "source_page": {"type": ["integer", "null"]},
    },
    "required": ["action_id", "element_id", "requires_human_review"],
}

EXTRACTION_TOOL = {
    "name": "record_extraction",
    "description": (
        "Sla de geëxtraheerde building/elements/observations/maintenance_actions "
        "op volgens het vaste datamodel. Nooit een ontbrekende waarde verzinnen: "
        "value=null, confidence=0, requires_human_review=true."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "building": BUILDING_TOOL_SCHEMA,
            "elements": {"type": "array", "items": ELEMENT_TOOL_SCHEMA},
            "observations": {"type": "array", "items": OBSERVATION_TOOL_SCHEMA},
            "maintenance_actions": {"type": "array", "items": MAINTENANCE_ACTION_TOOL_SCHEMA},
            "extraction_notes": {"type": "string", "description": "Vrije toelichting, bijv. onduidelijke passages of documentkwaliteit."},
        },
        "required": ["building", "elements", "observations", "maintenance_actions"],
    },
}

EXTRACTION_SYSTEM_PROMPT = """Je extraheert gestructureerde gegevens uit een Nederlands \
meerjarenonderhoudsplan (MJOP) voor een VvE, volgens een vast datamodel.

Regels (niet onderhandelbaar):
1. Verzin NOOIT een waarde die niet in het document staat. Ontbrekende informatie ->
   value: null, confidence: 0, requires_human_review: true.
2. Elke waarde krijgt een provenance: het paginanummer (en tabelindex indien van
   toepassing) waar je de waarde vandaan hebt, plus een kort letterlijk citaat
   (text_fragment) als onderbouwing.
3. source_confidence: "high" als de waarde in een duidelijk gelabelde tabelcel
   staat; "medium" als het in lopende tekst met een expliciet label staat;
   "low" als je het indirect moet afleiden. Bij "low": requires_human_review: true.
4. Vind je twee verschillende waarden voor hetzelfde gegeven (bijv. bouwjaar op
   twee plekken)? Kies er GEEN. Zet conflict: true, requires_human_review: true,
   en zet beide waarden (met eigen provenance) in possible_values.
5. Voor element_code/element_type/material/unit/defect/severity/action/
   condition_score: geef alleen original_value (de letterlijke tekst uit het
   document). Laat normalized_value altijd null - de mapping naar de
   gecontroleerde vocabulaire gebeurt in een latere, deterministische stap,
   niet door jou. element_code is de code uit de 'Code'-kolom van het
   elementenoverzicht (bijv. '4711'), indien het document die kolom heeft -
   original_value: null als er geen zo'n kolom/code is, nooit zelf verzinnen.
6. Bereken NOOIT zelf kosten (quantity x unit_cost, indexatie). Geef alleen de
   waarden zoals ze in het document staan; de berekening gebeurt elders.
7. Claim nooit NEN 2767-certificering of een officiele conditieschaal als het
   document dat niet expliciet zo benoemt.
8. Splits gemeenschappelijke en prive elementen (bijv. traphuisdeuren vs.
   tuindeuren) nooit samen tot een element als het document ze onderscheidt.
9. Gebruik korte, stabiele lokale ids (bijv. 'el-1', 'obs-1', 'act-1') zodat
   observaties en onderhoudsacties naar het juiste element kunnen verwijzen.

Gebruik uitsluitend de meegegeven tool om je antwoord te geven."""


def call_model(document_text, vocab_context, doc_id, retry_error=None):
    import anthropic

    client = anthropic.Anthropic()
    user_content = f"Document ID: {doc_id}\n\n{vocab_context}\n\n{document_text}"
    if retry_error:
        user_content += (
            "\n\nJe vorige antwoord voldeed niet aan het verwachte schema "
            f"(vormfout, geen inhoudelijke fout):\n{retry_error}\n"
            "Corrigeer alleen de vorm/structuur - verzin geen nieuwe inhoud."
        )
    # claude-opus-5 accepteert geen temperature/sampling-parameters meer (denken
    # vervangt dat) en grote documenten kunnen veel outputtokens vergen, dus
    # streamen (voorkomt HTTP-timeouts) met een ruime max_tokens.
    with client.messages.stream(
        model=DEFAULT_MODEL,
        max_tokens=64000,
        system=EXTRACTION_SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": EXTRACTION_TOOL["name"]},
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        response = stream.get_final_message()
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Model gaf geen tool_use-blok terug.")


# ---------------------------------------------------------------------------
# Post-processing: normalisatie strippen, ids canonicaliseren, schema-check,
# deterministische review-ondergrens
# ---------------------------------------------------------------------------

def strip_normalization(node):
    """Forceert normalized_value=None op elk original/normalized-paar, ongeacht
    wat het model teruggeeft - de vocabulaire-mapping gebeurt uitsluitend in
    normalize_batch.py (zie CLAUDE.md)."""
    if isinstance(node, dict):
        if "original_value" in node and "normalized_value" in node:
            node["normalized_value"] = None
        for value in node.values():
            strip_normalization(value)
    elif isinstance(node, list):
        for item in node:
            strip_normalization(item)


def canonicalize_ids(record, doc_id):
    """Vervangt de lokale ids die het model gebruikte door canonieke,
    document-gebonden ids, en wijst building_id/document_ids/element-referenties
    toe - dit is bewust GEEN extractietaak (het model verzint geen ids uit het
    document), dus dit gebeurt in code, niet door het taalmodel."""
    element_id_map = {}
    for index, element in enumerate(record.get("elements", []), start=1):
        canonical = f"{doc_id}-EL-{index:03d}"
        element_id_map[element.get("element_id")] = canonical
        element["element_id"] = canonical
        element["building_id"] = f"{doc_id}-BLD-001"

    for index, observation in enumerate(record.get("observations", []), start=1):
        observation["observation_id"] = f"{doc_id}-OBS-{index:03d}"
        observation["element_id"] = element_id_map.get(
            observation.get("element_id"), observation.get("element_id")
        )

    for index, action in enumerate(record.get("maintenance_actions", []), start=1):
        action["action_id"] = f"{doc_id}-ACT-{index:03d}"
        action["element_id"] = element_id_map.get(action.get("element_id"), action.get("element_id"))

    if record.get("building") is not None:
        record["building"]["building_id"] = f"{doc_id}-BLD-001"
        record["building"]["document_ids"] = [doc_id]

    return record


def enforce_review_floor(node):
    """Deterministische ondergrens: requires_human_review wordt ALTIJD True bij
    lage confidence, source_confidence=='low' of conflict==True - los van wat
    het model zelf claimt. Bubbelt omhoog naar het dichtstbijzijnde niveau dat
    een requires_human_review-veld heeft. Retourneert True als er ergens in
    (of onder) deze node een niet-geabsorbeerd signaal is."""
    if isinstance(node, dict):
        child_flag = False
        for key, value in node.items():
            if key == "requires_human_review":
                continue
            child_flag = enforce_review_floor(value) or child_flag

        low_here = False
        if node.get("source_confidence") == "low":
            low_here = True
        confidence = node.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < REVIEW_THRESHOLD:
            low_here = True
        if node.get("conflict") is True:
            low_here = True

        flag = child_flag or low_here
        if "requires_human_review" in node:
            if flag:
                node["requires_human_review"] = True
            return False  # geabsorbeerd op dit niveau
        return flag
    if isinstance(node, list):
        return any(enforce_review_floor(item) for item in node)
    return False


def _validate_against_schema(instance, schemas_dir, schema_filename):
    # Absoluut pad nodig: bij een relatief pad breekt de file://-resolutie van
    # interne $ref's (bijv. "_extracted_value.schema.json") in RefResolver.
    schema_path = os.path.abspath(os.path.join(schemas_dir, schema_filename))
    schema = json.load(open(schema_path))
    resolver = jsonschema.RefResolver(base_uri=f"file://{schema_path}", referrer=schema)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema, resolver=resolver)
    return list(validator.iter_errors(instance))


REQUIRED_TOP_LEVEL_KEYS = ("building", "elements", "observations", "maintenance_actions")


def validate_record(record, schemas_dir):
    errors = []
    # EXTRACTION_TOOL vereist deze velden altijd (desnoods als lege array) -
    # als het model er eentje weglaat is dat een schemafout, geen "toevallig
    # niets gevonden": anders passeert een onvolledig antwoord stilzwijgend
    # omdat de rest van deze functie overal record.get(key, []) gebruikt.
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in record]
    if missing:
        errors.append(f"top-level velden ontbreken in modelantwoord: {missing}")

    if record.get("building") is not None:
        for err in _validate_against_schema(record["building"], schemas_dir, "building.schema.json"):
            errors.append(f"building: {err.message} (pad: {list(err.absolute_path)})")
    for element in record.get("elements", []):
        for err in _validate_against_schema(element, schemas_dir, "element.schema.json"):
            errors.append(f"element {element.get('element_id')}: {err.message} (pad: {list(err.absolute_path)})")
    for observation in record.get("observations", []):
        for err in _validate_against_schema(observation, schemas_dir, "observation.schema.json"):
            errors.append(f"observation {observation.get('observation_id')}: {err.message} (pad: {list(err.absolute_path)})")
    for action in record.get("maintenance_actions", []):
        for err in _validate_against_schema(action, schemas_dir, "maintenance_action.schema.json"):
            errors.append(f"maintenance_action {action.get('action_id')}: {err.message} (pad: {list(err.absolute_path)})")
    return errors


def metadata_fields():
    return {
        "extraction_model": DEFAULT_MODEL,
        "extraction_prompt_version": PROMPT_VERSION,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "temperature": 0,
    }


def failure_record(doc_id, batch, error):
    record = {
        "status": "extraction_failed",
        "document_id": doc_id,
        "batch": batch,
        "building": None,
        "elements": [],
        "observations": [],
        "maintenance_actions": [],
        "extraction_notes": error,
        "requires_human_review": True,
    }
    record.update(metadata_fields())
    return record


def extract_document(doc_meta, raw_dir, vocab_dir, schemas_dir, model_fn, doc_id=None, batch=None):
    doc_id = doc_id or doc_meta.get("document_id")

    try:
        document_text = build_document_text(doc_meta, raw_dir)
    except (FileNotFoundError, ValueError) as exc:
        # Geen brontekst -> geen modelaanroep. Niets om te extraheren, dus
        # ook geen kosten maken of het risico lopen dat het model iets
        # verzint bij een lege/ontbrekende input.
        return failure_record(doc_id, batch, str(exc))

    vocab_context = load_vocabulary_context(vocab_dir)

    retry_error = None
    record = None
    for _attempt in range(2):  # 1 poging + maximaal 1 herhaling bij schemafout
        try:
            record = model_fn(document_text, vocab_context, doc_id, retry_error=retry_error)
        except Exception as exc:  # modelaanroep zelf mislukt (netwerk, API-fout, ...)
            return failure_record(doc_id, batch, f"Modelaanroep mislukt: {exc}")

        record = copy.deepcopy(record)
        strip_normalization(record)
        canonicalize_ids(record, doc_id)

        errors = validate_record(record, schemas_dir)
        if not errors:
            enforce_review_floor(record)
            record["status"] = "extracted"
            record["document_id"] = doc_id
            record["batch"] = batch
            record.setdefault("extraction_notes", "")
            record.update(metadata_fields())
            return record

        retry_error = "; ".join(errors)

    return failure_record(doc_id, batch, f"Schemavalidatie mislukt na herhaling: {retry_error}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--vocab-dir", default="vocabularies")
    ap.add_argument("--schemas-dir", default="schemas")
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Alleen placeholders aanmaken, geen LLM-call (ook als ANTHROPIC_API_KEY gezet is).",
    )
    args = ap.parse_args()

    inventory = load_inventory(args.reports_dir)
    os.makedirs(args.out_dir, exist_ok=True)

    live = (not args.dry_run) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not args.dry_run and not live:
        print("Geen ANTHROPIC_API_KEY gevonden - er worden alleen placeholders aangemaakt, geen echte extractie.")

    created = 0
    extracted = 0
    for doc in inventory:
        doc_id = doc.get("document_id")
        if not doc_id:
            continue
        out_path = os.path.join(args.out_dir, f"{doc_id}.json")

        if os.path.exists(out_path):
            existing = json.load(open(out_path))
            if existing.get("status") != "pending_extraction":
                continue  # mens of eerdere run heeft hier al iets staan - nooit overschrijven
        else:
            rec = dict(EXTRACTED_RECORD_TEMPLATE)
            rec["document_id"] = doc_id
            rec["batch"] = args.batch
            json.dump(rec, open(out_path, "w"), ensure_ascii=False, indent=2)
            created += 1

        if not live:
            continue

        record = extract_document(
            doc,
            raw_dir=args.raw_dir,
            vocab_dir=args.vocab_dir,
            schemas_dir=args.schemas_dir,
            model_fn=call_model,
            doc_id=doc_id,
            batch=args.batch,
        )
        json.dump(record, open(out_path, "w"), ensure_ascii=False, indent=2)
        extracted += 1

    print(f"{created} placeholder-extractiebestanden aangemaakt in {args.out_dir}/")
    if live:
        print(f"{extracted} documenten daadwerkelijk geëxtraheerd (LLM-call).")
    else:
        print("LET OP: geen echte extractie uitgevoerd (dry-run of geen API-key).")


if __name__ == "__main__":
    main()
