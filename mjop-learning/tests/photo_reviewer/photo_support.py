"""Hulpfuncties (eigen modulenaam: voorkomt botsing met tests/agent_tools/support.py): synthetische fixtures laden, een geldige voorstelset bouwen, en een hash-manifest van de canonieke lagen."""
import copy
import hashlib
import json
import os

from agent.photo.contract import PROJECT_ROOT
from agent.photo.providers import ReplayProvider, VisionRequest, build_proposal_set

FIX = os.path.join(PROJECT_ROOT, "tests", "fixtures", "photo_reviewer")


def load_json(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def png():
    with open(os.path.join(FIX, "synthetic_facade_v1.png"), "rb") as f:
        return f.read()


def request(data=None):
    data = data or png()
    sha = hashlib.sha256(data).hexdigest()
    return VisionRequest(photo_id="synthetic_facade_v1", source_sha256=sha, derivative_sha256=sha, width_px=640, height_px=480,
                         image_bytes=data, media_type="image/png", derivative_transform=("SYNTHETIC",))


def proposal_set():
    req = request()
    provider = ReplayProvider.from_file(os.path.join(FIX, "synthetic_facade_v1_replay.json"))
    return build_proposal_set(req, provider.analyze(req))


def fresh():
    return copy.deepcopy(proposal_set())


def reseal(doc):
    from agent.photo.verifier import seal_set
    return seal_set(doc)


def dims():
    return copy.deepcopy(load_json("synthetic_facade_v1_dimension_input.json"))


def tree_manifest(root=PROJECT_ROOT, dirs=("data", "reports", "vocabularies", "config")):
    out = {}
    for d in dirs:
        for dp, _, files in os.walk(os.path.join(root, d)):
            for f in files:
                p = os.path.join(dp, f)
                with open(p, "rb") as fh:
                    out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out
