"""External Vision Safety Gate v1: adversariële tests (bytes, metadata, budget over processen heen, consent, omzeiling van de poort).
Er wordt nergens een echte externe aanroep gedaan: clients zijn mocks die tellen hoe vaak ze worden aangeroepen."""
import ast
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import zlib

import pytest

from agent.photo import providers as P
from agent.photo import safety_gate as G
from agent.photo.contract import PROJECT_ROOT, sha256_bytes
from conftest import AUTH_KEY

import photo_support as S
from test_providers import FakeClient, GOOD_TEXT, cfg, consent, signed

import vision_budget_ledger as L


# --- afbeeldingen bouwen -------------------------------------------------------------------------------------------------
def img(fmt, size=(64, 48), **save):
    from PIL import Image
    im = Image.new("RGB", size, (200, 120, 90))
    for x in range(0, size[0], 7):
        im.putpixel((x, x % size[1]), (10, 20, 30))
    buf = io.BytesIO()
    im.save(buf, fmt, **save)
    return buf.getvalue()


def exif_bytes():
    from PIL import Image
    ex = Image.Exif()
    ex[0x010F] = "SecretMaker"
    ex[0x8825] = {1: "N", 2: (52.0, 31.0, 1.0), 3: "E", 4: (6.0, 5.0, 1.0)}      # GPS
    return ex.tobytes()


def png_chunks(data):
    pos, out = 8, []
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        out.append((data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]))
        pos += 12 + n
    return out


def png_build(chunks):
    out = b"\x89PNG\r\n\x1a\n"
    for t, d in chunks:
        out += struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return out


def insert_png_chunk(data, ctype, body):
    ch = png_chunks(data)
    return png_build(ch[:-1] + [(ctype, body)] + ch[-1:])


def facts(data, media, w=64, h=48, edge=1000, size=200_000):
    return G.inspect_image(data, declared_media_type=media, declared_width=w, declared_height=h, max_long_edge_px=edge, max_file_bytes=size)


def refusal(data, media, **kw):
    with pytest.raises(G.GateRefusal) as ei:
        facts(data, media, **kw)
    return ei.value.reasons


# --- 3. werkelijke afbeeldingsbytes ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("fmt,media", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("GIF", "image/gif"), ("WEBP", "image/webp")])
def test_clean_images_of_every_supported_format_pass(fmt, media):
    data = img(fmt)
    f = facts(data, media)
    assert (f.media_type, f.width_px, f.height_px, f.file_bytes, f.sha256) == (media, 64, 48, len(data), sha256_bytes(data))


def test_committed_synthetic_fixture_passes():
    assert facts(S.png(), "image/png", 640, 480).sha256 == sha256_bytes(S.png())


