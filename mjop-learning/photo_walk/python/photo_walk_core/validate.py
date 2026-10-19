"""Valideer een exportbestand tegen photo_walk_capture_v1 (bijv. de export van de iPhone-app):
python -m photo_walk_core.validate <bestand.json>"""
import json
import sys

from .contract import schema_errors


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    rec = json.load(open(argv[0], encoding="utf-8"))
    errs = schema_errors(rec)
    if errs:
        print(f"ONGELDIG ({len(errs)} fouten):")
        for e in errs[:30]:
            print(" -", e)
        return 1
    print("GELDIG: photo_walk_capture_v1;", len(rec["objects"]), "kozijnen; origin:", rec["data_origin"], "; validation_level:", rec["validation_level"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
