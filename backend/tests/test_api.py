from datetime import UTC, datetime

import cv2
import numpy as np

KEYMAN = {"X-Actor": "KM-0412", "X-Role": "Keyman"}
JE = {"X-Actor": "JE-PW-77", "X-Role": "JE"}


def _jpeg(blur=False):
    rng = np.random.default_rng(1)
    img = (rng.random((960, 1280)) * 255).astype(np.uint8)
    for x in range(0, 1280, 40):
        cv2.line(img, (x, 0), (x, 960), 255, 2)
    if blur:
        img = cv2.GaussianBlur(img, (41, 41), 15)
    _ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    return buf.tobytes()


def _patrol(client):
    r = client.post("/patrols", json={"patrol_type": "PT-01", "beat_from_km": "1204/0", "beat_to_km": "1207/4",
                                      "line": "UP", "kit_check_ok": True}, headers=KEYMAN)
    assert r.status_code == 201
    return r.json()["id"]


def test_health_and_taxonomy_hindi(client):
    assert client.get("/health").json()["status"] == "ok"
    t = client.get("/taxonomy", params={"lang": "hi"}).json()
    erc = next(c for c in t["classes"] if c["id"] == "PW-FS-001")
    assert erc["label"] == "ERC गायब"
    assert all(c["category"] != "D" for c in t["classes"])  # Cat D never offered as a visual class


def test_r1_disabled_class_rejected(client):
    pid = _patrol(client)
    r = client.post("/findings", json={"patrol_id": pid, "class_id": "PW-RL-009", "km_reference": "1205/2", "line": "UP"},
                    headers=KEYMAN)
    assert r.status_code == 422


def test_r2_protect_first_requires_protection(client):
    pid = _patrol(client)
    body = {"patrol_id": pid, "class_id": "PW-RL-001", "km_reference": "1205/2", "line": "UP", "rail_side": "L"}
    assert client.post("/findings", json=body, headers=KEYMAN).status_code == 422
    t = datetime.now(UTC).isoformat()
    body |= {"line_protected_at": t, "sm_informed_at": t, "action_taken": "Protected per G&SR 3.62; SM informed"}
    assert client.post("/findings", json=body, headers=KEYMAN).status_code == 201


def test_full_lifecycle_with_quality_gate_and_closure(client):
    pid = _patrol(client)
    f = client.post("/findings", json={"patrol_id": pid, "class_id": "PW-FS-001", "km_reference": "1205/6",
                                       "line": "UP", "rail_side": "R", "action_taken": "Recouped ERC"},
                    headers=KEYMAN).json()
    ev = client.post(f"/findings/{f['id']}/evidence", files={"image": ("a.jpg", _jpeg(), "image/jpeg")},
                     data={"kind": "defect"}, headers=KEYMAN).json()
    assert ev["quality"]["passed"] and ev["ai_candidates"] == []  # R3: no model configured → no AI labels
    # R4 keyman cannot review
    assert client.post(f"/findings/{f['id']}/review", json={"accept": True, "severity": "RF-P3"}, headers=KEYMAN).status_code == 403
    # reviewer must assign severity
    assert client.post(f"/findings/{f['id']}/review", json={"accept": True}, headers=JE).status_code == 422
    r = client.post(f"/findings/{f['id']}/review", json={"accept": True, "severity": "RF-P3", "work_order_ref": "TMS-WO-1"},
                    headers=JE)
    assert r.json()["status"] == "reviewed"
    # R5 blurred closure evidence is refused
    bad = client.post(f"/findings/{f['id']}/evidence", files={"image": ("c.jpg", _jpeg(blur=True), "image/jpeg")},
                      data={"kind": "closure"}, headers=JE).json()
    assert not bad["quality"]["passed"]
    assert client.post(f"/findings/{f['id']}/close", json={"closure_evidence_id": bad["evidence"]["id"]}, headers=JE).status_code == 422
    good = client.post(f"/findings/{f['id']}/evidence", files={"image": ("d.jpg", _jpeg(), "image/jpeg")},
                       data={"kind": "closure"}, headers=JE).json()
    c = client.post(f"/findings/{f['id']}/close", json={"closure_evidence_id": good["evidence"]["id"]}, headers=JE)
    assert c.json()["status"] == "closed"
    book = client.post(f"/patrols/{pid}/end", headers=KEYMAN).json()
    assert book["count"] == 1 and book["findings"][0]["action_taken"] == "Recouped ERC"


def test_r6_audit_chain_valid(client):
    assert client.get("/audit/verify").json()["chain_valid"] is True
