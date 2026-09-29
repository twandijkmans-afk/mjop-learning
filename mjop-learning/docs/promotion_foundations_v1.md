# Promotion Foundations v1 — deterministische Batch 1

Doel: de gevalideerde deterministische handoff-laag
`data/extracted_deterministic/batch1_v1/` controleerbaar maken en de gevolgen van een
latere promotie naar de canonieke pipeline zichtbaar maken. **In deze fase wordt niets
gepromoot, gemigreerd of herbouwd.** `data/extracted`, `data/normalized`, `data/verified`,
price observations, comparability, kengetallen en human decisions blijven ongewijzigd.

## Tooling

```bash
python3 scripts/promote_deterministic_batch.py --check            # handoff-laag valideren, schrijft niets
python3 scripts/promote_deterministic_batch.py --dry-run          # -> reports/deterministic_promotion_batch1_v1.json
                                                                  #    (weigert bij een ongeldige handoff, tenzij
                                                                  #    --analyse-despite-invalid-handoff)
```

`--check` draait geen xpdf; het controleert de opgeslagen laag:

- `manifest.json`-structuur, `manifest.sha256`, `batch_id`, `xpdf_version`;
- documentset exact DOC-001..DOC-010: 9 PASS + DOC-003 `DUPLICATE_SKIP`
  (`duplicate_of` DOC-002, `relation` DREL-001, bevestigd in `document_relations.json`);
- `source_sha256` tegen `reports/document_registry.json` én het ruwe bestand;
- `output_path` en de drie output-hashes (zie hieronder), geen DOC-003-JSON, geen onverwachte bestanden;
- parser-/profiel-/extractormetadata en xpdf 4.06 in het manifest, en de inhoud van elk
  record (document_id, source_sha256, pdftotext-versie, profiel, regels, valutaregel,
  `uses_ai_api`/`network_calls` false) tegen zijn manifestregel.

`--dry-run` voert eerst `--check` uit en schrijft alleen het rapport (nooit in `data/`):
verschillen per document in categorieën A–G, classificatie van de 220 oude accepts
(EXACT_MATCH_CANDIDATE / AMBIGUOUS / NO_MATCH, alleen exacte sleutels) en een read-only
analyse van `data/review_decisions/human_decision_records.json`.

## Manifest v1.1 (uitgevoerd) en de CRLF-kwestie

Manifest v1.0.0 legde per document één `output_sha256` vast, berekend op Windows over de
CRLF-vorm van de bestanden; git bewaart ze als LF. Vastgesteld voor alle 9 PASS-documenten:
de v1.0-hash wijkt af van de repository-bytes, is exact gelijk aan sha256 na uitsluitend
LF → CRLF, de geparste JSON is gelijk, en er is geen ander byteverschil (geen CR, geen BOM).

`manifest.json` is daarom `manifest_version: "1.1.0"` met per PASS-document:

| Veld | Betekenis | Controle in `--check` |
|---|---|---|
| `repository_output_sha256` | sha256 van de gecommitte bytes (LF) | strikt, exacte bytes |
| `canonical_content_sha256` | sha256 van `json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`, UTF-8 | strikt herberekend |
| `validated_windows_output_sha256` + `validated_windows_newline: "CRLF"` | de oorspronkelijke Windows/xpdf 4.06-validatiehash (v1.0) | benoemde relatie `windows_validation_bytes_reproducible`: repository-bytes bevatten geen CR en sha256(LF → CRLF) is exact gelijk; én gelijk aan de `output_sha256` in het historische v1.0-manifest |

Er is geen tolerante hashcontrole: een CRLF-hash als repository-hash, een CR in de
repository-bytes of een afwijkende canonieke hash is altijd een fout.

Historie: het oorspronkelijke manifest staat ongewijzigd in
`batch1_v1/history/manifest_v1.0.0.json` (+ `.sha256`); `supersedes` legt versie, sha256,
pad en reden vast en `--check` controleert ze. De JSON-bestanden van de documenten zelf
zijn niet gewijzigd.

Voor nieuwe runs (nog te doen): extractor-output altijd met `newline="\n"` schrijven, en
een gerichte `.gitattributes`-regel alleen voor `data/extracted_deterministic/**`.

## Toolversies die batch1_v1 bepalen

| Onderdeel | Versie (uit manifest/records) |
|---|---|
| Code | commit `be34bac` (`code_commit` per document; twee runs byte-identiek) |
| Extractor | `deterministic_extraction.py`, `deterministic_extraction_v1.0.0` |
| Profiel / regels | `pro_vve_overzicht15` 1.0.0, `pro_vve_overzicht_rules_v1`, `pdf_whole_euro_dot_thousands` |
| pdftotext | `pdftotext version 4.06 [www.xpdfreader.com]` (lokaal, Windows) |
| Tekstlaag (block-provenance) | `text_layer` 1.0.0 met pdfplumber 0.11.10, pdfminer.six 20260107 |

`requirements.txt` pint deze versies (nog) niet; een andere pdfplumber-versie kan
`text_layer_sha256` en block_id's veranderen.

## normalize_batch: externe elementcodering

`normalize_batch.normalize_record` normaliseert `element_code` niet via de interne
vocabulaire als het document externe codering heeft (`extraction_metadata.external_element_coding`
of `DOCUMENT_PROFILES[doc]["external_element_coding"]`, nu DOC-004): `original_value`
blijft, `normalized_value` blijft null, `normalization_skipped_reason:
"external_element_coding"`. Interne documenten gedragen zich exact als voorheen
(regressietest: `data/extracted` → `normalize_record` == `data/normalized`).

## Human decisions

Stabiele identiteit is `observation_id` (positioneel uit de xpdf-bronlaag), nooit
`pair_id` (volgnummer). block_id's van de nieuwe laag gebruiken een andere regelnummering
(pdfplumber-tekstlaag) dan observation_id (xpdf-regel); koppelen kan alleen via pagina +
brontekst.
