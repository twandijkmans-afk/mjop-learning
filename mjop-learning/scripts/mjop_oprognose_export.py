#!/usr/bin/env python3
"""
mjop_oprognose_export.py  (GEACTUALISEERD MJOP -> OPROGNOSE XML-IMPORTBESTAND, v1)

Documentatie: docs/mjop_actualisatie_light_v1.md (sectie OPrognose-export).

Formaat: .NET DataSet-XML zoals OPrognose exporteert: <NewDataSet>, het ingebouwde XSD-schema
(config/oprognose/dataset_schema.xml, letterlijk overgenomen uit een echte export) en daarna één
<opo> (object) met geneste <ope> (elementen) en per element <oph> (handelingen). Elke record bevat
alle kolommen van het schema in schemavolgorde; lege waarden zoals OPrognose ze schrijft
(<veld />, 0, false, 1900-01-01T00:00:00+01:00). CRLF, inspringing 2 spaties.

Mapping (waargenomen in de voorbeeldexport):
  ele_nlsfb / ele_nlsfbhoofd   elementcode (4 cijfers) / eerste 2 cijfers
  han_startjaar, han_cyclus    eerste uitvoeringsjaar, cyclus (0 = eenmalig)
  han_bitpatroon               200 tekens, positie 0 = jaar 2000, '1' = uitvoering, anders '-'
  han_hvhreken x han_prijs     = han_totaal (2 decimalen); han_hvh = han_hvhreken / ele_hvh
Alleen geplande handelingen (han_type 'H'); geen bevindingen (geen inspectie). Vaste
handelingsvelden: config/oprognose/export_defaults.json.

Prijs: is voor alle bedragen een indexfactor beschikbaar, dan geïndexeerde bedragen met
obj_prijspeil = doelprijspeil; anders historische bedragen met obj_prijspeil = prijspeil van het
oude MJOP (OPrognose kan dan zelf indexeren). Is dat prijspeil onbekend, dan prijs 0 en het
historische bedrag in han_opm (geen bedrag met een verkeerd prijspeil).

Planjaren en bedragen zijn voorstellen (niet geïnspecteerd); elke handeling vermeldt in han_opm
herkomst, cyclusbron, aannames en vlaggen, zodat de adviseur ze in OPrognose kan beoordelen.
"""
import datetime
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_maintenance_line_v2 as line_v2  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMAT_DIR = os.path.join(ROOT, "config", "oprognose")
EXPORT_VERSION = "mjop_oprognose_export_v1"
XS = "{http://www.w3.org/2001/XMLSchema}"
CENT = Decimal("0.01")
ACTION_NL = {"replace": "Vervangen", "exterior_painting": "Buitenschilderwerk", "interior_painting": "Binnenschilderwerk",
             "paint": "Schilderwerk", "repair": "Herstellen", "clean": "Reinigen", "inspect": "Inspecteren",
             "maintain": "Onderhouden", "install": "Aanbrengen", "impregnate": "Impregneren", "scaffolding": "Steigerwerk",
             "project_management": "Projectbegeleiding", "advice": "Advies", "site_access_cost": "Benaderingskosten"}
FLAG_NL = {
    "NOT_INSPECTED": "niet geïnspecteerd", "CYCLE_UNKNOWN": "cyclus onbekend",
    "CYCLE_FROM_DOCUMENT_IRREGULAR": "onregelmatige jaren in oud MJOP",
    "CYCLE_DOCUMENT_TABLE_DIFFER": "cyclus oud MJOP wijkt af van levensduurtabel",
    "OVERDUE_NO_CYCLE": "planjaar verstreken zonder cyclus: jaar bepalen", "BASE_YEAR_UNKNOWN": "basisjaar onbekend",
    "ASSUMED_FROM_CONSTRUCTION_YEAR": "AANNAME bouwjaar als laatste vervanging", "ELEMENT_CODE_MISSING": "geen elementcode",
    "ACTION_UNKNOWN": "actie niet genormaliseerd", "BEYOND_HORIZON": "valt na de horizon",
    "PRICE_LEVEL_UNKNOWN": "prijspeil oud MJOP onbekend", "INDEX_MISSING": "indexjaar ontbreekt"}


class ExportError(ValueError):
    pass


