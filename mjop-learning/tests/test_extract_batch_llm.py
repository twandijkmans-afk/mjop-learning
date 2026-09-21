"""
Tests voor de daadwerkelijke extractielogica in scripts/extract_batch.py
(strip_normalization, canonicalize_ids, enforce_review_floor, extract_document).

Er wordt NERGENS een echte Anthropic-call gemaakt: model_fn wordt overal
gestubt, zodat deze tests zonder ANTHROPIC_API_KEY en zonder netwerktoegang
draaien. Dat is bewust: deze tests toetsen de garanties uit CLAUDE.md (nooit
verzinnen, altijd provenance/confidence, deterministische review-ondergrens,
nooit zelf normaliseren) - niet de kwaliteit van een specifiek LLM-antwoord.
"""
import copy
import importlib.util
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS_DIR = os.path.join(PROJECT_ROOT, "schemas")
VOCAB_DIR = os.path.join(PROJECT_ROOT, "vocabularies")

spec = importlib.util.spec_from_file_location(
    "extract_batch", os.path.join(PROJECT_ROOT, "scripts", "extract_batch.py")
)
extract_batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract_batch)


def make_extracted_value(value=None, confidence=0.0, requires_human_review=True,
                          source_confidence="low", conflict=False):
    ev = {
        "value": value,
        "confidence": confidence,
        "requires_human_review": requires_human_review,
        "conflict": conflict,
        "provenance": {
            "document_id": "DOC-TEST",
            "page": None,
            "table_index": None,
            "text_fragment": None,
            "source_confidence": source_confidence,
        },
    }
    return ev


def make_valid_building():
    return {
        "construction_year": make_extracted_value(),
        "number_of_units": make_extracted_value(),
        "building_type": make_extracted_value(),
        "address": make_extracted_value(),
        "inspection_date": make_extracted_value(),
        "mjop_period": make_extracted_value(),
    }


def make_valid_record():
    return {
        "building": make_valid_building(),
        "elements": [
            {
                "element_id": "el-1",
                "element_type": {"original_value": "gevel", "normalized_value": None},
                "quantity": make_extracted_value(value="100", confidence=0.9, requires_human_review=False, source_confidence="high"),
            }
        ],
        "observations": [
            {
                "observation_id": "obs-1",
                "element_id": "el-1",
                "source": {"document_id": "DOC-TEST", "source_confidence": "medium", "page": 3, "table_index": None, "text_fragment": None},
                "requires_human_review": False,
            }
        ],
        "maintenance_actions": [
            {
                "action_id": "act-1",
                "element_id": "el-1",
                "unit_cost": {
                    "value": "125.50",
                    "is_estimated": False,
                    "provenance": {"document_id": "DOC-TEST", "source_confidence": "low", "page": 4, "table_index": None, "text_fragment": None},
                },
                "requires_human_review": False,
            }
        ],
        "extraction_notes": "test",
    }


# ---------------------------------------------------------------------------
# enforce_review_floor
# ---------------------------------------------------------------------------

def test_validate_against_schema_works_with_relative_schemas_dir():
    """Regressie: bij een relatief schemas_dir-pad (zoals de CLI standaard
    gebruikt, --schemas-dir schemas) brak de file://-resolutie van interne
    $ref's zoals '_extracted_value.schema.json'."""
    cwd = os.getcwd()
    try:
        os.chdir(PROJECT_ROOT)
        errors = extract_batch._validate_against_schema(
            make_extracted_value(value="1998", confidence=0.9, requires_human_review=False, source_confidence="high"),
            "schemas", "_extracted_value.schema.json",
        )
        assert errors == []
    finally:
        os.chdir(cwd)


def test_validate_record_flags_missing_top_level_key():
    """Regressie: een model dat 'observations' helemaal weglaat (i.p.v. een
    lege array) moet een schemafout opleveren, niet stilzwijgend 0 observaties
    worden (dat gebeurde echt bij een van de batch-1-documenten)."""
    record = make_valid_record()
    del record["observations"]
    errors = extract_batch.validate_record(record, SCHEMAS_DIR)
    assert any("observations" in e for e in errors)


