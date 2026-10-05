"""Validator voor MJOP-App-hoeveelhedenbundels (scripts/export_app_quantity_bundle.py), met nadruk op v3.

Controleert een bundel tegen de canonieke stores (read-only):
  - schema/versie en gebouwscope (consistent, geen dubbele pand-ID's, optioneel exact aantal panden);
  - elk scope-aggregaat = exacte Decimal-som van zijn components; components = alle panden van de scope;
  - historische context: complexniveau, role RELATED_CONTEXT, selectable false, ander onderwerp dan het
    kiesbare onderwerp, zelfde eenheid als het kiesbare onderwerp, relatie RELATED_NOT_EQUIVALENT en niet
    resolveerbaar als dezelfde hoeveelheid;
  - geen automatisch gekozen evidence en geen resolved quantity in de bundel; geen ACTIVE quantity resolution
    voor de scope in data/quantity_resolutions;
  - alle evidence-, child-, snapshot-, building-link- en quantity-observation-verwijzingen bestaan, en waarde,
    eenheid, methode en status in de bundel zijn gelijk aan de canonieke evidence;
  - de afhankelijkheid tussen documenten van hetzelfde object (source cluster) is behouden;
  - geen secrets/API-sleutels in de export;
  - meerdere app-elementen: elke PRIMARY volgt uit een geverifieerde app-mapping (XW-/XQ-) met precies dat
    app-element en onderwerp, hoogstens één PRIMARY per (app-element, onderwerp), nooit een onderwerp met product_role
    INFRASTRUCTURE_ONLY/CONTEXT_ONLY; elke RELATED_CONTEXT heeft een effectief geverifieerde onderwerp-mapping (HSM)
    van exact dat onderwerp die de quantity observation nog steeds exact matcht, een vastgelegde relatie
    RELATED_NOT_EQUIVALENT met het PRIMARY-onderwerp van hetzelfde app-element, en dezelfde eenheid. Een gedeelde
    element_code is nooit genoeg.

    python scripts/validate_app_quantity_bundle.py reports/quantity/app_bundles/maldenhof_DOC-005_DOC-006_v3.json \
        [--expect-panden 15] [--check-export]

--check-export: exporteert opnieuw en eist een byte-identieke bundel (determinisme / up-to-date).
"""

import argparse
from collections import Counter
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESOLUTIONS = ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json"
VERSIONS = (eab.BUNDLE_VERSION, eab.BUNDLE_VERSION_MULTI, eab.BUNDLE_VERSION_RELATED)
FORBIDDEN_KEYS = {"selected", "selected_evidence_id", "selectedEvidenceId", "resolved_value", "resolved_unit",
                  "resolution_id", "quantity_resolution", "manual", "confirmed"}
SECRET_RE = re.compile(r"(sk-ant-[A-Za-z0-9_\-]{8,}|sk-[A-Za-z0-9]{20,}|api[_-]?key|authorization|bearer\s|password|secret)", re.I)


