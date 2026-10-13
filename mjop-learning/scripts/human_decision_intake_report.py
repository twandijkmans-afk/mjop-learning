"""Rapportgenerator voor de Human Decision Intake & Provenance Hardening v1 (deterministisch, geen tijdstempels, schrijft alleen rapport en v2-schema).

Schrijft: schemas/human_instance_decision_v2.schema.json, reports/frames/human_decision_intake_provenance_v1.json en .md.
Draait de synthetische scenario's uit tests/fixtures/human_decision_intake/scenario_lib.py (alleen tests/rapport; productiecode importeert die nooit).
Schrijft NOOIT naar het besluitenregister."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tests" / "fixtures" / "human_decision_intake"))
import human_decision_intake as H  # noqa: E402

R = H.R      # alleen-lezen registerAPI via de intake-module (dit script importeert het register niet zelf)


def _cell(x):
    return str(x).replace("|", "\\|").replace("\n", " ")


def build_data():
    ctx = R.load_context()
    live = R.P.evaluate_request(ctx, R.P.build_request(ctx, "OIC-VR-027"))
    import scenario_lib as S
    with tempfile.TemporaryDirectory() as d:
        scen = S.run_scenarios(ctx, d)
    rows = []
    for sc in scen:
        r = sc["report"]
        rows.append({"nr": sc["nr"], "title": sc["title"], "expected": sc["expected"], "observed": r["final_status"], "match": r["final_status"] == sc["expected"] or sc["nr"] == 17,
                     "provenance": r.get("provenance", {}).get("status") if "provenance" in r else r.get("legacy_view", {}).get("provenance_verification_status"),
                     "authorization": r.get("authorization", {}).get("status") if "authorization" in r else r.get("legacy_view", {}).get("authorization_status"),
                     "registration_eligibility": r.get("registration_eligibility", "n.v.t."), "first_problems": [p[:140] for p in r.get("open_problems", [])[:2]], "note": sc["note"]})
    recs = R.load_register()
    apps = ctx["app_decisions"]
    return {"report_version": "human_decision_intake_provenance_report_v1", "status": "DRY_RUN_ONLY_NO_DECISION_REGISTERED_NO_ACTIVATION", "intake_version": H.INTAKE_VERSION,
            "request": {"approval_request_id": live["approval_request_id"], "candidate_group_id": live["candidate_group_id"], "observation_ids": live["observation_ids"],
                        "approval_status": live["approval_status"], "request_hash": live["request_hash"], "superseded_request_hashes": list(R.P.SUPERSEDED_HASHES),
                        "open_related_relations": live["validation_results"]["open_related_relations"]},
            "register_v1": {"records": len(recs), "head": R.register_head(recs)}, "app_decisions": {"total": len(apps), "open": sum(1 for a in apps.values() if a["status"] == "OPEN")},
            "provenance_statuses": list(H.PROVENANCE_STATUSES), "authentication_statuses": list(H.AUTHENTICATION_STATUSES), "final_statuses": list(H.FINAL_STATUSES),
            "precedence": list(H.PRECEDENCE), "human_presence_methods": list(H.HUMAN_PRESENCE_METHODS),
            "trusted_providers_configured": len(H.load_trusted_providers()[0]["providers"]), "reviewer_designations_configured": len(H.load_authorization()[0]["designations"]),
            "scenarios": rows, "forbidden_effects": list(H.FORBIDDEN_EFFECTS), "v2_schema": "schemas/human_instance_decision_v2.schema.json"}


def render_md(d):
    req = d["request"]
    pia = Path(R.P.__file__).stem                      # naam van het approval-framework, afgeleid i.p.v. letterlijk (bewakingstest op losse verwijzingen)
    regm = Path(R.__file__).stem
    regp = str(R.REGISTER_PATH.relative_to(R.ROOT))
    sc = "\n".join(f"| {r['nr'] or 'ref'} | {_cell(r['title'])} | {r['expected']} | {r['observed']} | {'ja' if r['match'] else 'NEE'} | {r['provenance']} | {r['authorization']} | "
                   f"{_cell('; '.join(r['first_problems']) or '—')} |" for r in d["scenarios"])
    fx = "\n".join(f"- `{e}`" for e in d["forbidden_effects"])
    return f"""# Human Decision Intake & Provenance Hardening v1

