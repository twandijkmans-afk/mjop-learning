# Evidence Reconciliation v1: VR-045 en MAP-009

Onafhankelijk onderzoek van het verschil tussen de MAP-009-beoordeling uit PR #42 en de bestaande P1-kwaliteitsreview van VR-045. **VR-045, de kwaliteitsreview, het pilotregister en de OIC zijn niet gewijzigd; er is geen menselijk besluit aangemaakt.** De originele foto's (zip in de projectbestanden, niet in de repository) zijn tegen het SHA256-register gecontroleerd en op volledige resolutie gelezen. Dit is handmatige lezing (`MANUAL_VISUAL_READING`).

## 1. Uitkomst

**COMPATIBLE_DIFFERENT_SCOPE**

- De twee beoordelingen gaan over verschillende MAP-009-uitsneden en verschillende bewijsclaims. REF-MAP009-006 bevat alleen het tweedelige kozijn en sluit het smalle raam met folie, het meest onderscheidende kenmerk, buiten; VR-045 vergelijkt bovendien een groep (kozijn plus smal raam) met die enkele uitsnede.
- De P1-review heeft daarom terecht vastgesteld dat deze uitsnede en de feature-match (4 van 7) geen identiteit bewijzen. Mijn PR #42-beoordeling steunt op een ruimere uitsnede met het smalle raam en op een kenmerk-voor-kenmerk lezing. Beide uitspraken kunnen naast elkaar bestaan.
- Twee kanttekeningen: (1) de P1-bevinding 'geen uniek kenmerk' en 'smal raam ontbreekt' is juist voor de uitsnede maar niet voor de foto: het smalle raam staat in MAP-009, net buiten de uitsnede, en F1-F3 waren ook binnen de uitsnede zichtbaar. (2) Mijn PR #42-tekst noemde de plakstrook ook in MAP-009; dat is niet verifieerbaar en is hierbij teruggebracht.

Geen genuine conflict: Dezelfde bewijsclaim (zelfde uitsnede, zelfde eindpunten) heeft geen tegenstrijdige beoordelingen gekregen; er is geen menselijk besluit over VR-045 dat door een AI-beoordeling zou worden vervangen.

## 2. Bronnen

| Bron | Bestand | Pad |
|---|---|---|
| p1_feature_match | `reports/frames/photo_review_map003_map004_v1/p1_quality_review/p1_feature_match_evidence_v1.json` | relations[relation_id=VR-045] |
| p1_review_sheet | `reports/frames/photo_review_map003_map004_v1/p1_quality_review/QREL-sheet-4.jpg` | rij VR-045 |
| pr42_verification | `reports/frames/physical_object_identity_evidence_v1/physical_object_identity_evidence_verification_v1.json` | additional_matches[MAP-009] |
| quality_review_vr027 | `reports/frames/photo_review_map003_map004_v1/maldenhof_p1_visual_quality_review_v1.json` | records[review_id=RV-REL-VR-027] |
| quality_review_vr045 | `reports/frames/photo_review_map003_map004_v1/maldenhof_p1_visual_quality_review_v1.json` | records[review_id=RV-REL-VR-045] |
| reference_ref009_006 | `reports/frames/photo_review_map003_map004_v1/maldenhof_visual_photo_review_map003_map004_v1.json` | references[ref_id=REF-MAP009-006] |
| relation_vr027 | `reports/frames/photo_review_map003_map004_v1/maldenhof_visual_photo_review_map003_map004_v1.json` | relations[rel_id=VR-027] |
| relation_vr045 | `reports/frames/photo_review_map003_map004_v1/maldenhof_visual_photo_review_map003_map004_v1.json` | relations[rel_id=VR-045] |

| Foto | Bestand | Afmeting | SHA256 | Controle |
|---|---|---|---|---|
| MAP-003 | IMG_8518.JPEG | 2048x1536 | `9f121e711b0cea13…` | klopt |
| MAP-004 | IMG_8520.JPEG | 2048x1536 | `197556869a8e91a9…` | klopt |
| MAP-009 | P1000236.JPG | 3264x2448 | `15591a9648ddfec7…` | klopt |

## 3. Wat VR-045 vergelijkt

