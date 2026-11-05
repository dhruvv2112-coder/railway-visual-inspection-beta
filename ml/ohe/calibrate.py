"""Confidence calibration for the OHE detector (HLD confidence vector, "C" calibrated).

Runs the exported ONNX detector through the backend adapter (same code path as the server) on the held-out TEST split,
marks every detection as correct (same class, IoU >= 0.5 with an unmatched ground-truth box) or not, and fits Platt
scaling per class: p = sigmoid(a * logit(score) + b). Quality is reported on a half the fit never saw (ECE before/after),
then the final map is fitted on the whole test split. Public data only: not a railway calibration.

usage: python calibrate.py <reports dir with ohe_detector.onnx> <ohe_yolo dir> <out json>"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.ohe.pipeline import OnnxYoloDetector  # noqa: E402


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


def logit(s):
    s = np.clip(np.asarray(s, float), 1e-6, 1 - 1e-6)
    return np.log(s / (1 - s))


def platt(scores, labels, iters=100, l2=1e-3):
    """Logistic regression on logit(score) by Newton's method (tiny L2 for stability)."""
    x, y = logit(scores), np.asarray(labels, float)
    a, b = 1.0, 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(a * x + b)))
        w = p * (1 - p)
        g = np.array([np.sum((p - y) * x) + l2 * a, np.sum(p - y)])
        h = np.array([[np.sum(w * x * x) + l2, np.sum(w * x)], [np.sum(w * x), np.sum(w) + 1e-9]])
        step = np.linalg.solve(h, g)
        a, b = a - step[0], b - step[1]
        if np.abs(step).max() < 1e-7:
            break
    return float(a), float(b)


def apply(a, b, s):
    return 1 / (1 + np.exp(-(a * logit(s) + b)))


def ece(p, y, bins=10):
    p, y = np.asarray(p, float), np.asarray(y, float)
    e = 0.0
    for lo in np.linspace(0, 1, bins, endpoint=False):
        m = (p >= lo) & (p < lo + 1 / bins)
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e)


def main():
    rep, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    names = json.loads((rep / "ohe_detector.names.json").read_text())
    det = OnnxYoloDetector(str(rep / "ohe_detector.onnx"), names)
    rows = {n: [] for n in names}          # cls -> [(score, correct, image_index)]
    missed = {n: 0 for n in names}
    imgs = sorted((data / "test" / "images").iterdir())
    for k, ip in enumerate(imgs):
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
                gt.append([names[c], ((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h), False])
        for d in sorted(det.detect(img), key=lambda d: -d.score):
            best, bi = 0.5, None
            for i, g in enumerate(gt):
                if not g[2] and g[0] == d.cls:
                    v = iou(d.box, g[1])
                    if v >= best:
                        best, bi = v, i
            if bi is not None:
                gt[bi][2] = True
            rows[d.cls].append((d.score, bi is not None, k))
        for g in gt:
            missed[g[0]] += not g[2]
        if k % 500 == 0:
            print(f"{k}/{len(imgs)} images", flush=True)
    res = {"method": "platt-per-class", "data": "public held-out test split (training sources); not railway photos",
           "detector": det.version, "images": len(imgs), "iou": 0.5, "min_score": det.conf, "classes": {}, "report": {}}
    for c, r in rows.items():
        if len(r) < 30 or len({x[1] for x in r}) < 2:
            res["report"][c] = {"detections": len(r), "skipped": "too few detections to calibrate"}
            continue
        s, y, im = (np.array([x[i] for x in r]) for i in range(3))
        fit, hold = im % 2 == 0, im % 2 == 1          # split by image so boxes of one photo stay together
        a, b = platt(s[fit], y[fit])
        rep_c = {"detections": len(r), "precision_at_threshold": round(float(y.mean()), 4), "missed_boxes": missed[c],
                 "ece_raw_holdout": round(ece(s[hold], y[hold]), 4), "ece_calibrated_holdout": round(ece(apply(a, b, s[hold]), y[hold]), 4)}
        a, b = platt(s, y)
        res["classes"][c] = {"a": round(a, 5), "b": round(b, 5)}
        res["report"][c] = rep_c
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
