#!/usr/bin/env python3
"""
check_test_baseline.py - onderscheidt NIEUWE testfouten van de bekende xpdf-omgevingsproblemen.

Gebruik:
    python -m pytest -q --junitxml=junit.xml || true
    python scripts/check_test_baseline.py junit.xml [--baseline config/known_environment_failures.json]
                                                    [--xpdf-available | --xpdf-missing]

Regels (config/known_environment_failures.json):
  - Een falende/errorende test geldt alleen als KNOWN_ENVIRONMENT als (1) xpdf pdftotext 4.06 ontbreekt,
    (2) de test in de baseline staat en (3) de foutmelding de bekende afhankelijkheidsfout bevat.
  - Is xpdf 4.06 wel beschikbaar, dan wordt NIETS getolereerd: elke fout is nieuw.
  - Elke andere fout (ook een collection-error, of een andere fout in een baseline-test) is NEW_FAILURE.
  - Een rapport zonder testgevallen (crash) is een fout (exit 2); een baseline-test die slaagt is gewoon goed.
Exit: 0 geen nieuwe fouten, 1 nieuwe fout(en), 2 onbruikbaar rapport. Alleen lezen; schrijft niets.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BASELINE = os.path.join(ROOT, "config", "known_environment_failures.json")


def load_baseline(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detect_xpdf(version_line_regex, binary=None):
    """True alleen als `pdftotext -v` exact de gepinde xpdf-versieregel geeft."""
    binary = binary or os.environ.get("PDFTOTEXT") or "pdftotext"
    try:
        p = subprocess.run([binary, "-v"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    line = ((p.stderr or "") + (p.stdout or "")).strip().splitlines()
    return bool(line) and re.match(version_line_regex, line[0].strip()) is not None


def nodeid(classname, name):
    return classname.replace(".", "/") + ".py::" + name if classname else name


def parse_junit(path):
    tree = ET.parse(path)
    cases = []
    for tc in tree.getroot().iter("testcase"):
        problem = tc.find("failure")
        if problem is None:
            problem = tc.find("error")
        skipped = tc.find("skipped") is not None
        text = ""
        if problem is not None:
            text = (problem.get("message") or "") + "\n" + (problem.text or "")
        cases.append({"nodeid": nodeid(tc.get("classname", ""), tc.get("name", "")),
                      "failed": problem is not None, "skipped": skipped, "text": text})
    return cases


def classify(cases, baseline, xpdf_available):
    known = {k["nodeid"]: re.compile(k["signature_regex"], re.S) for k in baseline["known_failures"]}
    out = {"KNOWN_ENVIRONMENT": [], "NEW_FAILURE": [], "PASSED_BASELINE_TEST": []}
    for c in cases:
        if not c["failed"]:
            if c["nodeid"] in known and not c["skipped"]:
                out["PASSED_BASELINE_TEST"].append(c["nodeid"])
            continue
        sig = known.get(c["nodeid"])
        if not xpdf_available and sig is not None and sig.search(c["text"]):
            out["KNOWN_ENVIRONMENT"].append(c["nodeid"])
        else:
            out["NEW_FAILURE"].append(c["nodeid"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("junit")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--xpdf-available", action="store_true", help="forceer: xpdf 4.06 is beschikbaar (niets tolereren)")
    g.add_argument("--xpdf-missing", action="store_true", help="forceer: xpdf 4.06 ontbreekt")
    args = ap.parse_args(argv)

    baseline = load_baseline(args.baseline)
    try:
        cases = parse_junit(args.junit)
    except (OSError, ET.ParseError) as e:
        print(f"ONBRUIKBAAR RAPPORT: {e}")
        return 2
    if not cases:
        print("ONBRUIKBAAR RAPPORT: geen testgevallen in het junit-bestand (crash of lege run?)")
        return 2
    if args.xpdf_available:
        xpdf = True
    elif args.xpdf_missing:
        xpdf = False
    else:
        xpdf = detect_xpdf(baseline["requires"]["version_line_regex"])
    result = classify(cases, baseline, xpdf)
    print(f"testgevallen: {len(cases)}; xpdf 4.06 beschikbaar: {xpdf}")
    for key in ("KNOWN_ENVIRONMENT", "PASSED_BASELINE_TEST", "NEW_FAILURE"):
        print(f"{key}: {len(result[key])}")
        for n in result[key]:
            print(f"  - {n}")
    if result["NEW_FAILURE"]:
        print("RESULTAAT: NIEUWE FOUTEN (niet gemaskeerd)")
        return 1
    print("RESULTAAT: geen nieuwe fouten" + (" (alleen bekende xpdf-omgevingsproblemen)" if result["KNOWN_ENVIRONMENT"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
