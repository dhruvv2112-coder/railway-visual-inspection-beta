"""Train the OHE component detector (HLD §6.5 step 2), evaluate per class on the held-out test split, export ONNX
for the backend adapter (backend/app/ohe/pipeline.py OnnxYoloDetector) and write a benchmark report.

  CI (CPU):       OHE_EPOCHS=25 OHE_IMGSZ=640 python train_detector.py
  RTX 5070:       OHE_DEVICE=0 OHE_EPOCHS=100 OHE_IMGSZ=960 OHE_MODEL=yolo11s.pt python train_detector.py
Models: yolo11n/s (AGPL-3.0, benchmark reference / mobile challenger per HLD §6.2). The HLD core baseline
RT-DETRv2-R18 (Apache-2.0) bake-off is the next GPU step (not yet implemented)."""
import json
import os
import shutil
import time
from pathlib import Path

import yaml
from ultralytics import YOLO

DATA = Path(os.environ.get("OHE_DATA", ".cache/ohe")) / "ohe_yolo"
REPORTS = Path(os.environ.get("RVI_REPORTS", "reports"))
MODEL = os.environ.get("OHE_MODEL", "yolo11n.pt")
EPOCHS = int(os.environ.get("OHE_EPOCHS", "25"))
IMGSZ = int(os.environ.get("OHE_IMGSZ", "640"))
DEVICE = os.environ.get("OHE_DEVICE", "cpu")


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load((DATA / "data.yaml").read_text())
    if not any((DATA / "val" / "images").glob("*")):
        cfg["val"] = "test/images"
        (DATA / "data.yaml").write_text(yaml.safe_dump(cfg))
    names = cfg["names"]
    t = time.perf_counter()
    m = YOLO(MODEL)
    m.train(data=str(DATA / "data.yaml"), epochs=EPOCHS, imgsz=IMGSZ, device=DEVICE, batch=16 if DEVICE == "cpu" else 16,
            workers=2, seed=0, deterministic=True, plots=False, verbose=False, project=str(DATA / "runs"), name="det", exist_ok=True)
    minutes = (time.perf_counter() - t) / 60
    best = YOLO(str(DATA / "runs" / "det" / "weights" / "best.pt"))
    r = best.val(data=str(DATA / "data.yaml"), split="test", imgsz=IMGSZ, device=DEVICE, plots=False, verbose=False)
    rows = []
    for i, c in enumerate(r.box.ap_class_index):
        p, rc, ap50, ap = r.box.class_result(i)
        rows.append({"class": names[int(c)], "precision": float(p), "recall": float(rc), "AP50": float(ap50), "AP50_95": float(ap)})
    rows.append({"class": "all", "precision": float(r.box.mp), "recall": float(r.box.mr), "AP50": float(r.box.map50),
                 "AP50_95": float(r.box.map)})
    onnx = Path(best.export(format="onnx", imgsz=IMGSZ, simplify=True))
    out = REPORTS / "ohe_detector.onnx"
    shutil.copy(onnx, out)
    (REPORTS / "ohe_detector.names.json").write_text(json.dumps(names))
    manifest = json.loads((DATA / "manifest.json").read_text())
    rep = {"name": "ohe_detector", "title": f"OHE component detector ({Path(MODEL).stem}, {EPOCHS} ep, {IMGSZ}px, {DEVICE})",
           "summary": f"Held-out test split per class. Training {minutes:.1f} min. Sources: "
                      + "; ".join(f"{s.get('source')} ({s.get('licence', s.get('error') or s.get('skipped'))})" for s in manifest["sources"])
                      + f". Images per source: {json.dumps({k: v['images'] for k, v in manifest['stats'].items()})}",
           "results": rows,
           "extra": {"manifest": manifest, "onnx_mb": round(out.stat().st_size / 1e6, 1), "imgsz": IMGSZ},
           "notes": ["Public data are drone views of transmission lines, not ground-level 25 kV railway OHE: results show the "
                     "pipeline works and give starting weights; they are not field performance (HLD §12.1).",
                     "Per-class results only; overall mAP does not certify any defect family (HLD §15.1).",
                     f"{Path(MODEL).stem} is AGPL-3.0 (Ultralytics). The HLD core baseline is RT-DETRv2-R18 (Apache-2.0)."]}
    (REPORTS / "ohe_detector.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
