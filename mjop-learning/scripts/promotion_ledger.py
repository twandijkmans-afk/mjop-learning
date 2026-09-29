#!/usr/bin/env python3
"""
promotion_ledger.py - keten van canonieke promoties (batch 1 + incoming batches).

Batch 1 legde zijn eindtoestand vast in data/promotion_state_batch1_v1.json (post_manifest).
Elke latere incoming-promotie legt vast in data/incoming_promotions/<promotion_id>.json:
  pre_manifest  = hashes van de gevolgde canonieke bestanden vlak vóór de promotie
  post_manifest = hashes direct erna
De keten klopt als elke pre_manifest aansluit op de vorige toestand; de huidige bestanden moeten
gelijk zijn aan de post_manifest van de laatste actieve promotie. Alleen lezen, geen writes.
"""
import glob
import hashlib
import json
import os

STATE_DIR = os.path.join("data", "incoming_promotions")
HISTORY_ROOT = os.path.join("data", "history", "incoming_promotions")
# gevolgde canonieke lagen voor incoming-promoties (dirs + losse bestanden)
TRACKED_DIRS = ("data/raw", "data/extracted", "data/normalized", "data/verified", "data/price_observations",
                "data/comparability", "data/kengetallen", "data/review_decisions", "data/match_review_decisions")
TRACKED_FILES = ("reports/document_registry.json", "reports/document_inventory.json",
                 "reports/document_inventory.csv", "reports/raw_manifest.json")
# de lagen die batch 1 in zijn post_manifest vastlegde
BATCH1_DIRS = ("data/extracted", "data/normalized", "data/verified", "data/price_observations", "data/comparability",
               "data/kengetallen", "data/review_decisions", "data/match_review_decisions")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_hashes(root, dirs=TRACKED_DIRS, files=TRACKED_FILES):
    out = {}
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(root, d, "**", "*"), recursive=True)):
            if os.path.isfile(p):
                out[os.path.relpath(p, root).replace(os.sep, "/")] = sha256_file(p)
    for f in files:
        p = os.path.join(root, f)
        if os.path.isfile(p):
            out[f] = sha256_file(p)
    return out


def restrict(manifest, dirs):
    return {k: v for k, v in manifest.items() if any(k.startswith(d + "/") for d in dirs)}


def states(root):
    """Actieve (PROMOTED) incoming-promoties, in volgorde."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, STATE_DIR, "*.json"))):
        with open(p, encoding="utf-8") as f:
            s = json.load(f)
        if s.get("status") == "PROMOTED":
            out.append(s)
    return sorted(out, key=lambda s: s["sequence"])


def chain_errors(root):
    """Sluit de keten batch1 -> incoming-promoties aan, en is de huidige toestand de laatste post?"""
    errors = []
    active = states(root)
    b1 = os.path.join(root, "data", "promotion_state_batch1_v1.json")
    prev = None
    if os.path.exists(b1):
        with open(b1, encoding="utf-8") as f:
            prev = ("batch1", restrict(json.load(f)["post_manifest"], BATCH1_DIRS), BATCH1_DIRS)
    for s in active:
        if prev is not None:
            name, post, dirs = prev
            if restrict(s["pre_manifest"], dirs) != post:
                errors.append(f"{s['promotion_id']}: pre_manifest sluit niet aan op {name}")
        prev = (s["promotion_id"], s["post_manifest"], TRACKED_DIRS)
    if active:
        cur = tracked_hashes(root)
        last = active[-1]["post_manifest"]
        if cur != last:
            diff = sorted(set(cur.items()) ^ set(last.items()))[:5]
            errors.append(f"huidige canonieke bestanden wijken af van {active[-1]['promotion_id']}: {diff}")
    return errors


def latest(root):
    active = states(root)
    return active[-1] if active else None


def promoted_document_ids(root):
    """DOC-ID's die via actieve incoming-promoties canoniek zijn geworden (in volgorde)."""
    return [d["document_id"] for s in states(root) for d in s["summary"]["promoted_documents"]]


def added_price_observations(root):
    return sum(s["summary"]["price_observations"]["added"] for s in states(root))