- Linkereindpunt (groep): OBS-MAP003-011, OBS-MAP003-012, OBS-MAP004-006, OBS-MAP004-007; rechtereindpunt: REF-MAP009-006 = MAP-009 [362,362,747,682].
- Kwaliteitsrecord: INSUFFICIENT_EVIDENCE, basis OBLIQUE_VIEW, PARTIAL_OVERLAP, feature-match 4 van 7; voorstel Claude UNDECIDABLE; bevinding: "onvoldoende bewijs: MAP-009 is sterk verkort: alleen het tweedelige kozijn is herkenbaar, het smalle raam ontbreekt; geen uniek kenmerk."
- Menselijk besluit over VR-045: **None** (geen).
- Dezelfde vraag als VR-027: **nee**. Zelfde soort vraag (PHYSICAL_OBJECT) en dezelfde twee observaties in de groep, maar een andere claim: groep tegen een enkele MAP-009-referentie. VR-027 zelf vergelijkt alleen OBS-MAP003-011 met OBS-MAP004-006.

## 4. Vergelijkingstabel

| Aspect | P1-review VR-045 | PR #42-verificatie |
|---|---|---|
| Welke relatie | VR-045: PHYSICAL_OBJECT, sterkte LOW, groep-tegen-referentie | VR-027: PHYSICAL_OBJECT, sterkte MEDIUM, paar OBS-MAP003-011 / OBS-MAP004-006; MAP-009 alleen aanvullend |
| Eindpunten | MAP-003:OBS-MAP003-011/012 en MAP-004:OBS-MAP004-006/007 (tweedelig kozijn plus smal raam) tegen MAP-009:REF-MAP009-006 | OBS-MAP003-011 en OBS-MAP004-006, beide met het smalle raam rechts, tegen een brede MAP-009-uitsnede |
| MAP-009-uitsnede | [362,362,747,682], 385x320 px, alleen het tweedelige kozijn | [300,300,1050,800], 750x500 px, tweedelig kozijn plus smal raam met folie |
| Zichtbaar in de MAP-009-uitsnede | F1, F2, F3; niet F4, F5, F6 | F1, F2, F3, F4, F6; F5 niet verifieerbaar |
| Vraag | Is de referentie hetzelfde als de groep (met smal raam)? Smal raam ontbreekt in de referentie | Geeft MAP-009 aanvullende steun voor het paar uit VR-027? |
| Bewijsstandaard | Uniek kenmerk binnen de uitsnede plus feature-match; indeling alleen telt niet | Kenmerk-voor-kenmerk lezing van de originele pixels, positie en verwisselingscontrole |
| Feature-match | 4 inliers op 7 matches; methode: CLAHE, +12% marge, max 360 px, groepsuitsnede (alleen ondersteunend) | 8 inliers op 22 matches; methode: zonder CLAHE, hoogte 400 px, ruime uitsneden (alleen ondersteunend). De getallen zijn niet vergelijkbaar |
| Uitkomst | INSUFFICIENT_EVIDENCE; Claude-voorstel UNDECIDABLE; NEEDS_BETTER_PHOTO | STERK_VISUEEL_ONAFHANKELIJK_TOESTEL_EN_HOEK (aanvullend; mijn handmatige lezing) |
| Menselijk besluit | geen | geen |

Beeld van het verschil in uitsnede: `physical_instance_approval_v1/RC-crop_scope.jpg` (boven MAP-003/004, onder MAP-009 met de VR-045-uitsnede links en de ruimere uitsnede rechts).

## 5. Herbeoordeling kenmerk voor kenmerk

Klassen: DIRECTLY_VISIBLE = rechtstreeks zichtbaar in de originele pixels; DIRECTLY_VISIBLE_LOW_RESOLUTION = zichtbaar maar klein of schuin; INTERPRETATION = mijn lezing; NOT_VERIFIABLE = niet vast te stellen.

