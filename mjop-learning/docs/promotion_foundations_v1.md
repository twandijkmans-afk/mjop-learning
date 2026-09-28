# Promotion Foundations v1 — deterministische Batch 1

Doel: de gevalideerde deterministische handoff-laag
`data/extracted_deterministic/batch1_v1/` controleerbaar maken en de gevolgen van een
latere promotie naar de canonieke pipeline zichtbaar maken. **In deze fase wordt niets
gepromoot, gemigreerd of herbouwd.** `data/extracted`, `data/normalized`, `data/verified`,
price observations, comparability, kengetallen en human decisions blijven ongewijzigd.

## Tooling

```bash
python3 scripts/promote_deterministic_batch.py --check            # handoff-laag valideren, schrijft niets
python3 scripts/promote_deterministic_batch.py --dry-run          # weigert bij een ongeldige handoff
python3 scripts/promote_deterministic_batch.py --dry-run --analyse-despite-invalid-handoff
                                                                  # -> reports/deterministic_promotion_batch1_v1.json
                                                                  #    (handoff_valid: false + alle fouten)
```

`--check` draait geen xpdf; het controleert de opgeslagen laag:

- `manifest.json`-structuur, `manifest.sha256`, `batch_id`, `xpdf_version`;
- documentset exact DOC-001..DOC-010: 9 PASS + DOC-003 `DUPLICATE_SKIP`
  (`duplicate_of` DOC-002, `relation` DREL-001, bevestigd in `document_relations.json`);
- `source_sha256` tegen `reports/document_registry.json` én het ruwe bestand;
- `output_path`/`output_sha256`, geen DOC-003-JSON, geen onverwachte bestanden;
- parser-/profiel-/extractormetadata en xpdf 4.06 in het manifest, en de inhoud van elk
  record (document_id, source_sha256, pdftotext-versie, profiel, regels, valutaregel,
  `uses_ai_api`/`network_calls` false) tegen zijn manifestregel.

`--dry-run` voert eerst `--check` uit en schrijft alleen het rapport (nooit in `data/`):
verschillen per document in categorieën A–G, classificatie van de 220 oude accepts
(EXACT_MATCH_CANDIDATE / AMBIGUOUS / NO_MATCH, alleen exacte sleutels) en een read-only
analyse van `data/review_decisions/human_decision_records.json`.

## output_sha256 en CRLF (architectuurpunt, nog open)

`--check` is strikt: `output_sha256` moet gelijk zijn aan de sha256 van de bytes in de
repository. Er is geen line-ending-tolerantie. Bij een afwijking voegt `--check` alleen een
diagnose toe (`output_hash_diagnosis`); die maakt de check nooit geldig.

Stand van batch1_v1 (manifest v1.0.0, ongewijzigd):

- 9 van de 9 `output_sha256`'s komen **niet** overeen met de bytes in Git (LF; blob == worktree,
  `git ls-files --eol`: `i/lf w/lf`, geen `core.autocrlf` in de cloud).
- 9 van de 9 komen **wel exact** overeen na uitsluitend LF → CRLF (elke `\n` → `\r\n`).
- De geparste JSON is voor alle 9 semantisch gelijk (LF-versie == CRLF-versie).
- Er is geen ander byteverschil: geen CR in de repository-bytes, geen BOM, eind-newline
  aanwezig, en de sha256 van de exact getransformeerde bytes is gelijk aan de manifest-hash
  (dus de Windows-bytes waren precies die transformatie). JSON-strings bevatten geen ruwe
  newlines (json.dumps escapet ze), dus de transformatie raakt alleen witruimte tussen tokens.

Gevolg: `--check` faalt nu op batch1_v1 met 9 fouten (en verder niets). Dat is bewust.

### Voorstel manifest v1.1 (nog niet uitgevoerd)

| Optie | Inhoud | Beoordeling |
|---|---|---|
| A | `output_sha256` = sha256 van de repository-bytes (LF) | strikt verifieerbaar in de cloud, maar de oorspronkelijke Windows/xpdf-validatiehash gaat verloren |
| B | `repository_output_sha256` (LF, strikt) + `validated_windows_output_sha256` (CRLF, historisch) | beide hashes expliciet; cloud controleert alleen de eerste strikt; de tweede is provenance van de lokale validatie |
| C | B + `canonical_content_sha256` (line-ending-onafhankelijk) | maakt content-equivalentie aantoonbaar en platformonafhankelijk vergelijkbaar |

Aanbeveling: **C**, als nieuwe `manifest_version: "1.1.0"` naast (niet over) v1.0.0:

- `repository_output_sha256`: strikt gecontroleerd door `--check` (exacte bytes);
- `validated_windows_output_sha256`: de huidige v1.0-waarde, alleen als vastgelegd feit
  (niet gebruikt voor geldigheid), met `validated_windows_newline: "CRLF"`;
- `canonical_content_sha256`: sha256 van `json.dumps(obj, ensure_ascii=False, sort_keys=True,
  separators=(",", ":"))` in UTF-8; `--check` herberekent en eist exacte gelijkheid;
- `--check` controleert daarnaast expliciet dat `validated_windows_output_sha256` ==
  sha256(repository-bytes LF → CRLF), als afzonderlijke, benoemde controle
  (`windows_validation_bytes_reproducible`) - geen tolerantie, een vastgelegde relatie;
- `supersedes: {"manifest_version": "1.0.0", "manifest_sha256": "<huidige>"}`; v1.0 blijft
  bewaard (bijv. `history/manifest_v1.0.0.json`), niets verdwijnt;
- voor nieuwe runs: extractor-output altijd met `newline="\n"` schrijven, zodat Windows en
  cloud dezelfde bytes produceren; een gerichte `.gitattributes`-regel alleen voor
  `data/extracted_deterministic/** -text` of `eol=lf` (geen brede renormalisatie).

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
