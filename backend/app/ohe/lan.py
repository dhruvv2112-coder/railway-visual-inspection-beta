"""Local-network serving for a laptop server (draft 1): the phone app finds the server on the same Wi-Fi by mDNS
(service type _ontrack._tcp), and the laptop shows a connect page with the address, a QR code and the app download.

Everything here is optional: zeroconf and qrcode are imported lazily and the server works without them."""
import html
import json
import os
import socket
from datetime import UTC
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from ..config import settings

router = APIRouter(prefix="/ohe/connect", tags=["connect"])
SERVICE = "_ontrack._tcp.local."
_zc: dict = {}


def lan_ips() -> list[str]:
    """IPv4 addresses other devices can reach (no loopback). The default-route address comes first."""
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no packet is sent; picks the outgoing interface
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.") and not ip.startswith("169.254.")]


def urls() -> list[str]:
    return [f"http://{ip}:{settings.port}/" for ip in lan_ips()]


async def start_mdns() -> bool:
    """Advertise this server on the local network. Never stops the server: any failure only disables discovery."""
    if not settings.mdns:
        return False
    try:
        from zeroconf import ServiceInfo
        from zeroconf.asyncio import AsyncZeroconf
    except ImportError:
        print("mDNS: zeroconf not installed; phones must enter the address by hand")
        return False
    ips = lan_ips()
    if not ips:
        return False
    name = f"{settings.server_name} ({socket.gethostname()})"[:60]
    try:
        info = ServiceInfo(SERVICE, f"{name}.{SERVICE}", addresses=[socket.inet_aton(ip) for ip in ips], port=settings.port,
                           properties={"path": "/", "app": "ontrack", "v": "1"}, server=f"{socket.gethostname()}.local.")
        azc = AsyncZeroconf()
        await azc.async_register_service(info, allow_name_change=True)
    except Exception as e:  # noqa: BLE001 - discovery is optional
        print("mDNS: advertising failed, phones must enter the address by hand:", e)
        return False
    _zc.update(zc=azc, info=info)
    keep_awake()
    print("mDNS: advertising", name, "on", ", ".join(ips))
    return True


def keep_awake() -> None:
    """Windows laptop server: stop the laptop sleeping while the server runs (the display may still turn off)."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


async def stop_mdns() -> None:
    azc, info = _zc.pop("zc", None), _zc.pop("info", None)
    if azc:
        try:
            if info:
                await azc.async_unregister_service(info)
        except Exception:  # noqa: BLE001
            pass
        finally:
            await azc.async_close()


def _qr_svg(text: str) -> str:
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return ""
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    return img.to_string(encoding="unicode")


def _app_meta() -> dict | None:
    p, apk = settings.app_dir / "latest.json", settings.app_dir / "app.apk"
    if not apk.exists():
        return None
    meta = json.loads(p.read_text()) if p.exists() else {}
    return meta | {"size_mb": round(apk.stat().st_size / 1e6, 1)}


@router.get("/info")
def info():
    """What the phone needs to connect: the addresses and whether an app build can be downloaded here."""
    return {"name": settings.server_name, "host": socket.gethostname(), "urls": urls(), "mdns_service": SERVICE,
            "mdns": bool(_zc), "app": _app_meta()}


@router.get("/app.apk", include_in_schema=False)
def app_apk():
    """App download for phones on the same network (no sign-in: the phone has no account until the app is installed)."""
    f = settings.app_dir / "app.apk"
    if not settings.public_apk or not f.exists():
        raise HTTPException(404, "No app build on this server")
    return FileResponse(f, media_type="application/vnd.android.package-archive", filename="OnTrack.AI.apk")


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def connect_page():
    us = urls()
    first = us[0] if us else f"http://<this-laptop>:{settings.port}/"
    meta = _app_meta()
    apk_url = first + "ohe/connect/app.apk"
    qr_apk = _qr_svg(apk_url) if meta else ""
    qr_srv = _qr_svg(first)
    esc = html.escape
    app_block = (f"<div class='card'><h2>1 · Install the app</h2><div class='qr'>{qr_apk}</div>"
                 f"<p>Scan with the phone camera, download, then open the file to install.</p>"
                 f"<p class='mono'>{esc(apk_url)}</p><p class='muted'>Version {esc(str(meta.get('version_name', '—')))} · "
                 f"{meta['size_mb']} MB</p></div>") if meta else (
        "<div class='card'><h2>1 · Install the app</h2><p>No app build is on this laptop yet. Put the .apk in the "
        "<span class='mono'>app</span> folder next to the server and refresh.</p></div>")
    others = "".join(f"<li class='mono'>{esc(u)}</li>" for u in us[1:])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OnTrack.AI server</title><style>
:root{{--ink:#0E1020;--blue:#3346FF;--muted:#464B63}}
body{{margin:0;font-family:'Segoe UI',system-ui,sans-serif;color:var(--ink);background:#E6EAF5;min-height:100vh;
background-image:radial-gradient(600px 400px at 0% 0%,rgba(51,70,255,.35),transparent),radial-gradient(500px 400px at 100% 30%,rgba(20,200,180,.3),transparent)}}
main{{max-width:960px;margin:0 auto;padding:40px 20px}} h1{{font-size:34px;letter-spacing:-.03em;margin:0 0 6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:18px;margin-top:24px}}
.card{{background:rgba(255,255,255,.65);backdrop-filter:blur(24px);border:1px solid #fff;border-radius:28px;padding:22px;box-shadow:0 14px 36px rgba(23,27,66,.12)}}
h2{{margin:0 0 12px;font-size:18px}} .qr svg{{width:220px;height:220px;background:#fff;border-radius:16px;padding:8px}}
.mono{{font-family:Consolas,monospace;word-break:break-all}} .muted{{color:var(--muted)}} .ok{{color:#046C4E;font-weight:700}}
a{{color:var(--blue)}}</style></head><body><main>
<h1>OnTrack.AI server is running</h1><p class="muted">Keep this laptop on and on the same Wi-Fi as the phones. Close the server window to stop.</p>
<div class="grid">{app_block}
<div class="card"><h2>2 · Connect the phone</h2><div class="qr">{qr_srv}</div>
<p>The app finds this laptop by itself on the same Wi-Fi ({'<span class="ok">advertising</span>' if _zc else 'discovery off'}).
If it does not, type this address in the app:</p><p class="mono" style="font-size:20px">{esc(first)}</p>
{f'<p class="muted">Other addresses:</p><ul>{others}</ul>' if others else ''}</div>
<div class="card"><h2>3 · Review reports</h2><p>Open the reviewer page on this laptop:</p><p><a href="/ohe/review">/ohe/review</a></p>
<p class="muted">Server health: <a href="/health">/health</a></p></div>
</div></main></body></html>"""


def install_app_from(folder: Path) -> bool:
    """Copy the newest .apk found in a folder into settings.app_dir with a latest.json (used by the Windows starter)."""
    import hashlib
    from datetime import datetime
    apks = sorted(folder.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not apks:
        return False
    data = apks[0].read_bytes()
    d = settings.app_dir
    d.mkdir(parents=True, exist_ok=True)
    meta_src = folder / "latest.json"
    meta = json.loads(meta_src.read_text()) if meta_src.exists() else {"version_code": 0, "version_name": apks[0].stem, "notes": []}
    meta |= {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
             "built_at": meta.get("built_at") or datetime.now(UTC).isoformat()}
    (d / "app.apk").write_bytes(data)
    (d / "latest.json").write_text(json.dumps(meta))
    return True
