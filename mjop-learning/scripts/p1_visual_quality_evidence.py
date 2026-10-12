#!/usr/bin/env python3
"""P1 visual quality evidence for the Maldenhof decision pack (report only).

Independent, deterministic feature-match evidence (SIFT + ratio test + RANSAC
similarity transform) for the overlap relations VR-xxx, plus a negative-control
rank: how well does the proposed partner score against all other candidate
partners of the same type in the other photo.  The numbers are *support for a
human reviewer*, never a SAME decision, never a merge and never a pand link.
Output: reports/frames/photo_review_map003_map004_v1/p1_quality_review/
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_p1_quality_review as Q  # noqa: E402
import build_visual_photo_review_map003_map004 as B  # noqa: E402
import visual_review_map003_map004_data as V  # noqa: E402

PAD = 0.12
MAXDIM = 360


def crop_gray(im, box):
    w, h = box[2] - box[0], box[3] - box[1]
    x0, y0 = max(0, box[0] - w * PAD), max(0, box[1] - h * PAD)
    x1, y1 = min(im.width, box[2] + w * PAD), min(im.height, box[3] + h * PAD)
    t = im.crop((int(x0), int(y0), int(x1), int(y1))).convert("L")
    s = MAXDIM / max(t.size)
    a = np.asarray(t.resize((max(8, round(t.width * s)), max(8, round(t.height * s)))))
    return cv2.createCLAHE(2.0, (4, 4)).apply(a)


_sift = cv2.SIFT_create()


def feats(g):
    k, d = _sift.detectAndCompute(g, None)
    return k, d


def match(fa, fb):
    ka, da = fa
    kb, db = fb
    if da is None or db is None or len(ka) < 4 or len(kb) < 4:
        return 0, 0
    m = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
    if len(good) < 4:
        return len(good), 0
    pa = np.float32([ka[g.queryIdx].pt for g in good])
    pb = np.float32([kb[g.trainIdx].pt for g in good])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=6.0, maxIters=2000, confidence=0.99)
    return len(good), int(inl.sum()) if inl is not None else 0


def main():
    ims, ver = B.load_sources(B.ZIP_DEFAULT)
    boxes, _ = B.photo2_boxes()
    obs = Q.obs_index()
    cv2.setRNGSeed(1)
    # all-pairs matrix MAP-003 x MAP-004 (windows, partial, door)
    f3 = {k: feats(crop_gray(ims[v[0]], v[1])) for k, v in obs.items() if v[0] == "MAP-003"}
    f4 = {k: feats(crop_gray(ims[v[0]], v[1])) for k, v in obs.items() if v[0] == "MAP-004"}
    mat = {a: {b: match(f3[a], f4[b])[1] for b in f4} for a in f3}
    res = []
    for r in V.RELATIONS:
        rid, soc, l, rr, cls, strength, basis = r[:7]
        e = {"relation_id": rid, "left": l, "right": rr, "claude_class": cls, "claude_strength": strength}
        if cls in ("SAME_FACADE_SECTION", "DIFFERENT_FRAMES") or "buiten beeld" in rr or "rand" in l:
            e["method"] = "NOT_APPLICABLE_FACADE_OR_OUTSIDE"
            res.append(e)
            continue
        a = Q.resolve(l, ims, obs, boxes)
        b = Q.resolve(rr, ims, obs, boxes)
        if not a or not b:
            e["method"] = "NOT_RESOLVABLE_TO_SINGLE_BOX"
            res.append(e)
            continue
        ga, gb = crop_gray(ims[a[0]], a[1]), crop_gray(ims[b[0]], b[1])
        n_good, n_inl = match(feats(ga), feats(gb))
        e.update(method="SIFT_RATIO_RANSAC_SIMILARITY", good_matches=n_good, inliers=n_inl)
        # negative-control rank for the 003 x 004 relations with plain single observations
        if l.startswith("MAP-003:OBS-MAP003-") and rr.startswith("MAP-004:OBS-MAP004-") and "+" not in l + rr and "/" not in l + rr:
            ka, kb = l.split(":")[1], rr.split(":")[1]
            row = sorted(mat[ka].items(), key=lambda x: -x[1])
            col = sorted(((x, mat[x][kb]) for x in mat), key=lambda x: -x[1])
            e["rank_of_partner_among_MAP004"] = 1 + [x[0] for x in row].index(kb)
            e["rank_of_partner_among_MAP003"] = 1 + [x[0] for x in col].index(ka)
            e["best_other_inliers_row"] = max([v for k, v in row if k != kb] or [0])
            e["best_other_inliers_col"] = max([v for k, x in col for v in [x] if k != ka] or [0])
        res.append(e)
    out = Q.QDIR
    out.mkdir(parents=True, exist_ok=True)
    doc = {"title": "P1 feature-match evidence (support for human review, not a decision)",
           "method": "SIFT, Lowe ratio 0.75, CLAHE, RANSAC similarity (6px), crops +12% pad, max dim 360; cv2 RNG seed 1",
           "opencv": cv2.__version__, "relations": res}
    (out / "p1_feature_match_evidence_v1.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    for e in res:
        print(e["relation_id"], e.get("inliers"), e.get("good_matches"), e.get("rank_of_partner_among_MAP004"), e.get("rank_of_partner_among_MAP003"), e.get("best_other_inliers_row"), e.get("best_other_inliers_col"), e["method"][:12])


if __name__ == "__main__":
    main()