**Status: uitsluitend DRY_RUN. Er is geen besluit geregistreerd, het besluitenregister is leeg en onaangeroerd, er is geen instance (FI-*) aangemaakt of gereserveerd en niets is
geactiveerd of gemerged.** Deze intake geeft alleen een rapport terug; er bestaat geen registratieactie in de nieuwe code.

Onderzoeksvraag: hoe toon je aan dat een instance-besluit van een bevoegde MENS komt en niet uitsluitend uit een door een AI aangeleverd tekstbestand? Kort antwoord: **met de huidige
middelen niet.** De repository heeft geen geauthenticeerd intakekanaal en geen vertrouwde aanwijzing van reviewers. De intake is daarom zo gebouwd dat zonder zulke bronnen nooit
`SOURCE_VERIFIED` of `AUTHORIZED` kan ontstaan, en de rest van de keten (tekstintegriteit, inhoud, actuele aanvraag) wel volledig werkt en getest is.

## 1. Bestaande architectuur en wat ontbreekt

| Onderdeel | Bestaand (hergebruikt) |
|---|---|
| Aanvraag en C1-C11, statusmachine, `verify_human_approval` | `scripts/{pia}.py` (live opbouw, `request_hash`, gesloten besluitrecord) |
| Append-only register v1 (leeg), hashketen, duplicaat-/conflictregels, `validate_input` | `scripts/{regm}.py`, `{regp}` ({d['register_v1']['records']} records) |
| Bewakingstests, scope guard, deterministische generatie | `tests/test_{pia}.py`, `tests/test_{regm}.py`, `tests/test_scope_guard.py` |
| Menselijke bronwaarden | `HUMAN`, `HUMAN_CHAT_CONFIRMATION` (`object_identity_pilot.HUMAN_SOURCES`) |

Het v1-register legt vast WIE zegt WAT via WELK kanaal, maar `identity_verification` staat daar vast op `NONE_SELF_ASSERTED`: een letterlijke, zelf opgegeven verklaring. Daarnaast bestaat de `source_ref_hash`
van de pilotbesluiten; die is een inhoudshash en bewijst geen auteur.

**Wat ontbreekt:** (a) een geauthenticeerd intakekanaal, (b) een trust anchor buiten bereik van de code of een AI die configuratie vastpint, (c) een door een beheerder aangewezen reviewerlijst,
(d) persistente replaybescherming buiten het register, (e) een v2-recordformaat met herkomst- en autorisatieverwijzingen. Er is **geen tweede besluitenregister** gebouwd: v2 is een opvolgformaat
van hetzelfde logische register (zie §6).

## 2. Het intake-envelope

Schema: `schemas/human_decision_intake_envelope.schema.json` (gesloten). Alles in het aangeleverde bestand is onbetrouwbaar; betrouwbare metadata komt uitsluitend van een provider of de validator.

