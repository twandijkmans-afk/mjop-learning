# Maldenhof — dak: 3D BAG vs historisch MJOP (v1)

Classificatie: **SCOPE_OR_DEFINITION_MISMATCH_REVIEW**. Het verschil is GEEN bewijs dat het MJOP of 3D BAG fout is. Er wordt niets gecorrigeerd: historische hoeveelheden en 3D BAG-waarden blijven ongewijzigd en naast elkaar staan.

| Onderwerp | MJOP (m²) | 3D BAG, 15 panden EVEN_ONLY (m²) | Verschil (m²) | % t.o.v. 3D BAG |
|---|---|---|---|---|
| plat dak (4711 Dakbedekking APP vs b3_opp_dak_plat) | 425.80 | 190.65 | 235.15 | 123.3 |
| hellend dak (4712 Dakpan beton vs b3_opp_dak_schuin) | 1485.60 | 1415.57 | 70.03 | 4.9 |

## Onderzocht

- **element_description**: 4711 'Dakbedekking APP', locatie 'Platte dak', eenheid m2 (DOC-005 p7 P07-L013). Eén post voor alle platte daken; het MJOP specificeert niet welke dakdelen (hoofddak, dakkapellen, bergingen, luifels).
- **location**: 'Platte dak' is een verzamellocatie, geen pand- of dakvlakverwijzing.
- **quantity_unit**: Beide m2; geen eenheidsverschil.
- **which_roof_parts**: Onbekend uit de bron. Een hellend dak met platte delen (dakkapellen, kopse overgangen) en losse bergingen kunnen in één 4711-post zitten.
- **threedbag_scope**: 3D BAG telt per BAG-pand; panden zonder adres (bergingen) vallen buiten de adresgedreven scope van BPRJ-00001. De grens plat/schuin in 3D BAG volgt de hellingshoek van gereconstrueerde dakvlakken (definitie te verifiëren), niet de dakbedekking.
- **multiple_roof_types_in_one_post**: Mogelijk; het hellende dak (4712) ligt dicht bij 3D BAG (~5%), het platte dak niet.
- **exploratory_outbuildings** (EXPLORATORY_NOT_EVIDENCE): 18 panden, bouwjaar 1981, plat 94.80 m². 18 kleine panden van ~5 m² (vermoedelijk bergingen) met plat dak. Welke bij de VvE horen (even kant) is onbekend; ook opgeteld (190.65 + 94.80 = 285.45 m²) verklaren ze 425.80 m² niet volledig.

## Bron-elementen

- DOC-005-EL-025: `4711 Dakbedekking APP Platte dak 425,80m2 3` (p7, P07-L013)
- DOC-005-EL-027: `4712 Dakpan beton Hellend dak 1485,60m2 3` (p7, P07-L015)
- DOC-006-EL-025: `4711 Dakbedekking APP Platte dak 425,80m2 1` (p7, P07-L007)
- DOC-006-EL-027: `4712 Dakpan beton Hellend dak 1485,60m2 1` (p7, P07-L009)

## Open vragen

- Welke dakdelen omvat post 4711 (425,80 m2): alleen de platte delen van de woningen, ook bergingen/aanbouwen, luifels?
- Horen de bergingen zonder adres (aparte BAG-panden) tot de VvE, en zo ja welke (even kant)?
- Hoe definieert 3D BAG de grens tussen b3_opp_dak_plat en b3_opp_dak_schuin voor dakkapellen en flauwe dakvlakken?

Er is niets gecorrigeerd.