# --------------------------------------------------------------------------
# Formaat (uit het ingebouwde schema van een echte export)
# --------------------------------------------------------------------------

def load_format(format_dir=FORMAT_DIR):
    schema_text = open(os.path.join(format_dir, "dataset_schema.xml"), encoding="utf-8").read().rstrip("\n")
    defaults = json.load(open(os.path.join(format_dir, "export_defaults.json"), encoding="utf-8"))
    root = ET.fromstring(schema_text)
    columns, children = OrderedDict(), {}

    def walk(el, parent):
        seq = el.find(f"{XS}complexType/{XS}sequence")
        cols, nested = [], []
        for ch in seq.findall(f"{XS}element"):
            if ch.find(f"{XS}complexType") is not None:
                nested.append(ch.get("name"))
                walk(ch, ch.get("name"))
            else:
                cols.append((ch.get("name"), (ch.get("type") or "").replace("xs:", "")))
        columns[parent], children[parent] = cols, nested

    top = root.find(f"{XS}element/{XS}complexType/{XS}choice/{XS}element")
    walk(top, top.get("name"))
    return {"schema_text": schema_text, "columns": columns, "children": children, "defaults": defaults}


def default_value(xs_type, fmt):
    if xs_type == "string":
        return ""
    if xs_type == "boolean":
        return "false"
    if xs_type == "dateTime":
        return fmt["defaults"]["null_datetime"]
    return "0"


def blank_record(table, fmt):
    return OrderedDict((name, default_value(t, fmt)) for name, t in fmt["columns"][table])


def num(d):
    """Decimal zoals de export getallen schrijft: geen exponent, geen overbodige nullen."""
    d = Decimal(d)
    if d == 0:
        return "0"
    return format(d.normalize(), "f")


def local_timestamp(fmt, when=None):
    from zoneinfo import ZoneInfo
    when = when or datetime.datetime.now(datetime.timezone.utc)
    return when.astimezone(ZoneInfo(fmt["defaults"]["timezone"])).replace(microsecond=0).isoformat()


def bitpattern(start, cycle, fmt):
    d = fmt["defaults"]
    first, length = d["bitpattern_start_year"], d["bitpattern_length"]
    bits = ["-"] * length
    if start:
        if not first <= start < first + length:
            raise ExportError(f"startjaar {start} valt buiten het bitpatroon {first}-{first + length - 1}")
        y = start
        while y < first + length:
            bits[y - first] = "1"
            if not cycle:
                break
            y += cycle
    return "".join(bits)


# --------------------------------------------------------------------------
# Opbouw
# --------------------------------------------------------------------------

def _v(field):
    if isinstance(field, dict):
        return field.get("normalized_value", field.get("value"))
    return field


def _positive(q):
    try:
        d = Decimal(str(q))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return d if q is not None and d > 0 else None


def price_mode(lines, source_price_year):
    """'indexed' als elk bruikbaar historisch bedrag geïndexeerd is; anders 'historical'
    (of 'historical_unknown_level' als het prijspeil van het oude MJOP onbekend is)."""
    usable = [l["price_update"] for l in lines if l["price_update"] and l["price_update"]["status"] != "REJECTED"
              and l["price_update"]["source_total_as_stated"] is not None]
    if usable and all(pu["indexed_total"] is not None for pu in usable):
        return "indexed"
    return "historical" if source_price_year else "historical_unknown_level"


def line_amount(line, mode):
    """(bedrag per keer of None, toelichting)."""
    if line["price_status"] in ("HUMAN_ACCEPTED", "HUMAN_ADJUSTED", "MANUALLY_SET"):
        t = line["financial"]["effective_total"]
        return (Decimal(t) if t is not None else None), "kengetal/handmatig bedrag (eigen prijspeil)"
    pu = line["price_update"]
    if pu is None or pu["status"] == "REJECTED":
        return None, "geen bedrag"
    if pu["not_computed_reason"] == "SOURCE_AMOUNTS_DIFFER":
        return None, "bedragen per keer verschillen in oud MJOP: bedrag bepalen"
    if pu["source_total_as_stated"] is None:
        return None, "geen bedrag in oud MJOP"
    src = f"oud MJOP {pu['source_document_id']} € {pu['source_total_as_stated']} (prijspeil {pu['base_price_level_year'] or 'onbekend'})"
    if mode == "indexed":
        return Decimal(pu["indexed_total"]), f"{src} x indexfactor {pu['indexation_factor']} ({pu['index_source']})"
    if mode == "historical":
        return Decimal(pu["source_total_as_stated"]), f"{src}, niet geïndexeerd"
    return None, f"{src}: prijspeil onbekend, bedrag niet ingevuld"


