# Gevelopbouw v1: buitenkozijn, glas en gevel apart

Probleem (diagnose oktober 2026): de scanner nam vaak de **binnenste glasruit** als kozijn. Oorzaken in de oude code:
* Apple Vision `VNDetectRectanglesRequest` is een algemene rechthoekzoeker; de rand glas/profiel heeft meestal het sterkste contrast, de buitenrand profiel/metselwerk is rommeliger (voegen).
* Het oude filter verwijderde een binnenvak alleen als de buitenrand óók gevonden was; anders werd de ruit als kozijn gemeten. Bij een close-up (kozijn > 30 % van het beeld) bleven glas en kozijn allebei als kozijn staan.
* Elke ruit van een kozijn met meerdere ruiten werd een apart kozijn.
* Het datamodel kende geen rollen: glas, opening en gevelvlak bestonden niet.

## Rollen
| Rol | Betekenis | Telt als kozijn? |
|---|---|---|
| `FRAME_OUTER` | buitencontour van het kozijn (buitenmaat) | ja |
| `GLASS_PANE` | één glasvlak binnen een kozijn | **nooit** |
| `OPENING` | raam-/deuropening in de gevel; v1: gelijk aan de buitenmaat van het kozijn (aanname, dagkant niet gemeten) | – |
| `FACADE_GROSS` | bruto gevelvlak, door de gebruiker getekend (vier hoeken, zonder dak) | – |

## Herkenning (lokaal, geen eigen AI-model)
1. Kandidaat-vierhoeken uit Vision-rechthoeken **en** Vision-contouren (`VNDetectContoursRequest`, alleen contouren die als convexe vierhoek te benaderen zijn).
2. `ContourOrganizer` (PhotoWalkCore, getest, Python-referentie `facade.organize`):
   * een vierhoek die andere vierhoeken omsluit = **buitenkozijn met glasvlakken** (`DETECTED_ENCLOSING_PANES`; bij weinig glas t.o.v. de buitenmaat `UNVERIFIED`, bv. een deur met klein glas);
   * een vierhoek die zelf kozijnen omsluit (gevelvlak, paneel) is geen kozijn;
   * losse vierhoeken naast elkaar = **glasvlakken van één kozijn** (`PANE_GROUP`): één opening, de buitencontour is een **voorstel**;
   * een losse vierhoek = glas of kozijn? (`UNVERIFIED`).
3. `OuterFrameSearch` (randzoeker): stelt vanaf het glas een buitencontour voor door per zijde de eerste duidelijke evenwijdige rand naar buiten te zoeken (profiel -> muur). Altijd `PROPOSED_EXPANSION`; geen rand = geen voorstel (dan tekent de gebruiker zelf).

## Geen maat zonder bevestigde buitencontour
**Alle automatisch herkende buitencontouren** (`DETECTED_ENCLOSING_PANES`, `UNVERIFIED`, `PROPOSED_EXPANSION`) krijgen via `ContourGate` de blokkerende code `OUTER_CONTOUR_UNVERIFIED`: geen kozijnmaat in export, oppervlakvoorstel of gevelopbouw, ook niet als de LiDAR-schaal goed is. In de app is de maat wel zichtbaar als **indicatief** ("indicatief 1,2×1,5 m (niet bevestigd)"). Een maat vraagt dus altijd een betrouwbare schaal **én** een bevestigde of zelf aangegeven buitencontour. De gebruiker kan:
* **Dit is de buitenmaat** (bevestigen) -> `USER_CONFIRMED`;
* de hoeken naar de buitenrand **slepen** -> `MANUAL`;
* **Vergroot naar buitenkozijn (voorstel)** -> de oude vierhoek wordt een glasvlak, het voorstel wordt het kader (`PROPOSED_EXPANSION`, nog steeds geblokkeerd tot bevestiging);
* **Dit is een glasvlak** -> geen kozijn meer; glasvlak van het omsluitende kozijn (indien aanwezig);
* een glasvlak verwijderen; het **gevelvlak tekenen**.
Oudere opgeslagen scans worden `LEGACY` en gedragen zich precies als voorheen (geen ongemerkte wijziging). Originele hoeken, revisies, foto's en dieptekaarten blijven bewaard, zodat verbeterde herkenning later opnieuw kan draaien.

Op de foto: kozijn doorgetrokken (kleur = meetfeedback), **oranje gestreept** = buitencontour nog bevestigen, **blauw gestippeld** = glas, **paars gestippeld** = klaargezet voorstel, **blauw gestreept** = gevelvlak.

## Hoeveelheden per foto (`FacadeComposition`, Python-referentie `facade.compose`)
| Hoeveelheid | Berekening | Zonder schaal |
|---|---|---|
| Bruto gevel | getekend gevelvlak geprojecteerd op het gevelvlak (LiDAR-vlakfit buiten de kozijnen; anders het vlak van een kozijn met referentiemaat, met `COPLANARITY_ASSUMED`) | UNKNOWN |
| Openingen / buitenkozijn | som van de bestaande kozijnmetingen (buitenmaat b x h); alleen als ALLE kozijnen in het gevelvlak een maat hebben (anders deelsom ter informatie) | UNKNOWN |
| Glas | glasvlakken geprojecteerd op het vlak van het eigen kozijn; alleen als elk kozijn glasvlakken én schaal heeft | UNKNOWN |
| Netto gesloten gevel (bv. metselwerk) | bruto gevel min openingen; groter dan bruto -> `OPENINGS_EXCEED_FACADE`, geen waarde | UNKNOWN |
| Onderhouds-/schilderoppervlak kozijn | **niet afgeleid**: buitenkozijn min glas is niet het schilderoppervlak (profieldiepte, dagkanten, roeden, glaslatten, binnen/buiten) | altijd UNKNOWN |

Een enkele foto geeft hoogstens `ESTIMATED` (LiDAR) of `DERIVED` (referentiemaat). 3D BAG (`b3_opp_buitenmuur`) is alleen een **aanvullende controle** (`FACADE_GROSS_EXCEEDS_3DBAG_WALL_AREA`), nooit bewijs; in de scanner zelf is de 3D BAG-waarde nog niet beschikbaar (veld blijft `null`).

## Export en compatibiliteit
`photo_walk_capture_v1` **1.2.0**: optioneel `observations[].facade_role` en top-level `facade_composition`. Records 1.0.0/1.1.0 blijven geldig (getest). `mjop_scan_proposal_v2` is **ongewijzigd**: er gaan geen nieuwe automatische hoeveelheden (glas, gevel) naar het MJOP. Een kozijn met onbevestigde buitencontour heeft geen maat, dus het oppervlakvoorstel blijft `null` (bestaande regel "niet alle kozijnen gemeten").

## Wat getest is en wat niet
* Getest (CI): rekenregels in Python en Swift met gedeelde synthetische cases (zelfde beeld, zelfde uitkomsten), exportschema oud/nieuw, opslaan/herstellen, de app-selftest op een synthetisch kozijn met profiel en tussenstijl, UI-test van de bevestigingsstap.
* **Niet** getest: herkenning op echte gevels, reflecties, donkere kozijnen, schuine foto's, de randzoeker op echte foto's. Daarvoor: `docs/facade_ground_truth_protocol.md`. Alle drempels zijn `PROVISIONAL_UNVALIDATED`.
