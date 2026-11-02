"""End-to-end demo against a running server: start a patrol, upload photos, add a note, end the patrol, print the
report summary and the reviewer link. Uses only the Python standard library.

  python demo.py --server http://localhost:8000 --id PT-1 --pin 1111 photos/*.jpg
  python demo.py --server http://localhost:8000 --synthetic 4     # no photos at hand: generated images (flow test only)
"""
import argparse
import hashlib
import io
import json
import struct
import urllib.request
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path


def call(server, path, token=None, body=None, files=None, fields=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {"X-Actor": "demo", "X-Role": "Patrol"}
    data = None
    if files:
        b = uuid.uuid4().hex
        out = io.BytesIO()
        for k, v in (fields or {}).items():
            out.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        for k, (name, content) in files.items():
            out.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{name}\"\r\n"
                      f"Content-Type: image/jpeg\r\n\r\n".encode() + content + b"\r\n")
        out.write(f"--{b}--\r\n".encode())
        data, headers["Content-Type"] = out.getvalue(), f"multipart/form-data; boundary={b}"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(server.rstrip("/") + path, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def synthetic_png(seed: int) -> bytes:
    """A noisy grey PNG (valid image, no railway content): exercises the flow, not the models."""
    w = h = 640
    rows = b"".join(b"\x00" + bytes(((x * 7 + y * 13 + seed * 31) * 2654435761 >> 24) & 0xFF for x in range(w)) for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--id")
    ap.add_argument("--pin")
    ap.add_argument("--section", default="SEC-DEMO-01")
    ap.add_argument("--synthetic", type=int, default=0)
    ap.add_argument("photos", nargs="*")
    a = ap.parse_args()
    token = call(a.server, "/ohe/auth/login", body={"id": a.id, "pin": a.pin})["token"] if a.id and a.pin else None
    sid = call(a.server, "/ohe/sessions", token, body={"territory": a.section})["id"]
    print("patrol", sid)
    imgs = [(Path(p).name, Path(p).read_bytes()) for p in a.photos] + [(f"synthetic_{i}.png", synthetic_png(i)) for i in range(a.synthetic)]
    for name, data in imgs:
        r = call(a.server, f"/ohe/sessions/{sid}/media", token, files={"image": (name, data)},
                 fields={"sha256": hashlib.sha256(data).hexdigest(), "captured_at": datetime.now(timezone.utc).isoformat()})
        an = r.get("analysis", {})
        states = [x["state"] for x in an.get("assessments", [])] or [an.get("image_state") or r["media"]["status"]]
        print(f"  {name}: {', '.join(states)}" + (f"  → retake: {an['recapture_prompt']}" if an.get("recapture_prompt") else ""))
    call(a.server, f"/ohe/sessions/{sid}/notes", token, body={"text": "Demo note: not used by the inspection"})
    end = call(a.server, f"/ohe/sessions/{sid}/end", token, body={})
    print("report", end["report_id"], json.dumps(end["summary"], indent=1))
    print("review at", a.server.rstrip("/") + "/ohe/review")


if __name__ == "__main__":
    main()
