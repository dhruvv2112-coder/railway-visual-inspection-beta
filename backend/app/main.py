"""Beta API. Business rules encoded here (each has a test in tests/test_api.py):
R1 Only taxonomy classes enabled for Beta can be reported.
R2 Protect-first classes (RF-P1) cannot be reported without line-protection and SM-informed timestamps.
R3 AI output is stored as candidates only; it never sets class, severity or status.
R4 Only supervisors (JE/SSE/ADEN) can review, assign severity or close.
R5 Closure requires closure evidence that passed the quality gate (or a measurement record).
R6 Every state change is written to an append-only hash-chained audit log.
"""
import hashlib
import json
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from . import inference, quality, taxonomy
from .config import settings
from .db import audit, get_session, init_db, verify_chain
from .models import Evidence, Finding, FindingStatus, Patrol, PatrolType, now

SUPERVISOR_ROLES = {"JE", "SSE", "ADEN"}

app = FastAPI(title="RVI Beta API", version="0.1.0")


@app.on_event("startup")
def _startup():
    init_db()
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)


SessionDep = Annotated[Session, Depends(get_session)]


def actor(x_actor: Annotated[str, Header()] = "anon", x_role: Annotated[str, Header()] = "Keyman"):
    return {"id": x_actor, "role": x_role}


ActorDep = Annotated[dict, Depends(actor)]


def require_supervisor(a: dict):
    if a["role"] not in SUPERVISOR_ROLES:
        raise HTTPException(403, "Supervisor role (JE/SSE/ADEN) required")


@app.get("/health")
def health():
    return {"status": "ok", "detector_available": inference.available(), "taxonomy_version": taxonomy.load()["version"]}


@app.get("/taxonomy")
def get_taxonomy(lang: str = "en", beta_only: bool = True):
    t = taxonomy.load()
    out = []
    for c in t["classes"]:
        if beta_only and not c["beta_enabled"]:
            continue
        out.append({"id": c["id"], "label": c["label"].get(lang) or c["label"]["en"], "category": c["category"],
                    "asset": c["asset"], "focus_unit": c["focus_unit"], "protect_first": c["protect_first"],
                    "needs_measurement": c["needs_measurement"]})
    return {"version": t["version"], "classes": out}


class PatrolIn(BaseModel):
    patrol_type: PatrolType
    beat_from_km: str
    beat_to_km: str
    line: str = "UP"
    kit_check_ok: bool


@app.post("/patrols", status_code=201)
def start_patrol(body: PatrolIn, s: SessionDep, a: ActorDep):
    p = Patrol(**body.model_dump(), inspector_id=a["id"], role=a["role"])
    s.add(p)
    audit(s, "patrol", p.id, "start", a["id"], body.model_dump())
    s.commit()
    s.refresh(p)
    return p


class FindingIn(BaseModel):
    patrol_id: str
    class_id: str
    km_reference: str
    line: str
    rail_side: str = "NA"
    lat: float | None = None
    lon: float | None = None
    gnss_accuracy_m: float | None = None
    note: str = ""
    note_language: str = "en"
    action_taken: str = ""
    line_protected_at: datetime | None = None
    sm_informed_at: datetime | None = None
    submit: bool = True


@app.post("/findings", status_code=201)
def create_finding(body: FindingIn, s: SessionDep, a: ActorDep):
    c = taxonomy.get(body.class_id)
    if not c or not c["beta_enabled"]:
        raise HTTPException(422, f"Class {body.class_id} not enabled for Beta")  # R1
    if not s.get(Patrol, body.patrol_id):
        raise HTTPException(404, "Patrol not found")
    if c["protect_first"] and (body.line_protected_at is None or body.sm_informed_at is None):
        raise HTTPException(422, "Protect-first class: record line protection and SM notification first")  # R2
    data = body.model_dump(exclude={"submit"})
    f = Finding(**data, status=FindingStatus.reported if body.submit else FindingStatus.draft)
    s.add(f)
    audit(s, "finding", f.id, "create", a["id"], data)
    s.commit()
    s.refresh(f)
    return f


