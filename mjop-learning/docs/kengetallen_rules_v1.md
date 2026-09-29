# Kengetallen — regels versie 1

Status: inhoudelijk goedgekeurd door de gebruiker (2026-09-24). Nog **niet**
geïmplementeerd: er bestaat nog geen schema, geen kengetal-output en geen
code. Dit document legt vast hoe een kengetal v1 wordt bepaald, bovenop de
bestaande lagen:

- source layer (`data/price_observations/price_observations_batch1.json`);
- normalisatie (`..._normalized.json`, incl. `material`);
- comparability v1 (`docs/comparability_rules_v1.md`, F1–F8);
- human review v1 (`docs/human_review_v1.md`,
  `data/review_decisions/human_decision_records.json`).

Die lagen worden door deze regels niet gewijzigd.

## Definitie

> Een **kengetal v1** is de mediaan van de source-cluster contributions van
> één volledig menselijk beoordeelde vergelijkbare groep, met minimaal drie
> onafhankelijke source clusters.
>
> Het kengetal is **historisch** (prijzen zoals ze in de brondocumenten
> stonden), **niet geïndexeerd**, **geen actuele marktprijs** en **geen
> normprijs**. Het is volledig herleidbaar naar observations, source clusters,
> posten en menselijke beslissingen.

Begrippen:

| Begrip | Betekenis |
|---|---|
| observation | één jarenplanrij met bedrag > 0 in het venster (source layer) |
| source cluster | set documenten die geen onafhankelijke bronnen van elkaar zijn (comparability D1–D4) |
| human decision | ACTIVE menselijk besluit over precies één paar observations uit verschillende clusters |
| vergelijkbare groep | zie regel 2 |
| post | één of meer observations van één document die volgens regel 3 dezelfde bronpost vertegenwoordigen |
| cluster contribution | één waarde per source cluster binnen een groep (regel 4) |

Prijs = `derived_unit_price_per_execution` als exacte waarde
(`annual_amount_used / quantity_value`), per eenheid, per uitvoering.

## Regels

1. **Onafhankelijke bewijs-eenheid.** `source_cluster` is de onafhankelijke
   bewijs-eenheid. Meerdere observations uit één cluster zijn geen meerdere
   onafhankelijke bronnen.

2. **Vergelijkbare groep.** Een set observations is alleen een vergelijkbare
   groep als:
   - alle observations dezelfde `element_code` (intern), dezelfde
     genormaliseerde `action` en dezelfde genormaliseerde `unit` hebben;
   - alle observations hetzelfde **bekende** materiaal hebben (regel 12);
   - alle observations `independent_input = true` hebben;
   - **elke** combinatie van twee observations uit **verschillende** source
     clusters een ACTIVE human decision `COMPARABLE` of
     `COMPARABLE_WITH_CAVEATS` heeft;
   - er binnen de set geen ACTIVE `NOT_COMPARABLE` bestaat;
   - er geen transitiviteit wordt aangenomen: A≈B en B≈C zegt niets over A≈C.

   Een connected component van menselijke beslissingen is op zichzelf dus
   geen vergelijkbare groep.

3. **Post consolidation** (vóór de cluster contribution). Twee observations
   uit **hetzelfde document** worden alleen als één post geconsolideerd
   wanneer:
   1. ze onder dezelfde elementregel staan
      (`source_representations[role = primary_financial_row].element_line`,
      gelijke pagina en regel);
   2. ze dezelfde genormaliseerde action hebben;
   3. ze dezelfde unit hebben;
   4. ze dezelfde quantity hebben;
   5. hun actieteksten uitsluitend verschillen in een woord uit de vaste,
      goedgekeurde **gevelzijde-lijst**:
      `achter`, `voor`, `achterzijde`, `voorzijde`, `achtergevel`,
      `voorgevel` (woordtokens, hoofdletterongevoelig; niet automatisch
      uitbreiden);
   6. er geen ander inhoudelijk verschil uit de bron blijkt.

   Verschillende Stj/Cy/planning verhindert consolidatie niet. Niet
   consolideren op alleen: dezelfde prijs, dezelfde quantity, dezelfde of
   vergelijkbare tekst, of dezelfde tariefgroep. Consolidatie verwijdert geen
   bronrij: Stj, Cy, provenance en alle overige velden blijven per
   observation bewaard. De post legt vast welke observations hij omvat en op
   welke elementregel dat berust. Een observation die met geen enkele andere
   wordt geconsolideerd is zelf één post.

   Postwaarde = mediaan van de prijzen van de observations in de post.

