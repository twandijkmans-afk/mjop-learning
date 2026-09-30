"""Tests voor scripts/append_only_store.py (gedeelde invarianten voor append-only beslissingsopslag)."""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import append_only_store as aos  # noqa: E402


def rec(i, key="K1", status="ACTIVE", supersedes=None, payload="x"):
    return {"rid": f"R-{i:05d}", "key": key, "status": status, "supersedes": supersedes, "payload": payload}


def errs(records):
    return aos.invariant_errors(records, "rid", lambda r: r["key"])


def test_valid_supersede_chain_has_no_errors():
    assert errs([rec(1, status="SUPERSEDED"), rec(2, supersedes="R-00001")]) == []
    assert errs([]) == []


def test_duplicate_ids_and_multiple_active_are_flagged():
    assert any("meer dan eens" in e for e in errs([rec(1), rec(1, key="K2")]))
    assert any("meer dan één ACTIVE" in e for e in errs([rec(1), rec(2)]))
    assert errs([rec(1, key="K1"), rec(2, key="K2")]) == []


def test_supersedes_rules():
    assert any("onbekende" in e for e in errs([rec(2, supersedes="R-00009")]))
    assert any("dezelfde sleutel" in e for e in errs([rec(1, key="K2", status="SUPERSEDED"), rec(2, supersedes="R-00001")]))
    assert any("dezelfde sleutel" in e for e in errs([rec(1, status="ACTIVE"), rec(2, key="K1", supersedes="R-00001", status="SUPERSEDED")]))
    assert any("precies één later record" in e for e in errs([rec(1, status="SUPERSEDED")]))
    assert any("precies één later record" in e for e in errs([rec(1, status="SUPERSEDED"), rec(2, supersedes="R-00001", status="SUPERSEDED"),
                                                              rec(3, supersedes="R-00001")]))


def test_append_only_detects_removal_overwrite_and_bad_transitions():
    old = [rec(1)]
    assert aos.append_only_errors(old, old + [rec(2, key="K2")], "rid") == []
    assert any("verwijderd" in e for e in aos.append_only_errors(old, [], "rid"))
    changed = copy.deepcopy(old)
    changed[0]["payload"] = "y"
    assert any("overschreven" in e for e in aos.append_only_errors(old, changed, "rid"))
    for start, end, ok in (("ACTIVE", "SUPERSEDED", True), ("ACTIVE", "REVIEW_REQUIRED", True), ("REVIEW_REQUIRED", "SUPERSEDED", True),
                           ("SUPERSEDED", "ACTIVE", False), ("REVIEW_REQUIRED", "ACTIVE", False), ("SUPERSEDED", "REVIEW_REQUIRED", False)):
        new = [rec(1, status=end)]
        out = aos.append_only_errors([rec(1, status=start)], new, "rid")
        assert (out == []) is ok, (start, end, out)


def test_next_id():
    assert aos.next_id([], "rid", "R") == "R-00001"
    assert aos.next_id([rec(1), rec(7)], "rid", "R") == "R-00008"
