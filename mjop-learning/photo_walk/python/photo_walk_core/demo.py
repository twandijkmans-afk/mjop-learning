"""Reproduceerbare demonstratie (python -m photo_walk_core.demo --out <map buiten de repo>). Alleen synthetische data."""
import argparse
import json
import sys
import tempfile
from decimal import Decimal

from .contract import build_record
from .export import export_record, record_sha256
from .pipeline import process_session
from .simulate import annotate, standard_facade, walk, make_view
from .workflow import SESSION, single_frame_workflow


def multi_frame_demo(seed=10):
    f = standard_facade()
    views = walk(f, seed=seed)
    obs = []
    for v in views:
        for k, fr in enumerate(f.frames):
            o = annotate(fr, v, seed=3 + k + int(v.frame_id[1:]))
            if o:
                obs.append(o)
    s = dict(SESSION, session_id="SYN-WALK-001")
    res = process_session(s, views, obs)
    from .coverage import facade_coverage
    from .config import DEFAULT
    cov = facade_coverage(views, [0, 0, 1.0], 0.0, (0.0, 10.5, 0.0, 3.0), DEFAULT)
    return f, views, obs, s, res, build_record(s, views, obs, [], res, coverage=cov)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="uitvoermap BUITEN de repository (standaard: tijdelijke map)")
    ap.add_argument("--write-examples", default=None, help="schrijf de synthetische voorbeeldrecords naar deze map in de repository (alleen onderhoud)")
    a = ap.parse_args(argv)
    out = a.out or tempfile.mkdtemp(prefix="photo_walk_demo_")
    print("== SIMULATIE: synthetische data; bewijst geen nauwkeurigheid op een echte gevel ==\n")
    r = single_frame_workflow()
    for s in r["steps"]:
        print("  ", s)
    t = r["truth"]
    for label, res in (("voor correctie ", r["before"]), ("na correctie   ", r["after"])):
        o = res["objects"][0]
        if o["gross_area_m2"] is None:
            print(f"  {label}: UNKNOWN (geen waarde) - {[x['code'] for x in o['quality_flags'] if x['severity'] == 'BLOCKING']}")
            print(f"                     volgende stap: {o['next_steps_nl'][:1]}")
            continue
        err = Decimal(o["gross_area_m2"]) - Decimal(str(t["area_m2"]))
        print(f"  {label}: {o['outer_width_m']} x {o['outer_height_m']} m = {o['gross_area_m2_presented']} m2  [{o['dimension_status']}]  "
              f"sigma_area={o['measurement_uncertainty']['area_sigma_m2']}  afwijking t.o.v. simulatiewaarheid {float(err):+.4f} m2")
    print("   waarheid (gesimuleerd):", t["width_m"], "x", t["height_m"], "=", round(t["area_m2"], 4), "m2")
    print("   originele hoeken bewaard:", r["original_preserved"])
    p1, p2 = export_record(r["record"], out, "single_frame_measurement", allow_in_repo=bool(a.write_examples and out == a.write_examples))
    print("   export:", p1, p2)
    print("\n== Meerdere kozijnen (gesimuleerde geveldoorloop, 7 keyframes) ==")
    f, views, obs, s, res, rec = multi_frame_demo()
    truth = {fr.frame_id: fr for fr in f.frames}
    print(f"   waarnemingen: {len(obs)}  ->  unieke voorlopige kozijnen: {len(res['objects'])} (werkelijk {len(f.frames)})")
    for o, fr in zip(res["objects"], f.frames):
        print(f"   {o['provisional_object_id']}  {o['outer_width_m']} x {o['outer_height_m']} m = {o['gross_area_m2_presented']} m2 [{o['dimension_status']}] "
              f"obs={len(o['observation_refs'])}  (sim: {fr.width} x {fr.height})")
    print("   samenvatting:", json.dumps(res["summary"]["by_status"]))
    print("   dekking:", f"{rec['coverage']['coverage_fraction']:.2f}", rec["coverage"]["guidance_nl"])
    p1, p2 = export_record(rec, out, "walk_measurement", allow_in_repo=bool(a.write_examples and out == a.write_examples))
    print("   record sha256:", record_sha256(rec))
    print("   export:", p1, p2)
    if a.write_examples:
        export_record(r["record"], a.write_examples, "single_frame_measurement", allow_in_repo=True)
        export_record(rec, a.write_examples, "walk_measurement", allow_in_repo=True)
        print("   voorbeelden geschreven naar", a.write_examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
