"""Building links v1 — historisch MJOP-document <-> BAG-pand(en), uitsluitend door een mens bevestigd.

Zie docs/building_link_3dbag_evidence_v1.md.

  python scripts/building_links.py candidates [--check]       # read-only kandidatenrapport
  python scripts/building_links.py record --document DOC-005 --bag-pand-id 0363100012345678 \
      --snapshot BAGSNAP-... --reviewer twandijkmans --reason "..." [--status CONFIRMED|REJECTED]

Regels:
- Het kandidatenrapport beslist niets: het toont het opgegeven adres (met provenance), de deterministisch
  ontlede adresdelen, de opvraagplanning, kandidaat-panden uit opgeslagen BAG-snapshots en review-redenen.
- Een link is een append-only record per (document_id, bag_pand_id), met een menselijke reviewer.
  Er is geen automatische of fuzzy bevestiging: 'record' vereist een expliciete reviewer, reden, en een
  pand dat in een opgeslagen snapshot voor dit document het exact gevonden adrespunt bevat.
- Meerdere panden per document zijn gewoon meerdere links; er wordt geen één-pand-aanname afgedwongen.
"""

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import append_only_store as aos  # noqa: E402
import bag_snapshots as bs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VERIFIED_DIR = ROOT / "data" / "verified"
DOC_RELATIONS = ROOT / "data" / "price_observations" / "document_relations.json"
COMPARABILITY = ROOT / "data" / "comparability" / "comparability_batch1.json"
LINK_STORE = ROOT / "data" / "building_links" / "building_link_records.json"
OUT_JSON = ROOT / "reports" / "quantity" / "building_link_candidates_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "building_link_candidates_v1.md"

RULE_VERSION = "building_link_rules_v1"
REPORT_VERSION = "building_link_candidates_v1"
SAME_OBJECT_RELATION_TYPES = {"duplicate_source", "version_of_same_mjop", "same_building_other_inspection"}

REVIEW_REASONS = {
    "NO_STATED_ADDRESS": "het document noemt geen adres in het objectblad",
    "ADDRESS_FROM_OBJECT_NAME": "adres alleen afgeleid uit de objectnaam (VvE-naam), niet uit een adresveld",
    "ADDRESS_NOT_PARSED": "adres(deel) niet deterministisch te ontleden",
    "MULTIPLE_STREETS": "meerdere straten: waarschijnlijk meerdere panden",
    "ADDRESS_RANGE": "huisnummerbereik: aantal panden en even/oneven onbekend",
    "POSTCODE_MISSING": "geen postcode in het document",
    "CITY_MISSING": "geen plaats in het document",
    "OBJECT_NAME_ADDRESS_DIFFERS": "adres in de objectnaam verschilt van het adresveld",
    "ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT": "een document over hetzelfde object noemt het adres anders (geen fuzzy gelijkstelling)",
    "SUBPLAN_SCOPE": "deelplan van een complex: de panden kunnen gelijk zijn, de scope van de hoeveelheden niet",
    "NO_BAG_SNAPSHOT": "nog geen BAG/3D BAG-snapshot voor dit document (ophalen vereist netwerktoegang)",
    "SNAPSHOT_WITHOUT_EXACT_ADDRESS_MATCH": "snapshot aanwezig maar geen exact overeenkomend adres",
    "MULTIPLE_CANDIDATE_PANDEN": "meerdere kandidaat-panden: elk pand apart bevestigen of afwijzen",
}


class LinkError(RuntimeError):
    pass


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Adres ontleden (deterministisch)
# --------------------------------------------------------------------------

