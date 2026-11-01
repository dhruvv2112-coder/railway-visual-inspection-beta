"""Build one YOLO-format OHE dataset from public sources, mapped to the registry component names
(shared/ohe_registry.yaml). Download routes avoid per-file API calls (HF rate limits): git clone for GitHub,
`datasets.load_dataset` (parquet) for Hugging Face.

Sources found (search log in docs/OHE_DATASETS.md):
  CPLID      github.com/InsulatorData/InsulatorDataSet            VOC; insulator + defect      licence undetermined (user: use for training)
  POWERLINE  hf docmhvr/powerline-components-and-faults           parquet, drone                MIT
  SYNTH      hf silera/broken-insulators-synthetic-detection      parquet, synthetic            CC BY 4.0
  ROBOFLOW   railway catenary / dropper / pantograph sets (optional, needs ROBOFLOW_API_KEY)  CC BY 4.0
  EPDCL      hf EPDCL/pd-defect (pole_detection, vegetation_conductor) phone, ground level, India  CC BY 4.0
  RAILFOD23  figshare 24180738: foreign objects on railway lines (bird nest, kite, balloon, bag); COCO  CC BY 4.0
  VPMBGI     github phd-benel/VPMBGI release: broken glass insulators (ground patrol + helicopter)   CC BY 4.0
  CORROSION  hf LibreYOLO/corrosion-bi3q3 (Roboflow 100)                                          CC BY 4.0
Domain caveat: none of these is ground-level 25 kV railway OHE from a phone; EPDCL is the closest (Indian 11 kV
distribution poles, phone photos). Sources that label only some classes leave the others unlabelled in their images
(partial labels); per-source test scores in the detector report expose the effect."""
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
EVAL_CAP = int(os.environ.get("OHE_EVAL_CAP_PER_SOURCE", "250"))
# e.g. "powerline-co=800" (keeps enough powerline vegetation while the global cap stays low)
CAP_OVR = dict(kv.split("=") for kv in os.environ.get("OHE_CAP_OVERRIDES", "").split(",") if "=" in kv)
TARGET = ["insulator", "insulator_defect", "bird_nest", "vegetation", "dropper", "number_plate", "catenary", "pantograph",
          "mast", "foreign_object", "corrosion"]
HF = [("docmhvr/powerline-components-and-faults", "MIT"), ("silera/broken-insulators-synthetic-detection", "CC BY 4.0")]
# sources whose class names are not published but whose content is a single known class (dataset card)
HF_FIXED_CLASS = {"silera/broken-insulators-synthetic-detection": "insulator_defect"}
ROBOFLOW = [("railway-monitor", "catenary", 1), ("object-detection-bmosq", "panto-catenary", 1)]  # (workspace, project, version)


PINYIN = {"niaocao": "bird_nest", "piaofuwu": "foreign_object", "qiqiu": "foreign_object", "suliaodai": "foreign_object"}


def map_name(n: str) -> str | None:
    n = n.lower().replace("_", " ").replace("-", " ")
    if n.strip().replace(" ", "") in PINYIN:  # RailFOD23 class names are pinyin
        return PINYIN[n.strip().replace(" ", "")]
    if re.search(r"broken glass|iso broken", n):  # VPMBGI 'iso_broken_glass'
        return "insulator_defect"
    if re.search(r"defect|broken|damag|fault|flash|crack|missing|burn", n) and ("insulator" in n or n.strip() in
                                                                                ("defect", "broken", "damaged", "flashed")):
        return "insulator_defect"
    if "insulator" in n:
        return "insulator"
    if "nest" in n:
        return "bird_nest"
    if re.search(r"kite|balloon|plastic|bag|float|debris|foreign|garbage|rubbish", n):
        return "foreign_object"
    if re.search(r"corros|rust", n):
        return "corrosion"
    if re.fullmatch(r"(leaned |straight )?pole|mast|catenary pole", n.strip()):
        return "mast"
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
        if st["images"][split] >= (int(CAP_OVR.get(src, CAP)) if split == "train" else EVAL_CAP):
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


def _boxes_from_yolo_txt(txt: str, names: list) -> list:
    """YOLO rows: 'c cx cy w h' or a polygon 'c x1 y1 x2 y2 ...' (segmentation export) -> mapped boxes."""
    out = []
    for r in txt.splitlines():
        v = r.split()
        if len(v) < 5:
            continue
        t = map_name(str(names[int(v[0])])) if int(v[0]) < len(names) else None
        if not t:
            continue
        f = list(map(float, v[1:]))
        if len(f) == 4:
            out.append((t, *f))
        else:
            xs, ys = f[0::2], f[1::2]
            out.append((t, (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)))
    return out


