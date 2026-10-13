"""Rapport- en reviewpakketweergave voor het Physical Instance Approval Framework v1 (alleen presentatie, geen logica, geen schrijfacties buiten de aanroeper)."""
import base64
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RC_FIGS = [
    ("reports/frames/physical_instance_approval_v1/RC-crop_scope.jpg", "Waarom VR-045 en PR #42 verschillen: boven MAP-003/004; onder MAP-009 met de VR-045-uitsnede (zonder smal raam) en de ruimere uitsnede (met smal raam)."),
    ("reports/frames/physical_instance_approval_v1/RC-feature_comparison.jpg", "Kenmerken naast elkaar: merktekens, vensterbank en folie in MAP-003, MAP-004 en MAP-009."),
]
FIGS = [
    ("reports/frames/photo_review_map003_map004_v1/pilot_review/PQ-rel-VR-027.jpg", "OBS-MAP003-011 (links) en OBS-MAP004-006 (rechts): de twee observaties van het kandidaatverband."),
    ("reports/frames/physical_object_identity_evidence_v1/EV-window_comparison.jpg", "Bewijsvergelijking: bronobservaties, MAP-009 (andere camera en hoek), MAP-007 (tegenvoorbeeld, ander huis) en buurramen."),
    ("reports/frames/photo_review_map003_map004_v1/C1_MAP-003_vs_MAP-004_upper_facade.jpg", "Bovenste gevelrij MAP-003 naast MAP-004 (bestaand vergelijkingsbeeld)."),
]
ICON = {"PASS": "geslaagd", "NEEDS_EVIDENCE": "bewijs ontbreekt", "BLOCK": "geblokkeerd"}


def _flat(v):
    return "; ".join(str(x) for x in v) if isinstance(v, list) else str(v)