| Nr | Kenmerk | MAP-003 | MAP-004 | MAP-009 | In VR-045-uitsnede | Klasse | Opmerking |
|---|---|---|---|---|---|---|---|
| F1 | Twee witte merktekens in het linkervak (rechtsboven en rechtsonder) | ja | ja | ja | ja | DIRECTLY_VISIBLE | Zelfde twee tekens op dezelfde plaats in alle drie de foto's, ook binnen de VR-045-uitsnede. Niet uniek op zichzelf: de linkerbuur in MAP-003 heeft één los merkteken op een andere plaats. |
| F2 | Wit geplooid gordijn in het grote vak | ja | ja | ja | ja | DIRECTLY_VISIBLE | Zichtbaar in alle drie, ook in de VR-045-uitsnede. Gordijnen zijn op zichzelf niet onderscheidend; de buurvensters tonen een rolgordijnkast. |
| F3 | Vensterbankvoorwerpen: lichte doos plus klein puntig voorwerp | ja | ja | ja | ja | DIRECTLY_VISIBLE_LOW_RESOLUTION | In MAP-009 herkenbaar als lichte doos en wit puntje, maar op lage resolutie en schuin; de kleinere voorwerpen uit MAP-003/004 zijn niet afzonderlijk te onderscheiden. |
| F4 | Doorschijnende folie in het smalle raam rechts | ja | ja | ja | nee | DIRECTLY_VISIBLE | Folie is in MAP-009 zichtbaar, maar het smalle raam ligt buiten REF-MAP009-006; dit is het meest onderscheidende kenmerk en ontbrak dus in de VR-045-vergelijking. |
| F5 | Verticale plakstrook langs de folie | ja | ja | onbepaald | nee | NOT_VERIFIABLE | In MAP-003/004 duidelijk. In MAP-009 is aan de linkerrand van de folie een lichtere verticale baan te zien, maar dat kan ook een plooi of weerspiegeling zijn. PR #42 stelde de strook ook in MAP-009 vast; dat is hierbij teruggebracht tot niet verifieerbaar. |
| F6 | Positie: rechts van het tweedelige kozijn, onder de goot, boven donkere houten bekleding, bij de kaphoek rechtsonder | ja | ja | ja | nee | DIRECTLY_VISIBLE | Dezelfde ruimtelijke combinatie in alle drie; schuin perspectief maakt maten onvergelijkbaar. Plaat 280 bewijst alleen de muur, niet het pand van dit kozijn. |
| F7 | Buurkozijnen: zelfde indeling maar rolgordijnkast en geen folie | ja | ja | onbepaald | nee | DIRECTLY_VISIBLE | Linkerbuur in MAP-003 heeft dezelfde indeling met rolgordijnkast op het smalle raam, zonder folie. Slechts enkele buren zijn zichtbaar in een lange rij identieke woningen. |

Beeld: `physical_instance_approval_v1/RC-feature_comparison.jpg` (per kenmerk MAP-003, MAP-004, MAP-009).

### Uitsneden (originele pixels)

| Id | Foto | Regio [x0,y0,x1,y1] | Wat |
|---|---|---|---|
| C-VR045-REF | MAP-009 | [362, 362, 747, 682] | REF-MAP009-006: de uitsnede van de VR-045-review; alleen het tweedelige kozijn |
| C-PR42-WIDE | MAP-009 | [300, 300, 1050, 800] | PR #42: ruimere uitsnede; tweedelig kozijn + smal raam rechts + omgeving |
| C-NARROW | MAP-009 | [800, 500, 960, 760] | MAP-009: smal raam met folie (buiten de VR-045-uitsnede) |
| C-LEFTPANE | MAP-009 | [362, 362, 520, 600] | MAP-009: linkervak met witte merktekens (binnen de VR-045-uitsnede) |
| C-SILL | MAP-009 | [480, 570, 720, 720] | MAP-009: vensterbank onder het gordijn (binnen de VR-045-uitsnede) |
| C-M3-OBS | MAP-003 | [1167, 481, 1316, 571] | OBS-MAP003-011 (exacte observatie-uitsnede) |
| C-M3-WIDE | MAP-003 | [1150, 470, 1420, 590] | OBS-MAP003-011 plus smal raam rechts |
| C-M3-NARROW | MAP-003 | [1350, 478, 1415, 580] | MAP-003: smal raam met folie |
| C-M3-LEFTPANE | MAP-003 | [1170, 485, 1220, 570] | MAP-003: linkervak |
| C-M3-SILL | MAP-003 | [1215, 535, 1305, 575] | MAP-003: vensterbank |
| C-M3-NEIGH-L | MAP-003 | [300, 440, 600, 580] | MAP-003: linkerbuur, zelfde indeling |
| C-M4-OBS | MAP-004 | [535, 477, 692, 569] | OBS-MAP004-006 (exacte observatie-uitsnede) |
| C-M4-WIDE | MAP-004 | [520, 465, 790, 585] | OBS-MAP004-006 plus smal raam rechts |
| C-M4-NARROW | MAP-004 | [730, 470, 790, 583] | MAP-004: smal raam met folie |
| C-M4-LEFTPANE | MAP-004 | [540, 480, 590, 568] | MAP-004: linkervak |
| C-M4-SILL | MAP-004 | [580, 535, 675, 575] | MAP-004: vensterbank |

