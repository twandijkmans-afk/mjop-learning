"""Evaluatie: precisie, recall en telfouten van een voorstelset tegen een menselijke referentie.

De menselijke referentie (bv. Maldenhof-foto 2) wordt UITSLUITEND hier gelezen, als JSON-coordinaten voor evaluatie. Er worden
geen foto's gelezen en de referentie wordt nooit als invoer voor een visionprovider gebruikt."""
import json
import os

from agent.photo.contract import COUNTING_TYPES, ELEMENT_TYPES, PROJECT_ROOT, canonical_sha256, iou

FRAME_STORE = "data/frame_inventory/maldenhof_photo_frame_instances_v1.json"
CANDIDATES = "data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json"


def _load(rel, root):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return json.load(f)


def load_maldenhof_photo2_reference(root=PROJECT_ROOT):
    """Alleen lezen. Referentie = door een mens bevestigde instances (kozijnopeningen/buitendeur) plus de menselijk besloten
    dakraam-/dakkapelcontext uit de gecorrigeerde kandidatenlijst."""
    store, cand = _load(FRAME_STORE, root), _load(CANDIDATES, root)
    ref = []
    inst = {i["frame_instance_id"]: i for i in store["instances"]}
    for fid, ann in store["instance_annotations"].items():
        i = inst.get(fid)
        if not i or i.get("status") != "CONFIRMED":
            continue
        etype = {"EXTERIOR_FRAME": "WINDOW_OPENING", "EXTERIOR_DOOR": "EXTERIOR_DOOR"}.get(i["component_type"])
        if etype:
            ref.append({"ref_id": fid, "element_type": etype, "bbox_norm": ann["bbox_norm"], "visibility": ann["photo_visibility"]})
    for r in cand.get("roof_context_observations", []):
        ref.append({"ref_id": r["candidate_id"], "element_type": "ROOF_WINDOW", "bbox_norm": r["bbox_norm"], "visibility": None})
    for r in cand.get("dormer_context_observations", []):
        ref.append({"ref_id": r["candidate_id"], "element_type": "DORMER_OPENING", "bbox_norm": r["bbox_norm"], "visibility": None})
    meta = {"photo_id": "maldenhof_2", "source_sha256": cand["photo"]["sha256"], "frame_store": FRAME_STORE, "candidates": CANDIDATES,
            "reference_sha256": canonical_sha256(ref), "usage": "EVALUATION_ONLY_NOT_MODEL_INPUT"}
    return ref, meta


def match(pred, ref, threshold=0.5):
    """Deterministische greedy-koppeling per type op afnemende IoU. Geeft (paren, ongekoppelde pred, ongekoppelde ref)."""
    pairs, used_p, used_r = [], set(), set()
    cands = []
    for pi, p in enumerate(pred):
        for ri, r in enumerate(ref):
            if p["element_type"] == r["element_type"]:
                v = iou(p["bbox_norm"], r["bbox_norm"])
                if v >= threshold:
                    cands.append((-v, pi, ri))
    for negv, pi, ri in sorted(cands):
        if pi not in used_p and ri not in used_r:
            used_p.add(pi), used_r.add(ri)
            pairs.append((pi, ri, -negv))
    return pairs, [i for i in range(len(pred)) if i not in used_p], [i for i in range(len(ref)) if i not in used_r]


def _ratio(n, d):
    return None if d == 0 else round(n / d, 4)


def evaluate_proposals(proposals, reference, threshold=0.5):
    """proposals: lijst uit een geverifieerde voorstelset; reference: lijst {ref_id, element_type, bbox_norm, visibility}."""
    pairs, fp_i, fn_i = match(proposals, reference, threshold)
    out = {"iou_threshold": threshold, "per_type": {}, "overall": {}, "unmatched_proposals": [proposals[i]["observation_id"] for i in fp_i],
           "missed_reference": [reference[i]["ref_id"] for i in fn_i]}
    tp_all = fp_all = fn_all = 0
    for t in ELEMENT_TYPES:
        p_idx = [i for i, p in enumerate(proposals) if p["element_type"] == t]
        r_idx = [i for i, r in enumerate(reference) if r["element_type"] == t]
        if not p_idx and not r_idx:
            continue
        tp = sum(1 for pi, ri, _ in pairs if proposals[pi]["element_type"] == t)
        fp, fn = len(p_idx) - tp, len(r_idx) - tp
        vis = [(proposals[pi]["visibility"], reference[ri]["visibility"]) for pi, ri, _ in pairs
               if proposals[pi]["element_type"] == t and reference[ri]["visibility"] is not None]
        out["per_type"][t] = {"tp": tp, "fp": fp, "fn": fn, "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
                              "count_proposed": len(p_idx), "count_reference": len(r_idx), "count_error": len(p_idx) - len(r_idx),
                              "counts_toward_frame_counts": t in COUNTING_TYPES,
                              "visibility_agreement": _ratio(sum(a == b for a, b in vis), len(vis)), "visibility_compared": len(vis)}
        tp_all, fp_all, fn_all = tp_all + tp, fp_all + fp, fn_all + fn
    cp = sum(1 for p in proposals if p["element_type"] in COUNTING_TYPES)
    cr = sum(1 for r in reference if r["element_type"] in COUNTING_TYPES)
    out["overall"] = {"tp": tp_all, "fp": fp_all, "fn": fn_all, "precision": _ratio(tp_all, tp_all + fp_all),
                      "recall": _ratio(tp_all, tp_all + fn_all), "count_proposed_frame_types": cp, "count_reference_frame_types": cr,
                      "count_error_frame_types": cp - cr,
                      "note": "mock/replay-uitkomsten meten de evaluatieharnas, niet de nauwkeurigheid van een echt model"}
    return out
