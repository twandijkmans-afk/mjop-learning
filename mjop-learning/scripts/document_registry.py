#!/usr/bin/env python3
"""
document_registry.py - permanent register van document-ID's op basis van sha256.

Waarom: document_id is de basis van alle provenance. Eerder werden ID's
afgeleid van de volgorde van os.walk; een nieuw bestand in data/raw/ kon dan
alle bestaande ID's laten verschuiven. Dit register maakt ID's permanent:

  - Een geregistreerd document houdt voor altijd zijn ID (sleutel = sha256).
  - Nieuwe documenten krijgen max(ID)+1, in gesorteerde padvolgorde, en ALLEEN
    als dat expliciet wordt gevraagd (register_new=True) - geen stille import.
  - ID's worden nooit hergebruikt of verwijderd.
  - Een bekend pad met een andere sha256 = data/raw/ is aangepast -> fout.

Bestand: reports/document_registry.json

Gebruik:
    python3 scripts/document_registry.py --check
    python3 scripts/document_registry.py --register-new   (alleen met toestemming)
"""
import argparse
import hashlib
import json
import os
import re
import sys

REGISTRY_VERSION = 1
ID_RE = re.compile(r"^DOC-(\d{3,})$")


class RegistryError(Exception):
    pass


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def list_raw_files(raw_dir):
    """Alle bestanden onder raw_dir, gesorteerd op relatief pad (deterministisch)."""
    out = []
    for root, dirs, files in os.walk(raw_dir):
        dirs.sort()
        for fn in sorted(files):
            if fn.lower() == "thumbs.db" or fn.startswith("."):
                continue
            out.append(os.path.relpath(os.path.join(root, fn), raw_dir))
    return sorted(out)


def load_registry(path):
    if not os.path.exists(path):
        return {"registry_version": REGISTRY_VERSION, "documents": []}
    with open(path) as f:
        return json.load(f)


def save_registry(registry, path):
    registry["documents"] = sorted(registry["documents"], key=lambda d: _id_num(d["document_id"]))
    with open(path, "w") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _id_num(doc_id):
    m = ID_RE.match(doc_id)
    if not m:
        raise RegistryError(f"ongeldig document_id: {doc_id}")
    return int(m.group(1))


def by_id(registry):
    return {d["document_id"]: d for d in registry["documents"]}


def get_document(registry, document_id):
    doc = by_id(registry).get(document_id)
    if doc is None:
        raise RegistryError(f"{document_id} staat niet in het document registry")
    return doc


def reconcile(registry, raw_dir, register_new=False):
    """Vergelijk data/raw/ met het register.

    Retourneert (registry, report). Muteert het register alleen als
    register_new=True en er nieuwe bestanden zijn.
    """
    by_sha = {d["sha256"]: d for d in registry["documents"]}
    by_path = {d["relative_path"]: d for d in registry["documents"]}
    report = {"unchanged": [], "new": [], "modified": [], "missing": [], "duplicate_content": []}

    seen_paths = set()
    new_files = []
    for rel in list_raw_files(raw_dir):
        seen_paths.add(rel)
        sha = sha256_of(os.path.join(raw_dir, rel))
        known_path = by_path.get(rel)
        if known_path is not None:
            if known_path["sha256"] != sha:
                report["modified"].append({"relative_path": rel, "document_id": known_path["document_id"]})
            else:
                report["unchanged"].append(known_path["document_id"])
            continue
        if sha in by_sha:
            report["duplicate_content"].append({"relative_path": rel, "same_as": by_sha[sha]["document_id"]})
            continue
        new_files.append((rel, sha))

    for d in registry["documents"]:
        if d["relative_path"] not in seen_paths:
            report["missing"].append(d["document_id"])

    if report["modified"]:
        raise RegistryError(
            "Bestanden in data/raw/ zijn gewijzigd t.o.v. het register (nooit toegestaan): "
            f"{report['modified']}"
        )

    if new_files and not register_new:
        report["new"] = [{"relative_path": rel, "document_id": None} for rel, _ in new_files]
        return registry, report

    next_num = max([_id_num(d["document_id"]) for d in registry["documents"]] or [0]) + 1
    for rel, sha in new_files:  # al gesorteerd op pad
        doc_id = f"DOC-{next_num:03d}"
        next_num += 1
        registry["documents"].append({
            "document_id": doc_id,
            "relative_path": rel,
            "filename": os.path.basename(rel),
            "project_folder": rel.split(os.sep)[0],
            "sha256": sha,
            "file_size_bytes": os.path.getsize(os.path.join(raw_dir, rel)),
            "inventaris_document_id": None,
        })
        report["new"].append({"relative_path": rel, "document_id": doc_id})
    return registry, report


def verify_file(registry, document_id, raw_dir):
    """Controleer vóór het lezen dat het bronbestand exact het geregistreerde is."""
    doc = get_document(registry, document_id)
    path = os.path.join(raw_dir, doc["relative_path"])
    if not os.path.exists(path):
        raise RegistryError(f"{document_id}: bronbestand ontbreekt: {path}")
    actual = sha256_of(path)
    if actual != doc["sha256"]:
        raise RegistryError(f"{document_id}: sha256 wijkt af van register - data/raw/ is aangepast")
    return path, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--registry", default="reports/document_registry.json")
    ap.add_argument("--check", action="store_true", help="alleen controleren, niets schrijven")
    ap.add_argument("--register-new", action="store_true",
                    help="nieuwe bestanden een nieuw ID geven (alleen met expliciete toestemming)")
    args = ap.parse_args()

    registry = load_registry(args.registry)
    try:
        registry, report = reconcile(registry, args.raw_dir, register_new=args.register_new and not args.check)
    except RegistryError as e:
        print(f"FOUT: {e}", file=sys.stderr)
        sys.exit(2)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.register_new and not args.check and any(n["document_id"] for n in report["new"]):
        save_registry(registry, args.registry)
        print(f"Register bijgewerkt: {args.registry}")
    elif report["new"]:
        print("Er staan ongeregistreerde bestanden in data/raw/. Registreer ze alleen met "
              "expliciete toestemming (--register-new).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
