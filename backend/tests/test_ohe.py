"""End-to-end scenarios from the OHE HLD §15.2 (V01–V07, V09, V11) with fixture model adapters."""
import hashlib
import math
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest
import yaml

from app.config import settings
from app.ohe import api as ohe
from app.ohe import auth
from app.ohe.pipeline import Det

SIGNER = {"X-Actor": "sse-trd-1", "X-Role": "SSE"}
PATROL = {"X-Actor": "pt-1", "X-Role": "Patrol"}
NEAR_12 = {"lat": "26.91258", "lon": "75.78755", "accuracy_m": "8"}


def _jpeg(seed=0, blur=False):
    rng = np.random.default_rng(seed)
    img = (rng.integers(40, 215, (768, 1024, 3))).astype(np.uint8)
    if blur:
        img = cv2.GaussianBlur(img, (0, 0), 25)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()


class FixDet:
    version = "fixture-det"
    def __init__(self, dets): self.dets = dets
    def detect(self, img): return self.dets


class FixOCR:
    version = "fixture-ocr"
    def __init__(self, texts): self.texts = texts
    def read(self, img): return [(t, 0.97) for t in self.texts]


INS = Det("insulator", 0.91, (400, 200, 520, 420))
NEST = Det("bird_nest", 0.88, (300, 300, 520, 480))
DEFECT = Det("insulator_defect", 0.83, (430, 260, 500, 330))


@pytest.fixture
def models():
    yield ohe.Models
    ohe.Models.detector, ohe.Models.ocr = ohe.pipeline.NullDetector(), ohe.pipeline.NullOCR()


def _session(client, expected=None):
    return client.post("/ohe/sessions", json={"territory": "SEC-DEMO-01", "expected_assets": expected}, headers=PATROL).json()["id"]


def _upload(client, sid, data, **form):
    f = {"sha256": hashlib.sha256(data).hexdigest(), "captured_at": datetime.now(UTC).isoformat()} | form
    return client.post(f"/ohe/sessions/{sid}/media", files={"image": ("a.jpg", data, "image/jpeg")}, data=f, headers=PATROL)