def render_md(rep):
    req, ver = rep["draft_request"], rep["photo_evidence_summary"]
    vr = req["validation_results"]
    L = ["# Physical Instance Approval Framework v1", "",
         "**Status: raamwerk plus één CONCEPTAANVRAAG. Er is geen menselijk instance-besluit genomen, geen instance aangemaakt en niets gemerged.** "
         "Een approval request (IAR-*) is geen fysieke instance (FI-*) en reserveert geen instance-id.", "",
         "Centrale vraag: hoe voorkomen we dat een foutief of onvoldoende onderbouwd kandidaatverband als definitief kozijn in de MJOP-App terechtkomt? "
         "Antwoord: drie strikt gescheiden stappen die nooit automatisch in elkaar overgaan, fail-closed gecontroleerd, met een menselijk besluit als enige weg naar goedkeuring en een nog niet bestaand, apart geautoriseerd proces voor activatie.", "",
         "## 1. Bestaande architectuur en wat ontbreekt", "",
         "| Onderdeel | Bestaand | Hergebruikt |", "|---|---|---|",
         "| Instance-store | `data/frame_inventory/maldenhof_photo_frame_instances_v1.json` (bevroren): 12 actieve + 2 vervangen instances, allemaal `FI-M2-nnn` uit foto 2; id's worden per script (`build_frame_instance_activation.py`) toegekend | alleen lezen (conflictcontrole C9) |",
         "| OIC-model | `scripts/object_identity_pilot.py`: OIC-VR-027 SUPPORTED_CANDIDATE, fail-closed `evaluate_relation` | live her-evaluatie (C2) |",
         "| Menselijke besluiten | pilotregister (10 besluiten, herkomst ChatGPT-bevestiging) | C6 |",
         "| APP-besluiten | 48 rijen, allemaal OPEN, in het goedkeuringsdocument | alleen lezen, C10 |",
         "| Bewijs | P1-kwaliteitsreview, evidence-verificatie (MAP-009), archiefregister (SHA256) | C4, C7, fotobewijs |",
         "| Scopebescherming | `tests/test_scope_guard.py` met bevroren manifest | ongewijzigd |", "",
         "**Ontbrekend vóór deze PR:** een mechanisme voor menselijke *instance*-goedkeuring bestond niet (geen `approval_request`, geen statusmachine, geen besluit dat bij een exacte aanvraag hoort). "
         "Er was ook geen controle dat een observatie niet al aan een bestaande instance hangt of dat twee kandidaten niet dezelfde observaties claimen. Er is bewust géén tweede instance-store gemaakt en geen schrijfpad naar de bestaande.", "",
         "## 2. Het approval-requestmodel", "",
         "Velden: " + ", ".join(f"`{f}`" for f in rep["request_model"]["required_fields"]) + ".", "",
         "- `approval_request_id` = `IAR-<candidate_group_id>`; botst per constructie nooit met `FI-*`. `frame_instance_id` en `reserved_instance_id` zijn altijd `null`; een `FI-`-id ergens in de aanvraag blokkeert.",
         "- `request_hash` bindt het besluit aan de exacte inhoud: wijzigt het bewijs, dan hoort een eerder besluit niet meer bij de aanvraag.",
         "- Een aanvraag mag zelf geen status `APPROVED_FOR_ACTIVATION`, geen `human_decision` en geen inhoud voor niveau B of C dragen.", "",
         "## 3. De drie besluitvormingsniveaus", "",
         "| Niveau | Vraag | In deze PR |", "|---|---|---|"]
    for k, v in rep["decision_levels"].items():
        L.append(f"| {k} | {v} | {'NOT_DECIDED (aanvraag gaat alleen over A)' if k == 'A' else 'NOT_DECIDED, niet aangeroerd'} |")
    L += ["", "Een goedkeuring op niveau A geeft nooit automatisch goedkeuring voor B (BAG-pand) of C (hoeveelheid, afmeting, onderhoud, kosten). Het menselijke besluitrecord moet precies `covers_levels = [\"A\"]` zeggen; "
          "elk besluit met pand-, hoeveelheid-, kosten- of afmetinginhoud wordt geweigerd.", "",
          "## 4. Statusmachine", "", "| Status | Betekenis | Toegestaan naar |", "|---|---|---|"]
    for s in rep["status_machine"]["statuses"]:
        L.append(f"| `{s}` | {rep['status_machine']['meaning'][s]} | {', '.join('`'+t+'`' for t in rep['status_machine']['transitions'][s]) or '(eindstatus)'} |")
    L += [""] + [f"- {r}" for r in rep["status_machine"]["rules"]]
    L += ["", "Onderscheid dat nooit automatisch overgaat: **technisch geschikt voor beoordeling** (`READY_FOR_HUMAN_REVIEW`) → **menselijk goedgekeurd voor fysieke identiteit** (`APPROVED_FOR_ACTIVATION`) → **geactiveerde instance** (bestaat in deze PR niet; er is geen code die `FI-*` aanmaakt of wijzigt).", "",
          "## 5. Harde voorwaarden (technisch geschikt voor beoordeling)", ""]
    L += [f"- **{c['id']}** {c['condition']}" for c in rep["technical_conditions"]]
    L += ["", "Elke voorwaarde faalt gesloten: een fout, ontbrekend of tegenstrijdig gegeven geeft `NEEDS_MORE_EVIDENCE` of `REJECTED` (technische blokkade, geen menselijk besluit), nooit een gunstiger uitkomst. "
          "Een geldig SAME-pilotbesluit is een *kandidaat*-besluit en geen instance-goedkeuring.", "",
          "## 6. Conceptaanvraag OIC-VR-027", "",
          f"- Aanvraag: `{req['approval_request_id']}` (hash `{req['request_hash']}`), status **`{req['approval_status']}`**, technisch oordeel **{vr['technical_verdict']}**.",
          f"- Observaties: {', '.join(req['observation_ids'])} (foto's {', '.join(req['photo_ids'])}); relatie {', '.join(req['supporting_relation_ids'])}; "
          f"bronsterkte {req['relation_strength_in_source']}, kwaliteitsreview {req['evidence_class']}.",
          "- Voorgesteld type: EXTERIOR_FRAME, materiaal en subtype UNKNOWN (voorstel, niet besloten). Geen BAG-pand, geen hoeveelheid, geen kosten.", "",
          "| Check | Resultaat | Soort | Detail |", "|---|---|---|---|"]
    for c in vr["checks"]:
        L.append(f"| {c['id']} {c['title']} | {ICON[c['result']]} | {c['kind']} | {_flat(c['detail']).replace('|', '/')} |")
    L += ["", "### Fotobewijs (samenvatting)", ""]
    for a in ver["additional_matches"] or []:
        L.append(f"- **{a['photo_id']}** ({a['strength']}): " + "; ".join(a["arguments"]))
        L += [f"  - Beperking: {x}" for x in a["limits"]]
    L += ["- Tegenvoorbeeld MAP-007 (zelfde raamtype, ander huis) en de buurramen laten zien dat vorm en indeling niet onderscheiden; feature-match is alleen ondersteunend "
          "(39 inliers op de observatie-uitsneden, 29 op ruimere uitsneden, buurramen tot 54 bij andere paren; via de schuine MAP-009 slechts 8).",
          f"- Zwakte van de verwisseling: {ver['swap_risk']}", "",
          "### Open onzekerheden (blijven zichtbaar, niet omgezet in goedkeuring)", ""]
    L += [f"- {q}" for q in req["unresolved_questions"] + req.get("derived_open_questions", [])]
    L += ["", "**Let op, tegenstrijdige beoordeling van MAP-009:** de aanvullende MAP-009-lezing uit PR #42 is een handmatige beoordeling door Claude. De bestaande P1-kwaliteitsreview van de open relatie VR-045 (zelfde kozijn, MAP-009 als referentie, andere uitsnede) "
          "noemt het bewijs daar onvoldoende en stelt UNDECIDABLE voor. Er is geen menselijk besluit over VR-045. Deze aanvraag steunt daarom niet op MAP-009; het blijft aanvullend en openstaand.", "",
          "## 6b. Bewijsverzoening VR-045 en MAP-009", ""]
    er = rep["evidence_reconciliation"]
    L += [f"Uitkomst **{er['summary']['outcome']}** ({er['note']}).", ""] + [f"- {x}" for x in er["outcome_explanation"]]
    L += ["", "| Kenmerk | Klasse | In VR-045-uitsnede |", "|---|---|---|"]
    L += [f"| {f['id']} {f['feature']} | {f['class']} | {'ja' if f['in_vr045_crop'] else 'nee'} |" for f in er["features"]]
    L += ["", f"Volledig rapport: `{er['report']}`. De aanvraag steunt niet op MAP-009 (`{er['summary']['map009_role']}`); VR-045 blijft zonder menselijk besluit. "
          f"De eerder gepubliceerde request_hash {', '.join('`'+h+'`' for h in er['stale_request_hashes'])} is verouderd (de aanvraag is inhoudelijk uitgebreid met de bewijsverzoening); er hangt aan die hash geen besluit.", "",
          "## 7. Relatie met de 48 APP-besluiten", ""]
    rel = vr["related_app_decisions"]
    L += ["| APP | Onderwerp | Soort | Relevantie | Status |", "|---|---|---|---|---|"]
    L += [f"| {r['app_id']} | {r['subject']} | {r['kind']} | {r['relevance']} | {r['status']} |" for r in rel]
    L += ["", "Alle 48 blijven OPEN en ongewijzigd. De direct relevante fotoniveau-overlapvragen (APP-012 voor MAP-003/004/009 en APP-025 voor de schuine reeks) gaan over *foto's*, niet over dit kozijn; "
          "een instance-besluit moet ze daarom expliciet erkennen (laten openstaan of beantwoorden), maar beantwoordt ze niet. Pandkoppeling (APP-002/003/006) hoort bij niveau B en blijft buiten deze aanvraag.", "",
          "## 8. Conflicten en dubbeltellingen", "",
          "- Instance-store: geen verwijzing naar OBS-MAP003-011, OBS-MAP004-006 of OIC-VR-027; alle instances komen uit foto 2 (MAP-002). SOC-001 (MAP-002/MAP-003) is een foto-overlap rond plaat 288, geen claim op dit kozijn.",
          "- Overlap tussen kandidaatgroepen: er is één OIC; twee kandidaten of aanvragen met overlappende observaties worden beide geblokkeerd.",
          "- Geen foto-2-object, APP-besluit of pilotbesluit wordt geraakt (hash-gecontroleerd door de tests en de scope guard).",
          "- Bewijs bestaat uit visuele lezing; een niet-visueel anker (bv. leesbaar nummer bij dit raam) ontbreekt. Dat is zichtbaar gemaakt, niet weggepoetst.", "",
          "## 9. Verboden effecten (blijven verboden)", ""]
    L += [f"- `{e}`" for e in rep["forbidden_effects"]]
    L += ["", "Technisch onmogelijk gemaakt in deze PR: er bestaat geen functie die de instance-store, het pilotregister, de APP-besluiten of de bronobservaties schrijft; `transition()` is een zuivere functie; "
          "`APPROVED_FOR_ACTIVATION` is alleen bereikbaar met een geregistreerd menselijk niveau-A-besluit dat de exacte `request_hash` noemt, en bestaat in deze PR niet als registerbestand.", "",
          "## 10. Wat is wat", ""]
    L += [f"- **{k}**: {v}" for k, v in rep["fact_classes"].items()]
    L += ["", "## 11. Nog vereiste menselijke beslissingen", "",
          "Voor goedkeuring van de fysieke identiteit (alleen niveau A):",
          "1. Het besluit `APPROVE_PHYSICAL_IDENTITY`, `REJECT` of `NEEDS_MORE_EVIDENCE` over de vraag: *tonen OBS-MAP003-011 en OBS-MAP004-006 hetzelfde fysieke kozijn?* "
          "(expliciet, met de request_hash, buiten het chat-pilotbesluit en niet door Claude in te vullen).",
          "2. Erkenning (laten openstaan of beantwoorden) van de direct relevante APP-overlapvragen en van VR-045.",
          "3. Daarna, apart en later: B (pand) en C (hoeveelheid/kosten), elk met een eigen besluit.", "",
          "## 12. Voorstel voor een latere gecontroleerde activatiefase (niet gebouwd)", ""]
    L += [f"{i}. {s}" for i, s in enumerate(rep["later_activation_phase_proposal"], 1)]
    L += ["", "## 13. Effecten van deze PR", "", "```json", json.dumps(rep["effects"], indent=2, ensure_ascii=False), "```", "",
          f"Reviewpakket: `reports/frames/physical_instance_approval_v1/IAR-OIC-VR-027_review_pack.html` (statisch, zelfstandig, zonder formulier).", "",
          f"**STOP.** {rep['stop']}", ""]
    return "\n".join(L)


