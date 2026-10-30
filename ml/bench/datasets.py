"""Dataset fetchers. Only openly licensed sources that a CI runner can download without credentials.
Each returns local paths; failures raise with a clear message (recorded in the report)."""
import csv
import io
import json
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from common import DATA

UA = {"User-Agent": "rvi-bench/0.1"}


def _get(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    return dest


# ---------------- Indian railway track defects (Mendeley 88sh5y3tmj v2, CC BY 4.0) ----------------
MENDELEY_ID, MENDELEY_VER = "88sh5y3tmj", 2


def mendeley_rail_defects() -> Path:
    root = DATA / "mendeley_rail"
    marker = root / ".done"
    if marker.exists():
        return root
    api = f"https://data.mendeley.com/public-api/datasets/{MENDELEY_ID}/files?folder_id=root&version={MENDELEY_VER}"
    files = json.loads(urllib.request.urlopen(urllib.request.Request(api, headers=UA), timeout=120).read())

    def walk(items, sub=""):
        for it in items:
            if it.get("content_details"):  # file
                url = it["content_details"]["download_url"]
                p = _get(url, root / "raw" / sub / it["filename"])
                if p.suffix.lower() == ".zip":
                    with zipfile.ZipFile(p) as z:
                        z.extractall(root / "x")
            elif it.get("id"):  # folder
                sub_api = (f"https://data.mendeley.com/public-api/datasets/{MENDELEY_ID}/files?"
                           f"folder_id={it['id']}&version={MENDELEY_VER}")
                walk(json.loads(urllib.request.urlopen(urllib.request.Request(sub_api, headers=UA)).read()),
                     f"{sub}/{it.get('name', it['id'])}")

    walk(files)
    marker.write_text("ok")
    return root


# ---------------- FLEURS (CC BY 4.0) speech: hi_in, en_us ----------------
def fleurs(lang: str, split: str = "test", limit: int = 100) -> list[dict]:
    from huggingface_hub import hf_hub_download

    tsv = hf_hub_download("google/fleurs", f"data/{lang}/{split}.tsv", repo_type="dataset")
    tar = hf_hub_download("google/fleurs", f"data/{lang}/audio/{split}.tar.gz", repo_type="dataset")
    out_dir = DATA / "fleurs" / lang / split
    if not out_dir.exists():
        with tarfile.open(tar) as t:
            t.extractall(out_dir)
    wavs = {p.name: p for p in out_dir.rglob("*.wav")}
    rows = []
    with open(tsv, encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t"):
            # columns: id, file_name, raw_transcription, transcription, phonemes, num_samples, gender
            if r[1] in wavs:
                rows.append({"id": r[0], "wav": wavs[r[1]], "text": r[2], "norm": r[3]})
            if len(rows) >= limit:
                break
    return rows


# ---------------- ESC-50 environmental noise (CC BY-NC 3.0, benchmark use only) ----------------
def esc50() -> Path:
    z = _get("https://github.com/karolpiczak/ESC-50/archive/master.zip", DATA / "esc50.zip")
    root = DATA / "ESC-50-master"
    if not root.exists():
        with zipfile.ZipFile(z) as zz:
            zz.extractall(DATA)
    return root


def esc50_noise(categories=("train", "rain", "wind", "engine", "church_bells")) -> list[Path]:
    root = esc50()
    out = []
    with open(root / "meta" / "esc50.csv") as f:
        for r in csv.DictReader(f):
            if r["category"] in categories:
                out.append(root / "audio" / r["filename"])
    return out


def find_images(root: Path, limit: int | None = None) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    imgs = sorted(p for p in root.rglob("*") if p.suffix.lower() in exts)
    return imgs[:limit] if limit else imgs