def test_v01_known_defect_assessed_and_routed_without_confirmation(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    sid = _session(client)
    r = _upload(client, sid, _jpeg(1), **NEAR_12).json()
    a = r["analysis"]["assessments"][0]
    assert r["analysis"]["identity"]["selected_asset_id"] == "1205/12"
    assert a["state"] == "assessable_defect" and a["condition"] == "insulator_visible_damage"
    assert a["routing"]["primary"] == "OHE coordinator" and a["alert"] and a["confidence"]["calibration"] == "uncalibrated"
    assert "Internal condition" in a["limitations"]                       # scoped claim, no electrical health
    fs = client.get(f"/ohe/sessions/{sid}/processing").json()["findings"]
    assert len(fs) == 1 and fs[0]["asset_id"] == "1205/12" and fs[0]["alert"]


def test_v02_no_visible_defect_is_scoped(client, models):
    models.detector, models.ocr = FixDet([INS]), FixOCR(["1205/12"])
    sid = _session(client, ["1205/12", "1205/14"])
    a = _upload(client, sid, _jpeg(2), **NEAR_12).json()["analysis"]
    assert a["assessments"][0]["state"] == "assessable_no_visible_defect"
    rep = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()
    reg = {x["asset_id"]: x["state"] for x in client.get(f"/ohe/reports/{rep['report_id']}").json()["content"]["RPT-05_asset_register"]}
    assert reg == {"1205/12": "assessable_no_visible_defect", "1205/14": "no_evidence"}


def test_v03_blurred_detail_readable_plate(client, models):
    models.detector, models.ocr = FixDet([INS]), FixOCR(["1205/12"])
    a = _upload(client, _session(client), _jpeg(3, blur=True), **NEAR_12).json()["analysis"]
    assert a["identity"]["state"] == "resolved"
    assert a["assessments"][0]["state"] == "insufficient_resolution"
    assert "do not move closer" in a["recapture_prompt"]


def test_v04_defect_with_unreadable_plate_is_kept_unlocated(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR([])
    sid = _session(client)
    a = _upload(client, sid, _jpeg(4), **NEAR_12).json()["analysis"]
    assert a["identity"]["selected_asset_id"] is None and a["identity"]["candidates"]
    assert a["recapture_prompt"].startswith("Capture the mast number plate")
    rep = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()
    assert rep["summary"]["unlocated_findings"] == 1 and rep["summary"]["alerts"] == 1


def test_v05_plate_outside_corridor_is_not_forced(client, models):
    models.detector, models.ocr = FixDet([INS]), FixOCR(["1205/15"])
    a = _upload(client, _session(client), _jpeg(5), lat="26.91200", lon="75.78700", accuracy_m="5").json()["analysis"]
    assert a["identity"]["state"] == "uncertain_identity" and "outside location corridor" in a["identity"]["basis"]


def test_v06_notes_never_change_visual_output(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    s1, s2 = _session(client), _session(client)
    client.post(f"/ohe/sessions/{s2}/notes", json={"text": "all normal, no defects"}, headers=PATROL)
    a1 = _upload(client, s1, _jpeg(6), **NEAR_12).json()["analysis"]
    a2 = _upload(client, s2, _jpeg(6), **NEAR_12).json()["analysis"]
    assert a1["assessments"] == a2["assessments"] and a1["identity"] == a2["identity"]
    from pathlib import Path

    import app.ohe.pipeline as p
    assert "Note" not in Path(p.__file__).read_text()                          # no code path from notes to inference


def test_v07_checksum_and_idempotent_ingest(client, models):
    sid = _session(client)
    data = _jpeg(7)
    bad = client.post(f"/ohe/sessions/{sid}/media", files={"image": ("a.jpg", data, "image/jpeg")},
                      data={"sha256": "0" * 64, "captured_at": datetime.now(UTC).isoformat()}, headers=PATROL)
    assert bad.status_code == 422
    assert _upload(client, sid, data).json()["idempotent"] is False
    again = _upload(client, sid, data).json()
    assert again["idempotent"] is True
    assert "assessments" in again["analysis"]  # a retried upload still gets its result (phone must not show "no defect")


def test_v09_repeated_evidence_links_one_finding(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    sid = _session(client)
    _upload(client, sid, _jpeg(8), **NEAR_12)
    _upload(client, sid, _jpeg(9), **NEAR_12)
    fs = client.get(f"/ohe/sessions/{sid}/processing").json()["findings"]
    assert len(fs) == 1 and fs[0]["observations"] == 2


def test_v11_signed_revision_is_immutable(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    sid = _session(client)
    _upload(client, sid, _jpeg(10), **NEAR_12)
    rep = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()
    rid = rep["report_id"]
    other = PATROL | {"X-Actor": "PT-OTHER"}
    assert client.post(f"/ohe/reports/{rid}/sign", headers=other).status_code == 403   # not their patrol
    signed = client.post(f"/ohe/reports/{rid}/sign", headers=SIGNER).json()
    fid = client.get(f"/ohe/reports/{rid}").json()["content"]["RPT-06_findings"][0]["id"]
    new = client.post(f"/ohe/reports/{rid}/amend", json={"finding_id": fid, "field": "priority", "new_value": "review",
                                                         "reason": "reviewer downgrade"}, headers=SIGNER).json()
    old = client.get(f"/ohe/reports/{rid}").json()
    assert old["status"] == "AUTHORISED_SIGNED" and old["sha256"] == signed["sha256"]
    assert new["revision"] == 2 and new["supersedes"] == rid
    assert client.get(f"/ohe/reports/{new['report_id']}").json()["sha256"] != signed["sha256"]
    assert "OHE visual patrol report" in client.get(f"/ohe/reports/{rid}/html").text
    # the phone keeps the first revision's id and follows "latest" to the amended one
    assert old["latest"]["id"] == new["report_id"] and old["latest"]["revision"] == 2
    assert old["latest"]["status"] == "READY_FOR_REVIEW"


# ---- sign-in, reviewer lists, alert feed and evidence images ----


def test_lists_alert_feed_and_photo(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    sid = _session(client)
    up = _upload(client, sid, _jpeg(3), **NEAR_12).json()
    mid = up["media"]["id"]
    alerts = client.get("/ohe/alerts", headers=SIGNER).json()
    assert any(a["session"] == sid and a["asset_id"] == "1205/12" for a in alerts)  # raised before any report exists
    rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
    rows = client.get("/ohe/reports", headers=SIGNER).json()
    row = next(r for r in rows if r["id"] == rid)
    assert row["status"] == "READY_FOR_REVIEW" and row["summary"]["alerts"] >= 1
    info = client.get(f"/ohe/media/{mid}", headers=SIGNER).json()
    assert info["assessments"] and info["identity"]["selected_asset_id"] == "1205/12"
    img = client.get(f"/ohe/media/{mid}/image", headers=SIGNER)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert client.get("/ohe/review").status_code == 200
    me = client.get("/ohe/me", headers=SIGNER).json()
    assert me["can_sign"] is True


def test_token_mode_requires_sign_in(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "token")
    monkeypatch.setattr(settings, "secret_key", "test-secret")
    users = tmp_path / "users.yaml"
    monkeypatch.setattr(settings, "users_file", users)
    users.write_text(yaml.safe_dump({"users": [{"id": "SSE-1", "name": "SSE", "role": "SSE", "pin_sha256": auth.pin_hash("4826")}]}))
    assert client.get("/ohe/reports", headers=SIGNER).status_code == 401          # headers no longer trusted
    assert client.post("/ohe/auth/login", json={"id": "SSE-1", "pin": "0000"}).status_code == 401
    tok = client.post("/ohe/auth/login", json={"id": "SSE-1", "pin": "4826"}).json()["token"]
    me = client.get("/ohe/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me == {"id": "SSE-1", "role": "SSE", "can_sign": True, "signoff": "patroller"}
    bad = tok[:-2] + ("AA" if not tok.endswith("AA") else "BB")
    assert client.get("/ohe/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


# ---- HLD V08, V10, V12 and report sections RPT-03/07/11/12 ----

class BrokenDet:
    version = "broken"
    def detect(self, img): raise TimeoutError("model backend timed out")


def test_v08_processing_failure_is_visible_and_retryable(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    sid = _session(client)
    good = _upload(client, sid, _jpeg(20), **NEAR_12).json()
    assert good["analysis"]["assessments"]
    models.detector = BrokenDet()
    bad = _upload(client, sid, _jpeg(21), **NEAR_12)
    assert bad.status_code == 201 and bad.json()["media"]["status"] == "failed"     # evidence kept, failure recorded
    mid = bad.json()["media"]["id"]
    assert client.post(f"/ohe/media/{mid}/reprocess", headers=PATROL).status_code == 503
    rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
    c = client.get(f"/ohe/reports/{rid}", headers=SIGNER).json()["content"]
    assert c["RPT-02_summary"]["failed_media"] == 1
    assert any(mid in x and "could not be processed" in x for x in c["RPT-09_limitations"])
    assert c["RPT-06_findings"]                                                      # completed findings remain available
    models.detector = FixDet([INS])
    assert client.post(f"/ohe/media/{mid}/reprocess", headers=PATROL).json()["status"] == "assessed"


def test_v10_no_improvement_claim_without_comparison(client, models):
    models.detector, models.ocr = FixDet([INS]), FixOCR(["1205/12"])
    sid = _session(client)
    _upload(client, sid, _jpeg(22), **NEAR_12)
    rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
    c = client.get(f"/ohe/reports/{rid}", headers=SIGNER).json()["content"]
    assert c["RPT-07_temporal"]["state"] in ("first_cycle", "compared")   # compared now, but never as improvement
    import json as _j
    text = _j.dumps(c["RPT-06_findings"]).lower()
    assert "improv" not in text and "resolved since" not in text


def test_v12_unknown_design_is_unsupported_not_a_pass(client, models):
    models.detector, models.ocr = FixDet([Det("cantilever_tube_unknown", 0.88, (300, 150, 600, 400))]), FixOCR(["1205/12"])
    sid = _session(client, expected=["1205/12"])
    a = _upload(client, sid, _jpeg(23), **NEAR_12).json()["analysis"]
    assert a["assessments"][0]["state"] == "unsupported_class"
    rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
    c = client.get(f"/ohe/reports/{rid}", headers=SIGNER).json()["content"]
    row = c["RPT-05_asset_register"][0]
    assert row["state"] == "unsupported_class" and c["RPT-02_summary"]["no_visible_defect"] == 0
    assert any("not supported" in x for x in c["RPT-09_limitations"])


def test_report_sections_coverage_notes_and_review(client, models):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    sid = _session(client, expected=["1205/12", "1205/13"])
    _upload(client, sid, _jpeg(24), **NEAR_12)
    client.post(f"/ohe/sessions/{sid}/notes", json={"text": "branch near mast"}, headers=PATROL)
    rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
    r = client.get(f"/ohe/reports/{rid}", headers=SIGNER).json()
    c = r["content"]
    assert "not verified inspection coverage" in c["RPT-03_coverage"]["statement"]
    assert c["RPT-03_coverage"]["evidence_gaps"] == ["1205/13"]
    assert c["RPT-12_notes"]["notes"][0]["text"] == "branch near mast"
    assert "not used by the AI" in c["RPT-12_notes"]["statement"]
    assert all(a["status"].startswith("suggested") for a in c["RPT-08_actions"])
    client.post(f"/ohe/reports/{rid}/sign", headers=SIGNER)
    rev = client.get(f"/ohe/reports/{rid}", headers=SIGNER).json()["RPT-11_review"]
    assert rev["signer"] == "sse-trd-1" and rev["report_checksum"] == r["sha256"] and rev["signed_at"]


class FixView:
    version, threshold = "fixture-view", 0.5
    def __init__(self, p): self.p = p
    def p_distorted(self, img): return self.p


def test_view_check_is_information_only(client, models):
    models.detector, models.ocr = FixDet([INS]), FixOCR(["1205/12"])
    sid = _session(client)
    base = _upload(client, sid, _jpeg(30), **NEAR_12).json()["analysis"]
    models.view = FixView(0.9)
    try:
        a = _upload(client, sid, _jpeg(31), **NEAR_12).json()["analysis"]
    finally:
        models.view = None
    assert a["view_check"]["flag"] is True and a["recapture_prompt"] is None   # angled photos are accepted
    assert [x["state"] for x in a["assessments"]] == [x["state"] for x in base["assessments"]]   # assessment unchanged


def test_app_update_publish_and_latest(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "app_dir", tmp_path / "app")
    assert client.get("/ohe/app/latest", headers=PATROL).status_code == 404
    admin = {"X-Actor": "admin", "X-Role": "Admin"}
    assert client.post("/ohe/app", files={"apk": ("a.apk", b"APK1", "application/octet-stream")},
                       data={"version_code": "1012", "version_name": "0.2.1012"}, headers=PATROL).status_code == 403
    r = client.post("/ohe/app", files={"apk": ("a.apk", b"APK1", "application/octet-stream")},
                    data={"version_code": "1012", "version_name": "0.2.1012", "notes": "Sign-in\nUpdates"}, headers=admin)
    assert r.status_code == 201
    latest = client.get("/ohe/app/latest", headers=PATROL).json()
    assert latest["version_code"] == 1012 and latest["notes"] == ["Sign-in", "Updates"]
    assert client.get("/ohe/app/apk", headers=PATROL).content == b"APK1"


def test_connect_page_and_public_apk(tmp_path, monkeypatch):
    """Laptop server: connect info, page and the public app download from a dropped-in .apk."""
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    from app.ohe import lan
    monkeypatch.setattr(settings, "app_dir", tmp_path / "app")
    drop = tmp_path / "drop"
    drop.mkdir()
    (drop / "OnTrack.AI-draft1.apk").write_bytes(b"PK-fake-apk")
    (drop / "latest.json").write_text('{"version_code": 1001, "version_name": "0.3.1001"}')
    assert lan.install_app_from(drop)
    c = TestClient(app)
    info = c.get("/ohe/connect/info").json()
    assert info["app"]["version_code"] == 1001 and info["name"]
    assert c.get("/ohe/connect/app.apk").content == b"PK-fake-apk"
    page = c.get("/ohe/connect").text
    assert "OnTrack.AI server is running" in page and "app.apk" in page
    monkeypatch.setattr(settings, "public_apk", False)
    assert c.get("/ohe/connect/app.apk").status_code == 404


def test_server_starts_with_mdns_on(monkeypatch):
    """Laptop mode: startup with discovery enabled must not block or crash (Windows EventLoopBlocked regression)."""
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    monkeypatch.setattr(settings, "mdns", True)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert "mdns" in c.get("/ohe/connect/info").json()


def test_internet_sign_in_layer(tmp_path, monkeypatch):
    """Over-the-internet use: PIN lockout, laptop-only pages hidden through the tunnel, pairing needs a sign-in,
    relay messages are signed, and the tunnel's public address is picked up from cloudflared."""
    import json as _json
    import stat
    import time as _time

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    from app.ohe import auth, remote
    users = tmp_path / "users.yaml"
    monkeypatch.setattr(settings, "users_file", users)
    monkeypatch.setattr(settings, "relay_file", tmp_path / "relay.json")
    monkeypatch.setattr(settings, "auth_mode", "token")
    monkeypatch.setattr(settings, "tunnel", "fixed-test")
    monkeypatch.setattr(settings, "public_url", "https://ontrack.example.org")
    import yaml
    users.write_text(yaml.safe_dump({"users": [{"id": "PT-9", "name": "T", "role": "Patrol", "pin_sha256": auth.pin_hash("2468")}]}))
    remote._fails.clear()
    c = TestClient(app)
    fwd = {"cf-connecting-ip": "203.0.113.7"}
    # lockout after 5 wrong PINs, even the right PIN is refused while locked
    for _ in range(5):
        assert c.post("/ohe/auth/login", json={"id": "PT-9", "pin": "0000"}, headers=fwd).status_code == 401
    r = c.post("/ohe/auth/login", json={"id": "PT-9", "pin": "2468"}, headers=fwd)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    remote._fails.clear()
    tok = c.post("/ohe/auth/login", json={"id": "PT-9", "pin": "2468"}, headers=fwd).json()["token"]
    # laptop-only pages are hidden through the tunnel, visible locally
    assert c.get("/ohe/connect", headers=fwd).status_code == 404
    assert c.get("/ohe/connect/info", headers=fwd).status_code == 404
    assert c.get("/ohe/connect/info").json()["public_url"] == "https://ontrack.example.org/"
    # pairing requires a token and returns the relay key
    assert c.get("/ohe/connect/pairing", headers=fwd).status_code == 401
    p = c.get("/ohe/connect/pairing", headers=fwd | {"Authorization": f"Bearer {tok}"}).json()
    assert p["public_url"] == "https://ontrack.example.org/" and p["relay"]["topic"].startswith("ontrack-")
    # relay signature is HMAC-SHA256 over "url|ts" with the pairing key
    ts = int(_time.time())
    assert remote.sign("https://a.example/", ts, p["relay"]["key"]) == remote.sign("https://a.example/", ts, remote.relay_secrets()["key"])
    assert _json.loads((tmp_path / "relay.json").read_text())["key"] == p["relay"]["key"]
    # cloudflared stand-in prints the quick-tunnel address on stderr; the supervisor picks it up
    fake = tmp_path / "cloudflared"
    fake.write_text("#!/bin/sh\necho 'INF |  https://brave-test-words.trycloudflare.com  |' 1>&2\nsleep 30\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(settings, "public_url", "")
    monkeypatch.setattr(settings, "cloudflared_path", fake)
    monkeypatch.setattr(settings, "relay_server", "")
    monkeypatch.setattr(settings, "tunnel", "cloudflare")
    remote._state["public_url"] = None
    remote.start()
    for _ in range(50):
        if remote.public_url():
            break
        _time.sleep(0.1)
    assert remote.public_url() == "https://brave-test-words.trycloudflare.com/"
    remote.stop()


def test_sign_in_ignores_id_case(tmp_path, monkeypatch):
    """An account created as 'pt-0007' signs in as 'PT-0007' (the phone sends capitals) and vice versa."""
    import yaml
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    from app.ohe import auth, remote
    users = tmp_path / "users.yaml"
    users.write_text(yaml.safe_dump({"users": [{"id": "pt-0007", "name": "R", "role": "Patrol", "pin_sha256": auth.pin_hash("1357")}]}))
    monkeypatch.setattr(settings, "users_file", users)
    remote._fails.clear()
    c = TestClient(app)
    for typed in ("PT-0007", "pt-0007", " Pt-0007 "):
        r = c.post("/ohe/auth/login", json={"id": typed, "pin": "1357"})
        assert r.status_code == 200, typed
        assert r.json()["id"] == "pt-0007"
    assert c.post("/ohe/auth/login", json={"id": "PT-0007", "pin": "9999"}).status_code == 401


# ---------------------------------------------------------------- mast lean, corrosion, vegetation, calibration
def _mast_img(angle_deg: float, w=900, h=1200):
    import cv2
    img = np.full((h, w, 3), 200, np.uint8)
    t = math.radians(angle_deg)
    cx, top, bot = w // 2, 100, h - 50
    dx = (bot - top) * math.tan(t)          # top leans right for positive angle
    pts = np.array([[cx - 30 + dx / 2, top], [cx + 30 + dx / 2, top], [cx + 30 - dx / 2, bot], [cx - 30 - dx / 2, bot]], np.int32)
    cv2.fillPoly(img, [pts], (60, 60, 60))
    rng = np.random.default_rng(0)  # sensor-like texture so the photo passes the sharpness gate
    img = np.clip(img.astype(int) + rng.integers(-25, 25, img.shape), 0, 255).astype(np.uint8)
    return img, (cx - 200, top - 10, cx + 200, bot + 10)


def test_mast_lean_measured_and_corrected_for_phone_tilt():
    from app.ohe.pipeline import mast_lean
    img, box = _mast_img(5.0)
    lean, _ = mast_lean(img, box, 0.0)
    assert lean is not None and abs(lean - 5.0) < 1.0
    lean2, _ = mast_lean(img, box, -5.0)    # phone itself was turned: the apparent lean was the phone, not the mast
    assert abs(lean2) < 1.0
    assert mast_lean(img, box, None)[0] is None
    assert mast_lean(img, box, 45.0)[0] is None


def test_mast_lean_raises_review_finding():
    from app.ohe import pipeline
    img, box = _mast_img(6.0)
    reg = pipeline.load_registry()

    class D:
        version = "t"
        def detect(self, _):
            return [pipeline.Det("mast", 0.9, box)]
    r = pipeline.assess_image(img, reg, D(), pipeline.NullOCR(), roll_deg=0.0)
    o = r["observations"][0]
    assert o["state"] == "assessable_defect" and o["condition"] == "mast_lean"
    a = pipeline.decide(o, r["identity"], True, reg)
    assert a["rule_id"] == "R-LEAN-01" and a["priority"] == "review" and not a["alert"]
    r0 = pipeline.assess_image(_mast_img(0.5)[0], reg, D(), pipeline.NullOCR(), roll_deg=0.0)
    assert r0["observations"][0]["state"] == "assessable_no_visible_defect"


def test_corrosion_and_vegetation_are_routine_findings():
    from app.ohe import pipeline
    reg = pipeline.load_registry()
    img = np.full((800, 800, 3), 128, np.uint8)
    img[::7] = 30

    class D:
        version = "t"
        def detect(self, _):
            return [pipeline.Det("corrosion", 0.8, (100, 100, 400, 400)), pipeline.Det("vegetation", 0.7, (400, 400, 780, 780))]
    r = pipeline.assess_image(img, reg, D(), pipeline.NullOCR())
    asm = {a["component"]: pipeline.decide(a, r["identity"], True, reg) for a in r["observations"]}
    assert asm["corrosion"]["rule_id"] == "R-COR-01" and asm["vegetation"]["rule_id"] == "R-VEG-01"
    assert all(a["priority"] == "routine" and not a["alert"] for a in asm.values())


def test_calibration_applied_when_fitted():
    from app.ohe import pipeline
    cal = {"classes": {"insulator": {"a": 1.0, "b": 0.0}}}
    assert abs(pipeline.calibrate(0.7, "insulator", cal) - 0.7) < 1e-3
    assert pipeline.calibrate(0.7, "mast", cal) is None and pipeline.calibrate(0.7, "insulator", None) is None


def test_existing_database_gets_new_columns(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from app import db
    eng = create_engine(f"sqlite:///{tmp_path/'old.db'}")
    with eng.begin() as c:
        c.execute(text('CREATE TABLE ohemedia (id VARCHAR PRIMARY KEY, session_id VARCHAR)'))
    old, db.engine = db.engine, eng
    try:
        db._add_missing_columns()
    finally:
        db.engine = old
    assert "roll_deg" in {c["name"] for c in inspect(eng).get_columns("ohemedia")}


def test_report_compares_with_previous_patrol_of_same_section(client, models):
    terr = {"territory": "SEC-CMP-" + datetime.now(UTC).strftime("%H%M%S%f")}
    def cycle(dets, seed):
        models.detector, models.ocr = FixDet(dets), FixOCR(["1205/12"])
        sid = client.post("/ohe/sessions", json=terr | {"expected_assets": ["1205/12"]}, headers=PATROL).json()["id"]
        _upload(client, sid, _jpeg(seed), **NEAR_12)
        rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
        return client.get(f"/ohe/reports/{rid}").json()["content"]
    first = cycle([INS, DEFECT], 501)
    assert first["RPT-07_temporal"]["state"] == "first_cycle"
    second = cycle([INS, DEFECT], 502)
    t = second["RPT-07_temporal"]
    assert t["state"] == "compared" and t["persistent"] == 1 and t["new"] == 0
    assert second["RPT-06_findings"][0]["temporal"] == "persistent"
    third = cycle([INS], 503)                       # mast assessed clean this time
    g = third["RPT-07_temporal"]["not_seen_again"]
    assert len(g) == 1 and g[0]["state"] == "not_seen_this_cycle" and "not proof of repair" in third["RPT-07_temporal"]["statement"]


def test_real_detector_numpy_scores_are_stored(client, models):
    """The ONNX adapter yields numpy numbers; a finding built from them must save (Windows smoke test caught this)."""
    box = tuple(np.float32(v) for v in (100, 100, 400, 400))
    models.detector, models.ocr = FixDet([Det("vegetation", np.float32(0.8), box)]), FixOCR([])
    sid = _session(client)
    r = _upload(client, sid, _jpeg(777)).json()
    assert r["media"]["status"] == "assessed" and r["analysis"]["assessments"][0]["condition"] == "vegetation_near_ohe"



def test_patroller_signs_off_own_patrol(client, models, monkeypatch):
    models.detector, models.ocr = FixDet([INS, DEFECT]), FixOCR(["1205/12"])
    sid = _session(client)
    _upload(client, sid, _jpeg(901), **NEAR_12)
    rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
    assert client.get(f"/ohe/reports/{rid}", headers=PATROL).json()["can_sign"] is True
    r = client.post(f"/ohe/reports/{rid}/sign", headers=PATROL | {"X-Actor": PATROL["X-Actor"].lower()}).json()
    assert r["status"] == "PATROLLER_SIGNED"
    got = client.get(f"/ohe/reports/{rid}").json()
    assert got["status"] == "PATROLLER_SIGNED" and got["signoff"] == "patroller"
    assert client.post(f"/ohe/reports/{rid}/sign", headers=SIGNER).status_code == 409   # already closed


def test_sse_mode_needs_authorised_signer(client, models, monkeypatch):
    from app.ohe import api
    monkeypatch.setattr(api.settings, "signoff", "sse")
    models.detector, models.ocr = FixDet([INS]), FixOCR(["1205/12"])
    sid = _session(client)
    _upload(client, sid, _jpeg(902), **NEAR_12)
    rid = client.post(f"/ohe/sessions/{sid}/end", headers=PATROL).json()["report_id"]
    assert client.post(f"/ohe/reports/{rid}/sign", headers=PATROL).status_code == 403
    assert client.post(f"/ohe/reports/{rid}/sign", headers=SIGNER).json()["status"] == "AUTHORISED_SIGNED"



def test_no_framing_demands_for_partial_views(client, models):
    """Field photos are partial and at any angle: nothing detected or a partial view never asks to reframe."""
    models.detector, models.ocr = FixDet([]), FixOCR([])
    sid = _session(client)
    a = _upload(client, sid, _jpeg(40)).json()["analysis"]
    assert a["recapture_prompt"] is None


def test_rotation_merge_finds_sideways_parts():
    import cv2

    from app.ohe import pipeline

    class Upright:   # finds a tall bar only when it stands upright, like a detector trained on upright insulators
        version = "u"
        def detect(self, img):
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) < 80
            ys, xs = np.nonzero(g)
            if len(xs) == 0 or (ys.max() - ys.min()) < 2 * (xs.max() - xs.min()):
                return []
            return [pipeline.Det("insulator", 0.9, (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())))]
    img = np.full((400, 600, 3), 200, np.uint8)
    img[180:220, 100:500] = 30                       # a horizontal part (e.g. a bracket insulator)
    assert Upright().detect(img) == []
    d = pipeline.RotationTTA(Upright()).detect(img)
    assert len(d) == 1 and d[0].cls == "insulator"
    x1, y1, x2, y2 = d[0].box
    assert x1 < 130 and x2 > 470 and 150 < y1 < 200 and 200 < y2 < 250   # box mapped back onto the original photo


def _exif_jpeg(seed, lat=None, lon=None, when=None):
    import io
    from PIL import Image
    from PIL.TiffImagePlugin import IFDRational as R
    im = Image.fromarray(cv2.cvtColor(cv2.imdecode(np.frombuffer(_jpeg(seed), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB))
    ex = im.getexif()
    def dms(v):
        d = int(v); m = int((v - d) * 60); return (R(d), R(m), R(round(((v - d) * 60 - m) * 60, 2)))
    if lat is not None:
        ex[0x8825] = {1: "N", 2: dms(lat), 3: "E", 4: dms(lon)}
    if when:
        ex[306] = when
    b = io.BytesIO()
    im.save(b, "JPEG", exif=ex, quality=95)
    return b.getvalue()


def test_gallery_photo_located_by_exif_without_mast_number(client, models):
    models.detector, models.ocr = FixDet([NEST]), FixOCR([])
    sid = _session(client)
    data = _exif_jpeg(601, 26.9124, 75.7873, "2026:11:05 10:45:00")
    r = _upload(client, sid, data, origin="gallery").json()
    m = r["media"]
    assert m["location_source"] == "exif" and abs(m["lat"] - 26.9124) < 1e-3 and m["time_source"] == "exif"
    assert str(m["captured_at"]).startswith("2026-11-05")
    f = r["analysis"]["assessments"][0]
    assert f["state"] == "assessable_defect"
    proc = client.get(f"/ohe/sessions/{sid}/processing", headers=PATROL).json()
    assert proc["findings"][0]["assessment"]["where"]["location_source"] == "exif"


def test_stamped_location_read_from_photo_text(client, models):
    models.detector, models.ocr = FixDet([NEST]), FixOCR(["Lat26.912400", "Long75.787300", "05/11/202610:45AM"])
    sid = _session(client)
    r = _upload(client, sid, _jpeg(602), origin="gallery").json()
    w = r["analysis"]["where"]
    assert w["location_source"] == "photo_stamp" and abs(w["lat"] - 26.9124) < 1e-6 and w["time_source"] == "photo_stamp"


def test_unlocated_findings_on_different_photos_stay_separate(client, models):
    models.detector, models.ocr = FixDet([NEST]), FixOCR([])
    sid = _session(client)
    _upload(client, sid, _jpeg(603))
    _upload(client, sid, _jpeg(604))
    assert len(client.get(f"/ohe/sessions/{sid}/processing", headers=PATROL).json()["findings"]) == 2
