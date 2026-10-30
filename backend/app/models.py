"""Persistence models (SQLModel). Four record layers are kept separate (Phase 1 report, Table 14.1):
raw observation (Evidence), automated interpretation (Finding.ai_*), human conclusion
(Finding.confirmed_*), authorised decision (Finding.severity/closure)."""
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(UTC)


def uid() -> str:
    return str(uuid4())


class PatrolType(str, Enum):
    keyman_daily = "PT-01"
    gang_rain = "PT-02"
    monsoon = "PT-03"
    hot_weather = "PT-04"
    cold_weather = "PT-05"
    mobile_watchman = "PT-06"
    stationary_watchman = "PT-07"
    security = "PT-08"
    je_foot = "PT-09"
    aden_foot = "PT-10"


class FindingStatus(str, Enum):
    draft = "draft"            # captured, not yet confirmed by inspector
    reported = "reported"      # inspector confirmed and submitted
    reviewed = "reviewed"      # supervisor validated, severity assigned
    rejected = "rejected"      # supervisor rejected (false report)
    closed = "closed"          # corrective action verified with evidence


class Patrol(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    patrol_type: PatrolType
    inspector_id: str
    role: str
    beat_from_km: str
    beat_to_km: str
    line: str = "UP"
    kit_check_ok: bool = False
    started_at: datetime = Field(default_factory=now)
    ended_at: datetime | None = None


class Finding(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    patrol_id: str = Field(foreign_key="patrol.id", index=True)
    class_id: str = Field(index=True)            # D02 taxonomy ID, chosen/confirmed by human
    km_reference: str
    line: str
    rail_side: str = "NA"
    lat: float | None = None
    lon: float | None = None
    gnss_accuracy_m: float | None = None
    note: str = ""
    note_language: str = "en"
    action_taken: str = ""
    # protection record (mandatory for protect-first classes)
    line_protected_at: datetime | None = None
    sm_informed_at: datetime | None = None
    # automated interpretation (never authoritative)
    ai_candidates_json: str = "[]"
    ai_model_version: str | None = None
    # human + authorised layers
    status: FindingStatus = FindingStatus.draft
    severity: str | None = None                  # set only by supervisor
    reviewed_by: str | None = None
    review_note: str = ""
    work_order_ref: str | None = None
    closed_by: str | None = None
    closure_evidence_id: str | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Evidence(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    finding_id: str = Field(foreign_key="finding.id", index=True)
    kind: str = "defect"                         # defect | context | closure | measurement
    path: str
    sha256: str
    width: int
    height: int
    quality_passed: bool
    quality_reasons: str = ""
    captured_at: datetime = Field(default_factory=now)


class AuditEvent(SQLModel, table=True):
    """Append-only hash chain: each event hashes the previous event's hash (tamper evidence)."""
    id: int | None = Field(default=None, primary_key=True)
    entity: str
    entity_id: str
    action: str
    actor: str
    payload_json: str
    prev_hash: str
    hash: str
    at: datetime = Field(default_factory=now)
