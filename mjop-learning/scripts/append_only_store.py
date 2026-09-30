"""Gedeelde invarianten voor append-only menselijke beslissingsopslag.

Zelfde regels als de bestaande human decision records (scripts/export_human_review_queue.py,
scripts/human_match_review.py): records worden nooit verwijderd of overschreven; alleen de status mag
ACTIVE -> SUPERSEDED, ACTIVE -> REVIEW_REQUIRED of REVIEW_REQUIRED -> SUPERSEDED; per sleutel hoogstens één
ACTIVE record; 'supersedes' verwijst naar een bestaand SUPERSEDED record met dezelfde sleutel, en elk
SUPERSEDED record is door precies één later record vervangen.
"""

ALLOWED_STATUS_TRANSITIONS = {("ACTIVE", "SUPERSEDED"), ("ACTIVE", "REVIEW_REQUIRED"), ("REVIEW_REQUIRED", "SUPERSEDED")}


def invariant_errors(records, id_field, key_fn, status_field="status"):
    errors, by_id = [], {}
    for r in records:
        if r[id_field] in by_id:
            errors.append(f"{r[id_field]}: {id_field} komt meer dan eens voor")
        by_id[r[id_field]] = r
    active, superseded_by = {}, {}
    for r in records:
        key = key_fn(r)
        if r[status_field] == "ACTIVE":
            active.setdefault(key, []).append(r[id_field])
        if r.get("supersedes"):
            old = by_id.get(r["supersedes"])
            if old is None:
                errors.append(f"{r[id_field]}: supersedes verwijst naar onbekende {r['supersedes']}")
            elif key_fn(old) != key or old[status_field] != "SUPERSEDED":
                errors.append(f"{r[id_field]}: vervangen record {old[id_field]} moet dezelfde sleutel hebben en SUPERSEDED zijn")
            superseded_by.setdefault(r["supersedes"], []).append(r[id_field])
    for r in records:
        if r[status_field] == "SUPERSEDED" and len(superseded_by.get(r[id_field], [])) != 1:
            errors.append(f"{r[id_field]}: SUPERSEDED record moet door precies één later record vervangen zijn")
    errors += [f"{k}: meer dan één ACTIVE record ({', '.join(ids)})" for k, ids in sorted(active.items(), key=str) if len(ids) > 1]
    return errors


def append_only_errors(old_records, new_records, id_field, status_field="status"):
    new = {r[id_field]: r for r in new_records}
    errors = []
    for r in old_records:
        n = new.get(r[id_field])
        if n is None:
            errors.append(f"{r[id_field]}: record verwijderd")
            continue
        if {k: v for k, v in n.items() if k != status_field} != {k: v for k, v in r.items() if k != status_field}:
            errors.append(f"{r[id_field]}: record overschreven")
        if n[status_field] != r[status_field] and (r[status_field], n[status_field]) not in ALLOWED_STATUS_TRANSITIONS:
            errors.append(f"{r[id_field]}: statuswijziging {r[status_field]} -> {n[status_field]} niet toegestaan")
    return errors


def next_id(records, id_field, prefix):
    n = max([int(r[id_field].rsplit("-", 1)[1]) for r in records] + [0])
    return f"{prefix}-{n + 1:05d}"
