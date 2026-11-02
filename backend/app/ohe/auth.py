"""Sign-in for the OHE service (Beta). Users and roles live in a YAML file (no PINs in plain text); a signed, expiring
token carries the user id and role. Mode 'header' (development and tests) trusts X-Actor / X-Role headers instead.

  users file:  users: [{id: SSE-1205, name: "SSE TRD Jaipur", role: SSE, pin_sha256: <hex of sha256(salt + pin)>}]
  add a user:  python -m app.ohe.auth add SSE-1205 SSE 4826 "SSE TRD Jaipur"
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import Header, HTTPException

from ..config import settings

ROLES = {"Patrol", "SSE", "ADEE", "DEE", "SrDEE", "Admin"}


def _users() -> list[dict]:
    p = Path(settings.users_file)
    return (yaml.safe_load(p.read_text()) or {}).get("users", []) if p.exists() else []


def pin_hash(pin: str) -> str:
    return hashlib.sha256((settings.secret_key + ":" + pin).encode()).hexdigest()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def issue(uid: str, role: str, name: str = "") -> str:
    body = _b64(json.dumps({"id": uid, "role": role, "name": name, "exp": int(time.time()) + settings.token_hours * 3600}).encode())
    sig = _b64(hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str) -> dict | None:
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return data if data["exp"] > time.time() else None
    except (ValueError, KeyError, TypeError):  # malformed token, bad base64 or JSON
        return None


def login(uid: str, pin: str) -> dict:
    u = next((x for x in _users() if x["id"] == uid), None)
    if not u or not hmac.compare_digest(u.get("pin_sha256", ""), pin_hash(pin)):
        raise HTTPException(401, "Wrong ID or PIN")
    return {"token": issue(u["id"], u["role"], u.get("name", "")), "id": u["id"], "role": u["role"], "name": u.get("name", "")}


def actor(authorization: Annotated[str | None, Header()] = None, x_actor: Annotated[str, Header()] = "anon",
          x_role: Annotated[str, Header()] = "Patrol") -> dict:
    if authorization and authorization.lower().startswith("bearer "):
        data = verify(authorization[7:])
        if not data:
            raise HTTPException(401, "Sign in again")
        return {"id": data["id"], "role": data["role"]}
    if settings.auth_mode == "token":
        raise HTTPException(401, "Sign in required")
    return {"id": x_actor, "role": x_role}


if __name__ == "__main__" and len(sys.argv) >= 5 and sys.argv[1] == "add":
    _, _, uid, role, pin, *name = sys.argv
    assert role in ROLES, f"role must be one of {sorted(ROLES)}"
    p = Path(settings.users_file)
    data = yaml.safe_load(p.read_text()) if p.exists() else {"users": []}
    data["users"] = [u for u in data.get("users", []) if u["id"] != uid] + [
        {"id": uid, "name": " ".join(name), "role": role, "pin_sha256": pin_hash(pin)}]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"saved {uid} ({role}) to {p}")