4. **Cluster contribution.** Mediaan van de postwaarden van de eligible,
   onafhankelijke observations van de groep binnen dat source cluster.
   Standaard statistische mediaan: bij een even aantal het gemiddelde van de
   twee middelste exacte waarden (de waarde hoeft niet letterlijk in een bron
   voor te komen). Geen quantity-, confidence- of andere weging.

5. **Eén bijdrage per cluster.** Een source cluster levert maximaal één
   cluster contribution, ongeacht het aantal observations of posten.

6. **Kengetal.** `kengetal_value = median(cluster contributions)`, zelfde
   mediaandefinitie als regel 4. Altijd bewaard naast de waarde: minimum,
   maximum, range (max − min), alle cluster contributions, posten en
   observations per cluster.

7. **Minimum data.** Minimaal 3 onafhankelijke source clusters met elk een
   cluster contribution, volledige cross-cluster human review (regel 2), geen
   `NOT_COMPARABLE`, alleen `independent_input = true`.

8. **Onvoldoende data.** Minder dan 3 source clusters → status
   `INSUFFICIENT_DATA` zonder centrale waarde; minimum, maximum, range en de
   cluster contributions blijven zichtbaar. De reden wordt vastgelegd.

9. **Precisie.** Alle berekeningen met exacte `Decimal`-waarden; afronding
   uitsluitend bij presentatie.

10. **Geen indexatie.** Prijzen worden niet naar een ander jaar omgerekend.

11. **Prijspeil altijd zichtbaar.** Bewaard: prijspeil per observation, per
    cluster, alle aanwezige jaren, een vlag `mixed_price_levels` en een vlag
    `missing_price_level`. Een kengetal met gemengde of ontbrekende
    prijspeilen wordt nooit gepresenteerd als waarde voor één specifiek
    prijsjaar. Een observation zonder prijspeil mag in een historisch
    kengetal meetellen, maar niet in een toekomstig prijsjaar-specifiek
    kengetal zonder verdere validatie.

12. **Materiaal.** Exact hetzelfde bekende materiaal is vereist, met de
    materiaalbron uit comparability F8: verified-element, anders goedgekeurd
    `material_from_text` (`MATERIAL_FROM_TEXT`, bron `element_text`). Geen
    materiaalhiërarchie, geen fuzzy matching.

13. **Geen weging, scoring of confidence.**

14. **Caveats herleidbaar.** Bewaard en zichtbaar in de onderbouwing:
    human `decision_caveats`, observation-caveats (ook
    `CODE_LABEL_MISMATCH` als de reviewer die niet koos), prijspeil-caveats,
    quantity/scope-caveats en de provenance per observation.

15. **Versies.** Een bestaande kengetalversie wordt nooit stilzwijgend
    overschreven of verwijderd.

16. **Wijzigingen in invoer.** Veranderen relevante observations, source
    clusters, human decisions, regels of input hashes, dan blijft de oude
    versie herleidbaar en wordt ze gemarkeerd voor opnieuw controleren/
    opbouwen.

## Herleidbaarheid (minimaal vast te leggen per kengetalversie)

- sleutel (element_code, action, unit), materiaal + materiaalbron, BTW-basis;
- status (`AVAILABLE` / `INSUFFICIENT_DATA` / te herbouwen) en reden;
- centrale waarde (exact en weergave), minimum, maximum, range;
- per cluster: contribution, posten, observations, prijspeil;
- per post: observations, gedeelde `element_line`, consolidatiereden;
- per observation: document/pagina/regel/brontekst, quantity, prijs per
  uitvoering, uitvoeringen, Stj/Cy, prijspeil, caveats, `independent_input`;
- gebruikte ACTIVE `decision_id`'s en de controle op complete cross-cluster
  review;
- uitgesloten observations met reden;
- prijspeiljaren, `mixed_price_levels`, `missing_price_level`,
  `indexation: none`;
- regelversie (kengetallen_rules_v1, comparability_rules_v1), input hashes
  (normalisatie, comparability, beslissingenopslag), aanmaakdatum.

## Wat v1 niet doet

- geen schaalcorrectie (quantity is bronkenmerk en caveat, geen rekenfactor);
- geen indexatie;
- geen fuzzy matching (tekst of materiaal);
- geen materiaalhiërarchie;
- geen confidence, score of weging;
- geen automatische transitiviteit of afgeleide beslissingen;
- geen marktprijsmodellering of normprijzen;
- geen prijsjaar-specifieke kengetallen;
- geen matching engine en geen koppeling aan nieuwe MJOP's.
