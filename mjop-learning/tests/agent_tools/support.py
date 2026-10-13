"""Hulpfuncties voor de agent-tests: vaste fixture-root, hash-manifest en een dynamische alleen-lezen sandbox."""
import builtins
import contextlib
import hashlib
import io
import os
import pathlib
import shutil
import socket
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import promotion_history as ph  # noqa: E402

# Vaste, alleen-lezen pre-promotie-toestand (C1/C2), zoals tests/test_mjop_kengetal_workflow.py; blijft stabiel
# als de live kengetallen veranderen.
FIXTURE_ROOT = ph.pre_promotion_fixture_root(PROJECT_ROOT)

MANIFEST_DIRS = ("data", "reports", "schemas", "vocabularies", "config", "docs")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest(root=PROJECT_ROOT, dirs=MANIFEST_DIRS):
    """sha256 van elk bestand in de canonieke lagen (en schemas/vocabularies/config/docs/reports)."""
    out = {}
    for d in dirs:
        base = os.path.join(root, d)
        for dirpath, _, files in os.walk(base):
            for name in files:
                p = os.path.join(dirpath, name)
                out[os.path.relpath(p, root)] = sha256_file(p)
    return out


def root_with_store(tmp_path, store):
    """Tijdelijke projectroot: alles verwijst (symlink) naar FIXTURE_ROOT, behalve de beslissingenopslag."""
    import json
    root = tmp_path / "root"
    root.mkdir()
    for name in os.listdir(FIXTURE_ROOT):
        if name != "data":
            os.symlink(os.path.join(FIXTURE_ROOT, name), root / name)
    (root / "data").mkdir()
    for name in os.listdir(os.path.join(FIXTURE_ROOT, "data")):
        if name != "match_review_decisions":
            os.symlink(os.path.join(FIXTURE_ROOT, "data", name), root / "data" / name)
    (root / "data" / "match_review_decisions").mkdir()
    with open(root / "data" / "match_review_decisions" / "human_match_decision_records.json", "w",
              encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    return str(root)


class SandboxViolation(RuntimeError):
    pass


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


@contextlib.contextmanager
def read_only_sandbox(reads=None):
    """Elke schrijf-, verwijder-, proces- of netwerkpoging binnen deze context geeft SandboxViolation.
    `reads` (lijst) verzamelt de absolute paden van gelezen bestanden."""
    saved = []

    def patch(obj, name, replacement):
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, replacement)

    def refuse(label):
        def f(*a, **k):
            raise SandboxViolation(f"{label}{a!r}")
        return f

    real_open = builtins.open

    def guarded_open(file, mode="r", *a, **k):
        if any(c in mode for c in "wax+"):
            raise SandboxViolation(f"open({file!r}, {mode!r})")
        if reads is not None and isinstance(file, (str, bytes, os.PathLike)):
            reads.append(os.path.realpath(os.fsdecode(file)))
        return real_open(file, mode, *a, **k)

    real_os_open = os.open

    def guarded_os_open(path, flags, *a, **k):
        if flags & _WRITE_FLAGS:
            raise SandboxViolation(f"os.open({path!r}, {flags})")
        return real_os_open(path, flags, *a, **k)

    patch(builtins, "open", guarded_open)
    patch(io, "open", guarded_open)
    patch(os, "open", guarded_os_open)
    for n in ("replace", "rename", "remove", "unlink", "rmdir", "mkdir", "makedirs", "removedirs", "symlink", "link",
              "truncate", "utime", "chmod", "chown", "system", "popen"):
        if hasattr(os, n):
            patch(os, n, refuse(f"os.{n}"))
    for n in ("copy", "copy2", "copyfile", "copytree", "move", "rmtree"):
        patch(shutil, n, refuse(f"shutil.{n}"))
    for n in ("write_text", "write_bytes", "touch", "mkdir", "unlink", "rename", "replace", "rmdir"):
        patch(pathlib.Path, n, refuse(f"Path.{n}"))
    patch(subprocess, "Popen", refuse("subprocess.Popen"))
    for n in ("connect", "connect_ex", "sendto"):
        patch(socket.socket, n, refuse(f"socket.{n}"))
    patch(socket, "create_connection", refuse("socket.create_connection"))
    patch(socket, "getaddrinfo", refuse("socket.getaddrinfo"))
    try:
        yield
    finally:
        for obj, name, original in reversed(saved):
            setattr(obj, name, original)
