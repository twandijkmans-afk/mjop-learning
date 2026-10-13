"""v1-registratie is GESLOTEN voor het canonieke register (T1-T9 + adversariële uitbreidingen).

REGEL (niet terugdraaien om 'toch even' te registreren): registreren in v1 kan niet veilig, want v1 kent alleen zelf opgegeven herkomst (NONE_SELF_ASSERTED).
Heropenen kan uitsluitend via een toekomstig v2-schrijfpad met geverifieerd menselijk bewijs. Geen enkele test hier registreert een echt besluit: de canonieke
registerfile blijft 0 bytes; schrijfmechaniek wordt alleen op TIJDELIJKE bestanden getest, zonder enige schakelaar."""
import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import human_instance_decision_register as H  # noqa: E402
import physical_instance_approval as P  # noqa: E402

SCRIPT = ROOT / "scripts" / "human_instance_decision_register.py"
CANON = ROOT / "data" / "instance_decisions" / "human_instance_decision_register_v1.jsonl"
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
EMPTY_SHA = hashlib.sha256(b"").hexdigest()
# Gouden waarden, vastgesteld op origin/main (2851b01) vóór deze wijziging: de hashketen-/validatielogica is byte-identiek gebleven.
GOLDEN = {"record_hash": "bf042039d4e609d76daadfc41868f34bc6f53147a1895b7c830574afdea28f10",
          "canonical_sha": "08c59de0df4b462aa39ed7838530a36d37cf457f07e4a6522f0c88e67e37fa78", "genesis": "0" * 64}
TOKEN = H.CONFIRM_TOKEN


@pytest.fixture(scope="module")
def ctx():
    return H.load_context()


@pytest.fixture(scope="module")
def live(ctx):
    return P.evaluate_request(ctx, P.build_request(ctx, "OIC-VR-027"))


@pytest.fixture(autouse=True)
def canonical_untouched():
    """Elke test in dit bestand: het canonieke register is vooraf en achteraf byte-identiek, zonder lock- of tmp-bestanden in de map."""
    before = (CANON.read_bytes(), sorted(os.listdir(CANON.parent)))
    yield
    assert (CANON.read_bytes(), sorted(os.listdir(CANON.parent))) == before
    assert CANON.read_bytes() == b""


def make(live, decision="NEEDS_MORE_EVIDENCE", **over):
    t = H.blank_template(live)
    t.update(decision=decision, covers_levels=["A"], decision_source="HUMAN_CHAT_CONFIRMATION", decided_by="Testpersoon Voorbeeld",
             decision_timestamp="2026-10-13T11:00:00Z", acknowledged_open_app_ids=["APP-012", "APP-025"], acknowledged_open_relations=["VR-045"],
             evidence_reviewed=live["observation_ids"] + live["photo_ids"] + live["supporting_relation_ids"] + ["MAP-009"], reviewer_notes="testnotitie")
    t["decision_provenance"].update(channel="CLAUDE_CODE_CHAT", entered_by_kind="HUMAN_DIRECT", source_message_ref="testbericht-1",
                                    source_message_text=f"Voor {live['approval_request_id']} met request_hash {live['request_hash']} kies ik {decision} (testverklaring).",
                                    identity_verification="NONE_SELF_ASSERTED", ai_authored_decision=False)
    t.update(over)
    return t


def closed(res):
    return res["status"] == "VALIDATION_FAILED" and any("V1_REGISTRATIE_GESLOTEN" in r for r in res["reasons"]) and res["decision_id"] is None


# --- T1: register() op het canonieke pad ----------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("confirm", [None, "", "yes", TOKEN, TOKEN.lower(), TOKEN + " "])
def test_t1_register_on_canonical_path_is_closed_with_any_token(live, ctx, confirm):
    assert closed(H.register(make(live), mode="REGISTER", confirm=confirm, path=H.REGISTER_PATH, ctx=ctx, now=NOW))


def test_t1_default_path_argument_is_the_canonical_register_and_closed(live, ctx):
    assert closed(H.register(make(live), mode="REGISTER", confirm=TOKEN, ctx=ctx, now=NOW))


@pytest.mark.parametrize("decision", list(H.DECISIONS))
def test_t1_all_three_valid_decisions_are_closed(live, ctx, decision):
    assert closed(H.register(make(live, decision), mode="REGISTER", confirm=TOKEN, path=CANON, ctx=ctx, now=NOW))


def test_t1_dry_run_on_canonical_still_works_and_writes_nothing(live, ctx):
    res = H.register(make(live), mode="DRY_RUN", path=CANON, ctx=ctx, now=NOW)
    assert res["status"] == "DRY_RUN" and res["register_head_before"] == GOLDEN["genesis"] and res["register_head_after"] == GOLDEN["genesis"]


