#!/usr/bin/env python3
"""
xpdf_runner_setup.py - installeert en verifieert xpdf pdftotext 4.06 op een cloud-runner (GitHub Actions).

Er is bewust geen fallback naar poppler of een andere PDF-parser. Stappen:

  1. archief downloaden van een vastgepinde URL (config/xpdf_pin.json), sha256 berekenen;
     is er een gepinde sha256, dan MOET die kloppen (anders FAILED_RUNNER_SETUP);
  2. alleen de pdftotext-binary uitpakken, `pdftotext -v` moet exact de verwachte versieregel geven;
  3. (--verify-reproduction) de canonieke batch-1-documenten opnieuw deterministisch extraheren en
     de canonical_content_sha256 vergelijken met data/extracted_deterministic/batch1_v1/manifest.json
     (de lokaal onder Windows gevalideerde xpdf-4.06-uitvoer).

Status in runner_setup.json:
  VERIFIED_RUNNER_SETUP     gepinde sha256 klopt, versie klopt en alle reproducties zijn identiek
  UNVERIFIED_RUNNER_SETUP   versie klopt, maar sha256 nog niet gepind en/of reproductie wijkt af
  FAILED_RUNNER_SETUP       download, checksum of versie faalt -> geen xpdf voor de pipeline

Geen AI, geen andere netwerkverbindingen dan de download zelf.
"""
import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

PIN = os.path.join(ROOT, "config", "xpdf_pin.json")
HANDOFF = os.path.join(ROOT, "data", "extracted_deterministic", "batch1_v1", "manifest.json")


def load_pin(path=PIN):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def download(urls, timeout=120):
    errors = []
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return url, r.read(), errors
        except Exception as e:  # netwerk/HTTP-fout: volgende gepinde URL
            errors.append(f"{url}: {type(e).__name__}: {e}")
    return None, None, errors


def extract_binary(archive_bytes, suffix, dest_dir):
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.isfile() and m.name.endswith("/" + suffix)), None)
        if member is None:
            raise RuntimeError(f"{suffix} niet gevonden in het archief")
        data = tar.extractfile(member).read()
    os.makedirs(dest_dir, exist_ok=True)
    target = os.path.join(dest_dir, "pdftotext")
    with open(target, "wb") as f:
        f.write(data)
    os.chmod(target, 0o755)
    return target, member.name


def version_line(binary):
    out = subprocess.run([binary, "-v"], capture_output=True, text=True)
    text = ((out.stdout or "") + (out.stderr or "")).strip()
    return text.splitlines()[0] if text else None