def test_review_floor_flags_low_confidence():
    node = make_extracted_value(value="1998", confidence=0.3, requires_human_review=False, source_confidence="high")
    extract_batch.enforce_review_floor(node)
    assert node["requires_human_review"] is True


def test_review_floor_flags_low_source_confidence():
    node = make_extracted_value(value="1998", confidence=0.95, requires_human_review=False, source_confidence="low")
    extract_batch.enforce_review_floor(node)
    assert node["requires_human_review"] is True


def test_review_floor_flags_conflict():
    node = make_extracted_value(value="1998", confidence=0.95, requires_human_review=False, source_confidence="high", conflict=True)
    extract_batch.enforce_review_floor(node)
    assert node["requires_human_review"] is True


def test_review_floor_leaves_high_confidence_alone():
    node = make_extracted_value(value="1998", confidence=0.95, requires_human_review=False, source_confidence="high")
    extract_batch.enforce_review_floor(node)
    assert node["requires_human_review"] is False


def test_review_floor_bubbles_through_unit_cost_to_action():
    action = {
        "action_id": "act-1",
        "element_id": "el-1",
        "unit_cost": {
            "value": "125.50",
            "is_estimated": False,
            # unit_cost/provenance hebben zelf geen requires_human_review-veld
            "provenance": {"document_id": "DOC-TEST", "source_confidence": "low"},
        },
        "requires_human_review": False,
    }
    extract_batch.enforce_review_floor(action)
    assert action["requires_human_review"] is True


# ---------------------------------------------------------------------------
# strip_normalization
# ---------------------------------------------------------------------------

def test_strip_normalization_forces_null_even_if_model_guessed():
    record = {
        "elements": [
            {"element_type": {"original_value": "gevel", "normalized_value": "facade"}}
        ]
    }
    extract_batch.strip_normalization(record)
    assert record["elements"][0]["element_type"]["normalized_value"] is None
    assert record["elements"][0]["element_type"]["original_value"] == "gevel"


# ---------------------------------------------------------------------------
# canonicalize_ids
# ---------------------------------------------------------------------------

def test_canonicalize_ids_rewrites_cross_references():
    record = make_valid_record()
    extract_batch.canonicalize_ids(record, "DOC-042")

    element = record["elements"][0]
    assert element["element_id"] == "DOC-042-EL-001"
    assert element["building_id"] == "DOC-042-BLD-001"

    observation = record["observations"][0]
    assert observation["observation_id"] == "DOC-042-OBS-001"
    assert observation["element_id"] == "DOC-042-EL-001"  # herschreven vanaf lokale 'el-1'

    action = record["maintenance_actions"][0]
    assert action["action_id"] == "DOC-042-ACT-001"
    assert action["element_id"] == "DOC-042-EL-001"

    assert record["building"]["building_id"] == "DOC-042-BLD-001"
    assert record["building"]["document_ids"] == ["DOC-042"]


# ---------------------------------------------------------------------------
# extract_document (met gestubde model_fn - geen echte API-call)
# ---------------------------------------------------------------------------

def _doc_meta():
    return {"document_id": "DOC-042", "relative_path": "does/not/exist.pdf", "file_type": "pdf"}


def test_extract_document_never_calls_model_when_source_file_missing(monkeypatch, tmp_path):
    calls = []

    def stub_model(document_text, vocab_context, doc_id, retry_error=None):
        calls.append(1)
        return make_valid_record()

    record = extract_batch.extract_document(
        _doc_meta(), raw_dir=str(tmp_path), vocab_dir=VOCAB_DIR, schemas_dir=SCHEMAS_DIR,
        model_fn=stub_model, doc_id="DOC-042", batch="batch_1",
    )

    assert calls == []  # geen brontekst -> geen modelaanroep, geen kosten
    assert record["status"] == "extraction_failed"
    assert record["requires_human_review"] is True
    assert record["elements"] == []


