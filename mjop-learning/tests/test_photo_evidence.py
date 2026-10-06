import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_photo_evidence as bpe  # noqa: E402


def test_three_photos_with_hashes():
    doc = bpe.build()
    assert [p["photo_id"] for p in doc["photos"]] == ["maldenhof_1", "maldenhof_2", "maldenhof_3"]
    assert all(len(p["sha256"]) == 64 for p in doc["photos"])


def test_observations_are_never_confirmed_and_have_no_quantities():
    doc = bpe.build()
    bpe.validate(doc)
    assert doc["observations"]
    assert all(o["confirmed"] is False and o["requires_human_review"] for o in doc["observations"])
    assert {o["status"] for o in doc["observations"]} <= {"REVIEW_REQUIRED", "REPEAT_CANDIDATE"}
    assert set(doc["quantity_concepts_status"].values()) == {"UNKNOWN"}


def test_download_jpg_removed_and_was_maldenhof_3():
    doc = bpe.build()
    rec = doc["removed_duplicates"][0]
    maldenhof_3 = next(p for p in doc["photos"] if p["photo_id"] == "maldenhof_3")
    assert rec["sha256"] == maldenhof_3["sha256"]
    assert not os.path.exists(os.path.join(ROOT, "data", "download.jpg"))


def test_committed_output_is_current():
    with open(bpe.OUT_JSON, encoding="utf-8") as f:
        assert json.load(f) == bpe.build()
