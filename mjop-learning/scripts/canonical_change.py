#!/usr/bin/env python3
"""
canonical_change.py - een vastgelegde menselijke beslissing als schakel in de canonieke keten.

Een relatiebesluit (scripts/record_relation_decision.py) of een comparability-familiebesluit
(scripts/apply_family_decision.py) wijzigt gevolgde canonieke bestanden (document_relations.json,
de decision store, comparability, kengetallen). Zo'n wijziging loopt via dezelfde keten als de
incoming-promoties (scripts/promotion_ledger.py):

  - snapshot van alle gevolgde bestanden in data/history/incoming_promotions/<change_id>/pre (+ pre_manifest);
  - de wijziging zelf (apply_fn), met eigen invarianten; bij elke fout wordt alles exact teruggezet;
  - status in data/incoming_promotions/<change_id>.json met status APPLIED, pre/post-manifest en het besluit;
  - rollback alleen van de laatste schakel; de history blijft bewaard (rolled_back_state.json).

Geen AI, geen automatische beslissingen: apply_fn voert alleen een expliciet menselijk besluit uit.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402

TOOL_VERSION = "canonical_change_v1.0.0"


class ChangeError(RuntimeError):
    pass


def unique_change_id(root, base):
    """base, of base-2, base-3, ... als er al een status of history (bijv. na rollback) met die naam bestaat."""
    n, cid = 1, base
    while os.path.exists(os.path.join(root, pl.STATE_DIR, f"{cid}.json")) or \
            os.path.exists(os.path.join(root, pl.HISTORY_ROOT, cid)):
        n += 1
        cid = f"{base}-{n}"
    return cid


def preflight_errors(root):
    """De keten moet schoon zijn vóór een nieuwe schakel (zelfde controles als een promotie)."""
    return pr.canonical_errors(root)


def apply_change(root, change_id, kind, apply_fn, decision, now=None):
    """apply_fn(root) -> summary (dict). decision = het menselijke besluit zoals vastgelegd."""
    now = now or pr.now_utc()
    if os.path.exists(os.path.join(root, pl.STATE_DIR, f"{change_id}.json")) or \
            os.path.exists(os.path.join(root, pl.HISTORY_ROOT, change_id)):
        raise ChangeError(f"{change_id} bestaat al (nooit overschrijven)")
    fails = preflight_errors(root)
    if fails:
        raise ChangeError("PREFLIGHT FAALT:\n- " + "\n- ".join(fails))
    hist = os.path.join(root, pl.HISTORY_ROOT, change_id)
    os.makedirs(hist)
    pre = pr.snapshot(root, hist)
    try:
        summary = apply_fn(root)
        after = pr.canonical_after_errors(root)
        if after:
            raise ChangeError(f"canonieke controles na wijziging: {after}")
    except BaseException:
        pr.restore(root, hist, pre)
        pr.write_json(os.path.join(hist, "failed_attempt.json"), {"change_id": change_id, "status": "FAILED_RESTORED"})
        raise
    post = pl.tracked_hashes(root)
    prev = pl.latest(root)
    state = {"promotion_id": change_id, "change_kind": kind, "tool_version": TOOL_VERSION, "status": "APPLIED",
             "batch_id": None, "sequence": (prev["sequence"] + 1) if prev else 1, "applied_at": now,
             "decision": decision,
             "history": os.path.relpath(hist, root).replace(os.sep, "/"),
             "pre_manifest_sha256": pl.sha256_file(os.path.join(hist, "pre_manifest.json")),
             "pre_manifest": pre, "post_manifest": post, "summary": summary}
    pr.write_json(os.path.join(root, pl.STATE_DIR, f"{change_id}.json"), state)
    return state


def rollback(root, change_id):
    last = pl.latest(root)
    if last is None or last["promotion_id"] != change_id:
        raise ChangeError(f"alleen de laatste schakel kan worden teruggedraaid "
                          f"(laatste: {last['promotion_id'] if last else 'geen'})")
    if pl.tracked_hashes(root) != last["post_manifest"]:
        raise ChangeError("huidige canonieke bestanden wijken af van de post_manifest; eerst onderzoeken")
    hist = os.path.join(root, last["history"])
    pr.restore(root, hist, last["pre_manifest"])
    pr.write_json(os.path.join(hist, "rolled_back_state.json"), dict(last, status="ROLLED_BACK"))
    os.remove(os.path.join(root, pl.STATE_DIR, f"{change_id}.json"))
    return f"ROLLBACK OK ({change_id})"
