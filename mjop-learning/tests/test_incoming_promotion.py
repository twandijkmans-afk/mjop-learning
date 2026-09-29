"""
End-to-end tests voor de incoming batch promotion v1 (scripts/promote_incoming_batch.py):

    upload -> incoming batch (extractie via fake xpdf) -> dry-run -> goedkeuring -> promotie op een
    tijdelijke kopie -> canonieke controles -> rollback

Alles gebeurt in een tijdelijke kopie van het project; het echte repo wordt alleen gelezen
(gecontroleerd met hashes).
"""
import copy
import glob
import hashlib
import json
import os
import shutil
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tests", "fixtures"))

import build_comparability as bc  # noqa: E402
import build_kengetallen as bk  # noqa: E402
import document_registry as dr  # noqa: E402
import process_incoming_batch as pib  # noqa: E402
import promote_canonical_batch1 as pcb  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402
from minimal_pdf import make_pdf  # noqa: E402

RAW = os.path.join(PROJECT_ROOT, "data", "raw")
DOC010 = os.path.join(RAW, "zomerdijkstraat-14", "Meerjarenonderhoudsplan 2023_VvE Zomerdijkstraat 14.pdf")
DOC003 = os.path.join(RAW, "jp-heijestraat", "2026_Overzicht 15 - Jarenplan (Gedetailleerd)_VvE 9690.xls")
FIXTURE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "pdftotext_doc010", "pages.json")
FAKE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "fake_pdftotext.py")
XPDF = "pdftotext version 4.06 [www.xpdfreader.com]"


def _repo_hashes():
    out = pl.tracked_hashes(PROJECT_ROOT)
    for extra in ("data/incoming_registry.json", "data/price_observations/document_relations.json"):
        out[extra] = pl.sha256_file(os.path.join(PROJECT_ROOT, extra))
    for p in glob.glob(os.path.join(PROJECT_ROOT, "data", "incoming_batches", "**", "*"), recursive=True):
        if os.path.isfile(p):
            out[p] = pl.sha256_file(p)
    return out


@pytest.fixture(scope="module", autouse=True)
def real_repo_unchanged():
    before = _repo_hashes()
    yield
    assert _repo_hashes() == before, "het echte repo is gewijzigd"


@pytest.fixture(scope="module")
def fake_xpdf(tmp_path_factory):
    d = tmp_path_factory.mktemp("bin")
    b = d / "pdftotext"
    b.write_text(f'#!/bin/sh\nFAKE_PDFTOTEXT_VERSION="{XPDF}" exec "{sys.executable}" "{FAKE}" "$@"\n')
    b.chmod(0o755)
    old = os.environ.get("FAKE_PDFTOTEXT_PAGES")
    os.environ["FAKE_PDFTOTEXT_PAGES"] = FIXTURE
    yield str(b)
    if old is None:
        os.environ.pop("FAKE_PDFTOTEXT_PAGES", None)
    else:
        os.environ["FAKE_PDFTOTEXT_PAGES"] = old


