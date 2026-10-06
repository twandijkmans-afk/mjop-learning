"""Maldenhof Frame Candidate Correction + Instance Activation v1, met Counting Semantics Correction v1.

Bouwt, bovenop de ongewijzigde annotatie van PR #33 (data/photo_evidence/maldenhof_2_frame_annotation_v1.json):
1. een append-only store met de menselijke kandidaat-besluiten (data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json);
2. gecorrigeerde kandidaten: FC-M2-001 en FC-M2-006 worden gesplitst in child candidates (eigen handmatige lezing van de foto door Claude,
   geen automatische detectie); de parent-evidence blijft ongewijzigd en herleidbaar;
3. frame instances (data/frame_inventory/maldenhof_photo_frame_instances_v1.json, apart van frame_inventory_v1.json) voor de
   human-accepted gewone gevelopeningen en de deur, status CONFIRMED, source USER_ASSISTED_PHOTO;
4. PHOTO_VISIBLE_* counts (geen BUILDING_TOTAL), corrected overlay en rapport onder reports/frames/photo_review_v2/.

Correction v1 (PCD-00024): 006-B en 006-C vormen een onafgebroken kozijnopening (kozijnstijl is geen bouwkundige scheiding); de child candidates en instances
van B en C blijven als SUPERSEDED bewaard en een nieuwe merged child/instance wordt actief.

Counting unit: een frame instance is een fysieke kozijn-/gevelopening tussen bouwkundige scheidingen (metselwerk); NIET iedere ruit of vleugel.
Geen maten, geen oppervlakken, geen painting area, geen quantity-resolutie, geen repeat-activatie. Deterministisch en idempotent.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import frame_inventory as fi  # noqa: E402

ANNOTATION = ROOT / "data" / "photo_evidence" / "maldenhof_2_frame_annotation_v1.json"
DECISIONS = ROOT / "data" / "photo_evidence" / "maldenhof_2_candidate_human_decisions_v1.json"
CORRECTED = ROOT / "data" / "photo_evidence" / "maldenhof_2_frame_candidates_corrected_v1.json"
INSTANCES = ROOT / "data" / "frame_inventory" / "maldenhof_photo_frame_instances_v1.json"
INVENTORY = ROOT / "data" / "frame_inventory" / "frame_inventory_v1.json"
PHOTO_2 = ROOT / "data" / "photos" / "incoming" / "maldenhof" / "maldenhof_2.jpg"
OUT_DIR = ROOT / "reports" / "frames" / "photo_review_v2"
OVERLAY = OUT_DIR / "maldenhof_2_frame_overlay_corrected.png"
REPORT = OUT_DIR / "maldenhof_2_frame_instance_activation_v1.md"
VERSION = "frame_instance_activation_v1.0.0"
REVIEWER_ID = "user-approved"
REVIEWED_AT = "2026-10-06T13:00:56Z"
EXPECTED_BASELINE_ORDINARY_WINDOW_CANDIDATES = 12  # v1-basislijn (voor de counting-semantics-correctie); assertion, niet gebruikt om het getal te produceren
EXPECTED_ORDINARY_WINDOW_CANDIDATES = 11  # na correctie: ASSERTION TO VERIFY uit de actieve gecorrigeerde bboxes (stopregel)
BASE_W, BASE_H = 2000.0, 1500.0

COUNTING_UNIT = ("Een frame instance is een fysieke kozijn-/gevelopening tussen bouwkundige scheidingen. Meerdere raamvleugels binnen een onafgebroken "
                 "kozijnopening zijn een instance; twee openingen gescheiden door metselwerk zijn twee instances. Niet iedere glasruit of draaivleugel apart.")

# --- menselijke besluiten ---------------------------------------------------------------------------------------------------
_ROOF = "Dakraam: foto-observatie geaccepteerd; NIET naar de gewone EXTERIOR_FRAME inventory. Dakramen blijven een aparte physical/maintenance context."
# (target_type, target_id, decision, reason, extra)
HUMAN = [
    ("CANDIDATE", "FC-M2-001", "SPLIT_REQUIRED", "De huidige bbox bevat twee afzonderlijke fysieke kozijnopeningen, gescheiden door zichtbaar metselwerk.", {"child_count": 2}),
    ("CANDIDATE", "FC-M2-002", "ACCEPT_DISTINCT_FRAME", "FC-M2-002 en FC-M2-003 zijn afzonderlijke kozijnopeningen met een zichtbare gemetselde penant ertussen.", {}),
    ("CANDIDATE", "FC-M2-003", "ACCEPT_DISTINCT_FRAME", "FC-M2-002 en FC-M2-003 zijn afzonderlijke kozijnopeningen met een zichtbare gemetselde penant ertussen.", {}),
    ("DUPLICATE_GROUP", "DUP-M2-001", "NOT_DUPLICATES", "FC-M2-002 en FC-M2-003 zijn afzonderlijke kozijnopeningen met een zichtbare gemetselde penant ertussen.", {"candidate_ids": ["FC-M2-002", "FC-M2-003"]}),
    ("CANDIDATE", "FC-M2-004", "ACCEPT_DISTINCT_FRAME", "FC-M2-004 en FC-M2-005 zijn afzonderlijke kozijnopeningen met zichtbaar metselwerk ertussen.", {}),
    ("CANDIDATE", "FC-M2-005", "ACCEPT_DISTINCT_FRAME", "FC-M2-004 en FC-M2-005 zijn afzonderlijke kozijnopeningen met zichtbaar metselwerk ertussen.", {}),
    ("DUPLICATE_GROUP", "DUP-M2-002", "NOT_DUPLICATES", "FC-M2-004 en FC-M2-005 zijn afzonderlijke kozijnopeningen met zichtbaar metselwerk ertussen.", {"candidate_ids": ["FC-M2-004", "FC-M2-005"]}),
    ("CANDIDATE", "FC-M2-006", "SPLIT_REQUIRED", "De huidige bbox omvat drie afzonderlijke fysieke kozijnopeningen: een smalle opening links, een grotere middenopening en een smalle opening rechts, gescheiden door metselwerk.", {"child_count": 3}),
    ("CANDIDATE", "FC-M2-007", "ACCEPT_FRAME", "Gevelkozijn geaccepteerd.", {}),
    ("CANDIDATE", "FC-M2-008", "ACCEPT_FRAME", "Gevelkozijn geaccepteerd; visibility blijft PARTIAL.", {"visibility": "PARTIAL"}),
    ("CANDIDATE", "FC-M2-009", "ACCEPT_FRAME", "Gevelkozijn geaccepteerd; address hint Maldenhof 288 behouden.", {"address_hint": "Maldenhof 288"}),
    ("CANDIDATE", "FC-M2-010", "REJECT", "Onvoldoende visueel bewijs dat dit een fysieke gevelopening is.", {}),
    ("CANDIDATE", "FC-M2-011", "ACCEPT_EXTERIOR_DOOR", "Buitendeur geaccepteerd; visibility PARTIAL, materiaal UNKNOWN.", {"visibility": "PARTIAL", "material": "UNKNOWN"}),
    ("CANDIDATE", "FC-M2-012", "KEEP_UNKNOWN", "Te zwaar afgedekt om type of bestaan als opening voldoende te bevestigen.", {}),
    ("CANDIDATE", "FC-M2-013", "REJECT", "Alleen een lichte horizontale strook zichtbaar; onvoldoende bewijs voor een fysieke gevelopening.", {}),
] + [("CANDIDATE", f"FC-M2-{n:03d}", "ACCEPT_PHOTO_OBSERVATION", _ROOF, {"observation_type": "ROOF_WINDOW", "promote_to_exterior_frame": False}) for n in range(14, 19)] + [
    ("CANDIDATE", "FC-M2-019", "ACCEPT_PHOTO_OBSERVATION", "Dakkapelraam geaccepteerd als foto-observatie; behouden als dakkapelraam-context (parent ROOF_DORMER), niet samengevoegd met de gewone gevelkozijn-count.",
     {"observation_type": "WINDOW", "parent": "ROOF_DORMER", "promote_to_exterior_frame": False}),
    ("REPEAT_MODULE", "MOD-M2-A", "DO_NOT_ACTIVATE_REPEAT_YET", "De modules vertonen overeenkomsten maar verschillen zichtbaar in dakkapel, bovenste gevelrij en begane-grondsituatie; coverage is bovendien onvolledig.", {}),
    ("REPEAT_MODULE", "MOD-M2-B", "DO_NOT_ACTIVATE_REPEAT_YET", "De modules vertonen overeenkomsten maar verschillen zichtbaar in dakkapel, bovenste gevelrij en begane-grondsituatie; coverage is bovendien onvolledig.", {}),
    ("CHILD_CANDIDATES", "FC-M2-006-B+FC-M2-006-C", "MERGE_AS_SINGLE_FRAME_OPENING",
     "De scheiding tussen B en C is een kozijnstijl binnen een onafgebroken kozijnopening en geen bouwkundige scheiding/metselwerk. Volgens de vastgelegde counting unit vormen zij een frame instance.",
     {"parent_candidate": "FC-M2-006", "merge_children": ["FC-M2-006-B", "FC-M2-006-C"], "merged_child_id": "FC-M2-006-BC", "unchanged_child": "FC-M2-006-A",
      "supersedes": "PCD-00008", "supersedes_scope": "PARTIAL: alleen de splitsing in B en C; de afscheiding van FC-M2-006-A blijft uit PCD-00008 gelden",
      "reviewed_at": "2026-10-06T13:32:03Z"}),
]

# --- gecorrigeerde child candidates (EIGEN handmatige lezing van foto 2 door Claude; bbox in 2000x1500-pixels) ----------------------------
# (child suffix, parent, bbox px, visibility, occlusion reason, note)
CHILDREN = [
    ("A", "FC-M2-001", (553, 522, 655, 610), "PARTIAL", "Lantaarnpaal en boom verbergen het linkerdeel van de linker opening; de linkerrand ligt achter het gebladerte",
     "Linker kozijnopening; open vleugel rechts naast het kozijn"),
    ("B", "FC-M2-001", (690, 522, 750, 610), "FULL", None, "Rechter kozijnopening, gescheiden van de linker door zichtbaar metselwerk (ca. x 655-690)"),
    ("A", "FC-M2-006", (1718, 538, 1778, 622), "FULL", None, "Smalle linker opening met geopende vleugel"),
    ("B", "FC-M2-006", (1783, 538, 1892, 622), "FULL", None, "Grotere middenopening met geopende vleugel links en gordijn"),
    ("C", "FC-M2-006", (1893, 538, 1950, 622), "FULL", None,
     "Smalle rechter opening met geopende vleugel; de scheiding met de middenopening is op de foto een kozijnstijl (geen zichtbaar metselwerk); gevolgd conform het menselijke besluit"),
]
CHILD_NOTE = ("Child bbox is een eigen handmatige visuele lezing van maldenhof_2.jpg door Claude (geen automatische detectie, geen foto-AI-model); "
              "de parent-bbox is niet overschreven.")

# --- instances ---------------------------------------------------------------------------------------------------------------
# (instance volgorde): kandidaat/child -> storey komt uit de parent-annotatie.
FRAME_ORDER = ["FC-M2-001-A", "FC-M2-001-B", "FC-M2-002", "FC-M2-003", "FC-M2-004", "FC-M2-005", "FC-M2-006-A", "FC-M2-006-B", "FC-M2-006-C",
               "FC-M2-007", "FC-M2-008", "FC-M2-009"]
DOOR_CANDIDATE = "FC-M2-011"
WINDOW_DECISIONS = {"ACCEPT_DISTINCT_FRAME", "ACCEPT_FRAME", "SPLIT_REQUIRED"}


def dumps(o):
    return json.dumps(o, indent=2, ensure_ascii=False) + "\n"


def norm(b):
    return [round(b[0] / BASE_W, 4), round(b[1] / BASE_H, 4), round(b[2] / BASE_W, 4), round(b[3] / BASE_H, 4)]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# --- append-only decisions ----------------------------------------------------------------------------------------------------
def new_store():
    return {"store_version": "photo_candidate_human_decisions_v1", "append_only": True, "photo": "maldenhof_2.jpg",
            "note": "Menselijke besluiten over kandidaten, duplicate groups en repeat modules van foto 2. Records worden nooit overschreven; correcties via supersedes.",
            "records": []}


def apply_decisions(store):
    have = {(r["target_type"], r["target_id"], r["decision"]) for r in store["records"] if r["status"] == "ACTIVE"}
    for ttype, tid, decision, reason, extra in HUMAN:
        if (ttype, tid, decision) in have:
            continue
        rec = {"decision_id": f"PCD-{len(store['records']) + 1:05d}", "target_type": ttype, "target_id": tid, "decision": decision, "reason": reason}
        over = {k: extra[k] for k in ("supersedes", "reviewed_at") if k in extra}
        rec.update({k: v for k, v in extra.items() if k not in over})
        rec.update({"reviewer_type": "human", "reviewer_id": REVIEWER_ID, "reviewed_at": REVIEWED_AT, "supersedes": None, "status": "ACTIVE"})
        rec.update(over)
        store["records"].append(rec)
    return store


def append_only_errors(old, new):
    n = {r["decision_id"]: r for r in new["records"]}
    return [r["decision_id"] for r in old["records"] if n.get(r["decision_id"]) != r]


# --- gecorrigeerde kandidaten ------------------------------------------------------------------------------------------------
def decision_index(store):
    return {(r["target_type"], r["target_id"]): r for r in store["records"] if r["status"] == "ACTIVE"}


def build_corrected(ann, store):
    idx = decision_index(store)
    parents = {c["candidate_id"]: c for c in ann["candidates"]}
    children = []
    for suffix, parent, bbox, vis, occ, note in CHILDREN:
        p = parents[parent]
        children.append({
            "candidate_id": f"{parent}-{suffix}", "parent_candidate_id": parent, "split_decision_id": idx[("CANDIDATE", parent)]["decision_id"],
            "candidate_type": "WINDOW", "bbox_norm": norm(bbox), "storey": p["storey"], "visibility": vis, "occlusion_reason": occ,
            "bag_address_scope_hint": p["bag_address_scope_hint"], "module_hint": p["module_hint"], "note": note,
            "bbox_method": "MANUAL_VISUAL_READING_CORRECTION", "bbox_method_note": CHILD_NOTE,
            "original_parent_bbox_norm": p["bbox_norm"], "lifecycle": "ACTIVE"})
    merge = idx.get(("CHILD_CANDIDATES", "FC-M2-006-B+FC-M2-006-C"))
    if merge:
        kb, kc = (next(k for k in children if k["candidate_id"] == f"FC-M2-006-{x}") for x in "BC")
        for k in (kb, kc):
            k["lifecycle"] = "SUPERSEDED"
            k["superseded_by"] = merge["merged_child_id"]
            k["superseded_by_decision_id"] = merge["decision_id"]
        b1, c1 = kb["bbox_norm"], kc["bbox_norm"]
        children.append({
            "candidate_id": merge["merged_child_id"], "parent_candidate_id": "FC-M2-006", "split_decision_id": kb["split_decision_id"],
            "correction_decision_id": merge["decision_id"], "merged_from": [kb["candidate_id"], kc["candidate_id"]],
            "candidate_type": "WINDOW", "bbox_norm": [min(b1[0], c1[0]), min(b1[1], c1[1]), max(b1[2], c1[2]), max(b1[3], c1[3])], "storey": kb["storey"],
            "visibility": "FULL" if kb["visibility"] == kc["visibility"] == "FULL" else "PARTIAL",
            "occlusion_reason": kb["occlusion_reason"] or kc["occlusion_reason"], "bag_address_scope_hint": kb["bag_address_scope_hint"], "module_hint": kb["module_hint"],
            "note": "Een onafgebroken kozijnopening: de scheiding tussen de vroegere B en C is een kozijnstijl (mullion) binnen een kozijn, geen bouwkundige scheiding.",
            "bbox_method": "MERGED_FROM_CHILD_BBOXES", "bbox_method_note": "Omhullende van de bboxes van FC-M2-006-B en FC-M2-006-C (eigen handmatige lezing, geen automatische detectie).",
            "original_parent_bbox_norm": kb["original_parent_bbox_norm"], "lifecycle": "ACTIVE",
            "refs": ["FC-M2-006", "FC-M2-006-B", "FC-M2-006-C", kb["split_decision_id"], merge["decision_id"]]})
    entries = []
    for c in ann["candidates"]:
        d = idx[("CANDIDATE", c["candidate_id"])]
        entries.append({"candidate_id": c["candidate_id"], "original_candidate_type": c["candidate_type"], "original_visibility": c["visibility"],
                        "original_bbox_norm": c["bbox_norm"], "human_decision_id": d["decision_id"], "human_decision": d["decision"],
                        "children": [k["candidate_id"] for k in children if k["parent_candidate_id"] == c["candidate_id"]]})
    dups = []
    for g in ann["duplicate_groups"]:
        r = idx[("DUPLICATE_GROUP", g["group_id"])]
        dups.append({"group_id": g["group_id"], "candidate_ids": g["candidate_ids"], "original_status": g["status"], "original_question": g["question"],
                     "human_resolution": r["decision"], "human_decision_id": r["decision_id"], "resolution_reason": r["reason"]})
    mods = [{"module_id": m["module_id"], "status": "REPEAT_CANDIDATE", "active": False, "multiplier": None, "user_confirmed_repeat": False,
             "human_decision": idx[("REPEAT_MODULE", m["module_id"])]["decision"], "human_decision_id": idx[("REPEAT_MODULE", m["module_id"])]["decision_id"]}
            for m in ann["repeat_modules"]["modules"]]
    roof = [{"candidate_id": n, "category": "ROOF_WINDOW", "human_decision_id": idx[("CANDIDATE", n)]["decision_id"], "bbox_norm": parents[n]["bbox_norm"]}
            for n in [f"FC-M2-{i:03d}" for i in range(14, 19)]]
    dormer = [{"candidate_id": "FC-M2-019", "category": "DORMER_WINDOW", "parent": {"type": "ROOF_DORMER", "ref": "DORMER-M2-001"},
               "human_decision_id": idx[("CANDIDATE", "FC-M2-019")]["decision_id"], "bbox_norm": parents["FC-M2-019"]["bbox_norm"]}]
    doc = {
        "builder_version": VERSION, "photo": ann["photo"], "source_annotation": "data/photo_evidence/maldenhof_2_frame_annotation_v1.json (ongewijzigd)",
        "counting_unit": COUNTING_UNIT, "metric_scale": "NONE_PROVEN", "coordinate_system": ann["coordinate_system"],
        "candidate_decisions": entries, "child_candidates": children, "duplicate_groups": dups, "repeat_modules": mods,
        "roof_context_observations": roof, "dormer_context_observations": dormer,
        "rejected_or_unknown": [{"candidate_id": e["candidate_id"], "human_decision": e["human_decision"], "human_decision_id": e["human_decision_id"]}
                                for e in entries if e["human_decision"] in {"REJECT", "KEEP_UNKNOWN"}],
        "lineage_rule": ("parent candidate -> human split decision -> child candidates -> (eventuele human correction -> superseded children + merged child) -> confirmed frame instance; "
                         "parent-evidence en superseded children/besluiten worden nooit overschreven of verwijderd."),
    }
    return doc


def ordinary_window_candidates(ann, corrected, baseline=False):
    """Gewone gevel-window/frame candidates na splits en human review. baseline=True: de v1-set (voor de counting-semantics-correctie, zonder merged children);
    anders de actieve set (superseded children vervangen door merged children)."""
    by_parent = {}
    for k in corrected["child_candidates"]:
        by_parent.setdefault(k["parent_candidate_id"], []).append(k)
    cmap = {c["candidate_id"]: c for c in ann["candidates"]}
    dec = {e["candidate_id"]: e for e in corrected["candidate_decisions"]}
    out = []
    for cid, c in cmap.items():
        d = dec[cid]
        if d["human_decision"] == "SPLIT_REQUIRED":
            for k in by_parent[cid]:
                if (baseline and "merged_from" in k) or (not baseline and k["lifecycle"] != "ACTIVE"):
                    continue
                out.append({"candidate_id": k["candidate_id"], "origin_candidate_id": cid, "visibility": k["visibility"], "bbox_norm": k["bbox_norm"],
                            "storey": k["storey"], "human_decision_id": d["human_decision_id"], "occlusion_reason": k["occlusion_reason"],
                            "address_hint": k["bag_address_scope_hint"], "module_hint": k["module_hint"], "child": True})
        elif d["human_decision"] in {"ACCEPT_DISTINCT_FRAME", "ACCEPT_FRAME"} and c["candidate_type"] == "WINDOW" and not c["parent"]:
            out.append({"candidate_id": cid, "origin_candidate_id": cid, "visibility": c["visibility"], "bbox_norm": c["bbox_norm"], "storey": c["storey"],
                        "human_decision_id": d["human_decision_id"], "occlusion_reason": c["occlusion_reason"], "address_hint": c["bag_address_scope_hint"],
                        "module_hint": c["module_hint"], "child": False})
    return out


def geometry_errors(ann, corrected):
    """Controleert splitsing: exact 2 resp. 3 children, binnen de parent, onderling disjunct."""
    errs = []
    parents = {c["candidate_id"]: c for c in ann["candidates"]}
    for pid, n, n_active in (("FC-M2-001", 2, 2), ("FC-M2-006", 3, 2)):
        kids = [k for k in corrected["child_candidates"] if k["parent_candidate_id"] == pid and "merged_from" not in k]
        if len(kids) != n:
            errs.append(f"{pid}: {len(kids)} originele children, verwacht {n}")
        active = [k for k in corrected["child_candidates"] if k["parent_candidate_id"] == pid and k["lifecycle"] == "ACTIVE"]
        if len(active) != n_active:
            errs.append(f"{pid}: {len(active)} actieve children, verwacht {n_active}")
        pb = parents[pid]["bbox_norm"]
        for k in kids + [k for k in active if "merged_from" in k]:
            b = k["bbox_norm"]
            if not (pb[0] <= b[0] < b[2] <= pb[2] and pb[1] <= b[1] < b[3] <= pb[3]):
                errs.append(f"{k['candidate_id']}: bbox valt buiten parent")
        for grp in (kids, active):
            errs += _overlap_errors(grp)
        for k in active:
            for src in k.get("merged_from", []):
                sb = next(x for x in kids if x["candidate_id"] == src)["bbox_norm"]
                if not (k["bbox_norm"][0] <= sb[0] and sb[2] <= k["bbox_norm"][2] and k["bbox_norm"][1] <= sb[1] and sb[3] <= k["bbox_norm"][3]):
                    errs.append(f"{k['candidate_id']}: omvat {src} niet")
    return errs


def _overlap_errors(kids):
    errs = []
    for i, a in enumerate(kids):
        for b in kids[i + 1:]:
            if not (a["bbox_norm"][2] <= b["bbox_norm"][0] or b["bbox_norm"][2] <= a["bbox_norm"][0]):
                errs.append(f"{a['candidate_id']}/{b['candidate_id']}: overlappen")
    return errs


# --- frame instances ----------------------------------------------------------------------------------------------------------
def build_instances(ann, corrected, store, inventory):
    # v1-basislijn: de 12 instances zoals geactiveerd in PR #34 (historie blijft bewaard); daarna de counting-semantics-correctie.
    cands = ordinary_window_candidates(ann, corrected, baseline=True)
    if len(cands) != EXPECTED_BASELINE_ORDINARY_WINDOW_CANDIDATES:
        raise CountMismatch({"expected": EXPECTED_BASELINE_ORDINARY_WINDOW_CANDIDATES, "found": len(cands), "candidate_ids": [c["candidate_id"] for c in cands]})
    assert [c["candidate_id"] for c in cands] == FRAME_ORDER, "volgorde/kandidaten wijken af"
    active_cands = ordinary_window_candidates(ann, corrected)
    if len(active_cands) != EXPECTED_ORDINARY_WINDOW_CANDIDATES:
        raise CountMismatch({"expected": EXPECTED_ORDINARY_WINDOW_CANDIDATES, "found": len(active_cands), "candidate_ids": [c["candidate_id"] for c in active_cands]})
    building = next(b for b in inventory["buildings"] if b["label"].startswith("Maldenhof"))
    cpd = building["exterior_frame_presence"]
    idx = decision_index(store)
    photo = ann["photo"]
    instances, extras = [], {}

    def mat_ref():
        return {"ref_type": "MATERIAL_BASIS", "material_basis": "SOURCE_REPORTED_BUILDING_LEVEL", "material_as_reported": cpd["material_as_reported"],
                "presence_decision_id": cpd["decision_id"], "considered_evidence_ids": cpd["considered_evidence_ids"],
                "note": "Materiaal komt uit de historische MJOP-vermelding op gebouwniveau (Kozijn buiten hout), niet uit visuele vaststelling per kozijn."}

    for n, c in enumerate(cands, 1):
        iid = f"FI-M2-{n:03d}"
        refs = [{"ref_type": "PHOTO", "photo_id": photo["photo_id"], "photo_sha256": photo["sha256"]},
                {"ref_type": "ORIGINAL_CANDIDATE", "candidate_id": c["origin_candidate_id"], "candidate_file": "data/photo_evidence/maldenhof_2_frame_annotation_v1.json"},
                {"ref_type": "HUMAN_DECISION", "decision_id": c["human_decision_id"], "store": "data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json"}]
        if c["child"]:
            refs.append({"ref_type": "CORRECTED_CHILD_CANDIDATE", "candidate_id": c["candidate_id"],
                         "candidate_file": "data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json"})
        refs.append(mat_ref())
        instances.append({
            "frame_instance_id": iid, "building_id": building["building_id"], "bag_pand_id": None, "component_type": "EXTERIOR_FRAME", "facade_side": "UNKNOWN",
            "storey": c["storey"], "subtype": "UNKNOWN", "material": "WOOD", "count": 1, "source_refs": refs,
            "provenance": {"source_type": "USER_ASSISTED_PHOTO", "photo_id": photo["photo_id"], "method": "HUMAN_CONFIRMED_MANUAL_PHOTO_READING"},
            "status": "CONFIRMED", "human_decision_ref": c["human_decision_id"], "repeat_group_id": None, "frame_group_id": None})
        extras[iid] = {"candidate_id": c["candidate_id"], "origin_candidate_id": c["origin_candidate_id"], "photo_visibility": c["visibility"],
                       "bbox_norm": c["bbox_norm"], "address_hint": c["address_hint"], "module_hint": c["module_hint"],
                       "material_basis": "SOURCE_REPORTED_BUILDING_LEVEL", "quantity_contributions": {"FRAME_COUNT": 1, "WINDOW_COUNT": 1},
                       "scope": "PHOTO_VISIBLE_CONFIRMED_COUNT"}
    door = next(c for c in ann["candidates"] if c["candidate_id"] == DOOR_CANDIDATE)
    d = idx[("CANDIDATE", DOOR_CANDIDATE)]
    iid = f"FI-M2-{len(cands) + 1:03d}"
    instances.append({
        "frame_instance_id": iid, "building_id": building["building_id"], "bag_pand_id": None, "component_type": "EXTERIOR_DOOR", "facade_side": "UNKNOWN",
        "storey": door["storey"], "subtype": "EXTERIOR_DOOR", "material": "UNKNOWN", "count": 1,
        "source_refs": [{"ref_type": "PHOTO", "photo_id": photo["photo_id"], "photo_sha256": photo["sha256"]},
                        {"ref_type": "ORIGINAL_CANDIDATE", "candidate_id": DOOR_CANDIDATE, "candidate_file": "data/photo_evidence/maldenhof_2_frame_annotation_v1.json"},
                        {"ref_type": "HUMAN_DECISION", "decision_id": d["decision_id"], "store": "data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json"}],
        "provenance": {"source_type": "USER_ASSISTED_PHOTO", "photo_id": photo["photo_id"], "method": "HUMAN_CONFIRMED_MANUAL_PHOTO_READING"},
        "status": "CONFIRMED", "human_decision_ref": d["decision_id"], "repeat_group_id": None, "frame_group_id": None})
    extras[iid] = {"candidate_id": DOOR_CANDIDATE, "origin_candidate_id": DOOR_CANDIDATE, "photo_visibility": "PARTIAL", "bbox_norm": door["bbox_norm"],
                   "address_hint": door["bag_address_scope_hint"], "module_hint": door["module_hint"], "material_basis": "UNKNOWN",
                   "quantity_contributions": {"EXTERIOR_DOOR_COUNT": 1}, "scope": "PHOTO_VISIBLE_CONFIRMED_COUNT"}
    # --- counting-semantics-correctie: superseded B/C-instances bewaren, merged instance toevoegen -----------------------------------
    superseded = []
    merged_kids = [k for k in corrected["child_candidates"] if "merged_from" in k and k["lifecycle"] == "ACTIVE"]
    for mk in merged_kids:
        new_id = f"FI-M2-{len(instances) + 1:03d}"
        old_ids = []
        for src in mk["merged_from"]:
            old_id = next(i for i, e in extras.items() if e["candidate_id"] == src)
            old_ids.append(old_id)
            rec = next(i for i in instances if i["frame_instance_id"] == old_id)
            instances.remove(rec)
            superseded.append({"instance": rec, "annotation": extras.pop(old_id), "lifecycle": "SUPERSEDED", "superseded_by_instance": new_id,
                               "supersession_decision_id": mk["correction_decision_id"],
                               "reason": "Kozijnstijl binnen een onafgebroken kozijnopening; geen aparte physical frame instance (counting unit)."})
        corr = mk["correction_decision_id"]
        instances.append({
            "frame_instance_id": new_id, "building_id": building["building_id"], "bag_pand_id": None, "component_type": "EXTERIOR_FRAME", "facade_side": "UNKNOWN",
            "storey": mk["storey"], "subtype": "UNKNOWN", "material": "WOOD", "count": 1,
            "source_refs": [{"ref_type": "PHOTO", "photo_id": photo["photo_id"], "photo_sha256": photo["sha256"]},
                            {"ref_type": "ORIGINAL_CANDIDATE", "candidate_id": mk["parent_candidate_id"], "candidate_file": "data/photo_evidence/maldenhof_2_frame_annotation_v1.json"},
                            {"ref_type": "HUMAN_DECISION", "decision_id": mk["split_decision_id"], "store": "data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json"},
                            {"ref_type": "HUMAN_CORRECTION_DECISION", "decision_id": corr, "store": "data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json"},
                            {"ref_type": "CORRECTED_CHILD_CANDIDATE", "candidate_id": mk["candidate_id"], "candidate_file": "data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json"}]
                           + [{"ref_type": "SUPERSEDED_CHILD_CANDIDATE", "candidate_id": src} for src in mk["merged_from"]]
                           + [{"ref_type": "SUPERSEDED_INSTANCE", "frame_instance_id": o} for o in old_ids] + [mat_ref()],
            "provenance": {"source_type": "USER_ASSISTED_PHOTO", "photo_id": photo["photo_id"], "method": "HUMAN_CONFIRMED_MANUAL_PHOTO_READING"},
            "status": "CONFIRMED", "human_decision_ref": corr, "repeat_group_id": None, "frame_group_id": None})
        extras[new_id] = {"candidate_id": mk["candidate_id"], "origin_candidate_id": mk["parent_candidate_id"], "photo_visibility": mk["visibility"],
                          "bbox_norm": mk["bbox_norm"], "address_hint": mk["bag_address_scope_hint"], "module_hint": mk["module_hint"],
                          "material_basis": "SOURCE_REPORTED_BUILDING_LEVEL", "quantity_contributions": {"FRAME_COUNT": 1, "WINDOW_COUNT": 1},
                          "scope": "PHOTO_VISIBLE_CONFIRMED_COUNT", "supersedes_instances": old_ids, "merged_from_candidates": mk["merged_from"]}
    active_ids = [e["candidate_id"] for e in extras.values() if e["candidate_id"] != DOOR_CANDIDATE]
    assert sorted(active_ids) == sorted(c["candidate_id"] for c in active_cands), "actieve instances wijken af van actieve kandidaten"
    return {
        "store_version": "maldenhof_photo_frame_instances_v1", "builder_version": VERSION,
        "note": ("Foto-gebaseerde frame instances voor Maldenhof 240-296, apart van data/frame_inventory/frame_inventory_v1.json (dat ongewijzigd blijft). "
                 "`instances` bevat alleen ACTIEVE instances; vervangen instances staan ongewijzigd in `superseded_instances` (provenance blijft bewaard). "
                 "Een instance is een kozijn-/gevelopening (component_type EXTERIOR_FRAME) en draagt bij aan FRAME_COUNT en WINDOW_COUNT; de deur aan EXTERIOR_DOOR_COUNT. "
                 "Alleen PHOTO_VISIBLE_CONFIRMED_COUNT; geen BUILDING_TOTAL."),
        "counting_unit": COUNTING_UNIT, "building_id": building["building_id"], "instances": instances, "frame_groups": [], "instance_annotations": extras,
        "superseded_instances": superseded,
        "photo_visible_counts": photo_counts(instances, extras, superseded),
        "building_totals": {k: {"status": "UNKNOWN", "value": None} for k in
                            ("FRAME_COUNT", "WINDOW_COUNT", "EXTERIOR_DOOR_COUNT", "WINDOW_OPENING_AREA", "FRAME_OUTER_AREA", "FRAME_PAINTING_AREA", "GLASS_AREA")},
        "policy": {"metric_dimensions": "NONE", "painting_area": "NEVER_AUTOMATIC", "quantity_resolution": "NOT_WRITTEN", "repeat_modules": "NOT_ACTIVE",
                   "historical_756_80_m2": "NOT_COMPARABLE", "photo_scale": "NONE_PROVEN"},
    }


class CountMismatch(Exception):
    pass


def photo_counts(instances, extras, superseded=()):
    frames = [i for i in instances if i["component_type"] == "EXTERIOR_FRAME"]
    doors = [i for i in instances if i["component_type"] == "EXTERIOR_DOOR"]
    vis = lambda i: extras[i["frame_instance_id"]]["photo_visibility"]  # noqa: E731
    return {"count_basis": "PHOTO_VISIBLE_CONFIRMED_COUNT", "photo": "maldenhof_2.jpg", "is_building_total": False,
            "PHOTO_VISIBLE_FRAME_COUNT": sum(extras[i["frame_instance_id"]]["quantity_contributions"].get("FRAME_COUNT", 0) for i in instances),
            "PHOTO_VISIBLE_WINDOW_COUNT": sum(extras[i["frame_instance_id"]]["quantity_contributions"].get("WINDOW_COUNT", 0) for i in instances),
            "PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT": sum(extras[i["frame_instance_id"]]["quantity_contributions"].get("EXTERIOR_DOOR_COUNT", 0) for i in instances),
            "ordinary_frames_FULL": len([i for i in frames if vis(i) == "FULL"]), "ordinary_frames_PARTIAL": len([i for i in frames if vis(i) == "PARTIAL"]),
            "exterior_doors_PARTIAL": len([i for i in doors if vis(i) == "PARTIAL"]),
            "superseded_instance_ids": [x["instance"]["frame_instance_id"] for x in superseded],
            "excluded": {"ROOF_WINDOW": 5, "DORMER_WINDOW": 1, "REJECTED": 2, "KEEP_UNKNOWN": 1}}


def instance_store_errors(doc):
    errs = fi.store_errors({"instances": doc["instances"] + [x["instance"] for x in doc.get("superseded_instances", [])], "frame_groups": doc["frame_groups"]})
    for i in doc["instances"]:
        for k in ("width_m", "height_m", "opening_area_m2", "frame_outer_area_m2"):
            if i.get(k) is not None:
                errs.append(f"{i['frame_instance_id']}: {k} niet toegestaan")
    return errs


# --- overlay / rapport --------------------------------------------------------------------------------------------------------
def render_overlay(ann, corrected, inst):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(PHOTO_2).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 19)

    def box(b, col, dashed, w=4):
        x1, y1, x2, y2 = b[0] * W, b[1] * H, b[2] * W, b[3] * H
        if not dashed:
            d.rectangle([x1, y1, x2, y2], outline=col, width=w)
            return
        step = 14
        for x in range(int(x1), int(x2), step * 2):
            d.line([x, y1, min(x + step, x2), y1], fill=col, width=w)
            d.line([x, y2, min(x + step, x2), y2], fill=col, width=w)
        for y in range(int(y1), int(y2), step * 2):
            d.line([x1, y, x1, min(y + step, y2)], fill=col, width=w)
            d.line([x2, y, x2, min(y + step, y2)], fill=col, width=w)

    def label(text, x, y, col, f=font):
        tw = d.textlength(text, font=f)
        x = max(2, min(x, W - tw - 10))
        d.rectangle([x, y, x + tw + 8, y + 26], fill=(0, 0, 0, 200))
        d.text((x + 4, y + 1), text, fill=col, font=f)

    GREEN, MAG, CYAN, ORANGE, GREY = (46, 204, 113), (255, 0, 200), (0, 200, 255), (255, 140, 0), (200, 200, 200)
    # context: dakramen / dakkapelraam / afgewezen / onbekend
    pm = {c["candidate_id"]: c for c in ann["candidates"]}
    for r in corrected["roof_context_observations"]:
        box(r["bbox_norm"], CYAN, False, 3)
        label(f"{r['candidate_id'][-3:]} RW", r["bbox_norm"][0] * W, r["bbox_norm"][1] * H - 28, CYAN, small)
    for r in corrected["dormer_context_observations"]:
        box(r["bbox_norm"], ORANGE, True, 3)
        label(f"{r['candidate_id'][-3:]} DORMER-W", r["bbox_norm"][0] * W, r["bbox_norm"][1] * H - 28, ORANGE, small)
    for r in corrected["rejected_or_unknown"]:
        c = pm[r["candidate_id"]]
        box(c["bbox_norm"], GREY, True, 3)
        txt = f"{r['candidate_id'][-3:]} {'REJECT' if r['human_decision'] == 'REJECT' else 'UNKNOWN'}"
        label(txt, c["bbox_norm"][0] * W, c["bbox_norm"][3] * H + 4, GREY, small)
    # confirmed frames; label-posities (above1/above2/below)
    pos = {"FI-M2-001": "a2", "FI-M2-002": "a1", "FI-M2-003": "b", "FI-M2-004": "a2", "FI-M2-005": "b", "FI-M2-006": "a2", "FI-M2-007": "b",
           "FI-M2-008": "a2", "FI-M2-009": "b2", "FI-M2-010": "a1", "FI-M2-011": "a1", "FI-M2-012": "a1", "FI-M2-013": "a1", "FI-M2-014": "a2"}
    for i in inst["instances"]:
        iid = i["frame_instance_id"]
        e = inst["instance_annotations"][iid]
        b = e["bbox_norm"]
        door = i["component_type"] == "EXTERIOR_DOOR"
        col = MAG if door else GREEN
        partial = e["photo_visibility"] != "FULL"
        box(b, col, partial, 4)
        vis = "PARTIAL" if partial else "FULL"
        text = f"{iid} {'DOOR ' if door else ''}{vis}"
        x, yt, yb = b[0] * W, b[1] * H, b[3] * H
        y = {"a1": yt - 28, "a2": yt - 56, "b": yb + 4, "b2": yb + 32}[pos[iid]]
        label(text, x, y, col)
    leg = ["Corrected overlay: confirmed frame instances (groen = gevelopening, magenta = deur; doorgetrokken = FULL, gestippeld = PARTIAL). Alleen beeldcoordinaten, geen maten.",
           "Cyaan = dakraam (aparte context), oranje gestippeld = dakkapelraam (aparte context), grijs gestippeld = afgewezen/onbekend (geen instance). Geen BUILDING_TOTAL."]
    d.rectangle([0, H - 64, W, H], fill=(0, 0, 0, 215))
    for k, t in enumerate(leg):
        d.text((10, H - 60 + k * 28), t, fill=(255, 255, 255), font=small)
    im = im.resize((1600, 1200), Image.LANCZOS)
    OVERLAY.parent.mkdir(parents=True, exist_ok=True)
    im.save(OVERLAY, optimize=True)


def render_report(ann, corrected, store, inst):
    pc = inst["photo_visible_counts"]
    L = ["# Maldenhof Frame Instance Activation v1 (incl. Counting Semantics Correction v1)", "",
         "Scope: menselijke kandidaat-correctie en activatie van foto-gebaseerde frame instances voor maldenhof_2.jpg. Geen gebouwtotaal, geen maten, geen painting area, "
         "geen quantity-resolutie, geen repeat-activatie, geen MJOP-App wijziging.", "", "## Counting unit", "", COUNTING_UNIT, "",
         "## 1. Human candidate decisions (append-only)", "", "| Decision | Target | Besluit | Reviewer |", "|---|---|---|---|"]
    for r in store["records"]:
        L.append(f"| {r['decision_id']} | {r['target_type']} {r['target_id']} | {r['decision']} | {r['reviewer_type']} ({r['reviewer_id']}), {r['reviewed_at']} |")
    L += ["", "## 2. Corrected child candidates", "",
          CHILD_NOTE, "", "| Child | Parent | Split decision | Visibility | Lifecycle | bbox_norm |", "|---|---|---|---|---|---|"]
    for k in corrected["child_candidates"]:
        life = k["lifecycle"] + (f" door {k['superseded_by']} ({k['superseded_by_decision_id']})" if k["lifecycle"] == "SUPERSEDED" else "")
        L.append(f"| {k['candidate_id']} | {k['parent_candidate_id']} | {k['split_decision_id']} | {k['visibility']} | {life} | {k['bbox_norm']} |")
    L += ["", "FC-M2-006-B en FC-M2-006-C zijn na de counting-semantics-correctie SUPERSEDED door FC-M2-006-BC (zie sectie 3a); beide blijven met hun oorspronkelijke bbox bewaard. "
          "Bij FC-M2-001-B: de rechter opening is zichtbaar en niet door lantaarnpaal of boom afgedekt, daarom FULL; "
          "alleen de linker opening is PARTIAL.", "",
          "## 3a. Counting semantics correction (PCD-00024)", "",
          "De splitsing van FC-M2-006 in drie openingen (PCD-00008) was te ruim: de scheiding tussen de middenopening (B) en de rechter opening (C) is op de foto een "
          "kozijnstijl (mullion) binnen een onafgebroken kozijn en geen metselwerk. FC-M2-006-A blijft een afzonderlijke opening; B en C vormen samen een opening.", "",
          "**Waarom een kozijnstijl geen bouwkundige scheiding is.** Een kozijnstijl is een onderdeel van het kozijn zelf: hij verdeelt een opening in vakken maar maakt geen nieuwe "
          "opening in de gevel. Een bouwkundige scheiding is metselwerk (een penant) of ander gevelvlak tussen twee openingen. De counting unit telt openingen tussen bouwkundige scheidingen, dus een stijl binnen een kozijn telt niet mee.", "",
          "| Begrip | Wat het is | Telt als frame instance? |", "|---|---|---|",
          "| GLAZING / OPERABLE LEAF | glasvlak, draaiende of kierende vleugel binnen een kozijn | Nee: nooit per ruit of vleugel |",
          "| MULLION (kozijnstijl) | verdeling binnen een onafgebroken kozijnopening | Nee: geen scheiding tussen instances |",
          "| FRAME OPENING | fysieke kozijn-/gevelopening tussen bouwkundige scheidingen (metselwerk) | Ja: een instance per opening |", "",
          "PCD-00008 en de oorspronkelijke child candidates en instances zijn niet verwijderd of overschreven; PCD-00024 supersedet PCD-00008 alleen voor de splitsing in B en C.", "",
          "## 3. Duplicate groups", "", "| Groep | Oorspronkelijke status (bewaard) | Menselijke resolutie |", "|---|---|---|"]
    for g in corrected["duplicate_groups"]:
        L.append(f"| {g['group_id']} ({', '.join(g['candidate_ids'])}) | {g['original_status']} | {g['human_resolution']} ({g['human_decision_id']}) |")
    L += ["", "## 4. Confirmed frame instances", "", f"| Instance | Kandidaat | Origin | Visibility | Material | Decision |", "|---|---|---|---|---|---|"]
    for i in inst["instances"]:
        e = inst["instance_annotations"][i["frame_instance_id"]]
        L.append(f"| {i['frame_instance_id']} | {e['candidate_id']} | {e['origin_candidate_id']} | {e['photo_visibility']} | {i['material']} ({e['material_basis']}) | {i['human_decision_ref']} |")
    L += ["", "Vervangen (SUPERSEDED, ongewijzigd bewaard in `superseded_instances`):", "", "| Instance | Kandidaat | Vervangen door | Besluit |", "|---|---|---|---|"]
    for x in inst["superseded_instances"]:
        L.append(f"| {x['instance']['frame_instance_id']} | {x['annotation']['candidate_id']} | {x['superseded_by_instance']} | {x['supersession_decision_id']} |")
    L += ["", "Materiaal WOOD op de gewone kozijnen komt uit de historische MJOP-vermelding op gebouwniveau (material_as_reported hout, CPD-00001) en is "
          "niet per kozijn visueel bewezen. De deur heeft materiaal UNKNOWN.", "",
          "## 5. PHOTO_VISIBLE counts (maldenhof_2.jpg, NIET BUILDING_TOTAL)", "", "| Concept | Waarde |", "|---|---|",
          f"| PHOTO_VISIBLE_FRAME_COUNT | {pc['PHOTO_VISIBLE_FRAME_COUNT']} |", f"| PHOTO_VISIBLE_WINDOW_COUNT | {pc['PHOTO_VISIBLE_WINDOW_COUNT']} |",
          f"| PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT | {pc['PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT']} |",
          f"| Gewone kozijnen FULL / PARTIAL | {pc['ordinary_frames_FULL']} / {pc['ordinary_frames_PARTIAL']} |",
          f"| Deuren PARTIAL | {pc['exterior_doors_PARTIAL']} |", "",
          f"De actieve instances leveren {pc['PHOTO_VISIBLE_FRAME_COUNT']} gewone gevelopeningen op ({EXPECTED_ORDINARY_WINDOW_CANDIDATES} verwacht na de correctie; "
          "de stopregel is gecontroleerd). Voor de correctie waren dat er 12 (FI-M2-001..012). De verdeling FULL/PARTIAL volgt uit de visibility van de actieve instances.", "",
          "Buiten de count: dakramen FC-M2-014..018 (aparte physical/maintenance context), dakkapelraam FC-M2-019 (aparte dakkapelraam-context, niet samengevoegd), "
          "afgewezen FC-M2-010 en FC-M2-013, FC-M2-012 KEEP_UNKNOWN. Geen van deze heeft een instance.", "",
          "## 6. Building totals en quantity-status", "", "FRAME_COUNT, WINDOW_COUNT en EXTERIOR_DOOR_COUNT als BUILDING_TOTAL = UNKNOWN. WINDOW_OPENING_AREA, FRAME_OUTER_AREA, "
          "FRAME_PAINTING_AREA en GLASS_AREA = UNKNOWN: geen maten en geen foto-schaal. Geen quantity_resolution record. 756,80 blijft NOT_COMPARABLE (historische context).", "",
          "## 7. Repeat modules", "", "MOD-M2-A en MOD-M2-B blijven REPEAT_CANDIDATE, active = false, multiplier = null. Besluit DO_NOT_ACTIVATE_REPEAT_YET. Geen x2, geen x13, geen extrapolatie.", "",
          "## 8. Herleidbaarheid", "", corrected["lineage_rule"], "",
          "Opslag: `data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json`, `data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json`, "
          "`data/frame_inventory/maldenhof_photo_frame_instances_v1.json`. De bestaande annotatie en `frame_inventory_v1.json` zijn ongewijzigd.", "",
          "## 9. Overlay", "", "`reports/frames/photo_review_v2/maldenhof_2_frame_overlay_corrected.png`", ""]
    return "\n".join(L)


def build_all():
    ann = load(ANNOTATION)
    inv = load(INVENTORY)
    old = load(DECISIONS) if DECISIONS.exists() else new_store()
    store = apply_decisions(json.loads(json.dumps(old)))
    assert not append_only_errors(old, store)
    corrected = build_corrected(ann, store)
    errs = geometry_errors(ann, corrected)
    if errs:
        raise SystemExit("geometrie-fouten, stop vóór activation: " + "; ".join(errs))
    inst = build_instances(ann, corrected, store, inv)
    errs = instance_store_errors(inst)
    assert not errs, errs
    return ann, store, corrected, inst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    try:
        ann, store, corrected, inst = build_all()
    except CountMismatch as e:
        print(f"STOP: gecorrigeerde bboxes leveren {e.args[0]['found']} gewone window/frame candidates, verwacht {e.args[0]['expected']}: {e.args[0]['candidate_ids']}")
        raise SystemExit(2)
    if a.check:
        assert DECISIONS.read_text(encoding="utf-8") == dumps(store), "decisions verouderd"
        assert CORRECTED.read_text(encoding="utf-8") == dumps(corrected), "corrected verouderd"
        assert INSTANCES.read_text(encoding="utf-8") == dumps(inst), "instances verouderd"
        assert REPORT.read_text(encoding="utf-8") == render_report(ann, corrected, store, inst), "rapport verouderd"
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DECISIONS.write_text(dumps(store), encoding="utf-8")
    CORRECTED.write_text(dumps(corrected), encoding="utf-8")
    INSTANCES.write_text(dumps(inst), encoding="utf-8")
    REPORT.write_text(render_report(ann, corrected, store, inst), encoding="utf-8")
    render_overlay(ann, corrected, inst)


if __name__ == "__main__":
    main()
