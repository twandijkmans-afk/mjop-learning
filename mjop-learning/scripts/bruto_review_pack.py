"""Quantity Review & Triage v1: offline HTML-reviewpack en JSON-export (puur, deterministisch).

De HTML is zelfstandig: geen script, geen formulier, geen externe afbeelding, lettertype of verwijzing, een CSP die alles
verbiedt. Een klik registreert niets; er is geen invoerelement. Alle tekst uit de invoer wordt ge-escaped. De CLI schrijft
uitsluitend naar een opgegeven pad buiten de repository; zonder pad schrijft hij naar stdout.
"""
import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bruto_triage as triage  # noqa: E402

CLASS_NL = {"CLEAN_PROVISIONAL": "Schoon voorlopig", "REVIEW_REQUIRED": "Beoordeling nodig", "INSUFFICIENT_EVIDENCE": "Onvoldoende bewijs", "CONFLICT": "Conflict"}
STATE_NL = {"AUTO_PROVISIONAL": "Automatisch voorlopig", "INDIVIDUAL_REVIEW": "Individuele beoordeling", "BLOCKED": "Geblokkeerd",
            "READY_FOR_GROUP_REVIEW": "Klaar voor groepsbeoordeling (voorbereid, niet vrijgegeven)"}
CSS = ("body{font-family:sans-serif;margin:16px;color:#1b1b1b;background:#fff}h1{font-size:1.4em}table{border-collapse:collapse;width:100%}"
       "th,td{border:1px solid #bbb;padding:4px 6px;text-align:left;vertical-align:top;font-size:.9em}.banner{border:2px solid #a40;padding:8px;margin:8px 0;background:#fff4e5}"
       ".c-CLEAN_PROVISIONAL{background:#e6f4ea}.c-REVIEW_REQUIRED{background:#fff8e1}.c-INSUFFICIENT_EVIDENCE{background:#ffebd6}.c-CONFLICT{background:#fde0e0}"
       "details{margin:6px 0;border:1px solid #ccc;padding:4px 8px}summary{cursor:pointer;font-weight:bold}code{font-size:.85em}")


def e(x):
    return html.escape("" if x is None else str(x), quote=True)


def _dash(v):
    return "onbekend (null)" if v is None else e(v)


