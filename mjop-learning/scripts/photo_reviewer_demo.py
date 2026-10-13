#!/usr/bin/env python3
"""Photo Reviewer PoC: offline demo en evaluatie (docs/photo_reviewer_poc_v1.md).

Subcommando's:
  demo --out DIR                                  synthetische gevel -> ReplayProvider -> verifier -> hoeveelheden -> evaluatie -> HTML
  eval-reference-mock --reference-set ID --out DIR   evaluatieharnas op een menselijke referentieset (agent/photo/evaluate.py: REFERENCE_SETS)
                                                  met GEMOCKTE modelresultaten

Uitvoer gaat uitsluitend naar een map BUITEN de repository (nooit naar data/ of reports/); dat wordt in elke run-functie zelf afgedwongen
(safe_out_dir), niet alleen in de CLI. Dit script schrijft nooit in de repository: het ontwikkelcommando dat de synthetische fixtures
opnieuw genereert staat bewust apart (tests/photo_reviewer/regenerate_fixtures.py). Geen netwerk, geen echte foto's, geen externe AI-aanroep."""
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


DEMO_OUTPUTS = ("synthetic_facade_v1.png", "proposal_set.json", "quantity_state.json", "evaluation.json", "review.html", "run_manifest.json")
MOCK_OUTPUTS = ("reference_mock_evaluation.json",)
OUTPUT_NAMES = frozenset(DEMO_OUTPUTS + MOCK_OUTPUTS)


def safe_out_dir(path):
    """Valideert en maakt de uitvoermap. Wordt door run_demo en run_reference_mock zelf aangeroepen (dus ook bij direct gebruik buiten de CLI).

    Weigert (SystemExit): een map in of boven de repository (canonieke lagen), een pad dat geen map is, een map met bestanden die dit
    script niet zelf schrijft (bestaande gevoelige bestanden worden nooit overschreven) en een uitvoerbestand dat een symlink of
    geen gewoon bestand is. Alleen eerdere uitvoer van dit script (OUTPUT_NAMES) wordt bij een herhaalde run vervangen."""
    out = os.path.realpath(path)
    for root in {os.path.realpath(repo_root()), os.path.realpath(ROOT)}:
        if out == root or out.startswith(root + os.sep):
            raise SystemExit(f"WEIGERING: uitvoermap {out} ligt binnen de repository; kies een map erbuiten (testresultaten horen niet in de publieke repo).")
        if root.startswith(out + os.sep):
            raise SystemExit(f"WEIGERING: uitvoermap {out} bevat de repository; kies een eigen lege map erbuiten.")
    if os.path.lexists(out) and not os.path.isdir(out):
        raise SystemExit(f"WEIGERING: {out} is geen map.")
    if os.path.isdir(out):
        foreign = sorted(n for n in os.listdir(out) if n not in OUTPUT_NAMES)
        if foreign:
            raise SystemExit(f"WEIGERING: uitvoermap {out} bevat bestanden die dit script niet schrijft ({', '.join(foreign[:5])}); "
                             "kies een lege map zodat niets bestaands wordt overschreven.")
        for n in OUTPUT_NAMES:
            p = os.path.join(out, n)
            if os.path.lexists(p) and (os.path.islink(p) or not os.path.isfile(p)):
                raise SystemExit(f"WEIGERING: {p} is een symlink of geen gewoon bestand.")
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
    out = safe_out_dir(out)
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


def run_reference_mock(out, reference_set):
    out = safe_out_dir(out)
    if reference_set not in evaluate.REFERENCE_SETS:
        raise SystemExit(f"onbekende referentieset {reference_set!r}; kies uit {sorted(evaluate.REFERENCE_SETS)}")
    ref, meta = evaluate.REFERENCE_SETS[reference_set]()
    # GEMOCKT modelresultaat: kleine afwijkingen, een gemiste opening, een onterecht voorstel; geen echte afbeelding gebruikt.
    prop = []
    missed = max((r["ref_id"] for r in ref if r["element_type"] == "WINDOW_OPENING"), default=None)
    for i, r in enumerate(ref):
        if r["ref_id"] == missed:
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
    write_json(os.path.join(out, "reference_mock_evaluation.json"), {"reference_set": reference_set, "reference_meta": meta, "evaluation": ev})
    return ev


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo").add_argument("--out", required=True, help="uitvoermap BUITEN de repository")
    mock = sub.add_parser("eval-reference-mock")
    mock.add_argument("--out", required=True, help="uitvoermap BUITEN de repository")
    mock.add_argument("--reference-set", required=True, choices=sorted(evaluate.REFERENCE_SETS))
    a = ap.parse_args(argv)
    out = safe_out_dir(a.out)
    if a.cmd == "demo":
        pset, state, ev = run_demo(out)
        print(json.dumps({"set_id": pset["set_id"], "state_id": state["state_id"], "totals": state["totals"], "overall": ev["overall"], "out": out}, indent=2, ensure_ascii=False))
    else:
        ev = run_reference_mock(out, a.reference_set)
        print(json.dumps({"overall": ev["overall"], "out": out}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