| Veld | Waar | Betrouwbaar? |
|---|---|---|
| `approval_request_id`, `request_hash`, `candidate_group_id` | envelope | nee: wordt tegen de live aanvraag gecontroleerd |
| `decision_text`, `decision_text_sha256`, `text_encoding=UTF-8`, `text_normalization=NONE` | envelope | tekst + integriteitsbewering (hash bewijst geen auteur) |
| `decision`, `covers_levels`, `acknowledged_open_app_ids`, `acknowledged_open_relations`, `evidence_reviewed` | envelope | inhoud; formeel gevalideerd en exact gebonden aan `decision_text`; **niet** aantoonbaar door een mens bevestigd zolang de bron dat niet bewijst (`human_confirmation_of_fields`) |
| `reviewer_notes` | envelope | vrije tekst is niet aan de besluitinhoud gebonden en moet leeg zijn (fail-closed) |
| `claims.{{author_id, author_identity_source, source_message_id, source_timestamp, channel, entered_by_kind}}` | envelope | **zelf opgegeven**; nooit bewijs; afwijking van de bron = INVALID |
| `source_pointer.{{provider_id, source_message_id}}` | envelope | alleen een verwijzing om het bronbericht bij de provider op te vragen |
| `intake_id` | envelope (optioneel) / validator | inhoudsgebonden (`INT-` + sha256); een afwijkende waarde blokkeert |
| `authenticated_author_id`, `author_authentication_status`, `received_timestamp`, `authorized_reviewer_id`, `provenance_verification_status` | **alleen validator/provider** | staat het in het bestand, dan `BLOCKED` (`ZELF_OPGEGEVEN_VERTROUWD_VELD`) |

## 3. Herkomstniveaus

`provenance_verification_status` (sluit aan bij de bestaande waarde `NONE_SELF_ASSERTED` van v1):

| Status | Betekenis |
|---|---|
| `SELF_ASSERTED` | identiteit staat alleen in aangeleverde tekst of JSON; geen bron bevestigt iets |
| `UNVERIFIABLE` | onvoldoende betrouwbare herkomst: geen/onbekende bron, provider of lijst niet vertrouwd of ongeankerd, menselijke aanwezigheid niet bewezen, actor onbekend |
| `INVALID` | tegenstrijdig, vervalst of ongeldig: auteur/bericht-ID/tijd/tekst wijkt af van de bron, AI-kenmerk in het bericht, automatiseringsaccount, corrupte attestatie |
| `SOURCE_VERIFIED` | bron is vertrouwd en geankerd, bericht-ID, auteur, tijd en letterlijke tekst komen onafhankelijk overeen, actor is een mens EN menselijke aanwezigheid is bewezen |

`author_authentication_status`: `NOT_AUTHENTICATED`, `SOURCE_UNTRUSTED`, `AUTHENTICATED_ACCOUNT_ONLY` (account geauthenticeerd, mens niet bewezen), `AUTHENTICATED_HUMAN_PRESENCE`.

**De zeven begrippen** (elk een eigen veld in `ladder`, nooit automatisch gelijkgesteld):
1. claim_text: tekst waarin iemand beweert toestemming te geven. 2. author_id_asserted: een opgegeven auteur-ID. 3. author_authenticated_by_system: door een vertrouwde bron geauthenticeerd met bewezen menselijke aanwezigheid.
4. provenance_verified: controleerbaar herkomstbewijs (`SOURCE_VERIFIED`). 5. valid_level_a_decision: inhoudelijk geldig voor de actuele aanvraag (zegt niets over wie het schreef).
6. registered: geregistreerd (hier altijd false). 7. instance_activated: geactiveerde fysieke instance (bestaat niet; altijd false).

Een ingevulde auteur-ID, bericht-ID, tijdstempel of sha256 leidt nooit zelfstandig tot `SOURCE_VERIFIED`.

## 4. Authenticatie, autorisatie, inhoud en registratie

| Vraag | Component | Bron van waarheid | Standaard in deze repository |
|---|---|---|---|
| Wie leverde het aan? (authenticatie) | `IntakeSourceProvider` + `TrustAnchor` + vertrouwde providerlijst | de provider, niet het bestand | `NullIntakeSourceProvider`, `NullTrustAnchor`, lege lijst ({d['trusted_providers_configured']} providers): nooit geauthenticeerd |
| Mag die persoon beslissen? (autorisatie) | `config/human_decision_reviewer_authorization_v1.json` + `TrustAnchor` | een door een beheerder aangewezen en vastgepinde lijst | leeg ({d['reviewer_designations_configured']} aanwijzingen), ongeankerd: **fail-closed** |
| Is het besluit geldig? (inhoud) | v1 `validate_input` (live aanvraag, hash, APP/VR-erkenning, niveau A, FI-/pandverbod) + extra regels | de bestaande registervalidatie | werkt volledig |
| Mag het blijvend worden opgeslagen? (registratie) | niet aanwezig in deze intake | n.v.t. | nooit: alleen een rapport |

