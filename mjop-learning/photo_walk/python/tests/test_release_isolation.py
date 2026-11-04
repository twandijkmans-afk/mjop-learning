"""Afscherming van de ontwikkelinterface (meetdiagnose + ontwikkelbundel) in Release-builds.

Statische controle (draait op Linux, zonder Xcode): de ontwikkelbestanden zijn volledig `#if DEBUG`, elke verwijzing ernaar vanuit de rest van de app staat zelf in een
`#if DEBUG`-gebied, en alleen de Debug-configuratie definieert DEBUG. De CI op macOS bewijst dit aanvullend op het gebouwde Release-binary (zie photo-walk-ios.yml)."""
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "ios" / "App"
SRC = APP / "Sources"
DEV_FILES = ["DiagnosticsView.swift", "DiagnosticsExport.swift", "DevBundleStore.swift"]
# alles waarmee de ontwikkelinterface bereikt of aangeroepen wordt
DEV_SYMBOLS = re.compile(r"\b(DiagnosticsView|DiagnosticsExport|DevBundleStore|CaptureBundle|ExtendedDiagnostics|ladderImages)\b|devBundle|devbundles|exportDiagnostics|diagnosticsLink|meetdiagnose_")


def strip_comment(line):
    return re.sub(r"//.*$", "", line)


def debug_mask(lines):
    """Per regel: True als de regel binnen een `#if DEBUG`-tak staat (de `#else`-tak telt niet mee; samengestelde condities tellen niet als DEBUG)."""
    stack, mask = [], []
    for raw in lines:
        t = raw.strip()
        if t.startswith("#if "):
            stack.append(t == "#if DEBUG")
            mask.append(False)
            continue
        if t.startswith("#elseif") or t == "#else":
            if stack:
                stack[-1] = False
            mask.append(False)
            continue
        if t == "#endif":
            if stack:
                stack.pop()
            mask.append(False)
            continue
        mask.append(bool(stack) and all(stack))
    assert not stack, "onevenwichtige #if/#endif"
    return mask


def swift_files():
    return sorted(p for p in SRC.rglob("*.swift"))


@pytest.mark.parametrize("name", DEV_FILES)
def test_dev_files_are_entirely_inside_if_debug(name):
    lines = (SRC / name).read_text(encoding="utf-8").splitlines()
    mask = debug_mask(lines)
    outside = [(i + 1, l) for i, (l, m) in enumerate(zip(lines, mask)) if not m and l.strip() and not l.strip().startswith(("#if", "#endif", "//"))]
    assert not outside, f"{name}: regels buiten #if DEBUG: {outside[:3]}"
    assert lines[0].strip() == "#if DEBUG" and lines[-1].strip() == "#endif"


def test_no_reference_to_dev_interface_outside_if_debug():
    bad = []
    for p in swift_files():
        if p.name in DEV_FILES:
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        mask = debug_mask(lines)
        for i, (l, m) in enumerate(zip(lines, mask)):
            if DEV_SYMBOLS.search(strip_comment(l)) and not m:
                bad.append(f"{p.relative_to(SRC)}:{i + 1}: {l.strip()[:100]}")
    assert not bad, "verwijzing naar de ontwikkelinterface buiten #if DEBUG:\n" + "\n".join(bad)


def test_the_dev_interface_is_actually_referenced_inside_debug_only():
    """Positieve controle: de test hierboven is niet blind (de twee bekende, afgeschermde aanroepen bestaan)."""
    hits = []
    for p in swift_files():
        if p.name in DEV_FILES:
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        mask = debug_mask(lines)
        hits += [p.name for l, m in zip(lines, mask) if m and DEV_SYMBOLS.search(strip_comment(l))]
    assert "PhotoResultView.swift" in hits and "PhotoWalkApp.swift" in hits, hits


def test_motion_advice_user_feature_stays_available_in_release():
    ma = (SRC / "MotionAdvice.swift").read_text(encoding="utf-8")
    assert "#if" not in ma and "static func needsMotion" in ma
    pr = (SRC / "PhotoResultView.swift").read_text(encoding="utf-8").splitlines()
    mask = debug_mask(pr)
    use = [m for l, m in zip(pr, mask) if "MotionAdvice.needsMotion" in l]
    assert use and not any(use), "het bewegingsadvies voor gebruikers moet buiten #if DEBUG blijven"


def test_only_the_debug_configuration_defines_debug():
    y = (APP / "project.yml").read_text(encoding="utf-8")
    m = re.search(r"configs:\s*\n(?:\s*#[^\n]*\n)*\s*Debug:\s*\n\s+SWIFT_ACTIVE_COMPILATION_CONDITIONS:\s*(\S+)\s*\n\s+Release:\s*\n\s+SWIFT_ACTIVE_COMPILATION_CONDITIONS:\s*(\S+)", y)
    assert m, "project.yml: expliciete compilatievlaggen per configuratie ontbreken"
    assert m.group(1) == "DEBUG" and "DEBUG" not in m.group(2)


def test_no_other_swift_target_compiles_the_dev_interface_into_release():
    """De ontwikkelbestanden horen alleen bij het app-target; geen tweede bron voor Release (bv. in een package)."""
    assert not list((APP.parent / "Sources").rglob("DevBundleStore.swift"))
    assert not list((APP.parent / "Sources").rglob("DiagnosticsView.swift"))


def test_ci_workflow_scans_the_release_binary():
    wf = (Path(__file__).resolve().parents[4] / ".github" / "workflows" / "photo-walk-ios.yml").read_text(encoding="utf-8")
    assert "Release-binary" in wf and "dd-dev" in wf and "DevBundleStore" in wf
