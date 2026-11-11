# Gevelscanner 2.0 — meetplan voor veldvalidatie

**Stand nu: de nauwkeurigheid is niet bewezen.** Alle tests draaien op synthetische scènes. Die tonen aan dat de rekenregels kloppen; ze zeggen niets over echte iPhone-LiDAR, echte kozijnen of de herkenning op echte gevels.
Dit plan beschrijft hoe het bewijs er komt. Er staan bewust **geen acceptatiegrenzen** in: die stelt de eigenaar vast nadat de eerste cijfers er zijn.

## Wat er al is aan echte gegevens
* Eén kozijn (92 × 210 cm, glas 79 × 198 cm; rolmaat, opgegeven door de eigenaar, niet door een tweede meting bevestigd) met twee meetdiagnoses (`python/tests/real_captures/`). Zonder foto's en zonder dieptekaart: daarmee kan de 2.0-pijplijn niet worden nagespeeld.
* Verder niets. Geen gelabelde gevelfoto's, geen trainingsdata.

## Wat gemeten wordt
Per goed gekoppeld kozijn: fout in **breedte**, **hoogte**, **totale oppervlakte** en **glasoppervlakte** (absoluut en relatief), en het verschil in **aantal draaiende delen**.
Per gevel: fout in het **aantal kozijnen**.
Over alles: **percentage dubbel getelde** kozijnen, **percentage niet-herkende** kozijnen, en objecten die geen kozijn bleken.

Het script `python -m photo_walk_core.gevel_eval referentie.json inventaris.json rapport.json` rekent dit uit (getest). Het rapport noemt de steekproefgrootte, heeft `verdict: null` en geeft geen oordeel.

## Benodigdheden
* iPhone met LiDAR (Pro-model) en een testbuild van MJOP Live.
* Rolmaat en bij voorkeur een laserafstandsmeter; noteer het gereedschap.
* Toestemming van de VvE/bewoners voor foto's van de gevel.

## Steekproef (eerste ronde)
Minimaal 3 gebouwen, per gebouw 2 gevels, samen ten minste 40 kozijnen, zo gevarieerd mogelijk:
* hout, kunststof en aluminium; lichte en donkere kozijnen;
* één vak, meerdere vakken naast en boven elkaar, deuren met en zonder glas;
* terugliggend en vlak in de gevel liggend;
* zon (spiegeling) en schaduw; bewolkt en laagstaande zon;
* kozijnen direct naast elkaar; begane grond en eerste verdieping;
* minstens één gevel met begroeiing of een obstakel.

Dit is een eerste praktijktest. Hij is te klein voor een algemene nauwkeurigheidsclaim.

## Werkwijze per gevel
1. **Eerst met de hand** (zodat de app-uitkomst de meting niet beïnvloedt): per kozijn buitenmaat breedte en hoogte in meters met drie decimalen; glasmaat per vak (breedte × hoogte, dagmaat); aantal draaiende en vaste delen. Noteer wat niet te meten is als onbekend.
2. **Fotoronde in de app**, in één keer (één scansessie per gevel): overzichtsfoto's met overlap, daarna per kozijn twee foto's vanaf een stap opzij. Verander niets aan de herkende contouren.
3. Rond de ronde af en bewaar de inventaris (in deze fase via de selftest-/exportroute van de ontwikkelbuild).
4. Vul `gevelscan_reference_v1` in (schema `schemas/gevelscan_reference_v1.schema.json`, voorbeeld `examples/ground_truth/gevelscan_reference_synthetic.json`). Zet per echt kozijn de object-id('s) uit de app (scherm *Kozijn* → *Kenmerk*): één id = herkend, meerdere = dubbel geteld, geen = gemist. Zet `frames_complete: true` alleen als werkelijk alle kozijnen van de gevel in de lijst staan.
5. Herhaal de ronde één keer **met** bevestigde contouren, om herkenning en meting apart te kunnen beoordelen.

Referentiebestanden van echte gebouwen horen niet in Git (privacy); bewaar ze buiten de repository. Gebruik ze nooit om drempels of herkenning op af te stemmen: dan is het geen onafhankelijke toets meer.

## Wat er daarna beslist moet worden (door de eigenaar)
1. Acceptatiegrenzen per hoeveelheid (welke fout is voor een MJOP aanvaardbaar).
2. Of de herkenning met Vision-kandidaten volstaat of dat een getraind model nodig is (en met welke data).
3. Of en wanneer `PipelineValidation.current` om mag, zodat betrouwbare resultaten automatisch verwerkt worden.

## Ook nog op een echt toestel te controleren (los van nauwkeurigheid)
* dat de inventaris na *Toevoegen aan MJOP* in de website verschijnt;
* rekentijd, warmte en batterij bij een ronde van 30–50 foto's;
* of de dekkingsweergave en de gerichte vragen in de praktijk begrijpelijk zijn;
* hervatten van een onderbroken ronde met inventaris;
* de scherpte- en spiegelingsdrempels (nu werkwaarden).
