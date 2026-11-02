"""Sign-in, reviewer lists, alert feed and evidence images for the OHE service."""
import yaml

from app.config import settings
from app.ohe import auth
from tests.test_ohe import DEFECT, INS, NEAR_12, PATROL, SIGNER, FixDet, FixOCR, _jpeg, _session, _upload, models  # noqa: F401


def test_lists_alert_feed_and_photo(client, models):  # noqa: F811
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
    assert me == {"id": "SSE-1", "role": "SSE", "can_sign": True}
    bad = tok[:-2] + ("AA" if not tok.endswith("AA") else "BB")
    assert client.get("/ohe/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