def _b64(rel):
    return base64.b64encode((ROOT / rel).read_bytes()).decode("ascii")


def render_pack(rep):
    e = html.escape
    req, vr = rep["draft_request"], rep["draft_request"]["validation_results"]
    ver = rep["photo_evidence_summary"]
    h = ["<!doctype html><html lang='nl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
         "<title>Reviewpakket IAR-OIC-VR-027</title><style>",
         ":root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--mut:#555;--line:#ccc;--warn:#fff3cd;--ok:#e6f4ea}",
         "@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#aaa;--line:#444;--warn:#4a3d10;--ok:#173a22}}",
         "body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:980px;margin:0 auto;padding:16px}",
         "img{max-width:100%;border:1px solid var(--line)}table{border-collapse:collapse;width:100%}td,th{border:1px solid var(--line);padding:6px;vertical-align:top;text-align:left}",
         ".warn{background:var(--warn);padding:10px;border-radius:6px}.ok{background:var(--ok);padding:10px;border-radius:6px}pre{overflow:auto;border:1px solid var(--line);padding:8px}</style></head><body>",
         f"<h1>Reviewpakket {e(req['approval_request_id'])}</h1>",
         "<p class='warn'><b>Dit is geen goedkeuring en geen instance.</b> Alleen niveau A (is dit hetzelfde fysieke kozijn?) ligt voor. Pand (B) en hoeveelheid/kosten (C) vallen erbuiten. "
         "Niets op deze pagina wordt opgeslagen of verstuurd.</p>",
         f"<p>Aanvraag-hash <code>{e(req['request_hash'])}</code> · status <b>{e(req['approval_status'])}</b> · technisch oordeel <b>{e(vr['technical_verdict'])}</b> "
         "(technisch geschikt voor beoordeling, niet: goedgekeurd).</p>",
         "<h2>De vraag</h2><p>Tonen <b>OBS-MAP003-011</b> (MAP-003) en <b>OBS-MAP004-006</b> (MAP-004) hetzelfde fysieke kozijn? "
         "Keuzes voor een later, apart besluit: APPROVE_PHYSICAL_IDENTITY, REJECT of NEEDS_MORE_EVIDENCE.</p><h2>Beeldmateriaal</h2>"]
    for rel, cap in FIGS:
        h.append(f"<figure><img alt='{e(cap)}' src='data:image/jpeg;base64,{_b64(rel)}'><figcaption>{e(cap)} <small>({e(rel)})</small></figcaption></figure>")
    h.append("<h2>Wat voor het verband pleit</h2><ul>")
    for a in ver["additional_matches"] or []:
        h += [f"<li><b>{e(a['photo_id'])}</b>: {e(x)}</li>" for x in a["arguments"]]
    h.append("</ul><h2>Tegenvoorbeelden en beperkingen</h2><ul>")
    for a in ver["additional_matches"] or []:
        h += [f"<li>{e(x)}</li>" for x in a["limits"]]
    h += [f"<li>{e(q)}</li>" for q in req["unresolved_questions"] + req.get("derived_open_questions", [])]
    h.append("<li>Tegenvoorbeeld MAP-007: zelfde raamtype bij een ander huis. Buurramen halen tot 54 feature-match-inliers; feature-match onderscheidt niet.</li>")
    h.append("<li>De MAP-009-lezing is een handmatige beoordeling door Claude. De P1-kwaliteitsreview van VR-045 noemt MAP-009 onvoldoende en stelt UNDECIDABLE voor; er is geen menselijk besluit over VR-045.</li></ul>")
    er = rep["evidence_reconciliation"]
    h.append(f"<h2>Bewijsverzoening VR-045 en MAP-009: {e(er['summary']['outcome'])}</h2><p>{e(er['note'])}</p><ul>")
    h += [f"<li>{e(x)}</li>" for x in er["outcome_explanation"]]
    h.append("</ul>")
    for rel, cap in RC_FIGS:
        h.append(f"<figure><img alt='{e(cap)}' src='data:image/jpeg;base64,{_b64(rel)}'><figcaption>{e(cap)} <small>({e(rel)})</small></figcaption></figure>")
    h.append("<table><tr><th>Kenmerk</th><th>Klasse</th><th>In VR-045-uitsnede</th><th>Opmerking</th></tr>")
    for f in er["features"]:
        h.append(f"<tr><td>{e(f['id'])} {e(f['feature'])}</td><td>{e(f['class'])}</td><td>{'ja' if f['in_vr045_crop'] else 'nee'}</td><td>{e(f['comment'])}</td></tr>")
    h.append("</table>")
    h.append(f"<p>MAP-009-rol: <b>{e(er['summary']['map009_role'])}</b>; VR-045 zonder menselijk besluit; verouderde request-hash(es): {e(', '.join(er['stale_request_hashes']))}.</p>")
    h.append("<h2>Technische controles</h2><table><tr><th>Check</th><th>Resultaat</th><th>Detail</th></tr>")
    for c in vr["checks"]:
        h.append(f"<tr><td>{e(c['id'])} {e(c['title'])}</td><td>{e(ICON[c['result']])}</td><td>{e(_flat(c['detail']))}</td></tr>")
    h.append("</table><h2>Open APP-besluiten die dit raken</h2><table><tr><th>APP</th><th>Onderwerp</th><th>Relevantie</th><th>Status</th></tr>")
    for r in vr["related_app_decisions"]:
        h.append(f"<tr><td>{e(r['app_id'])}</td><td>{e(r['subject'])}</td><td>{e(r['relevance'])}</td><td>{e(r['status'])}</td></tr>")
    h.append("</table><h2>Wat een mens nog moet beslissen</h2><ul>")
    h += [f"<li>{e(x)}</li>" for x in req["required_human_decisions"]]
    h.append("<li>Het niveau-A-besluit zelf (apart, met de request_hash; niet door Claude in te vullen).</li></ul>")
    tmpl = {"decision_id": "(door het latere besluitenregister toe te kennen)", "request_id": req["approval_request_id"], "request_hash": req["request_hash"],
            "decision": "(APPROVE_PHYSICAL_IDENTITY | REJECT | NEEDS_MORE_EVIDENCE)", "level": "A", "covers_levels": ["A"], "decided_by": "(naam van de beslisser)",
            "decision_source": "HUMAN", "statement": "(eigen verklaring)", "acknowledged_app_decisions": [r["app_id"] for r in vr["related_app_decisions"] if r["relevance"] == "DIRECT"]}
    h.append("<h2>Vorm van een later besluitrecord</h2><p class='ok'>Voorbeeld van de vorm, <b>niet ingevuld, niet geregistreerd en zonder werking</b>. Verifieerbaarheid vraagt registratie in een apart besluitenregister.</p>")
    h.append(f"<pre>{e(json.dumps(tmpl, indent=2, ensure_ascii=False))}</pre></body></html>")
    return "\n".join(h)
