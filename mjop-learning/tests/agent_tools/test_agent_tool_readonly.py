"""Alleen-lezen: statische controle van het agent-pakket, dynamische sandbox rond echte aanroepen, en
ongewijzigde bronhashes (data/, reports/, schemas/, vocabularies/, config/, docs/) vóór en na uitvoering."""
import ast
import os

import pytest

import support  # noqa: F401
from support import FIXTURE_ROOT, PROJECT_ROOT, SandboxViolation, manifest, read_only_sandbox

import promotion_ledger as pl
from agent import call_tool
from agent.tools.get_kengetal_candidates import get_kengetal_candidates

AGENT_DIR = os.path.join(PROJECT_ROOT, "agent")

# Alleen deze bestaande scripts mogen door het agent-pakket worden geïmporteerd (alleen-lezen API's).
ALLOWED_SCRIPT_IMPORTS = {"human_match_review", "match_kengetal", "mjop_kengetal_workflow"}
# Alleen deze standaardbibliotheekmodules (en jsonschema) mogen worden geïmporteerd.
ALLOWED_STDLIB = {"copy", "json", "os", "sys", "jsonschema"}
FORBIDDEN_NAMES = {"eval", "exec", "compile", "__import__"}
WRITE_ATTRS = {"write", "writelines", "write_text", "write_bytes", "replace", "rename", "remove", "unlink", "rmdir",
               "mkdir", "makedirs", "rmtree", "copy2", "copyfile", "copytree", "move", "dump", "system", "popen",
               "Popen", "run", "check_call", "check_output", "urlopen", "urlretrieve", "connect", "touch", "chmod"}


def agent_files():
    out = []
    for d, _, files in os.walk(AGENT_DIR):
        out += [os.path.join(d, f) for f in files if f.endswith(".py")]
    return sorted(out)


def parse(path):
    with open(path, encoding="utf-8") as f:
        return ast.parse(f.read(), filename=path)


def test_agent_package_is_present_and_small():
    names = [os.path.relpath(p, AGENT_DIR) for p in agent_files()]
    assert "contract.py" in names and os.path.join("tools", "get_kengetal_candidates.py") in names
    assert len(names) <= 5, names


def test_static_import_allowlist():
    for path in agent_files():
        for node in ast.walk(parse(path)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [("." * node.level) + (node.module or "")]
            for mod in mods:
                top = mod.split(".")[0]
                if top == "agent" or mod.startswith("."):
                    continue
                assert top in ALLOWED_SCRIPT_IMPORTS | ALLOWED_STDLIB, f"{path}: niet toegestane import {mod}"


def test_static_no_write_network_or_dynamic_code():
    for path in agent_files():
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ALLOWED_SCRIPT_IMPORTS:
                    continue    # de gecontroleerde alleen-lezen script-API's; zie test_static_only_read_functions_...
                assert name not in FORBIDDEN_NAMES, f"{path}:{node.lineno}: {name}()"
                assert name not in WRITE_ATTRS, f"{path}:{node.lineno}: mogelijke schrijf-/proces-/netwerkaanroep {name}()"
                if name == "open":
                    mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else "r"
                    for kw in node.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = kw.value.value
                    assert not any(c in str(mode) for c in "wax+"), f"{path}:{node.lineno}: open(mode={mode!r})"


def test_static_only_read_functions_of_the_scripts_are_used():
    """Het agent-pakket gebruikt uit de bestaande scripts uitsluitend deze (alleen-lezen) functies."""
    allowed = {("human_match_review", "canonical_sha256"), ("human_match_review", "load_json"),
               ("human_match_review", "IntegrityError"), ("match_kengetal", "load_context"),
               ("mjop_kengetal_workflow", "run"), ("mjop_kengetal_workflow", "paths"),
               ("mjop_kengetal_workflow", "WorkflowError")}
    used = set()
    for path in agent_files():
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in ALLOWED_SCRIPT_IMPORTS:
                used.add((node.value.id, node.attr))
            if isinstance(node, ast.ImportFrom) and (node.module or "") in ALLOWED_SCRIPT_IMPORTS:
                used |= {(node.module, a.name) for a in node.names}
    assert used and used <= allowed, sorted(used - allowed)


def test_no_tool_accepts_a_path_parameter():
    from agent import tool_specs

    def names(schema):
        if isinstance(schema, dict):
            for k, v in schema.get("properties", {}).items():
                yield k
                yield from names(v)
    for spec in tool_specs():
        for n in names(spec["input_schema"]):
            assert not any(t in n.lower() for t in ("path", "file", "dir", "root", "url", "out")), n


CASES = [
    dict(object_id="RO-1", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
         material_normalized="pvc", object_description="Hemelwaterafvoer pvc", quantity="100", vat_basis="inclusive"),
    dict(object_id="RO-2", element_code_internal="4645", action_normalized="exterior_painting", unit_normalized="m2",
         material_normalized="concrete", object_description="Buitenschilderwerk betonconstructie plafond"),
    dict(object_id="RO-3", element_code_internal="9999", action_text="vervangen", unit_text="m1"),
    # padachtige tekst is gewoon tekst: wordt nooit als bestand geopend
    dict(object_id="RO-4", element_code_internal="5211", object_description="../../data/raw/../../etc/passwd",
         material_text="/etc/shadow", action_text="vervangen", unit_text="m1"),
]


def test_sandbox_blocks_writes_network_and_processes_when_used_directly():
    import socket
    import subprocess
    with read_only_sandbox():
        with pytest.raises(SandboxViolation):
            open(os.path.join(PROJECT_ROOT, "data", "zzz_probe.txt"), "w")
        with pytest.raises(SandboxViolation):
            os.replace("a", "b")
        with pytest.raises(SandboxViolation):
            os.makedirs(os.path.join(PROJECT_ROOT, "data", "zzz"))
        with pytest.raises(SandboxViolation):
            socket.create_connection(("example.com", 443))
        with pytest.raises(SandboxViolation):
            subprocess.Popen(["true"])
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "data", "zzz_probe.txt"))


