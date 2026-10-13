# Physical Object Identity Pilot v1

Status: **voorstel/pilot**. Er is geen instance, samenvoeging, BAG-koppeling, telling, hoeveelheid of kostenpost aangemaakt. Dit rapport en `physical_object_identity_pilot_v1.json` worden gegenereerd door `scripts/object_identity_pilot.py` (deterministisch).

## 1. Gegevensmodel (hergebruik, geen tweede model)

Bestaand en hergebruikt: observaties `OBS-*` en relaties `VR-*` (review-JSON), `SOC-*` (foto-niveau kandidaatgroepen uit de fotoarchief-audit), evidence_class/evidence_basis (P1-kwaliteitsreview), menselijke pilotbesluiten (register) en `FI-*` frame instances (bevroren store, onaangeroerd). `component_repeat_groups_v1.json` (herhaalde elementen) is een ander concept en blijft leeg.

Wat ontbrak: een observatie-niveau-verband dat relatie, bewijs en menselijk besluit samenbrengt zonder instance te zijn. Dat is het enige nieuwe concept: `OIC-*`.

| Concept | ID | Betekenis |
|---|---|---|
| PHOTO_OBSERVATION | `OBS-*` | Wat in één foto zichtbaar is. Buiten de instance-store, telt nergens. |
| VISUAL_OVERLAP_RELATION | `VR-*` | Visuele relatie tussen twee observaties of gevelsecties (review-JSON). FACADE_SECTION ≠ PHYSICAL_OBJECT. |
| PROVISIONAL_IDENTITY_LINK | `OIC-*` | NIEUW: kandidaat dat twee observaties hetzelfde fysieke object tonen. Geen instance. |
| APPROVED_PHYSICAL_INSTANCE | `FI-*` | Bestaat alleen in de instance-store (bevroren); wordt door deze pilot nooit aangemaakt. |

Velden van een kandidaatverband: `candidate_group_id`, `observation_ids`, `photo_ids`, `supporting_relation_ids`, `evidence_refs`, `evidence_strength`, `evidence_basis`, `decision_refs`, `identity_status`, `unresolved_questions`, `source_hashes`, en vaste vlaggen `is_instance=false`, `merged=false`, `counts_in_any_total=false`, `bag_pand_id=null`, `same_physical_frame_proven=false`, `frame_instance_id=null`.

## 2. Onderzochte relatie VR-027

- Klasse in de bron: `POSSIBLY_SAME_PHYSICAL_FRAME`, sterkte in de bron: MEDIUM (kwaliteitsreview: STRONG_VISUAL_SUPPORT).
- Basis: Tweedelig kozijn bovenste rij boven de kap.

## 3. Relevante foto-observaties

| Observatie | Foto | Bestand | Uitsnede (px) | Zichtbaarheid | Onzekerheid | Pand |
|---|---|---|---|---|---|---|
| OBS-MAP003-011 | MAP-003 | IMG_8518.JPEG | [1167, 481, 1316, 571] | FULL | LOW | NOT_PROVEN |
| OBS-MAP004-006 | MAP-004 | IMG_8520.JPEG | [535, 477, 692, 569] | FULL | LOW | NOT_PROVEN |

## 4. Exacte bewijsverwijzingen

- Foto MAP-003: sha256 `9f121e711b0cea13cc22f8ff7ea89c234fcd35fc8a95ce8c43334f05d43cc02d`
- Foto MAP-004: sha256 `197556869a8e91a9fe285197aa4c0db595f059bf18ae79126bdefd05d4867576`
- Bewijsbasis: FEATURE_MATCH, UNIQUE_CONFIGURATION. Visueel overzicht: `p1_quality_review/QREL-sheet-2.jpg` en `C1_MAP-003_vs_MAP-004_upper_facade.jpg` (map `photo_review_map003_map004_v1`).
- Kenmerkmatch (alleen ondersteunend): 39 inliers; beste niet-partner: 24 inliers.
- Besluit: `RV-REL-VR-027` = SAME, bevestigd door de gebruiker via ChatGPT (niet via het HTML-formulier), source_ref_hash `b4c272b4bf256bba`, betekenis `SAME_PHYSICAL_OBJECT_CANDIDATE`: kandidaat, niet bewezen, niet samengevoegd.

