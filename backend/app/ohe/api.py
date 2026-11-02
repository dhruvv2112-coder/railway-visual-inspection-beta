"""OHE patrol API (HLD §9.3, §10): sessions, media ingest with checksum + idempotency, cascade processing,
findings, end-of-cycle reconciliation, immutable report revisions, signing, and an isolated notes channel."""
from __future__ import annotations

import hashlib
import html
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, select

from .. import quality
from ..config import settings
from ..db import audit, get_session
from ..models import now
from . import auth, pipeline

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
        try:
            cls.ocr = pipeline.RapidOcrAdapter()
        except ImportError:  # optional dependency (installed in the server image)
            cls.ocr = pipeline.NullOCR()


actor = auth.actor  # bearer token, or X-Actor/X-Role headers in development (settings.auth_mode)


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
async def ingest(sid: str, s: SessionDep, a: ActorDep, bg: BackgroundTasks, image: Annotated[UploadFile, File()],
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
    try:
        new_alerts = process(m, s)
    except Exception as e:  # noqa: BLE001 - any model/runtime failure: keep the evidence, report it truthfully (HLD V08)
        new_alerts = []
        m.status = "failed"
        m.analysis_json = json.dumps({"error": f"{type(e).__name__}: {str(e)[:300]}", "assessments": []})
        audit(s, "ohe_media", m.id, "processing.failed", "system", {"error": type(e).__name__})
    s.commit()
    s.refresh(m)
    for f in new_alerts:
        bg.add_task(_push_alert, {"finding": f.id, "session": sid, "territory": sess.territory, "asset_id": f.asset_id,
                                  "assessment": json.loads(f.payload_json)})
    return {"media": m, "analysis": json.loads(m.analysis_json), "idempotent": False}


def _push_alert(payload: dict) -> None:
    """Urgent finding raised the moment it is seen, before any report is signed (HLD §8.4). Optional webhook;
    the alert feed (/ohe/alerts) always has it."""
    if not settings.alert_webhook:
        return
    import urllib.request
    try:
        req = urllib.request.Request(settings.alert_webhook, data=json.dumps(payload, default=str).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except (OSError, ValueError) as e:  # never block ingest on a notification
        print("alert webhook failed:", e)


def process(m: OheMedia, s: Session) -> list:
    """Run the cascade for one media item and link results to findings (repeat evidence never duplicates)."""
    reg = pipeline.load_registry()
    img = quality.decode(Path(m.path).read_bytes())
    res = pipeline.assess_image(img, reg, Models.detector, Models.ocr, Models.anomaly, m.lat, m.lon, m.accuracy_m)
    if res["identity"]["selected_asset_id"] and m.lat is None:
        m.location_source = "registry_inherited"
    res["assessments"] = [pipeline.decide(o, res["identity"], res["quality"]["passed"], reg) for o in res["observations"]]
    m.analysis_json = json.dumps(res, default=str)
    m.status = "assessed"
    new_alerts = []
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
                new_alerts.append(f)
        s.add(f)
    return new_alerts


@router.get("/sessions/{sid}/processing")
def processing(sid: str, s: SessionDep, a: ActorDep):
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


def esc(v) -> str:
    return html.escape(str(v))


def _an(m) -> dict:
    return json.loads(m.analysis_json or "{}")


def _reconcile(sess: OheSession, s: Session) -> dict:
    """Cycle ledger: every expected asset gets a state; unlocated findings and failed media stay visible (HLD §10)."""
    media = s.exec(select(OheMedia).where(OheMedia.session_id == sess.id)).all()
    fs = s.exec(select(OheFinding).where(OheFinding.session_id == sess.id)).all()
    notes = s.exec(select(OheNote).where(OheNote.session_id == sess.id)).all()  # report annex only (RPT-12), never inspection
    reg_version = pipeline.load_registry()["version"]
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
        "RPT-03_coverage": {
            "registry_version": reg_version,
            "statement": "Capture locations and associations below show where photos were taken and which masts they were "
                         "linked to. A walked route is not verified inspection coverage.",
            "captures": [{"media_id": m.id, "lat": m.lat, "lon": m.lon, "accuracy_m": m.accuracy_m,
                          "location_source": m.location_source, "asset_id": (_an(m).get("identity") or {}).get("selected_asset_id"),
                          "identity_state": (_an(m).get("identity") or {}).get("state")} for m in media],
            "ambiguous_captures": [m.id for m in media if m.status == "assessed"
                                   and not (_an(m).get("identity") or {}).get("selected_asset_id")],
            "evidence_gaps": [r["asset_id"] for r in register if r["state"] == "no_evidence"]},
        "RPT-04_special_attention": [f for f in findings if f["alert"]],
        "RPT-05_asset_register": register,
        "RPT-06_findings": findings,
        "RPT-07_temporal": {"state": "not_comparable",
                            "statement": "Comparison with earlier cycles is not part of this release (HLD Release C). "
                                         "No change, improvement or deterioration is claimed."},
        "RPT-08_actions": [{"finding": f["id"], "primary": f.get("routing", {}).get("primary", "OHE coordination queue"),
                            "contributors": f.get("routing", {}).get("contributors", []), "action_family": f.get("action_family"),
                            "urgency_basis": f.get("rule_id"), "action": f.get("recommendation"),
                            "status": "suggested – not adopted until the authorised organisation assigns it"} for f in findings],
        "RPT-09_limitations": ["Visual-only inspection: no electrical, thermal, tension or dimensional claims",
                               "Model scores are uncalibrated until a calibration set is fitted",
                               *[f"Finding {f['id']} not associated to a single asset" for f in findings if f["asset_id"] is None],
                               *[f"Photo {m.id} could not be processed ({_an(m).get('error', 'error')}); evidence kept, "
                                 "its masts are not assessed from it" for m in media if m.status == "failed"],
                               *[f"Mast {r['asset_id']}: design or part not supported by the current models" for r in register
                                 if r["state"] == "unsupported_class"]],
        "RPT-10_provenance": {"models": sorted({json.dumps(json.loads(m.analysis_json).get("model_versions", {}), sort_keys=True)
                                                for m in media}), "registry": pipeline.load_registry()["version"]},
        **({"RPT-12_notes": {"statement": "Transcribed or typed notes from the patrol. They were not used by the AI inspection.",
                             "notes": [{"at": n.created_at, "author": n.author, "text": n.text} for n in notes]}} if notes else {}),
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
def get_report(rid: str, s: SessionDep, a: ActorDep):
    r = s.get(OheReport, rid)
    if not r:
        raise HTTPException(404, "Report not found")
    return {"id": r.id, "revision": r.revision, "status": r.status, "sha256": r.sha256, "signed_by": r.signed_by,
            "content": json.loads(r.content_json), "RPT-11_review": _review_record(r, s)}


def _review_record(r: OheReport, s: Session) -> dict:
    """RPT-11: who reviewed, amended and signed, and the checksum of the frozen revision that was signed."""
    chain, cur = [], r
    while cur is not None:
        chain.append({"report_id": cur.id, "revision": cur.revision, "status": cur.status, "sha256": cur.sha256})
        cur = s.get(OheReport, cur.supersedes) if cur.supersedes else None
    amendments = [a | {"finding": f["id"]} for f in json.loads(r.content_json).get("RPT-06_findings", [])
                  for a in f.get("amendments", [])]
    return {"signer": r.signed_by, "signed_at": r.signed_at, "signature_mechanism": "signed-in role check; SHA-256 of the frozen revision",
            "report_checksum": r.sha256, "amendments": amendments, "revisions": chain[::-1]}


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
def report_html(rid: str, s: SessionDep, a: ActorDep):
    """Deterministic render from the frozen revision; no AI at export time (HLD §10.4). Print to PDF from here."""
    r = s.get(OheReport, rid)
    if not r:
        raise HTTPException(404, "Report not found")
    c = json.loads(r.content_json)
    row = lambda *v: "<tr>" + "".join(f"<td>{esc(x)}</td>" for x in v) + "</tr>"
    reg = "".join(row(x["asset_id"], x["state"].replace("_", " "), len(x["findings"])) for x in c["RPT-05_asset_register"])
    fnd = "".join(row(f["id"], f["asset_id"] or "unresolved: " + ", ".join(x["asset_id"] for x in f["candidates"][:3]),
                      f.get("observed_feature", f["state"]), f.get("priority", "review"), f.get("routing", {}).get("primary", ""))
                  for f in c["RPT-06_findings"])
    css = ("body{font-family:Montserrat,Arial,sans-serif;color:#222;background:#fff;margin:24px}table{border-collapse:collapse;"
           "width:100%;font-size:12px}td,th{border:1px solid #bbb;padding:4px 6px;text-align:left}h1{font-size:20px}")
    sm = c["RPT-02_summary"]
    cov = c.get("RPT-03_coverage", {})
    act = "".join(row(a["finding"], a["primary"], a.get("action") or "", a["status"]) for a in c["RPT-08_actions"])
    nt = c.get("RPT-12_notes")
    notes = ("<h2>Patrol notes (not used by the AI inspection)</h2><ul>"
             + "".join(f"<li>{esc(n['at'])} · {esc(n['author'])}: {esc(n['text'])}</li>" for n in nt["notes"]) + "</ul>") if nt else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>OHE patrol report {r.id}</title><style>{css}</style></head><body>"
            f"<h1>OHE visual patrol report · revision {r.revision} · {r.status}</h1><p>Session {c['RPT-01_document_control']['session']}"
            f" · territory {esc(c['RPT-01_document_control']['territory'])} · SHA-256 {r.sha256}</p>"
            f"<h2>Summary</h2><table>{''.join(row(k.replace('_', ' '), v) for k, v in sm.items())}</table>"
            f"<h2>Asset register</h2><table><tr><th>Asset</th><th>State</th><th>Findings</th></tr>{reg}</table>"
            f"<h2>Findings</h2><table><tr><th>ID</th><th>Asset</th><th>Observed</th><th>Priority</th><th>Route</th></tr>{fnd}</table>"
            f"<h2>Coverage</h2><p>{esc(cov.get('statement', ''))}</p><p>Photos: {len(cov.get('captures', []))} · not linked to one mast: "
            f"{len(cov.get('ambiguous_captures', []))} · masts with no photo: {esc(', '.join(cov.get('evidence_gaps', [])) or 'none')}"
            f" · registry {esc(cov.get('registry_version', ''))}</p>"
            f"<h2>Suggested actions</h2><table><tr><th>Finding</th><th>Primary</th><th>Action</th><th>Status</th></tr>{act}</table>"
            f"<h2>Comparison with earlier cycles</h2><p>{esc(c.get('RPT-07_temporal', {}).get('statement', ''))}</p>"
            f"<h2>Limitations</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in c['RPT-09_limitations'])}</ul>"
            f"<h2>Review and authorisation</h2><p>Signed by {esc(r.signed_by or '—')} at {esc(r.signed_at or '—')} · "
            f"checksum {r.sha256}</p>{notes}</body></html>")


# ---- sign-in, reviewer lists, evidence images and the reviewer web page --------------------------------------------

class LoginIn(BaseModel):
    id: str
    pin: str


@router.post("/auth/login")
def login(body: LoginIn):
    return auth.login(body.id.strip(), body.pin.strip())


@router.get("/me")
def me(a: ActorDep):
    return a | {"can_sign": a["role"] in SIGNER_ROLES}


@router.get("/reports")
def list_reports(s: SessionDep, a: ActorDep, limit: int = 100):
    """Latest revision per patrol, newest first, with the summary counts a reviewer sorts by."""
    out = {}
    for r in s.exec(select(OheReport).order_by(OheReport.revision.desc())).all():
        out.setdefault(r.session_id, r)
    rows = []
    for r in out.values():
        sess = s.get(OheSession, r.session_id)
        c = json.loads(r.content_json)
        rows.append({"id": r.id, "session": r.session_id, "territory": sess.territory if sess else "", "revision": r.revision,
                     "status": r.status, "signed_by": r.signed_by, "started_at": sess.started_at if sess else None,
                     "ended_at": sess.ended_at if sess else None, "summary": c.get("RPT-02_summary", {}),
                     "created_by": sess.created_by if sess else ""})
    rows.sort(key=lambda x: str(x["ended_at"] or ""), reverse=True)
    return rows[:limit]


@router.get("/alerts")
def alerts(s: SessionDep, a: ActorDep, limit: int = 50):
    """Urgent findings as raised, newest first (does not wait for the report to be signed)."""
    fs = s.exec(select(OheFinding).where(OheFinding.alert)).all()
    rows = []
    for f in fs:
        sess = s.get(OheSession, f.session_id)
        rows.append({"finding": f.id, "session": f.session_id, "territory": sess.territory if sess else "", "asset_id": f.asset_id,
                     "candidates": json.loads(f.candidates_json)[:3], "observations": f.observations,
                     "media_ids": json.loads(f.media_ids_json), "assessment": json.loads(f.payload_json),
                     "raised_at": sess.started_at if sess else None})
    return rows[::-1][:limit]


@router.get("/media/{mid}")
def media_info(mid: str, s: SessionDep, a: ActorDep):
    m = s.get(OheMedia, mid)
    if not m:
        raise HTTPException(404, "Photo not found")
    an = json.loads(m.analysis_json)
    return {"id": m.id, "sha256": m.sha256, "captured_at": m.captured_at, "lat": m.lat, "lon": m.lon,
            "location_source": m.location_source, "status": m.status, "identity": an.get("identity"),
            "assessments": an.get("assessments", []), "quality": an.get("quality"), "image_state": an.get("image_state")}


@router.post("/media/{mid}/reprocess")
def reprocess(mid: str, s: SessionDep, a: ActorDep):
    """Retry a photo whose processing failed (HLD V08). Evidence bytes are unchanged."""
    m = s.get(OheMedia, mid)
    if not m:
        raise HTTPException(404, "Photo not found")
    if m.status != "failed":
        raise HTTPException(409, "Photo is already processed")
    try:
        process(m, s)
    except Exception as e:  # still failing: stay visible as failed
        m.analysis_json = json.dumps({"error": f"{type(e).__name__}: {str(e)[:300]}", "assessments": []})
        s.commit()
        raise HTTPException(503, "Processing still failing; try again later") from e
    audit(s, "ohe_media", m.id, "processing.retried", a["id"], {})
    s.commit()
    return {"id": m.id, "status": m.status, "analysis": _an(m)}


@router.get("/media/{mid}/image")
def media_image(mid: str, s: SessionDep, a: ActorDep):
    m = s.get(OheMedia, mid)
    if not m or not Path(m.path).exists():
        raise HTTPException(404, "Photo not found")
    return FileResponse(m.path, media_type="image/jpeg")


@router.get("/review", response_class=HTMLResponse, include_in_schema=False)
def review_page():
    return (Path(__file__).parent / "static" / "review.html").read_text(encoding="utf-8")
