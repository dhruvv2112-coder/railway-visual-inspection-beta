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


# Class names for Mendeley 88sh5y3tmj v2 (Roboflow export without data.yaml). Names from Mordia & Verma,
# High-speed Railway 2026 (doi 10.1016/j.hspr.2026.03.002) §3.2; index order = Roboflow's alphabetical convention
# (consistent with instance counts: index 0 rarest = Broken-rail). Verify against the author's data.yaml when available.
MENDELEY_NAMES = ["Broken-rail", "Corrosion", "Cracks", "Flakings", "Joints", "Missing-fastener", "Shelling",
                  "Spalling", "Squats", "Wheel-burn"]


def _provided_splits(src: Path):
    """Use the dataset's own train/valid/test split when present (avoids frames of one video leaking across splits)."""
    roots = [p.parent for p in src.rglob("train") if (p / "images").is_dir() and (p.parent / "test" / "images").is_dir()]
    return roots[0] if roots else None


def build(seed: int = 0) -> tuple[Path, list[str], dict]:
    src = mendeley_rail_defects()
    out = DATA / "rail_yolo"
    if (out / "data.yaml").exists():
        d = yaml.safe_load((out / "data.yaml").read_text())
        return out / "data.yaml", d["names"], d.get("stats", {})
    names = _class_names(src) or (MENDELEY_NAMES if "mendeley" in str(src) else None)
    prov = _provided_splits(src)
    if prov is not None:
        stats = {"split": "provided (Roboflow train/valid/test)", "classes": len(names) if names else None, "per_split": {}}
        counts = [0] * len(names)
        for k, sub in (("train", "train"), ("val", "valid"), ("test", "test")):
            (out / k / "images").mkdir(parents=True, exist_ok=True)
            (out / k / "labels").mkdir(parents=True, exist_ok=True)
            ims = find_images(prov / sub / "images")
            n = 0
            for im in ims:
                lab = prov / sub / "labels" / (im.stem + ".txt")
                if not lab.exists():
                    continue
                shutil.copy(im, out / k / "images" / im.name)
                lines = lab.read_text().strip().splitlines()
                (out / k / "labels" / (im.stem + ".txt")).write_text("\n".join(lines))
                for l in lines:
                    if l.strip():
                        counts[int(l.split()[0])] += 1
                n += 1
            stats["per_split"][k] = n
        stats["images"] = sum(stats["per_split"].values())
        stats["instances_per_class"] = dict(zip(names, counts))
        (out / "data.yaml").write_text(yaml.safe_dump({"path": str(out), "train": "train/images", "val": "val/images",
                                                       "test": "test/images", "names": names, "stats": stats}, allow_unicode=True))
        return out / "data.yaml", names, stats
    imgs = find_images(src)
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
