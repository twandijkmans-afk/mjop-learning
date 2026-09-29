# data/incoming — hier nieuwe MJOP's en offertes neerzetten

Zet nieuwe bestanden (PDF, XLS, XLSX) in deze map. Submappen mogen, bijvoorbeeld één map per
gebouw of per aanlevering. De bestandsnaam maakt niet uit: een document wordt herkend aan zijn
inhoud (sha256).

Daarna: GitHub → Actions → "Process incoming MJOPs" → "Run workflow" (of gewoon uploaden via
GitHub; de workflow start dan vanzelf). Het resultaat staat in `reports/incoming/<batch_id>.json`.

Laat de bestanden hier staan tot de batch is gepromoveerd. Er wordt niets automatisch in de
canonieke kennis opgenomen. Uitleg: `docs/incoming_pipeline_v1.md`.
