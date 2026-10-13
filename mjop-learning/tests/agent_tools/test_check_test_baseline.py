"""check_test_baseline.py: bekende xpdf-omgevingsfouten worden herkend, nieuwe fouten nooit gemaskeerd."""
import json
import os
import subprocess
import sys
from xml.sax.saxutils import quoteattr

import support  # noqa: F401
from support import PROJECT_ROOT

import check_test_baseline as cb

BASELINE = cb.load_baseline(cb.DEFAULT_BASELINE)
KNOWN = BASELINE["known_failures"]
DEP_TEXT = ("scripts/deterministic_extraction.DependencyError: Ongeschikte pdftotext (/usr/bin/pdftotext): "
            "'pdftotext version 24.02.0'; vereist 'pdftotext version 4.06 [www.xpdfreader.com]'. blabla")
PO_TEXT = "RuntimeError: pdftotext faalde voor /x/y.pdf: pdftotext version 24.02.0\nCopyright 2005-2024 The Poppler"


def junit(tmp_path, cases):
    parts = []
    for classname, name, kind, text in cases:
        body = "" if kind is None else f"<{kind} message={quoteattr(text[:80])}>{text}</{kind}>"
        parts.append(f'<testcase classname="{classname}" name="{name}">{body}</testcase>')
    p = tmp_path / "junit.xml"
    p.write_text(f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{"".join(parts)}</testsuite></testsuites>',
                 encoding="utf-8")
    return str(p)


def known_cases(kind="failure"):
    return [("tests.test_deterministic_extraction", "test_doc007_dekkend_actions_link_to_element", kind, DEP_TEXT),
            ("tests.test_price_observations", "test_known_wrap_and_page_break_cases_on_batch1_sources", kind, PO_TEXT),
            ("tests.test_price_observations", "test_full_build_on_batch1_sources", kind, PO_TEXT)]


def run(tmp_path, cases, *flags):
    return cb.main([junit(tmp_path, cases), *flags])


def test_baseline_lists_exactly_the_three_known_xpdf_tests():
    assert len(KNOWN) == 3 and len({k["nodeid"] for k in KNOWN}) == 3
    assert all(k["nodeid"].startswith("tests/") and "::" in k["nodeid"] for k in KNOWN)


def test_only_the_known_failures_without_xpdf_pass(tmp_path, capsys):
    cases = known_cases() + [("tests.test_x", "test_ok", None, "")]
    assert run(tmp_path, cases, "--xpdf-missing") == 0
    assert "KNOWN_ENVIRONMENT: 3" in capsys.readouterr().out


def test_a_new_failure_next_to_the_known_ones_is_never_masked(tmp_path, capsys):
    cases = known_cases() + [("tests.test_agent", "test_new_regression", "failure", "AssertionError: 1 != 2")]
    assert run(tmp_path, cases, "--xpdf-missing") == 1
    out = capsys.readouterr().out
    assert "NEW_FAILURE: 1" in out and "tests/test_agent.py::test_new_regression" in out


def test_a_known_test_failing_for_another_reason_is_a_new_failure(tmp_path):
    cases = known_cases()
    cases[2] = (cases[2][0], cases[2][1], "failure", "AssertionError: price 1 != 2")
    assert run(tmp_path, cases, "--xpdf-missing") == 1


def test_an_error_at_setup_or_collection_is_a_new_failure(tmp_path):
    assert run(tmp_path, [("tests.test_y", "test_setup", "error", "ImportError: kapot")], "--xpdf-missing") == 1


def test_nothing_is_tolerated_when_xpdf_is_available(tmp_path):
    assert run(tmp_path, known_cases(), "--xpdf-available") == 1


def test_passing_baseline_tests_are_fine(tmp_path, capsys):
    cases = [(c, n, None, "") for c, n, _, _ in known_cases()]
    assert run(tmp_path, cases, "--xpdf-available") == 0
    assert "PASSED_BASELINE_TEST: 3" in capsys.readouterr().out


def test_empty_or_broken_report_is_not_a_pass(tmp_path):
    assert cb.main([junit(tmp_path, [])]) == 2
    bad = tmp_path / "bad.xml"
    bad.write_text("<nope", encoding="utf-8")
    assert cb.main([str(bad)]) == 2
    assert cb.main([str(tmp_path / "missing.xml")]) == 2


def test_xpdf_detection_requires_the_exact_pinned_version_line(tmp_path):
    fake = tmp_path / "pdftotext"
    fake.write_text("#!/bin/sh\necho 'pdftotext version 4.06 [www.xpdfreader.com]' >&2\n")
    fake.chmod(0o755)
    rx = BASELINE["requires"]["version_line_regex"]
    assert cb.detect_xpdf(rx, str(fake)) is True
    fake.write_text("#!/bin/sh\necho 'pdftotext version 24.02.0' >&2\n")
    assert cb.detect_xpdf(rx, str(fake)) is False
    assert cb.detect_xpdf(rx, str(tmp_path / "does-not-exist")) is False


def test_cli_exit_code(tmp_path):
    p = junit(tmp_path, known_cases())
    script = os.path.join(PROJECT_ROOT, "scripts", "check_test_baseline.py")
    r = subprocess.run([sys.executable, "-B", script, p, "--xpdf-missing"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
