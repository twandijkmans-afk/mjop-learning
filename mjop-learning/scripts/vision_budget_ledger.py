#!/usr/bin/env python3
"""Persistent, procesoverstijgend budgetgrootboek voor externe visionaanroepen (External Vision Safety Gate v1).

Eisen en werking:
- Eén append-only JSONL-grootboek in een map BUITEN de repository (MJOP_VISION_LEDGER_DIR of een expliciet pad), alleen voor de eigenaar
  (map 0700, bestanden 0600), geen symlinks.
- Elke bewerking (reserve/settle/release) draait onder een exclusief fcntl.flock op een lockbestand, leest en verifieert de HELE keten
  (seq, prev_hash, entry_hash) en voegt daarna één regel toe met O_APPEND + fsync. Twee processen kunnen dus nooit samen het budget
  overschrijden; een corrupte, afgekapte of aangepaste keten weigert alles (fail-closed) tot een mens het herstelt.
- Het budget geldt per consent_id als TOTAAL (calls en output-tokens). De eerste reservering legt het hash van het consentrecord vast;
  een later gewijzigd record onder hetzelfde consent_id wordt geweigerd. Een reservering telt mee tot ze expliciet is vrijgegeven
  (bewijsbaar niet verzonden); na een crash of mislukte verzending blijft ze dus verbruikt (conservatief).
- Bekende grens: wie schrijfrechten op de map heeft kan het grootboek volledig vervangen of de staart afkappen; dat is geen
  bescherming tegen een kwaadwillende eigenaar van de map, wel tegen vergissingen, race-condities en onopgemerkte wijzigingen.
Dit script voert nooit zelf een providercall uit."""
import fcntl
import hashlib
import json
import os
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.photo.safety_gate import BudgetLedger, GateRefusal  # noqa: E402

ENV_DIR = "MJOP_VISION_LEDGER_DIR"
GENESIS = "0" * 64
LEDGER_FILE, LOCK_FILE = "ledger.jsonl", "ledger.lock"


def _repo_root():
    d = ROOT
    while d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, ".git")):
            return d
        d = os.path.dirname(d)
    return ROOT


def _entry_hash(entry):
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _refuse(code, msg):
    raise GateRefusal([code], [f"{code}: {msg}"])


