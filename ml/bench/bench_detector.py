"""Defect detection: do pre-trained models work 'as stitched' or must we fine-tune?
Data: Indian railway track defects (Mendeley 88sh5y3tmj v2, CC BY 4.0), seeded 80/10/10 split.
A) Zero-shot open-vocabulary detectors with class-name prompts: OWLv2 (Apache-2.0), Grounding DINO tiny (Apache-2.0).
B) Quick CPU fine-tune of YOLO11n (AGPL-3.0, benchmark reference) and evaluation on clean + degraded test sets.
Metrics: mAP@50, mAP@50:95 (torchmetrics / COCO protocol), per-class AP50, latency."""
import os
import shutil
import time
from pathlib import Path

import albumentations as A
import cv2
import numpy as np
import torch
from PIL import Image
from torchmetrics.detection import MeanAveragePrecision

from common import DATA, write_report
from railds import build

ZS_N = int(os.environ.get("ZS_N", 200))
EPOCHS = int(os.environ.get("FT_EPOCHS", 8))
FRACTION = float(os.environ.get("FT_FRACTION", 0.4))
IMGSZ = int(os.environ.get("FT_IMGSZ", 416))
DEVICE = os.environ.get("RVI_DEVICE", "cpu")  # "cuda" on the RTX 5070 laptop
TORCH_DEV = "cuda" if DEVICE in ("cuda", "0") else "cpu"


def load_split(yaml_path, split, limit=None):
    root = Path(yaml_path).parent / split
    out = []
    for im in sorted((root / "images").iterdir())[:limit]:
        lab = root / "labels" / (im.stem + ".txt")
        w, h = Image.open(im).size
        boxes, cls = [], []
        for l in lab.read_text().splitlines() if lab.exists() else []:
            c, x, y, bw, bh = map(float, l.split()[:5])
            boxes.append([(x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h])
            cls.append(int(c))
        out.append((im, torch.tensor(boxes).reshape(-1, 4), torch.tensor(cls, dtype=torch.long)))
    return out


PROMPTS = {"Broken-rail": "broken rail", "Corrosion": "corroded rail", "Cracks": "crack on rail", "Flakings": "flaking on rail head",
           "Joints": "rail joint", "Missing-fastener": "missing rail fastener clip", "Shelling": "shelling on rail head",
           "Spalling": "spalling on rail", "Squats": "squat defect on rail head", "Wheel-burn": "wheel burn on rail"}


def prompt(name):
    return PROMPTS.get(name, name.replace("_", " ").replace("-", " ").lower())


def match_label(text, labels):
    """Grounding DINO returns the matched sub-phrase (e.g. 'crack' or 'rail'); map it to the prompt with most shared words."""
    if text in labels:
        return labels.index(text)
    w = set(str(text).split()) - {"on", "rail", "head", "of", "the"}
    best = max(range(len(labels)), key=lambda i: len(w & set(labels[i].split())))
    return best if w & set(labels[best].split()) else -1


def zero_shot(model_id, data, names):
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
    proc = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).eval().to(TORCH_DEV)
    labels = [prompt(n) for n in names]
    metric = MeanAveragePrecision(iou_type="bbox", class_metrics=True)
    agnostic = MeanAveragePrecision(iou_type="bbox")  # "is there a defect here at all", ignoring class
    lat, n_pred = [], 0
    for im_path, gt_b, gt_c in data:
        im = Image.open(im_path).convert("RGB")
        t = time.perf_counter()
        with torch.no_grad():
            if "grounding" in model_id:
                inputs = proc(images=im, text=". ".join(labels) + ".", return_tensors="pt").to(TORCH_DEV)
                out = model(**inputs)
                r = proc.post_process_grounded_object_detection(out, inputs.input_ids, threshold=0.2, text_threshold=0.2,
                                                                target_sizes=[im.size[::-1]])[0]
                txt = r.get("text_labels", r.get("labels"))
                cl = [match_label(t, labels) for t in txt]
            else:
                inputs = proc(text=[labels], images=im, return_tensors="pt").to(TORCH_DEV)
                out = model(**inputs)
                # OWLv2 pads to a square before resizing, so boxes must be scaled to the padded square side
                side = max(im.size)
                r = proc.post_process_object_detection(out, threshold=0.1, target_sizes=torch.tensor([[side, side]]))[0]
                cl = r["labels"].tolist()
        lat.append(time.perf_counter() - t)
        r = {k: (v.cpu() if hasattr(v, "cpu") else v) for k, v in r.items()}
        keep = [i for i, c in enumerate(cl) if c >= 0]
        n_pred += len(keep)
        agnostic.update([{"boxes": r["boxes"][keep], "scores": r["scores"][keep], "labels": torch.zeros(len(keep), dtype=torch.long)}],
                        [{"boxes": gt_b, "labels": torch.zeros(len(gt_c), dtype=torch.long)}])
        metric.update([{"boxes": r["boxes"][keep], "scores": r["scores"][keep], "labels": torch.tensor([cl[i] for i in keep], dtype=torch.long)}],
                      [{"boxes": gt_b, "labels": gt_c}])
    m = metric.compute()
    m["agnostic_map_50"] = agnostic.compute()["map_50"]
    m["preds_per_image"] = n_pred / max(len(data), 1)
    return m, float(np.median(lat))


