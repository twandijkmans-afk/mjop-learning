# BAG/3D BAG-snapshots

Onveranderlijke, content-addressed vastleggingen van PDOK/BAG/3D BAG-antwoorden (`scripts/bag_snapshots.py fetch` /
`fetch-range`). Bestandsnaam = `snapshot_id`. Nooit met de hand aanpassen; zie `docs/building_link_3dbag_evidence_v1.md`.

Een snapshot is bronvastlegging, geen besluit: welke panden bij een document horen, legt een mens vast in
`data/building_links/building_link_records.json`.

Stand (2026-10-05): `BAGSNAP-431559474da45dcf` (DOC-005) en `BAGSNAP-e23aa139a8589881` (DOC-006), beide
`fetch-range` Maldenhof 240–296 Amsterdam (56 adressen, 40 kandidaat-panden). Opgehaald via de officiële
PDOK- en 3D BAG-endpoints.

Stand (2026-10-05, Quantity Engine Generalization v1): `BAGSNAP-599d2f2004100011` (DOC-012), `fetch` Meppelweg 819,
2544 AW, "Den Haag" (BAG-woonplaatsnaam 's-Gravenhage via de expliciete alias `WPA-den-haag`, vastgelegd in de
query). Alleen de opvraging uit het opgegeven adres is canoniek; de hypothese "Meppelweg 801-883" uit de objectnaam
staat bewust NIET hier maar in `reports/quantity/doc012_scope_hypotheses/` (canonical=false).