def _remark(line, amount_note, scheduled):
    src, basis = line["origin_source"] or {}, line["planning_basis"] or {}
    parts = [f"Actualisatie {EXPORT_VERSION}"]
    if line["origin"] == "FROM_EXISTING_MJOP":
        pages = ",".join(str(p) for p in src.get("pages", []))
        years = ",".join(str(y) for y in src.get("document_planned_years", []))
        parts.append(f"uit {src.get('document_id')} p.{pages or '?'} (jaren oud MJOP: {years or '-'})")
    elif line["origin"] == "ADDED_FROM_LIFECYCLE":
        parts.append("TOEGEVOEGD o.b.v. levensduurtabel")
    if scheduled is None:
        parts.append("GEEN PLANJAAR: jaar en cyclus bepalen")
    else:
        status = "definitief" if scheduled[2] else "VOORSTEL"
        parts.append(f"planning {status}; cyclusbron {basis.get('cycle_source') or '-'}; "
                     f"basisjaar {basis.get('base_year') or '-'} ({basis.get('base_year_source') or '-'})")
    flags = [FLAG_NL.get(f, f) for f in line["planner_flags"]]
    if flags:
        parts.append("let op: " + ", ".join(flags))
    parts.append("bedrag: " + amount_note)
    return " | ".join(parts)


