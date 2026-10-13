"""Regressietests uit de onafhankelijke eindcontrole van PR #41 (import-veiligheid en afscherming)."""
import json
import re

from test_human_visual_decision_pack import Page, _base_export, _browser, _write, REVIEW, ROOT

REGISTER = REVIEW / "pilot_decisions/maldenhof_pilot_decision_register_v1.json"
CONFIRMED = REVIEW / "pilot_decisions/maldenhof_pilot_10_bevestigd_in_chat.json"
TEMPLATE = (ROOT / "scripts/human_decision_pack_template.html").read_text()


def _by(d, rid):
    return next(x for x in d["reviews"] if x["review_id"] == rid)


def test_prototype_keys_and_html_injection_are_rejected_or_inert(tmp_path):
    pw, br = _browser()
    try:
        P = Page(br)
        good = _base_export(P, tmp_path)
        P.choose("RV-OBS-MAP003-002", "CONFIRM", "blijft staan")
        before = P.state()
        for bad_id in ("__proto__", "constructor", "toString", "hasOwnProperty"):
            d = json.loads(json.dumps(good))
            _by(d, "RV-OBS-MAP003-001")["review_id"] = bad_id
            P.load(_write(tmp_path, f"proto_{bad_id}.json", d))
            pan = P.panel()
            assert not pan["can_apply"] and any("onbekend review_id" in e for e in pan["errors"]), (bad_id, pan)
            assert P.state() == before
        # __proto__ als sleutel in een entry mag niets vervuilen
        raw = json.dumps(good)[:-1] + ', "__proto__": {"polluted": true}}'
        P.load(_write(tmp_path, "proto_key.json", raw))
        assert P.pg.evaluate("({}).polluted === undefined")
        # HTML in een opmerking wordt als tekst behandeld
        d = json.loads(json.dumps(good))
        h = _by(d, "RV-OBS-MAP003-010")["human"]
        h.update(decision="CONFIRM", decision_source="HUMAN", comment='<img src=x onerror="window.__pwned=1"><script>window.__pwned=2</script>')
        P.load(_write(tmp_path, "inject.json", d))
        pan = P.panel()
        if pan["can_apply"]:
            P.pg.click("#imp-replace")
        assert P.pg.evaluate("window.__pwned === undefined")
        assert P.errors == []
    finally:
        br.close()
        pw.stop()


def test_register_and_ai_advice_cannot_be_imported_as_html_export(tmp_path):
    pw, br = _browser()
    try:
        P = Page(br)
        _base_export(P, tmp_path)
        before = P.state()
        for name in (REGISTER, CONFIRMED):
            P.load(name)
            pan = P.panel()
            assert not pan["can_apply"] and pan["errors"], name.name
            assert P.state() == before
    finally:
        br.close()
        pw.stop()


def test_import_code_only_writes_through_text_and_value_never_html():
    # geen onveilige opmaak-sinks voor door gebruikers aangeleverde tekst
    assert not re.search(r"\beval\(|new Function|document\.write|insertAdjacentHTML|outerHTML\s*=", TEMPLATE)
    for m in re.finditer(r"\.innerHTML\s*=\s*([^;\n]+)", TEMPLATE):
        assert m.group(1).strip() in ('""', "''"), m.group(0)
