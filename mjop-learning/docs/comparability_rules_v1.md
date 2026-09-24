# Vergelijkbaarheidsregels — versie 1

Status: inhoudelijk goedgekeurd door de gebruiker (2026-09-23), incl. de
beslissingen in sectie E en de aanvullingen in sectie F (2026-09-24). Implementatie: `scripts/build_comparability.py`.

Doel van deze laag: historische price observations → eligibility → source
clusters → vergelijkbare observation-paren. **Geen** kengetallen, gemiddelden,
medianen, percentielen, scores, prijsadvies, matching-aanbevelingen of
indexatie.

Drie gescheiden niveaus:

| Niveau | Vraag | Uitkomst |
|---|---|---|
| A. Observation | Mag deze observation op zichzelf meedoen, en met welke vaste voorbehouden? | ELIGIBLE / ELIGIBLE_WITH_CAVEATS / NOT_ELIGIBLE / UNKNOWN |
| B. Paar | Beschrijven twee observations uit verschillende source clusters hetzelfde werk? | COMPARABLE / COMPARABLE_WITH_CAVEATS / NOT_COMPARABLE / UNKNOWN |
| C. Bronnen | Welke observations zijn geen onafhankelijke bronnen van elkaar? | source cluster per observation + tariefgroepen |

Elk paar wordt afzonderlijk bewaard (welke twee observations, welke regels,
welke redenen). De klasse van een observation wordt daarvan afgeleid (sectie
D), maar vervangt de paarresultaten nooit.

## A. Observation (O-regels)

Zwaarste uitkomst wint: NOT_ELIGIBLE > UNKNOWN > ELIGIBLE_WITH_CAVEATS > ELIGIBLE.
Alle redencodes blijven bewaard.

| Regel | Implementatie (deterministisch) | Uitkomst |
|---|---|---|
| O1 Eenheid | `unit_normalized` ontbreekt → UNKNOWN; `lump_sum` → NOT_ELIGIBLE; `piece` met niet-gehele hoeveelheid → voorbehoud | `UNIT_UNKNOWN`, `LUMP_SUM`, `FRACTIONAL_PIECE_COUNT` |
| O2 Elementcontext | geen elementregel in de bron (`element_code_original` leeg / `element_context_missing`) | UNKNOWN `ELEMENT_CONTEXT_MISSING` |
| O3 Object bepaalbaar | elementomschrijving of actietekst met ongebalanceerde haakjes of eindigend op een scheidingsteken (`(`, `-`, `/`, `&`, `,`) → onvolledig | UNKNOWN `INCOMPLETE_DESCRIPTION` |
| O3 Algemeen object | alleen op paarniveau vast te stellen zonder woordenlijst: zie P8 | — |
| O4 Omvang bepaalbaar | geen goedgekeurde deterministische regel; niet automatisch toegepast | — |
| O5 Bundeling | goedgekeurd signaalwoord van type BUNDLED_COST in de actietekst | NOT_ELIGIBLE `BUNDLED_COST` |
| O6 Kwalificaties | goedgekeurd signaalwoord van type UPGRADE / PARTIAL_SCOPE / COMBINED_EXECUTION in de actietekst | voorbehoud met die code |
| O7 Aantal uitvoeringen | MULTIPLE_EXECUTIONS: prijs per uitvoering afleiden als aan sectie E1 is voldaan; anders voorbehoud. `total_scope` UNKNOWN → UNKNOWN | `ROW_TOTAL_RATIO` (alleen als afleiden niet kan), `TOTAL_SCOPE_UNKNOWN` |
| O8 Prijspeil | geen expliciet prijspeil | voorbehoud `PRICE_LEVEL_ABSENT` |
| O9 Materiaal | geen materiaal → voorbehoud; materiaal met `/` → voorbehoud | `MATERIAL_UNKNOWN`, `MIXED_MATERIAL` |
| O10 Classificatie | geen interne elementcode → NOT_ELIGIBLE (o.a. DOC-004, zie E4); label "Binnenschilderwerk…" bij `exterior_painting` of "Buitenschilderwerk…" bij `interior_painting` → voorbehoud | `NO_INTERNAL_CODE`, `CODE_LABEL_MISMATCH` |
| O11 Openstaande review | reviewreden die vergelijking raakt: actie niet genormaliseerd/conflict, eenheid onbekend, element ontbreekt, elementcode-mismatch | UNKNOWN `OPEN_REVIEW:<reden>` |
| D5 (zie C) | onopgeloste afhankelijkheid (`dependency_status` UNKNOWN) | UNKNOWN `UNRESOLVED_DEPENDENCY` |