class FileBudgetLedger(BudgetLedger):
    persistent = True
    cross_process_safe = True

    def __init__(self, directory=None):
        directory = directory or os.environ.get(ENV_DIR)
        if not directory:
            _refuse("LEDGER_UNCONFIGURED", f"{ENV_DIR} (of een expliciet pad) is verplicht")
        d = os.path.realpath(directory)
        for root in {os.path.realpath(_repo_root()), os.path.realpath(ROOT)}:
            if d == root or d.startswith(root + os.sep) or root.startswith(d + os.sep):
                _refuse("LEDGER_PATH_UNSAFE", "het grootboek mag niet in of boven de repository staan")
        os.makedirs(d, mode=0o700, exist_ok=True)
        st = os.stat(d)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            _refuse("LEDGER_PATH_UNSAFE", "map moet van de huidige gebruiker zijn en mag niet voor groep/anderen toegankelijk zijn (0700)")
        self.dir = d
        self.path, self.lock_path = os.path.join(d, LEDGER_FILE), os.path.join(d, LOCK_FILE)
        for p in (self.path, self.lock_path):
            if os.path.islink(p):
                _refuse("LEDGER_PATH_UNSAFE", f"{os.path.basename(p)} is een symlink")

    # -- intern ---------------------------------------------------------------------------------------------------
    def _locked(self):
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def _load(self):
        """Leest en verifieert de keten; geeft (entries, laatste hash)."""
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return [], GENESIS
        with os.fdopen(fd, "rb") as f:
            raw = f.read()
        if raw and not raw.endswith(b"\n"):
            _refuse("LEDGER_CORRUPT", "afgekapte laatste regel")
        entries, prev = [], GENESIS
        for i, line in enumerate(raw.splitlines()):
            try:
                e = json.loads(line)
            except ValueError:
                _refuse("LEDGER_CORRUPT", f"regel {i + 1} is geen JSON")
            if not isinstance(e, dict) or e.get("seq") != i + 1 or e.get("prev_hash") != prev or e.get("entry_hash") != _entry_hash(e):
                _refuse("LEDGER_TAMPERED", f"ketenfout bij regel {i + 1}")
            entries.append(e)
            prev = e["entry_hash"]
        return entries, prev

    def _append(self, entries, prev, event):
        e = dict(event, seq=len(entries) + 1, prev_hash=prev)
        e["entry_hash"] = _entry_hash(e)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, (json.dumps(e, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return e

    @staticmethod
    def _state(entries):
        res, consents = {}, {}
        for e in entries:
            if e["event"] == "RESERVE":
                res[e["reservation_id"]] = {"consent_id": e["consent_id"], "tokens": e["tokens"], "state": "RESERVED"}
                consents.setdefault(e["consent_id"], e["consent_sha256"])
            elif e["event"] in ("SETTLE", "RELEASE") and e["reservation_id"] in res:
                res[e["reservation_id"]]["state"] = "SETTLED" if e["event"] == "SETTLE" else "RELEASED"
        return res, consents

    # -- BudgetLedger ---------------------------------------------------------------------------------------------
    def reserve(self, *, consent_id, consent_sha256, derivative_sha256, max_calls, max_tokens_total, tokens_per_call, now):
        fd = self._locked()
        try:
            entries, prev = self._load()
            res, consents = self._state(entries)
            if consents.get(consent_id, consent_sha256) != consent_sha256:
                _refuse("LEDGER_CONSENT_CHANGED", f"{consent_id} is na de eerste reservering gewijzigd")
            mine = [r for r in res.values() if r["consent_id"] == consent_id and r["state"] != "RELEASED"]
            if len(mine) + 1 > max_calls:
                _refuse("BUDGET_CALLS_EXHAUSTED", f"{len(mine)} van {max_calls} calls verbruikt of gereserveerd")
            if sum(r["tokens"] for r in mine) + tokens_per_call > max_tokens_total:
                _refuse("BUDGET_TOKENS_EXHAUSTED", f"tokenbudget {max_tokens_total} zou worden overschreden")
            rid = f"RES-{len(entries) + 1:08d}"
            self._append(entries, prev, {"event": "RESERVE", "reservation_id": rid, "consent_id": consent_id, "consent_sha256": consent_sha256,
                                         "derivative_sha256": derivative_sha256, "tokens": tokens_per_call, "at": str(now)})
            return rid
        finally:
            os.close(fd)

    def _close(self, reservation_id, event, extra):
        fd = self._locked()
        try:
            entries, prev = self._load()
            res, _ = self._state(entries)
            if reservation_id not in res or res[reservation_id]["state"] != "RESERVED":
                _refuse("LEDGER_UNKNOWN_RESERVATION", f"{reservation_id} bestaat niet of is al afgesloten")
            self._append(entries, prev, dict({"event": event, "reservation_id": reservation_id}, **extra))
        finally:
            os.close(fd)

    def settle(self, reservation_id, *, outcome, output_tokens=None):
        self._close(reservation_id, "SETTLE", {"outcome": str(outcome), "output_tokens": output_tokens})

    def release(self, reservation_id, *, reason):
        self._close(reservation_id, "RELEASE", {"reason": str(reason)})

    def usage(self, consent_id):
        """Alleen lezen (voor rapportage): {calls, tokens} die onder dit consent verbruikt of gereserveerd zijn."""
        fd = self._locked()
        try:
            entries, _ = self._load()
        finally:
            os.close(fd)
        res, _ = self._state(entries)
        mine = [r for r in res.values() if r["consent_id"] == consent_id and r["state"] != "RELEASED"]
        return {"calls": len(mine), "tokens": sum(r["tokens"] for r in mine)}
