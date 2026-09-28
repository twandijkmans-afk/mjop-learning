"""
inventory_documents.py haalt document-ID's uit het permanente registry
(sha256), niet uit de volgorde van os.walk. Regressie: de oude code kon in een
andere omgeving DOC-002..DOC-007 aan andere bestanden geven.
"""
import json
import os
import shutil
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import document_registry as dr  # noqa: E402
import inventory_documents as inv  # noqa: E402

RAW = os.path.join(PROJECT_ROOT, "data", "raw")
REGISTRY = os.path.join(PROJECT_ROOT, "reports", "document_registry.json")
COMMITTED = os.path.join(PROJECT_ROOT, "reports", "document_inventory.json")


def test_inventory_ids_match_committed_inventory_exactly():
    records = inv.build_inventory(RAW, REGISTRY)
    committed = json.load(open(COMMITTED))
    assert [(r["document_id"], r["relative_path"], r["sha256"]) for r in records] == \
        [(r["document_id"], r["relative_path"], r["sha256"]) for r in committed]


def test_inventory_output_byte_identical_to_committed():
    with tempfile.TemporaryDirectory() as tmp:
        old = sys.argv
        sys.argv = ["inventory_documents.py", "--raw-dir", RAW, "--out-dir", tmp]
        try:
            inv.main()
        finally:
            sys.argv = old
        for name in ("document_inventory.json", "document_inventory.csv"):
            assert open(os.path.join(tmp, name), "rb").read() == \
                open(os.path.join(PROJECT_ROOT, "reports", name), "rb").read(), name


def _copy_env(tmp):
    raw = os.path.join(tmp, "raw")
    shutil.copytree(RAW, raw)
    reg = os.path.join(tmp, "document_registry.json")
    shutil.copy(REGISTRY, reg)
    return raw, reg


def test_new_file_sorting_first_does_not_shift_ids_and_is_not_auto_registered():
    with tempfile.TemporaryDirectory() as tmp:
        raw, reg = _copy_env(tmp)
        os.makedirs(os.path.join(raw, "aaa-nieuw-pand"))
        open(os.path.join(raw, "aaa-nieuw-pand", "nieuw.pdf"), "wb").write(b"%PDF-1.4 nieuw")
        # zonder registratie: inventaris weigert (geen stille import)
        with pytest.raises(dr.RegistryError):
            inv.build_inventory(raw, reg)
        # expliciet registreren: bestaande ID's blijven, nieuw bestand krijgt DOC-011
        registry, report = dr.reconcile(dr.load_registry(reg), raw, register_new=True)
        dr.save_registry(registry, reg)
        assert report["new"] == [{"relative_path": "aaa-nieuw-pand/nieuw.pdf", "document_id": "DOC-011"}]
        committed = {r["relative_path"]: r["document_id"] for r in json.load(open(COMMITTED))}
        ids = {d["relative_path"]: d["document_id"] for d in dr.load_registry(reg)["documents"]}
        for path, doc_id in committed.items():
            assert ids[path] == doc_id


def test_modified_raw_file_blocks_inventory():
    with tempfile.TemporaryDirectory() as tmp:
        raw, reg = _copy_env(tmp)
        target = os.path.join(raw, json.load(open(COMMITTED))[9]["relative_path"])
        with open(target, "ab") as f:
            f.write(b"x")
        with pytest.raises(dr.RegistryError):
            inv.build_inventory(raw, reg)
