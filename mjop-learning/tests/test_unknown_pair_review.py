"""
Tests voor de reviewtrack UNKNOWN_PAIR_REVIEW (comparability_review_v2 + apply_family_decision) en het read-only
beslispakket 4645|interior_painting|m2|wood.

  - een UNKNOWN-paar is alleen reviewbaar als ALLE voorwaarden gelden;
  - system_class blijft UNKNOWN, unknown_reasons blijven bewaard (pakket en record);
  - review_note verplicht voor COMPARABLE_WITH_CAVEATS; NOT_COMPARABLE werkt; COMPARABLE/UNKNOWN geweigerd;
  - hash binding, atomaire familiebesluiten (ook meerdere UNKNOWN-paren in één familie), rollback;
  - bestaande families en de besluiten/kengetallen van 5211 en 4711 blijven geldig;
  - het 4645-pakket verandert geen canonieke data.

Het echte repo wordt alleen gelezen (gecontroleerd met hashes); writes alleen in een tijdelijke kopie.
"""
import copy
import json
import os
import shutil
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import apply_family_decision as afd  # noqa: E402
import canonical_change as cc  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import decision_package_4645_interior_painting_wood as dp  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402

MULTI = "RF-4631-f714c6d97b"            # 4 UNKNOWN-paren, alle QUANTITY_SCALE_DIFFERENCE + PRICE_LEVEL_ABSENT
SINGLE = "RF-4621-004dc9d137"           # PAIR-00054
OTHER = "RF-4622-354fcb80f6"            # PAIR-00307, geen caveats


def _protected():
    out = pl.tracked_hashes(PROJECT_ROOT)
    for rel in (crv.OUT_JSON, crv.OUT_MD, dp.OUT_JSON, dp.OUT_MD):
        out[rel] = pl.sha256_file(os.path.join(PROJECT_ROOT, rel))
    return out


@pytest.fixture(scope="module", autouse=True)
def real_repo_unchanged():
    before = _protected()
    yield
    assert _protected() == before, "het echte repo is gewijzigd"


@pytest.fixture(scope="module")
def ctx():
    return crv.Context(PROJECT_ROOT)


@pytest.fixture(scope="module")
def pkg():
    return json.load(open(os.path.join(PROJECT_ROOT, crv.OUT_JSON), encoding="utf-8"))


def fam(pkg, fid):
    return next(f for f in pkg["families"] if f["review_family_id"] == fid)


# ------------------------------------------------------------------ selectie

def test_selection_requires_every_condition(ctx):
    p = copy.deepcopy(ctx.pairs["PAIR-00054"])
    assert p["class"] == "UNKNOWN" and crv.unknown_pair_blockers(ctx, p) == []
    a, b = p["observation_ids"]

    def blockers_with(mutate):
        c = copy.copy(ctx)
        c.assess = copy.deepcopy(ctx.assess)
        c.norm = copy.deepcopy(ctx.norm)
        q = copy.deepcopy(p)
        mutate(c, q)
        return crv.unknown_pair_blockers(c, q)

    assert blockers_with(lambda c, q: c.assess[a].update(independent_input=False)) == ["NOT_INDEPENDENT_INPUT"]
    assert blockers_with(lambda c, q: c.assess[b].update(candidate_key=[None, "exterior_painting", "m2"])) == \
        ["CANDIDATE_KEY_INCOMPLETE"]
    assert blockers_with(lambda c, q: c.assess[b].update(candidate_key=["4621", "exterior_painting", "m1"])) == \
        ["CANDIDATE_KEY_MISMATCH"]
    assert blockers_with(lambda c, q: c.assess[a].update(material={"original": None, "normalized": None,
                                                                   "source": None})) == ["MATERIAL_UNKNOWN"]
    assert blockers_with(lambda c, q: c.assess[a].update(material={"original": "staal", "normalized": "steel",
                                                                   "source": "verified_element"})) == ["MATERIAL_DIFFERS"]
    assert blockers_with(lambda c, q: c.assess[b].update(source_cluster=c.assess[a]["source_cluster"])) == \
        ["SAME_SOURCE_CLUSTER"]
    assert blockers_with(lambda c, q: q.update(hard_violations=["UNIT_MISMATCH"])) == ["HARD_VIOLATIONS"]

    def no_text(c, q):
        crv.primary(c.norm[a])["source_text"] = ""
    assert blockers_with(no_text) == ["INSUFFICIENT_PROVENANCE"]
    q = copy.deepcopy(p)
    q["class"] = "COMPARABLE_WITH_CAVEATS"
    assert crv.unknown_pair_blockers(ctx, q) == ["NOT_SYSTEM_CLASS_UNKNOWN"]