## B. Paar (P-regels)

Kandidaatparen: observations met gelijke (interne elementcode, genormaliseerde
actie, genormaliseerde eenheid) uit **verschillende** source clusters. Paren
met een NOT_ELIGIBLE observation worden niet gevormd. Paren met een UNKNOWN
observation worden wél gevormd en krijgen de reden `OBSERVATION_UNKNOWN`; ze
worden daardoor nooit COMPARABLE of COMPARABLE_WITH_CAVEATS. Paren binnen één
cluster worden niet beoordeeld maar als `SAME_SOURCE`-koppeling bewaard.

Voorrang (F1): harde schending (NOT_COMPARABLE) > UNKNOWN > voorbehoud
(COMPARABLE_WITH_CAVEATS) > COMPARABLE. Een aantoonbare harde schending maakt
een paar dus NOT_COMPARABLE, ook als een van beide observations UNKNOWN is;
zonder harde schending is zo'n paar UNKNOWN.

Tekstvergelijking (P2, P3, P4/P9) gebeurt op woordtokens (kleine letters,
alleen letters/cijfers): **gelijk**, **prefix** (de ene tokenreeks is het begin
van de andere) of **verschillend**. Er is geen fuzzy matching en geen
semantische interpretatie; verschillende teksten zonder prefixrelatie vragen
een menselijk oordeel.

| Regel | Implementatie | Uitkomst |
|---|---|---|
| P1 Zelfde eenheid | via de kandidaatsleutel; afwijkend → hard | NOT_COMPARABLE `UNIT_DIFFERS` |
| P2 Zelfde object | elementomschrijving gelijk → OK; prefix → P8; verschillend → menselijk oordeel nodig | UNKNOWN `OBJECT_EQUIVALENCE_REQUIRES_REVIEW` |
| P3 Zelfde werk | actietekst gelijk → OK; prefix → voorbehoud; verschillend → menselijk oordeel nodig | `ACTION_TEXT_VARIANT` / UNKNOWN `ACTION_EQUIVALENCE_REQUIRES_REVIEW` |
| P4 Zelfde materiaal | beide bekend: gelijk → OK; prefix → P9; verschillend → hard | NOT_COMPARABLE `MATERIAL_DIFFERS` |
| P5 Zelfde BTW-basis | beide bekend en verschillend → hard (omrekenen kan niet: hoog/laag tarief per post onbekend); één of beide kanten onbekend → UNKNOWN (F5) | NOT_COMPARABLE `VAT_BASIS_DIFFERS` / UNKNOWN `VAT_BASIS_UNKNOWN` |
| P6 Prijspeiljaar | verschillend jaar → voorbehoud (geen indexatie, zie E3) | `PRICE_LEVEL_DIFFERENCE` |
| P7 Hoeveelheid | verhouding > 10 → voorbehoud | `QUANTITY_SCALE_DIFFERENCE` |
| P8 Algemeen vs. specifiek object | elementomschrijvingen in prefixrelatie | `GENERIC_VS_SPECIFIC_OBJECT` |
| P9 Systeemvariant | materiaal in prefixrelatie (bijv. `APP` vs `APP+ballast`) | `MATERIAL_VARIANT` |
| P10 Voorbehouden uit A | voorbehouden van beide observations gaan mee | per kant bewaard |
| P11 Overgenomen inhoud | **alleen** als er concrete broninformatie is dat hoeveelheid/prijsinhoud uit een eerdere versie is overgenomen (in `document_relations.json` als `content_reuse_evidence`). Zelfde project of gelijke hoeveelheid is op zichzelf geen bewijs. In batch 1 is zulk bewijs er niet → nooit toegepast. | `CONTENT_REUSE` |

## C. Bronnen (D-regels)

Documentrelaties zijn leidend wanneer ze expliciet bekend zijn; rij-matching
mag een bekende documentrelatie niet overrulen.

| Regel | Implementatie |
|---|---|
| D1 duplicate_source | secundair document levert geen observations (DOC-003) |
| D2 version_of_same_mjop | alle observations van beide documenten in één cluster (DOC-005 + DOC-006) |
| D3 subplans_same_complex | beide documenten in één cluster (DOC-008 + DOC-009) |
| D4 same_building_other_inspection | aparte clusters (DOC-002, DOC-004); geen automatische P11 |
| D5 identieke rijen / onopgeloste afhankelijkheid | `dependency_status` UNKNOWN → observation UNKNOWN; `dependency_status` POSSIBLY_DEPENDENT → elk paar met die observation UNKNOWN `POSSIBLY_DEPENDENT_OBSERVATION` (F2; eligibility zelf ongewijzigd) |
| D6 zelfde tarief binnen één document | observations die onafhankelijke input zijn (F6: eligible, afgeleide prijs, niet POSSIBLY_DEPENDENT) met gelijke kandidaatsleutel en **exact** gelijke prijs per uitvoering (jaarbedrag / hoeveelheid als exacte breuk, niet afgerond; F3) in hetzelfde document vormen een tariefgroep = één bronbijdrage (vastgelegd, niet samengevoegd) |
| D7 zelfde inspecteur/opsteller | uitsluitend context; nooit reden voor clustering of afhankelijkheid |

