"""Normalise the downloaded rail-defect dataset to Ultralytics YOLO layout (standard format) with a fixed,
seeded train/val/test split. Supports YOLO txt and Pascal VOC xml sources (auto-detected)."""
import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from common import DATA
from datasets import find_images, mendeley_rail_defects


def _class_names(root: Path):
    for f in list(root.rglob("data.yaml")) + list(root.rglob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text())
            names = d.get("names")
            if names:
                return list(names.values()) if isinstance(names, dict) else list(names)
        except Exception:
            pass
    for f in root.rglob("classes.txt"):
        return [l.strip() for l in f.read_text().splitlines() if l.strip()]
    return None


def build(seed: int = 0) -> tuple[Path, list[str], dict]:
    src = mendeley_rail_defects()
    out = DATA / "rail_yolo"
    if (out / "data.yaml").exists():
        d = yaml.safe_load((out / "data.yaml").read_text())
        return out / "data.yaml", d["names"], d.get("stats", {})
    imgs = find_images(src)
    names = _class_names(src)
    voc = {p.stem: p for p in src.rglob("*.xml")}
    txt = {p.stem: p for p in src.rglob("*.txt") if p.name != "classes.txt"}
    items, voc_names = [], []
    for im in imgs:
        if im.stem in txt:
            items.append((im, txt[im.stem].read_text().strip().splitlines()))
        elif im.stem in voc:
            t = ET.parse(voc[im.stem]).getroot()
            w, h = float(t.find("size/width").text), float(t.find("size/height").text)
            lines = []
            for o in t.findall("object"):
                n = o.find("name").text.strip()
                if n not in voc_names:
                    voc_names.append(n)
                b = o.find("bndbox")
                x1, y1, x2, y2 = (float(b.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax"))
                lines.append(f"{voc_names.index(n)} {(x1 + x2) / 2 / w} {(y1 + y2) / 2 / h} {(x2 - x1) / w} {(y2 - y1) / h}")
            items.append((im, lines))
    if not items:
        raise RuntimeError(f"No annotated images found under {src} (found {len(imgs)} images)")
    if names is None:
        names = voc_names or [str(i) for i in range(1 + max(int(l.split()[0]) for _, ls in items for l in ls if l))]
    random.Random(seed).shuffle(items)
    n = len(items)
    splits = {"train": items[: int(.8 * n)], "val": items[int(.8 * n): int(.9 * n)], "test": items[int(.9 * n):]}
    stats = {"images": n, "classes": len(names), "per_split": {k: len(v) for k, v in splits.items()}}
    counts = [0] * len(names)
    for k, v in splits.items():
        (out / k / "images").mkdir(parents=True, exist_ok=True)
        (out / k / "labels").mkdir(parents=True, exist_ok=True)
        for im, lines in v:
            dst = out / k / "images" / f"{im.parent.name}_{im.name}"
            shutil.copy(im, dst)
            (out / k / "labels" / (dst.stem + ".txt")).write_text("\n".join(lines))
            for l in lines:
                if l.strip():
                    counts[int(l.split()[0])] += 1
    stats["instances_per_class"] = dict(zip(names, counts))
    (out / "data.yaml").write_text(yaml.safe_dump({"path": str(out), "train": "train/images", "val": "val/images",
                                                   "test": "test/images", "names": names, "stats": stats}, allow_unicode=True))
    return out / "data.yaml", names, stats