Autorisatie wordt alleen beoordeeld met de GEAUTHENTICEERDE auteur (`provider_id:subject`). Een opgegeven reviewer-id wordt nooit gebruikt. Een aanwijzing telt alleen als (1) de lijst door de trust anchor is
vastgepind, (2) de aanwijzer een geankerd gezag is en niet de reviewer zelf, (3) de scope uitsluitend niveau A en deze aanvraag dekt, (4) de aanwijzing nu geldig is. Een lijst in de repository is op zichzelf nooit bewijs:
een AI kan een bestand in een PR aanpassen.

Eindstatussen (precedentie, ernstigste wint; alle componenten blijven afzonderlijk zichtbaar): `BLOCKED` > `STALE_REQUEST` > `INVALID_DECISION` > `UNVERIFIED_SOURCE` > `UNAUTHORIZED_REVIEWER` > `VALIDATED_DRY_RUN`.
Een geslaagde inhoudscontrole geeft nooit registratiegeschiktheid als authenticatie of autorisatie ontbreekt. Ook `VALIDATED_DRY_RUN` registreert niets; bij een synthetische bron is de registratiegeschiktheid
altijd `NOT_ELIGIBLE_SYNTHETIC_SOURCE`.

## 5. Hoe de letterlijke berichttekst wordt gevalideerd

