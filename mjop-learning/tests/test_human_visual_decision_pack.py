import base64
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import human_decision_pack_data as H  # noqa: E402
REVIEW = ROOT / "reports/frames/photo_review_map003_map004_v1"
PACK = REVIEW / "decision_pack"
HTML_PATH = PACK / "maldenhof_human_visual_decision_pack_v1.html"
HTML = HTML_PATH.read_text()
INDEX = json.loads((PACK / "maldenhof_human_visual_decision_pack_v1_index.json").read_text())
REV = json.loads((REVIEW / "maldenhof_visual_photo_review_map003_map004_v1.json").read_text())
APPROVAL = (ROOT / "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md").read_text()
INST = json.loads((ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json").read_text())
PACK_JSON = json.loads(re.search(r"const PACK = (\{.*?\});\n\(function", HTML, re.S).group(1).replace("<\\/", "</"))
ITEMS = PACK_JSON["items"]
STD = {"CONFIRM", "REJECT", "UNDECIDABLE", "NEEDS_BETTER_PHOTO"}
OVL = {"SAME", "DIFFERENT", "UNDECIDABLE"}


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_html_is_self_contained_and_offline():
    assert not re.search(r"(src|href|action)\s*=\s*[\"']\s*(https?:)?//", HTML, re.I)
    assert not re.search(r"<script[^>]+src=", HTML, re.I) and not re.search(r"<link[^>]+href=", HTML, re.I)
    assert not re.search(r"url\(\s*[\"']?(https?:)?//", HTML) and "@import" not in HTML
    assert "fetch(" not in HTML and "XMLHttpRequest" not in HTML and "WebSocket" not in HTML
    uris = re.findall(r'src="(data:image/jpeg;base64,[A-Za-z0-9+/=]+)"', HTML)
    assert len(uris) > 80
    for u in uris[:: max(1, len(uris) // 15)]:
        assert base64.b64decode(u.split(",", 1)[1])[:3] == b"\xff\xd8\xff"
    assert len(re.findall(r"<img ", HTML)) == len(re.findall(r'<img [^>]*src="data:image/jpeg;base64,', HTML))


def test_review_points_are_complete_and_traceable():
    ids = [i["review_id"] for i in ITEMS]
    assert len(ids) == len(set(ids)) == INDEX["counts"]["review_points"]
    obs_ids = {o["obs_id"] for o in REV["observations"]}
    rel_ids = {r["rel_id"] for r in REV["relations"]}
    ref_ids = {r["ref_id"] for r in REV["references"]}
    assert len(obs_ids) == 50 and len(rel_ids) == 43
    assert {i["review_id"] for i in ITEMS if i["review_type"] == "OBSERVATION"} == {"RV-OBS-" + o[4:] for o in obs_ids}
    assert {r for i in ITEMS for r in i["relation_ids"]} == rel_ids          # alle 43 relaties behouden en beoordeelbaar
    assert PACK_JSON["pack_version"] == "human_visual_decision_pack_v1.2.0" and PACK_JSON["legacy_pack_version"] == "human_visual_decision_pack_v1.0.0"
    for i in ITEMS:                                                          # elke bronverwijzing is gebonden aan het reviewpunt (basis voor een veilige import)
        assert i["ref_hash"] == H.ref_hash(i), i["review_id"]
    assert len({i["ref_hash"] for i in ITEMS}) == len(ITEMS)
    assert sum(i["review_type"] == "PLATE_READING" for i in ITEMS) == 11
    assert {i["review_id"] for i in ITEMS if i["review_type"] == "EXISTING_QUESTION"} >= {"HQ-VR-001", "HQ-VR-002", "HQ-VR-003", "HQ-VR-004"}
    app = {a for i in ITEMS for a in i["app_links"]}
    assert {"APP-001", "APP-002", "APP-003", "APP-011", "APP-012", "APP-013", "APP-031", "APP-034", "APP-035"} <= app
    srcs = {s["photo_id"]: s for s in REV["sources"]}
    for i in ITEMS:
        assert i["priority"] in ("P1", "P2", "P3") and i["evidence_refs"], i["review_id"]
        assert set(i["observation_ids"]) <= obs_ids
        assert set(i["relation_ids"]) <= rel_ids
        assert set(i["choices"]) == (OVL if i["review_type"] == "OVERLAP_RELATION" else STD)
        assert i["claude_proposal"] in i["choices"]
        for e in i["evidence_refs"]:
            if e["type"] == "original_crop":
                assert e["sha256"] == srcs[e["photo_id"]]["sha256_register"] and e["sha256_verified"] is True
                x0, y0, x1, y1 = e["region_px"]
                assert 0 <= x0 < x1 <= srcs[e["photo_id"]]["width_px"] and 0 <= y0 < y1 <= srcs[e["photo_id"]]["height_px"]
            if e["type"] == "report_figure":
                assert (REVIEW / e["file"]).exists()
    for m in re.findall(r"REF-MAP\d{3}-\d{3}", json.dumps(ITEMS)):
        assert m in ref_ids


def test_every_item_has_form_controls_and_nothing_preselected():
    for i in ITEMS:
        rid = i["review_id"]
        assert f'id="item-{rid}"' in HTML and f'id="c-{rid}"' in HTML
        vals = re.findall(rf'<input type="radio" name="d-{re.escape(rid)}" value="([A-Z_]+)"( checked)?>', HTML)
        assert {v for v, _ in vals} == {"OPEN"} | set(i["choices"])
        assert [v for v, c in vals if c] == ["OPEN"], rid       # alleen OPEN is gekozen; nooit een voorstel van Claude
        assert f'data-reset="{rid}"' in HTML
    assert 'data-priority="P1"' in HTML and 'data-priority="P3"' in HTML


def test_priorities_counts_consistent_and_not_unique_object_counts():
    c = INDEX["counts"]
    per = {p: sum(i["priority"] == p for i in ITEMS) for p in ("P1", "P2", "P3")}
    assert per == c["by_priority"] and sum(per.values()) == len(ITEMS)
    assert c["review_groups"] == 18 and len(INDEX["review_groups"]) == 18
    grouped = [r for g in INDEX["review_groups"] for r in g["relation_ids"]]
    assert sorted(grouped) == sorted(r["rel_id"] for r in REV["relations"]) and len(grouped) == 43   # elke relatie in precies een reviewgroep
    assert "geen aantallen unieke fysieke kozijnen" in HTML


def test_no_effects_and_sources_unchanged():
    e = INDEX["effects"]
    assert (e["instances_created"], e["bag_links_created"], e["building_totals"], e["costs"], e["app_decisions_open"]) == (0, 0, None, None, 48)
    assert e["claude_proposals_exported_as_human_decisions"] is False and e["default_decision"] == "OPEN"
    rows = [l for l in APPROVAL.splitlines() if re.match(r"\| APP-\d{3} \|", l)]
    assert len(rows) == 48 and all(r.rstrip().endswith("| OPEN |") for r in rows)
    c = INST["photo_visible_counts"]
    assert (c["PHOTO_VISIBLE_FRAME_COUNT"], c["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"], c["ordinary_frames_FULL"], c["ordinary_frames_PARTIAL"]) == (11, 1, 9, 2)
    assert all(v["value"] is None for v in INST["building_totals"].values())
    for f in (ROOT / "data").rglob("*.json"):
        t = f.read_text()
        assert "RV-OBS-" not in t and "RV-REL-" not in t and "RV-SEP-" not in t, f


def test_facade_overlap_and_object_overlap_are_technically_separated():
    rels = {r["rel_id"]: r for r in REV["relations"]}
    overlap = [i for i in ITEMS if i["review_type"] == "OVERLAP_RELATION"]
    assert len(overlap) == 43
    for i in overlap:
        sem, r = i["relation_semantics"], rels[i["relation_ids"][0]]
        expect = "FACADE_SECTION" if r["class"] == "SAME_FACADE_SECTION" else "PHYSICAL_OBJECT"
        assert sem["relation_type"] == expect and sem == H.relation_semantics(r["class"], r["left"], r["right"])
        imp = sem["implies_when_same"]
        assert imp["same_physical_frame_proven"] is False and imp["bag_pand_link"] is False and imp["merge"] is False and imp["unique_instance"] is False
        if expect == "FACADE_SECTION":                     # SAME_FACADE_SECTION nooit lezen als SAME_PHYSICAL_FRAME
            assert imp["same_facade_section"] is True and imp["same_physical_object_candidate"] is False
        else:
            assert imp["same_facade_section"] is False and imp["same_physical_object_candidate"] is True
    assert {i["relation_ids"][0] for i in overlap if i["relation_semantics"]["relation_type"] == "FACADE_SECTION"} == {"VR-001", "VR-020"}
    fac, obj = PACK_JSON["meaning"]["FACADE_SECTION"], PACK_JSON["meaning"]["PHYSICAL_OBJECT"]
    assert fac["SAME"] == "SAME_FACADE_SECTION" and obj["SAME"] == "SAME_PHYSICAL_OBJECT_CANDIDATE"
    assert set(fac.values()) & set(obj.values()) == {"UNDECIDABLE"}                   # de betekenissen delen niets behalve 'niet te beslissen'
    assert not re.search(r"(?<!POSSIBLY_)SAME_PHYSICAL_FRAME", HTML)                   # geen gevelbeslissing als hetzelfde fysieke kozijn
    for vr in ("VR-001", "VR-020"):
        assert 'rt-FACADE' in re.search(rf'id="item-RV-REL-{vr}".*?</article>', HTML, re.S).group(0)
        assert "Gevelsectie: dezelfde gevelsectie" not in HTML and "= SAME_FACADE_SECTION" in re.search(rf'id="item-RV-REL-{vr}".*?</article>', HTML, re.S).group(0)
    assert "= SAME_PHYSICAL_OBJECT_CANDIDATE" in re.search(r'id="item-RV-REL-VR-002".*?</article>', HTML, re.S).group(0)


def test_quality_review_blocks_and_proposal_corrections_visible_and_recorded():
    corr = {"RV-OBS-MAP003-027": ("UNDECIDABLE", "NEEDS_BETTER_PHOTO"), "RV-OBS-MAP004-022": ("UNDECIDABLE", "NEEDS_BETTER_PHOTO"),
            "RV-REL-VR-008": ("UNDECIDABLE", "SAME"), "RV-REL-VR-026": ("SAME", "UNDECIDABLE"), "RV-REL-VR-044": ("SAME", "UNDECIDABLE")}
    byid = {i["review_id"]: i for i in ITEMS}
    for rid, (old, new) in corr.items():
        assert byid[rid]["claude_proposal"] == new and byid[rid]["claude_proposal_v1"] == old
        assert f"gecorrigeerd t.o.v. v1.0.0: was {old}" in re.search(rf'id="item-{rid}".*?</article>', HTML, re.S).group(0)
    p1 = [i for i in ITEMS if i["priority"] == "P1"]
    assert len(p1) == 54 and all(i["quality"]["quality_status"] in ("TECHNICALLY_VALIDATED", "VISUALLY_SUPPORTED", "NEEDS_MANUAL_REVIEW", "NEEDS_BETTER_PHOTO") for i in p1)
    assert all("quality" not in i for i in ITEMS if i["priority"] != "P1")
    for i in p1:
        assert "Kwaliteitscontrole v1.1" in re.search(rf'id="item-{re.escape(i["review_id"])}".*?</article>', HTML, re.S).group(0)
    assert "Een technisch geldige reviewkaart is niet automatisch een visueel bewezen object" in HTML


def _browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    pw = sync_api.sync_playwright().start()
    for kw in ({"executable_path": "/opt/pw-browsers/chromium", "args": ["--no-sandbox"]}, {"args": ["--no-sandbox"]}):
        try:
            return pw, pw.chromium.launch(**kw)
        except Exception:
            continue
    pw.stop()
    pytest.skip("geen Chromium beschikbaar")


class Page:
    """Kleine hulpklasse rond een Playwright-pagina met de beslisformulier-handelingen."""

    def __init__(self, br, dl_dir=None):
        self.pg = br.new_page(viewport={"width": 1300, "height": 900}, accept_downloads=True)
        self.errors, self.requests = [], []
        self.pg.on("pageerror", lambda e: self.errors.append(str(e)))
        self.pg.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.pg.on("request", lambda r: self.requests.append(r.url))
        self.pg.on("dialog", lambda d: d.accept())
        self.pg.goto(HTML_PATH.as_uri())

    def export(self, scope="ALL"):
        self.pg.select_option("#export-scope", scope)
        self.pg.click("#btn-show")
        return json.loads(self.pg.input_value("#export-json"))

    def state(self):
        """Alle beslissingen/opmerkingen van de pagina, onafhankelijk van de export-omvang."""
        return {r["review_id"]: (r["human"]["decision"], r["human"]["comment"]) for r in self.export("ALL")["reviews"]}

    def choose(self, rid, val, comment=None):
        self.pg.check(f'input[name="d-{rid}"][value="{val}"]')
        if comment is not None:
            self.pg.fill(f"#c-{rid}", comment)

    def load(self, path):
        self.pg.set_input_files("#import-file", str(path))
        self.pg.wait_for_selector("#import-panel:not(.hidden)")

    def panel(self):
        return {"summary": self.pg.inner_text("#import-summary"), "errors": [e.inner_text() for e in self.pg.query_selector_all("#import-errors li")],
                "can_apply": self.pg.is_visible("#imp-replace") and self.pg.is_visible("#imp-merge")}


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return p


def test_form_in_browser_fill_change_reset_export_and_sources_unchanged(tmp_path):
    guarded = [p for p in list(REVIEW.glob("*.json")) + list(REVIEW.glob("*.md")) + [HTML_PATH] + list((ROOT / "data/frame_inventory").glob("*.json"))]
    before = {str(p): _sha(p) for p in guarded}
    pw, br = _browser()
    try:
        P = Page(br)
        pg = P.pg
        total = int(pg.inner_text("#cnt-total"))
        assert total == len(ITEMS) and pg.inner_text("#cnt-decided") == "0"
        ex0 = P.export()
        assert ex0["export_format"] == "maldenhof_visual_decision_export_v2" and ex0["status"] == "PROVISIONAL_HUMAN_REVIEW_RESULT_NOT_APPLIED"
        assert ex0["export_scope"]["kind"] == "FULL" and len(ex0["export_scope"]["included_review_ids"]) == total == len(ex0["reviews"])
        assert all(r["human"]["decision"] == "OPEN" and r["human"]["decision_source"] == "NONE" for r in ex0["reviews"])   # niets gekozen -> alles OPEN, ook met voorstellen aanwezig
        assert all(r["claude_non_binding"]["proposal"] for r in ex0["reviews"]) and ex0["summary"]["decided_by_human"] == 0
        assert not any(ex0["effects"].values()) and ex0["app_decisions"].startswith("ALL_48")
        assert all("decision" not in r and "claude_proposal_non_binding" not in r for r in ex0["reviews"])         # voorstel en besluit staan strikt gescheiden

        rid_rel, rid_obs, rid_plate = "RV-REL-VR-002", "RV-OBS-MAP003-001", "RV-PLATE-MAP003-288"
        P.choose(rid_rel, "SAME", "ziet er hetzelfde uit")
        P.choose(rid_obs, "CONFIRM")
        P.choose(rid_plate, "REJECT")
        P.choose(rid_plate, "NEEDS_BETTER_PHOTO")                                     # wijzigen
        ex1 = P.export()
        r = {x["review_id"]: x for x in ex1["reviews"]}
        assert (r[rid_rel]["human"]["decision"], r[rid_rel]["human"]["decision_source"], r[rid_rel]["human"]["comment"]) == ("SAME", "HUMAN", "ziet er hetzelfde uit")
        assert r[rid_plate]["human"]["decision"] == "NEEDS_BETTER_PHOTO" and r[rid_obs]["human"]["decision"] == "CONFIRM"
        assert ex1["summary"]["decided_by_human"] == 3 and ex1["summary"]["open"] == total - 3
        assert sum(1 for x in ex1["reviews"] if x["human"]["decision"] != "OPEN") == 3        # niet-beoordeelde punten blijven OPEN
        assert r[rid_rel]["claude_non_binding"]["proposal"] == "SAME" and r[rid_plate]["claude_non_binding"]["proposal"] == "CONFIRM"
        for k in ("review_id", "photo_ids", "observation_ids", "human", "source_evidence", "pack_version", "linked_app_decisions", "source_ref_hash", "claude_non_binding"):
            assert k in r[rid_rel]
        assert r[rid_rel]["source_evidence"] and r[rid_rel]["pack_version"] == PACK_JSON["pack_version"]
        pg.click(f'button[data-reset="{rid_obs}"]')                                   # terug naar OPEN
        assert P.export()["summary"]["decided_by_human"] == 2

        pg.click('button[data-filter="P3"]')                                          # filter
        assert pg.is_hidden(f"#item-{rid_rel}")                                        # P1-item verborgen bij filter P3
        pg.click('button[data-filter="ALL"]')

        with pg.expect_download() as dl:                                              # echte download (volledig)
            pg.click("#btn-export")
        path = tmp_path / "export.json"
        dl.value.save_as(str(path))
        exd = json.loads(path.read_text())
        assert exd["summary"]["decided_by_human"] == 2 and exd["pack_version"] == PACK_JSON["pack_version"]

        pg.reload()                                                                   # bewaren in de browser (alleen als beschikbaar)
        if "automatisch" in pg.inner_text("#persist-status"):
            assert pg.is_checked(f'input[name="d-{rid_rel}"][value="SAME"]') and pg.input_value(f"#c-{rid_rel}") == "ziet er hetzelfde uit"
        pg.click("#btn-reset-all")                                                    # alles terug naar OPEN
        assert P.export()["summary"]["decided_by_human"] == 0
        P.load(path)                                                                  # rondreis: eigen export terugladen
        assert P.panel()["can_apply"] and not P.panel()["errors"]
        pg.click("#imp-replace")
        st = P.state()
        assert sum(v[0] != "OPEN" for v in st.values()) == 2 and st[rid_rel] == ("SAME", "ziet er hetzelfde uit")
        assert P.errors == []
        assert all(u.startswith("file:") or u.startswith("data:") or u.startswith("blob:") for u in P.requests), P.requests   # geen netwerkverkeer
    finally:
        br.close()
        pw.stop()
    assert {str(p): _sha(p) for p in guarded} == before                                # geen bestaande brondata gewijzigd


def test_semantics_in_export_gevel_versus_object(tmp_path):
    pw, br = _browser()
    try:
        P = Page(br)
        P.choose("RV-REL-VR-001", "SAME")
        P.choose("RV-REL-VR-020", "DIFFERENT")
        P.choose("RV-REL-VR-002", "SAME")
        P.choose("RV-REL-VR-002".replace("002", "050"), "UNDECIDABLE")
        P.choose("RV-OBS-MAP003-010", "CONFIRM")
        r = {x["review_id"]: x for x in P.export()["reviews"]}
        a, b, c = r["RV-REL-VR-001"], r["RV-REL-VR-020"], r["RV-REL-VR-002"]
        assert a["relation_semantics"]["relation_type"] == "FACADE_SECTION" and a["human"]["decision_meaning"] == "SAME_FACADE_SECTION"
        assert a["human"]["implies"] == {"same_facade_section": True, "same_physical_object_candidate": False, "same_physical_frame_proven": False, "bag_pand_link": False, "merge": False, "unique_instance": False}
        assert b["human"]["decision_meaning"] == "DIFFERENT_FACADE_SECTION" and not any(b["human"]["implies"].values())
        assert c["relation_semantics"]["relation_type"] == "PHYSICAL_OBJECT" and c["human"]["decision_meaning"] == "SAME_PHYSICAL_OBJECT_CANDIDATE"
        assert c["human"]["implies"]["same_physical_object_candidate"] is True and c["human"]["implies"]["same_facade_section"] is False
        assert all(x["human"]["implies"]["same_physical_frame_proven"] is False and x["human"]["implies"]["bag_pand_link"] is False for x in r.values())
        assert r["RV-REL-VR-050"]["human"]["decision_meaning"] == "UNDECIDABLE"
        assert r["RV-OBS-MAP003-010"]["human"]["decision_meaning"] == "CONFIRM" and r["RV-OBS-MAP003-010"]["relation_semantics"] is None
        # een gevelbesluit mag nooit als objectbesluit worden geimporteerd (en omgekeerd): de betekenis moet bij het relatietype passen
        ex = P.export()
        for x in ex["reviews"]:
            if x["review_id"] == "RV-REL-VR-001":
                x["human"]["decision_meaning"] = "SAME_PHYSICAL_OBJECT_CANDIDATE"
        before = P.state()
        P.load(_write(tmp_path, "bad_meaning.json", ex))
        assert not P.panel()["can_apply"] and any("decision_meaning" in e and "VR-001" in e for e in P.panel()["errors"])
        assert P.state() == before and P.errors == []
    finally:
        br.close()
        pw.stop()


def _base_export(P, tmp_path):
    P.choose("RV-REL-VR-002", "SAME", "ok")
    P.choose("RV-OBS-MAP003-010", "CONFIRM", "klopt")
    P.choose("RV-OBS-MAP003-001", "UNDECIDABLE")
    return P.export()


def test_import_rejects_invalid_files_and_leaves_state_unchanged(tmp_path):
    pw, br = _browser()
    try:
        P = Page(br)
        good = _base_export(P, tmp_path)
        P.choose("RV-OBS-MAP003-002", "CONFIRM", "blijft staan")
        before = P.state()

        def mutate(fn):
            d = json.loads(json.dumps(good))
            fn(d)
            return d

        def by(d, rid):
            return next(x for x in d["reviews"] if x["review_id"] == rid)

        cases = {
            "pack_version": (mutate(lambda d: d.update(pack_version="human_visual_decision_pack_v9")), "pakketversie"),
            "review_package": (mutate(lambda d: d.update(review_package_version="x")), "reviewpakket"),
            "format": (mutate(lambda d: d.update(export_format="iets_anders")), "formaat"),
            "status": (mutate(lambda d: d.update(status="APPLIED")), "status"),
            "effects": (mutate(lambda d: d["effects"].update(instances_created=True)), "effects.instances_created"),
            "unknown_id": (mutate(lambda d: by(d, "RV-OBS-MAP003-001").update(review_id="RV-OBS-MAP999-001")), "onbekend review_id"),
            "duplicate_id": (mutate(lambda d: d["reviews"].append(json.loads(json.dumps(by(d, "RV-OBS-MAP003-010"))))), "dubbel review_id"),
            "invalid_choice": (mutate(lambda d: by(d, "RV-OBS-MAP003-010")["human"].update(decision="MAYBE")), "ongeldige keuze"),
            "overlap_choice_on_observation": (mutate(lambda d: by(d, "RV-OBS-MAP003-010")["human"].update(decision="SAME")), "ongeldige keuze"),
            "source_mismatch": (mutate(lambda d: by(d, "RV-OBS-MAP003-010")["human"].update(decision_source="NONE")), "decision_source"),
            "proposal_as_human": (mutate(lambda d: by(d, "RV-OBS-MAP003-002")["human"].update(decision="CONFIRM", decision_source="NONE")), "decision_source"),
            "ref_hash": (mutate(lambda d: by(d, "RV-REL-VR-002").update(source_ref_hash="0" * 16)), "bronverwijzing"),
            "type_changed": (mutate(lambda d: by(d, "RV-REL-VR-002").update(review_type="OBSERVATION")), "review_type"),
            "scope_ids": (mutate(lambda d: d["export_scope"]["included_review_ids"].pop()), "included_review_ids"),
            "full_incomplete": (mutate(lambda d: (d["reviews"].pop(), d["export_scope"]["included_review_ids"].pop())), "volledige export"),
            "no_reviews": (mutate(lambda d: d.update(reviews=[])), "reviews"),
            "human_missing": (mutate(lambda d: by(d, "RV-OBS-MAP003-010").pop("human")), "human ontbreekt"),
            "comment_type": (mutate(lambda d: by(d, "RV-OBS-MAP003-010")["human"].update(comment=5)), "opmerking"),
        }
        for name, (obj, needle) in cases.items():
            P.load(_write(tmp_path, f"{name}.json", obj))
            pan = P.panel()
            assert not pan["can_apply"] and pan["errors"] and any(needle in e for e in pan["errors"]), (name, pan)
            assert "afgewezen" in pan["summary"] and "niets gewijzigd" in pan["summary"]
            assert P.state() == before, name                        # geen enkele keuze of opmerking veranderd
        for name, text in (("notjson", "dit is geen json"), ("array", "[1,2,3]"), ("empty", "{}")):
            P.load(_write(tmp_path, f"{name}.json", text))
            assert not P.panel()["can_apply"] and P.panel()["errors"], name
            assert P.state() == before, name
        assert P.errors == []
    finally:
        br.close()
        pw.stop()


def test_import_replace_merge_partial_cancel_reset_and_reexport(tmp_path):
    pw, br = _browser()
    try:
        P = Page(br)
        pg = P.pg
        full = _base_export(P, tmp_path)                                    # 3 menselijke keuzes
        full_path = _write(tmp_path, "full.json", full)
        p1 = P.export("P1")                                                 # deelexport: alleen P1
        assert p1["export_scope"]["kind"] == "PARTIAL" and p1["export_scope"]["filter"] == "P1" and len(p1["reviews"]) == 54
        assert all(x["priority"] == "P1" for x in p1["reviews"]) and p1["summary"]["decided_by_human"] == 2 and p1["summary"]["pack_decided_by_human_total"] == 3
        decided = P.export("DECIDED")                                       # deelexport: alleen beoordeelde punten
        assert {x["review_id"] for x in decided["reviews"]} == {"RV-OBS-MAP003-001", "RV-OBS-MAP003-010", "RV-REL-VR-002"}
        assert decided["export_scope"]["kind"] == "PARTIAL" and all(x["human"]["decision"] != "OPEN" for x in decided["reviews"])
        p1_path, dec_path = _write(tmp_path, "p1.json", p1), _write(tmp_path, "decided.json", decided)

        # annuleren laat alles staan
        P.choose("RV-OBS-MAP003-002", "CONFIRM", "oude opmerking")           # P2/P3-punt dat niet in het P1-bestand zit
        before = P.state()
        P.load(p1_path)
        assert P.panel()["can_apply"] and "geldig" in P.panel()["summary"] and "PARTIAL" in P.panel()["summary"]
        pg.click("#imp-cancel")
        assert P.state() == before

        # volledig vervangen met een deelbestand: niet-opgenomen punten gaan naar OPEN, oude opmerkingen verdwijnen
        P.load(p1_path)
        pg.click("#imp-replace")
        st = P.state()
        assert st["RV-OBS-MAP003-002"] == ("OPEN", "")                                    # niet in het P1-bestand -> OPEN en opmerking weg
        assert st["RV-REL-VR-002"] == ("SAME", "ok") and st["RV-OBS-MAP003-010"] == ("CONFIRM", "klopt")
        assert sum(v[0] != "OPEN" for v in st.values()) == 2                              # OBS-MAP003-001 (P2) zat niet in het P1-bestand

        # gedeeltelijk samenvoegen: alleen de menselijke keuzes uit het bestand; OPEN-regels overschrijven niets
        P.choose("RV-OBS-MAP003-002", "REJECT", "blijft")                                  # niet in bestand
        P.choose("RV-OBS-MAP003-010", "REJECT", "eigen keuze")                              # in bestand: wordt overschreven met CONFIRM
        P.choose("RV-REL-VR-050", "DIFFERENT", "niet overschrijven")                       # in P1-bestand als OPEN: moet blijven
        P.load(p1_path)
        assert "overschreven" in P.panel()["summary"]
        pg.click("#imp-merge")
        st = P.state()
        assert st["RV-OBS-MAP003-002"] == ("REJECT", "blijft") and st["RV-REL-VR-050"] == ("DIFFERENT", "niet overschrijven")
        assert st["RV-OBS-MAP003-010"] == ("CONFIRM", "klopt") and st["RV-REL-VR-002"] == ("SAME", "ok")

        # deelbestand 'alleen beoordeelde punten' + vervangen
        P.load(dec_path)
        pg.click("#imp-replace")
        st = P.state()
        assert {k: v for k, v in st.items() if v[0] != "OPEN"} == {"RV-OBS-MAP003-001": ("UNDECIDABLE", ""), "RV-OBS-MAP003-010": ("CONFIRM", "klopt"), "RV-REL-VR-002": ("SAME", "ok")}
        assert all(v[1] == "" for k, v in st.items() if k not in ("RV-OBS-MAP003-010", "RV-REL-VR-002"))

        # onvolledig bestand dat zichzelf PARTIAL noemt is toegestaan en wordt bij vervangen aangevuld met OPEN
        part = json.loads(full_path.read_text())
        part["export_scope"]["kind"] = "PARTIAL"
        part["reviews"] = [x for x in part["reviews"] if x["review_id"] in ("RV-REL-VR-002", "RV-OBS-MAP003-010", "RV-OBS-MAP003-001")]
        part["export_scope"]["included_review_ids"] = [x["review_id"] for x in part["reviews"]]
        P.choose("RV-PLATE-MAP003-288", "CONFIRM", "weg")
        P.load(_write(tmp_path, "partial_by_hand.json", part))
        pg.click("#imp-replace")
        st = P.state()
        assert st["RV-PLATE-MAP003-288"] == ("OPEN", "") and sum(v[0] != "OPEN" for v in st.values()) == 3

        # claude-voorstellen komen nooit in de beslissingen: bestand met alleen OPEN maar andere voorstellen wijzigt niets bij samenvoegen en zet alles op OPEN bij vervangen
        blank = P.export("ALL")
        for x in blank["reviews"]:
            x["human"].update(decision="OPEN", decision_source="NONE", comment="", decision_meaning="OPEN")
            x["claude_non_binding"]["proposal"] = "SAME"
        bp = _write(tmp_path, "blank.json", blank)
        P.load(bp)
        pg.click("#imp-merge")
        assert sum(v[0] != "OPEN" for v in P.state().values()) == 3
        P.load(bp)
        pg.click("#imp-replace")
        assert all(v == ("OPEN", "") for v in P.state().values())

        # resetten, importeren en opnieuw exporteren geeft hetzelfde menselijke resultaat
        P.load(full_path)
        pg.click("#imp-replace")
        again = P.export("ALL")
        assert {x["review_id"]: (x["human"]["decision"], x["human"]["comment"]) for x in again["reviews"] if x["human"]["decision"] != "OPEN"} == \
            {x["review_id"]: (x["human"]["decision"], x["human"]["comment"]) for x in full["reviews"] if x["human"]["decision"] != "OPEN"}
        pg.click("#btn-reset-all")
        assert all(v == ("OPEN", "") for v in P.state().values())
        pg.select_option("#export-scope", "DECIDED")                       # niets beoordeeld: geen leeg deelbestand downloaden
        pg.click("#btn-export2")
        assert "niets te exporteren" in pg.inner_text("#export-msg")
        assert P.errors == []
    finally:
        br.close()
        pw.stop()


def test_import_of_old_v1_export_skips_facade_decisions(tmp_path):
    pw, br = _browser()
    try:
        P = Page(br)
        legacy = {"export_format": "maldenhof_visual_decision_export_v1", "pack_version": PACK_JSON["legacy_pack_version"], "review_package_version": PACK_JSON["review_package_version"],
                  "status": "PROVISIONAL_HUMAN_REVIEW_RESULT_NOT_APPLIED", "effects": {"instances_created": False, "merges_performed": False},
                  "reviews": [{"review_id": "RV-REL-VR-001", "decision": "SAME", "decision_source": "HUMAN", "comment": "oude betekenis"},
                              {"review_id": "RV-REL-VR-002", "decision": "SAME", "decision_source": "HUMAN", "comment": ""},
                              {"review_id": "RV-OBS-MAP003-001", "decision": "OPEN", "decision_source": "NONE", "comment": ""}]}
        P.load(_write(tmp_path, "legacy.json", legacy))
        pan = P.panel()
        assert pan["can_apply"] and "oud formaat v1" in pan["summary"] and any("VR-001" in e and "opnieuw beoordelen" in e for e in pan["errors"])
        P.pg.click("#imp-replace")
        st = P.state()
        assert st["RV-REL-VR-001"][0] == "OPEN" and st["RV-REL-VR-002"] == ("SAME", "")
        bad = dict(legacy, pack_version="human_visual_decision_pack_v1.2.0")
        P.load(_write(tmp_path, "legacy_bad.json", bad))
        assert not P.panel()["can_apply"]
        assert P.errors == []
    finally:
        br.close()
        pw.stop()


PILOT = ["RV-SEP-001", "RV-REL-VR-027", "RV-REL-VR-020", "RV-REL-VR-024", "RV-REL-VR-026", "RV-OBS-MAP004-012", "RV-OBS-MAP003-027", "RV-OBS-MAP003-009", "RV-OBS-MAP003-010", "HQ-VR-001"]


def test_pilot_section_uses_existing_items_and_explains_each_point():
    assert [i["review_id"] for i in sorted((i for i in ITEMS if "pilot" in i), key=lambda i: i["pilot"]["order"])] == PILOT
    sec = re.search(r'<section id="pilot">.*?</section>', HTML, re.S).group(0)
    assert sec.count('class="pilot-card"') == 10 and sec.count('data-pilot="1"') == 10
    for rid in PILOT:
        assert f'id="item-{rid}"' in sec and HTML.count(f'id="item-{rid}"') == 1            # elk punt precies een keer: de bestaande reviewkaart
        assert f'name="d-{rid}" value="OPEN" checked' in sec
    for lab in ("Wat is zichtbaar", "Welke beslissing is nodig", "Welk bewijs ondersteunt het voorstel", "Wat is nog onzeker", "Wat de keuze wel doet", "Wat de keuze niet doet"):
        assert sec.count(f"<h4>{lab}</h4>") == 10, lab
    assert all(i["pilot"]["situation"] for i in ITEMS if "pilot" in i) and sum("pilot" in i for i in ITEMS) == 10
    # alleen bestaande classificaties: geen nieuwe review-ID's, aantal punten ongewijzigd
    assert len(ITEMS) == 123 and set(PILOT) <= {i["review_id"] for i in ITEMS}


def test_pilot_filter_and_export_keep_all_other_points_open_in_browser(tmp_path):
    pw, br = _browser()
    try:
        P = Page(br)
        pg = P.pg
        pg.click('button[data-filter="PILOT"]')
        assert pg.locator(".review-item:visible").count() == 10
        assert {pg.locator(".review-item:visible").nth(k).get_attribute("data-id") for k in range(10)} == set(PILOT)
        assert pg.is_visible("#pilot") and pg.is_visible("#exportsec") and not pg.is_visible("#RG-01")
        choices = {"RV-SEP-001": "CONFIRM", "RV-REL-VR-027": "SAME", "RV-REL-VR-020": "SAME", "RV-REL-VR-024": "UNDECIDABLE", "RV-REL-VR-026": "UNDECIDABLE",
                   "RV-OBS-MAP004-012": "UNDECIDABLE", "RV-OBS-MAP003-027": "NEEDS_BETTER_PHOTO", "RV-OBS-MAP003-009": "UNDECIDABLE", "RV-OBS-MAP003-010": "CONFIRM", "HQ-VR-001": "UNDECIDABLE"}
        for rid, c in choices.items():
            P.choose(rid, c, f"opm {rid}")
        pex = P.export("PILOT")
        assert pex["export_scope"] == {"kind": "PARTIAL", "filter": "PILOT", "included_review_ids": [i["review_id"] for i in ITEMS if "pilot" in i], "pack_review_points_total": 123}
        assert len(pex["reviews"]) == 10 and pex["summary"]["decided_by_human"] == 10 and pex["summary"]["open"] == 0
        r = {x["review_id"]: x for x in pex["reviews"]}
        for rid, c in choices.items():
            h = r[rid]["human"]
            assert (h["decision"], h["decision_source"], h["comment"]) == (c, "HUMAN", f"opm {rid}")
        assert r["RV-REL-VR-020"]["human"]["decision_meaning"] == "SAME_FACADE_SECTION" and r["RV-REL-VR-020"]["human"]["implies"]["same_physical_frame_proven"] is False
        assert r["RV-REL-VR-027"]["human"]["decision_meaning"] == "SAME_PHYSICAL_OBJECT_CANDIDATE" and r["RV-REL-VR-027"]["human"]["implies"]["bag_pand_link"] is False
        full = P.export("ALL")
        others = [x for x in full["reviews"] if x["review_id"] not in PILOT]
        assert len(others) == 113 and all(x["human"]["decision"] == "OPEN" and x["human"]["decision_source"] == "NONE" and x["human"]["comment"] == "" for x in others)
        # het pilotbestand kan in een schone pagina als deelbestand worden teruggeladen
        path = tmp_path / "pilot.json"
        path.write_text(json.dumps(pex))
        pg.click("#btn-reset-all")
        P.load(path)
        pg.click("#imp-replace")
        st = P.state()
        assert {k for k, v in st.items() if v[0] != "OPEN"} == set(PILOT) and st["RV-OBS-MAP003-027"][0] == "NEEDS_BETTER_PHOTO"
        # een export van het vorige pakket (v1.1.0) blijft bruikbaar
        old = json.loads(json.dumps(full))
        old["pack_version"] = "human_visual_decision_pack_v1.1.0"
        P.load(_write(tmp_path, "v110.json", old))
        assert P.panel()["can_apply"] and not P.panel()["errors"]
        pg.click("#imp-cancel")
        pg.click('button[data-filter="ALL"]')
        assert not pg.evaluate("document.body.classList.contains('pilot-only')")
        assert P.errors == []
    finally:
        br.close()
        pw.stop()