## 5. Voorlopige identiteitsstatus

`OIC-VR-027`: **SUPPORTED_CANDIDATE** (observaties OBS-MAP003-011, OBS-MAP004-006). Dit is een kandidaat, geen instance en geen telling.

Onzekerheden die blijven:
- Bewijst de visuele combinatie (stickers, merktekens, gordijn) het fysieke object, of staan er identieke woningen met dezelfde inrichting? Alleen een derde onafhankelijke foto of een unieke afwijking kan dat beslissen.
- Beide observaties liggen in dezelfde gevelreeks (SOC-002); die groep is een foto-niveau-kandidaat (confidence MEDIUM), geen bewijs voor het kozijn.
- Geen van beide observaties heeft een bewezen pand (pand_status NOT_PROVEN); een objectidentiteit zegt niets over het BAG-pand.
- De bronrelatie noemt sterkte MEDIUM, de kwaliteitsreview STRONG_VISUAL_SUPPORT; het verschil is niet menselijk opgelost.
- De pilot-SAME is bevestigd via ChatGPT, niet via het HTML-formulier; er is geen instance-besluit gegeven.

## 6. Negatieve controles

| Controle | Relatie | Menselijk besluit | Uitkomst | Identiteitsverband? | Geslaagd |
|---|---|---|---|---|---|
| A Gevelsectie is geen fysiek kozijn | VR-020 | SAME | REJECTED | nee | ja |
| B Onvoldoende bewijs (UNDECIDABLE) | VR-026 | UNDECIDABLE | UNRESOLVED | nee | ja |
| C Matig bewijs (UNDECIDABLE) | VR-024 | UNDECIDABLE | UNRESOLVED | nee | ja |
| C2 Hypothetisch: VR-024 met SAME maakt nog geen identiteitsverband | VR-024 | UNDECIDABLE (hypothetisch: SAME) | UNRESOLVED | nee | ja |
| D1 Repeterende woningen, te donker (VR-022), hypothetisch SAME | VR-022 | - (hypothetisch: SAME) | UNRESOLVED | nee | ja |
| D2 Groepseindpunt met herhaling (VR-044) wordt geweigerd, ook bij hypothetisch SAME | VR-044 | - (hypothetisch: SAME) | REJECTED | nee | ja |
| D3 Alleen gelijke indeling/feature-match: VR-025 | VR-025 | - (hypothetisch: SAME) | CANDIDATE | ja (kandidaat) | ja |
| E Niet-transitief A~B, B~C, A≁C | synthetisch | - | groepen [], ketens 1 | n.v.t. | ja |
| E2 Alleen volledig ondersteunde clique A,B,C wordt één kandidaatgroep | synthetisch | - | groepen [['A', 'B', 'C']], ketens 0 | n.v.t. | ja |
| F Twee observaties in dezelfde foto kunnen nooit hetzelfde object zijn | VR-SELF (synthetisch) | - | REJECTED | nee | ja |

Toelichting: VR-020 heeft SAME maar alleen als `SAME_FACADE_SECTION`; VR-024 en VR-026 zijn UNDECIDABLE; zonder onderscheidend anker (UNIQUE_CONFIGURATION of PLATE_ANCHOR) of met REPETITION_RISK/HIDDEN/TOO_DARK ontstaat geen identiteitsverband, ook niet bij een hypothetisch SAME. Relaties met groepseindpunten of foto-2-ID's (FC-M2/FI-M2) worden geweigerd. Identiteit is niet-transitief: een groep van meer dan twee observaties bestaat alleen als elk paar direct ondersteund is.

## 7. Risico bij identieke naastgelegen woningen

