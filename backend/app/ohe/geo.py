"""Where and when a photo was taken when the mast number is not known (draft 1).

Order of trust: the phone's own GPS/time at capture > the photo file's EXIF GPS/time (gallery uploads, other
cameras) > a time/location stamp printed on the image by a GPS-camera app (read with the OCR text). Each value
keeps its source so the report says how it was located."""
import io
import re
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def from_exif(data: bytes) -> dict:
    """GPS (decimal degrees) and DateTimeOriginal from JPEG EXIF; {} when absent or unreadable."""
    try:
        from PIL import Image
        ex = Image.open(io.BytesIO(data)).getexif()
    except Exception:  # noqa: BLE001
        return {}
    out: dict = {}
    try:
        gps = ex.get_ifd(0x8825)
        def deg(v, ref):
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return -d if ref in ("S", "W", b"S", b"W") else d
        if gps.get(2) and gps.get(4):
            lat, lon = deg(gps[2], gps.get(1, "N")), deg(gps[4], gps.get(3, "E"))
            if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0.0, 0.0):
                out |= {"lat": round(lat, 7), "lon": round(lon, 7)}
    except Exception:  # noqa: BLE001, S110 - unreadable EXIF just means no GPS tag
        pass
    try:
        sub = ex.get_ifd(0x8769)
        t = sub.get(36867) or ex.get(306)                     # DateTimeOriginal, else DateTime
        off = sub.get(36881) or sub.get(36880)                # OffsetTimeOriginal / OffsetTime, e.g. "+05:30"
        if t:
            dt = datetime.strptime(str(t).strip("\x00 "), "%Y:%m:%d %H:%M:%S")  # noqa: DTZ007 - EXIF has no zone; set below
            tz = IST
            if off and re.fullmatch(r"[+-]\d{2}:\d{2}", str(off)):
                sign = 1 if str(off)[0] == "+" else -1
                tz = timezone(sign * timedelta(hours=int(str(off)[1:3]), minutes=int(str(off)[4:6])))
            out["taken_at"] = dt.replace(tzinfo=tz)
    except Exception:  # noqa: BLE001, S110 - unreadable EXIF just means no GPS tag
        pass
    return out


_NUM = r"(-?\d{1,3}\.\d{3,})"


def from_stamp(texts: list[str]) -> dict:
    """Latitude/longitude and date-time printed on the photo (GPS-camera apps). OCR text has spaces removed."""
    t = " ".join(texts)
    out: dict = {}
    lat = re.search(r"Lat(?:itude)?[:=.]?" + _NUM + r"°?([NS])?", t, re.IGNORECASE)
    lon = re.search(r"(?:Long(?:itude)?|Lng|Lon)[:=.]?" + _NUM + r"°?([EW])?", t, re.IGNORECASE)
    if not (lat and lon):  # "26.912400°N 75.787300°E" / "26.9124N,75.7873E" / "26.9124, 75.7873"
        pair = re.search(_NUM + r"°?([NS])?[,;/\s]*" + _NUM + r"°?([EW])?", t)
        if pair:
            la, ns, lo, ew = pair.groups()
            lat, lon = (la, ns), (lo, ew)
        else:
            lat = lon = None
    else:
        lat, lon = lat.groups(), lon.groups()
    if lat and lon:
        la, lo = float(lat[0]), float(lon[0])
        if lat[1] and lat[1].upper() == "S":
            la = -abs(la)
        if lon[1] and lon[1].upper() == "W":
            lo = -abs(lo)
        if -90 <= la <= 90 and -180 <= lo <= 180 and abs(la) > 0.01:
            out |= {"lat": la, "lon": lo}
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\D{0,3}(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?", t, re.IGNORECASE) \
        or re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\D{0,3}(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?", t, re.IGNORECASE)
    if m:
        g = m.groups()
        try:
            if len(g[0]) == 4:
                y, mo, d = int(g[0]), int(g[1]), int(g[2])
            else:   # Indian stamps are day/month/year
                d, mo, y = int(g[0]), int(g[1]), int(g[2])
                y += 2000 if y < 100 else 0
            hh, mm, ss = int(g[3]), int(g[4]), int(g[5] or 0)
            if g[6]:
                hh = hh % 12 + (12 if g[6].upper() == "PM" else 0)
            out["taken_at"] = datetime(y, mo, d, hh, mm, ss, tzinfo=IST)
        except ValueError:
            pass
    return out


def cell(lat: float, lon: float, metres: float = 30.0) -> str:
    """Grid cell (~metres) used to merge repeat photos of the same unlocated finding."""
    step = metres / 111_000
    return f"{round(lat / step) * step:.5f},{round(lon / step) * step:.5f}"