def render_html(pack):
    out = ["<!DOCTYPE html>", '<html lang="nl"><head><meta charset="utf-8">',
           "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">",
           f"<title>Reviewpack {e(pack['pack_id'])}</title><style>{CSS}</style></head><body>",
           f"<h1>Quantity Review &amp; Triage: reviewpack {e(pack['pack_id'])}</h1>",
           '<div class="banner"><b>Voorlopig. Niet vrijgegeven. Geen definitieve MJOP-hoeveelheid.</b> Dit overzicht registreert geen besluit; '
           "een klik of selectie hier heeft geen effect. Scenario's zijn onafhankelijk en mogen niet worden opgeteld.</div>"]
    cal = pack["calibration"]
    out.append(f"<h2>Kalibratie</h2><p>Status: <b>{e(cal['effective_status'])}</b> (opgegeven: {e(cal['declared_status'])}). "
               + ("Drempels zijn ongekalibreerd: conservatieve triage, geen enkel object is schoon voorlopig. " if cal["conservative_fallback"] else "")
               + (f"Redenen: {e(', '.join(cal['problems']))}." if cal["problems"] else "") + "</p>")
    s = pack["summary"]
    out.append("<h2>Samenvatting</h2><table><tr><th>Klasse</th><th>Objecten</th></tr>")
    for c, n in s["by_overall_class"].items():
        out.append(f'<tr class="c-{c}"><td>{e(CLASS_NL[c])} ({e(c)})</td><td>{n}</td></tr>')
    out.append(f"</table><p>Totaal objecten: {s['object_count']}. Elk object staat expliciet in de lijst hieronder; niets is stilzwijgend vrijgegeven.</p>")
    out.append("<h2>Werklijst (volgorde van beoordeling)</h2><table><tr><th>Prio</th><th>Object</th><th>Totaal</th><th>Identiteit</th><th>Maat</th><th>Werkstatus</th><th>Redenen</th></tr>")
    byid = {o["object_id"]: o for o in pack["objects"]}
    for oid in pack["work_queue"]:
        o = byid[oid]
        out.append(f'<tr class="c-{e(o["overall_class"])}"><td>{o["review_priority"]}</td><td>{e(oid)}</td><td>{e(o["overall_class"])}</td>'
                   f'<td>{e(o["identity_axis"]["class"])}</td><td>{e(o["dimension_axis"]["class"])}</td><td>{e(STATE_NL[o["work_state"]])}</td>'
                   f'<td>{e(", ".join(r["rule_id"] for r in o["review_reasons"]))}</td></tr>')
    out.append("</table>")
    out.append("<h2>Objecten</h2>")
    for o in pack["objects"]:
        d = o["dimension"]
        out.append(f'<details class="c-{e(o["overall_class"])}"><summary>{e(o["object_id"])} · {e(o["object_category"])} · {e(CLASS_NL[o["overall_class"]])} · {e(STATE_NL[o["work_state"]])}</summary>')
        out.append(f"<p>Voorlopig object-ID: <code>{e(o['provisional_object_id'])}</code>; herkomst {e(o['object_origin'])}; type {_dash(o['type_id'])}; aantal {o['quantity']}.</p>")
        out.append(f"<p>Maat: {_dash(d['outer_width_m'])} x {_dash(d['outer_height_m'])} m, status {e(d['dimension_status'])}, bron {e(d['source_kind'])} {_dash(d['source_id'])}. "
                   f"Bruto oppervlak ({e(d['area_class'])}): exact {_dash(d['gross_area_m2_exact'])} m², weergegeven {_dash(d['gross_area_m2_presented'])} m².</p>")
        out.append(f"<p>Identiteitsas: <b>{e(o['identity_axis']['class'])}</b>"
                   + (" (zou schoon zijn bij gekalibreerde drempels)" if o["identity_axis"]["would_be_clean_if_calibrated"] else "")
                   + f". Maatas: <b>{e(o['dimension_axis']['class'])}</b>.</p>")
        if o["review_reasons"]:
            out.append("<ul>" + "".join(f"<li><code>{e(r['rule_id'])}</code> {e(r['title'])}: {e(r['detail'])}</li>" for r in o["review_reasons"]) + "</ul>")
        if o["contradictions"]:
            out.append("<p><b>Tegenstrijdigheden:</b></p><ul>" + "".join(f"<li>{e(c['rule_id'])}: {e(c['detail'])}</li>" for c in o["contradictions"]) + "</ul>")
        out.append("<table><tr><th>Observatie</th><th>Foto</th><th>Zicht</th><th>Bron</th><th>Markeringen</th></tr>"
                   + "".join(f"<tr><td>{e(x['observation_id'])}</td><td>{e(x['photo_id'])}</td><td>{e(x['visibility'])}</td><td>{_dash(x['source_ref'])}</td><td>{e(', '.join(x['flags']))}</td></tr>" for x in o["observations"])
                   + "</table>")
        if o["identity_evidence"]:
            out.append("<table><tr><th>Bewijs</th><th>Observaties</th><th>Grond</th><th>Richting</th><th>Bron</th></tr>"
                       + "".join(f"<tr><td>{e(x['evidence_id'])}</td><td>{e(' / '.join(x['observation_ids']))}</td><td>{e(x['evidence_basis'])}</td><td>{e(x['polarity'])}</td><td>{_dash(x['source_ref'])}</td></tr>" for x in o["identity_evidence"])
                       + "</table>")
        out.append(f"<p>Effect op voorlopige hoeveelheden: {e(o['effect_on_provisional_quantities']['text'])}</p>")
        ai = o["ai_confidence"]
        out.append(f"<p>AI-zekerheid (informatie, niet gebruikt in de classificatie): {_dash(ai['value'])}.</p>")
        for f in o["info_flags"]:
            out.append(f"<p>Let op: {e(f['flag'])} (geen effect op de klasse).</p>")
        out.append("</details>")
    out.append("<h2>Reviewscenario's (voorlopig, niet optellen)</h2>")
    if not pack["scenarios"]:
        out.append("<p>Geen scenario's.</p>")
    for sc in pack["scenarios"]:
        out.append(f"<details><summary>{e(sc['scenario_id'])} · {e(sc['kind'])} · overlapgroep {e(sc['overlap_group'])}</summary><p>{e(sc['statement'])}</p>"
                   f"<pre>{e(json.dumps(sc['effect'], indent=2, sort_keys=True, ensure_ascii=False))}</pre><p>{e(sc['note'])}</p></details>")
    out.append("<h2>Groepen</h2>")
    if not pack["groups"]:
        out.append("<p>Geen groep voorbereid.</p>")
    for g in pack["groups"]:
        out.append(f"<p>{e(g['group_id'])}: {len(g['member_object_ids'])} leden, auditsteekproef {e(', '.join(g['audit_sample_object_ids']))}. "
                   f"Voorbereid, niet vrijgegeven; {len(g['exception_list_object_ids'])} object(en) staan op de uitzonderingenlijst.</p>")
    st = pack["baseline_state"]
    out.append("<h2>Voorlopige basisstand</h2><p>Gescheiden lagen; geen gecombineerd totaal. Gebouwtotaal: onbekend.</p><pre>"
               + e(json.dumps({"layers": st["layers"], "areas": st["areas"], "unknown": st["unknown"], "building_total": st["building_total"]}, indent=2, sort_keys=True, ensure_ascii=False))
               + "</pre>")
    out.append("<h2>Opmerkingen</h2><ul>" + "".join(f"<li>{e(n)}</li>" for n in pack["notes"]) + "</ul>")
    out.append(f"<p><small>invoer-sha256 {e(pack['input_sha256'])}</small></p></body></html>\n")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bouw een reviewpack (HTML + JSON) uit een triage-invoerbestand. Schrijft nooit in de repository.")
    ap.add_argument("input")
    ap.add_argument("--out-dir", help="map buiten de repository; zonder dit wordt de JSON naar stdout geschreven")
    a = ap.parse_args(argv)
    pack = triage.triage(json.loads(Path(a.input).read_text(encoding="utf-8")))
    if not a.out_dir:
        sys.stdout.write(triage.pack_json(pack))
        return 0
    out = Path(a.out_dir).resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit("weigert te schrijven binnen de repository")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pack['pack_id']}.json").write_text(triage.pack_json(pack), encoding="utf-8")
    (out / f"{pack['pack_id']}.html").write_text(render_html(pack), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