def build_dataset(doc, lines, *, mjop_id, start_year, target_price_year, source_price_year, fmt, at=None,
                  obj_code=None, opening_note=None):
    """Geeft (opo-record met geneste lijsten, rapport)."""
    d = fmt["defaults"]
    mode = price_mode(lines, source_price_year)
    stamp = local_timestamp(fmt, at)
    pk = d["pk_base"]
    building = doc.get("building", {})
    dl = doc.get("document_level_values") or {}
    dv = lambda k: (dl.get(k) or {}).get("value") if isinstance(dl.get(k), dict) else dl.get(k)  # noqa: E731
    vat = next((l["vat_basis"] for l in lines if l["vat_basis"]), None)

    obj = blank_record("opo", fmt)
    obj_pk = pk + d["pk_offsets"]["opo"]
    price_year = target_price_year if mode == "indexed" else source_price_year
    obj.update({
        "obj_pk": str(obj_pk), "obj_code": obj_code or mjop_id, "obj_type": dv("object_name") or mjop_id,
        "obj_postcode": dv("object_postcode") or "", "obj_plaats": dv("object_city") or "",
        "obj_bouwjaar": str(_v(building.get("construction_year")) or 0),
        "obj_aantapp": str(_v(building.get("number_of_units")) or 0),
        "obj_btw": "true" if vat == "inclusive" else "false",
        "obj_btwtarieftoepassen": "true" if vat == "inclusive" else "false",
        "obj_prijspeil": f"{price_year}-01-01T00:00:00+01:00" if price_year else d["null_datetime"],
        "obj_created": stamp, "obj_lastopened": stamp,
        "obj_opm": (f"CONCEPT-actualisatie naar 30 jaar ({start_year}-{start_year + 29}) op basis van {doc['document_id']}. "
                    "Niet geïnspecteerd, geen NEN 2767-conditiemeting, geen actuele marktprijzen. Planjaren en bedragen "
                    "zijn voorstellen; zie per handeling de opmerking. " + (opening_note or "")).strip(),
    })
    elements = {e["element_id"]: e for e in doc.get("elements", [])}
    unit_map = d["unit_map"]
    groups = OrderedDict()
    for l in lines:
        groups.setdefault(l["object_id"], []).append(l)

    ope_records, report_lines, deviation = [], [], Decimal(0)
    n_ele = n_han = 0
    for object_id, group in groups.items():
        el = elements.get(object_id, {})
        ele = blank_record("ope", fmt)
        ele_pk = pk + d["pk_offsets"]["ope"] + n_ele
        n_ele += 1
        code = group[0]["element_code_internal"] or _v(el.get("element_code")) or ""
        el_qty = _positive(_v(el.get("quantity")))
        el_unit_norm = _v(el.get("unit"))
        el_unit = unit_map.get(el_unit_norm) or (el["unit"].get("original_value") if isinstance(el.get("unit"), dict) else None)
        if el_qty is None:   # geen elementhoeveelheid in het document: die van de eerste regel
            el_qty = _positive(group[0]["quantity"])
            el_unit = unit_map.get(group[0]["unit_normalized"]) or group[0]["unit_text"]
        ele.update({"ele_pk": str(ele_pk), "ele_objfk": str(obj_pk),
                    "ele_tekst": _v(el.get("element_name")) or group[0]["object_description"] or code or object_id,
                    "ele_hvh": num(el_qty) if el_qty else "0", "ele_eenheid": el_unit or "",
                    "ele_locatie": _v(el.get("location")) or group[0]["context"]["location"] or "",
                    "ele_nlsfb": code, "ele_nlsfbhoofd": code[:2] if code[:2].isdigit() else "", "modified": stamp})
        han_records = []
        for l in group:
            amount, amount_note = line_amount(l, mode)
            sched = line_v2.schedule(l)
            start, cycle = (sched[0], sched[1] or 0) if sched else (0, 0)
            qty = _positive(l["quantity"])
            unit = unit_map.get(l["unit_normalized"]) or l["unit_text"]
            if qty is None or not unit:
                qty, unit = Decimal(1), "pst"
                amount_note += "; hoeveelheid onbekend: als post"
            if amount is not None:
                prijs = (amount / qty).quantize(CENT, rounding=ROUND_HALF_EVEN)
                totaal = (qty * prijs).quantize(CENT, rounding=ROUND_HALF_EVEN)
                deviation += totaal - amount
            else:
                prijs = totaal = Decimal(0)
            hvh = Decimal(1)
            if el_qty and unit == el_unit and el_qty != qty:
                hvh = (qty / el_qty).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
            han = blank_record("oph", fmt)
            han.update(d["oph"])
            han.update({"han_pk": str(pk + d["pk_offsets"]["oph"] + n_han), "han_elefk": str(ele_pk),
                        "han_tekst": l["action_text"] or ACTION_NL.get(l["action_normalized"] or "", "") or l["object_description"] or "",
                        "han_eenheid": unit, "han_hvhreken": num(qty), "han_hvh": num(hvh), "han_prijs": num(prijs),
                        "han_startjaar": str(start), "han_cyclus": str(cycle), "han_bitpatroon": bitpattern(start, cycle, fmt),
                        "han_totaal": num(totaal), "han_locatie": l["context"]["location"] or "",
                        "han_opm": _remark(l, amount_note, sched)})
            n_han += 1
            han_records.append(han)
            report_lines.append({"maintenance_line_id": l["maintenance_line_id"], "ele_pk": ele_pk, "han_pk": int(han["han_pk"]),
                                 "startjaar": start, "cyclus": cycle, "scheduled": sched is not None,
                                 "definitive": bool(sched and sched[2]), "prijs": han["han_prijs"], "totaal": han["han_totaal"],
                                 "amount_known": amount is not None})
        ope_records.append((ele, han_records))
    report = {"export_version": EXPORT_VERSION, "price_mode": mode, "obj_prijspeil_year": price_year,
              "elements": len(ope_records), "actions": n_han,
              "actions_without_year": sum(1 for r in report_lines if not r["scheduled"]),
              "actions_proposed": sum(1 for r in report_lines if r["scheduled"] and not r["definitive"]),
              "actions_without_amount": sum(1 for r in report_lines if not r["amount_known"]),
              "rounding_deviation_total": format(deviation, "f"), "lines": report_lines}
    return (obj, ope_records), report


# --------------------------------------------------------------------------
# Schrijven en controleren
# --------------------------------------------------------------------------

def _record_xml(tag, record, indent):
    pad = "  " * indent
    out = [f"{pad}<{tag}>"]
    for k, v in record.items():
        out.append(f"{pad}  <{k} />" if v == "" else f"{pad}  <{k}>{escape(str(v))}</{k}>")
    return out


