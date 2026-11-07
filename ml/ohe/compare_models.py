"""Score detectors on the SAME held-out test photos through the backend adapter (what the laptop runs), per class
and per source, upright and turned 90 degrees. Precision / recall at the server threshold and AP50 (IoU 0.5).
usage: python compare_models.py <ohe_yolo dir> <out.json> name=<dir with ohe_detector.onnx> [name=<dir> ...]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.ohe.pipeline import OnnxYoloDetector, RotationTTA, Routed, Sectioned  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate import iou  # noqa: E402


def ap50(scored, n_gt):
    if n_gt == 0 or not scored:
        return None
    scored = sorted(scored, key=lambda t: -t[0])
    tp = np.cumsum([c for _, c in scored])
    prec = tp / np.arange(1, len(scored) + 1)
    rec = tp / n_gt
    ap, last = 0.0, 0.0
    for r in np.linspace(0, 1, 101):          # COCO-style 101-point interpolation
        p = prec[rec >= r].max() if (rec >= r).any() else 0.0
        ap += p / 101
    return round(float(ap), 4)


def score(det, data: Path, rotate: bool, conf_server: float = 0.25):
    names = det.names
    by = defaultdict(lambda: {"scored": [], "gt": 0, "tp": 0, "fp": 0})
    imgs = sorted((data / "test" / "images").iterdir())
    for ip in imgs:
        img = cv2.imread(str(ip))
        if img is None:
            continue
        h, w = img.shape[:2]
        gt = []
        lp = data / "test" / "labels" / (ip.stem + ".txt")
        for line in (lp.read_text().splitlines() if lp.exists() else []):
            p = line.split()
            if len(p) >= 5:
                c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:5])
                b = ((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h)
                if rotate:   # 90 deg clockwise: (x, y) -> (h - y, x)
                    b = (h - b[3], b[0], h - b[1], b[2])
                gt.append([names[c], b, False])
        if rotate:
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        src = ip.name.split("_")[0]
        for g in gt:
            by[(g[0], src)]["gt"] += 1
        for d in sorted(det.detect(img), key=lambda d: -d.score):
            best, bi = 0.5, None
            for i, g in enumerate(gt):
                if not g[2] and g[0] == d.cls:
                    v = iou(d.box, g[1])
                    if v >= best:
                        best, bi = v, i
            if bi is not None:
                gt[bi][2] = True
            k = by[(d.cls, src)]
            k["scored"].append((d.score, bi is not None))
            if d.score >= conf_server:
                k["tp" if bi is not None else "fp"] += 1
    def summ(rows):
        s = [x for r in rows for x in r["scored"]]
        g, tp, fp = sum(r["gt"] for r in rows), sum(r["tp"] for r in rows), sum(r["fp"] for r in rows)
        return {"gt": g, "precision": round(tp / (tp + fp), 4) if tp + fp else None, "recall": round(tp / g, 4) if g else None,
                "AP50": ap50(s, g)}
    classes = sorted({k[0] for k in by})
    out = {"per_class": {c: summ([v for k, v in by.items() if k[0] == c]) for c in classes},
           "per_source": {f"{c}@{s}": summ([v]) for (c, s), v in sorted(by.items()) if v["gt"]}}
    aps = [v["AP50"] for v in out["per_class"].values() if v["AP50"] is not None]
    out["mAP50"] = round(float(np.mean(aps)), 4) if aps else None
    return out


def main():
    data, outp = Path(sys.argv[1]), Path(sys.argv[2])
    res = {}
    import os
    tta = os.environ.get("CMP_TTA") == "1"   # deployment mode: 8 rotations merged, as the laptop server runs
    load = lambda d: OnnxYoloDetector(str(Path(d) / "ohe_detector.onnx"), json.loads((Path(d) / "ohe_detector.names.json").read_text()), conf=0.05)
    for arg in sys.argv[3:]:
        name, d = arg.split("=", 1)
        if d.startswith("route:"):   # route:<dirA>,<dirB>,<classes from B separated by |>
            a, b, cls = d[6:].split(",")
            det = Routed(load(a), load(b), set(cls.split("|")))
        else:
            det = load(d)
        if name.endswith("+sections"):   # sections only (no rotation merge), as the server with rotation_views=1
            det = Sectioned(det, full_angles=(0,), tile_angles=(0,))
        elif name.endswith("+rot4"):    # four right-angle views only (no 45-degree views)
            det = RotationTTA(det, angles=(0, 90, 180, 270))
        elif tta:
            det = RotationTTA(det)
        det.names = getattr(det, "names", None) or getattr(getattr(det, "base", None), "names", None) or det.full.base.names
        res[name] = {"upright": score(det, data, False), "rotated_90": score(det, data, True)}
        print(name, "upright mAP50", res[name]["upright"]["mAP50"], "rotated mAP50", res[name]["rotated_90"]["mAP50"], flush=True)
    outp.write_text(json.dumps(res, indent=1))
    names = list(res)
    classes = sorted({c for n in names for c in res[n]["upright"]["per_class"]})
    for view in ("upright", "rotated_90"):
        print(f"\n{view}: class | " + " | ".join(f"{n} P/R/AP50" for n in names))
        for c in classes:
            print(c, "|", " | ".join("{}/{}/{}".format(*(res[n][view]["per_class"].get(c, {}).get(k) for k in ("precision", "recall", "AP50"))) for n in names))


if __name__ == "__main__":
    main()
