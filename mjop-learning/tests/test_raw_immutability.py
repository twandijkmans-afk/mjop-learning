"""
Test: data/raw/ mag nooit stilzwijgend veranderen (CLAUDE.md: 'originele
bestanden nooit overschrijven'). We vergelijken elke sha256 in data/raw/
tegen reports/raw_manifest.json, dat is vastgelegd op het moment dat de
batch-1-documenten zijn gekopieerd.
"""
import hashlib
import json
import os

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "reports", "raw_manifest.json")


def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


@pytest.fixture(scope="module")
def manifest():
    if not os.path.exists(MANIFEST_PATH):
        pytest.skip("reports/raw_manifest.json ontbreekt nog")
    return json.load(open(MANIFEST_PATH))


def test_manifest_not_empty(manifest):
    assert len(manifest) > 0, "raw_manifest.json bevat geen bestanden"


def test_all_manifest_files_unchanged(manifest):
    changed = []
    for rel_path, meta in manifest.items():
        full_path = os.path.join(RAW_DIR, rel_path)
        if not os.path.exists(full_path):
            changed.append((rel_path, "ONTBREEKT"))
            continue
        actual_hash = _sha256(full_path)
        if actual_hash != meta["sha256"]:
            changed.append((rel_path, "GEWIJZIGD"))
    assert not changed, f"Deze raw-bestanden zijn aangepast of verdwenen: {changed}"


def test_no_untracked_files_silently_added():
    """Nieuwe bestanden mogen wel worden toegevoegd (nieuwe batch), maar dan
    hoort raw_manifest.json opnieuw gegenereerd te worden - dit signaleert
    het verschil zodat het niet onopgemerkt blijft."""
    manifest = json.load(open(MANIFEST_PATH)) if os.path.exists(MANIFEST_PATH) else {}
    on_disk = set()
    for root, _, files in os.walk(RAW_DIR):
        for fn in files:
            if fn.lower() == "thumbs.db":
                continue
            on_disk.add(os.path.relpath(os.path.join(root, fn), RAW_DIR))
    untracked = on_disk - set(manifest.keys())
    if untracked:
        pytest.skip(
            f"Nieuwe bestanden in data/raw/ die nog niet in het manifest staan "
            f"(waarschijnlijk een nieuwe batch): {untracked}. Genereer een nieuw "
            f"manifest, overschrijf het oude niet zonder review."
        )