@app.post("/findings/{fid}/evidence", status_code=201)
async def add_evidence(fid: str, s: SessionDep, a: ActorDep, image: UploadFile = File(...), kind: str = Form("defect")):
    f = s.get(Finding, fid)
    if not f:
        raise HTTPException(404, "Finding not found")
    data = await image.read()
    img = quality.decode(data)
    q = quality.assess(img)
    sha = hashlib.sha256(data).hexdigest()
    path = settings.evidence_dir / f"{sha}.jpg"
    path.write_bytes(data)
    ev = Evidence(finding_id=fid, kind=kind, path=str(path), sha256=sha, width=q.width, height=q.height,
                  quality_passed=q.passed, quality_reasons=",".join(q.reasons))
    s.add(ev)
    cands = []
    if kind == "defect" and q.passed and inference.available():  # R3: stored as candidates only
        cands = [c.__dict__ for c in inference.detect(img)]
        f.ai_candidates_json = json.dumps(cands)
        f.ai_model_version = str(settings.detector_onnx.name)
    audit(s, "evidence", ev.id, "add", a["id"], {"finding": fid, "kind": kind, "sha256": sha, "quality": q.reasons})
    s.commit()
    s.refresh(ev)
    return {"evidence": ev, "quality": {"passed": q.passed, "reasons": q.reasons, "sharpness": q.sharpness,
                                        "brightness": q.brightness}, "ai_candidates": cands}


class ReviewIn(BaseModel):
    accept: bool
    severity: str | None = None
    review_note: str = ""
    work_order_ref: str | None = None


@app.post("/findings/{fid}/review")
def review(fid: str, body: ReviewIn, s: SessionDep, a: ActorDep):
    require_supervisor(a)  # R4
    f = s.get(Finding, fid)
    if not f:
        raise HTTPException(404, "Finding not found")
    if body.accept and not body.severity:
        raise HTTPException(422, "Severity must be assigned by the reviewer")
    f.status = FindingStatus.reviewed if body.accept else FindingStatus.rejected
    f.severity, f.review_note, f.work_order_ref, f.reviewed_by = body.severity, body.review_note, body.work_order_ref, a["id"]
    f.updated_at = now()
    audit(s, "finding", fid, "review", a["id"], body.model_dump())
    s.commit()
    s.refresh(f)
    return f


class CloseIn(BaseModel):
    closure_evidence_id: str


@app.post("/findings/{fid}/close")
def close(fid: str, body: CloseIn, s: SessionDep, a: ActorDep):
    require_supervisor(a)
    f = s.get(Finding, fid)
    if not f or f.status != FindingStatus.reviewed:
        raise HTTPException(409, "Only reviewed findings can be closed")
    ev = s.get(Evidence, body.closure_evidence_id)
    if not ev or ev.finding_id != fid or ev.kind not in {"closure", "measurement"} or (ev.kind == "closure" and not ev.quality_passed):
        raise HTTPException(422, "Closure needs closure evidence of this finding that passed the quality gate")  # R5
    f.status, f.closed_by, f.closure_evidence_id, f.updated_at = FindingStatus.closed, a["id"], ev.id, now()
    audit(s, "finding", fid, "close", a["id"], body.model_dump())
    s.commit()
    s.refresh(f)
    return f


@app.post("/patrols/{pid}/end")
def end_patrol(pid: str, s: SessionDep, a: ActorDep):
    p = s.get(Patrol, pid)
    if not p:
        raise HTTPException(404, "Patrol not found")
    p.ended_at = now()
    audit(s, "patrol", pid, "end", a["id"], {})
    s.commit()
    return keyman_book(pid, s)


@app.get("/patrols/{pid}/report")
def keyman_book(pid: str, s: SessionDep, lang: str = "en"):
    """Auto-compiled keyman-book style summary (CAMTECH 2021, B17 fields)."""
    p = s.get(Patrol, pid)
    if not p:
        raise HTTPException(404, "Patrol not found")
    fs = s.exec(select(Finding).where(Finding.patrol_id == pid)).all()
    rows = []
    for f in fs:
        c = taxonomy.get(f.class_id)
        rows.append({"km": f.km_reference, "line": f.line, "rail": f.rail_side,
                     "defect": c["label"].get(lang) or c["label"]["en"], "class_id": f.class_id,
                     "action_taken": f.action_taken, "status": f.status, "protected": f.line_protected_at is not None})
    return {"patrol": p, "findings": rows, "count": len(rows),
            "protect_first_count": sum(r["protected"] for r in rows)}


@app.get("/audit/verify")
def audit_verify(s: SessionDep):
    return {"chain_valid": verify_chain(s)}
