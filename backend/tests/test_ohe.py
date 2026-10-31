"""End-to-end scenarios from the OHE HLD §15.2 (V01–V07, V09, V11) with fixture model adapters."""
import hashlib
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest

from app.ohe import api as ohe
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
    assert _upload(client, sid, data).json()["idempotent"] is True


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
    assert client.post(f"/ohe/reports/{rid}/sign", headers=PATROL).status_code == 403
    signed = client.post(f"/ohe/reports/{rid}/sign", headers=SIGNER).json()
    fid = client.get(f"/ohe/reports/{rid}").json()["content"]["RPT-06_findings"][0]["id"]
    new = client.post(f"/ohe/reports/{rid}/amend", json={"finding_id": fid, "field": "priority", "new_value": "review",
                                                         "reason": "reviewer downgrade"}, headers=SIGNER).json()
    old = client.get(f"/ohe/reports/{rid}").json()
    assert old["status"] == "AUTHORISED_SIGNED" and old["sha256"] == signed["sha256"]
    assert new["revision"] == 2 and new["supersedes"] == rid
    assert client.get(f"/ohe/reports/{new['report_id']}").json()["sha256"] != signed["sha256"]
    assert "OHE visual patrol report" in client.get(f"/ohe/reports/{rid}/html").text