def make_project(dst):
    for rel in pr.SIMULATION_COPY:
        s, d = os.path.join(PROJECT_ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return dst


def upload(root):
    inc = os.path.join(root, "data", "incoming")
    os.makedirs(os.path.join(inc, "gebouw-x"))
    shutil.copyfile(DOC010, os.path.join(inc, "gebouw-x", "nieuw plan.pdf"))       # nieuw document (andere bytes)
    with open(os.path.join(inc, "gebouw-x", "nieuw plan.pdf"), "ab") as f:
        f.write(b"%e2e-test\n")
    shutil.copyfile(DOC010, os.path.join(inc, "kopie.pdf"))                        # exacte duplicate
    shutil.copyfile(DOC003, os.path.join(inc, "export.xls"))                       # spreadsheet
    with open(os.path.join(inc, "export.xls"), "ab") as f:
        f.write(b"\0")
    with open(os.path.join(inc, "offerte.pdf"), "wb") as f:                        # onbekend sjabloon
        f.write(make_pdf(["Offerte schilderwerk", "Totaal 1.234,00"]))
    with open(os.path.join(inc, "notities.docx"), "wb") as f:                      # niet ondersteund
        f.write(b"PK\x03\x04docx")


def process(root, runner):
    plan = pib.plan_batch(root, None, state_root=root, runner=runner)
    files, _ = pib.build_outputs(plan)
    pib.apply_writes(root, pib.plan_writes(root, files, plan["batch_id"]))
    return plan["batch_id"]


def runner(fake, status="VERIFIED_RUNNER_SETUP"):
    r = pib.runner_info(fake)
    return dict(r, runner_setup_status=status,
                runner_setup={"status": status, "text_layer_platform_variance": ["DOC-007", "DOC-009"]})


@pytest.fixture(scope="module")
def project(tmp_path_factory, fake_xpdf):
    root = make_project(str(tmp_path_factory.mktemp("proj")))
    upload(root)
    batch_id = process(root, runner(fake_xpdf))
    return root, batch_id


def by_input(decisions):
    return {d["input_path"]: d for d in decisions if d["input_path"]}


# ------------------------------------------------------------------ beslissingen

def test_decisions_per_document(project):
    root, bid = project
    batch = pr.load_batch(root, bid)
    d = by_input(pr.decide(root, batch, None))
    assert d["kopie.pdf"]["decision"] == "SKIPPED_DUPLICATE"
    assert d["notities.docx"]["decision"] == "BLOCKED" and "UNSUPPORTED_FORMAT" in d["notities.docx"]["reasons"]
    assert d["offerte.pdf"]["decision"] == "BLOCKED" and "UNKNOWN_TEMPLATE" in d["offerte.pdf"]["reasons"]
    # spreadsheet nu deterministisch geëxtraheerd; relatiekandidaat met DOC-002 vereist menselijke review
    assert d["export.xls"]["decision"] == "REVIEW_REQUIRED"
    assert d["export.xls"]["reasons"] == ["RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION"]
    new = d["gebouw-x/nieuw plan.pdf"]
    assert new["decision"] == "REVIEW_REQUIRED"                       # relatiekandidaat met DOC-010
    assert new["reasons"] == ["RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION"]
    assert {x["decision"] for x in d.values()} <= set(pr.DECISIONS)


def test_unverified_runner_blocks_everything(project):
    root, bid = project
    batch = pr.load_batch(root, bid)
    batch["manifest"] = copy.deepcopy(batch["manifest"])
    batch["manifest"]["runner"]["runner_setup_status"] = "UNVERIFIED_RUNNER_SETUP"
    d = by_input(pr.decide(root, batch, {"approved_document_ids": ["DOC-011"], "review_acknowledgements": {
        "DOC-011": ["RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION"]}}))
    assert d["gebouw-x/nieuw plan.pdf"]["decision"] == "BLOCKED"
    assert d["gebouw-x/nieuw plan.pdf"]["reasons"][0].startswith("RUNNER_NOT_VERIFIED")


def test_review_required_needs_exact_acknowledgement(project):
    root, bid = project
    batch = pr.load_batch(root, bid)
    did = by_input(pr.decide(root, batch, None))["gebouw-x/nieuw plan.pdf"]["document_id"]
    no_ack = by_input(pr.decide(root, batch, {"approved_document_ids": [did], "review_acknowledgements": {}}))
    assert no_ack["gebouw-x/nieuw plan.pdf"]["decision"] == "REVIEW_REQUIRED"
    ok = by_input(pr.decide(root, batch, {"approved_document_ids": [did], "review_acknowledgements": {
        did: ["RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION"]}}))
    assert ok["gebouw-x/nieuw plan.pdf"]["decision"] == "APPROVED_FOR_PROMOTION"


def test_approval_of_blocked_document_is_refused(project):
    root, bid = project
    batch = pr.load_batch(root, bid)
    dec = pr.decide(root, batch, {"approved_document_ids": ["DOC-012"], "review_acknowledgements": {}})
    assert any(x["reasons"] == ["APPROVAL_FOR_NON_ELIGIBLE_DOCUMENT"] for x in dec)


# ------------------------------------------------------------------ dry-run

def test_dry_run_simulates_and_writes_nothing_canonical(project):
    root, bid = project
    before = pl.tracked_hashes(root)
    n_before = len(json.load(open(os.path.join(root, pr.PO_PATH), encoding="utf-8"))["observations"])
    report = pr.dry_run(root, bid)
    assert pl.tracked_hashes(root) == before
    sim = report["simulation"]
    assert report["preflight_blockers"] == [] and report["canonical_checks_after_simulation"] == []
    assert sim["price_observations"]["before"] == n_before and sim["price_observations"]["added"] > 0
    assert sim["kengetallen"]["before"] == sim["kengetallen"]["after"] and sim["kengetallen"]["content_changed"] is False
    assert sim["comparability_impact"]["new_pairs_have_human_decisions"] == 0
    assert sim["comparability_impact"]["new_pairs_between_documents_with_open_relation_candidate"] >= 0
    assert report["needs_review"] and report["possible_duplicates_and_relations"]
    assert set(report["decisions"]) == set(pr.DECISIONS)


# ------------------------------------------------------------------ promotie + rollback

@pytest.fixture(scope="module")
def promoted(project):
    root, bid = project
    pre = pl.tracked_hashes(root)
    with pytest.raises(pr.PromotionError, match="approval"):
        pr.promote(root, bid, now="2026-09-29T12:00:00Z")
    assert pl.tracked_hashes(root) == pre
    pr.approve(root, bid, "twandijkmans", include_review=[], now="2026-09-29T11:00:00Z")
    with pytest.raises(pr.PromotionError, match="APPROVED_FOR_PROMOTION"):     # alleen EXTRACTED: hier geen
        pr.promote(root, bid, now="2026-09-29T12:00:00Z")
    did = next(d["document_id"] for d in pr.load_batch(root, bid)["documents"]
               if d["input_path"] == "gebouw-x/nieuw plan.pdf")
    pr.approve(root, bid, "twandijkmans", include_review=[did], now="2026-09-29T11:30:00Z")
    old_po = json.load(open(os.path.join(root, pr.PO_PATH), encoding="utf-8"))["observations"]
    old_kg = json.load(open(os.path.join(root, pr.KG_PATH), encoding="utf-8"))
    rel_before = pl.sha256_file(os.path.join(root, "data", "price_observations", "document_relations.json"))
    store_before = pl.sha256_file(os.path.join(root, pr.DECISIONS_PATH))
    states_before = pl.states(root)                                    # eerdere promoties (bijv. Testbatch 01)
    state = pr.promote(root, bid, now="2026-09-29T12:00:00Z")
    return {"root": root, "bid": bid, "did": did, "pre": pre, "state": state, "old_po": old_po, "old_kg": old_kg,
            "rel_before": rel_before, "store_before": store_before, "states_before": states_before}


def test_promotion_state_and_canonical_checks(promoted):
    root, st = promoted["root"], promoted["state"]
    assert st["status"] == "PROMOTED" and st["approval"]["reviewer"] == "twandijkmans"
    assert [d["document_id"] for d in st["summary"]["promoted_documents"]] == [promoted["did"]]
    assert pl.chain_errors(root) == [] and pr.verify(root) == [] and pcb.verify(root) == []
    assert pib.check(root) == [] and pr.canonical_errors(root) == [] and pr.canonical_after_errors(root) == []


def test_new_document_is_canonical_and_existing_data_unchanged(promoted):
    root, did = promoted["root"], promoted["did"]
    reg = dr.load_registry(os.path.join(root, pr.REGISTRY))
    entry = dr.by_id(reg)[did]
    assert entry["relative_path"] == f"incoming/{did}/nieuw plan.pdf"
    assert pl.sha256_file(os.path.join(root, "data", "raw", *entry["relative_path"].split("/"))) == entry["sha256"]
    _, rep = dr.reconcile(reg, os.path.join(root, "data", "raw"))
    assert rep["new"] == rep["missing"] == rep["modified"] == []
    for layer in ("extracted", "normalized", "verified"):
        assert os.path.isfile(os.path.join(root, "data", layer, f"{did}.json"))
    po = json.load(open(os.path.join(root, pr.PO_PATH), encoding="utf-8"))
    n = len(promoted["old_po"])
    assert po["observations"][:n] == promoted["old_po"]                            # bestaand: byte-gelijk
    assert {o["document_id"] for o in po["observations"][n:]} == {did}
    kg = json.load(open(os.path.join(root, pr.KG_PATH), encoding="utf-8"))
    assert kg["kengetallen"] == promoted["old_kg"]["kengetallen"] and kg["summary"] == promoted["old_kg"]["summary"]
    assert kg["supersedes"] and os.path.isfile(os.path.join(root, kg["supersedes"]["file"]))
    assert pl.sha256_file(os.path.join(root, pr.DECISIONS_PATH)) == promoted["store_before"]
    assert pl.sha256_file(os.path.join(root, "data", "price_observations", "document_relations.json")) == \
        promoted["rel_before"]                                                     # relaties nooit stil bevestigd
    rp = json.load(open(os.path.join(root, pr.RELATION_PROPOSALS), encoding="utf-8"))
    assert rp["proposals"] and all(p["status"] == "PROPOSAL_REQUIRES_HUMAN_CONFIRMATION" for p in rp["proposals"])
    comp = json.load(open(os.path.join(root, pr.COMP_PATH), encoding="utf-8"))
    assert f"SC-{did}" in [c["source_cluster"] for c in comp["source_clusters"]]


def test_inventory_matches_fresh_regeneration(promoted, tmp_path):
    import inventory_documents as inv
    root = promoted["root"]
    records = inv.build_inventory(os.path.join(root, "data", "raw"), os.path.join(root, pr.REGISTRY))
    assert records == json.load(open(os.path.join(root, pr.INVENTORY_JSON)))


def test_same_batch_cannot_be_promoted_twice(promoted):
    with pytest.raises(pr.PromotionError):
        pr.promote(promoted["root"], promoted["bid"], now="2026-09-29T13:00:00Z")


def test_rollback_restores_exact_pre_state_and_keeps_history(promoted):
    root = promoted["root"]
    with pytest.raises(pr.PromotionError):
        pr.rollback(root, "ANDERE-BATCH")
    hist = os.path.join(root, promoted["state"]["history"])
    assert pr.rollback(root, promoted["bid"]).startswith("ROLLBACK OK")
    assert pl.tracked_hashes(root) == promoted["pre"]
    assert os.path.isfile(os.path.join(hist, "rolled_back_state.json"))          # geen delete zonder history
    assert pl.states(root) == promoted["states_before"] and pcb.verify(root) == [] and pl.chain_errors(root) == []
    assert not os.path.exists(os.path.join(root, "data", "raw", "incoming", promoted["did"]))


# ------------------------------------------------------------------ fouten tijdens promotie

@pytest.fixture
def approved_project(tmp_path, fake_xpdf):
    root = make_project(str(tmp_path / "p"))
    upload(root)
    bid = process(root, runner(fake_xpdf))
    did = next(d["document_id"] for d in pr.load_batch(root, bid)["documents"]
               if d["input_path"] == "gebouw-x/nieuw plan.pdf")
    pr.approve(root, bid, "twandijkmans", include_review=[did], now="2026-09-29T11:00:00Z")
    return root, bid


def test_failure_mid_promotion_restores_everything(approved_project, monkeypatch):
    root, bid = approved_project
    pre, states_before = pl.tracked_hashes(root), pl.states(root)
    monkeypatch.setattr(bc, "build", lambda r: (_ for _ in ()).throw(RuntimeError("gesimuleerde fout")))
    with pytest.raises(RuntimeError):
        pr.promote(root, bid, now="2026-09-29T12:00:00Z")
    assert pl.tracked_hashes(root) == pre and pl.states(root) == states_before
    assert glob.glob(os.path.join(root, pl.HISTORY_ROOT, "*", "failed_attempt.json"))


def test_kengetal_change_without_decisions_is_hard_failure(approved_project, monkeypatch):
    root, bid = approved_project
    pre = pl.tracked_hashes(root)
    real = bk.build

    def changed(r, generated_at=None):
        out = real(r, generated_at=generated_at)
        out["kengetallen"][0]["value_display"] = "99.99"
        return out
    monkeypatch.setattr(bk, "build", changed)
    with pytest.raises(pr.PromotionError, match="kengetallen"):
        pr.promote(root, bid, now="2026-09-29T12:00:00Z")
    assert pl.tracked_hashes(root) == pre


def test_approval_bound_to_manifest(approved_project):
    root, bid = approved_project
    path = os.path.join(root, pib.BATCHES_DIR, bid, "approval.json")
    a = json.load(open(path, encoding="utf-8"))
    a["manifest_sha256"] = "0" * 64
    json.dump(a, open(path, "w", encoding="utf-8"))
    with pytest.raises(pr.PromotionError, match="manifest"):
        pr.promote(root, bid, now="2026-09-29T12:00:00Z")


def test_explicit_exclusion_keeps_document_review_required(approved_project):
    root, bid = approved_project
    docs = by_input(pr.decide(root, pr.load_batch(root, bid), None))
    did, xls = docs["gebouw-x/nieuw plan.pdf"]["document_id"], docs["export.xls"]["document_id"]
    with pytest.raises(pr.PromotionError, match="tegelijk"):
        pr.approve(root, bid, "twandijkmans", include_review=[did], exclude=[did])
    with pytest.raises(pr.PromotionError, match="horen niet bij"):
        pr.approve(root, bid, "twandijkmans", include_review=[did], exclude=["DOC-999"])
    a = pr.approve(root, bid, "twandijkmans", include_review=[did], exclude=[xls], exclude_reason="relatiereview",
                   now="2026-09-29T11:45:00Z")
    assert a["excluded_document_ids"] == [xls] and a["exclusion_reason"] == "relatiereview"
    assert xls not in a["approved_document_ids"]
    d = by_input(pr.decide(root, pr.load_batch(root, bid), a))
    assert d["export.xls"]["decision"] == "REVIEW_REQUIRED" and d["export.xls"]["reasons"][0] == "EXCLUDED_BY_REVIEWER"
    assert d["gebouw-x/nieuw plan.pdf"]["decision"] == "APPROVED_FOR_PROMOTION"
    report = pr.dry_run(root, bid)                                     # met approval: exact die goedkeuring
    assert report["simulation"]["price_observations"]["added"] > 0


def test_dry_run_documents_only_for_eligible_documents_without_approval(tmp_path, fake_xpdf):
    root = make_project(str(tmp_path / "p"))
    upload(root)
    bid = process(root, runner(fake_xpdf))
    did = by_input(pr.decide(root, pr.load_batch(root, bid), None))["gebouw-x/nieuw plan.pdf"]["document_id"]
    with pytest.raises(pr.PromotionError, match="niet promoveerbaar"):
        pr.dry_run(root, bid, documents=[did])                         # REVIEW_REQUIRED nooit via --documents
    pr.approve(root, bid, "twandijkmans", include_review=[did], now="2026-09-29T11:00:00Z")
    with pytest.raises(pr.PromotionError, match="zonder approval"):
        pr.dry_run(root, bid, documents=[did])                         # met approval: alleen exact die simuleren


def test_cli_check_on_real_repository():
    assert pr.main(["--check"]) == 0