# --- alle spellingen/aliassen van het canonieke pad -------------------------------------------------------------------------------------------------------
def test_t1_every_alias_of_the_canonical_path_is_closed(live, ctx, tmp_path, monkeypatch):
    aliases = [str(CANON), CANON.parent / ".." / CANON.parent.name / CANON.name, str(CANON).replace("human_instance", "HUMAN_INSTANCE"),
               os.path.relpath(CANON, Path.cwd())]
    link = tmp_path / "alias.jsonl"
    link.symlink_to(CANON)
    aliases.append(link)
    dirlink = tmp_path / "dirlink"
    dirlink.symlink_to(CANON.parent, target_is_directory=True)
    aliases.append(dirlink / CANON.name)
    chain = tmp_path / "chain.jsonl"
    chain.symlink_to(link)
    aliases.append(chain)
    hard = tmp_path / "hard.jsonl"
    try:
        os.link(CANON, hard)
        aliases.append(hard)
    except OSError:
        pass                                    # hardlink over bestandssystemen kan niet; de overige aliassen blijven
    for a in aliases:
        assert closed(H.register(make(live), mode="REGISTER", confirm=TOKEN, path=a, ctx=ctx, now=NOW)), a
    monkeypatch.chdir(CANON.parent)
    assert closed(H.register(make(live), mode="REGISTER", confirm=TOKEN, path=CANON.name, ctx=ctx, now=NOW))


@pytest.mark.parametrize("bad", [None, 0, 1.5, b"x", object(), [], {}])
def test_t1_unassessable_path_is_failclosed(live, ctx, bad):
    res = H.register(make(live), mode="REGISTER", confirm=TOKEN, path=bad, ctx=ctx, now=NOW)
    assert res["status"] == "VALIDATION_FAILED" and res["decision_id"] is None


def test_t1_closure_does_not_depend_on_patchable_module_globals(live, ctx, tmp_path, monkeypatch):
    monkeypatch.setattr(H, "REGISTER_PATH", tmp_path / "elders.jsonl")
    monkeypatch.setattr(H, "ROOT", tmp_path)
    assert closed(H.register(make(live), mode="REGISTER", confirm=TOKEN, path=CANON, ctx=ctx, now=NOW))


# --- T2: CLI -----------------------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("extra", [[], ["--confirm", TOKEN], ["--confirm", ""]])
def test_t2_cli_register_is_closed_and_does_not_even_read_the_decision_file(tmp_path, extra):
    f = tmp_path / "bestaat_niet.json"
    r = subprocess.run([sys.executable, str(SCRIPT), "register", "--decision", str(f)] + extra, cwd=ROOT, capture_output=True, text=True)
    out = json.loads(r.stdout)
    assert r.returncode == 2 and "V1_REGISTRATIE_GESLOTEN" in out["reasons"][0] and out["register_written"] is False and not f.exists()


