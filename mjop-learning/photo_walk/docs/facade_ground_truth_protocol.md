# Testprocedure gevelscanner: 5 tot 10 kozijnen met rolmaat

Doel: een kleine, eerlijke referentieset om te zien of de scanner de **buitencontour van het kozijn** vindt (en niet alleen het glas), en hoe groot de **maatfout** is als hij het goede kozijn heeft. Herkenning en meting worden apart beoordeeld. Deze set is alleen voor evaluatie: drempels worden er niet op afgestemd.

## Wat je nodig hebt
* iPhone met LiDAR (Pro-model) en de MJOP Live-app (gevelscanner).
* Rolmaat of duimstok (liefst een laser voor hoge kozijnen; noteer welk gereedschap).
* 5 tot 10 kozijnen die je veilig van buiten kunt opmeten, zo gevarieerd mogelijk:
  * enkel glas in één vak en kozijnen met **meerdere ruiten** (tussenstijl/tussendorpel);
  * wit en donker kozijn; metselwerk en gevelbekleding;
  * minstens één **deur** (met en zonder glas);
  * minstens één kozijn in de zon (reflectie) en één in de schaduw.

## Per kozijn
1. **Rolmaat**: meet de **buitenmaat van het kozijn** (buitenkant profiel tot buitenkant profiel), niet het glas en niet de muuropening.
   * Breedte: op halve hoogte. Hoogte: op halve breedte, van bovenkant kozijn tot onderkant onderdorpel.
   * Noteer in meters met 3 decimalen (bv. `1.235`), plus het gereedschap.
   * Kun je de onderdorpel of een kant niet goed meten: noteer dat (dan telt dit kozijn niet mee voor de meetfout).
2. **Foto in de app**: sta recht voor het kozijn op 2-4 m, hele kozijn plus wat muur eromheen in beeld, telefoon rechtop, rustig vasthouden.
   * Laat de app herkennen en verander **niets** voordat je exporteert (zo meten we de automatische herkenning).
   * Exporteer (knop *Exporteren*; bestand `photo_walk_<sessie>.json` in de Bestanden-app).
3. **Daarna corrigeren** (optioneel, tweede export): bevestig of versleep de buitencontour en exporteer opnieuw. Zo zien we ook hoe goed de maat is ná menselijke correctie.

## Wat ik daarna doe
* Per foto teken ik (of jij) de ware contouren in `facade_ground_truth_v1` (schema `schemas/facade_ground_truth_v1.schema.json`, voorbeeld `examples/ground_truth/facade_ground_truth_synthetic.json`):
  `FRAME_OUTER` (buitenkozijn), `GLASS_PANE` (elk glasvlak), optioneel `FACADE_GROSS`, plus jouw rolmaatmaten.
* Beoordeling: `python -m photo_walk_core.facade_eval ground_truth.json export.json rapport.json`
  * **Herkenning** (zonder schaal): goed herkende kozijnen, gemiste kozijnen, en de fouten apart: *glas als kozijn*, *één kozijn in stukken* (bv. elke ruit een kozijn), *overig*. Plus de hoekafwijking in pixels.
  * **Meting** (alleen bij goed herkende kozijnen met rolmaat én een app-maat): afwijking breedte/hoogte in mm en procent, en bruto m². Een maat die op het glas is gemeten telt hier NIET mee: dat is een herkenningsfout.
* Er komt **geen nauwkeurigheidsclaim** uit 5-10 kozijnen. Het rapport noemt de steekproefgrootte; het is een eerste praktijktest om te beslissen of we een eigen herkenningsmodel nodig hebben.

## Wat wel en niet in de set hoort
* Wel: de originele app-export (die verwijst naar de foto en dieptekaart op de telefoon; die blijven ongewijzigd bewaard), jouw rolmaatmaten, de door een mens getekende contouren.
* Niet: foto's van mensen of kentekens, adressen van anderen dan het eigen complex (privacy), en geen 3D BAG-waarden als "waarheid" (3D BAG is alleen een plausibiliteitscontrole).
