"""OHE patrol API (HLD §9.3, §10): sessions, media ingest with checksum + idempotency, cascade processing,
findings, end-of-cycle reconciliation, immutable report revisions, signing, and an isolated notes channel."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, select

from .. import quality
from ..config import settings
from ..db import audit, get_session
from ..models import now
from . import pipeline

router = APIRouter(prefix="/ohe", tags=["ohe"])
SessionDep = Annotated[Session, Depends(get_session)]
SIGNER_ROLES = {"SSE", "ADEE", "DEE", "SrDEE"}


def _id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- records (HLD §9.1)
class OheSession(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    territory: str
    expected_assets_json: str = "[]"
    started_at: datetime = Field(default_factory=now)
    ended_at: datetime | None = None
    created_by: str = ""


class OheMedia(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    session_id: str = Field(index=True)
    sha256: str = Field(index=True)
    captured_at: datetime
    uploaded_at: datetime = Field(default_factory=now)
    lat: float | None = None
    lon: float | None = None
    accuracy_m: float | None = None
    location_source: str = "capture"      # capture | registry_inherited | none
    device: str = ""
    path: str = ""
    analysis_json: str = "{}"             # model run outputs, versions included
    status: str = "persisted"             # persisted | assessed | failed


class OheFinding(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    session_id: str = Field(index=True)
    key: str = Field(index=True)          # asset-or-candidates + component + condition: repeat evidence links here
    asset_id: str | None = None
    candidates_json: str = "[]"
    payload_json: str                     # assessment (claims, confidence vector, routing)
    media_ids_json: str = "[]"
    observations: int = 1
    alert: bool = False
    created_at: datetime = Field(default_factory=now)


class OheReport(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    session_id: str = Field(index=True)
    revision: int
    status: str = "READY_FOR_REVIEW"      # DRAFT_PROCESSING | READY_FOR_REVIEW | AUTHORISED_SIGNED | SUPERSEDED
    content_json: str
    sha256: str
    signed_by: str | None = None
    signed_at: datetime | None = None
    supersedes: str | None = None


class OheNote(SQLModel, table=True):
    """Isolated notes channel (HLD I-06). Nothing in the pipeline reads this table."""
    id: str = Field(default_factory=_id, primary_key=True)
    session_id: str = Field(index=True)
    text: str
    author: str
    created_at: datetime = Field(default_factory=now)


# ---------------------------------------------------------------- model wiring (replaceable, HLD §6.4)
class Models:
    detector: pipeline.Detector = pipeline.NullDetector()
    ocr: pipeline.OCR = pipeline.NullOCR()
    anomaly = None

    @classmethod
    def load(cls):
        p = settings.model_dir / "ohe_detector.onnx"
        names = settings.model_dir / "ohe_detector.names.json"
        if p.exists() and names.exists():
            cls.detector = pipeline.OnnxYoloDetector(str(p), json.loads(names.read_text()))


def actor(x_actor: Annotated[str, Header()] = "anon", x_role: Annotated[str, Header()] = "Patrol"):
    return {"id": x_actor, "role": x_role}


ActorDep = Annotated[dict, Depends(actor)]


# ---------------------------------------------------------------- endpoints
class SessionIn(BaseModel):
    territory: str
    expected_assets: list[str] | None = None


@router.post("/sessions", status_code=201)
def start(body: SessionIn, s: SessionDep, a: ActorDep):
    reg = pipeline.load_registry()
    exp = body.expected_assets or [x["id"] for x in reg["assets"]]
    o = OheSession(territory=body.territory, expected_assets_json=json.dumps(exp), created_by=a["id"])
    s.add(o)
    audit(s, "ohe_session", o.id, "start", a["id"], {"territory": body.territory, "expected": exp})
    s.commit()
    s.refresh(o)
    return o


def _finding_key(ident: dict, a: dict) -> str:
    where = ident["selected_asset_id"] or "cand:" + ",".join(c["asset_id"] for c in ident["candidates"][:3])
    return f"{where}|{a['component']}|{a['condition']}"


@router.post("/sessions/{sid}/media", status_code=201)
async def ingest(sid: str, s: SessionDep, a: ActorDep, image: Annotated[UploadFile, File()],
                 sha256: Annotated[str, Form()], captured_at: Annotated[datetime, Form()],
                 lat: Annotated[float | None, Form()] = None, lon: Annotated[float | None, Form()] = None,
                 accuracy_m: Annotated[float | None, Form()] = None, device: Annotated[str, Form()] = ""):
    sess = s.get(OheSession, sid)
    if not sess or sess.ended_at:
        raise HTTPException(409, "Session not open")
    data = await image.read()
    if hashlib.sha256(data).hexdigest() != sha256.lower():
        raise HTTPException(422, "Checksum mismatch – media not persisted")          # HLD §4.2, V07
    dup = s.exec(select(OheMedia).where(OheMedia.session_id == sid, OheMedia.sha256 == sha256.lower())).first()
    if dup:
        return {"media": dup, "idempotent": True}
    d = settings.evidence_dir / "ohe"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{sha256.lower()}.jpg"
    path.write_bytes(data)
    m = OheMedia(session_id=sid, sha256=sha256.lower(), captured_at=captured_at, lat=lat, lon=lon, accuracy_m=accuracy_m,
                 location_source="capture" if lat is not None else "none", device=device, path=str(path))
    s.add(m)
    audit(s, "ohe_media", m.id, "persisted", a["id"], {"sha256": m.sha256})
    process(m, s)
    s.commit()
    s.refresh(m)
    return {"media": m, "analysis": json.loads(m.analysis_json), "idempotent": False}


def process(m: OheMedia, s: Session) -> None:
    """Run the cascade for one media item and link results to findings (repeat evidence never duplicates)."""
    reg = pipeline.load_registry()
    img = quality.decode(Path(m.path).read_bytes())
    res = pipeline.assess_image(img, reg, Models.detector, Models.ocr, Models.anomaly, m.lat, m.lon, m.accuracy_m)
    if res["identity"]["selected_asset_id"] and m.lat is None:
        m.location_source = "registry_inherited"
    res["assessments"] = [pipeline.decide(o, res["identity"], res["quality"]["passed"], reg) for o in res["observations"]]
    m.analysis_json = json.dumps(res, default=str)
    m.status = "assessed"
    for asm in res["assessments"]:
        if asm["state"] not in ("assessable_defect", "anomalous_unclassified"):
            continue
        key = _finding_key(res["identity"], asm)
        f = s.exec(select(OheFinding).where(OheFinding.session_id == m.session_id, OheFinding.key == key)).first()
        if f:
            f.observations += 1
            f.media_ids_json = json.dumps(json.loads(f.media_ids_json) + [m.id])
        else:
            f = OheFinding(session_id=m.session_id, key=key, asset_id=res["identity"]["selected_asset_id"],
                           candidates_json=json.dumps(res["identity"]["candidates"]), payload_json=json.dumps(asm),
                           media_ids_json=json.dumps([m.id]), alert=asm.get("alert", False))
            if f.alert:
                audit(s, "ohe_finding", f.id, "concern.flagged", "system", {"key": key})  # immediate, before signing
        s.add(f)


@router.get("/sessions/{sid}/processing")
def processing(sid: str, s: SessionDep):
    media = s.exec(select(OheMedia).where(OheMedia.session_id == sid)).all()
    fs = s.exec(select(OheFinding).where(OheFinding.session_id == sid)).all()
    return {"media": [{"id": m.id, "status": m.status, "analysis": json.loads(m.analysis_json)} for m in media],
            "findings": [{"id": f.id, "asset_id": f.asset_id, "observations": f.observations, "alert": f.alert,
                          "assessment": json.loads(f.payload_json)} for f in fs]}


@router.post("/sessions/{sid}/notes", status_code=201)
def add_note(sid: str, body: dict, s: SessionDep, a: ActorDep):
    n = OheNote(session_id=sid, text=str(body.get("text", "")), author=a["id"])
    s.add(n)
    s.commit()
    return {"id": n.id}


def _reconcile(sess: OheSession, s: Session) -> dict:
    """Cycle ledger: every expected asset gets a state; unlocated findings and failed media stay visible (HLD §10)."""
    media = s.exec(select(OheMedia).where(OheMedia.session_id == sess.id)).all()
    fs = s.exec(select(OheFinding).where(OheFinding.session_id == sess.id)).all()
    per_asset: dict[str, set] = {}
    for m in media:
        an = json.loads(m.analysis_json)
        aid = an.get("identity", {}).get("selected_asset_id")
        if aid:
            states = {x["state"] for x in an.get("assessments", [])} or {an.get("image_state") or "occluded_or_missing_view"}
            per_asset.setdefault(aid, set()).update(states)
    order = ["assessable_defect", "anomalous_unclassified", "insufficient_resolution", "occluded_or_missing_view",
             "unsupported_class", "assessable_no_visible_defect", "no_evidence"]
    register = []
    for aid in json.loads(sess.expected_assets_json):
        st = per_asset.get(aid, set())
        state = next((x for x in order if x in st), "no_evidence")
        register.append({"asset_id": aid, "state": state,
                         "findings": [f.id for f in fs if f.asset_id == aid]})
    findings = [{"id": f.id, "asset_id": f.asset_id, "candidates": json.loads(f.candidates_json),
                 "observations": f.observations, "alert": f.alert, "media_ids": json.loads(f.media_ids_json),
                 **json.loads(f.payload_json)} for f in fs]
    count = lambda st: sum(r["state"] == st for r in register)
    return {
        "RPT-01_document_control": {"session": sess.id, "territory": sess.territory, "capture_start": sess.started_at,
                                    "capture_end": sess.ended_at, "timezone": "UTC"},
        "RPT-02_summary": {"expected_assets": len(register), "evidenced_assets": sum(r["state"] != "no_evidence" for r in register),
                           "no_visible_defect": count("assessable_no_visible_defect"), "with_findings": count("assessable_defect"),
                           "not_assessable": count("insufficient_resolution") + count("occluded_or_missing_view"),
                           "unlocated_findings": sum(f["asset_id"] is None for f in findings),
                           "alerts": sum(f["alert"] for f in findings), "media": len(media),
                           "failed_media": sum(m.status == "failed" for m in media)},
        "RPT-04_special_attention": [f for f in findings if f["alert"]],
        "RPT-05_asset_register": register,
        "RPT-06_findings": findings,
        "RPT-08_actions": [{"finding": f["id"], "primary": f.get("routing", {}).get("primary", "OHE coordination queue"),
                            "contributors": f.get("routing", {}).get("contributors", []),
                            "action": f.get("recommendation"), "status": "suggested"} for f in findings],
        "RPT-09_limitations": ["Visual-only inspection: no electrical, thermal, tension or dimensional claims",
                               "Model scores are uncalibrated until a calibration set is fitted",
                               *[f"Finding {f['id']} not associated to a single asset" for f in findings if f["asset_id"] is None]],
        "RPT-10_provenance": {"models": sorted({json.dumps(json.loads(m.analysis_json).get("model_versions", {}), sort_keys=True)
                                                for m in media}), "registry": pipeline.load_registry()["version"]},
        "RPT-13_evidence_manifest": [{"media_id": m.id, "sha256": m.sha256, "captured_at": m.captured_at,
                                      "location_source": m.location_source} for m in media],
    }


def _hash(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


@router.post("/sessions/{sid}/end")
def end(sid: str, s: SessionDep, a: ActorDep):
    sess = s.get(OheSession, sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    sess.ended_at = sess.ended_at or now()
    content = _reconcile(sess, s)
    r = OheReport(session_id=sid, revision=1, content_json=json.dumps(content, default=str), sha256=_hash(content))
    s.add(r)
    audit(s, "ohe_report", r.id, "report.ready_for_review", a["id"], {"sha256": r.sha256})
    s.commit()
    s.refresh(r)
    return {"report_id": r.id, "revision": r.revision, "sha256": r.sha256, "summary": content["RPT-02_summary"]}


@router.get("/reports/{rid}")
def get_report(rid: str, s: SessionDep):
    r = s.get(OheReport, rid)
    if not r:
        raise HTTPException(404, "Report not found")
    return {"id": r.id, "revision": r.revision, "status": r.status, "sha256": r.sha256, "signed_by": r.signed_by,
            "content": json.loads(r.content_json)}


@router.post("/reports/{rid}/sign")
def sign(rid: str, s: SessionDep, a: ActorDep):
    r = s.get(OheReport, rid)
    if not r:
        raise HTTPException(404, "Report not found")
    if a["role"] not in SIGNER_ROLES:
        raise HTTPException(403, "Authorised signer role required")
    if r.status != "READY_FOR_REVIEW":
        raise HTTPException(409, f"Report is {r.status}")
    r.status, r.signed_by, r.signed_at = "AUTHORISED_SIGNED", a["id"], now()
    audit(s, "ohe_report", r.id, "report.signed", a["id"], {"sha256": r.sha256})
    s.commit()
    return {"id": r.id, "status": r.status, "sha256": r.sha256}


class Amendment(BaseModel):
    finding_id: str
    field: str
    new_value: str
    reason: str


@router.post("/reports/{rid}/amend")
def amend(rid: str, body: Amendment, s: SessionDep, a: ActorDep):
    """Any change creates a new revision; a signed revision is never edited (HLD §10.1, V11)."""
    r = s.get(OheReport, rid)
    if not r:
        raise HTTPException(404, "Report not found")
    content = json.loads(r.content_json)
    for f in content["RPT-06_findings"]:
        if f["id"] == body.finding_id:
            f.setdefault("amendments", []).append({"field": body.field, "old": f.get(body.field), "new": body.new_value,
                                                   "reason": body.reason, "by": a["id"]})
            f[body.field] = body.new_value
    new = OheReport(session_id=r.session_id, revision=r.revision + 1, content_json=json.dumps(content, default=str),
                    sha256=_hash(content), supersedes=r.id)
    if r.status == "READY_FOR_REVIEW":
        r.status = "SUPERSEDED"
    s.add(new)
    audit(s, "ohe_report", new.id, "report.amended", a["id"], body.model_dump())
    s.commit()
    s.refresh(new)
    return {"report_id": new.id, "revision": new.revision, "status": new.status, "supersedes": r.id}


@router.get("/reports/{rid}/html", response_class=HTMLResponse)
def report_html(rid: str, s: SessionDep):
    """Deterministic render from the frozen revision; no AI at export time (HLD §10.4). Print to PDF from here."""
    r = s.get(OheReport, rid)
    if not r:
        raise HTTPException(404, "Report not found")
    c = json.loads(r.content_json)
    row = lambda *v: "<tr>" + "".join(f"<td>{x}</td>" for x in v) + "</tr>"
    reg = "".join(row(x["asset_id"], x["state"].replace("_", " "), len(x["findings"])) for x in c["RPT-05_asset_register"])
    fnd = "".join(row(f["id"], f["asset_id"] or "unresolved: " + ", ".join(x["asset_id"] for x in f["candidates"][:3]),
                      f.get("observed_feature", f["state"]), f.get("priority", "review"), f.get("routing", {}).get("primary", ""))
                  for f in c["RPT-06_findings"])
    css = ("body{font-family:Montserrat,Arial,sans-serif;color:#222;background:#fff;margin:24px}table{border-collapse:collapse;"
           "width:100%;font-size:12px}td,th{border:1px solid #bbb;padding:4px 6px;text-align:left}h1{font-size:20px}")
    sm = c["RPT-02_summary"]
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>OHE patrol report {r.id}</title><style>{css}</style></head><body>"
            f"<h1>OHE visual patrol report · revision {r.revision} · {r.status}</h1><p>Session {c['RPT-01_document_control']['session']}"
            f" · territory {c['RPT-01_document_control']['territory']} · SHA-256 {r.sha256}</p>"
            f"<h2>Summary</h2><table>{''.join(row(k.replace('_', ' '), v) for k, v in sm.items())}</table>"
            f"<h2>Asset register</h2><table><tr><th>Asset</th><th>State</th><th>Findings</th></tr>{reg}</table>"
            f"<h2>Findings</h2><table><tr><th>ID</th><th>Asset</th><th>Observed</th><th>Priority</th><th>Route</th></tr>{fnd}</table>"
            f"<h2>Limitations</h2><ul>{''.join(f'<li>{x}</li>' for x in c['RPT-09_limitations'])}</ul></body></html>")
