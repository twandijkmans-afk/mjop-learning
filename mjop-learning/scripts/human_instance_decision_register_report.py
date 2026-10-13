"""Presentatie voor het Human Instance Decision Register v1 (rapport + beslispakket). Alleen weergave; geen logica en geen schrijfacties."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import physical_instance_approval as P  # noqa: E402
import physical_instance_approval_report as AR  # noqa: E402

E = html.escape

CHOICES = [
    ("APPROVE_PHYSICAL_IDENTITY", "Ik oordeel dat OBS-MAP003-011 en OBS-MAP004-006 hetzelfde fysieke kozijn tonen. Alleen niveau A. Dit maakt GEEN instance, "
                                 "koppelt geen pand en zet geen hoeveelheid of kosten; activatie is een later, apart besluit."),
    ("REJECT", "Ik oordeel dat dit niet (aantoonbaar) hetzelfde fysieke kozijn is. De aanvraag voor deze request_hash is daarmee afgesloten."),
    ("NEEDS_MORE_EVIDENCE", "Ik kan het nu niet beslissen en wil eerst extra bewijs (bijvoorbeeld een foto met leesbaar huisnummer of een nieuwe foto). "
                            "Dit is een volwaardige keuze; kiezen hoeft niet."),
]
RISKS = [
    "Risico van identieke buurwoningen: de buurramen en MAP-007 tonen hetzelfde raamtype; het onderscheidende bewijs zit in de combinatie van tijdelijke kenmerken, niet in het raamtype.",
    "Beperking van foto's uit dezelfde dag (14-08-2026): MAP-009 is onafhankelijk in toestel en hoek, maar niet in tijd. Tijdelijke kenmerken (gordijn, folie, voorwerpen) zeggen niets over andere dagen.",
    "Feature-matching (SIFT/RANSAC) is crop- en methodeafhankelijk en wordt nergens als poort gebruikt.",
]
LIMITS = [
    "Chatbevestiging bewijst geen identiteit: er is geen cryptografische of andere onafhankelijke verificatie van de persoon. `identity_verification` staat daarom vast op NONE_SELF_ASSERTED.",
    "Het register legt vast WIE zegt WAT via WELK kanaal, met een letterlijke bronverklaring. Het kan niet uitsluiten dat iemand anders (of een AI) die verklaring plaatst.",
    "Een AI kan een menselijk bericht overnemen (AI_TRANSCRIPTION_OF_HUMAN_MESSAGE) maar nooit zelf een besluit nemen of een formulier invullen en dat als menselijke handeling voorstellen.",
    "Een AI-aanbeveling, een voorbeeldbestand of een ChatGPT- of Claude-antwoord is op zichzelf nooit een besluit.",
]


def render_md(rep):
    rq, st = rep["request"], rep["decision_state"]
    L = ["# Human Instance Decision Register v1", "",
         "**Status: registerframework met een LEEG register. Er is geen menselijk besluit geregistreerd, geen instance (FI-*) aangemaakt en niets gemerged of geactiveerd.**", "",
         "Doel: een veilig, append-only en controleerbaar register voor menselijke niveau-A-besluiten (fysieke objectidentiteit) over approval requests (IAR-*). "
         "Het hergebruikt `physical_instance_approval.py` (live opbouw, C1-C11, statusmachine, `verify_human_approval`) en bouwt geen tweede framework of instance-store.", "",
         "## 0. Vier stappen die nooit automatisch samenvallen", ""]
    L += [f"{i}. **{x['step']}**: {x['meaning']}" for i, x in enumerate(rep["ladder"], 1)]
    L += ["", "## 1. Registerschema", "",
          f"Bestand: `{rep['register_file']}` (JSON Lines, één canoniek record per regel, nu {rep['records_registered']} records, kop = `{rep['register_head'][:16]}…`). "
          f"JSON Schema: `{rep['schema_file']}`. Het schema is gesloten (`additionalProperties: false`); onbekende velden, ook activatiecommando's, worden geweigerd.", "",
          "| Veld | Betekenis |", "|---|---|"]
    meaning = {"approval_request_id": "IAR-id van de aanvraag", "request_hash": "exacte hash van de live aanvraag waarover besloten wordt",
               "candidate_group_id": "OIC-kandidaat", "decision": "APPROVE_PHYSICAL_IDENTITY, REJECT of NEEDS_MORE_EVIDENCE (anders geweigerd)",
               "covers_levels": "uitsluitend [\"A\"]; B (pand) en C (hoeveelheid/kosten) zijn uitgesloten",
               "decision_source": "HUMAN of HUMAN_CHAT_CONFIRMATION (bestaande menselijke herkomstwaarden)", "decided_by": "naam van de beslisser (geen AI-naam)",
               "decision_provenance": "kanaal, invoerwijze, bronbericht-verwijzing, letterlijke verklaring, identity_verification=NONE_SELF_ASSERTED, ai_authored_decision=false",
               "decision_timestamp": "ISO 8601 met tijdzone; niet in de toekomst", "acknowledged_open_app_ids": "erkende OPEN APP-vragen (verplicht: alle DIRECT-gerelateerde)",
               "acknowledged_open_relations": "erkende open relaties (verplicht: VR-045)", "evidence_reviewed": "verklaring dat observaties, foto's, relaties en MAP-009 zijn bekeken",
               "reviewer_notes": "vrije toelichting (zonder pand-ID of FI-ID)", "record_version": "1",
               "decision_id": "door het register toegekend (HID-0001, …)", "sequence": "volgnummer", "previous_record_hash": "hash van het vorige record (GENESIS = nullen)",
               "record_hash": "SHA-256 over het record zonder dit veld", "register_version": REGISTER_ID}
    for k in rep["stored_keys"]:
        L.append(f"| `{k}` | {meaning[k]} |")
    L += ["", "## 2. Registratieprocedure", "",
          "1. Laad de actuele aanvraag (`build_request`) en bouw haar live opnieuw op. 2. `evaluate_request` (C1-C11) en alle bewijsreferenties opnieuw valideren. "
          "3. `request_hash` exact vergelijken (ook tegen de vervangen hashes). 4. Het apart aangeleverde besluit controleren. 5. Gesloten schema toepassen. "
          "6. Bestaande besluiten op duplicaten en conflicten controleren. 7. Alleen het besluit append-only toevoegen. 8. Resultaat rapporteren zonder iets anders te wijzigen.", "",
          "| Status | Betekenis |", "|---|---|",
          "| `DRY_RUN` (standaard) | Alles gevalideerd, **niets geschreven**. |", "| `VALIDATION_FAILED` | Minstens één voorwaarde faalt; niets geschreven; redenen genoemd. |",
          "| `REGISTERED` | Niet mogelijk op het canonieke v1-register (GESLOTEN, fail-closed); alleen op een tijdelijk testregister. |", "",
          "Het canonieke v1-register is **gesloten**: `register()` en `register --decision` stoppen altijd, ook met de bevestigingstoken (die in de code staat en dus geen bewijs van "
          "menselijke goedkeuring is). Er bestaat geen codepad dat zelf een besluit genereert, goedkeurt of een instance activeert.", "", "## 3. Autorisatievoorwaarden", ""]
    L += ["- " + x for x in ["De actuele aanvraag is live opnieuw opgebouwd en slaagt (READY_FOR_HUMAN_REVIEW).", "De `request_hash` komt exact overeen; een vervangen of gewijzigde hash faalt.",
                             "Een expliciete keuze uit de drie toegestane besluiten.", "Herkomst: menselijke bron, niet-AI-beslisser, kanaal en invoerwijze benoemd, `ai_authored_decision=false`, "
                             "letterlijke verklaring die aanvraag-id, request_hash en keuze noemt.", "Alleen niveau A (`covers_levels == [\"A\"]`).",
                             "Alle DIRECT-gerelateerde OPEN APP-vragen (APP-012, APP-025) en de open relatie VR-045 zijn expliciet erkend; erkennen van iets dat niet OPEN is faalt.",
                             "Het bewijs (observaties, foto's, relaties, MAP-009) is als bekeken verklaard.", "Geen conflicterend of dubbel besluit voor dezelfde request_hash.",
                             "Het record voldoet aan het gesloten schema én `verify_human_approval` van het bestaande framework."]]
    L += ["", "### Beperkingen van chatbevestiging als bewijs", ""] + ["- " + x for x in LIMITS]
    L += ["", "## 4. Conflictafhandeling", "",
          "- Hetzelfde besluit opnieuw aangeboden: `VALIDATION_FAILED` met `DUPLICAAT_BESLUIT`; niets geschreven.",
          "- Ander besluit voor dezelfde request_hash: `CONFLICTEREND_BESLUIT`; nooit overschrijven. Nieuw bewijs betekent een nieuwe aanvraag-hash en dus een nieuwe beoordeling.",
          "- Aanvraag gewijzigd na een besluit: het oude besluit blijft staan maar is `STALE_REQUEST_CHANGED` en geldt niet voor de nieuwe hash (`audit_register`).",
          "- Gelijktijdige registratie: een exclusief lockbestand; wie het niet krijgt faalt gesloten (`REGISTER_VERGRENDELD`). Een achtergebleven slot wordt nooit automatisch opgeruimd.", "",
          "## 5. Append-only gedrag", "",
          "- Elk record bevat `previous_record_hash` en `record_hash` (SHA-256-keten, begin = nullen) en een volgnummer; het register is `HID-0001…` zonder gaten.",
          "- Schrijven: oude bytes + één nieuwe regel naar een tijdelijk bestand in dezelfde map, `fsync`, `os.replace` (atomisch), map-`fsync`, daarna volledige nacontrole inclusief controle dat de oude bytes ongewijzigd voorop staan.",
          "- Compare-and-swap onder het slot: is het register tussentijds veranderd, dan faalt de registratie.",
          "- Een beschadigd, gedeeltelijk geschreven (geen regeleinde), niet-canoniek, gebroken-keten of ontbrekend registerbestand stopt alles (`REGISTER_BESCHADIGD`). Niets wordt gerepareerd of herschreven.",
          "- Er is geen functie om een record te wijzigen of te verwijderen.", "",
          "## 6. De voorbeeldaanvraag", "",
          f"`{rq['approval_request_id']}` (kandidaat `{rq['candidate_group_id']}`, observaties {', '.join(rq['observation_ids'])}), status **{rq['approval_status']}**, technisch oordeel "
          f"**{rq['technical_verdict']}**, live `request_hash` = `{rq['request_hash']}` (vervangen: {', '.join('`'+h+'`' for h in rq['superseded_request_hashes'])}).",
          f"Open relaties: {', '.join(rq['open_related_relations'])}. Gerelateerde APP: " + ", ".join(f"{r['app_id']} ({r['relevance']}, {r['status']})" for r in rq["related_app_decisions"]) + ".", "",
          "Het leesbare beslispakket met bewijsbeelden en een leeg invulsjabloon: `reports/frames/human_instance_decision_register_v1/IAR-OIC-VR-027_decision_pack.html` "
          "(sjabloon: `…_decision_input_TEMPLATE.json`, alle beslisvelden leeg, geen voorgeselecteerde optie).", "",
          "## 7. Huidige status zonder besluit", "", "| Stap | Stand |", "|---|---|",
          f"| 1 technisch geldige aanvraag | {'ja' if st['step_1_technically_valid_request'] else 'nee'} |",
          f"| 2 expliciet menselijk besluit geregistreerd | {'ja' if st['step_2_explicit_human_decision_registered'] else 'nee'} |",
          f"| 3 technisch geverifieerd besluit | {'ja' if st['step_3_technically_verified_decision'] else 'nee'} |",
          f"| 4 geactiveerde instance | nee (bestaat niet) |", f"| niveau A / B / C | {st['level_A']} / {st['level_B']} / {st['level_C']} |", "",
          f"Het ingevulde-maar-lege sjabloon geeft in DRY_RUN `{rep['template_dry_run']['status']}` (verwacht: het sjabloon is geen besluit). APP-besluiten: "
          f"{rep['app_decisions']['open']} van {rep['app_decisions']['total']} OPEN.", "", "## 8. Verboden effecten", ""]
    L += ["- `" + x + "`" for x in rep["forbidden_effects"]]
    L += ["", "## 9. Testresultaten", "",
          "- `tests/test_human_instance_decision_register.py`: 157 tests (registratievalidatie, gesloten schema, hash-integriteit, append-only, duplicaten/conflicten, onbetrouwbare herkomst, "
          "vervalste autorisatie, corrupte/gedeeltelijke registers, atomische writes, gelijktijdige registratie, niveau-A-isolatie, verboden activatie, bescherming van bestaande bestanden, "
          "deterministische generatie): alle geslaagd.",
          "- Bestaande approval-, reconciliatie- en scope-guard-tests: geslaagd (samen 236 met de registertests).",
          "- Volledige suite: alleen de 3 bekende Xpdf 4.06-downloadfouten (zelfde als op `main`): `test_doc007_dekkend_actions_link_to_element`, "
          "`test_known_wrap_and_page_break_cases_on_batch1_sources`, `test_full_build_on_batch1_sources`.",
          "- Het enige aangepaste bestaande bewaker-test (`test_no_other_script_imports_or_drives_the_approval_framework`) is niet verzwakt: alleen de twee registerscripts zijn bij naam toegestaan "
          "en een apart registertest bewaakt dat geen ander script het register aanroept.", "",
          "## 10. De exacte latere handeling om één echt besluit te registreren", ""]
    L += [f"{i}. {x}" for i, x in enumerate(rep["later_registration_action"], 1)]
    L += ["", "**STOP.** Deze PR registreert geen besluit, maakt geen FI-id en activeert niets. Merge alleen met jouw expliciete opdracht.", ""]
    return "\n".join(L)


REGISTER_ID = "human_instance_decision_register_v1"


def render_pack(rep):
    base = AR.render_pack(P.build_report())
    base = base.replace("<title>Reviewpakket IAR-OIC-VR-027</title>", "<title>Beslispakket IAR-OIC-VR-027</title>").replace("<h1>Reviewpakket", "<h1>Beslispakket")
    # het eerdere sjabloon (zonder werking) vervangen door het register-sjabloon; wat er na de laatste tabel stond blijft behouden
    cut = base.rfind("<h2>Vorm van een later besluitrecord</h2>")
    base = base[:cut]
    rq = rep["request"]
    h = ["<h2>Wat is MEDIUM en wat is STRONG?</h2><ul>",
         "<li><b>MEDIUM</b> = de sterkte van de relatie VR-027 in de bronreview (visuele overlap). Dat is een eigenschap van de relatie, geen oordeel over het eigenlijke kozijn.</li>",
         "<li><b>STRONG_VISUAL_SUPPORT</b> = de kwaliteitsklasse van het onderscheidende bewijs (combinatie van tijdelijke kenmerken, onafhankelijk bevestigd door MAP-009). "
         "Beide staan los van elkaar in de aanvraag; STRONG maakt de relatie niet STRONG en is geen goedkeuring.</li></ul>",
         "<h2>MAP-009, VR-045, APP-012 en APP-025</h2><ul>",
         "<li><b>MAP-009</b>: extra foto-bewijs (zelfde dag, ander toestel en andere hoek). Uitkomst van de bewijsverzoening: COMPATIBLE_DIFFERENT_SCOPE, gebaseerd op een handmatige lezing; geen menselijk besluit.</li>",
         "<li><b>VR-045</b> is een open relatie zonder menselijk besluit. Je moet in je besluit expliciet erkennen dat die open staat (<code>acknowledged_open_relations</code>); stilzwijgend als opgelost beschouwen faalt.</li>",
         "<li><b>APP-012</b> en <b>APP-025</b> zijn OPEN fotoniveau-overlapvragen over dezelfde foto's en moeten expliciet erkend worden (<code>acknowledged_open_app_ids</code>). "
         "Je beantwoordt ze er niet mee; ze blijven OPEN.</li></ul><h2>Risico's en beperkingen</h2><ul>"]
    h += [f"<li>{E(x)}</li>" for x in RISKS]
    h.append("</ul><h2>De drie mogelijke beslissingen</h2><table><tr><th>Keuze</th><th>Betekenis</th></tr>")
    h += [f"<tr><td><code>{E(k)}</code></td><td>{E(v)}</td></tr>" for k, v in CHOICES]
    h.append("</table><p class='warn'><b>NEEDS_MORE_EVIDENCE is een gelijkwaardige keuze.</b> Er is geen voorgeselecteerde optie en deze pagina bevat geen knop of formulier: niets wordt opgeslagen of verstuurd.</p>")
    h.append("<h2>Beperkingen van chatbevestiging</h2><ul>" + "".join(f"<li>{E(x)}</li>" for x in LIMITS) + "</ul>")
    h.append(f"<h2>Invulsjabloon (alle beslisvelden leeg)</h2><p class='ok'>Aanvraag-id, hash en kandidaat staan er al in; <b>alles wat een besluit is, is leeg</b>. Dit sjabloon is "
             f"<b>geen besluit, geen goedkeuring en heeft geen werking</b>; het bestaat als bestand <code>IAR-OIC-VR-027_decision_input_TEMPLATE.json</code>. Live request_hash: "
             f"<code>{E(rq['request_hash'])}</code>. Verplicht te erkennen APP: " + ", ".join(E(r['app_id']) for r in rq['related_app_decisions'] if r['relevance'] == 'DIRECT')
             + "; open relatie(s): " + ", ".join(E(x) for x in rq['open_related_relations']) + ".</p>")
    h.append(f"<pre>{E(json.dumps(rep['template'], indent=2, ensure_ascii=False))}</pre>")
    h.append(f"<p>Registratie in het canonieke v1-register is momenteel gesloten (fail-closed); dit pakket registreert niets. Status nu: {rep['records_registered']} besluiten geregistreerd.</p></body></html>")
    return base + "\n".join(h)