De Maldenhof-woningen zijn grotendeels identiek. Niet-partners halen tot 24 inliers (partner: 39). Vorm, kleur, raamindeling en feature-match bewijzen daarom nooit identiteit; alleen een uniek anker (hier de combinatie stickers/merktekens/gordijn) of een leesbare plaat doet dat, en dan nog uitsluitend als kandidaat.

## 8. Ontbrekend voor een definitieve instance

- Een afzonderlijk menselijk besluit om het kandidaatverband als fysieke instance te activeren (bestaat niet en wordt niet voorgesteld door deze pilot).
- Een tweede onafhankelijke foto/hoek of unieke afwijking die buurwoningen uitsluit.
- Een leesbaar huisnummer/plaat of ander bewijs voor het pand (BAG-koppeling is een aparte stap).
- Beslissing over de relatie met de 48 OPEN APP-besluiten, tel- en hoeveelheidsregels.

## 9. Statusmodel

### CANDIDATE
- Voorwaarden: Relatie is PHYSICAL_OBJECT; observaties bestaan, verschillende foto's, bronhashes kloppen. Nog geen (voldoende) menselijk SAME of onderscheidend bewijs.
- Beslissing nodig: Menselijke beoordeling van de relatie (SAME / DIFFERENT / UNDECIDABLE).
- Toegestaan: bewijs verzamelen; door mens laten beoordelen; betere foto vragen
- Verboden: instance maken; samenvoegen; BAG-koppelen; tellen; hoeveelheid of kosten afleiden

### SUPPORTED_CANDIDATE
- Voorwaarden: Geregistreerd menselijk SAME met kloppende source_ref_hash voor een PHYSICAL_OBJECT-relatie, evidence_class STRONG met onderscheidend anker (UNIQUE_CONFIGURATION of PLATE_ANCHOR), geen REPETITION_RISK/HIDDEN/TOO_DARK.
- Beslissing nodig: Een afzonderlijk, expliciet menselijk besluit voor elke verdere stap (instance, BAG-koppeling).
- Toegestaan: als kandidaat tonen in review en rapport; extra onafhankelijke foto's zoeken; vervolgbesluit voorbereiden
- Verboden: automatisch instance maken; samenvoegen; BAG-pand koppelen; unieke telling aanpassen; hoeveelheden/kosten afleiden; transitief uitbreiden naar andere observaties

### UNRESOLVED
- Voorwaarden: Menselijk besluit UNDECIDABLE (of bewijs onvoldoende/repetitief). Er wordt GEEN identiteitsverband gemaakt.
- Beslissing nodig: Betere foto of nieuw menselijk besluit.
- Toegestaan: bewaren als open vraag; betere foto aanvragen
- Verboden: identiteit afleiden uit gelijkenis; samenvoegen; tellen; BAG-koppelen

### REJECTED
- Voorwaarden: Menselijk besluit DIFFERENT, of de relatie is geen objectrelatie (gevelsectie) of botst met de regels (zelfde foto).
- Beslissing nodig: Geen; herbeoordeling kan alleen met nieuw bewijs en nieuw besluit.
- Toegestaan: vastleggen waarom afgewezen
- Verboden: alsnog samenvoegen; als kandidaat blijven tonen

Overgangen: (geen) → CANDIDATE, UNRESOLVED, REJECTED, SUPPORTED_CANDIDATE; CANDIDATE → SUPPORTED_CANDIDATE, UNRESOLVED, REJECTED; SUPPORTED_CANDIDATE → UNRESOLVED, REJECTED; UNRESOLVED → CANDIDATE, REJECTED; REJECTED → (eindstatus)

Geen enkele overgang leidt naar een definitieve fysieke instance; die stap bestaat in deze pilot niet.

## 10. Aanbeveling voor de volgende stap

Laat de gebruiker beoordelen of OIC-VR-027 als kandidaat blijft staan, en vraag een tweede onafhankelijke foto of detail van dit kozijn. Pas daarna kan een afzonderlijk besluit over instance-activatie worden voorbereid. Pas het model niet op andere relaties toe voordat dit besluit er is.
