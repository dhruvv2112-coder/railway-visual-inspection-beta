"""Build one YOLO-format OHE dataset from public sources, mapped to the registry component names
(shared/ohe_registry.yaml). Download routes avoid per-file API calls (HF rate limits): git clone for GitHub,
`datasets.load_dataset` (parquet) for Hugging Face.

Sources found (search log in docs/OHE_DATASETS.md):
  CPLID      github.com/InsulatorData/InsulatorDataSet            VOC; insulator + defect      licence undetermined (user: use for training)
  POWERLINE  hf docmhvr/powerline-components-and-faults           parquet, drone                MIT
  SYNTH      hf silera/broken-insulators-synthetic-detection      parquet, synthetic            CC BY 4.0
  ROBOFLOW   railway catenary / dropper / pantograph sets (optional, needs ROBOFLOW_API_KEY)  CC BY 4.0
Domain caveat: none of these is ground-level 25 kV railway OHE from a phone."""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

BASE = Path(os.environ.get("OHE_DATA", ".cache/ohe"))
OUT = BASE / "ohe_yolo"
CAP = int(os.environ.get("OHE_CAP_PER_SOURCE", "1500"))
TARGET = ["insulator", "insulator_defect", "bird_nest", "vegetation", "dropper", "number_plate", "catenary", "pantograph"]
HF = [("docmhvr/powerline-components-and-faults", "MIT"), ("silera/broken-insulators-synthetic-detection", "CC BY 4.0")]
# sources whose class names are not published but whose content is a single known class (dataset card)
HF_FIXED_CLASS = {"silera/broken-insulators-synthetic-detection": "insulator_defect"}
ROBOFLOW = [("railway-monitor", "catenary", 1), ("object-detection-bmosq", "panto-catenary", 1)]  # (workspace, project, version)


def map_name(n: str) -> str | None:
    n = n.lower().replace("_", " ").replace("-", " ")
    if re.search(r"defect|broken|damag|fault|flash|crack|missing|burn", n) and ("insulator" in n or n.strip() in
                                                                                ("defect", "broken", "damaged", "flashed")):
        return "insulator_defect"
    if "insulator" in n:
        return "insulator"
    if "nest" in n:
        return "bird_nest"
    if re.search(r"veget|tree|branch", n):
        return "vegetation"
    if "dropper" in n:
        return "dropper"
    if "panto" in n:
        return "pantograph"
    if "catenary" in n or "contact wire" in n:
        return "catenary"
    return None


def split_for(key: str) -> str:
    h = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