## D. Klasse van een observation

- NOT_ELIGIBLE → klasse NOT_COMPARABLE (reden `NOT_ELIGIBLE`), geen paren.
- UNKNOWN → klasse UNKNOWN; paren worden als UNKNOWN vastgelegd.
- Anders: beste paarklasse tegen een observation uit een ander cluster
  (COMPARABLE > COMPARABLE_WITH_CAVEATS > UNKNOWN > NOT_COMPARABLE); geen enkel
  paar → NOT_COMPARABLE `NO_INDEPENDENT_COUNTERPART`.

## E. Beslissingen (2026-09-23)

1. **Prijs per uitvoering** mag deterministisch worden afgeleid als: het aantal
   uitvoeringen uit de bron blijkt (jaarbedragen), alle jaarbedragen
   beschikbaar en gelijk zijn, de hoeveelheid tussen uitvoeringen niet
   verandert (één bronrij = één hoeveelheid) en het rijtotaal sluit.
   `derived_unit_price_per_execution` = jaarbedrag / hoeveelheid. Bronprijs,
   hoeveelheid, aantal uitvoeringen en jaarbedragen blijven ongewijzigd
   bewaard. Anders blijft `ROW_TOTAL_RATIO` of UNKNOWN.
2. **Signaalwoorden** uitsluitend uit `vocabularies/comparability_signal_words.json`;
   niet automatisch uitbreiden.
3. **Geen prijsindexatie**; prijsjaarverschil blijft `PRICE_LEVEL_DIFFERENCE`.
4. **DOC-004**: codesysteem niet gelijkgesteld aan het interne systeem; geen
   automatische codekoppeling; blijft historische bron.
5. **D7** alleen context.

## F. Aanvullende beslissingen (2026-09-24, na audit)

1. **Voorrang bij een UNKNOWN observation**: harde schending > UNKNOWN >
   voorbehoud > COMPARABLE. Een aantoonbare harde incompatibiliteit maakt een
   paar NOT_COMPARABLE, ook als een observation daarnaast UNKNOWN is.
2. **POSSIBLY_DEPENDENT**: een mogelijke, onopgeloste afhankelijkheid is geen
   onafhankelijke vergelijkingsbasis. Elk paar met zo'n observation wordt
   UNKNOWN (`POSSIBLY_DEPENDENT_OBSERVATION`), behalve bij een harde schending
   (F1). Geen weging.
3. **Exacte prijsvergelijking**: gelijkheid van `derived_unit_price_per_execution`
   (D6) wordt bepaald op de exacte waarde jaarbedrag / hoeveelheid, niet op de
   naar 2 decimalen afgeronde `value`. Die afronding is alleen weergave.
4. **Afgeleide prijs bij niet-eligible observations**: blijft berekend en
   opgeslagen voor auditeerbaarheid, maar komt niet in tariefgroepen. De
   samenvatting telt `derived_price_per_execution` (technisch afgeleid, alle
   observations) en `derived_price_per_execution_eligible` (alleen ELIGIBLE /
   ELIGIBLE_WITH_CAVEATS).
5. **Onbekende BTW**: één of beide kanten onbekend → paar UNKNOWN
   (`VAT_BASIS_UNKNOWN`); beide bekend en verschillend blijft een harde
   schending (`VAT_BASIS_DIFFERS`).
6. **POSSIBLY_DEPENDENT als aggregatie-input**: de observation blijft bestaan,
   met ongewijzigde eligibility, `dependency_status` en provenance, en mag een
   afgeleide prijs bevatten. Ze is echter geen onafhankelijke input:
   `independent_input = false` met reden `POSSIBLY_DEPENDENT`, en ze komt niet
   in tariefgroepen. Per observation onderscheidt de output
   `derived_unit_price_per_execution` (technisch afgeleide prijs) van
   `independent_input` (mag als onafhankelijke kengetalinput dienen). De
   samenvatting telt `derived_price_per_execution` (technisch),
   `derived_price_per_execution_eligible` en
   `derived_price_per_execution_independent_input`. De paarregel blijft F2.
