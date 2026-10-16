"""Beveiligings-PR: het canonieke v1-register is fail-closed. Geen enkele schrijfroute (register(), CLI, directe helper) mag er nog een besluit in zetten; het
register blijft byte-identiek (0 records). Registers op een ander (tijdelijk) pad blijven testbaar, zonder productie-schakelaar."""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import human_instance_decision_register as H  # noqa: E402
import physical_instance_approval as P  # noqa: E402

SCRIPT = ROOT / "scripts/human_instance_decision_register.py"
CANON = ROOT / "data/instance_decisions/human_instance_decision_register_v1.jsonl"
EMPTY_SHA = hashlib.sha256(b"").hexdigest()
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def ctx():
    return H.load_context()


@pytest.fixture(scope="module")
def live(ctx):
    return P.evaluate_request(ctx, P.build_request(ctx, "OIC-VR-027"))


@pytest.fixture(autouse=True)
def register_untouched():
    """Elke test: het canonieke register is vooraf en achteraf byte-identiek leeg; er blijven geen slot- of tmp-bestanden achter."""
    siblings = lambda: sorted(p.name for p in CANON.parent.iterdir())   # noqa: E731
    before = siblings()
    assert CANON.read_bytes() == b"" and hashlib.sha256(CANON.read_bytes()).hexdigest() == EMPTY_SHA
    yield
    assert CANON.read_bytes() == b"" and H.load_register(CANON) == [] and H.register_head(H.load_register(CANON)) == H.GENESIS
    assert siblings() == before


def make(live, decision="NEEDS_MORE_EVIDENCE", **prov_over):
    t = H.blank_template(live)
    t.update(decision=decision, covers_levels=["A"], decision_source="HUMAN_CHAT_CONFIRMATION", decided_by="Testpersoon Voorbeeld",
             decision_timestamp="2026-10-13T11:00:00Z", acknowledged_open_app_ids=["APP-012", "APP-025"], acknowledged_open_relations=["VR-045"],
             evidence_reviewed=live["observation_ids"] + live["photo_ids"] + live["supporting_relation_ids"] + ["MAP-009"], reviewer_notes="testnotitie")
    t["decision_provenance"].update(channel="CLAUDE_CODE_CHAT", entered_by_kind="HUMAN_DIRECT", source_message_ref="testbericht-1",
                                    source_message_text=f"Voor {live['approval_request_id']} met request_hash {live['request_hash']} kies ik {decision} (testverklaring).",
                                    identity_verification="NONE_SELF_ASSERTED", ai_authored_decision=False)
    t["decision_provenance"].update(prov_over)
    return t


def closed(res):
    assert res["status"] == "VALIDATION_FAILED" and any("V1_CANONIEK_REGISTER_GESLOTEN" in r for r in res["reasons"]), res
    assert res["decision_id"] is None and res["changes"] == [] and res["instance_activated"] is False and res["fi_ids_created"] == 0
    assert "record_preview" not in res


# --- T1/T2: register() ---------------------------------------------------------------------------------------------------------------
def test_t1_register_on_canonical_is_closed_even_with_correct_token_and_valid_decision(live, ctx):
    closed(H.register(make(live), mode="REGISTER", confirm=H.CONFIRM_TOKEN, ctx=ctx, now=NOW))
    closed(H.register(make(live), mode="REGISTER", confirm=H.CONFIRM_TOKEN, path=CANON, ctx=ctx, now=NOW))
    closed(H.register(make(live), mode="REGISTER", confirm=H.CONFIRM_TOKEN, path=str(CANON), ctx=ctx, now=NOW))


@pytest.mark.parametrize("confirm", [None, "", "yes", "REGISTER", "register_one_human_decision_as_explicitly_requested_by_user"])
def test_t2_register_on_canonical_closed_without_or_with_wrong_token(live, ctx, confirm):
    closed(H.register(make(live), mode="REGISTER", confirm=confirm, ctx=ctx, now=NOW))