def test_t2_cli_has_no_option_that_selects_another_path_or_opens_registration():
    r = subprocess.run([sys.executable, str(SCRIPT), "register", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert "--path" not in r.stdout and "--force" not in r.stdout and "--enable" not in r.stdout and TOKEN not in r.stdout + r.stderr
    r = subprocess.run([sys.executable, str(SCRIPT), "register", "--decision", "x", "--path", str(CANON)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2 and "unrecognized" in r.stderr.lower()      # onbekende optie wordt geweigerd; er is niets geschreven


def test_t2_cli_check_still_a_dry_run(live, tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps(make(live)))
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--decision", str(f)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and '"status": "DRY_RUN"' in r.stdout


# --- T3: token nergens als bewijs of uitnodiging gepubliceerd ----------------------------------------------------------------------------------------
def test_t3_token_value_is_not_published_in_reports_docs_schemas_or_data():
    hits = []
    for d in ("reports", "docs", "schemas", "data", "config"):
        for dp, _, files in os.walk(ROOT / d):
            for f in files:
                p = Path(dp, f)
                try:
                    if TOKEN in p.read_text(encoding="utf-8", errors="ignore"):
                        hits.append(str(p.relative_to(ROOT)))
                except OSError:
                    pass
    assert hits == []


def test_t3_generated_report_states_closure_and_has_no_token_fields():
    rep = json.loads((ROOT / "reports/frames/human_instance_decision_register_v1.json").read_text())
    assert "confirm_token" not in rep and "confirm_token_required_for_register" not in rep
    assert rep["registration_status"] == H.REGISTRATION_STATUS == "CLOSED_NO_VERIFIED_HUMAN_CHANNEL" and "V1_REGISTRATIE_GESLOTEN" in rep["registration_closed_reason"]
    assert rep["decision_state"]["registration_status"] == H.REGISTRATION_STATUS and rep["records_registered"] == 0
    md = (ROOT / "reports/frames/human_instance_decision_register_v1.md").read_text()
    assert "Registratie is gesloten" in md and "--confirm" not in md
    assert H.build_report()["registration_status"] == H.REGISTRATION_STATUS


def test_t3_token_never_changes_any_outcome_on_the_canonical_register(live, ctx):
    a = H.register(make(live), mode="REGISTER", confirm=TOKEN, path=CANON, ctx=ctx, now=NOW)
    b = H.register(make(live), mode="REGISTER", confirm=None, path=CANON, ctx=ctx, now=NOW)
    assert a["reasons"] == b["reasons"] and closed(a) and closed(b)


# --- T4: directe helper-aanroepen ---------------------------------------------------------------------------------------------------------------------------
def test_t4_atomic_replace_refuses_the_canonical_register_and_all_its_aliases(tmp_path):
    link = tmp_path / "l.jsonl"
    link.symlink_to(CANON)
    for target in (CANON, str(CANON), link):
        with pytest.raises(H.RegistrationClosed):
            H._atomic_replace(target, b'{"x":1}\n')
    assert not [p for p in CANON.parent.iterdir() if p.name != CANON.name]


def test_t4_write_helper_for_reports_refuses_the_canonical_register():
    with pytest.raises(H.RegistrationClosed):
        H._write(CANON, "x")


def test_t4_build_stored_record_is_pure_and_cannot_write(live):
    rec = H.build_stored_record(make(live), [])
    assert rec["record_hash"] == GOLDEN["record_hash"] and CANON.read_bytes() == b""


# --- T5: niets dat een AI kan instellen schakelt dit uit -----------------------------------------------------------------------------------------------
ENV_GUESSES = ["MJOP_ALLOW_V1_REGISTER", "MJOP_REGISTER_ENABLED", "MJOP_REGISTRATION_OPEN", "REGISTRATION_STATUS", "ALLOW_REGISTER", "FORCE", "DEBUG", "TESTING", "CI",
               "GITHUB_ACTIONS", "PYTEST_CURRENT_TEST", "REGISTER_ONE_HUMAN_DECISION_AS_EXPLICITLY_REQUESTED_BY_USER", "CONFIRM_TOKEN", "HUMAN_APPROVED", "I_AM_HUMAN"]


def test_t5_environment_variables_cannot_open_registration(live, ctx, monkeypatch):
    for k in ENV_GUESSES:
        monkeypatch.setenv(k, "1")
        monkeypatch.setenv(k, TOKEN)
    assert closed(H.register(make(live), mode="REGISTER", confirm=TOKEN, path=CANON, ctx=ctx, now=NOW))
    env = {**os.environ, **{k: "1" for k in ENV_GUESSES}}
    r = subprocess.run([sys.executable, str(SCRIPT), "register", "--decision", "x", "--confirm", TOKEN], cwd=ROOT, capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "V1_REGISTRATIE_GESLOTEN" in r.stdout


def test_t5_config_files_next_to_cwd_cannot_open_registration(live, ctx, tmp_path, monkeypatch):
    for name in ("register.json", "config.json", "settings.json", ".env", "pytest.ini", "conftest.py", "human_instance_decision_register.json"):
        (tmp_path / name).write_text('{"registration": "OPEN", "allow": true}')
    monkeypatch.chdir(tmp_path)
    assert closed(H.register(make(live), mode="REGISTER", confirm=TOKEN, path=CANON, ctx=ctx, now=NOW))


def test_t5_module_namespace_and_source_have_no_switch_env_or_config_reads():
    names = [n for n in dir(H) if any(w in n.upper() for w in ("ENABLE", "ALLOW", "OVERRIDE", "BYPASS", "FORCE", "UNSAFE", "LEGACY", "TESTING"))]
    assert names == []
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    attrs = {(ast.unparse(n.value), n.attr) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert ("os", "environ") not in attrs and ("os", "getenv") not in attrs and ("os", "putenv") not in attrs
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not imported & {"configparser", "tomllib", "yaml", "dotenv"}


def test_t5_patching_registration_status_or_token_does_not_open(live, ctx, monkeypatch):
    monkeypatch.setattr(H, "REGISTRATION_STATUS", "OPEN")
    monkeypatch.setattr(H, "CONFIRM_TOKEN", "x")
    assert closed(H.register(make(live), mode="REGISTER", confirm="x", path=CANON, ctx=ctx, now=NOW))


# --- T6: register en hashketen ongewijzigd ------------------------------------------------------------------------------------------------------------------
def test_t6_canonical_register_is_empty_with_genesis_head_and_equals_git_head():
    assert CANON.read_bytes() == b"" and hashlib.sha256(CANON.read_bytes()).hexdigest() == EMPTY_SHA
    recs = H.load_register(CANON)
    assert recs == [] and H.register_head(recs) == GOLDEN["genesis"]
    r = subprocess.run(["git", "show", "HEAD:mjop-learning/data/instance_decisions/human_instance_decision_register_v1.jsonl"], cwd=ROOT, capture_output=True)
    if r.returncode == 0:
        assert r.stdout == b""
    st = subprocess.run(["git", "status", "--porcelain", "--", str(CANON)], cwd=ROOT, capture_output=True, text=True)
    assert st.stdout.strip() == ""


# --- T7: schrijfroutes in de code ---------------------------------------------------------------------------------------------------------------------------
WRITE_ATTRS = {"write", "write_text", "write_bytes", "replace", "rename", "unlink", "remove", "rmdir", "mkdir", "makedirs", "rmtree", "copy", "copy2", "copyfile", "move", "touch",
               "truncate", "symlink", "link", "chmod"}


def _enclosing(tree):
    out = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                name = n.func.attr if isinstance(n.func, ast.Attribute) else (n.func.id if isinstance(n.func, ast.Name) else None)
                if name == "replace" and not (isinstance(n.func, ast.Attribute) and ast.unparse(n.func.value) in ("os", "shutil")):
                    continue                    # str.replace is geen schrijfactie
                if name in WRITE_ATTRS or (name == "open" and any(isinstance(a, ast.Constant) and isinstance(a.value, str) and set(a.value) & set("wax+") for a in n.args + [k.value for k in n.keywords])):
                    out.setdefault(fn.name, set()).add(name)
    return out


def test_t7_only_known_functions_write_and_each_is_guarded_or_a_tempfile_helper():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    enc = _enclosing(tree)
    assert set(enc) <= {"_atomic_replace", "register", "_write", "_fsync_dir"}, enc
    src = SCRIPT.read_text(encoding="utf-8")
    body = {n.name: ast.get_source_segment(src, n) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_refuse_canonical(path)" in body["_atomic_replace"] and body["_atomic_replace"].index("_refuse_canonical(path)") < body["_atomic_replace"].index("open(")
    assert "_refuse_canonical(p)" in body["_write"] and body["_write"].index("_refuse_canonical(p)") < body["_write"].index("write_text")
    reg = body["register"]
    assert reg.index("_targets_canonical(path)") < reg.index("os.open(") < reg.index("_atomic_replace(")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_atomic_replace"]
    owners = {fn.name for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) for c in ast.walk(fn) if c in calls}
    assert owners == {"register"}


def test_t7_no_other_python_file_in_scripts_or_agent_touches_the_canonical_register_for_writing():
    allowed = {"human_instance_decision_register.py", "human_decision_intake.py"}      # tweede: alleen-lezen (PR intake; eigen AST-bewaking)
    needles = ("human_instance_decision_register_v1.jsonl", "REGISTER_PATH", "instance_decisions", "_atomic_replace", "build_stored_record")
    offenders = []
    for base in ("scripts", "agent"):
        for p in (ROOT / base).rglob("*.py"):
            if p.name in allowed or "__pycache__" in p.parts:
                continue
            t = p.read_text(encoding="utf-8")
            if any(n in t for n in needles):
                offenders.append(str(p.relative_to(ROOT)))
    assert offenders == [], offenders


def test_t7_no_workflow_or_script_calls_the_register_subcommand_or_passes_the_token():
    wf = ROOT.parent / ".github" / "workflows"
    for p in list(wf.glob("*.yml")) + list((ROOT / "scripts").glob("*.sh")):
        t = p.read_text(encoding="utf-8")
        assert TOKEN not in t and "decision_register.py register" not in t and "decision_register.py\" register" not in t, p.name


# --- T8: labels in audit/decision_state --------------------------------------------------------------------------------------------------------------------
def test_t8_audit_and_state_never_present_v1_as_human_authenticated(live, ctx, tmp_path):
    reg = tmp_path / "tijdelijk.jsonl"
    reg.write_bytes(b"")
    res = H.register(make(live), mode="REGISTER", confirm=TOKEN, path=reg, ctx=ctx, now=NOW)      # mechaniek op een TIJDELIJK bestand
    assert res["status"] == "REGISTERED"
    audit = H.audit_register(ctx, reg, now=NOW)
    assert audit and all(a["verification_scope"] == "V1_TECHNICAL_SELF_ASSERTED" and a["human_authenticated"] is False and a["instance_activated"] is False for a in audit)
    st = H.decision_state(ctx, "OIC-VR-027", reg)
    assert st["registration_status"] == H.REGISTRATION_STATUS and st["step_4_instance_activated"] is False and st["level_B"] == st["level_C"] == "NOT_DECIDED"


# --- T9: gedrag van het bestaande register is byte-identiek -------------------------------------------------------------------------------------------------
def test_t9_validation_hashes_and_chain_are_identical_to_origin_main(live, ctx):
    why, _, _ = H.validate_input(ctx, make(live), [], now=NOW)
    assert why == []
    rec = H.build_stored_record(make(live), [])
    assert rec["record_hash"] == GOLDEN["record_hash"] and hashlib.sha256(H.canonical(rec).encode()).hexdigest() == GOLDEN["canonical_sha"]
    assert H.register_head([rec]) == GOLDEN["record_hash"] and rec["decision_id"] == "HID-0001" and rec["sequence"] == 1 and rec["previous_record_hash"] == GOLDEN["genesis"]


def test_t9_temp_registers_still_work_without_any_switch_and_chain_stays_valid(live, ctx, tmp_path):
    reg = tmp_path / "tijdelijk.jsonl"
    reg.write_bytes(b"")
    first = H.register(make(live), mode="REGISTER", confirm=TOKEN, path=reg, ctx=ctx, now=NOW)
    assert first["status"] == "REGISTERED" and first["register_head_after"] == GOLDEN["record_hash"]
    assert H.register(make(live), mode="REGISTER", confirm=TOKEN, path=reg, ctx=ctx, now=NOW)["status"] == "VALIDATION_FAILED"       # duplicaat blijft geweigerd
    assert [r["record_hash"] for r in H.load_register(reg)] == [GOLDEN["record_hash"]]


def test_t9_tampered_temp_register_is_still_detected(live, ctx, tmp_path):
    reg = tmp_path / "t.jsonl"
    reg.write_bytes(b"")
    H.register(make(live), mode="REGISTER", confirm=TOKEN, path=reg, ctx=ctx, now=NOW)
    reg.write_bytes(reg.read_bytes().replace(b"NEEDS_MORE_EVIDENCE", b"APPROVE_PHYSICAL_IDENTITY"))
    with pytest.raises(H.RegisterCorrupt):
        H.load_register(reg)


# --- compatibiliteit met de alleen-lezen intake (PR #49) -----------------------------------------------------------------------------------------------
def test_compat_read_only_api_used_by_the_dry_run_intake_is_unchanged():
    api = {"load_context", "load_register", "register_head", "validate_input", "REGISTER_PATH", "DECISIONS", "RECORD_VERSION", "IDENTITY_VERIFICATION", "FORBIDDEN_EFFECTS",
           "RegisterCorrupt", "canonical", "record_hash", "NON_HUMAN_NAME", "GENESIS", "P", "ROOT", "decision_id_for", "REGISTER_VERSION", "CONFIRM_TOKEN"}
    assert api <= set(dir(H))
    assert H.REGISTER_PATH == CANON and H.RECORD_VERSION == 1 and H.REGISTER_VERSION == "human_instance_decision_register_v1"


# --- acceptatie: AI-voorstellen, commits en zelfverklaringen veroorzaken geen registratie ------------------------------------------------------
@pytest.mark.parametrize("over", [
    {"decision_provenance": None},      # wordt hieronder ingevuld
])
def test_ai_proposals_commits_and_self_declared_confirmations_cannot_register(live, ctx, over):
    variants = []
    base = make(live)
    variants.append(base)                                                                                                       # formeel perfect, zelf opgegeven "mens"
    ai = make(live)
    ai["decision_provenance"].update(entered_by_kind="AI_TRANSCRIPTION_OF_HUMAN_MESSAGE", source_message_ref="claude-session")
    variants.append(ai)
    commit = make(live)
    commit["decision_provenance"].update(channel="FILE_EDITED_BY_HUMAN", source_message_ref="git-commit-abc1234")
    variants.append(commit)
    selfdecl = make(live, decided_by="De eigenaar (bevestigd in chat)")
    variants.append(selfdecl)
    for v in variants:
        assert closed(H.register(v, mode="REGISTER", confirm=TOKEN, path=CANON, ctx=ctx, now=NOW))