def test_queue_and_counts_consistent(ctx, pkg):
    u = pkg["unknown_pair_review"]
    unknown = [p for p in ctx.comp["pairs"] if p["class"] == "UNKNOWN"]
    assert u["unknown_pairs_total"] == u["outside_review_queue_before_unknown_track"] == len(unknown)
    assert u["reviewable"] + u["blocked"] == len(unknown)
    assert u["reviewable_pair_ids"] == [p["pair_id"] for p in crv.select_unknown_pairs(ctx)]
    track_pairs = sorted(pid for f in pkg["families"] if f["review_track"] == crv.UNKNOWN_TRACK for pid in f["pair_ids"])
    assert track_pairs == sorted(u["reviewable_pair_ids"])
    # de 4645-paren zijn nu (materiaal onbekend) nog NIET reviewbaar
    for pid in dp.EXPECTED_PAIRS:
        assert pid not in u["reviewable_pair_ids"] and "MATERIAL_UNKNOWN" in crv.unknown_pair_blockers(ctx, ctx.pairs[pid])


def test_system_class_and_unknown_reasons_preserved(ctx, pkg):
    comp = {p["pair_id"]: p for p in ctx.comp["pairs"]}
    for f in pkg["families"]:
        if f["review_track"] != crv.UNKNOWN_TRACK:
            continue
        assert [c["choice"] for c in f["allowed_human_choices"]] == list(crv.UNKNOWN_TRACK_CHOICES)
        assert f["allowed_human_choices"][0]["requires_review_note"] is True
        for p in f["pairs"]:
            assert p["system_class"] == comp[p["pair_id"]]["class"] == "UNKNOWN"
            assert p["unknown_reasons"] == comp[p["pair_id"]]["unknown_reasons"] and p["unknown_reasons"]
            assert f["unknown_reasons"] == sorted(p["unknown_reasons"])
            assert len(p["provenance"]) == 2 and all(x["source_text"] for x in p["provenance"])


def test_existing_families_unchanged_vs_main(pkg):
    try:
        base = subprocess.check_output(["git", "merge-base", "HEAD", "origin/main"], cwd=PROJECT_ROOT, text=True).strip()
        old = json.loads(subprocess.check_output(
            ["git", "show", f"{base}:mjop-learning/reports/review/comparability_review_v2.json"], cwd=PROJECT_ROOT))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("geen git-basis beschikbaar")
    if "unknown_pair_review" in old:
        pytest.skip("basis bevat de UNKNOWN-track al")
    new = {f["review_family_id"]: f for f in pkg["families"] if f["review_track"] != crv.UNKNOWN_TRACK}
    assert {f["review_family_id"]: (f["pair_ids"], f["family_input_sha256"]) for f in old["families"]} == \
        {k: (f["pair_ids"], f["family_input_sha256"]) for k, f in new.items()}


# ------------------------------------------------------------------ toepassen op een kopie