@pytest.mark.parametrize("use_root", ["fixture", "live"])
def test_dynamic_sandbox_run_reads_only_the_expected_files_and_leaves_sources_unchanged(use_root):
    root = FIXTURE_ROOT if use_root == "fixture" else PROJECT_ROOT
    kwargs = {"root": root} if use_root == "fixture" else {}
    for case in CASES:          # opwarmen buiten de sandbox: lazy imports van jsonschema e.d.
        get_kengetal_candidates(case, **kwargs)
    before = manifest()
    ledger_before = pl.tracked_hashes(PROJECT_ROOT)
    reads = []
    with read_only_sandbox(reads):
        for case in CASES:
            out = get_kengetal_candidates(case, **kwargs)
            assert out["read_only"] is True
            assert out["price_presentation"]["is_accepted_price"] is False
    assert manifest() == before
    assert pl.tracked_hashes(PROJECT_ROOT) == ledger_before
    # Alleen deze bestanden worden gelezen (symlinks opgelost); niets onder data/raw, extracted, verified, ...
    data_reads = {os.path.relpath(r, os.path.realpath(root)) if r.startswith(os.path.realpath(root) + os.sep)
                  else os.path.basename(r) for r in reads if "/data/" in r or "/schemas/" in r or "/vocabularies/" in r}
    forbidden_layers = ("data/raw", "data/extracted", "data/verified", "data/normalized", "data/comparability")
    assert not [r for r in reads if any(f"/{layer}/" in r for layer in forbidden_layers)], sorted(set(reads))
    names = {os.path.basename(r) for r in reads}
    assert {"kengetallen_batch1.json", "price_observations_batch1_normalized.json",
            "human_match_decision_records.json"} <= names
    assert data_reads    # er is daadwerkelijk gelezen


def test_call_tool_in_sandbox_with_invalid_input_also_touches_nothing():
    get_kengetal_candidates(CASES[0], root=FIXTURE_ROOT)
    before = manifest()
    with read_only_sandbox():
        for bad in ({"object_id": "x", "element_code_internal": "5211", "root": "/"}, {}, None):
            with pytest.raises(Exception):
                call_tool("get_kengetal_candidates", bad)
    assert manifest() == before
