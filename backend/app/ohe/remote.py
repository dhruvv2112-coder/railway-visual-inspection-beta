"""Reaching the laptop server from any network (draft 1.1).

- Tunnel: the laptop opens an outbound Cloudflare quick tunnel (`cloudflared tunnel --url`), giving an HTTPS address
  like https://<words>.trycloudflare.com. No account, no router or firewall changes. A fixed address (a named
  Cloudflare tunnel, ngrok static domain, etc.) can be set instead with RVI_PUBLIC_URL.
- Relay: a quick-tunnel address changes when the server restarts, so the server posts its current address to a
  private ntfy topic, signed with HMAC-SHA256 using a key that only paired phones hold. A phone that cannot reach the
  old address reads the newest signed message, verifies it and switches. The relay only ever carries the address.
- Pairing: a signed-in phone fetches the topic and key once (GET /ohe/connect/pairing), at home on Wi-Fi or over the
  internet address typed in by hand.
"""
import hashlib
import hmac
import json
import re
import secrets
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from ..config import settings

QUICK_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_state: dict = {"public_url": None, "proc": None, "published": None, "error": None}


def relay_secrets() -> dict:
    """Topic and signing key, created once and kept next to the database."""
    p = Path(settings.relay_file)
    if p.exists():
        try:
            d = json.loads(p.read_text())
            if d.get("topic") and d.get("key"):
                return d
        except ValueError:
            pass
    d = {"topic": "ontrack-" + secrets.token_hex(12), "key": secrets.token_urlsafe(32)}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d))
    return d


def sign(url: str, ts: int, key: str) -> str:
    return hmac.new(key.encode(), f"{url}|{ts}".encode(), hashlib.sha256).hexdigest()


def public_url() -> str | None:
    return settings.public_url.rstrip("/") + "/" if settings.public_url else _state["public_url"]


def status() -> dict:
    return {"public_url": public_url(), "tunnel": settings.tunnel or ("fixed" if settings.public_url else "off"),
            "relay": bool(settings.relay_server) and bool(public_url()), "published_at": _state["published"], "error": _state["error"]}


def publish(url: str) -> bool:
    """Post the signed address to the relay topic (ntfy keeps it for at least 12 hours; republished every 30 min)."""
    if not settings.relay_server:
        return False
    s = relay_secrets()
    ts = int(time.time())
    body = json.dumps({"url": url, "ts": ts, "sig": sign(url, ts, s["key"])}).encode()
    req = urllib.request.Request(f"{settings.relay_server.rstrip('/')}/{s['topic']}", data=body, method="POST",
                                 headers={"Title": "OnTrack.AI server address", "User-Agent": "ontrack-server"})
    try:
        urllib.request.urlopen(req, timeout=15).read()
        _state["published"] = ts
        return True
    except OSError as e:
        _state["error"] = f"relay: {e}"
        print("relay publish failed:", e)
        return False


def _publisher() -> None:
    last_url, last_at = None, 0.0
    while True:
        url = public_url()
        if url and (url != last_url or time.time() - last_at > 1800) and publish(url):
            last_url, last_at = url, time.time()
            print("relay: published", url)
        time.sleep(10)


def _watch(proc: subprocess.Popen) -> None:
    for raw in iter(proc.stderr.readline, b""):
        line = raw.decode(errors="replace")
        m = QUICK_URL.search(line)
        if m and _state["public_url"] != m.group(0) + "/":
            _state["public_url"] = m.group(0) + "/"
            print("tunnel: public address", _state["public_url"])
    _state["error"] = f"tunnel stopped (exit {proc.poll()})"


def _supervise() -> None:
    """Keep cloudflared running; restart with back-off if it exits (the address may change, the relay follows)."""
    delay = 5
    while True:
        try:
            proc = subprocess.Popen([str(settings.cloudflared_path), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{settings.port}"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            _state["error"] = f"cloudflared not started: {e}"
            print(_state["error"])
            return
        _state["proc"] = proc
        _watch(proc)
        _state["public_url"] = None
        time.sleep(delay)
        delay = min(delay * 2, 300)


def start() -> None:
    """Start the tunnel (if configured) and the relay publisher. Never raises: the LAN server keeps working."""
    if settings.tunnel == "cloudflare":
        threading.Thread(target=_supervise, name="tunnel", daemon=True).start()
    if settings.tunnel or settings.public_url:
        threading.Thread(target=_publisher, name="relay", daemon=True).start()


def stop() -> None:
    p = _state.get("proc")
    if p and p.poll() is None:
        p.terminate()


# ---- sign-in protection for an internet-facing server -----------------------------------------------------------------

_fails: dict[str, tuple[int, float]] = {}
LOCK_AFTER = 5


def locked_for(*keys: str) -> int:
    """Seconds left on a lockout for any of the keys (an ID or a client address), 0 if none."""
    now = time.time()
    return max((int(until - now) for k in keys if (v := _fails.get(k)) and (until := v[1]) > now), default=0)


def record_failure(*keys: str) -> None:
    now = time.time()
    for k in keys:
        n, _ = _fails.get(k, (0, 0.0))
        n += 1
        until = now + min(60 * 2 ** (n - LOCK_AFTER), 3600) if n >= LOCK_AFTER else 0.0  # 1, 2, 4 ... 60 min
        _fails[k] = (n, until)


def record_success(*keys: str) -> None:
    for k in keys:
        _fails.pop(k, None)
