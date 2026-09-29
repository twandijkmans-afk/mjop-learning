#!/usr/bin/env python3
"""
incoming_registry.py - register voor nieuwe (nog niet gepromoveerde) documenten.

Identiteit = sha256 van de bytes. De bestandsnaam en de map zijn alleen metadata.

  - Het canonieke register (reports/document_registry.json, data/raw) wordt ALLEEN gelezen.
  - Een nieuw document krijgt het eerstvolgende vrije DOC-ID: max(canoniek ∪ incoming) + 1.
    Bestaande ID's verschuiven nooit, ID's worden nooit hergebruikt of verwijderd.
  - Een sha256 die al in het canonieke register staat = exacte duplicate (DUPLICATE_SKIP).
  - Een sha256 die al in dit register staat = hetzelfde document (zelfde DOC-ID), geen nieuw ID.
  - Bij een latere promotie verhuist het document met hetzelfde DOC-ID naar data/raw.

Bestand: data/incoming_registry.json (UTF-8, LF, gesorteerd, geen tijdstempels).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import document_registry  # noqa: E402

REGISTRY_VERSION = 1
REGISTRY_PATH = os.path.join("data", "incoming_registry.json")
CANONICAL_REGISTRY_PATH = os.path.join("reports", "document_registry.json")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ENTRY_KEYS = {"document_id", "sha256", "format", "file_size_bytes", "first_batch_id", "first_observed_path"}


class RegistryError(Exception):
    pass


def empty():
    return {"registry_version": REGISTRY_VERSION,
            "note": "Incoming-register: document_id is gekoppeld aan sha256 en verandert nooit; ID's "
                    "worden nooit hergebruikt. Bestandsnamen zijn alleen metadata. Canonieke documenten "
                    "staan in reports/document_registry.json.",
            "documents": []}


def load(path):
    if not os.path.exists(path):
        return empty()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dumps(registry):
    reg = dict(registry)
    reg["documents"] = sorted(reg["documents"], key=lambda d: document_registry._id_num(d["document_id"]))
    return json.dumps(reg, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def integrity_errors(incoming, canonical):
    """Controles die altijd moeten gelden (ook vóór schrijven)."""
    errors = []
    ids, shas = set(), set()
    canon_ids = {d["document_id"] for d in canonical["documents"]}
    canon_shas = {d["sha256"] for d in canonical["documents"]}
    for d in incoming.get("documents", []):
        missing = ENTRY_KEYS - set(d)
        if missing:
            errors.append(f"{d.get('document_id')}: ontbrekende velden {sorted(missing)}")
            continue
        try:
            document_registry._id_num(d["document_id"])
        except document_registry.RegistryError as e:
            errors.append(str(e))
        if not SHA_RE.match(d["sha256"]):
            errors.append(f"{d['document_id']}: ongeldige sha256")
        if d["document_id"] in ids or d["document_id"] in canon_ids:
            errors.append(f"{d['document_id']}: document_id dubbel (of botst met canoniek register)")
        if d["sha256"] in shas or d["sha256"] in canon_shas:
            errors.append(f"{d['document_id']}: sha256 dubbel (of al canoniek geregistreerd)")
        ids.add(d["document_id"])
        shas.add(d["sha256"])
    return errors


def append_only_errors(old, new):
    """Bestaande entries mogen nooit wijzigen of verdwijnen."""
    new_by_id = {d["document_id"]: d for d in new["documents"]}
    errors = []
    for d in old["documents"]:
        if new_by_id.get(d["document_id"]) != d:
            errors.append(f"{d['document_id']}: bestaande registry-entry gewijzigd of verwijderd")
    return errors


def next_id(incoming, canonical):
    nums = [document_registry._id_num(d["document_id"]) for d in canonical["documents"] + incoming["documents"]]
    return (max(nums) if nums else 0) + 1


def lookup(sha, incoming, canonical):
    """Returns ('canonical'|'incoming'|None, entry)."""
    for d in canonical["documents"]:
        if d["sha256"] == sha:
            return "canonical", d
    for d in incoming["documents"]:
        if d["sha256"] == sha:
            return "incoming", d
    return None, None