### Verwisseling met buurkozijnen

- Zichtbare buren: linkerbuur MAP-003 (zelfde indeling, rolgordijnkast, geen folie, één los merkteken elders); rechterbuur MAP-003 (andere indeling, open vleugels); buur MAP-004.
- Tegenvoorbeeld: MAP-007: zelfde raamtype bij een ander huis, rolgordijnen.
- Restrisico: Laag-tot-matig: de combinatie F1+F2+F3+F4 komt bij geen zichtbare buur voor, maar slechts enkele buren zijn zichtbaar in een rij van identieke woningen; kenmerken zijn deels tijdelijk (zelfde dag, 14-08-2026).

### Feature-match (alleen ondersteunend)

SIFT/RANSAC is alleen ondersteunend. De waarde hangt sterk af van uitsnede en methode: de exacte REF-MAP009-006-uitsnede geeft hier 35 en 26 inliers tegen de observatie-uitsneden, terwijl de P1-review (CLAHE, +12% marge, 360 px, groepsuitsnede) 4 vond en de ruime uitsneden van PR #42 8 of 5. Dat deze waarden zo uiteenlopen is zelf een reden om er niets op te baseren; hogere waarden komen ook bij niet-partners voor (PR #42: tot 54).

| Paar | Goede matches | Inliers |
|---|---|---|
| C-VR045-REF vs C-M3-OBS | 69 | 35 |
| C-VR045-REF vs C-M4-OBS | 50 | 26 |
| C-PR42-WIDE vs C-M3-WIDE | 18 | 5 |
| C-PR42-WIDE vs C-M4-WIDE | 26 | 5 |
| C-NARROW vs C-M3-NARROW | 46 | 18 |
| C-NARROW vs C-M4-NARROW | 9 | 5 |
| C-M3-OBS vs C-M4-OBS | 20 | 12 |
| C-M3-WIDE vs C-M4-WIDE | 61 | 29 |

## 6. Correctie op PR #42

- Plakstrook (F5) is in MAP-009 niet verifieerbaar; PR #42 noemde die als zichtbaar. De overige MAP-009-argumenten blijven staan.

## 7. Gevolgen voor IAR-OIC-VR-027

- READY_FOR_HUMAN_REVIEW kan blijven: **ja**; MAP-009-rol: `ADDITIONAL_EVIDENCE_NOT_RELIED_ON`; OIC hangt af van MAP-009: **nee**.
- OIC-VR-027 is SUPPORTED_CANDIDATE op basis van VR-027 (MEDIUM bron, STRONG kwaliteitsreview, menselijk SAME); MAP-009 speelt daarin geen rol.
- VR-045 heeft geen menselijk besluit; het blijft open en wordt in de aanvraag zo getoond.
- MAP-009 is aanvullend bewijs voor hetzelfde kozijn, geen nieuwe fysieke instance en geen nieuwe observatie.

## 8. Advies voor de menselijke beoordeling

1. Laat de reviewer VR-045 apart beoordelen met de ruimere uitsnede (smal raam erbij), niet met REF-MAP009-006 alleen.
2. Leg de beperking vast dat alle bewijs visueel en deels tijdelijk is; een derde foto uit een andere sessie of dag zou de verwisselingsvraag het sterkst beslissen.
3. Neem de plakstrook niet als MAP-009-bewijs mee.

## 9. Effecten

```json
{
  "bag_links_created": 0,
  "building_totals": null,
  "costs": null,
  "human_decisions_changed": 0,
  "human_decisions_created": 0,
  "instances_created": 0,
  "new_observations": 0,
  "oic_changed": false,
  "pilot_register_changed": false,
  "quality_review_modified": false,
  "quantities": null,
  "vr045_modified": false
}
```

**STOP.** Stop vóór iedere menselijke goedkeuring, instance-activatie en merge.