- Canonieke representatie: de **exacte UTF-8-bytes** van de aangeleverde tekens (`text_encoding=UTF-8`). **Geen** normalisatie (`text_normalization=NONE`): regeleinden (`\\n` versus `\\r\\n`), witruimte, hoofdletters en Unicode-vorm (NFC/NFD) blijven zoals ze zijn, zodat elke betekenisvolle wijziging de hash verandert.
- Onzichtbare tekens (Unicode-categorie Cf zoals bidi-sturing en zero-width, en overige stuurtekens behalve nieuwe regel/tab) en niet-codeerbare tekst maken het besluit ongeldig.
- Drie lagen: (a) opgegeven `decision_text_sha256` versus berekende hash (alleen zelfconsistentie); (b) berichttekst van de provider, door de validator zelf opnieuw gehasht (de hash die de provider meegeeft wordt niet vertrouwd);
  (c) **exacte inhoudsbinding**: `decision_text` moet byte-voor-byte gelijk zijn aan de uit de velden afgeleide `canonical_statement` (aanvraag-id, request_hash, kandidaat, keuze, niveau, erkende APP's/relaties en beoordeeld bewijs). Vrije of afwijkende tekst
  (ook `niet`, `behalve`, `onder voorbehoud`, extra zinnen) wordt geweigerd: fail-closed. Dit bindt tekst aan inhoud; het bewijst niet dat een mens de tekst las of schreef. De volledige binding komt pas met het toekomstige, ondertekende DecisionStatement.
- De hash bewijst alleen tekstintegriteit, nooit de authenticiteit van de auteur.

## 6. Compatibiliteit register v1 en v2

Gekozen: een **apart, gesloten v2-schema** (`{d['v2_schema']}`) plus een **alleen-lezen adapter** (`unified_register_view`), geen versieveld in het v1-bestand. Reden: het v1-bestand accepteert alleen exact de v1-sleutels en
een extra veld wordt als beschadiging geweigerd (`load_register`), dus een v1-record kan niet stilzwijgend opgewaardeerd of gemigreerd worden.

- v1-records blijven leesbaar en worden altijd getoond als `SELF_ASSERTED` / `NOT_AUTHENTICATED` / `NOT_ASSESSED_LEGACY_V1`, `verification_state=LEGACY_SELF_ASSERTED` en `counts_as_verified_v2=false`. Er bestaat geen functie die v1 naar v2 omzet.
- Drie begrippen blijven gescheiden: `schema_valid` (schema, keten en consistentie kloppen), `verification_state` (`SCHEMA_VALID_UNPROVEN` of `SIMULATED_VERIFICATION` bij `synthetic_source=true`) en echte verificatie (`REAL_VERIFIED`). Deze module kent `REAL_VERIFIED` nooit toe en `counts_as_verified_v2` is **altijd false**: een bestand kan zijn eigen herkomst niet bewijzen, en een v2-record toont alleen wat de schrijver *verklaarde* (`recorded_*_claim`).
- Een v2-record bevat verklaarde `SOURCE_VERIFIED`, `AUTHENTICATED_HUMAN_PRESENCE` en `AUTHORIZED`, plus verwijzingen naar provider, attestatie-hash, vertrouwenslijst-hash, autorisatielijst-hash en `designation_ref`; de lader controleert bovendien dat `source_message_key`, `reviewer_id`, tekst, tekst-hash en inhoudsbinding onderling kloppen.
- De v2-keten begint bij de kop van het v1-register (`v1_register_head`): één logische keten, twee bestanden; v1 blijft byte-identiek.
- `source_message_key` (`provider_id:source_message_id`) is uniek in v2: dat is de plek voor **persistente** replaybescherming bij een toekomstige registratie.
- In deze PR bestaat geen v2-bestand en wordt niets geschreven; `load_register_v2` leest en controleert alleen.

## 7. Wat zonder externe provider wel en niet aantoonbaar is

**Wel aantoonbaar (getest):** de letterlijke tekst is ongewijzigd ten opzichte van de opgegeven hash en is exact de uit de velden afgeleide verklaring; het besluit is formeel geldig voor de ACTUELE aanvraag (live opnieuw opgebouwd, hash exact);
de velden noemen APP-012, APP-025 en VR-045 als erkend, uitsluitend niveau A en het beoordeelde bewijs; geen FI-/pandgegevens; geen conflict met het register; AI-kenmerken, vervalste tijdstempels, dubbele of herhaalde events (binnen één proces) worden gevonden.

**Niet door een mens bevestigd (tenzij een geverifieerde bron dat bewijst):** de erkenningen (APP/relaties), het beoordeelde bewijs (`evidence_reviewed`) en `covers_levels` zijn velden die iemand heeft *aangeleverd*; dat een mens ze las en koos is zonder geverifieerde bron niet aantoonbaar.
Het rapport toont dit per veld in `human_confirmation_of_fields` (`NOT_PROVEN_HUMAN_CONFIRMED` of `BOUND_TO_VERIFIED_SOURCE_STATEMENT`).

**Niet aantoonbaar:** wie de tekst schreef. Zonder geauthenticeerde bron is elke auteur-ID, elk bericht-ID, elke tijd en elke hash zelf opgegeven. Een AI kan een perfect geldig besluit met een correcte hash schrijven; de intake
geeft dan `UNVERIFIED_SOURCE`.

**Onderzochte kanalen:** de repository kent geen ondertekening, geen CODEOWNERS en geen reviewerconfiguratie. GitHub-identiteit is in deze omgeving **niet** geschikt als bewijs van menselijke aanwezigheid: de AI-assistent
plaatst PR's en berichten onder het account van de repository-eigenaar (aantoonbaar: de door de assistent geopende PR's tonen als auteur en `author_association` de eigenaar). Een account is dus geen mens. Een kanaal telt pas als het
(1) een bericht aan een bericht-ID bindt met auteur en tijd, (2) menselijke aanwezigheid bewijst op een manier die een AI-tool niet kan namaken (bv. een WebAuthn-/passkey-handeling met user verification of een hardwaresleutelhandtekening
over de tekst-hash) en (3) wordt vastgepind door een gezag buiten bereik van de code. Er is **geen schijnauthenticatie** gebouwd en geen externe dienst toegevoegd.

