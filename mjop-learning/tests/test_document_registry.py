"""
Stabiele document-ID's: bestaande ID's verschuiven nooit, nieuwe bestanden
krijgen alleen met expliciete toestemming een nieuw ID.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import json
import os
import shutil
import tempfile

import pytest

import document_registry as dr
import promotion_ledger as pl

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(PROJECT_ROOT, "reports", "document_registry.json")
RAW = os.path.join(PROJECT_ROOT, "data", "raw")


def test_registry_keeps_batch1_ids():
    reg = dr.load_registry(REGISTRY)
    ids = [d["document_id"] for d in reg["documents"]]
    assert ids == [f"DOC-{i:03d}" for i in range(1, 11)] + pl.promoted_document_ids(PROJECT_ROOT)
    by_id = dr.by_id(reg)
    assert by_id["DOC-010"]["relative_path"].startswith("zomerdijkstraat-14/")
    # consistent met de eerdere inventaris
    inv = json.load(open(os.path.join(PROJECT_ROOT, "reports", "document_inventory.json")))
    for d in inv:
        assert by_id[d["document_id"]]["sha256"] == d["sha256"]


def test_registry_matches_raw_files():
    reg = dr.load_registry(REGISTRY)
    _, report = dr.reconcile(reg, RAW, register_new=False)
    assert report["new"] == [] and report["missing"] == [] and report["modified"] == []
    assert sorted(report["unchanged"]) == [f"DOC-{i:03d}" for i in range(1, 11)] + \
        pl.promoted_document_ids(PROJECT_ROOT)


def _mini_env(tmp):
    raw = os.path.join(tmp, "raw")
    os.makedirs(os.path.join(raw, "b-pand"))
    os.makedirs(os.path.join(raw, "d-pand"))
    open(os.path.join(raw, "b-pand", "x.pdf"), "wb").write(b"bbb")
    open(os.path.join(raw, "d-pand", "y.pdf"), "wb").write(b"ddd")
    reg, _ = dr.reconcile({"registry_version": 1, "documents": []}, raw, register_new=True)
    return raw, reg


def test_new_file_sorting_first_does_not_shift_existing_ids():
    with tempfile.TemporaryDirectory() as tmp:
        raw, reg = _mini_env(tmp)
        before = {d["relative_path"]: d["document_id"] for d in reg["documents"]}
        assert before == {"b-pand/x.pdf": "DOC-001", "d-pand/y.pdf": "DOC-002"}
        # nieuw bestand dat alfabetisch VOOR de bestaande komt
        os.makedirs(os.path.join(raw, "a-pand"))
        open(os.path.join(raw, "a-pand", "z.pdf"), "wb").write(b"aaa")
        reg, report = dr.reconcile(reg, raw, register_new=True)
        after = {d["relative_path"]: d["document_id"] for d in reg["documents"]}
        assert after["b-pand/x.pdf"] == "DOC-001"
        assert after["d-pand/y.pdf"] == "DOC-002"
        assert after["a-pand/z.pdf"] == "DOC-003"


def test_new_file_not_registered_without_permission():
    with tempfile.TemporaryDirectory() as tmp:
        raw, reg = _mini_env(tmp)
        open(os.path.join(raw, "b-pand", "nieuw.pdf"), "wb").write(b"nnn")
        reg2, report = dr.reconcile(json.loads(json.dumps(reg)), raw, register_new=False)
        assert report["new"] == [{"relative_path": "b-pand/nieuw.pdf", "document_id": None}]
        assert len(reg2["documents"]) == 2


def test_modified_raw_file_is_an_error():
    with tempfile.TemporaryDirectory() as tmp:
        raw, reg = _mini_env(tmp)
        open(os.path.join(raw, "b-pand", "x.pdf"), "wb").write(b"gewijzigd")
        with pytest.raises(dr.RegistryError):
            dr.reconcile(reg, raw)


def test_ids_never_reused_after_file_removed():
    with tempfile.TemporaryDirectory() as tmp:
        raw, reg = _mini_env(tmp)
        os.remove(os.path.join(raw, "d-pand", "y.pdf"))
        open(os.path.join(raw, "d-pand", "w.pdf"), "wb").write(b"www")
        reg, report = dr.reconcile(reg, raw, register_new=True)
        assert report["missing"] == ["DOC-002"]
        ids = {d["relative_path"]: d["document_id"] for d in reg["documents"]}
        assert ids["d-pand/w.pdf"] == "DOC-003"
        assert ids["d-pand/y.pdf"] == "DOC-002"  # blijft in het register


def test_verify_file_rejects_changed_content():
    with tempfile.TemporaryDirectory() as tmp:
        raw, reg = _mini_env(tmp)
        path, doc = dr.verify_file(reg, "DOC-001", raw)
        assert doc["relative_path"] == "b-pand/x.pdf"
        open(path, "wb").write(b"anders")
        with pytest.raises(dr.RegistryError):
            dr.verify_file(reg, "DOC-001", raw)
