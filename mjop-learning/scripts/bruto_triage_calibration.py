"""Quantity Review & Triage v1: kalibratieconfiguratie (alleen lezen, puur).

De standaard is UNCALIBRATED: alle drempels leeg, triage conservatief. Dit bestand voert GEEN kalibratie uit en verzint
geen prestaties. Het valideert wel de structuur van een latere, menselijke kalibratie: gelabelde set met hashes, gescheiden
ontwikkel-/kalibratie-/testdata, exact (Clopper-Pearson) betrouwbaarheidsinterval op het aantal onterecht schone objecten
(herberekend, niet overgenomen) en een door de gebruiker gesteld foutbudget. De echtheid van zo'n configuratie wordt hier
niet vastgesteld (authenticity blijft NOT_VERIFIED).
"""
import hashlib
import math

CONFIG_REL = "config/bruto_triage_calibration_v2.json"
PARAM_KEYS = ("min_independent_anchors", "dimension_deviation_tolerance_m", "estimate_min_references", "estimate_allowed_bases",
              "estimate_max_spread_m")


def binom_cdf(k, n, p):
    """P(X <= k) voor X ~ Binomial(n, p), exact via log-gamma-vrije som met herhaalde factor."""
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    total, term = 0.0, (1 - p) ** n
    for i in range(0, k + 1):
        total += term
        term *= (n - i) / (i + 1) * p / (1 - p)
    return min(total, 1.0)


def clopper_pearson_upper(k, n, confidence):
    """Eenzijdige exacte bovengrens van de foutfractie: kleinste p met P(X<=k | n, p) <= 1 - confidence."""
    if n <= 0 or k < 0 or k > n:
        raise ValueError("ongeldige telling")
    alpha = 1 - confidence
    if k == n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def min_audit_sample_size(error_budget, confidence=0.95):
    """Kleinste steekproef zonder enige fout die een fout-fractie boven het budget uitsluit (regel van drie, exact)."""
    if not 0 < error_budget < 1:
        raise ValueError("foutbudget moet tussen 0 en 1 liggen")
    return math.ceil(math.log(1 - confidence) / math.log(1 - error_budget))


def audit_sample(object_ids_with_hash, seed, size):
    """Deterministische auditsteekproef: SHA256-rangorde over seed|object_id|inhoudshash. Zelfde invoer, zelfde steekproef."""
    ranked = sorted(object_ids_with_hash, key=lambda t: (hashlib.sha256(f"{seed}|{t[0]}|{t[1]}".encode()).hexdigest(), t[0]))
    return sorted(oid for oid, _ in ranked[:max(0, size)])


def _uncalibrated(problems, declared):
    return {"declared_status": declared, "effective_status": "UNCALIBRATED", "conservative_fallback": True,
            "problems": sorted(problems), "parameters": {k: None for k in PARAM_KEYS}}


def effective(config, *, allow_synthetic=False):
    """Bepaalt de werkzame kalibratie. Elke tekortkoming geeft UNCALIBRATED met de redenen; nooit stilzwijgend gekalibreerd.

    allow_synthetic is uitsluitend voor testlogica; een SYNTHETIC-dataset geldt anders nooit als kalibratie."""
    declared = config.get("status")
    if declared != "CALIBRATED":
        return _uncalibrated([] if declared == "UNCALIBRATED" else ["STATUS_ONBEKEND"], declared)
    probs = []
    ds, sp, rs, eb, au, pa = (config.get(k) for k in ("dataset", "splits", "results", "error_budget", "audit_sample", "parameters"))
    if not ds:
        probs.append("DATASET_ONTBREEKT")
    else:
        if ds.get("labeling") == "SYNTHETIC" and not allow_synthetic:
            probs.append("DATASET_SYNTHETISCH")
        elif ds.get("labeling") not in ("HUMAN_LABELED", "SYNTHETIC"):
            probs.append("DATASET_NIET_MENSELIJK_GELABELD")
        if ds.get("representative") is not True:
            probs.append("DATASET_NIET_REPRESENTATIEF")
    if not sp:
        probs.append("SPLITS_ONTBREKEN")
    else:
        hashes = [sp[k]["split_sha256"] for k in ("development", "calibration", "test")]
        if len(set(hashes)) != 3:
            probs.append("SPLITS_NIET_GESCHEIDEN")
    if not eb or eb.get("set_by") != "USER":
        probs.append("FOUTBUDGET_NIET_DOOR_GEBRUIKER_GESTELD")
    if not rs:
        probs.append("RESULTATEN_ONTBREKEN")
    elif eb:
        upper = clopper_pearson_upper(rs["false_clean_k"], rs["clean_predictions_n"], rs["confidence_level"])
        if abs(upper - rs["declared_upper_bound"]) > 1e-6:
            probs.append("BETROUWBAARHEIDSINTERVAL_KLOPT_NIET")
        if upper > eb["max_false_clean_rate"]:
            probs.append("FOUTBUDGET_OVERSCHREDEN")
    if not au:
        probs.append("AUDITSTEEKPROEF_ONTBREEKT")
    elif eb and au["size"] < min_audit_sample_size(eb["max_false_clean_rate"]):
        probs.append("AUDITSTEEKPROEF_TE_KLEIN")
    if not pa or any(pa.get(k) is None for k in PARAM_KEYS):
        probs.append("DREMPELS_ONVOLLEDIG")
    if probs:
        return _uncalibrated(probs, declared)
    return {"declared_status": declared, "effective_status": "CALIBRATED", "conservative_fallback": False, "problems": [],
            "parameters": {k: pa[k] for k in PARAM_KEYS}, "audit_sample": {"seed": au["seed"], "size": au["size"]}}