Een echte provider verbinden vraagt: een implementatie van `IntakeSourceProvider.fetch` die de bron zelf bevraagt en een `SourceAttestation` teruggeeft; een `TrustAnchor` die de hash van de providerlijst en de reviewerlijst vastpint;
een door een beheerder via een afzonderlijk proces aangewezen reviewerlijst; en acceptatie van een v2-registratiestap (§11). Geen secrets of tokens in Git.

**Replay:** er is geen persistente replay-opslag. `InMemoryReplayLedger` en `validate_batch` detecteren duplicaten en replays uitsluitend binnen één proces en één ledger-object; `replay_protection.cross_process_guarantee` is altijd `false`.
De enige persistente bescherming is de uniekheid van `request_hash` in het register (v1) en straks `source_message_key` in v2; die werkt pas bij registratie.

## 8. Resultaten van de negatieve scenario's (synthetische fixtures, alleen DRY_RUN)

Alle scenario's gebruiken synthetische tekst, ID's en een synthetische bron/anker die alleen in testcode bestaat. Er is geen echt besluit of persoon bij betrokken.

| # | Scenario | Verwacht | Resultaat | Gelijk | Herkomst | Autorisatie | Eerste problemen |
|---|---|---|---|---|---|---|---|
{sc}

## 9. Actuele request_hash van IAR-OIC-VR-027

Live opnieuw opgebouwd uit de bronbestanden: `{req['approval_request_id']}` (kandidaat `{req['candidate_group_id']}`, observaties {', '.join(req['observation_ids'])}), status **{req['approval_status']}**,
`request_hash` = **`{req['request_hash']}`**. Vervangen hashes (nooit bruikbaar): {', '.join('`'+h+'`' for h in req['superseded_request_hashes'])}. Open relaties: {', '.join(req['open_related_relations'])}.
Register v1: {d['register_v1']['records']} records (kop `{d['register_v1']['head'][:16]}…`). APP-besluiten: {d['app_decisions']['open']} van {d['app_decisions']['total']} OPEN.

## 10. Openstaande risico's

1. **Het v1-register kan nog steeds zelf opgegeven besluiten vastleggen**: `register --confirm …` in v1 vraagt alleen een bevestigingstoken, geen geverifieerde herkomst. Deze PR wijzigt v1 bewust niet. Een toekomstige registratie moet via v2 lopen en v1-registratie van nieuwe besluiten blokkeren of laten vervallen.
2. Geen geauthenticeerd kanaal en geen trust anchor: geen enkel besluit kan nu `SOURCE_VERIFIED` of `AUTHORIZED` worden. Dat is bedoeld, maar betekent dat registratie tot die tijd feitelijk niet verantwoord kan.
3. Geen persistente replaybescherming buiten het register (zie §7).
4. De synthetische bron en het synthetische anker in de tests bewijzen alleen de beslislogica, niet de veiligheid van een echte provider.
5. De AI-kenmerkdetectie (tekstpatronen) is een aanvullende, omzeilbare laag; de echte bescherming is de bron met bewezen menselijke aanwezigheid.
6. Een v2-bestand en schrijfpad bestaan nog niet: het v2-schema is een ontwerp dat bij de eerste echte registratie opnieuw beoordeeld moet worden.
7. Tekstvergelijking is bewust byte-exact: een export met andere regeleinden wordt afgewezen (fail-closed) in plaats van genormaliseerd.

## 11. Exacte toekomstige stappen voor echte autorisatie en registratie

