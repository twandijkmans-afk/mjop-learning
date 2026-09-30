"""Crosswalk-verificatie v1 — menselijke besluiten over voorgestelde mappings (append-only).

Twee soorten voorstellen, beide NOOIT automatisch geldig:
  - HSM-*  vocabularies/quantity_subjects_v1.json  historische element_code+eenheid -> hoeveelheidsonderwerp
  - XW-*   vocabularies/app_element_crosswalk_v1.json  MJOP-App-element <-> interne element_code

Een mapping is alleen 'VERIFIED' als er een ACTIVE record met decision VERIFY bestaat in
data/crosswalk_decisions/crosswalk_decision_records.json (reviewer_type human). REJECT maakt haar
expliciet ongeldig. Zonder besluit blijft de status van het voorstel (PROPOSED / REVIEW_REQUIRED) staan.

    python scripts/crosswalk.py status
    python scripts/crosswalk.py record --mapping XW-dak-plat-4711-m2 --decision VERIFY \
        --reviewer twandijkmans --reason "..."
"""

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import append_only_store as aos  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SUBJECTS = ROOT / "vocabularies" / "quantity_subjects_v1.json"
APP_CROSSWALK = ROOT / "vocabularies" / "app_element_crosswalk_v1.json"
DECISIONS = ROOT / "data" / "crosswalk_decisions" / "crosswalk_decision_records.json"
RULE_VERSION = "crosswalk_rules_v1"


class CrosswalkError(RuntimeError):
    pass


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_proposals():
    subj = json.loads(SUBJECTS.read_text(encoding="utf-8"))
    app = json.loads(APP_CROSSWALK.read_text(encoding="utf-8"))
    out = {m["mapping_id"]: dict(m, kind="HISTORICAL_SUBJECT") for m in subj["historical_subject_mappings"]}
    out.update({m["mapping_id"]: dict(m, kind="APP_ELEMENT") for m in app["mappings"]})
    return out


def new_store():
    return {"store_version": "crosswalk_decision_v1", "append_only": True,
            "description": "Menselijke verificatie van crosswalk-/onderwerpmappings (scripts/crosswalk.py). Append-only.",
            "records": []}


def load_store(path=DECISIONS):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else new_store()


def store_errors(store):
    return aos.invariant_errors(store["records"], "decision_id", lambda r: r["mapping_id"])


def effective(proposals=None, store=None):
    """mapping_id -> {status, human_verified, decision_id}. Alleen een ACTIVE VERIFY maakt 'VERIFIED'."""
    proposals = proposals if proposals is not None else load_proposals()
    store = store if store is not None else load_store()
    active = {r["mapping_id"]: r for r in store["records"] if r["status"] == "ACTIVE"}
    out = {}
    for mid, m in sorted(proposals.items()):
        d = active.get(mid)
        if d and d["decision"] == "VERIFY" and d["proposal_sha256"] == canonical_sha256(m):
            out[mid] = {"status": "VERIFIED", "human_verified": True, "decision_id": d["decision_id"]}
        elif d and d["decision"] == "REJECT":
            out[mid] = {"status": "REJECTED", "human_verified": True, "decision_id": d["decision_id"]}
        elif d:  # voorstel gewijzigd na het besluit
            out[mid] = {"status": "REVIEW_REQUIRED", "human_verified": False, "decision_id": d["decision_id"],
                        "reason": "voorstel gewijzigd sinds het besluit"}
        else:
            out[mid] = {"status": m["status"], "human_verified": False, "decision_id": None}
    return out


def record_decision(store, *, mapping_id, decision, reviewer_id, reason, reviewed_at, proposals=None):
    proposals = proposals if proposals is not None else load_proposals()
    if mapping_id not in proposals:
        raise CrosswalkError(f"onbekende mapping {mapping_id}")
    if decision not in ("VERIFY", "REJECT"):
        raise CrosswalkError("decision moet VERIFY of REJECT zijn")
    if not reviewer_id or not reason:
        raise CrosswalkError("reviewer en reden zijn verplicht")
    out = copy.deepcopy(store)
    previous = [r for r in out["records"] if r["mapping_id"] == mapping_id and r["status"] in ("ACTIVE", "REVIEW_REQUIRED")]
    rec = {
        "decision_id": aos.next_id(out["records"], "decision_id", "XWD"),
        "mapping_id": mapping_id,
        "decision": decision,
        "proposal_sha256": canonical_sha256(proposals[mapping_id]),
        "decision_reason": reason,
        "reviewer": {"reviewer_id": reviewer_id, "reviewer_type": "human"},
        "reviewed_at": reviewed_at,
        "rule_version": RULE_VERSION,
        "supersedes": previous[0]["decision_id"] if previous else None,
        "status": "ACTIVE",
    }
    for r in previous:
        r["status"] = "SUPERSEDED"
    out["records"].append(rec)
    errs = store_errors(out) + aos.append_only_errors(store["records"], out["records"], "decision_id")
    if errs:
        raise CrosswalkError("; ".join(errs))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Crosswalk-verificatie v1")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    r = sub.add_parser("record")
    r.add_argument("--mapping", required=True)
    r.add_argument("--decision", required=True, choices=["VERIFY", "REJECT"])
    r.add_argument("--reviewer", required=True)
    r.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "status":
        for mid, e in effective().items():
            print(f"{mid}: {e['status']}")
        return 0
    store = load_store()
    try:
        new = record_decision(store, mapping_id=args.mapping, decision=args.decision, reviewer_id=args.reviewer,
                              reason=args.reason, reviewed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    except CrosswalkError as e:
        print(f"FOUT: {e}", file=sys.stderr)
        return 2
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    DECISIONS.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.mapping}: {args.decision} vastgelegd")
    return 0


if __name__ == "__main__":
    sys.exit(main())