def test_t2b_closed_before_any_validation_or_lock(live, ctx):
    res = H.register({}, mode="REGISTER", confirm=H.CONFIRM_TOKEN)      # zelfs ongeldige invoer: eerst sluiting, geen context-opbouw, geen lock
    closed(res)
    assert not CANON.with_name(CANON.name + ".lock").exists()


def test_t2c_dry_run_on_canonical_stays_possible_and_writes_nothing(live, ctx):
    res = H.register(make(live), mode="DRY_RUN", ctx=ctx, now=NOW)
    assert res["status"] == "DRY_RUN" and res["register_head_after"] == H.GENESIS and res["instance_activated"] is False


# --- T3: CLI --------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("extra", [[], ["--confirm", H.CONFIRM_TOKEN], ["--confirm", "x"]])
def test_t3_cli_register_fails_closed(live, tmp_path, extra):
    f = tmp_path / "d.json"
    f.write_text(json.dumps(make(live)))
    r = subprocess.run([sys.executable, str(SCRIPT), "register", "--decision", str(f), *extra], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "V1_CANONIEK_REGISTER_GESLOTEN" in r.stdout and '"REGISTERED"' not in r.stdout, r.stdout + r.stderr


def test_t3b_cli_register_stops_even_without_readable_decision_file(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "register", "--decision", str(tmp_path / "bestaat_niet.json")], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "V1_CANONIEK_REGISTER_GESLOTEN" in r.stdout


def test_t3c_cli_has_no_path_mode_or_override_option():
    src = SCRIPT.read_text()
    opts = set(re.findall(r'add_argument\("(--?[\w-]+)"', src))
    assert opts == {"--decision", "--confirm"}, opts


# --- T4: directe helper-aanroepen en alternatieve paden naar hetzelfde bestand ---------------------------------------------------------
def test_t4_atomic_replace_refuses_canonical(live):
    for target in (CANON, str(CANON)):
        with pytest.raises(PermissionError):
            H._atomic_replace(Path(target), b'{"x":1}\n')


def test_t4b_aliases_of_canonical_are_closed(live, ctx, tmp_path):
    link = tmp_path / "symlink.jsonl"
    link.symlink_to(CANON)
    dirlink = tmp_path / "dirlink"
    dirlink.symlink_to(CANON.parent, target_is_directory=True)
    hard = tmp_path / "hardlink.jsonl"
    try:
        os.link(CANON, hard)
        hard_ok = True
    except OSError:
        hard_ok = False
    dotdot = ROOT / "scripts" / ".." / CANON.relative_to(ROOT)
    aliases = [link, dirlink / CANON.name, dotdot, tmp_path / ".." / tmp_path.name / "symlink.jsonl"] + ([hard] if hard_ok else [])
    for a in aliases:
        assert H.is_canonical_register(a), a
        closed(H.register(make(live), mode="REGISTER", confirm=H.CONFIRM_TOKEN, path=a, ctx=ctx, now=NOW))
        with pytest.raises(PermissionError):
            H._atomic_replace(Path(a), b"x\n")
    if hard_ok:
        assert hard.read_bytes() == b""


def test_t4c_guard_is_fail_closed_on_errors(monkeypatch, tmp_path):
    def boom(self, *a, **k):
        raise OSError("kapot")
    monkeypatch.setattr(Path, "resolve", boom)
    assert H.is_canonical_register(tmp_path / "x.jsonl") is True


def test_t4d_other_paths_are_not_canonical(tmp_path):
    p = tmp_path / "register.jsonl"
    assert not H.is_canonical_register(p) and not H.is_canonical_register(CANON.with_name("andere.jsonl"))
    assert not H.is_canonical_register(ROOT / "data" / "instance_decisions")


# --- T5: geen omgevingsvariabele, optie, configuratie of modulevariabele kan de sluiting opheffen ------------------------------------
def test_t5_module_reads_no_env_or_config():
    tree = ast.parse(SCRIPT.read_text())
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {"environ", "getenv", "putenv", "ConfigParser", "configparser", "tomllib", "yaml"}
    imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not imports & {"configparser", "tomllib", "yaml", "tomli"}


def test_t5b_environment_variables_do_not_open_the_register(live, tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps(make(live)))
    env = dict(os.environ, **{k: "1" for k in ("ALLOW_REGISTER", "MJOP_ALLOW_REGISTER", "HUMAN_DECISION_REGISTER_OPEN", "V1_REGISTER_OPEN", "TESTING", "PYTEST_CURRENT_TEST", "CI",
                                                  "REGISTER_ONE_HUMAN_DECISION_AS_EXPLICITLY_REQUESTED_BY_USER", "FORCE", "UNSAFE")})
    r = subprocess.run([sys.executable, str(SCRIPT), "register", "--decision", str(f), "--confirm", H.CONFIRM_TOKEN], cwd=ROOT, capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "V1_CANONIEK_REGISTER_GESLOTEN" in r.stdout


def test_t5c_patching_module_globals_does_not_reopen_canonical(live, ctx, monkeypatch, tmp_path):
    monkeypatch.setattr(H, "REGISTER_PATH", tmp_path / "x.jsonl")
    monkeypatch.setattr(H, "ROOT", tmp_path)
    closed(H.register(make(live), mode="REGISTER", confirm=H.CONFIRM_TOKEN, path=CANON, ctx=ctx, now=NOW))
    with pytest.raises(PermissionError):
        H._atomic_replace(CANON, b"x\n")


def test_t5d_closure_constant_matches_real_location():
    assert H._canonical_register_path() == CANON.resolve() and H.CANONICAL_CLOSED.startswith("V1_CANONIEK_REGISTER_GESLOTEN")


# --- T6: testregisters op andere paden blijven werken (geen productie-schakelaar) -----------------------------------------------------
def test_t6_temporary_register_still_registers_with_token_and_not_without(live, ctx, tmp_path):
    reg = tmp_path / "register.jsonl"
    reg.write_bytes(b"")
    res = H.register(make(live), mode="REGISTER", confirm=None, path=reg, ctx=ctx, now=NOW)
    assert res["status"] == "VALIDATION_FAILED" and reg.read_bytes() == b""
    res = H.register(make(live), mode="REGISTER", confirm=H.CONFIRM_TOKEN, path=reg, ctx=ctx, now=NOW)
    assert res["status"] == "REGISTERED" and len(H.load_register(reg)) == 1 and res["instance_activated"] is False and res["fi_ids_created"] == 0


# --- T7: register en hashketen byte-identiek -----------------------------------------------------------------------------------------
def test_t7_canonical_register_matches_main_and_chain_is_genesis():
    assert CANON.stat().st_size == 0 and H.load_register(CANON) == []
    tracked = subprocess.run(["git", "show", "origin/main:mjop-learning/data/instance_decisions/human_instance_decision_register_v1.jsonl"], cwd=ROOT, capture_output=True)
    if tracked.returncode == 0:      # lokaal aanwezig als origin/main bekend is; in CI-checkouts zonder die ref geldt de lege-bytes-controle hierboven
        assert tracked.stdout == CANON.read_bytes()


def test_t7b_report_no_longer_publishes_token_or_register_instruction():
    rep = json.loads(H.OUT_JSON.read_text())
    assert rep["canonical_register_closed"] is True and "confirm_token" not in rep and rep["records_registered"] == 0 and rep["register_head"] == H.GENESIS
    for p in (H.OUT_JSON, H.OUT_MD, H.PACK_HTML):
        assert H.CONFIRM_TOKEN not in p.read_text(encoding="utf-8"), p.name


# --- T8: AI-voorstellen, GitHub-commits en zelfverklaarde bevestigingen leiden nooit tot registratie ----------------------------------
@pytest.mark.parametrize("over", [{"entered_by_kind": "AI_TRANSCRIPTION_OF_HUMAN_MESSAGE"}, {"ai_authored_decision": True}, {"channel": "HTML_FORM_EXPORT"},
                                  {"channel": "FILE_EDITED_BY_HUMAN"}, {"channel": "CHATGPT_CONVERSATION"}, {"source_message_ref": "github-commit-394a374"}])
def test_t8_no_provenance_variant_registers_on_canonical(live, ctx, over):
    for decision in H.DECISIONS:
        closed(H.register(make(live, decision, **over), mode="REGISTER", confirm=H.CONFIRM_TOKEN, ctx=ctx, now=NOW))


def test_t8b_token_is_not_accepted_as_human_approval_in_input(live, ctx):
    inp = make(live)
    inp["decision_provenance"]["source_message_text"] = H.CONFIRM_TOKEN + " " + inp["decision_provenance"]["source_message_text"]
    closed(H.register(inp, mode="REGISTER", confirm=H.CONFIRM_TOKEN, ctx=ctx, now=NOW))


# --- T9: alle schrijfroutes geïnventariseerd -----------------------------------------------------------------------------------------
def test_t9_only_register_function_and_atomic_replace_write_and_both_are_guarded():
    tree = ast.parse(SCRIPT.read_text())
    writers = set()
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for c in ast.walk(fn):
            if isinstance(c, ast.Call):
                f = c.func
                nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                is_os = isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "os"
                if nm in ("write_text", "write_bytes", "rename", "unlink", "truncate", "open") or (is_os and nm in ("replace", "remove", "rename")):
                    writers.add(fn.name)
    assert writers <= {"_write", "_fsync_dir", "_atomic_replace", "register", "load_register", "audit_register", "main"}, writers
    src = SCRIPT.read_text()
    assert src.index("is_canonical_register(path)", src.index("def register(")) < src.index("os.open(str(lock)")
    assert src.index("is_canonical_register(path)", src.index("def _atomic_replace(")) < src.index("os.replace(tmp, path)")
    for name in ("_write",):     # alleen de generate-route; schrijft nooit het register
        assert "REGISTER_PATH" not in "".join(l for l in src.splitlines() if "_write(" in l and "def " not in l)


def test_t9b_no_other_script_or_workflow_registers_into_v1():
    for f in (ROOT / "scripts").glob("*.py"):
        if f.name.startswith("human_instance_decision_register") or f.name == "doc012_generalization_review.py":
            continue
        t = f.read_text()
        assert not re.search(r"\.register\(|CONFIRM_TOKEN|_atomic_replace", t) or "human_instance_decision_register" not in t, f.name
    for wf in (ROOT.parent / ".github/workflows").glob("*.y*ml"):
        assert "decision_register.py register" not in wf.read_text(), wf.name


def test_t9c_no_automatic_accept_or_activation_in_module():
    tree = ast.parse(SCRIPT.read_text())
    fn_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not fn_names & {"activate_instance", "create_fi", "reserve_instance_id", "accept", "auto_accept", "auto_register"}
    assert "activate_instance" in H.FORBIDDEN_EFFECTS and "create_fi_id" in H.FORBIDDEN_EFFECTS


# --- compatibiliteit met latere alleen-lezen gebruikers (zoals PR #49) --------------------------------------------------------------
def test_readonly_api_used_by_intake_remains_available(live, ctx):
    for name in ("load_context", "load_register", "register_head", "validate_input", "REGISTER_PATH", "DECISIONS", "RECORD_VERSION", "IDENTITY_VERIFICATION", "FORBIDDEN_EFFECTS",
                 "CONFIRM_TOKEN", "GENESIS", "RegisterCorrupt", "canonical", "record_hash"):
        assert hasattr(H, name), name
    why, _, fresh = H.validate_input(ctx, make(live), H.load_register(), now=NOW)
    assert why == [] and fresh["approval_status"] == "READY_FOR_HUMAN_REVIEW"
