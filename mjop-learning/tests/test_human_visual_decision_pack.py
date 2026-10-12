import base64
import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
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


def test_form_in_browser_fill_change_reset_export_and_sources_unchanged(tmp_path):
    guarded = [p for p in list(REVIEW.glob("*.json")) + list(REVIEW.glob("*.md")) + [HTML_PATH] + list((ROOT / "data/frame_inventory").glob("*.json"))]
    before = {str(p): _sha(p) for p in guarded}
    pw, br = _browser()
    try:
        pg = br.new_page(viewport={"width": 1300, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        requests = []
        pg.on("request", lambda r: requests.append(r.url))
        pg.goto(HTML_PATH.as_uri())
        total = int(pg.inner_text("#cnt-total"))
        assert total == len(ITEMS) and pg.inner_text("#cnt-decided") == "0"

        def export():
            pg.click("#btn-show")
            return json.loads(pg.input_value("#export-json"))

        ex0 = export()
        assert ex0["export_format"] == "maldenhof_visual_decision_export_v1" and ex0["status"] == "PROVISIONAL_HUMAN_REVIEW_RESULT_NOT_APPLIED"
        assert all(r["decision"] == "OPEN" and r["decision_source"] == "NONE" for r in ex0["reviews"])   # niets gekozen -> alles OPEN, ook met voorstellen aanwezig
        assert all(r["claude_proposal_non_binding"] for r in ex0["reviews"]) and ex0["summary"]["decided_by_human"] == 0
        assert not any(ex0["effects"].values()) and ex0["app_decisions"].startswith("ALL_48")

        rid_rel, rid_obs, rid_plate = "RV-REL-VR-002", "RV-OBS-MAP003-001", "RV-PLATE-MAP003-288"
        pg.check(f'input[name="d-{rid_rel}"][value="SAME"]')                      # invullen
        pg.fill(f"#c-{rid_rel}", "ziet er hetzelfde uit")
        pg.check(f'input[name="d-{rid_obs}"][value="CONFIRM"]')
        pg.check(f'input[name="d-{rid_plate}"][value="REJECT"]')
        pg.check(f'input[name="d-{rid_plate}"][value="NEEDS_BETTER_PHOTO"]')         # wijzigen
        ex1 = export()
        r = {x["review_id"]: x for x in ex1["reviews"]}
        assert (r[rid_rel]["decision"], r[rid_rel]["decision_source"], r[rid_rel]["comment"]) == ("SAME", "HUMAN", "ziet er hetzelfde uit")
        assert r[rid_plate]["decision"] == "NEEDS_BETTER_PHOTO" and r[rid_obs]["decision"] == "CONFIRM"
        assert ex1["summary"]["decided_by_human"] == 3 and ex1["summary"]["open"] == total - 3
        assert sum(1 for x in ex1["reviews"] if x["decision"] != "OPEN") == 3        # niet-beoordeelde punten blijven OPEN
        assert r[rid_rel]["claude_proposal_non_binding"] == "SAME" and r[rid_plate]["claude_proposal_non_binding"] == "CONFIRM"
        for k in ("review_id", "photo_ids", "observation_ids", "decision", "comment", "source_evidence", "pack_version", "linked_app_decisions"):
            assert k in r[rid_rel]
        assert r[rid_rel]["source_evidence"] and r[rid_rel]["pack_version"] == PACK_JSON["pack_version"]
        pg.click(f'button[data-reset="{rid_obs}"]')                                   # terug naar OPEN
        ex2 = export()
        assert {x["review_id"]: x for x in ex2["reviews"]}[rid_obs]["decision"] == "OPEN" and ex2["summary"]["decided_by_human"] == 2

        pg.click('button[data-filter="P3"]')                                          # filter
        assert pg.is_hidden(f"#item-{rid_rel}")                                        # P1-item verborgen bij filter P3
        pg.click('button[data-filter="ALL"]')

        with pg.expect_download() as dl:                                              # echte download
            pg.click("#btn-export")
        path = tmp_path / "export.json"
        dl.value.save_as(str(path))
        exd = json.loads(path.read_text())
        assert exd["summary"]["decided_by_human"] == 2 and exd["pack_version"] == PACK_JSON["pack_version"]

        pg.reload()                                                                   # bewaren in de browser (alleen als beschikbaar)
        if "automatisch" in pg.inner_text("#persist-status"):
            assert pg.is_checked(f'input[name="d-{rid_rel}"][value="SAME"]') and pg.input_value(f"#c-{rid_rel}") == "ziet er hetzelfde uit"
        pg.on("dialog", lambda d: d.accept())
        pg.click("#btn-reset-all")                                                    # alles terug naar OPEN
        assert export()["summary"]["decided_by_human"] == 0
        pg.set_input_files("#import-file", str(path))
        pg.wait_for_timeout(300)
        assert export()["summary"]["decided_by_human"] == 2
        assert errors == []
        assert all(u.startswith("file:") or u.startswith("data:") or u.startswith("blob:") for u in requests), requests   # geen netwerkverkeer
    finally:
        br.close()
        pw.stop()
    assert {str(p): _sha(p) for p in guarded} == before                                # geen bestaande brondata gewijzigd
