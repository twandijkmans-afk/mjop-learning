"""SYNTHETISCHE testhulpmiddelen en scenario's voor de Human Decision Intake (alleen tests en rapportgeneratie).

BELANGRIJK: de synthetische bron, het synthetische trust anchor en alle ID's hieronder bestaan uitsluitend in testcode. Ze simuleren een geauthenticeerd kanaal om
de BESLISLOGICA te testen (ook de negatieve paden); ze bewijzen niets over een echte provider. Geen echte personen, berichten, tokens of beslissingen. Niets wordt
geregistreerd: elk scenario retourneert alleen een DRY_RUN-rapport. Productiecode (scripts/) importeert deze module nooit.
"""
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import human_decision_intake as H  # noqa: E402
import human_instance_decision_register as R  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
SYNTH = "synthetic-intake-source"
REVIEWER_A, REVIEWER_B = "synthetic-reviewer-a", "synthetic-reviewer-b"
ADMIN = "synthetic-admin"
MSG = "synthetic-msg-0001"
TS = "2026-10-13T11:00:00Z"


class SyntheticIntakeSource(H.IntakeSourceProvider):
    """TEST-ONLY. Levert vooraf ingestelde attestaties; er is geen netwerk en geen echte identiteit."""
    provider_id = SYNTH

    def __init__(self, messages=None):
        self.messages = dict(messages or {})
        self.calls = []

    def fetch(self, source_message_id):
        self.calls.append(source_message_id)
        v = self.messages.get(source_message_id)
        if isinstance(v, Exception):
            raise v
        return v


class FixtureTrustAnchor(H.TrustAnchor):
    """TEST-ONLY. Pint vooraf opgegeven artefact-hashes; simuleert een gezag buiten de code. Zonder pin: niet geanker(d)."""

    def __init__(self, pinned=None, authorities=(ADMIN,)):
        self.pinned = dict(pinned or {})
        self.authorities = tuple(authorities)

    def verify_pinned(self, artifact_name, artifact_sha256):
        if self.pinned.get(artifact_name) == artifact_sha256:
            return H.AnchorResult(True, self.authorities, "FIXTURE_PIN")
        return H.AnchorResult(False, (), "FIXTURE_ANCHOR_HEEFT_DEZE_HASH_NIET_VASTGEPIND")


def live_request(ctx):
    P = R.P
    return P.evaluate_request(ctx, P.build_request(ctx, "OIC-VR-027"))


def decision_text(live, decision="NEEDS_MORE_EVIDENCE", extra=""):
    return (f"Synthetische testverklaring: voor {live['approval_request_id']} met request_hash {live['request_hash']} kies ik {decision}. "
            f"Dit is een testbericht zonder echte beslisser.{extra}")


def make_envelope(live, text=None, decision="NEEDS_MORE_EVIDENCE", claims=None, pointer=True, **over):
    text = text if text is not None else decision_text(live, decision)
    env = {"envelope_version": H.ENVELOPE_VERSION, "approval_request_id": live["approval_request_id"], "request_hash": live["request_hash"],
           "candidate_group_id": live["candidate_group_id"], "decision_text": text, "decision_text_sha256": H.text_sha256(text), "text_encoding": "UTF-8",
           "text_normalization": "NONE", "decision": decision, "covers_levels": ["A"], "acknowledged_open_app_ids": ["APP-012", "APP-025"],
           "acknowledged_open_relations": ["VR-045"],
           "evidence_reviewed": live["observation_ids"] + live["photo_ids"] + live["supporting_relation_ids"] + ["MAP-009"], "reviewer_notes": "synthetische testnotitie",
           "source_pointer": {"provider_id": SYNTH if pointer else None, "source_message_id": MSG if pointer else None},
           "claims": {"author_id": REVIEWER_A, "author_identity_source": "SYNTHETIC", "source_message_id": MSG if pointer else None, "source_timestamp": TS,
                      "channel": "FILE_EDITED_BY_HUMAN", "entered_by_kind": "HUMAN_DIRECT"}}
    if claims:
        env["claims"].update(claims)
    env.update(over)
    return env


