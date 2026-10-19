# Maintenance Actions & Door Treatment v1

Aanvullende, deterministische laag op het Bruto Quantity Model v2 (PR #53) en de triage (PR #54). Zet een `bruto_review_pack_v2` (read-only
bron, `pack_id` wordt herberekend) om in **voorlopige onderhoudshoeveelheidsvoorstellen**. Geen prijs, kengetalkoppeling, kosten, MJOP-regel,
definitieve hoeveelheid, besluit, FI-id of netwerk; schrijft zelf niets.

| Bestand | Rol |
| --- | --- |
| `scripts/bruto_maintenance_actions.py` | `propose(pack, requests)` en CLI (schrijft nooit in de repository) |
| `schemas/bruto_maintenance_request_v2`, `bruto_maintenance_action_v2`, `bruto_maintenance_pack_v2` | gesloten, versieerbare contracten |
| `vocabularies/bruto_maintenance_rules_v2.json` | actietype → bestaande actie-ID, overlappende werkparen, regelcatalogus M-* |

## Hergebruik van vocabulaires
Acties, meetgrondslagen en deurbehandelingen komen uit `vocabularies/bruto_quantity_actions_v2.json`; de nieuwe vocabulary verwijst ernaar
(`EXTERIOR_PAINTING`→`PAINT_EXTERIOR`, `INTERIOR_PAINTING`→`PAINT_INTERIOR`, overige een-op-een) en definieert geen concurrerende varianten.

## Hoeveelheidsregels
* Bruto m² per object = `gross_area_m2_exact` uit het pack (breedte × hoogte × aantal); glas niet afgetrokken, draaiende delen niet apart, nooit de typemaat. Een kozijn met meerdere ramen of foto's is één object.
* `EXTERIOR_PAINTING`: standaard `GROSS_FRAME_AREA_OUTER` (m²). `INTERIOR_PAINTING`: altijd `UNKNOWN`, `null`; nooit af te leiden uit buiten (een buiten- of stuksgrondslag wordt geweigerd met `INTERIOR_FROM_EXTERIOR_FORBIDDEN`). `FRAME_MAINTENANCE`/`FRAME_REPLACEMENT`: grondslag UNKNOWN tenzij het verzoek expliciet `GROSS_FRAME_AREA_OUTER` met bronverwijzing opgeeft. `DOOR_*`: stuks (`DOOR_PIECES`, kandidaat).
* Deurbehandeling hoort bij de actie: `PART_OF_GROSS_FRAME_AREA` (deur in m², geen extra post), `AS_PIECES` (stuks), `NOT_RELEVANT`, `UNDECIDED` (geen onderhoudshoeveelheid, `M-R3`). Een kozijn met deur is één object. Deur in het m² én in stuks gevraagd voor dezelfde actie: `M-R4`.
* Statussen: `KNOWN_SUPPORTED`, `PROVISIONAL_CALCULATED`, `ESTIMATED`, `UNKNOWN`, `BLOCKED_BY_CONFLICT`; daarnaast altijd `release_state: NOT_RELEASED`. `null` = onbekend, nooit nul; één onbekend oppervlak maakt de hele som `null` (geen deelsom). Stuks hangen niet van de maat af.

## Bescherming tegen dubbel onderhoud
Zelfde type + exact dezelfde scope: `M-C1` CONFLICT (hoeveelheid null). Zelfde type, gedeelde objecten: `M-R1`. Werk dat elkaar kan insluiten (paren in de vocabulary, bijvoorbeeld kozijnvervanging × schilderwerk of deurvervanging × deuronderhoud): `M-R2`. Verschillend werk op hetzelfde object (bijvoorbeeld schilderen in m² en deur vervangen in stuks): geldige dubbele registratie, `M-N2` (info). Mogelijk dubbele objecten uit de triage: `M-R5`. Bronconflict `M-C2`. Voorstellen delen een `overlap_group`, zijn `additive: false` en er is geen totaal over acties.

## Triage-overerving
Het review_status van een voorstel is de slechtste klasse van de relevante triage-as (identiteit voor stuks, totaal voor m²) en de bevindingen. Bij ongekalibreerde triage is geen voorstel `CLEAN_PROVISIONAL` of `KNOWN_SUPPORTED` (`M-R6`).
