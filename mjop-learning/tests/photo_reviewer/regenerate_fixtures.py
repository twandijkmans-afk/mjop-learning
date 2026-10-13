#!/usr/bin/env python3
"""ONTWIKKELAARSHULP (geen onderdeel van de demo- of productieflow): genereert de synthetische Photo Reviewer-fixtures opnieuw.

Dit is het enige pad dat in tests/fixtures/photo_reviewer/ schrijft. Het staat bewust niet in scripts/photo_reviewer_demo.py.
Schrijven vereist ALLE drie: de omgevingsvariabele MJOP_PHOTO_REGENERATE_FIXTURES=1, het argument --confirm-overwrite-fixtures en
een doelmap die exact de fixturemap is. Zonder die voorwaarden wordt niets geschreven. De inhoud is deterministisch
(build_fixture_files() is zuiver en wordt in de tests vergeleken met de gecommitte fixtures)."""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.photo import synthetic  # noqa: E402
from agent.photo.contract import sha256_bytes  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "photo_reviewer")
ENV_FLAG = "MJOP_PHOTO_REGENERATE_FIXTURES"


def _json_bytes(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def build_fixture_files():
    """Zuiver: geeft {bestandsnaam: bytes} terug zonder iets te schrijven."""
    png = synthetic.png_bytes()
    return {"synthetic_facade_v1.png": png,
            "synthetic_facade_v1_replay.json": _json_bytes(synthetic.model_like_recording(sha256_bytes(png))),
            "synthetic_facade_v1_ground_truth.json": _json_bytes({"photo_id": "synthetic_facade_v1", "ground_truth": synthetic.GROUND_TRUTH})}


def write_fixtures(target=FIX, *, confirmed=False, env=None):
    env = os.environ if env is None else env
    if not confirmed or env.get(ENV_FLAG) != "1":
        raise SystemExit(f"WEIGERING: fixtures herschrijven vereist {ENV_FLAG}=1 en --confirm-overwrite-fixtures.")
    if os.path.realpath(target) != os.path.realpath(FIX):
        raise SystemExit("WEIGERING: alleen de fixturemap tests/fixtures/photo_reviewer/ mag worden herschreven.")
    files = build_fixture_files()
    for name, data in files.items():
        with open(os.path.join(FIX, name), "wb") as f:
            f.write(data)
    return sorted(files)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirm-overwrite-fixtures", action="store_true")
    a = ap.parse_args(argv)
    names = write_fixtures(confirmed=a.confirm_overwrite_fixtures)
    print("fixtures geschreven:", ", ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