def parse_address(text):
    """'Alkmaarstraat 1-83 en Groetstraat 189-217' -> [{street, kind, numbers}] of [] bij geen tekst.
    kind: single | range | list | unparsed."""
    if not text or not str(text).strip():
        return []
    parts = [p.strip() for p in re.split(r",|;|\sen\s|\s&\s", str(text)) if p.strip()]
    out = []
    for p in parts:
        m = re.match(r"^(?P<street>.*?[A-Za-zÀ-ÿ.'\-]+)\s+(?P<nums>\d[\d\s\-]*[A-Za-z]?)$", p)
        if not m:
            out.append({"street": None, "kind": "unparsed", "numbers": [], "text": p})
            continue
        street = re.sub(r"\s+", " ", m.group("street")).strip()
        nums = re.sub(r"\s+", "", m.group("nums"))
        if re.fullmatch(r"\d+[A-Za-z]?", nums):
            out.append({"street": street, "kind": "single", "numbers": [nums], "text": p})
        elif re.fullmatch(r"\d+-\d+", nums) and int(nums.split("-")[1]) > int(nums.split("-")[0]):
            a, b = nums.split("-")
            out.append({"street": street, "kind": "range", "numbers": [a, b], "text": p})
        elif re.fullmatch(r"\d+(-\d+){2,}", nums):
            out.append({"street": street, "kind": "list", "numbers": nums.split("-"), "text": p})
        else:
            out.append({"street": street, "kind": "unparsed", "numbers": [], "text": p})
    return out


def normalized_address(parts, postcode, city):
    segs = []
    for p in parts:
        if p["kind"] == "range":
            segs.append(f"{p['street'].lower()} {p['numbers'][0]}-{p['numbers'][1]}")
        elif p["street"]:
            segs.append(f"{p['street'].lower()} {'/'.join(p['numbers'])}")
        else:
            segs.append(p["text"].lower())
    tail = " ".join(x for x in ((postcode or "").replace(" ", "").upper(), (city or "").lower()) if x)
    return "; ".join(segs) + ((" | " + tail) if tail else "")


def lookup_plan(parts, postcode, city):
    """Welke adressen opgevraagd moeten worden. Een bereik ('240 - 296') wordt één range-opvraging
    (bag_snapshots.py fetch-range): alle adressen die PDOK binnen het bereik kent, zonder pariteit-aanname.
    De postcode wordt als filter alleen meegegeven bij één enkel adres; bij een bereik in één straat wordt hij
    meegegeven om per adres vast te leggen of hij overeenkomt (geen filter); bij meerdere straten niet."""
    single = len(parts) == 1 and parts[0]["kind"] == "single"
    one_street = len({p["street"] for p in parts if p["street"]}) == 1
    plan = []
    for p in parts:
        if not p["street"]:
            continue
        if p["kind"] == "range":
            plan.append({"street": p["street"], "kind": "range", "number_from": p["numbers"][0], "number_to": p["numbers"][1],
                         "postcode": postcode if one_street else None, "city": city})
            continue
        for n in p["numbers"]:
            plan.append({"street": p["street"], "number": n, "postcode": postcode if single else None, "city": city})
    return plan


# --------------------------------------------------------------------------
# Invoer
# --------------------------------------------------------------------------

def _val(x):
    return x.get("value") if isinstance(x, dict) else x