def attestation(text, author=REVIEWER_A, ts=TS, actor="HUMAN", presence="WEBAUTHN_USER_VERIFIED", mid=MSG, provider=SYNTH, **over):
    a = H.SourceAttestation(provider_id=provider, authenticated_author_id=author, author_authentication_method="SYNTHETIC_PASSKEY", actor_type=actor,
                            human_presence_evidence=presence, source_message_id=mid, message_text=text, message_sha256=H.text_sha256(text), source_timestamp=ts,
                            retrieved_at="2026-10-13T12:00:00Z")
    for k, v in over.items():
        setattr(a, k, v)
    return a


def trusted_providers(presence=("WEBAUTHN_USER_VERIFIED",), synthetic=True, provider=SYNTH):
    return {"registry_version": H.TRUSTED_PROVIDERS_VERSION, "note": "synthetisch testregister",
            "providers": [{"provider_id": provider, "provider_kind": "SYNTHETIC_TEST", "accepted_human_presence_methods": list(presence), "synthetic": synthetic}]}


def authorization_doc(reviewer=REVIEWER_A, designated_by=ADMIN, request_id="IAR-OIC-VR-027", levels=("A",), valid_until="2026-12-31T00:00:00Z", provider=SYNTH):
    return {"registry_version": H.AUTHORIZATION_VERSION, "note": "synthetische testaanwijzing",
            "designations": [{"reviewer_id": f"{provider}:{reviewer}", "designated_by": designated_by, "designation_ref": "SYN-DESIG-0001", "scope_levels": list(levels),
                              "approval_request_ids": [request_id], "valid_from": "2026-10-01T00:00:00Z", "valid_until": valid_until}]}


def pinned_anchor(tp, az, extra=None):
    pins = {"human_decision_intake_trusted_providers_v1": H.canonical_sha256(tp), "human_decision_reviewer_authorization_v1": H.canonical_sha256(az)}
    pins.update(extra or {})
    return FixtureTrustAnchor(pins)


def kit(ctx, text, **over):
    """Alles wat een volledig geslaagde SYNTHETISCHE intake nodig heeft; scenario's wijzigen telkens een onderdeel."""
    tp, az = over.pop("tp", None) or trusted_providers(), over.pop("az", None) or authorization_doc()
    att = over.pop("att", None)
    prov = SyntheticIntakeSource({MSG: att if att is not None else attestation(text)})
    anchor = over.pop("anchor", None) or pinned_anchor(tp, az)
    return dict(ctx=ctx, provider=prov, trusted_providers=tp, authorization=az, anchor=anchor, now=NOW, **over)


def v1_record(seq, prev, live, decision="NEEDS_MORE_EVIDENCE"):
    """Handmatig opgebouwd v1-record in een TIJDELIJK bestand (zonder de registeractie aan te roepen)."""
    rec = {"approval_request_id": live["approval_request_id"], "request_hash": live["request_hash"], "candidate_group_id": live["candidate_group_id"], "decision": decision,
           "covers_levels": ["A"], "decision_source": "HUMAN_CHAT_CONFIRMATION", "decided_by": "Synthetische Testpersoon", "decision_timestamp": TS,
           "decision_provenance": {"channel": "FILE_EDITED_BY_HUMAN", "entered_by_kind": "HUMAN_DIRECT", "source_message_ref": "synthetisch", "source_message_text": decision_text(live, decision),
                                   "identity_verification": R.IDENTITY_VERIFICATION, "ai_authored_decision": False},
           "acknowledged_open_app_ids": ["APP-012", "APP-025"], "acknowledged_open_relations": ["VR-045"], "evidence_reviewed": ["x"], "reviewer_notes": "", "record_version": 1,
           "decision_id": R.decision_id_for(seq), "sequence": seq, "previous_record_hash": prev, "register_version": R.REGISTER_VERSION}
    rec["record_hash"] = R.record_hash(rec)
    return rec


def write_v1(path, records):
    Path(path).write_bytes(b"".join((R.canonical(r) + "\n").encode("utf-8") for r in records))