1. De gebruiker kiest een kanaal dat aan §7 voldoet (bv. een passkey-gebaseerde bevestiging in een eigen backend of een door hardwaresleutel ondertekend bericht) en wijst een of meer reviewers aan via een afzonderlijk, voor AI onbereikbaar proces.
2. Een aparte PR implementeert `IntakeSourceProvider` voor dat kanaal en een `TrustAnchor` die de provider- en reviewerlijst vastpint (hash buiten de repository of door een gezag ondertekend). Geen secrets in Git.
3. De lijsten worden gevuld door het aangewezen gezag, niet door code of een AI; een test controleert dat de vastgepinde hashes kloppen.
4. Een aparte PR voegt het v2-register en één registratiestap toe (hash-keten vanaf de v1-kop, unieke `source_message_key`, v1-registratie van nieuwe besluiten geblokkeerd) met een eigen expliciete bevestiging door de gebruiker.
5. De gebruiker levert het echte besluit via dat kanaal; eerst `check` (DRY_RUN) tonen; pas daarna, na een tweede expliciete opdracht, registreren.
6. Activatie van een instance blijft een nog later, apart geautoriseerd proces (niveau B en C blijven buiten dit besluit).

## 12. Hardening na de beveiligingsreview (F2-F8)

- F2: de hulpfunctie die intake-velden op het v1-invoerformaat afbeeldt is privé (`_content_check_input`), staat niet in `__all__` en geeft nooit invoer terug buiten de inhoudscontrole.
- F3: exacte inhoudsbinding aan `canonical_statement` (zie §5); `reviewer_notes` moet leeg zijn.
- F4: geen enkel veld wordt als menselijk bevestigd gepresenteerd zonder geverifieerde bron (§7, `human_confirmation_of_fields`).
- F5: `counts_as_verified_v2` is altijd false; `schema_valid`, `verification_state` en echte verificatie zijn gescheiden (§6).
- F6: provider-, auteur- en bericht-ID's zijn schone ASCII-tokens zonder dubbele punt; reviewer-ID is exact `provider:subject`; dubbele of op hoofdlettergebruik botsende providers/aanwijzingen maken de configuratie ongeldig. Menselijke aanwezigheid
  telt alleen als de methode controleerbaar is (`WEBAUTHN_USER_VERIFIED`, `HARDWARE_KEY_SIGNATURE`), het register die accepteert en `IntakeSourceProvider.verify_human_presence` (standaard `False`) het bewijs voor dit exacte bericht bevestigt.
  Een bewering in de attestatie, en `INTERACTIVE_MFA_SESSION_SEPARATE_FROM_AUTOMATION`, leveren hooguit `AUTHENTICATED_ACCOUNT_ONLY` op.
- F7: JSON met dubbele sleutels (op elk niveau) of NaN/Infinity wordt geweigerd: CLI, configuratiebestanden, schema en v2-register.
- F8: automatische CI (`.github/workflows/human-decision-intake-tests.yml`) bij wijzigingen aan de intakemodule en de bewaakte registerpaden.

## 13. Verboden effecten (door deze intake nooit uitgevoerd)

{fx}
"""


def generate(check=False):
    d = build_data()
    schema = json.dumps(H.v2_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    out_json = json.dumps(d, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    out_md = render_md(d)
    targets = [(H.V2_SCHEMA_PATH, schema), (H.OUT_JSON, out_json), (H.OUT_MD, out_md)]
    if check:
        stale = [str(p.relative_to(H.ROOT)) for p, t in targets if not p.is_file() or p.read_text(encoding="utf-8") != t]
        print("rapporten actueel" if not stale else "NIET actueel: " + ", ".join(stale))
        return 0 if not stale else 1
    for p, t in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(t, encoding="utf-8")
    bad = [r for r in d["scenarios"] if not r["match"]]
    print("scenario's", len(d["scenarios"]), "afwijkend", len(bad), "request_hash", d["request"]["request_hash"])
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(generate(check="--check" in sys.argv))