def load_documents():
    docs = {}
    for f in sorted(VERIFIED_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        b = d.get("building") or {}
        dl = d.get("document_level_values") or {}
        addr = b.get("address") if isinstance(b.get("address"), dict) else {"value": b.get("address")}
        docs[d["document_id"]] = {
            "address_as_stated": addr.get("value"),
            "address_provenance": addr.get("provenance"),
            "postcode": _val(dl.get("object_postcode")),
            "city": _val(dl.get("object_city")),
            "object_name": _val(dl.get("object_name")),
            "construction_year": _val(b.get("construction_year")),
            "number_of_units": _val(b.get("number_of_units")),
            "verified_sha256": sha_file(f),
        }
    return docs


def load_store(path=LINK_STORE):
    path = Path(path)
    if not path.exists():
        return new_store()
    return json.loads(path.read_text(encoding="utf-8"))


def new_store():
    return {"store_version": "building_link_v1", "append_only": True,
            "description": "Menselijk bevestigde koppelingen historisch document <-> BAG-pand (docs/building_link_3dbag_evidence_v1.md). Append-only; één ACTIVE record per (document_id, bag_pand_id).",
            "records": []}


def active_links(store):
    out = defaultdict(list)
    for r in store["records"]:
        if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED":
            out[r["document_id"]].append(r["bag_pand_id"])
    return {d: sorted(v) for d, v in out.items()}


def store_errors(store):
    return aos.invariant_errors(store["records"], "link_id", lambda r: (r["document_id"], r["bag_pand_id"]))


# --------------------------------------------------------------------------
# Kandidatenrapport
# --------------------------------------------------------------------------

def build_candidates(docs=None, snapshots=None, store=None, relations=None, comparability=None):
    docs = docs if docs is not None else load_documents()
    snapshots = snapshots if snapshots is not None else bs.load_snapshots()
    store = store if store is not None else load_store()
    relations = relations if relations is not None else json.loads(DOC_RELATIONS.read_text(encoding="utf-8"))
    comparability = comparability if comparability is not None else json.loads(COMPARABILITY.read_text(encoding="utf-8"))
    cluster_of = {d: c["source_cluster"] for c in comparability["source_clusters"] for d in c["document_ids"]}
    rel_of = defaultdict(list)
    for r in relations["relations"]:
        ids = r.get("document_ids") or [r["primary_document_id"], r["secondary_document_id"]]
        for d in ids:
            for o in ids:
                if o != d:
                    rel_of[d].append({"relation_id": r["relation_id"], "type": r["type"], "other_document_id": o})
    links = active_links(store)
    snaps_by_doc = defaultdict(list)
    for s in snapshots:
        snaps_by_doc[s["document_id"]].append(s)

    out = []
    for doc_id, d in sorted(docs.items()):
        reasons = []
        parts = parse_address(d["address_as_stated"])
        from_name = False
        if not parts:
            reasons.append("NO_STATED_ADDRESS")
            name_addr = re.sub(r"^(vve|v\.v\.e\.)\s+", "", (d["object_name"] or ""), flags=re.I)
            name_addr = re.sub(r"\s+(hoofddak|woningen)$", "", name_addr, flags=re.I)
            parts = [p for p in parse_address(name_addr) if p["kind"] != "unparsed"]
            if parts:
                from_name = True
                reasons.append("ADDRESS_FROM_OBJECT_NAME")
        else:
            name_parts = parse_address(re.sub(r"^(vve|v\.v\.e\.)\s+", "", (d["object_name"] or ""), flags=re.I))
            name_parsed = [p for p in name_parts if p["kind"] != "unparsed"]
            if name_parsed and [(p["street"].lower(), p["numbers"]) for p in name_parsed] != \
                    [(p["street"].lower(), p["numbers"]) for p in parts if p["street"]]:
                reasons.append("OBJECT_NAME_ADDRESS_DIFFERS")
        if any(p["kind"] == "unparsed" for p in parts):
            reasons.append("ADDRESS_NOT_PARSED")
        if len({p["street"] for p in parts if p["street"]}) > 1:
            reasons.append("MULTIPLE_STREETS")
        if any(p["kind"] in ("range", "list") for p in parts):
            reasons.append("ADDRESS_RANGE")
        if not d["postcode"]:
            reasons.append("POSTCODE_MISSING")
        if not d["city"]:
            reasons.append("CITY_MISSING")
        rels = sorted(rel_of.get(doc_id, []), key=lambda r: (r["relation_id"], r["other_document_id"]))
        same_object = sorted({r["other_document_id"] for r in rels if r["type"] in SAME_OBJECT_RELATION_TYPES and r["other_document_id"] in docs})
        norm_addr = normalized_address(parts, d["postcode"], d["city"])
        for o in same_object:
            od = docs[o]
            if normalized_address(parse_address(od["address_as_stated"]), None, None) != normalized_address(parts, None, None):
                reasons.append("ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT")
        if any(r["type"] == "subplans_same_complex" for r in rels):
            reasons.append("SUBPLAN_SCOPE")
        snaps = sorted(snaps_by_doc.get(doc_id, []), key=lambda s: s["snapshot_id"])
        candidates = {}
        for s in snaps:
            name_of = {m["pdok_id"]: m for m in s["address_matches"]}
            for p in s["panden"]:
                c = candidates.setdefault(p["bag_pand_id"], {"bag_pand_id": p["bag_pand_id"], "snapshot_ids": [],
                                                             "contains_address_point_of": [], "addresses": [],
                                                             "bag_properties": p.get("bag_properties"),
                                                             "has_3dbag_attributes": bool((p.get("threedbag") or {}).get("attributes"))})
                c["snapshot_ids"].append(s["snapshot_id"])
                c["contains_address_point_of"] += p["contains_address_point_of"]
                for pid in p["contains_address_point_of"]:
                    m = name_of.get(pid) or {}
                    a = {"weergavenaam": m.get("weergavenaam"), "postcode": m.get("postcode"),
                         "postcode_matches_document": m.get("postcode_matches_document")}
                    if a not in c["addresses"]:
                        c["addresses"].append(a)
        for c in candidates.values():
            c["snapshot_ids"] = sorted(set(c["snapshot_ids"]))
            c["contains_address_point_of"] = sorted(set(c["contains_address_point_of"]))
            c["addresses"] = sorted(c["addresses"], key=lambda a: a["weergavenaam"] or "")
        if not snaps:
            reasons.append("NO_BAG_SNAPSHOT")
        elif not any(m["exact_match"] for s in snaps for m in s["address_matches"]):
            reasons.append("SNAPSHOT_WITHOUT_EXACT_ADDRESS_MATCH")
        if len(candidates) > 1:
            reasons.append("MULTIPLE_CANDIDATE_PANDEN")
        cluster = cluster_of.get(doc_id)
        cluster_links = sorted({p for od, ps in links.items() if cluster_of.get(od) == cluster and od != doc_id for p in ps})
        if links.get(doc_id):
            status = "LINKED"
        elif not parts:
            status = "NO_ADDRESS"
        elif not snaps:
            status = "AWAITING_BAG_SNAPSHOT"
        elif candidates:
            status = "CANDIDATES_READY_FOR_REVIEW"
        else:
            status = "NO_CANDIDATE_PANDEN"
        out.append({
            "document_id": doc_id,
            "address_as_stated": d["address_as_stated"],
            "address_provenance": d["address_provenance"],
            "address_from_object_name": from_name,
            "object_name": d["object_name"],
            "postcode": d["postcode"],
            "city": d["city"],
            "construction_year": d["construction_year"],
            "number_of_units": d["number_of_units"],
            "parsed_address": parts,
            "normalized_address": norm_addr,
            "lookup_plan": lookup_plan(parts, d["postcode"], d["city"]),
            "source_cluster": cluster,
            "document_relations": rels,
            "same_object_document_ids": same_object,
            "confirmed_links_in_same_source_cluster": cluster_links,
            "snapshot_ids": [s["snapshot_id"] for s in snaps],
            "candidate_bag_panden": [candidates[k] for k in sorted(candidates)],
            "confirmed_bag_pand_ids": links.get(doc_id, []),
            "review_reasons": sorted(set(reasons)),
            "status": status,
        })
    summary = {
        "documents": len(out),
        "by_status": {s: sum(1 for o in out if o["status"] == s) for s in sorted({o["status"] for o in out})},
        "confirmed_links": sum(len(v) for v in links.values()),
        "documents_with_multiple_confirmed_panden": sorted(d for d, v in links.items() if len(v) > 1),
        "review_reasons": {r: sum(1 for o in out if r in o["review_reasons"]) for r in sorted({r for o in out for r in o["review_reasons"]})},
    }
    return {"report_version": REPORT_VERSION, "rule_version": RULE_VERSION,
            "note": "Read-only kandidatenrapport. Beslist niets; een link ontstaat alleen via 'building_links.py record' door een mens.",
            "vocabulary": REVIEW_REASONS,
            "input_hashes": {"verified_sha256": {k: v["verified_sha256"] for k, v in sorted(docs.items())},
                             "snapshot_ids": sorted(s["snapshot_id"] for s in snapshots),
                             "link_store_sha256": canonical_sha256(store)},
            "summary": summary, "documents": out}


def render_candidates(rep):
    s = rep["summary"]
    L = ["# Building link candidates v1", "",
         "Read-only. Dit rapport bevestigt niets; een link ontstaat alleen door een menselijk besluit "
         "(`scripts/building_links.py record`). Zie `docs/building_link_3dbag_evidence_v1.md`.", "",
         f"- Documenten: {s['documents']}",
         f"- Status: " + ", ".join(f"{k} {v}" for k, v in s["by_status"].items()),
         f"- Bevestigde links (ACTIVE): {s['confirmed_links']}",
         f"- Documenten met meerdere bevestigde panden: {', '.join(s['documents_with_multiple_confirmed_panden']) or '—'}", "",
         "| Document | Adres (zoals vermeld) | Postcode | Plaats | Cluster | Kandidaat-panden | Status | Review-redenen |",
         "|---|---|---|---|---|---|---|---|"]
    for o in rep["documents"]:
        addr = o["address_as_stated"] or (f"({o['object_name']})" if o["object_name"] else "—")
        cands = ", ".join(c["bag_pand_id"] for c in o["candidate_bag_panden"]) or "—"
        L.append(f"| {o['document_id']} | {addr} | {o['postcode'] or '—'} | {o['city'] or '—'} | {o['source_cluster'] or '—'} | "
                 f"{cands} | {o['status']} | {', '.join(o['review_reasons'])} |")
    L += ["", "## Opvraagplanning (voor het ophalen van snapshots)", ""]
    for o in rep["documents"]:
        if o["lookup_plan"]:
            L.append(f"- {o['document_id']}: " + "; ".join(
                (f"{p['street']} {p['number_from']}-{p['number_to']} (bereik, fetch-range)" if p.get("kind") == "range"
                 else f"{p['street']} {p['number']}")
                + (f" {p['postcode']}" if p["postcode"] else "") + (f" {p['city']}" if p["city"] else "")
                for p in o["lookup_plan"]))
    for o in rep["documents"]:
        if not o["candidate_bag_panden"]:
            continue
        L += ["", f"## Kandidaat-panden {o['document_id']} (beslist niets)", "",
              "| BAG-pand | Adressen in het pand | Postcode = document? | 3D BAG |", "|---|---|---|---|"]
        for c in o["candidate_bag_panden"]:
            pc = sorted({str(a.get("postcode_matches_document")) for a in c.get("addresses", [])})
            L.append(f"| {c['bag_pand_id']} | {', '.join(a['weergavenaam'] or '?' for a in c.get('addresses', []))} | "
                     f"{'/'.join(pc) or '—'} | {'ja' if c['has_3dbag_attributes'] else 'nee'} |")
    L += ["", "## Review-redenen", "", "| Reden | Documenten | Betekenis |", "|---|---|---|"]
    L += [f"| `{k}` | {v} | {REVIEW_REASONS[k]} |" for k, v in s["review_reasons"].items()]
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# Menselijk besluit vastleggen
# --------------------------------------------------------------------------

def record_link(store, *, document_id, bag_pand_id, snapshot, reviewer_id, reason, reviewed_at,
                link_status="CONFIRMED", documents=None, candidates_report_sha256=None):
    """Pure functie: geeft een nieuwe store terug met één extra record (en het vorige ACTIVE record van
    dezelfde (document, pand) SUPERSEDED). Weigert zonder reviewer/reden, bij een snapshot van een ander
    document, of bij een pand dat niet als kandidaat in de snapshot staat."""
    if not reviewer_id or not str(reviewer_id).strip():
        raise LinkError("reviewer is verplicht (een link is altijd een menselijk besluit)")
    if not reason or not str(reason).strip():
        raise LinkError("reden is verplicht")
    if link_status not in ("CONFIRMED", "REJECTED"):
        raise LinkError("link_status moet CONFIRMED of REJECTED zijn")
    errs = bs.snapshot_errors(snapshot)
    if errs:
        raise LinkError("; ".join(errs))
    if snapshot["document_id"] != document_id:
        raise LinkError(f"snapshot {snapshot['snapshot_id']} hoort bij {snapshot['document_id']}, niet bij {document_id}")
    pand = next((p for p in snapshot["panden"] if p["bag_pand_id"] == str(bag_pand_id)), None)
    if pand is None:
        raise LinkError(f"pand {bag_pand_id} is geen kandidaat in snapshot {snapshot['snapshot_id']} (geen vrij ingetypte ID's)")
    docs = documents if documents is not None else load_documents()
    d = docs.get(document_id)
    if d is None:
        raise LinkError(f"onbekend document {document_id}")
    out = copy.deepcopy(store)
    previous = [r for r in out["records"] if r["document_id"] == document_id and r["bag_pand_id"] == str(bag_pand_id)
                and r["status"] in ("ACTIVE", "REVIEW_REQUIRED")]
    if len(previous) > 1:
        raise LinkError("meer dan één geldend record voor dit document + pand")
    parts = parse_address(d["address_as_stated"])
    record = {
        "link_id": aos.next_id(out["records"], "link_id", "BLINK"),
        "document_id": document_id,
        "bag_pand_id": str(bag_pand_id),
        "link_status": link_status,
        "address_as_stated": d["address_as_stated"],
        "normalized_address": normalized_address(parts, d["postcode"], d["city"]),
        "evidence": {
            "snapshot_id": snapshot["snapshot_id"],
            "address_matches_containing_pand": pand["contains_address_point_of"],
            "address_provenance": d["address_provenance"],
            "bag_properties": pand.get("bag_properties"),
        },
        "decision_reason": reason,
        "reviewer": {"reviewer_id": reviewer_id, "reviewer_type": "human"},
        "reviewed_at": reviewed_at,
        "rule_version": RULE_VERSION,
        "input_hashes": {"verified_sha256": d["verified_sha256"], "snapshot_id": snapshot["snapshot_id"],
                         "candidates_report_sha256": candidates_report_sha256},
        "supersedes": previous[0]["link_id"] if previous else None,
        "status": "ACTIVE",
    }
    for r in previous:
        r["status"] = "SUPERSEDED"
    out["records"].append(record)
    errs = store_errors(out) + aos.append_only_errors(store["records"], out["records"], "link_id")
    if errs:
        raise LinkError("; ".join(errs))
    return out


def write_store(store, path=LINK_STORE):
    path = Path(path)
    old = load_store(path)
    errs = store_errors(store) + aos.append_only_errors(old["records"], store["records"], "link_id")
    if errs:
        raise LinkError("; ".join(errs))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Building links v1")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--check", action="store_true")
    r = sub.add_parser("record")
    r.add_argument("--document", required=True)
    r.add_argument("--bag-pand-id", required=True, action="append")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--reviewer", required=True)
    r.add_argument("--reason", required=True)
    r.add_argument("--status", default="CONFIRMED", choices=["CONFIRMED", "REJECTED"])
    args = ap.parse_args(argv)
    if args.cmd == "candidates":
        rep = build_candidates()
        js, md = dumps(rep), render_candidates(rep)
        if args.check:
            ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
            print("building link candidates up-to-date" if ok else "building link candidates NIET up-to-date")
            return 0 if ok else 1
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
        OUT_MD.write_text(md, encoding="utf-8", newline="\n")
        print(f"{rep['summary']['documents']} documenten; {rep['summary']['by_status']}")
        return 0
    snap_path = bs.SNAPSHOT_DIR / f"{args.snapshot}.json"
    if not snap_path.exists():
        print(f"snapshot {args.snapshot} niet gevonden in {bs.SNAPSHOT_DIR}", file=sys.stderr)
        return 2
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    store = load_store()
    rep_sha = sha_file(OUT_JSON) if OUT_JSON.exists() else None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        for pid in args.bag_pand_id:
            store = record_link(store, document_id=args.document, bag_pand_id=pid, snapshot=snapshot, reviewer_id=args.reviewer,
                                reason=args.reason, reviewed_at=now, link_status=args.status, candidates_report_sha256=rep_sha)
        write_store(store)
    except LinkError as e:
        print(f"FOUT: {e}", file=sys.stderr)
        return 2
    print(f"vastgelegd: {', '.join(args.bag_pand_id)} voor {args.document} ({args.status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