def serialize(dataset, fmt):
    obj, ope_records = dataset
    out = ["<NewDataSet>"] + fmt["schema_text"].split("\n")
    out += _record_xml("opo", obj, 1)
    for ele, hans in ope_records:
        out += _record_xml("ope", ele, 2)
        for han in hans:
            out += _record_xml("oph", han, 3)
            out.append("      </oph>")
        out.append("    </ope>")
    out += ["  </opo>", "</NewDataSet>"]
    return "\r\n".join(out)


def _type_ok(value, xs_type):
    if value is None or value == "":
        return xs_type == "string"
    try:
        if xs_type in ("int", "short"):
            int(value)
        elif xs_type == "double":
            Decimal(value)
        elif xs_type == "boolean":
            return value in ("true", "false")
        elif xs_type == "dateTime":
            datetime.datetime.fromisoformat(value)
    except (ValueError, InvalidOperation):
        return False
    return True


def validate_xml(text, fmt):
    """Controleert een (eigen of echte) OPrognose-XML tegen het formaat. Geeft een lijst fouten."""
    errors = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [f"geen geldige XML: {e}"]
    if root.tag != "NewDataSet":
        return [f"root is {root.tag}, verwacht NewDataSet"]
    sch = root.find(f"{XS}schema")
    if sch is None:
        errors.append("ingebouwd schema ontbreekt")
    cols = fmt["columns"]
    pks = {"opo": set(), "ope": set(), "oph": set()}

    def check(rec, table, parent_pk=None):
        names = [c.tag for c in rec if c.tag not in fmt["children"].get(table, [])]
        expected = [n for n, _ in cols[table]]
        if names != expected:
            missing = [n for n in expected if n not in names]
            errors.append(f"{table}: kolommen wijken af van het schema (ontbrekend: {missing[:5]})")
            return
        types = dict(cols[table])
        for c in rec:
            if c.tag in types and not _type_ok(c.text, types[c.tag]):
                errors.append(f"{table}.{c.tag}: waarde {c.text!r} past niet bij {types[c.tag]}")

    for opo in root.findall("opo"):
        check(opo, "opo")
        obj_pk = opo.findtext("obj_pk")
        pks["opo"].add(obj_pk)
        for ope in opo.findall("ope"):
            check(ope, "ope")
            ele_pk = ope.findtext("ele_pk")
            if ele_pk in pks["ope"]:
                errors.append(f"ope: dubbele ele_pk {ele_pk}")
            pks["ope"].add(ele_pk)
            if ope.findtext("ele_objfk") != obj_pk:
                errors.append(f"ope {ele_pk}: ele_objfk verwijst niet naar obj_pk {obj_pk}")
            for oph in ope.findall("oph"):
                check(oph, "oph")
                han_pk = oph.findtext("han_pk")
                if han_pk in pks["oph"]:
                    errors.append(f"oph: dubbele han_pk {han_pk}")
                pks["oph"].add(han_pk)
                if oph.findtext("han_elefk") != ele_pk:
                    errors.append(f"oph {han_pk}: han_elefk verwijst niet naar ele_pk {ele_pk}")
                try:
                    start, cyc = int(oph.findtext("han_startjaar")), int(oph.findtext("han_cyclus"))
                    if oph.findtext("han_bitpatroon") != bitpattern(start, cyc, fmt):
                        errors.append(f"oph {han_pk}: han_bitpatroon past niet bij startjaar/cyclus")
                    q, p, t = (Decimal(oph.findtext(k)) for k in ("han_hvhreken", "han_prijs", "han_totaal"))
                    if (q * p).quantize(CENT, rounding=ROUND_HALF_EVEN) != t.quantize(CENT):
                        errors.append(f"oph {han_pk}: han_totaal != han_hvhreken x han_prijs")
                except (TypeError, ValueError, InvalidOperation, ExportError) as e:
                    errors.append(f"oph {han_pk}: {e}")
    if len(pks["opo"]) != 1:
        errors.append(f"verwacht precies één opo, gevonden {len(pks['opo'])}")
    return errors


def write(dataset, fmt, path):
    text = serialize(dataset, fmt)
    errors = validate_xml(text, fmt)
    if errors:
        raise ExportError("; ".join(errors[:10]))
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return text