def test_extract_document_success_on_first_attempt(monkeypatch):
    monkeypatch.setattr(extract_batch, "build_document_text", lambda doc_meta, raw_dir: "PAGINA 1: gevel 100 m2")
    calls = []

    def stub_model(document_text, vocab_context, doc_id, retry_error=None):
        calls.append(retry_error)
        return make_valid_record()

    record = extract_batch.extract_document(
        _doc_meta(), raw_dir="unused", vocab_dir=VOCAB_DIR, schemas_dir=SCHEMAS_DIR,
        model_fn=stub_model, doc_id="DOC-042", batch="batch_1",
    )

    assert len(calls) == 1
    assert record["status"] == "extracted"
    assert record["document_id"] == "DOC-042"
    assert record["extraction_model"]
    assert record["extraction_prompt_version"] == extract_batch.PROMPT_VERSION
    assert "extracted_at" in record
    # de deterministische ondergrens moet de lage source_confidence op de
    # unit_cost van de maintenance_action naar boven hebben gebubbeld
    assert record["maintenance_actions"][0]["requires_human_review"] is True


def test_extract_document_retries_once_on_schema_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(extract_batch, "build_document_text", lambda doc_meta, raw_dir: "PAGINA 1: gevel 100 m2")
    calls = []

    def stub_model(document_text, vocab_context, doc_id, retry_error=None):
        calls.append(retry_error)
        if len(calls) == 1:
            broken = make_valid_record()
            broken["building"]["construction_year"]["bogus_extra_field"] = "niet toegestaan"
            return broken
        return make_valid_record()

    record = extract_batch.extract_document(
        _doc_meta(), raw_dir="unused", vocab_dir=VOCAB_DIR, schemas_dir=SCHEMAS_DIR,
        model_fn=stub_model, doc_id="DOC-042", batch="batch_1",
    )

    assert len(calls) == 2
    assert calls[0] is None
    assert calls[1] is not None  # de foutmelding van de eerste poging werd teruggekoppeld
    assert record["status"] == "extracted"


def test_extract_document_fails_after_one_retry_without_fabricating_data(monkeypatch):
    monkeypatch.setattr(extract_batch, "build_document_text", lambda doc_meta, raw_dir: "PAGINA 1: gevel 100 m2")
    calls = []

    def stub_model(document_text, vocab_context, doc_id, retry_error=None):
        calls.append(retry_error)
        broken = make_valid_record()
        broken["building"]["construction_year"]["bogus_extra_field"] = "niet toegestaan"
        return broken

    record = extract_batch.extract_document(
        _doc_meta(), raw_dir="unused", vocab_dir=VOCAB_DIR, schemas_dir=SCHEMAS_DIR,
        model_fn=stub_model, doc_id="DOC-042", batch="batch_1",
    )

    assert len(calls) == 2  # 1 poging + max 1 herhaling, nooit meer
    assert record["status"] == "extraction_failed"
    assert record["requires_human_review"] is True
    assert record["building"] is None
    assert record["elements"] == []
    assert record["observations"] == []
    assert record["maintenance_actions"] == []


def test_extract_document_never_mutates_model_return_value(monkeypatch):
    """model_fn geeft 1 keer hetzelfde dict-object terug bij een retry-scenario
    (zoals een simpele stub/cache zou doen) - extract_document mag dat object
    niet in-place aanpassen, anders lekt canonicalisatie/normalisatie terug
    in wat de aanroeper als 'origineel modelantwoord' beschouwt."""
    monkeypatch.setattr(extract_batch, "build_document_text", lambda doc_meta, raw_dir: "tekst")
    shared_valid = make_valid_record()
    original_snapshot = copy.deepcopy(shared_valid)

    def stub_model(document_text, vocab_context, doc_id, retry_error=None):
        return shared_valid

    extract_batch.extract_document(
        _doc_meta(), raw_dir="unused", vocab_dir=VOCAB_DIR, schemas_dir=SCHEMAS_DIR,
        model_fn=stub_model, doc_id="DOC-042", batch="batch_1",
    )

    assert shared_valid == original_snapshot
