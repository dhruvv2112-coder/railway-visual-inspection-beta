import hashlib
import json

from sqlmodel import Session, SQLModel, create_engine, select

from .config import settings
from .models import AuditEvent

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False}
                       if settings.database_url.startswith("sqlite") else {})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def audit(session: Session, entity: str, entity_id: str, action: str, actor: str, payload: dict) -> AuditEvent:
    last = session.exec(select(AuditEvent).order_by(AuditEvent.id.desc())).first()
    prev = last.hash if last else "GENESIS"
    body = json.dumps({"entity": entity, "id": entity_id, "action": action, "actor": actor,
                       "payload": payload, "prev": prev}, sort_keys=True, default=str)
    ev = AuditEvent(entity=entity, entity_id=entity_id, action=action, actor=actor,
                    payload_json=json.dumps(payload, default=str), prev_hash=prev,
                    hash=hashlib.sha256(body.encode()).hexdigest())
    session.add(ev)
    return ev


def verify_chain(session: Session) -> bool:
    prev = "GENESIS"
    for ev in session.exec(select(AuditEvent).order_by(AuditEvent.id)).all():
        body = json.dumps({"entity": ev.entity, "id": ev.entity_id, "action": ev.action, "actor": ev.actor,
                           "payload": json.loads(ev.payload_json), "prev": prev}, sort_keys=True, default=str)
        if ev.prev_hash != prev or hashlib.sha256(body.encode()).hexdigest() != ev.hash:
            return False
        prev = ev.hash
    return True