def v2_record(seq, prev, v1_head, live, text, key=f"{SYNTH}:{MSG}"):
    rec = {"approval_request_id": live["approval_request_id"], "request_hash": live["request_hash"], "candidate_group_id": live["candidate_group_id"], "decision": "NEEDS_MORE_EVIDENCE",
           "covers_levels": ["A"], "acknowledged_open_app_ids": ["APP-012", "APP-025"], "acknowledged_open_relations": ["VR-045"], "evidence_reviewed": ["x"], "reviewer_notes": "",
           "record_version": 2, "intake_id": "INT-0123456789abcdef", "decision_text": text, "decision_text_sha256": H.text_sha256(text), "text_encoding": "UTF-8", "text_normalization": "NONE",
           "provenance": {"provenance_verification_status": "SOURCE_VERIFIED", "authentication_status": "AUTHENTICATED_HUMAN_PRESENCE", "provider_id": "provider-x", "trust_registry_sha256": "a" * 64,
                          "attestation_sha256": "b" * 64, "authenticated_author_id": "subject-x", "author_authentication_method": "METHOD", "human_presence_evidence": "WEBAUTHN_USER_VERIFIED",
                          "source_message_id": "m1", "source_timestamp": TS, "received_timestamp": TS, "synthetic_source": False},
           "authorization": {"status": "AUTHORIZED", "registry_sha256": "c" * 64, "anchor_authority_ids": ["admin-x"], "designation_ref": "D-1", "reviewer_id": "provider-x:subject-x"},
           "source_message_key": key, "v1_register_head": v1_head, "decision_id": R.decision_id_for(seq), "sequence": seq, "previous_record_hash": prev,
           "register_version": H.V2_REGISTER_VERSION}
    rec["record_hash"] = R.record_hash(rec)
    return rec


