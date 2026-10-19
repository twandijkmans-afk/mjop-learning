# Quantity Review & Triage v1

Deterministische triage bovenop het Bruto Quantity Model v2 (PR #53). Voorlopig: geen besluit, geen CONFIRMED-uitvoer,
geen FI-id, geen instance-activatie, geen BAG-koppeling, geen definitief gebouwtotaal, geen netwerk, geen Vision-aanroep.

## Onderdelen
| Bestand | Rol |
| --- | --- |
| `scripts/bruto_triage.py` | puur: invoer → review-pack (dict) |
| `scripts/bruto_triage_calibration.py` | valideert de structuur van een latere kalibratie; voert er geen uit |
| `scripts/bruto_triage_contracts.py` | schemavalidatie (hergebruikt de v2-schema's) |
| `scripts/bruto_review_pack.py` | offline HTML en CLI (schrijft nooit in de repository) |
| `schemas/bruto_triage_input_v2`, `bruto_triage_calibration_v2`, `bruto_review_pack_v2` | contracten |
| `vocabularies/bruto_triage_rules_v2.json` | regelcatalogus (id, as, klasse, titel) |
| `config/bruto_triage_calibration_v2.json` | standaard `UNCALIBRATED`, alle drempels leeg |

## Twee assen, vier klassen
As A (identiteit/telling) en as B (maatvoering) worden onafhankelijk beoordeeld; de totaalklasse is de slechtste.
`CLEAN_PROVISIONAL` < `REVIEW_REQUIRED` < `INSUFFICIENT_EVIDENCE` < `CONFLICT`.

* **CONFLICT**: de gegevens spreken zichzelf tegen (observatie bij twee objecten, zelfde foto meerdere keren voor één stuk, bewijs dat samenvoeging tegenspreekt, verankerd bewijs tussen verschillende objecten, onverenigbare maatbronnen, ongeldige maat). Geblokkeerd; buiten de basisstand.
* **INSUFFICIENT_EVIDENCE**: bewijs ontbreekt (geen volledig zicht, geen identiteitsvoorstel, samenvoeging zonder verankerd bewijs, blokkerende bewijsgrond, maat onbekend, schatting niet herleidbaar). Geblokkeerd; ontbrekende maat en ontbrekende identiteit zijn aparte regels.
* **REVIEW_REQUIRED**: individuele beoordeling (alleen gelijkenis tussen objecten, slechte beeldkwaliteit, bron niet verifieerbaar, aantal niet gedekt, schatting, afwijking binnen typegroep, ongekalibreerde drempel).
* **CLEAN_PROVISIONAL**: geen bezwaar op beide assen onder gekalibreerde drempels. Voorlopig, niet bevestigd.

AI-zekerheid is informatie (`used_in_decision: false`) en nooit regelinvoer. Een goedkeuringsbewering in de invoer (`approval_refs`) wordt als
`APPROVAL_CLAIM_UNVERIFIED` getoond en verandert de klasse niet.

## Kalibratie
Standaard `UNCALIBRATED`: geen object kan totaal `CLEAN_PROVISIONAL` zijn (regel A-R5), schattingen vragen altijd beoordeling (B-R1) en
typegroepen worden exact vergeleken. Er is **geen kalibratie uitgevoerd**. Een latere `CALIBRATED`-configuratie telt alleen als ze
structureel klopt: menselijk gelabelde, representatieve set; gescheiden ontwikkel-, kalibratie- en testdata met hashes; exact (Clopper-Pearson)
betrouwbaarheidsinterval, herberekend uit het aantal onterecht schone objecten; foutbudget door de gebruiker gesteld; auditsteekproef met
voldoende omvang (regel van drie). Elke tekortkoming valt terug op `UNCALIBRATED` met de reden. De echtheid blijft `NOT_VERIFIED`.

## Werkstatus en groepen
`CLEAN` → `AUTO_PROVISIONAL` (of `READY_FOR_GROUP_REVIEW` bij een voorbereide groep van ≥ 2 objecten onder gekalibreerde drempels),
`REVIEW_REQUIRED` → `INDIVIDUAL_REVIEW`, `INSUFFICIENT_EVIDENCE`/`CONFLICT` → `BLOCKED`. Een groep is alleen voorbereid
(`PREPARED_NOT_RELEASED`, `release_executed: false`) met uitzonderingenlijst en deterministische auditsteekproef. Elk object staat
expliciet in het pack; niets wordt stilzwijgend vrijgegeven.

## Hoeveelheden
De basisstand komt uit `bruto_quantity_core.build_state` over de niet-conflicterende objecten; objecten met onvoldoende identiteit tellen niet
als voorlopig-uniek. Lagen blijven gescheiden, onbekend oppervlak blijft `null`, er is geen gecombineerd totaal. Reviewscenario's
(dubbel-paar, potentiële schatting bij ontbrekende maat, conflict-op-het-spel) zijn onafhankelijk, `additive: false`, `is_final_quantity: false`
en hebben een `overlap_group`; ze mogen niet worden opgeteld.

## Gebruik
`python scripts/bruto_review_pack.py invoer.json --out-dir /pad/buiten/repo` schrijft `BRP-<hash>.json` en `BRP-<hash>.html`; zonder `--out-dir`
gaat de JSON naar stdout. De HTML heeft geen script, formulier, externe bron of netwerk; een klik registreert niets.
