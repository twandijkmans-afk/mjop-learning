#!/usr/bin/env python3
"""Photo Reviewer PoC: offline demo en evaluatie (docs/photo_reviewer_poc_v1.md).

Subcommando's:
  demo --out DIR                  synthetische gevel -> ReplayProvider -> verifier -> hoeveelheden -> evaluatie -> HTML
  eval-maldenhof-mock --out DIR   evaluatieharnas op de menselijke referentie van Maldenhof-foto 2 met GEMOCKTE modelresultaten
  write-fixtures                  (ontwikkeling) schrijft de synthetische fixtures in tests/fixtures/photo_reviewer/

Uitvoer gaat uitsluitend naar een map BUITEN de repository (nooit naar data/ of reports/). Geen netwerk, geen echte foto's,
geen externe AI-aanroep."""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent.photo import evaluate, review_page, synthetic  # noqa: E402
from agent.photo.contract import canonical_sha256, sha256_bytes  # noqa: E402
from agent.photo.providers import ReplayProvider, VisionRequest, build_proposal_set  # noqa: E402
from agent.photo.quantity import compute_quantity_state  # noqa: E402
from agent.photo.verifier import verify_or_raise  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "photo_reviewer")


def repo_root():
    d = ROOT
    while d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, ".git")):
            return d
        d = os.path.dirname(d)
    return ROOT


def safe_out_dir(path):
    out = os.path.realpath(path)
    root = os.path.realpath(repo_root())
    if out == root or out.startswith(root + os.sep):
        raise SystemExit(f"WEIGERING: uitvoermap {out} ligt binnen de repository; kies een map erbuiten (testresultaten horen niet in de publieke repo).")
    os.makedirs(out, exist_ok=True)
    return out


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def synthetic_request(png):
    sha = sha256_bytes(png)
    return VisionRequest(photo_id="synthetic_facade_v1", source_sha256=sha, derivative_sha256=sha, width_px=synthetic.W,
                         height_px=synthetic.H, image_bytes=png, media_type="image/png", derivative_transform=("SYNTHETIC",))


def run_demo(out):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(FIX, "synthetic_facade_v1.png"), "rb") as f:
        png = f.read()
    req = synthetic_request(png)
    provider = ReplayProvider.from_file(os.path.join(FIX, "synthetic_facade_v1_replay.json"))
    pset = build_proposal_set(req, provider.analyze(req))
    verify_or_raise(pset, image_bytes=png, image_size=(synthetic.W, synthetic.H), source_registry={req.photo_id: req.source_sha256})
    with open(os.path.join(FIX, "synthetic_facade_v1_dimension_input.json"), encoding="utf-8") as f:
        dims = json.load(f)
    state = compute_quantity_state(pset, dims)
    with open(os.path.join(FIX, "synthetic_facade_v1_ground_truth.json"), encoding="utf-8") as f:
        gt = json.load(f)["ground_truth"]
    ev = evaluate.evaluate_proposals(pset["proposals"], [{"ref_id": g["gt_id"], **{k: g[k] for k in ("element_type", "bbox_norm", "visibility")}} for g in gt])
    html = review_page.render_review_page(png, pset, state, dims, ev, title="Photo Reviewer PoC — synthetische voorbeeldgevel")
    with open(os.path.join(out, "synthetic_facade_v1.png"), "wb") as f:
        f.write(png)
    write_json(os.path.join(out, "proposal_set.json"), pset)
    write_json(os.path.join(out, "quantity_state.json"), state)
    write_json(os.path.join(out, "evaluation.json"), ev)
    with open(os.path.join(out, "review.html"), "w", encoding="utf-8") as f:
        f.write(html)
    manifest = {"note": "synthetische demo; geen echte foto's, geen externe aanroep", "sha256": {
        n: sha256_bytes(open(os.path.join(out, n), "rb").read()) for n in ("proposal_set.json", "quantity_state.json", "evaluation.json", "review.html", "synthetic_facade_v1.png")}}
    write_json(os.path.join(out, "run_manifest.json"), manifest)
    return pset, state, ev


def run_maldenhof_mock(out):
    os.makedirs(out, exist_ok=True)
    ref, meta = evaluate.load_maldenhof_photo2_reference()
    # GEMOCKT modelresultaat: kleine afwijkingen, een gemiste opening, een onterecht voorstel; geen echte afbeelding gebruikt.
    prop = []
    for i, r in enumerate(ref):
        if r["ref_id"] == "FI-M2-005":
            continue                                                  # gemist
        b = r["bbox_norm"]
        d = 0.003 if i % 2 == 0 else -0.003
        prop.append({"element_type": r["element_type"], "bbox_norm": [round(min(max(v + d, 0), 1), 4) for v in b],
                     "visibility": r["visibility"] or "FULL",
                     "uncertainties": [] if (r["visibility"] or "FULL") == "FULL" else [{"code": "OCCLUDED_BY_OBJECT", "level": "MEDIUM"}],
                     "observation": "gemockte voorstelregel"})
    prop.append({"element_type": "WINDOW_OPENING", "bbox_norm": [0.10, 0.80, 0.16, 0.88], "visibility": "PARTIAL",
                 "uncertainties": [{"code": "AMBIGUOUS_TYPE", "level": "HIGH"}], "observation": "gemockt onterecht voorstel"})
    mock_hash = sha256_bytes(("MOCK_NO_IMAGE|" + meta["photo_id"]).encode())
    req = VisionRequest(photo_id=meta["photo_id"], source_sha256=meta["source_sha256"], derivative_sha256=mock_hash, width_px=2048,
                        height_px=1536, derivative_transform=("MOCK_NO_IMAGE",))
    pset = build_proposal_set(req, ReplayProvider({mock_hash: {"proposals": prop, "hidden_element_hypotheses": []}}).analyze(req))
    verify_or_raise(pset)
    ev = evaluate.evaluate_proposals(pset["proposals"], ref)
    write_json(os.path.join(out, "maldenhof_photo2_mock_evaluation.json"), {"reference_meta": meta, "evaluation": ev})
    return ev


def write_fixtures():
    png = synthetic.png_bytes()
    sha = sha256_bytes(png)
    os.makedirs(FIX, exist_ok=True)
    with open(os.path.join(FIX, "synthetic_facade_v1.png"), "wb") as f:
        f.write(png)
    write_json(os.path.join(FIX, "synthetic_facade_v1_replay.json"), synthetic.model_like_recording(sha))
    write_json(os.path.join(FIX, "synthetic_facade_v1_ground_truth.json"), {"photo_id": "synthetic_facade_v1", "ground_truth": synthetic.GROUND_TRUTH})
    print("fixtures geschreven; sha256", sha)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("demo", "eval-maldenhof-mock"):
        sub.add_parser(name).add_argument("--out", required=True, help="uitvoermap BUITEN de repository")
    sub.add_parser("write-fixtures")
    a = ap.parse_args(argv)
    if a.cmd == "write-fixtures":
        write_fixtures()
        return 0
    out = safe_out_dir(a.out)
    if a.cmd == "demo":
        pset, state, ev = run_demo(out)
        print(json.dumps({"set_id": pset["set_id"], "state_id": state["state_id"], "totals": state["totals"], "overall": ev["overall"], "out": out}, indent=2, ensure_ascii=False))
    else:
        ev = run_maldenhof_mock(out)
        print(json.dumps({"overall": ev["overall"], "out": out}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