class Writer:
    def __init__(self):
        self.stats = {}

    def add(self, src: str, split: str, name: str, img_bytes: bytes, boxes: list[tuple[str, float, float, float, float]]):
        st = self.stats.setdefault(src, {"images": {"train": 0, "val": 0, "test": 0}, "instances": {t: 0 for t in TARGET}})
        if split == "train" and st["images"]["train"] >= CAP:
            return
        for d in ("images", "labels"):
            (OUT / split / d).mkdir(parents=True, exist_ok=True)
        (OUT / split / "images" / f"{src}_{name}.jpg").write_bytes(img_bytes)
        lines = []
        for t, cx, cy, w, h in boxes:
            if w > 0 and h > 0:
                lines.append(f"{TARGET.index(t)} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                st["instances"][t] += 1
        (OUT / split / "labels" / f"{src}_{name}.txt").write_text("\n".join(lines))
        st["images"][split] += 1


def cplid(w: Writer, manifest: list):
    d = BASE / "InsulatorDataSet"
    if not d.exists():
        subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/InsulatorData/InsulatorDataSet", str(d)], check=True)
    xmls = list(d.rglob("*.xml"))
    by_stem: dict[str, list[Path]] = {}
    for x in xmls:
        by_stem.setdefault(x.stem, []).append(x)
    imgs = {p.stem: p for p in d.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    names = set()
    for stem, xs in by_stem.items():
        if stem not in imgs:
            continue
        boxes = []
        for x in xs:
            r = ET.parse(x).getroot()
            W, H = float(r.find("size/width").text), float(r.find("size/height").text)
            for o in r.findall("object"):
                n = o.find("name").text.strip()
                names.add(n)
                t = map_name(n)
                b = o.find("bndbox")
                x1, y1, x2, y2 = (float(b.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax"))
                if t:
                    boxes.append((t, (x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H))
        # consecutive UAV frames share a chain: group by numeric block so a chain never spans splits
        num = re.sub(r"\D", "", stem)
        key = f"cplid-{imgs[stem].parent.name}-{int(num) // 10 if num else stem}"
        w.add("cplid", split_for(key), stem, imgs[stem].read_bytes(), boxes)
    manifest.append({"source": "CPLID github.com/InsulatorData/InsulatorDataSet", "licence": "undetermined (user: use for training)",
                     "source_names": sorted(names)})


def box_format(ds, col, flat) -> tuple[bool, bool]:
    """Decide the box convention once per dataset, not per image (a per-image guess misreads images whose boxes
    happen to fit either way). Normalised if every coordinate <= 1. Else COCO [x, y, w, h] unless some box would
    then run off the image while every box is a valid [x1, y1, x2, y2]."""
    bbs, sizes = [], []
    for part in ds.values():
        sub = part.select(range(min(300, len(part))))
        size = sub[0][next(k for k, v in part.features.items() if type(v).__name__ == "Image")].size
        rows = sub["bboxes"] if flat else [o["bbox"] if isinstance(o, dict) else [x["bbox"] for x in o] for o in sub[col]]
        for r in rows:
            bbs += r
            sizes += [size] * len(r)
    if not bbs:
        return False, False
    if all(max(b) <= 1.0 for b in bbs):
        return True, False
    # tolerant to a few degenerate boxes (x2 == x1) that real annotation sets contain
    valid_xyxy = sum(b[2] >= b[0] and b[3] >= b[1] for b in bbs) / len(bbs)
    overrun = sum(b[0] + b[2] > W * 1.02 or b[1] + b[3] > H * 1.02 for b, (W, H) in zip(bbs, sizes)) / len(bbs)
    print("box format evidence", {"boxes": len(bbs), "valid_as_xyxy": round(valid_xyxy, 3),
                                  "overrun_as_xywh": round(overrun, 3)}, flush=True)
    return False, valid_xyxy >= 0.98 and overrun > 0.02


def hf_parquet(w: Writer, repo: str, lic: str, manifest: list):
    from datasets import load_dataset
    ds = load_dataset(repo)
    src = repo.split("/")[1][:12]
    feats = next(iter(ds.values())).features
    print("features", repo, feats, flush=True)
    flat = "bboxes" in feats  # parallel top-level columns: bboxes + labels (e.g. docmhvr)
    if flat:
        col, sub = "bboxes", feats
    else:
        col = next(k for k, v in feats.items() if hasattr(v, "keys") and ("bbox" in v or "bboxes" in v) or
                   (getattr(v, "feature", None) is not None and hasattr(v.feature, "keys") and "bbox" in v.feature))
        sub = feats[col].feature if getattr(feats[col], "feature", None) is not None else feats[col]
    catk = next(k for k in ("category", "categories", "label", "labels", "class") if k in sub)
    cf = sub[catk]
    names = list(getattr(getattr(cf, "feature", cf), "names", []) or [])
    img_col = next(k for k, v in feats.items() if type(v).__name__ == "Image")
    fmt = box_format(ds, col, flat)
    print("box format", repo, {"normalised": fmt[0], "xyxy": fmt[1]}, flush=True)
    for split_name, part in ds.items():
        split = {"validation": "val", "valid": "val"}.get(split_name, split_name if split_name in ("train", "val", "test") else "train")
        for i, row in enumerate(part):
            im = row[img_col]
            W, H = im.size
            if flat:
                bbs, cats = row["bboxes"], row[catk]
            else:
                objs = row[col]
                bbs = objs["bbox"] if isinstance(objs, dict) else [o["bbox"] for o in objs]
                cats = objs[catk] if isinstance(objs, dict) else [o[catk] for o in objs]
            if i == 0:
                print("sample", repo, split_name, (W, H), bbs[:3], cats[:3], flush=True)
            norm, xyxy = fmt
            boxes = []
            for b, c in zip(bbs, cats):
                n = names[c] if names and isinstance(c, int) else str(c)
                t = HF_FIXED_CLASS.get(repo) or map_name(n)
                if not t:
                    continue
                if norm:
                    boxes.append((t, *map(float, b[:4])))
                    continue
                x1, y1 = b[0], b[1]
                bw, bh = (b[2] - b[0], b[3] - b[1]) if xyxy else (b[2], b[3])
                boxes.append((t, (x1 + bw / 2) / W, (y1 + bh / 2) / H, bw / W, bh / H))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=92)
            w.add(src, split, f"{split_name}{i:05d}", buf.getvalue(), boxes)
    manifest.append({"source": f"hf:{repo}", "licence": lic, "source_names": names, "bbox_column": col})


def roboflow(w: Writer, manifest: list):
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        manifest.append({"source": "roboflow railway catenary/panto sets", "skipped": "no ROBOFLOW_API_KEY"})
        return
    from roboflow import Roboflow
    rf = Roboflow(api_key=key)
    for ws, proj, ver in ROBOFLOW:
        try:
            loc = rf.workspace(ws).project(proj).version(ver).download("yolov8", location=str(BASE / f"rf_{proj}")).location
            names = yaml.safe_load((Path(loc) / "data.yaml").read_text())["names"]
            for img in Path(loc).rglob("images/*"):
                lab = img.parent.parent / "labels" / (img.stem + ".txt")
                rows = [ln.split() for ln in lab.read_text().splitlines()] if lab.exists() else []
                boxes = [(map_name(names[int(r[0])]), *map(float, r[1:5])) for r in rows if map_name(names[int(r[0])])]
                sp = {"valid": "val"}.get(img.parent.parent.name, img.parent.parent.name)
                w.add(f"rf{proj[:6]}", sp if sp in ("train", "val", "test") else "train", img.stem, img.read_bytes(), boxes)
            manifest.append({"source": f"roboflow:{ws}/{proj}/{ver}", "licence": "CC BY 4.0", "source_names": names})
        except Exception as e:  # keep going with other sources
            manifest.append({"source": f"roboflow:{ws}/{proj}", "error": str(e)[:200]})


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    w, manifest = Writer(), []
    for fn, args in ((cplid, ()), *((hf_parquet, a) for a in HF), (roboflow, ())):
        try:
            fn(w, *args, manifest)
        except Exception as e:
            manifest.append({"source": f"{fn.__name__}{args}", "error": f"{type(e).__name__}: {str(e)[:300]}"})
        print(json.dumps(manifest[-1])[:600], flush=True)
    used = [t for t in TARGET if sum(s["instances"][t] for s in w.stats.values()) > 0]
    # re-index labels to the classes actually present so the detector has no empty classes
    for lab in OUT.rglob("labels/*.txt"):
        rows = [r.split() for r in lab.read_text().splitlines() if r.strip()]
        lab.write_text("\n".join(" ".join([str(used.index(TARGET[int(r[0])]))] + r[1:]) for r in rows))
    (OUT / "data.yaml").write_text(yaml.safe_dump({"path": str(OUT.resolve()), "train": "train/images", "val": "val/images",
                                                   "test": "test/images", "names": used}))
    out = {"target_names": used, "sources": manifest, "stats": w.stats}
    (OUT / "manifest.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
