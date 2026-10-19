# Bruto Quantity Model v2: schema's, vocabulaires en rekenkern (fase 1 en 2)

Aanvullende, versieerbare laag naast de bestaande v1-contracten. Alleen modelleren en deterministisch rekenen. Er worden
geen besluiten geregistreerd, geen goedkeuringen gesimuleerd, geen objecten geactiveerd en geen FI-id's aangemaakt. Er is
geen koppeling met prijzen, kengetallen of kosten en geen wijziging in de MJOP-App.

| Onderdeel | Bestand |
|---|---|
| Begrippen, statussen, lagen, afrondingsregel | `vocabularies/bruto_quantity_concepts_v2.json` |
| Onderhoudsacties (actie, eenheid, meetgrondslag, kengetal, prijseenheid) | `vocabularies/bruto_quantity_actions_v2.json` |
| Maatvoering | `schemas/bruto_dimension_v2.schema.json` |
| Kozijn-/deurtype (geen instance) | `schemas/bruto_frame_type_v2.schema.json` |
| Foto-observatie (verwijzing) | `schemas/bruto_observation_v2.schema.json` |
| Object (of groep identieke objecten) | `schemas/bruto_quantity_object_v2.schema.json` |
| Hoeveelhedenstaat met gescheiden lagen | `schemas/bruto_quantity_state_v2.schema.json` |
| Rekenkern (zuiver, geen bestandstoegang) | `scripts/bruto_quantity_core.py` |
| Laden en validatie (alleen lezen) | `scripts/bruto_quantity_contracts.py` |
| Tests (synthetische fixtures) | `tests/test_bruto_quantity_model_v2.py` |

## Rekenregel

`gross_area_m2 = outer_width_m * outer_height_m * quantity`. Glas wordt niet afgetrokken; vaste en draaiende delen vallen
binnen de buitenmaat en tellen niet extra. Eén compleet kozijn is één object, ongeacht het aantal ramen; een balkondeur
met omliggend kozijn (`FRAME_WITH_DOOR`) is één object. Maten moeten tussen 0,10 en 10 m liggen (zelfde grenzen als de
Photo Reviewer). Alleen `Decimal`; floats, NaN en negatieve waarden worden geweigerd.

## Afronding (B2)

Intern altijd exact (canonieke Decimal-string zonder overbodige nullen). Alleen bij presentatie wordt op 2 decimalen
afgerond, half-up. Het totaal volgt uit de exacte som; subtotalen per typegroep worden met de grootste-restmethode zo
verdeeld dat ze exact optellen tot het afgeronde totaal (regel `ROUND_HALF_UP_2DP_LARGEST_REMAINDER_V1`).

## Maatstatussen en schattingen (B1)

| Status | Oppervlakteklasse | Opmerking |
|---|---|---|
| `MEASURED` | bekend | menselijke meting of gevalideerde referentiemaat; bronverwijzing is geen geauthenticeerde goedkeuring |
| `DRAWING_DERIVED` | bekend | schaalbewijs verplicht |
| `REFERENCE_DERIVED_ESTIMATE` | geschat | afgeleid van betrouwbare referenties; status `ESTIMATED`, `validated_measure` altijd `false` |
| `UNKNOWN` | onbekend | breedte en hoogte `null`; oppervlakte `null`, nooit 0 |

`derive_estimate` vereist een referentietype met minstens één `MEASURED`/`DRAWING_DERIVED` referentie, een categorie die
overeenkomt, een benoemde vergelijkbaarheidsbasis en een reden. Er zijn geen schattingsketens. Het resultaat bewaart
referentietype en referentie-id's, de oorspronkelijke bronnen, de afleidingsmethode, de herkomst van het voorstel
(AI/regel/mens) en de spreiding. Een AI-voorstel is daarmee nooit een gevalideerde maat.

## Lagen

`OBSERVED` (observaties, geen uniek aantal), `PROVISIONAL_UNIQUE` (voorgestelde consolidatie met zekerheid HIGH),
`CONFIRMED` (alleen met door een verifier bevestigde goedkeuring A en C; zonder bron `BLOCKED` en leeg), `ESTIMATED`
(geschatte ontbrekende objecten met aantoonbare herhaling), `REVIEW_LOW_CERTAINTY` (telt nergens als uniek mee) en
`UNKNOWN` (onbekende maat of oppervlakte). De laag van een object wordt afgeleid, nooit door het record zelf opgegeven. Elk
object staat in precies één laag. Aantallen en oppervlakten van verschillende lagen worden nooit opgeteld
(`sum_across_layers` en `combined_total_m2` zijn `null`). Een hoeveelheid krijgt nooit een hogere status dan identiteit,
telling en maatvoering rechtvaardigen: een bevestigd object met een geschatte maat levert geschatte m2.

## Goedkeuringsniveaus (B6)

A fysieke objectidentiteit, B gebouw- of pandtoewijzing, C goedkeuring van hoeveelheden. Dit is gemodelleerd als
`approval_refs` (beweringen met verwijzing en hash). De standaardverifier (`NullApprovalVerifier`) bevestigt niets; een
verifier kan alleen worden geïnjecteerd. De staat heeft vaste waarden `status = PROPOSED`, `release_status = NOT_RELEASED`
en `usable_for_mjop = false`; het schema laat geen andere waarde toe.

## Deuren en onderhoudsacties (B3, B4)

Deuren worden altijd in stuks geregistreerd. Of een losse deur in het bruto m2 meetelt hangt af van `door_treatment`
(`PART_OF_GROSS_FRAME_AREA`, `AS_PIECES`, `NOT_RELEVANT`, `UNDECIDED`; standaard `UNDECIDED`, dus niet in de m2). De staat
maakt nooit onderhoudshoeveelheden. Buitenschilderwerk heeft standaard de grondslag bruto kozijn-m2 (tenzij de historische
bron aantoonbaar iets anders gebruikt); binnenschilderwerk is een afzonderlijke actie waarvan grondslag en hoeveelheid
`UNKNOWN` blijven. `historical_kengetal_ref` en `price_unit` zijn in deze versie altijd `null`.

## Legacy en bescherming van v1 (B5)

`EXTERIOR_WINDOW` en `WINDOW_COUNT` blijven bestaan als legacy begrippen en worden niet als kozijnobjecten geteld of
hergeïnterpreteerd. Het v2-schema is gesloten en kent geen eigen raam- of glastelling. Er worden geen v1-bestanden gelezen,
gewijzigd of gemigreerd; de nieuwe bestanden staan buiten alle bevroren mappen, zodat de scope guard ongewijzigd blijft.

## Niet in deze fasen

Triage en reviewpack (fase 3), koppeling met historische kengetallen en prijzen, vrijgave en echte goedkeuringsbron
(fase 5), automatische herhalingsdetectie, app-bundel.
