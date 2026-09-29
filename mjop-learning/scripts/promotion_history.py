#!/usr/bin/env python3
"""
promotion_history.py  (pre-promotie-weergave van de projectroot)

Na de canonieke promotie van batch1_v1 (data/promotion_state_batch1_v1.json bestaat) horen de
pre-promotie-analyses (promote_deterministic_batch --dry-run, promotion v2/v3, het reviewpakket
en build_promoted_price_observations) te blijven werken op de toestand van VÓÓR de promotie.
Die toestand staat ongewijzigd in data/history/pre_deterministic_promotion_batch1_v1/.

pre_promotion_root(root) levert een tijdelijke projectroot waarin alles naar de echte repo
verwijst (symlinks), behalve de datalagen die de promotie verving: die verwijzen naar de
history-kopie. Zonder promotiestatus is het gewoon `root` zelf. Er wordt nooit iets geschreven
in de history of in canonieke data.
"""
import atexit
import contextlib
import os
import tempfile

STATE = os.path.join("data", "promotion_state_batch1_v1.json")
HISTORY = os.path.join("data", "history", "pre_deterministic_promotion_batch1_v1")
REPLACED = ("extracted", "normalized", "verified", "price_observations", "comparability", "kengetallen",
            "review_decisions", "match_review_decisions")


def is_promoted(root):
    return os.path.isfile(os.path.join(root, STATE))


@contextlib.contextmanager
def pre_promotion_root(root):
    if not is_promoted(root):
        yield root
        return
    hist = os.path.join(root, HISTORY, "data")
    if not os.path.isdir(hist):
        raise RuntimeError(f"promotiestatus aanwezig maar history ontbreekt: {hist}")
    with tempfile.TemporaryDirectory() as tmp:
        for name in os.listdir(root):
            if name != "data":
                os.symlink(os.path.join(root, name), os.path.join(tmp, name))
        os.makedirs(os.path.join(tmp, "data"))
        for name in os.listdir(os.path.join(root, "data")):
            if name in REPLACED or name in ("history", os.path.basename(STATE)):
                continue
            os.symlink(os.path.join(root, "data", name), os.path.join(tmp, "data", name))
        for name in REPLACED:
            src = os.path.join(hist, name)
            if os.path.isdir(src):
                os.symlink(src, os.path.join(tmp, "data", name))
        yield tmp


_KEEP = contextlib.ExitStack()
atexit.register(_KEEP.close)
_FIXTURE_ROOTS = {}


def pre_promotion_fixture_root(root):
    """Zoals pre_promotion_root, maar blijvend tot het proces eindigt. Voor tests die de
    pre-promotie-kengetallen (C1/C2) als vaste, alleen-lezen fixture gebruiken."""
    root = os.path.abspath(root)
    if root not in _FIXTURE_ROOTS:
        _FIXTURE_ROOTS[root] = _KEEP.enter_context(pre_promotion_root(root))
    return _FIXTURE_ROOTS[root]