def make_copy(dst):
    for rel in pr.SIMULATION_COPY + ("reports/review",):
        s, d = os.path.join(PROJECT_ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return dst


@pytest.fixture()
def proj(tmp_path):
    return make_copy(str(tmp_path / "p"))


def entry(pkg, fid, note="menselijke onderbouwing: zelfde onderhoudssemantiek, objecttekst beoordeeld"):
    f = fam(pkg, fid)
    caveats = sorted({c for p in f["pairs"] for c in p["pair_caveats"]})
    return {"review_family_id": fid, "family_input_sha256": f["family_input_sha256"], "pair_ids": f["pair_ids"],
            "decision_caveats": caveats, "review_note": note}


def decision(root, pkg, fids, choice="COMPARABLE_WITH_CAVEATS", **kw):
    d = {"review_package_sha256": pl.sha256_file(os.path.join(root, crv.OUT_JSON)),
         "decision": choice, "decision_reason": "testbesluit", "reviewer": "tester",
         "reviewed_at": "2026-09-29T12:00:00Z", "notes": None, "acknowledged_kengetal_effects": [],
         "families": [entry(pkg, f, **kw) for f in fids]}
    return d


def test_positive_requires_review_note_and_disallows_other_choices(proj, pkg):
    before = pl.tracked_hashes(proj)
    d = decision(proj, pkg, [SINGLE], note="  ")
    with pytest.raises(afd.FamilyDecisionError, match="review_note"):
        afd.apply(proj, d)
    for choice in ("COMPARABLE", "UNKNOWN"):
        with pytest.raises(afd.FamilyDecisionError, match="alleen"):
            afd.apply(proj, decision(proj, pkg, [SINGLE], choice=choice))
    d = decision(proj, pkg, [SINGLE])
    d["families"][0]["decision_caveats"] = []          # bestaande paarcaveat weglaten
    with pytest.raises(afd.FamilyDecisionError, match="moeten in decision_caveats blijven"):
        afd.apply(proj, d)
    d = decision(proj, pkg, [SINGLE])
    d["families"][0]["decision_caveats"].append("UPGRADE")   # nieuwe caveat
    with pytest.raises(afd.FamilyDecisionError, match="geen nieuwe caveats"):
        afd.apply(proj, d)
    assert pl.tracked_hashes(proj) == before


def test_multi_pair_unknown_family_positive_record_and_rollback(proj, pkg):
    before = pl.tracked_hashes(proj)
    comp_before = pl.sha256_file(os.path.join(proj, crv.COMP))
    d = decision(proj, pkg, [MULTI, OTHER])
    st = afd.apply(proj, d, now="2026-09-29T12:00:00Z")
    new = [r for r in pr.load(os.path.join(proj, pr.DECISIONS_PATH))["records"]
           if r["decision_id"] in st["summary"]["applied_decision_ids"]]
    assert len(new) == len(fam(pkg, MULTI)["pair_ids"]) + 1
    comp = {p["pair_id"]: p for p in pr.load(os.path.join(proj, crv.COMP))["pairs"]}
    for r in new:
        assert r["system_class"] == "UNKNOWN" == comp[r["pair_id"]]["class"]
        assert r["system_reasons"]["unknown_reasons"] == comp[r["pair_id"]]["unknown_reasons"]
        fd = r["family_decision"]
        assert fd["review_track"] == crv.UNKNOWN_TRACK and fd["review_note"]
        assert fd["unknown_reasons_at_review"] == comp[r["pair_id"]]["unknown_reasons"]
        assert r["decision"] == "COMPARABLE_WITH_CAVEATS" and r["status"] == "ACTIVE"
    assert pl.sha256_file(os.path.join(proj, crv.COMP)) == comp_before      # comparability onveranderd
    assert cc.rollback(proj, st["promotion_id"]).startswith("ROLLBACK OK")
    assert pl.tracked_hashes(proj) == before


def test_not_comparable_without_note(proj, pkg):
    d = decision(proj, pkg, [SINGLE], choice="NOT_COMPARABLE", note=None)
    d["families"][0]["decision_caveats"] = []
    st = afd.apply(proj, d, now="2026-09-29T12:00:00Z")
    (r,) = [r for r in pr.load(os.path.join(proj, pr.DECISIONS_PATH))["records"]
            if r["decision_id"] in st["summary"]["applied_decision_ids"]]
    assert r["decision"] == "NOT_COMPARABLE" and r["system_class"] == "UNKNOWN"
    assert r["family_decision"]["review_note"] is None


def test_hash_binding_and_atomicity(proj, pkg):
    before = pl.tracked_hashes(proj)
    d = decision(proj, pkg, [MULTI, SINGLE])
    d["families"][1]["family_input_sha256"] = "0" * 64
    with pytest.raises(afd.FamilyDecisionError, match="family_input_sha256"):
        afd.apply(proj, d)
    d = decision(proj, pkg, [MULTI, SINGLE])
    d["review_package_sha256"] = "0" * 64
    with pytest.raises(afd.FamilyDecisionError, match="reviewpakket"):
        afd.apply(proj, d)
    d = decision(proj, pkg, [MULTI, SINGLE])
    d["families"][1]["review_note"] = ""             # één familie ongeldig -> niets toegepast
    with pytest.raises(afd.FamilyDecisionError, match="review_note"):
        afd.apply(proj, d)
    assert pl.tracked_hashes(proj) == before


def test_existing_5211_4711_decisions_still_valid(ctx):
    kg = {k["kengetal_id"]: k for k in json.load(open(os.path.join(PROJECT_ROOT, crv.KG), encoding="utf-8"))["kengetallen"]}
    assert (kg["KG-5211-replace-m1-pvc-5cb98033"]["status"], kg["KG-5211-replace-m1-pvc-5cb98033"]["value_display"]) == \
        ("AVAILABLE", "54.39")
    assert (kg["KG-4711-replace-m1-aluminium-d463b0a2"]["status"],
            kg["KG-4711-replace-m1-aluminium-d463b0a2"]["value_display"]) == ("AVAILABLE", "37.47")
    active = {r["decision_id"] for r in ctx.store["records"] if r["status"] == "ACTIVE"}
    assert {f"HDR-{n:05d}" for n in range(36, 46)} <= active
    assert pl.chain_errors(PROJECT_ROOT) == [] and pr.verify(PROJECT_ROOT) == []


# ------------------------------------------------------------------ 4645-pakket

@pytest.fixture(scope="module")
def package():
    return dp.build(PROJECT_ROOT)


def test_4645_package_committed_readonly_and_ids(package):
    assert crv.dump(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_JSON), encoding="utf-8").read()
    assert dp.render_md(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_MD), encoding="utf-8").read()
    iv = package["id_verification"]
    assert iv["observations_match"] and iv["pairs_match"] and iv["mapping"] == {}
    assert [m["observation_id"] for m in package["material"]] == dp.EXPECTED_OBSERVATIONS
    assert all(m["record_material_decision_precheck"] == "WOULD_BE_ACCEPTED" and m["proposed_material"] == "wood"
               and m["current_material"]["value"] is None for m in package["material"])
    for p in package["pairs_current"]:
        assert p["system_class"] == "UNKNOWN" and "MATERIAL_UNKNOWN" in p["unknown_track_blockers"]
    for p in package["pairs_after_material_decision"]:
        assert p["system_class"] == "UNKNOWN" and p["unknown_track_blockers"] == [] and p["unknown_track_family_id"]
        assert p["unknown_reasons"] and p["hard_violations"] == []
    assert len(package["review_families_after_material_decision"]) == 3


def test_4645_simulations_follow_rules(package):
    sims = {s["scenario"]: s for s in package["simulations"]}
    assert sims["CURRENT"]["kengetal_groups"] == [] and not sims["CURRENT"]["available_kengetal"]
    assert sims["CURRENT_PLUS_MATERIAL_ONLY"]["kengetal_groups"] == []
    for k, s in sims.items():
        if k.startswith("MATERIAL_PLUS_1_POSITIVE") or k.startswith("MATERIAL_PLUS_2_POSITIVE"):
            assert not s["available_kengetal"]
    (all3,) = sims["MATERIAL_PLUS_ALL_3_POSITIVE"]["kengetal_groups"]
    assert (all3["status"], all3["source_cluster_count"], all3["median_display"], all3["min_display"],
            all3["max_display"]) == ("AVAILABLE", 3, "45.81", "44.18", "54.45")
    assert all3["observation_ids"] == dp.EXPECTED_OBSERVATIONS and all3["missing_cross_cluster_reviews"] == []
    for k, s in sims.items():
        if "NOT_COMPARABLE" in k:
            assert any(r.startswith("NOT_COMPARABLE_WITHIN_GROUP") for g in s["kengetal_groups"]
                       for r in g["insufficient_data_reasons"])