def degraded_copies(yaml_path):
    """Photometric degradations (labels unchanged) emulating trackside conditions."""
    conds = {"dark": A.RandomBrightnessContrast(brightness_limit=(-0.55, -0.55), contrast_limit=(-0.2, -0.2), p=1),
             "motion_blur": A.MotionBlur(blur_limit=(15, 15), p=1),
             "rain": A.RandomRain(brightness_coefficient=0.8, drop_width=2, blur_value=5, p=1),
             "glare": A.RandomSunFlare(flare_roi=(0, 0, 1, 0.5), src_radius=250, p=1)}
    base = Path(yaml_path).parent
    out = {}
    for c, aug in conds.items():
        d = DATA / f"rail_yolo_{c}"
        if not d.exists():
            (d / "test" / "images").mkdir(parents=True)
            shutil.copytree(base / "test" / "labels", d / "test" / "labels")
            for im in (base / "test" / "images").iterdir():
                x = cv2.cvtColor(cv2.imread(str(im)), cv2.COLOR_BGR2RGB)
                cv2.imwrite(str(d / "test" / "images" / im.name), cv2.cvtColor(aug(image=x)["image"], cv2.COLOR_RGB2BGR))
        import yaml
        y = yaml.safe_load(Path(yaml_path).read_text())
        y.update({"path": str(d), "train": "test/images", "val": "test/images", "test": "test/images"})
        (d / "data.yaml").write_text(yaml.safe_dump(y, allow_unicode=True))
        out[c] = d / "data.yaml"
    return out


def main():
    yaml_path, names, stats = build()
    rows, per_class, notes = [], {}, []
    test = load_split(yaml_path, "test", ZS_N)
    for mid in ("google/owlv2-base-patch16-ensemble", "IDEA-Research/grounding-dino-tiny"):
        try:
            m, lat = zero_shot(mid, test, names)
            rows.append({"approach": "zero-shot", "model": mid, "test_set": "clean", "n_images": len(test),
                         "mAP50": float(m["map_50"]), "mAP50_95": float(m["map"]), "median_latency_s": lat,
                         "agnostic_mAP50": float(m["agnostic_map_50"]), "preds_per_image": round(m["preds_per_image"], 2)})
            per_class[mid] = {names[int(c)]: float(a) for c, a in zip(m["classes"].flatten(), m["map_per_class"].flatten())}
        except Exception as e:
            notes.append(f"{mid} failed: {type(e).__name__}: {str(e)[:200]}")
    if os.environ.get("SKIP_FT") == "1":
        write_report("detector_zs", "Zero-shot defect detection (re-run with box-scaling and label-matching fixes)",
                     f"Dataset stats: {stats}.", rows, extra={"per_class_ap50": per_class, "class_names": names}, notes=notes)
        return
    try:
        from ultralytics import YOLO
        model = YOLO("yolo11n.pt")
        t = time.perf_counter()
        model.train(data=str(yaml_path), epochs=EPOCHS, imgsz=IMGSZ, fraction=FRACTION, device=0 if TORCH_DEV == "cuda" else "cpu", batch=16 if TORCH_DEV == "cpu" else 32,
                    workers=2, seed=0, deterministic=True, plots=False, verbose=False, project=str(DATA / "runs"), name="ft", exist_ok=True)
        train_s = time.perf_counter() - t
        best = YOLO(str(DATA / "runs" / "ft" / "weights" / "best.pt"))
        sets = {"clean": yaml_path} | degraded_copies(yaml_path)
        for cond, yp in sets.items():
            r = best.val(data=str(yp), split="test", imgsz=IMGSZ, device=0 if TORCH_DEV == "cuda" else "cpu", plots=False, verbose=False)
            rows.append({"approach": f"fine-tuned ({EPOCHS} ep, {int(FRACTION*100)}% train, {TORCH_DEV.upper()})", "model": "yolo11n",
                         "test_set": cond, "n_images": int(r.seen) if hasattr(r, "seen") else stats["per_split"]["test"],
                         "mAP50": float(r.box.map50), "mAP50_95": float(r.box.map),
                         "median_latency_s": float(r.speed["inference"]) / 1000})
            if cond == "clean":
                per_class["yolo11n-ft"] = {names[i]: float(v) for i, v in zip(r.box.ap_class_index, r.box.ap50)}
        onnx = best.export(format="onnx", imgsz=IMGSZ, simplify=True)
        notes.append(f"YOLO11n fine-tune wall time {train_s/60:.1f} min on {TORCH_DEV.upper()}; ONNX export: {Path(onnx).name} ({Path(onnx).stat().st_size/1e6:.1f} MB)")
        shutil.copy(onnx, Path(os.environ.get("RVI_REPORTS", "reports")) / "yolo11n_rail_ci.onnx")
    except Exception as e:
        notes.append(f"fine-tune failed: {type(e).__name__}: {str(e)[:300]}")
    write_report("detector", "Track-defect detection: zero-shot vs quick fine-tune (Indian railway images)",
                 f"Dataset stats: {stats}.", rows, extra={"per_class_ap50": per_class, "class_names": names},
                 notes=notes + ["CI fine-tune is a feasibility indicator only (CPU, few epochs, data fraction). Full training on RTX 5070: ml/train/train_detector.py.",
                                "YOLO11 is AGPL-3.0: production use needs an Enterprise licence or an Apache-2.0 alternative (RF-DETR, D-FINE).",
                                "Dataset captured by a phone mounted on an inspection vehicle ~0.8 m above the rail (Mordia & Verma 2026); eye-level foot-patrol imagery differs (domain shift)."])


if __name__ == "__main__":
    main()