def yolo_tree(w: Writer, src: str, root: Path, manifest: list, lic: str, label: str, hash_split: bool = False):
    """Any YOLO export: data.yaml somewhere for names; images/ + labels/ siblings; split from the path."""
    ymls = sorted(root.rglob("data.yaml")) or sorted(root.rglob("*.yaml"))
    raw = yaml.safe_load(ymls[0].read_text()) if ymls else {}
    names = raw.get("names", [])
    names = [names[k] for k in sorted(names)] if isinstance(names, dict) else list(names)
    n = 0
    for img in sorted(p for p in root.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png") and "images" in p.parts):
        parts = list(img.parts)
        i = len(parts) - 1 - parts[::-1].index("images")
        lab = Path(*parts[:i], "labels", *parts[i + 1:]).with_suffix(".txt")
        boxes = _boxes_from_yolo_txt(lab.read_text(), names) if lab.exists() else []
        sp = next((s for s in ("train", "valid", "val", "test") if s in [x.lower() for x in parts]), None)
        sp = split_for(f"{src}-{img.stem}") if hash_split else ({"valid": "val"}.get(sp, sp) or split_for(f"{src}-{img.stem}"))
        w.add(src, sp, re.sub(r"[^A-Za-z0-9]+", "-", img.stem)[:60] + f"-{n}", img.read_bytes(), boxes)
        n += 1
    manifest.append({"source": label, "licence": lic, "source_names": names, "files_seen": n})


def hf_files(repo: str, patterns: list[str], dest: Path, per_dir_cap: int) -> Path:
    """Download a capped subset of a large HF image repo one file at a time with backoff (HF 429s on bursts)."""
    import time
    from huggingface_hub import HfApi, hf_hub_download
    files = HfApi().list_repo_files(repo, repo_type="dataset")
    pick, seen = [], {}
    for f in sorted(files, key=lambda x: hashlib.md5(x.encode()).hexdigest()):
        if not any(re.search(p, f) for p in patterns):
            continue
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            k = str(Path(f).parent)
            if seen.get(k, 0) >= per_dir_cap:
                continue
            seen[k] = seen.get(k, 0) + 1
            stem = str(Path(f).with_suffix(""))
            pick += [f] + [x for x in files if x.startswith(stem.replace("/images/", "/labels/")) and x.endswith(".txt")]
        elif f.endswith((".yaml", ".md", ".json")) and f.count("/") <= 3:
            pick.append(f)
    print("hf_files", repo, len(pick), "files", dict(list(seen.items())[:12]), flush=True)
    for f in pick:
        for attempt in range(6):
            try:
                hf_hub_download(repo, f, repo_type="dataset", local_dir=str(dest))
                break
            except Exception as e:
                if "429" in str(e) and attempt < 5:
                    time.sleep(30 * (attempt + 1))
                    continue
                print("hf_files skip", f, str(e)[:120], flush=True)
                break
    return dest


def epdcl(w: Writer, manifest: list):
    d = hf_files("EPDCL/pd-defect", [r"^pole_detection/", r"^vegetation_conductor/"], BASE / "epdcl",
                 per_dir_cap=max(CAP, EVAL_CAP))
    for sub in ("pole_detection", "vegetation_conductor"):
        root = d / sub
        if root.exists():
            readme = root / "README.md"
            print("epdcl", sub, (readme.read_text()[:1200] if readme.exists() else "no README"), flush=True)
            if sub == "vegetation_conductor":
                coco_dir(w, "epdclvege", root, manifest, "CC BY 4.0", f"hf:EPDCL/pd-defect/{sub}")
            else:
                yolo_tree(w, "epdcl" + sub.split("_")[0][:4], root, manifest, "CC BY 4.0", f"hf:EPDCL/pd-defect/{sub}")


def coco_dir(w: Writer, src: str, root: Path, manifest: list, lic: str, label: str):
    """COCO json(s) with boxes or polygons; images looked up by file name under the same tree; hash split."""
    imgs = {p.name: p for p in root.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    cats_all, n = set(), 0
    for jf in sorted(root.rglob("*.json")):
        try:
            coco = json.loads(jf.read_text())
        except Exception:
            continue
        if not isinstance(coco, dict) or "annotations" not in coco or "images" not in coco:
            continue
        cats = {c["id"]: c["name"] for c in coco.get("categories", [])}
        cats_all |= set(cats.values())
        anns = {}
        for a in coco["annotations"]:
            anns.setdefault(a["image_id"], []).append(a)
        for im in coco["images"]:
            p = imgs.get(Path(im["file_name"]).name)
            if not p:
                continue
            W, H = im["width"], im["height"]
            boxes = []
            for a in anns.get(im["id"], []):
                t = map_name(cats.get(a["category_id"], ""))
                if not t:
                    continue
                if a.get("bbox"):
                    x, y, bw, bh = a["bbox"]
                else:
                    seg = [v for poly in a.get("segmentation", []) for v in poly]
                    if not seg:
                        continue
                    xs, ys = seg[0::2], seg[1::2]
                    x, y, bw, bh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
                boxes.append((t, (x + bw / 2) / W, (y + bh / 2) / H, bw / W, bh / H))
            w.add(src, split_for(f"{src}-{p.stem}"), re.sub(r"[^A-Za-z0-9]+", "-", p.stem)[:60], p.read_bytes(), boxes)
            n += 1
    manifest.append({"source": label, "licence": lic, "source_names": sorted(cats_all), "files_seen": n})


def download(url: str, dest: Path) -> Path:
    if not dest.exists() or dest.stat().st_size == 0:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sSL", "--retry", "5", "--retry-delay", "10", "-o", str(dest), url], check=True)
    print("downloaded", dest.name, round(dest.stat().st_size / 1e6, 1), "MB", flush=True)
    return dest


def railfod23(w: Writer, manifest: list):
    """COCO json(s) inside one 6.5 GB zip; images are read from the zip without extracting everything."""
    import zipfile
    z = zipfile.ZipFile(download("https://ndownloader.figshare.com/files/43616139", BASE / "RailFOD23_v2.zip"))
    members = z.namelist()
    by_base = {Path(m).name: m for m in members if m.lower().endswith((".jpg", ".jpeg", ".png"))}
    jsons = [m for m in members if m.endswith(".json")]
    print("railfod23 jsons", jsons[:10], "images", len(by_base), flush=True)
    cats_all = set()
    for jm in [j for j in jsons if "train_val" not in j]:
        try:
            coco = json.loads(z.read(jm))
        except Exception:
            continue
        if not isinstance(coco, dict) or "annotations" not in coco:
            continue
        cats = {c["id"]: c["name"] for c in coco.get("categories", [])}
        cats_all |= set(cats.values())
        anns = {}
        for a in coco["annotations"]:
            anns.setdefault(a["image_id"], []).append(a)
        low = jm.lower()
        sp = "test" if "test" in low else "val" if "val" in low else "train" if "train" in low else None
        for im in coco["images"]:
            m = by_base.get(Path(im["file_name"]).name)
            if not m:
                continue
            W, H = im["width"], im["height"]
            boxes = []
            for a in anns.get(im["id"], []):
                t = map_name(cats.get(a["category_id"], ""))
                x, y, bw, bh = a["bbox"]
                if t:
                    boxes.append((t, (x + bw / 2) / W, (y + bh / 2) / H, bw / W, bh / H))
            w.add("railfod", split_for(f"railfod-{im['file_name']}"), Path(im["file_name"]).stem[:60], z.read(m), boxes)
    manifest.append({"source": "figshare:RailFOD23 (24180738)", "licence": "CC BY 4.0", "source_names": sorted(cats_all),
                     "note": "railway transmission-line foreign objects; part of the set is synthesised (paper)"})


def vpmbgi(w: Writer, manifest: list):
    import zipfile
    z = download("https://github.com/phd-benel/VPMBGI/releases/download/dataset/iraset.v1i.yolov7pytorch.1.zip",
                 BASE / "vpmbgi.zip")
    d = BASE / "vpmbgi"
    if not d.exists():
        zipfile.ZipFile(z).extractall(d)
    yolo_tree(w, "vpmbgi", d, manifest, "CC BY 4.0", "github:phd-benel/VPMBGI", hash_split=True)


def corrosion(w: Writer, manifest: list):
    from huggingface_hub import snapshot_download
    d = Path(snapshot_download("LibreYOLO/corrosion-bi3q3", repo_type="dataset", local_dir=str(BASE / "corrosion"),
                               max_workers=2))
    yolo_tree(w, "corros", d, manifest, "CC BY 4.0", "hf:LibreYOLO/corrosion-bi3q3 (Roboflow 100)")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    w, manifest = Writer(), []
    for fn, args in ((cplid, ()), *((hf_parquet, a) for a in HF), (roboflow, ()), (epdcl, ()), (railfod23, ()),
                     (vpmbgi, ()), (corrosion, ())):
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