@pytest.mark.parametrize("data,media", [
    (insert_png_chunk(img("PNG"), b"tEXt", b"GPS\x0052.5,6.1"), "image/png"),
    (insert_png_chunk(img("PNG"), b"eXIf", exif_bytes()), "image/png"),
    (insert_png_chunk(img("PNG"), b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00<x:xmpmeta/>"), "image/png"),
    (insert_png_chunk(img("PNG"), b"zzZz", b"onbekend"), "image/png"),
    (img("JPEG", exif=exif_bytes()), "image/jpeg"),
    (img("WEBP", exif=exif_bytes()), "image/webp"),
    (img("WEBP", xmp=b"<x:xmpmeta/>"), "image/webp"),
])
def test_embedded_metadata_is_refused(data, media):
    assert "IMAGE_METADATA_PRESENT" in refusal(data, media)


def test_jpeg_comment_and_icc_and_xmp_are_refused():
    base = img("JPEG")
    for marker, body in ((0xFE, b"verborgen commentaar"), (0xE2, b"ICC_PROFILE\x00\x01\x01xx"), (0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x/>")):
        seg = b"\xff" + bytes([marker]) + struct.pack(">H", len(body) + 2) + body
        assert "IMAGE_METADATA_PRESENT" in refusal(base[:2] + seg + base[2:], "image/jpeg")


def test_gif_comment_extension_and_animation_are_refused():
    base = img("GIF")
    comment = b"\x21\xfe\x05hello\x00"
    i = base.index(b"\x2c")
    assert "IMAGE_METADATA_PRESENT" in refusal(base[:i] + comment + base[i:], "image/gif")
    from PIL import Image
    frames = [Image.new("RGB", (64, 48), c) for c in ((255, 0, 0), (0, 255, 0))]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:])
    assert {"IMAGE_ANIMATED_OR_MULTIFRAME"} & set(refusal(buf.getvalue(), "image/gif"))


@pytest.mark.parametrize("fmt,media", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("GIF", "image/gif"), ("WEBP", "image/webp")])
def test_trailing_or_polyglot_payload_is_refused(fmt, media):
    data = img(fmt)
    assert set(refusal(data + b"<script>payload</script>", media)) & {"IMAGE_TRAILING_DATA", "IMAGE_CONTAINER_INVALID"}
    assert set(refusal(data + img("JPEG"), media)) & {"IMAGE_TRAILING_DATA", "IMAGE_CONTAINER_INVALID"}


def test_png_with_bad_crc_truncation_and_garbage_pixels_is_refused():
    data = bytearray(img("PNG"))
    data[40] ^= 0xFF
    assert "IMAGE_CONTAINER_INVALID" in refusal(bytes(data), "image/png")
    assert "IMAGE_CONTAINER_INVALID" in refusal(img("PNG")[:-20], "image/png")
    ch = png_chunks(img("PNG"))
    garbage = png_build([(t, b"\x00\x01garbage-not-zlib" if t == b"IDAT" else d) for t, d in ch])      # geldige CRC, ongeldige pixeldata
    assert "IMAGE_DECODE_FAILED" in refusal(garbage, "image/png")


def test_declared_media_type_must_match_real_bytes():
    assert refusal(img("JPEG"), "image/png") == ["IMAGE_MEDIA_TYPE_MISMATCH"]
    assert refusal(b"MZ\x90\x00 this is an exe", "image/png") == ["IMAGE_FORMAT_UNSUPPORTED"]
    assert refusal(b"<html><script>x</script></html>", "image/png") == ["IMAGE_FORMAT_UNSUPPORTED"]


def test_declared_dimensions_must_match_real_pixels():
    assert "IMAGE_DIMENSION_MISMATCH" in refusal(img("PNG", (64, 48)), "image/png", w=640, h=480)
    assert "IMAGE_DIMENSION_MISMATCH" in refusal(img("PNG", (64, 48)), "image/png", w=48, h=64)


def test_real_pixels_not_the_claim_decide_the_long_edge():
    big = img("PNG", (400, 300))
    assert "IMAGE_TOO_LARGE_PIXELS" in refusal(big, "image/png", w=400, h=300, edge=300)         # waarheid is te groot
    assert "IMAGE_DIMENSION_MISMATCH" in refusal(big, "image/png", w=100, h=75, edge=300)         # leugen over kleinere maat


def test_file_size_limit_is_enforced_on_real_bytes():
    data = img("PNG", (300, 300))
    assert "IMAGE_TOO_LARGE_BYTES" in refusal(data, "image/png", w=300, h=300, size=len(data) - 1)
    assert facts(data, "image/png", 300, 300, size=len(data)).file_bytes == len(data)


def test_absolute_byte_ceiling_overrides_any_consent_value(monkeypatch):
    monkeypatch.setattr(G, "ABSOLUTE_MAX_FILE_BYTES", 1000)
    assert "IMAGE_TOO_LARGE_BYTES" in refusal(img("PNG", (300, 300)), "image/png", w=300, h=300, size=10 ** 9)


def test_decompression_bomb_is_refused_before_decoding(monkeypatch):
    from PIL import Image
    im = Image.new("1", (6000, 6000))                                                 # 36 Mpx, comprimeert tot enkele KB
    buf = io.BytesIO(); im.save(buf, "PNG")
    assert len(buf.getvalue()) < 100_000
    decoded = []
    real = Image.Image.load
    monkeypatch.setattr(Image.Image, "load", lambda self, *a, **k: decoded.append(1) or real(self, *a, **k))
    assert "IMAGE_TOO_MANY_PIXELS" in refusal(buf.getvalue(), "image/png", w=6000, h=6000, edge=10_000, size=1_000_000)
    assert decoded == []


@pytest.mark.parametrize("bad", [b"", None, "tekst", 12345])
def test_missing_or_non_bytes_image_is_refused(bad):
    assert refusal(bad, "image/png") == ["IMAGE_MISSING"]


# --- 2. consent: authenticiteit en inhoud -----------------------------------------------------------------------------------
def req():
    return S.request()


def authorize(ledger, record=None, config=None, request=None, env=None, **kw):
    return G.authorize_external_call(provider="anthropic", request=request or req(), config=config or cfg(), consent=record if record is not None else signed(),
                                     ledger=ledger, prompt_sha256=P.PROMPT_SHA256, environ=env, now=kw.get("now"))


def refused(ledger, **kw):
    with pytest.raises(G.GateRefusal) as ei:
        authorize(ledger, **kw)
    assert ledger.usage("PCON-00001") == {"calls": 0, "tokens": 0}, "een geweigerde controle mag niets verbruiken"
    return ei.value.reasons


def test_full_valid_authorization_reserves_exactly_one_call(approved_gate):
    auth = authorize(approved_gate)
    assert isinstance(auth, G.GateAuthorization) and auth.derivative_sha256 == req().derivative_sha256
    assert approved_gate.usage("PCON-00001") == {"calls": 1, "tokens": 2000}


def test_unapproved_provider_is_refused_even_when_everything_else_is_valid(approved_gate, monkeypatch):
    monkeypatch.setitem(G.PROVIDER_APPROVALS, "anthropic", {"status": "NOT_APPROVED", "reason": "x"})
    assert refused(approved_gate) == ["PROVIDER_NOT_APPROVED"]
    monkeypatch.setitem(G.PROVIDER_APPROVALS, "anthropic", {"status": "approved"})              # alleen exact APPROVED telt
    assert refused(approved_gate) == ["PROVIDER_NOT_APPROVED"]
    with pytest.raises(G.GateRefusal):
        G.authorize_external_call(provider="onbekend", request=req(), config=cfg(), consent=signed(), ledger=approved_gate, prompt_sha256="x")


def test_unsigned_forged_or_modified_consent_is_refused(approved_gate):
    unsigned = consent()
    assert refused(approved_gate, record=unsigned) == ["CONSENT_INVALID"]                         # schema vereist authorization
    forged = signed(); forged["authorization"]["mac"] = "0" * 64
    assert refused(approved_gate, record=forged) == ["CONSENT_NOT_AUTHENTIC"]
    raised = signed(); raised["budget"]["max_calls"] = 999                                        # budget verhogen breekt de handtekening
    assert refused(approved_gate, record=raised) == ["CONSENT_NOT_AUTHENTIC"]
    other_photo = signed(); other_photo["photos"][0]["privacy_check"] = "ALLOW_WITH_REDACTION"
    assert refused(approved_gate, record=other_photo) == ["CONSENT_NOT_AUTHENTIC"]
    wrong_key = G.sign_consent(consent(), "een-andere-sleutel-van-minstens-32-tekens!!")
    assert refused(approved_gate, record=wrong_key) == ["CONSENT_NOT_AUTHENTIC"]


def test_missing_or_short_auth_key_is_refused(approved_gate, monkeypatch):
    monkeypatch.delenv(G.ENV_AUTH_KEY)
    assert refused(approved_gate) == ["CONSENT_NOT_AUTHENTIC"]
    monkeypatch.setenv(G.ENV_AUTH_KEY, "kort")
    assert refused(approved_gate) == ["CONSENT_NOT_AUTHENTIC"]
    with pytest.raises(ValueError):
        G.sign_consent(consent(), "kort")


def test_second_key_expiry_and_model_and_token_limits_are_enforced(approved_gate, monkeypatch):
    monkeypatch.setenv("MJOP_PHOTO_EXTERNAL_CONSENT_ID", "PCON-99999")
    assert refused(approved_gate) == ["CONSENT_REFUSED"]
    monkeypatch.setenv("MJOP_PHOTO_EXTERNAL_CONSENT_ID", "PCON-00001")
    assert refused(approved_gate, record=signed(valid_until="2020-01-01T00:00:00Z")) == ["CONSENT_REFUSED"]
    assert refused(approved_gate, config=cfg(model="niet-toegestaan-model")) == ["CONSENT_REFUSED"]
    assert refused(approved_gate, config=cfg(max_tokens=10 ** 6)) == ["CONSENT_REFUSED"]
    deny = signed(); deny["photos"][0]["privacy_check"] = "DENY"
    assert refused(approved_gate, record=G.sign_consent(deny, AUTH_KEY)) == ["CONSENT_REFUSED"]
    other = signed(approved_by={"reviewer_type": "model", "reviewer_id": "x"})
    assert refused(approved_gate, record=other) == ["CONSENT_INVALID"]


def test_consent_for_other_bytes_or_other_policy_than_the_real_image_is_refused(approved_gate):
    other = S.request(img("PNG", (640, 480)))                                                    # echte afbeelding, maar andere hash dan in het record
    assert refused(approved_gate, request=other) == ["CONSENT_REFUSED"]
    jpeg = img("JPEG", (640, 480))
    r = S.request(jpeg); r.media_type = "image/jpeg"
    assert refused(approved_gate, request=r) == ["IMAGE_MEDIA_TYPE_MISMATCH"]


def test_request_that_lies_about_hash_size_or_type_is_refused(approved_gate):
    r = req(); r.derivative_sha256 = "0" * 64
    assert refused(approved_gate, request=r) == ["IMAGE_HASH_MISMATCH"]
    r = req(); r.width_px, r.height_px = 100, 100
    assert "IMAGE_DIMENSION_MISMATCH" in refused(approved_gate, request=r)
    r = req(); r.image_bytes = None
    assert refused(approved_gate, request=r) == ["IMAGE_MISSING"]
    r = req(); r.media_type = "image/jpeg"
    assert refused(approved_gate, request=r) == ["IMAGE_MEDIA_TYPE_MISMATCH"]


def test_image_with_metadata_is_refused_even_with_a_consent_that_names_its_hash(approved_gate):
    dirty = insert_png_chunk(S.png(), b"tEXt", b"GPS\x0052.5,6.1")
    r = S.request(dirty)
    rec = signed()
    rec["photos"][0]["derivative_sha256"] = sha256_bytes(dirty)
    assert refused(approved_gate, record=G.sign_consent(rec, AUTH_KEY), request=r) == ["IMAGE_METADATA_PRESENT"]


# --- 4. budget en grootboek ------------------------------------------------------------------------------------------------
def test_call_budget_is_a_total_and_new_ledger_objects_see_earlier_use(approved_gate):
    rec = signed(budget={"max_calls": 2, "max_output_tokens": 100_000})
    a1, a2 = authorize(approved_gate, record=rec), authorize(approved_gate, record=rec)
    with pytest.raises(G.GateRefusal) as ei:
        authorize(approved_gate, record=rec)
    assert ei.value.reasons == ["BUDGET_CALLS_EXHAUSTED"]
    fresh = L.FileBudgetLedger(approved_gate.dir)                                                # "nieuw proces": zelfde map
    with pytest.raises(G.GateRefusal) as ei:
        authorize(fresh, record=rec)
    assert ei.value.reasons == ["BUDGET_CALLS_EXHAUSTED"]
    a1.consume(); a1.settle("OK", 10)
    a2.release_unsent("test")
    assert fresh.usage("PCON-00001")["calls"] == 1
    authorize(fresh, record=rec)                                                                  # vrijgegeven ruimte komt terug, verzonden call niet


def test_token_budget_is_enforced(approved_gate):
    rec = signed(budget={"max_calls": 10, "max_output_tokens": 3000})
    authorize(approved_gate, record=rec)
    with pytest.raises(G.GateRefusal) as ei:
        authorize(approved_gate, record=rec)                                                      # 2000 + 2000 > 3000
    assert ei.value.reasons == ["BUDGET_TOKENS_EXHAUSTED"]


def test_resigned_consent_with_same_id_cannot_reset_the_budget(approved_gate):
    rec = signed(budget={"max_calls": 1, "max_output_tokens": 100_000})
    authorize(approved_gate, record=rec)
    bigger = signed(budget={"max_calls": 50, "max_output_tokens": 100_000})                       # geldig ondertekend, maar andere inhoud
    with pytest.raises(G.GateRefusal) as ei:
        authorize(approved_gate, record=bigger)
    assert ei.value.reasons == ["LEDGER_CONSENT_CHANGED"]


RACE = """
import sys, time
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from agent.photo import safety_gate as G
import vision_budget_ledger as L
led = L.FileBudgetLedger(sys.argv[3])
while time.time() < float(sys.argv[4]):                      # alle processen starten op hetzelfde moment
    pass
try:
    led.reserve(consent_id="PCON-00001", consent_sha256="a" * 64, derivative_sha256="b" * 64, max_calls=3, max_tokens_total=10**6, tokens_per_call=10, now=None)
    print("OK")
except G.GateRefusal as e:
    print(e.reasons[0])
"""


def test_budget_holds_across_concurrent_processes(tmp_path):
    d = tmp_path / "race"
    d.mkdir(mode=0o700)
    import time
    start = str(time.time() + 3)
    procs = [subprocess.Popen([sys.executable, "-c", RACE, PROJECT_ROOT, os.path.join(PROJECT_ROOT, "scripts"), str(d), start], stdout=subprocess.PIPE,
                              text=True) for _ in range(16)]
    outs = [p.communicate()[0].strip() for p in procs]
    assert outs.count("OK") == 3 and outs.count("BUDGET_CALLS_EXHAUSTED") == 13, outs
    assert L.FileBudgetLedger(str(d)).usage("PCON-00001")["calls"] == 3


def ledger_lines(led):
    return open(led.path, "rb").read().splitlines(keepends=True)


def test_tampered_ledger_fails_closed(approved_gate):
    authorize(approved_gate)
    lines = ledger_lines(approved_gate)
    d = json.loads(lines[0]); d["tokens"] = 1                                                      # tokens verlagen
    open(approved_gate.path, "wb").write((json.dumps(d, sort_keys=True, separators=(",", ":")) + "\n").encode())
    with pytest.raises(G.GateRefusal) as ei:
        authorize(approved_gate)
    assert ei.value.reasons == ["LEDGER_TAMPERED"]


def test_deleted_middle_entry_truncation_and_garbage_fail_closed(approved_gate):
    rec = signed(budget={"max_calls": 9, "max_output_tokens": 10 ** 6})
    for _ in range(3):
        authorize(approved_gate, record=rec)
    lines = ledger_lines(approved_gate)
    open(approved_gate.path, "wb").write(lines[0] + lines[2])                                      # middelste regel weg
    with pytest.raises(G.GateRefusal) as ei:
        authorize(approved_gate, record=rec)
    assert ei.value.reasons == ["LEDGER_TAMPERED"]
    open(approved_gate.path, "wb").write(b"".join(lines)[:-15])                                    # afgekapte staart
    with pytest.raises(G.GateRefusal) as ei:
        authorize(approved_gate, record=rec)
    assert ei.value.reasons == ["LEDGER_CORRUPT"]
    open(approved_gate.path, "wb").write(b"geen json\n")
    with pytest.raises(G.GateRefusal) as ei:
        authorize(approved_gate, record=rec)
    assert ei.value.reasons == ["LEDGER_CORRUPT"]


def test_ledger_path_safety(tmp_path):
    for bad in (os.path.join(PROJECT_ROOT, "reports", "ledger"), PROJECT_ROOT, os.path.dirname(PROJECT_ROOT)):
        with pytest.raises(G.GateRefusal) as ei:
            L.FileBudgetLedger(bad)
        assert ei.value.reasons == ["LEDGER_PATH_UNSAFE"]
    open_dir = tmp_path / "open"; open_dir.mkdir(); os.chmod(open_dir, 0o777)
    with pytest.raises(G.GateRefusal):
        L.FileBudgetLedger(str(open_dir))
    ok = tmp_path / "ok"; ok.mkdir(mode=0o700)
    secret = tmp_path / "secret"; secret.write_text("x")
    (ok / "ledger.jsonl").symlink_to(secret)
    with pytest.raises(G.GateRefusal):
        L.FileBudgetLedger(str(ok))
    assert secret.read_text() == "x"
    with pytest.raises(G.GateRefusal):
        L.FileBudgetLedger(None)


def test_non_persistent_or_foreign_ledgers_are_refused(approved_gate):
    class Memory(G.BudgetLedger):
        persistent, cross_process_safe = False, False
        def reserve(self, **kw): return "RES-1"
        def settle(self, *a, **k): pass
        def release(self, *a, **k): pass
    class Liar:
        persistent, cross_process_safe = True, True
        def reserve(self, **kw): return "RES-1"
    for led in (Memory(), Liar(), None):
        with pytest.raises(G.GateRefusal) as ei:
            authorize(led)
        assert ei.value.reasons == ["LEDGER_NOT_PERSISTENT"]


# --- centrale poort: niet te omzeilen -----------------------------------------------------------------------------------------
def test_gate_authorization_cannot_be_forged():
    with pytest.raises(TypeError):
        G.GateAuthorization("anthropic", "m", 1, "PCON-00001", "p", "h", "ph", None, "RES-1", None)
    with pytest.raises(TypeError):
        G.GateAuthorization("anthropic", "m", 1, "PCON-00001", "p", "h", "ph", None, "RES-1", None, _seal=object())


def test_send_function_refuses_without_a_live_authorization(approved_gate):
    client = FakeClient(GOOD_TEXT)
    auth = authorize(approved_gate)
    with pytest.raises(G.GateRefusal):
        P._send_authorized(client, auth, req(), cfg(), P.PROMPT)                                  # nog niet consume()d
    with pytest.raises(G.GateRefusal):
        G.require_authorization(object(), provider="anthropic", model="m", max_tokens=1, image_bytes=b"x", prompt_sha256="x")
    with pytest.raises(G.GateRefusal) as ei:
        G.require_authorization(auth, provider="anthropic", model="test-model-from-operator", max_tokens=2000, image_bytes=b"andere bytes",
                                prompt_sha256=P.PROMPT_SHA256)
    assert ei.value.reasons == ["AUTHORIZATION_MISMATCH"]
    with pytest.raises(G.GateRefusal):
        G.require_authorization(auth, provider="anthropic", model="ander-model", max_tokens=2000, image_bytes=S.png(), prompt_sha256=P.PROMPT_SHA256)
    with pytest.raises(G.GateRefusal):
        G.require_authorization(auth, provider="anthropic", model="test-model-from-operator", max_tokens=2000, image_bytes=S.png(), prompt_sha256="0" * 64)
    assert client.messages.calls == []


def test_authorization_is_single_use(approved_gate):
    auth = authorize(approved_gate)
    auth.consume()
    with pytest.raises(G.GateRefusal) as ei:
        auth.consume()
    assert ei.value.reasons == ["AUTHORIZATION_ALREADY_USED"]
    auth.settle("OK", 5)
    with pytest.raises(G.GateRefusal):
        G.require_authorization(auth, provider="anthropic", model="test-model-from-operator", max_tokens=2000, image_bytes=S.png(), prompt_sha256=P.PROMPT_SHA256)
    auth.release_unsent("te laat")                                                                  # na verzending kan niets meer worden vrijgegeven
    assert approved_gate.usage("PCON-00001")["calls"] == 1


def test_external_providers_cannot_override_analyze_or_skip_the_hook():
    with pytest.raises(TypeError):
        class Rogue(P.VisionProvider):
            data_egress = "EXTERNAL"
            def describe(self): return {}
            def analyze(self, request): return None
    with pytest.raises(TypeError):
        class NoHook(P.VisionProvider):
            data_egress = "EXTERNAL"
            def describe(self): return {}

    class Okay(P.VisionProvider):
        data_egress = "EXTERNAL"
        def describe(self): return {}
        def _authorize(self, request): raise G.GateRefusal(["STOP"])
        def _analyze_authorized(self, request, auth): raise AssertionError("mag nooit worden bereikt zonder poort")
    with pytest.raises(G.GateRefusal):
        Okay().analyze(req())


def test_every_shipped_provider_declares_its_egress_consistently():
    classes = [P.NullProvider, P.ReplayProvider, P.HumanImportProvider, P.ClaudeVisionProvider]
    for c in classes:
        inst = c.__new__(c)
        assert inst.describe()["data_egress"] == c.data_egress
    assert [c.__name__ for c in classes if c.data_egress != "NONE"] == ["ClaudeVisionProvider"]


def test_only_one_function_sends_data_to_a_client_and_nothing_imports_the_sdk_early():
    hits = []
    pkg = os.path.join(PROJECT_ROOT, "agent")
    for dp, _, files in os.walk(pkg):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(dp, f)
            tree = ast.parse(open(path, encoding="utf-8").read())
            for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for n in ast.walk(fn):
                    if isinstance(n, ast.Attribute) and n.attr in ("create", "stream") and isinstance(n.value, ast.Attribute) and n.value.attr == "messages":
                        hits.append((os.path.relpath(path, PROJECT_ROOT), fn.name))
            src = open(path, encoding="utf-8").read()
            assert "anthropic.Anthropic(" not in src or f == "providers.py"
    assert hits == [("agent/photo/providers.py", "_send_authorized")], hits


# --- provider-integratie: de client wordt nooit aangeroepen als de poort weigert ---------------------------------------------
def run_provider(ledger, client, record=None, request=None, config=None):
    return P.ClaudeVisionProvider(config or cfg(), record if record is not None else signed(), client, ledger).analyze(request or req())


def test_client_is_never_called_when_the_gate_refuses(approved_gate, monkeypatch):
    client = FakeClient(GOOD_TEXT)
    bad_requests = []
    r = req(); r.derivative_sha256 = "0" * 64; bad_requests.append(r)
    r = req(); r.width_px = 1; bad_requests.append(r)
    r = S.request(insert_png_chunk(S.png(), b"tEXt", b"x")); bad_requests.append(r)
    for r in bad_requests:
        with pytest.raises(G.GateRefusal):
            run_provider(approved_gate, client, request=r)
    for rec in (consent(), signed(budget={"max_calls": 1, "max_output_tokens": 10})):
        with pytest.raises(G.GateRefusal):
            run_provider(approved_gate, client, record=rec)
    with pytest.raises(G.GateRefusal):
        run_provider(None, client)
    monkeypatch.delenv(G.ENV_AUTH_KEY)
    with pytest.raises(G.GateRefusal):
        run_provider(approved_gate, client)
    assert client.messages.calls == [] and approved_gate.usage("PCON-00001") == {"calls": 0, "tokens": 0}


def test_failed_send_stays_counted_but_unsent_failure_is_released(approved_gate):
    class Boom:
        class messages:
            @staticmethod
            def create(**kw): raise RuntimeError("netwerkfout midden in verzending")
    with pytest.raises(RuntimeError):
        run_provider(approved_gate, Boom())
    assert approved_gate.usage("PCON-00001")["calls"] == 1                                           # onzeker of de provider iets kreeg: verbruikt
    entries = [json.loads(l) for l in ledger_lines(approved_gate)]
    assert [e["event"] for e in entries] == ["RESERVE", "SETTLE"] and entries[1]["outcome"] == "SEND_FAILED"


def test_provider_budget_survives_new_provider_instances(approved_gate):
    rec = signed(budget={"max_calls": 1, "max_output_tokens": 100_000})
    client = FakeClient(GOOD_TEXT)
    run_provider(approved_gate, client, record=rec)
    with pytest.raises(G.GateRefusal) as ei:
        run_provider(L.FileBudgetLedger(approved_gate.dir), client, record=rec)
    assert ei.value.reasons == ["BUDGET_CALLS_EXHAUSTED"] and len(client.messages.calls) == 1


def test_shipped_defaults_make_a_real_call_impossible(tmp_path, monkeypatch):
    """Zonder test-aanpassingen: provider NOT_APPROVED, geen sleutels, geen grootboek."""
    monkeypatch.delenv(G.ENV_AUTH_KEY, raising=False)
    client = FakeClient(GOOD_TEXT)
    led = L.FileBudgetLedger(str(tmp_path / "l"))
    with pytest.raises(G.GateRefusal) as ei:
        run_provider(led, client)
    assert ei.value.reasons == ["PROVIDER_NOT_APPROVED"] and client.messages.calls == []