def json_diff(expected, observed, path="", out=None, limit=40):
    """Compacte lijst verschillen (pad, verwacht, waargenomen) voor diagnose in de CI-log."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(expected, dict) and isinstance(observed, dict):
        for k in sorted(set(expected) | set(observed)):
            if k not in expected or k not in observed:
                out.append({"path": f"{path}/{k}", "expected": repr(expected.get(k))[:160],
                            "observed": repr(observed.get(k))[:160]})
            else:
                json_diff(expected[k], observed[k], f"{path}/{k}", out, limit)
    elif isinstance(expected, list) and isinstance(observed, list) and len(expected) == len(observed):
        for i, (a, b) in enumerate(zip(expected, observed)):
            json_diff(a, b, f"{path}[{i}]", out, limit)
    elif expected != observed:
        out.append({"path": path, "expected": repr(expected)[:160], "observed": repr(observed)[:160]})
    return out[:limit]


def verify_reproduction(binary, version):
    import deterministic_extraction as de
    import promote_deterministic_batch as pdb
    manifest = json.load(open(HANDOFF, encoding="utf-8"))
    results = []
    for entry in manifest["documents"]:
        did = entry["document_id"]
        if not entry.get("canonical_content_sha256"):      # bijv. DOC-003 (DUPLICATE_SKIP): geen extractie
            results.append({"document_id": did, "skipped": entry.get("status") or "NO_REFERENCE_HASH",
                            "identical": None})
            continue
        try:
            record = de.extract_document(did, ROOT, binary, version)
            got = pdb.canonical_content_sha256(record)
            res = {"document_id": did, "expected": entry["canonical_content_sha256"], "observed": got,
                   "identical": got == entry["canonical_content_sha256"]}
            if not res["identical"] and entry.get("output_path"):
                ref = os.path.join(ROOT, *entry["output_path"].split("/"))
                if os.path.exists(ref):
                    res["diff"] = json_diff(json.load(open(ref, encoding="utf-8")), record)
            results.append(res)
        except Exception as e:
            results.append({"document_id": did, "expected": entry["canonical_content_sha256"], "observed": None,
                            "identical": False, "error": f"{type(e).__name__}: {e}"})
    return results


def setup(dest_dir, pin, reproduce=False, fetch=download):
    info = {"pinned_sha256": pin.get("sha256"), "archive_name": pin["archive_name"], "url": None,
            "observed_archive_sha256": None, "archive_member": None, "binary": None, "version_line": None,
            "expected_version_line": pin["expected_version_line"], "reproduction": None, "reasons": []}
    url, data, errors = fetch(pin["urls"])
    info["download_errors"] = errors
    if data is None:
        info["reasons"].append("DOWNLOAD_FAILED")
        info["status"] = "FAILED_RUNNER_SETUP"
        return info
    info["url"] = url
    info["observed_archive_sha256"] = hashlib.sha256(data).hexdigest()
    if pin.get("sha256") and pin["sha256"] != info["observed_archive_sha256"]:
        info["reasons"].append("ARCHIVE_SHA256_MISMATCH")
        info["status"] = "FAILED_RUNNER_SETUP"
        return info
    try:
        binary, member = extract_binary(data, pin["binary_suffix_in_archive"], dest_dir)
    except Exception as e:
        info["reasons"].append(f"EXTRACT_FAILED: {e}")
        info["status"] = "FAILED_RUNNER_SETUP"
        return info
    info.update(binary=binary, archive_member=member, version_line=version_line(binary))
    if info["version_line"] != pin["expected_version_line"]:
        info["reasons"].append("VERSION_MISMATCH")
        info["status"] = "FAILED_RUNNER_SETUP"
        return info
    if not pin.get("sha256"):
        info["reasons"].append("ARCHIVE_SHA256_NOT_PINNED")
    if reproduce:
        try:
            info["reproduction"] = verify_reproduction(binary, info["version_line"])
        except Exception as e:  # reproductiecontrole kan de installatie nooit stilletjes goedkeuren
            info["reproduction"] = [{"error": f"{type(e).__name__}: {e}", "identical": False, "document_id": None}]
        checked = [r for r in info["reproduction"] if r["identical"] is not None]
        bad = [str(r["document_id"]) for r in checked if not r["identical"]]
        if not checked:
            info["reasons"].append("REPRODUCTION_NOTHING_CHECKED")
        if bad:
            info["reasons"].append("REPRODUCTION_MISMATCH:" + ",".join(bad))
    else:
        info["reasons"].append("REPRODUCTION_NOT_CHECKED")
    info["status"] = "UNVERIFIED_RUNNER_SETUP" if info["reasons"] else "VERIFIED_RUNNER_SETUP"
    return info


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", required=True, metavar="DIR", help="map voor de pdftotext-binary")
    ap.add_argument("--out", required=True, help="pad voor runner_setup.json")
    ap.add_argument("--verify-reproduction", action="store_true")
    args = ap.parse_args(argv)
    info = setup(args.install, load_pin(), reproduce=args.verify_reproduction)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: info[k] for k in ("status", "reasons", "url", "observed_archive_sha256", "version_line")},
                     ensure_ascii=False, indent=2))
    if info["reproduction"]:
        for r in info["reproduction"]:
            state = {True: "IDENTIEK", False: "AFWIJKEND", None: f"OVERGESLAGEN ({r.get('skipped')})"}[r["identical"]]
            print(f"  {r['document_id']}: {state} {r.get('error', '')}")
            for d in r.get("diff", []):
                print(f"      {d['path']}: verwacht {d['expected']} | runner {d['observed']}")
    return 0   # de status staat in runner_setup.json; de pipeline beslist wat er mag


if __name__ == "__main__":
    sys.exit(main())