def bundle_bytes(bundle):
    return (json.dumps(bundle, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def validate(bundle, evidence_store=None, link_store=None, snapshots=None, qos=None, resolutions=None, expect_panden=None,
             subjects_vocab=None):
    """Geeft een lijst fouten (leeg = geldig)."""
    errs = []
    evidence_store = evidence_store if evidence_store is not None else json.loads(bqe.OUT_EVIDENCE.read_text(encoding="utf-8"))
    link_store = link_store if link_store is not None else bl.load_store()
    snap_ids = {s["snapshot_id"] for s in (snapshots if snapshots is not None else bs.load_snapshots())}
    qo_list = qos if qos is not None else json.loads(bqe.QO_PATH.read_text(encoding="utf-8"))["observations"]
    qo_ids = {o["quantity_observation_id"] for o in qo_list}
    qo_by_id = {o["quantity_observation_id"]: o for o in qo_list}
    vocab = subjects_vocab if subjects_vocab is not None else json.loads(xw.SUBJECTS.read_text(encoding="utf-8"))
    roles = {x["subject_key"]: x.get("product_role") for x in vocab.get("subjects", [])}
    hsm_by_id = {m["mapping_id"]: m for m in vocab.get("historical_subject_mappings", [])}
    proposals = xw.load_proposals()
    eff = xw.effective()
    resolutions = resolutions if resolutions is not None else json.loads(RESOLUTIONS.read_text(encoding="utf-8"))
    ev_by_id = {e["evidence_id"]: e for e in evidence_store["evidence"]}
    link_ids = {r["link_id"] for r in link_store["records"]}

    version = bundle.get("bundle_version")
    if version not in VERSIONS:
        return [f"onbekende bundle_version {version!r}"]
    bid, pids = bundle.get("building_id"), [str(p) for p in bundle.get("bag_pand_ids") or []]
    if len(set(pids)) != len(pids):
        errs.append("dubbele pand-ID's in bag_pand_ids")
    if not pids or bid != bqe.building_id_for(pids):
        errs.append("building_id past niet bij de gesorteerde, ontdubbelde bag_pand_ids")
    if expect_panden is not None and len(pids) != expect_panden:
        errs.append(f"gebouwscope heeft {len(pids)} panden, verwacht {expect_panden}")
    scope = bundle.get("building_scope")
    if version != eab.BUNDLE_VERSION:
        if not scope or scope.get("building_id") != bid or scope.get("bag_pand_ids") != pids or scope.get("pand_count") != len(pids):
            errs.append("building_scope is niet consistent met building_id/bag_pand_ids")
    confirmed = {r["bag_pand_id"] for r in link_store["records"] if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED"}
    if not set(pids) <= confirmed:
        errs.append("scope bevat panden zonder ACTIVE + CONFIRMED building link: " + ", ".join(sorted(set(pids) - confirmed)))

    for k in _walk_keys(bundle):
        if k in FORBIDDEN_KEYS:
            errs.append(f"verboden sleutel {k!r}: een bundel bevat geen keuze of resolutie")
    text = bundle_bytes(bundle).decode("utf-8")
    if SECRET_RE.search(text):
        errs.append("mogelijk secret/API-sleutel in de bundel")

    entries = bundle.get("entries") or []
    if not entries:
        errs.append("bundel zonder entries")
    primary = [e for e in entries if e.get("role", "PRIMARY") == "PRIMARY"]
    context = [e for e in entries if e.get("role") == "RELATED_CONTEXT"]
    if version == eab.BUNDLE_VERSION_RELATED and not context:
        errs.append("v3-bundel zonder RELATED_CONTEXT-regels")
    if version != eab.BUNDLE_VERSION_RELATED and (context or any("role" in e for e in entries)):
        errs.append("role/RELATED_CONTEXT alleen in v3")
    primary_subjects = {e["subject_key"] for e in primary}
    primary_by_element = {}
    for e in primary:
        primary_by_element.setdefault(e.get("app_element_key"), []).append(e.get("subject_key"))
    for (el, subj), n in Counter((e.get("app_element_key"), e.get("subject_key")) for e in primary).items():
        if n > 1:
            errs.append(f"{el}: {n} PRIMARY-regels voor {subj} (hoogstens één)")

    for e in entries:
        ev = e.get("evidence") or {}
        eid = ev.get("evidence_id")
        canon = ev_by_id.get(eid)
        where = f"{e.get('app_element_key')}/{eid}"
        if canon is None:
            errs.append(f"{where}: evidence bestaat niet in de canonieke store")
            continue
        for k_b, k_c in (("value", "value"), ("unit", "unit_normalized"), ("method_class", "method_class"),
                         ("status", "status"), ("source_type", "source_type")):
            if ev.get(k_b) != canon[k_c]:
                errs.append(f"{where}: {k_b} {ev.get(k_b)!r} wijkt af van canoniek {canon[k_c]!r}")
        if canon["quantity_subject"].get("subject_key") != e.get("subject_key"):
            errs.append(f"{where}: subject_key wijkt af van de evidence")
        if canon["building_id"] not in (bid, *(f"BAG:{p}" for p in pids)):
            errs.append(f"{where}: evidence hoort bij een ander gebouw")
        if (e.get("crosswalk_decision_id") or None) != (eff.get(e.get("crosswalk_mapping_id"), {}).get("decision_id")):
            errs.append(f"{where}: crosswalk_decision_id hoort niet bij een geldend besluit")
        m = proposals.get(e.get("crosswalk_mapping_id"))
        if m is None or m.get("kind") != "APP_ELEMENT" or m.get("app_element_key") != e.get("app_element_key"):
            errs.append(f"{where}: crosswalk_mapping_id hoort niet bij dit app-element")
        elif e.get("role", "PRIMARY") == "PRIMARY":
            if eff.get(m["mapping_id"], {}).get("status") != "VERIFIED":
                errs.append(f"{where}: PRIMARY zonder geverifieerde app-mapping")
            if m.get("quantity_subject") != e.get("subject_key"):
                errs.append(f"{where}: PRIMARY-onderwerp {e.get('subject_key')} past niet bij de app-mapping ({m.get('quantity_subject')})")
            if roles.get(e.get("subject_key")) in eab.NON_PRIMARY_ROLES:
                errs.append(f"{where}: {e.get('subject_key')} heeft product_role {roles.get(e.get('subject_key'))} en mag geen PRIMARY zijn")
        # prijscontext (bijv. BUILDING_HEIGHT per pand voor de steiger): alleen bij PRIMARY, alleen als de mapping hem
        # declareert, CONTEXT_ONLY-onderwerp, precies de panden van de hoeveelheid, waarden = canonieke evidence,
        # ontbrekend = MISSING/null (nooit 0 of een andere hoogte)
        spec = (m or {}).get("pricing_context")
        pc = e.get("pricing_context")
        if pc is not None and (e.get("role", "PRIMARY") != "PRIMARY" or not spec):
            errs.append(f"{where}: pricing_context zonder declaratie in de app-mapping (of op een niet-PRIMARY-regel)")
        elif spec and e.get("role", "PRIMARY") == "PRIMARY" and pc is None:
            errs.append(f"{where}: pricing_context ontbreekt (de app-mapping vraagt {spec.get('context_subject')} per pand)")
        elif pc is not None:
            subj = pc.get("context_subject_key")
            if subj != spec.get("context_subject") or pc.get("purpose") != spec.get("purpose"):
                errs.append(f"{where}: pricing_context past niet bij de app-mapping")
            if roles.get(subj) != "CONTEXT_ONLY" or pc.get("context_product_role") != "CONTEXT_ONLY" or pc.get("selectable") is not False:
                errs.append(f"{where}: pricing_context-onderwerp {subj} moet CONTEXT_ONLY en niet kiesbaar zijn")
            if canon["source_ref"].get("aggregation"):
                want = sorted((ev_by_id[c]["source_ref"].get("bag_pand_id"), c) for c in canon["calculation"]["input_evidence_ids"] if c in ev_by_id)
            else:
                want = [(canon["source_ref"].get("bag_pand_id"), eid)]
            rows = pc.get("rows") or []
            if sorted((r.get("bag_pand_id"), r.get("quantity_evidence_id")) for r in rows) != want:
                errs.append(f"{where}: pricing_context dekt niet precies de panden/evidence van de hoeveelheid")
            for r in rows:
                pid = r.get("bag_pand_id")
                found = [x for x in evidence_store["evidence"] if x["building_id"] == f"BAG:{pid}" and x["source_type"] == "3D_BAG"
                         and x["quantity_subject"].get("subject_key") == subj]
                if r.get("status") == "AVAILABLE":
                    h = ev_by_id.get(r.get("context_evidence_id"))
                    if h is None or h["quantity_subject"].get("subject_key") != subj or h["building_id"] != f"BAG:{pid}":
                        errs.append(f"{where}: pricing_context {pid}: context_evidence_id hoort niet bij {subj} van dit pand")
                    elif r.get("value") != h["value"] or r.get("unit") != h["unit_normalized"]:
                        errs.append(f"{where}: pricing_context {pid}: waarde wijkt af van canoniek {h['value']!r}")
                elif r.get("status") == "MISSING":
                    if r.get("value") is not None or r.get("context_evidence_id") is not None:
                        errs.append(f"{where}: pricing_context {pid}: MISSING moet waarde null hebben (nooit 0)")
                    if found:
                        errs.append(f"{where}: pricing_context {pid}: als MISSING gemarkeerd terwijl {subj}-evidence bestaat")
                else:
                    errs.append(f"{where}: pricing_context {pid}: onbekende status {r.get('status')!r}")
        refs = ev.get("evidence_refs")
        if version == eab.BUNDLE_VERSION_RELATED:
            if not refs or refs.get("evidence_id") != eid:
                errs.append(f"{where}: evidence_refs ontbreekt")
                refs = {}
            for s in refs.get("snapshot_ids") or []:
                if s not in snap_ids:
                    errs.append(f"{where}: snapshot {s} bestaat niet")
            for lid in refs.get("building_link_ids") or []:
                if lid not in link_ids:
                    errs.append(f"{where}: building link {lid} bestaat niet")
            for c in refs.get("child_evidence_ids") or []:
                if c not in ev_by_id:
                    errs.append(f"{where}: child evidence {c} bestaat niet")
            if refs.get("quantity_observation_id") and refs["quantity_observation_id"] not in qo_ids:
                errs.append(f"{where}: quantity observation {refs['quantity_observation_id']} bestaat niet")
            if canon["source_type"] == "MJOP_ELEMENT_OVERVIEW" and refs.get("dependency") != {
                    "source_cluster": canon["dependency"].get("source_cluster"),
                    "same_object_document_ids": canon["dependency"].get("same_object_document_ids", []),
                    "identical_in_same_object_documents": canon["dependency"].get("identical_in_same_object_documents", [])}:
                errs.append(f"{where}: dependency (source cluster) niet behouden")
        if canon["source_type"] == "MJOP_ELEMENT_OVERVIEW":
            if ev.get("source_cluster") != canon["dependency"].get("source_cluster") or \
                    ev.get("same_object_document_ids") != canon["dependency"].get("same_object_document_ids", []):
                errs.append(f"{where}: source cluster/same-object-afhankelijkheid niet behouden")
            if len(pids) > 1 and (ev.get("scope_level") != "COMPLEX" or canon["building_id"] != bid or ev.get("components")):
                errs.append(f"{where}: historische waarde hoort ongesplitst op complexniveau")
        # aggregaat = exacte som van de components
        if canon["source_ref"].get("aggregation"):
            comps = ev.get("components") or []
            kids = canon["calculation"]["input_evidence_ids"]
            if sorted(c.get("evidence_id") for c in comps) != sorted(kids):
                errs.append(f"{where}: components wijken af van de child evidence")
            if sorted(str(c.get("bag_pand_id")) for c in comps) != sorted(pids):
                errs.append(f"{where}: components dekken niet precies alle panden van de scope")
            if len({c.get("bag_pand_id") for c in comps}) != len(comps):
                errs.append(f"{where}: dubbele pand in components")
            for c in comps:
                k = ev_by_id.get(c.get("evidence_id"))
                if k is None or k["value"] != c.get("value") or k["source_ref"].get("bag_pand_id") != c.get("bag_pand_id"):
                    errs.append(f"{where}: component {c.get('evidence_id')} wijkt af van de canonieke child evidence")
            if comps and sum(Decimal(c["value"]) for c in comps) != Decimal(ev["value"]):
                errs.append(f"{where}: aggregaat {ev['value']} != som van de components")
        # context: ander onderwerp, niet kiesbaar, niet resolveerbaar
        if e.get("role") == "RELATED_CONTEXT":
            rel = e.get("subject_relation") or {}
            if e.get("selectable") is not False:
                errs.append(f"{where}: RELATED_CONTEXT moet selectable false zijn")
            if e.get("subject_key") in primary_subjects or e.get("subject_key") == e.get("primary_subject_key"):
                errs.append(f"{where}: context-onderwerp gelijk aan het kiesbare onderwerp")
            if e.get("primary_subject_key") not in primary_by_element.get(e.get("app_element_key"), []):
                errs.append(f"{where}: primary_subject_key zonder kiesbare bron voor dit app-element")
            hsm_id = (canon.get("source_ref") or {}).get("subject_mapping_ref")
            hsm = hsm_by_id.get(hsm_id)
            if hsm is None or eff.get(hsm_id, {}).get("status") != "VERIFIED" or hsm.get("subject_key") != e.get("subject_key"):
                errs.append(f"{where}: context zonder effectief geverifieerde onderwerp-mapping voor {e.get('subject_key')} ({hsm_id})")
            else:
                qo = qo_by_id.get((canon.get("source_ref") or {}).get("quantity_observation_id"))
                if qo is None or not bqe.mapping_matches(hsm, qo):
                    errs.append(f"{where}: quantity observation matcht de onderwerp-mapping {hsm_id} niet (exact)")
            if bqe.related_subjects(vocab, e.get("primary_subject_key") or "").get(e.get("subject_key")) is None:
                errs.append(f"{where}: geen vastgelegde RELATED_NOT_EQUIVALENT-relatie {e.get('subject_key')} ~ {e.get('primary_subject_key')}")
            prim_units = {p["evidence"].get("unit") for p in primary if p.get("app_element_key") == e.get("app_element_key")}
            if prim_units and ev.get("unit") not in prim_units:
                errs.append(f"{where}: context-eenheid {ev.get('unit')!r} past niet bij het kiesbare onderwerp ({', '.join(sorted(map(str, prim_units)))})")
            if rel.get("relation") != "RELATED_NOT_EQUIVALENT" or rel.get("resolvable_as_same_quantity") is not False:
                errs.append(f"{where}: relatie moet RELATED_NOT_EQUIVALENT en niet resolveerbaar zijn")
        elif version == eab.BUNDLE_VERSION_RELATED and e.get("selectable") is not True:
            errs.append(f"{where}: PRIMARY-regel moet selectable true zijn")

    active = [r for r in resolutions["records"] if r["status"] == "ACTIVE" and r["building_id"] == bid]
    if active:
        errs.append(f"er bestaat een ACTIVE quantity resolution voor {bid} ({', '.join(r['resolution_id'] for r in active)})")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("--expect-panden", type=int)
    ap.add_argument("--check-export", action="store_true")
    a = ap.parse_args(argv)
    path = Path(a.bundle)
    raw = path.read_bytes()
    bundle = json.loads(raw)
    errs = validate(bundle, expect_panden=a.expect_panden)
    if a.check_export:
        store = json.loads(bqe.OUT_EVIDENCE.read_text(encoding="utf-8"))
        # zelfde app-elementen als de bundel (een beperkte bundel blijft zo reproduceerbaar)
        fresh = eab.build_bundle(bundle["building_id"], store["evidence"], json.loads(xw.APP_CROSSWALK.read_text(encoding="utf-8")),
                                 xw.effective(), json.loads(xw.SUBJECTS.read_text(encoding="utf-8")),
                                 app_elements={e["app_element_key"] for e in bundle.get("entries") or []})
        if bundle_bytes(fresh) != raw:
            errs.append("bundel is niet byte-identiek aan een nieuwe export (niet up-to-date of niet deterministisch)")
    for e in errs:
        print("FOUT: " + e, file=sys.stderr)
    print(f"{path.name}: {'GELDIG' if not errs else 'ONGELDIG'} ({bundle.get('bundle_version')}, {len(bundle.get('bag_pand_ids') or [])} panden, "
          f"{len(bundle.get('entries') or [])} regels)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