# --- de 18 scenario's -----------------------------------------------------------------------------------------------------------------------------
def run_scenarios(ctx, tmpdir):
    """Retourneert een lijst {nr, titel, verwacht, resultaat (rapport), opmerking}. Alles DRY_RUN; synthetische fixtures."""
    live = live_request(ctx)
    out = []
    tmp = Path(tmpdir)

    def add(nr, title, expected, rep, note=""):
        out.append({"nr": nr, "title": title, "expected": expected, "report": rep, "note": note})

    text = decision_text(live)
    good_env = make_envelope(live, text)

    # 0 (referentie, niet genummerd): volledig geslaagde synthetische DRY_RUN
    ref = H.validate_intake(good_env, **kit(ctx, text))
    out.append({"nr": 0, "title": "Referentie: volledig geslaagde SYNTHETISCHE intake (alle onderdelen slagen)", "expected": "VALIDATED_DRY_RUN", "report": ref,
                "note": "synthetische bron; registratiegeschiktheid blijft NOT_ELIGIBLE_SYNTHETIC_SOURCE; er is niets geregistreerd"})

    # 1 correct besluit, zelf opgegeven auteur (geen bron)
    add(1, "Correct besluit, maar zelf opgegeven auteur", "UNVERIFIED_SOURCE", H.validate_intake(good_env, ctx=ctx, now=NOW))
    # 2 correct besluit, geen geauthenticeerde bron (en geen opgegeven auteur)
    env2 = make_envelope(live, text, pointer=False, claims={"author_id": None, "author_identity_source": None, "source_timestamp": None, "source_message_id": None})
    add(2, "Correct besluit, maar ontbrekende geauthenticeerde bron", "UNVERIFIED_SOURCE", H.validate_intake(env2, ctx=ctx, now=NOW))
    # 3 correct besluit, niet-geautoriseerde (wel geauthenticeerde) auteur
    env3 = make_envelope(live, text, claims={"author_id": REVIEWER_B})
    add(3, "Correct besluit van niet-geautoriseerde auteur", "UNAUTHORIZED_REVIEWER",
        H.validate_intake(env3, **kit(ctx, text, att=attestation(text, author=REVIEWER_B))))
    # 4 geverifieerde auteur, ongeldige besluittekst (noemt request_hash niet)
    bad_text = f"Synthetisch: voor {live['approval_request_id']} kies ik NEEDS_MORE_EVIDENCE, zonder de hash te noemen, in een voldoende lange testverklaring."
    add(4, "Geverifieerde auteur met ongeldige besluittekst", "INVALID_DECISION", H.validate_intake(make_envelope(live, bad_text), **kit(ctx, bad_text)))
    # 5 verouderde request_hash
    old = R.P.SUPERSEDED_HASHES[0]
    t5 = text.replace(live["request_hash"], old)
    env5 = make_envelope(live, t5, request_hash=old)
    add(5, "Verouderde request_hash", "STALE_REQUEST", H.validate_intake(env5, **kit(ctx, t5)))
    # 6-8 ontbrekende erkenning APP-012, APP-025, VR-045
    for nr, name, over in ((6, "APP-012", {"acknowledged_open_app_ids": ["APP-025"]}), (7, "APP-025", {"acknowledged_open_app_ids": ["APP-012"]}),
                           (8, "VR-045", {"acknowledged_open_relations": []})):
        add(nr, f"Ontbrekende erkenning {name}", "INVALID_DECISION", H.validate_intake(make_envelope(live, text, **over), **kit(ctx, text)))
    # 9 onterecht niveau B of C
    r9a = H.validate_intake(make_envelope(live, text, covers_levels=["A", "B"]), **kit(ctx, text))
    t9 = decision_text(live, extra=" Ik bevestig ook niveau C.")
    r9b = H.validate_intake(make_envelope(live, t9), **kit(ctx, t9))
    add(9, "Besluit dat onterecht niveau B of C dekt (veld covers_levels)", "INVALID_DECISION", r9a)
    add(9, "Besluit dat onterecht niveau B of C dekt (tekst)", "INVALID_DECISION", r9b)
    # 10 AI-gegenereerd bericht dat menselijke toestemming claimt
    t10 = decision_text(live, extra="\n\n🤖 Generated with [Claude Code](https://claude.ai/code)")
    r10a = H.validate_intake(make_envelope(live, t10), **kit(ctx, t10))
    r10b = H.validate_intake(make_envelope(live, text), **kit(ctx, text, att=attestation(text, actor="BOT", presence="NONE")))
    add(10, "AI-gegenereerd bericht dat menselijke toestemming claimt (AI-kenmerk in tekst)", "BLOCKED", r10a)
    add(10, "AI-gegenereerd bericht dat menselijke toestemming claimt (bron meldt automatisering)", "BLOCKED", r10b)
    # 11 gemodificeerde berichttekst met oude hash
    env11 = make_envelope(live, text)
    env11["decision_text"] = text.replace("kies ik", "kies ik niet")
    add(11, "Gemodificeerde berichttekst met oude hash", "BLOCKED", H.validate_intake(env11, **kit(ctx, text)))
    # 12 ongeldige of gemanipuleerde tijdstempels
    ts_cases = (("niet-parsebaar", "gisteren rond lunchtijd", "INVALID_DECISION"), ("zonder tijdzone", "2026-10-13T11:00:00", "INVALID_DECISION"),
                ("in de toekomst", "2026-10-14T11:00:00Z", "BLOCKED"), ("afwijkend van de bron", "2026-10-13T10:00:00Z", "BLOCKED"),
                ("onwaarschijnlijk oud", "2020-01-01T00:00:00Z", "BLOCKED"))
    for label, ts, exp in ts_cases:
        att = attestation(text, ts=ts if label in ("in de toekomst", "onwaarschijnlijk oud") else TS)
        add(12, f"Gemanipuleerde tijdstempel: {label}", exp, H.validate_intake(make_envelope(live, text, claims={"source_timestamp": ts}), **kit(ctx, text, att=att)))
    # 13 dubbele source_message_id (verschillende inhoud, zelfde bronbericht) - batch
    e13a = make_envelope(live, text)
    e13b = make_envelope(live, text, reviewer_notes="andere synthetische notitie")
    r13 = H.validate_batch([e13a, e13b], **kit(ctx, text))
    add(13, "Dubbele source_message_id (tweede envelope, andere inhoud)", "BLOCKED", r13[1], "eerste envelope: " + r13[0]["final_status"])
    # 14 replay van hetzelfde intake-event
    r14 = H.validate_batch([e13a, copy.deepcopy(e13a)], **kit(ctx, text))
    add(14, "Replay van hetzelfde intake-event (zelfde ledger/proces)", "BLOCKED", r14[1], "eerste: " + r14[0]["final_status"] + "; een nieuw proces/ledger ziet dit NIET (zie replay_protection)")
    # 15 verschillende beslissingen met hetzelfde event-ID
    t15 = decision_text(live, "REJECT")
    e15b = make_envelope(live, t15, decision="REJECT")
    k15 = kit(ctx, text)
    k15["provider"].messages[MSG] = attestation(text)
    r15a = H.validate_intake(e13a, ledger=(led := H.InMemoryReplayLedger()), **k15)
    k15["provider"].messages[MSG] = attestation(t15)
    r15b = H.validate_intake(e15b, ledger=led, **k15)
    add(15, "Verschillende beslissingen met hetzelfde event-ID", "BLOCKED", r15b, "eerste: " + r15a["final_status"])
    # 16 ontbrekende of corrupte bronmetadata
    bad_att = attestation(text, author="")
    add(16, "Corrupte bronmetadata (lege geauthenticeerde auteur)", "BLOCKED", H.validate_intake(good_env, **kit(ctx, text, att=bad_att)))
    add(16, "Corrupte bronmetadata (geen attestatie-object)", "BLOCKED", H.validate_intake(good_env, **kit(ctx, text, att={"author": REVIEWER_A})))
    add(16, "Ontbrekende bronmetadata (bron kent het bericht niet)", "UNVERIFIED_SOURCE",
        H.validate_intake(good_env, **{**kit(ctx, text), "provider": SyntheticIntakeSource({})}))
    # 17 v1-record dat ten onrechte SOURCE_VERIFIED probeert te worden
    v1 = v1_record(1, R.GENESIS, live)
    reg_ok, reg_forged = tmp / "v1_ok.jsonl", tmp / "v1_forged.jsonl"
    write_v1(reg_ok, [v1])
    forged = dict(v1)
    forged["provenance_verification_status"] = "SOURCE_VERIFIED"
    forged["record_hash"] = R.record_hash(forged)
    write_v1(reg_forged, [forged])
    legacy = H.unified_register_view(reg_ok)
    try:
        R.load_register(reg_forged)
        forged_result = "NIET_GEWEIGERD"
    except R.RegisterCorrupt as exc:
        forged_result = f"GEWEIGERD {exc}"
    out.append({"nr": 17, "title": "v1-record dat ten onrechte SOURCE_VERIFIED probeert te worden", "expected": "SELF_ASSERTED (legacy) en forged record geweigerd",
                "report": {"final_status": "N.V.T. (registercontrole)", "legacy_view": legacy["entries"][0], "forged_v1_record": forged_result,
                           "open_problems": [], "effects": {"register_written": False}}, "note": "tijdelijke bestanden; echt register onaangeroerd"})
    # 18 vervalste reviewer-allowlist
    az_forged = authorization_doc(reviewer=REVIEWER_A, designated_by=REVIEWER_A)         # zelf aangewezen
    tp = trusted_providers()
    r18a = H.validate_intake(good_env, **{**kit(ctx, text), "authorization": az_forged, "anchor": pinned_anchor(tp, authorization_doc())})
    r18b = H.validate_intake(good_env, **{**kit(ctx, text), "anchor": FixtureTrustAnchor({"human_decision_intake_trusted_providers_v1": H.canonical_sha256(tp)})})
    r18c = H.validate_intake(make_envelope(live, text, authorized_reviewer_id=REVIEWER_A), **kit(ctx, text))
    r18d = H.validate_intake(good_env, **{**kit(ctx, text), "authorization": az_forged, "anchor": pinned_anchor(tp, az_forged)})
    add(18, "Vervalste reviewer-allowlist (aangeleverde lijst niet vastgepind: het gezag pint een andere lijst)", "UNAUTHORIZED_REVIEWER", r18a)
    add(18, "Vervalste reviewer-allowlist (er is geen enkele aanwijzing vastgepind)", "UNAUTHORIZED_REVIEWER", r18b)
    add(18, "Vervalste reviewer-allowlist (zelfaanwijzing, zelfs als de lijst is vastgepind)", "UNAUTHORIZED_REVIEWER", r18d)
    add(18, "Reviewer-id/allowlist in het aangeleverde besluit zelf", "BLOCKED", r18c)
    return out
