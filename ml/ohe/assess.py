"""Photo-angle (perspective) check for HLD cascade stage 1 (assessability).
Data: EPDCL/pd-defect perspective_validation (CC BY 4.0) – field smartphone photos, folders 'accepted' (valid view)
and 'rejected_perspective_issue' (perspective-distorted), three subtasks (full image, pole-top crop, DTR scene).
Model: torchvision MobileNetV3-small (ImageNet weights, BSD-3), fine-tuned at 224 px on CPU; ONNX export.
Output: reports/ohe_assess.{onnx,json} – accuracy, F1 and per-subtask results on the test split."""
import hashlib
import json
import os
import random
import re
import time
from pathlib import Path

import numpy as np
import torch
import torchvision
from PIL import Image, ImageOps
from sklearn.metrics import f1_score, precision_recall_fscore_support

from prepare_data import BASE, hf_files

REPORTS = Path(os.environ.get("RVI_REPORTS", "reports"))
EPOCHS = int(os.environ.get("OHE_ASSESS_EPOCHS", "8"))
SIZE = 224
torch.manual_seed(0)
random.seed(0)
LABELS = {"accepted": 0, "rejected_perspective_issue": 1}


def collect():
    d = hf_files("EPDCL/pd-defect", [r"^perspective_validation/"], BASE / "epdcl_pv", per_dir_cap=100000)
    rows = []
    for p in sorted((d / "perspective_validation").rglob("*")):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        parts = [x.lower() for x in p.relative_to(d / "perspective_validation").parts]
        lab = next((LABELS[x] for x in parts if x in LABELS), None)
        if lab is None:
            continue
        split = next(({"valid": "val", "validation": "val"}.get(x, x) for x in parts if x in ("train", "valid", "val", "validation", "test")), None)
        if split is None:
            h = int(hashlib.md5(p.name.encode()).hexdigest(), 16) % 100
            split = "train" if h < 70 else "val" if h < 85 else "test"
        rows.append({"path": str(p), "label": lab, "split": split, "subtask": parts[0] if len(parts) > 2 else "all"})
    return rows


class DS(torch.utils.data.Dataset):
    def __init__(self, rows, train):
        self.rows = rows
        aug = [torchvision.transforms.RandomResizedCrop(SIZE, scale=(0.7, 1.0), ratio=(0.6, 1.6)),
               torchvision.transforms.ColorJitter(0.3, 0.3, 0.2)] if train else [torchvision.transforms.Resize((SIZE, SIZE))]
        # no flips or rotations: they would change the very geometry being judged
        self.tf = torchvision.transforms.Compose(aug + [torchvision.transforms.ToTensor(),
                                                        torchvision.transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        im = ImageOps.exif_transpose(Image.open(r["path"])).convert("RGB")
        if not self.tf.transforms[0].__class__.__name__.startswith("Random"):
            im = im.resize((SIZE, SIZE))
        return self.tf(im), r["label"]


def predict(model, rows):
    dl = torch.utils.data.DataLoader(DS(rows, False), batch_size=64, num_workers=2)
    ps = []
    model.eval()
    with torch.no_grad():
        for x, _ in dl:
            ps += torch.softmax(model(x), 1)[:, 1].tolist()
    return np.array(ps)


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows = collect()
    counts = {}
    for r in rows:
        k = f"{r['subtask']}/{r['split']}/{'distorted' if r['label'] else 'valid'}"
        counts[k] = counts.get(k, 0) + 1
    print("counts", json.dumps(counts, indent=1), flush=True)
    tr, va, te = ([r for r in rows if r["split"] == s] for s in ("train", "val", "test"))
    if not te:
        te, va = va, []
    m = torchvision.models.mobilenet_v3_small(weights=torchvision.models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    m.classifier[3] = torch.nn.Linear(m.classifier[3].in_features, 2)
    w = torch.tensor([1.0, max(1.0, sum(1 for r in tr if r["label"] == 0) / max(1, sum(1 for r in tr if r["label"] == 1)))])
    opt = torch.optim.AdamW(m.parameters(), lr=3e-4, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
    dl = torch.utils.data.DataLoader(DS(tr, True), batch_size=32, shuffle=True, num_workers=2)
    t0, best, best_state = time.time(), -1.0, None
    for ep in range(EPOCHS):
        m.train()
        for x, y in dl:
            opt.zero_grad()
            torch.nn.functional.cross_entropy(m(x), y, weight=w).backward()
            opt.step()
        sched.step()
        if va:
            f1 = f1_score([r["label"] for r in va], predict(m, va) >= 0.5)
            print(f"epoch {ep + 1} val F1 {f1:.3f}", flush=True)
            if f1 > best:
                best, best_state = f1, {k: v.clone() for k, v in m.state_dict().items()}
    if best_state:
        m.load_state_dict(best_state)
    # threshold: best F1 on validation (falls back to 0.5)
    thr = 0.5
    if va:
        pv, yv = predict(m, va), [r["label"] for r in va]
        thr = max(np.arange(0.2, 0.81, 0.05), key=lambda t: f1_score(yv, pv >= t))
    pt, yt = predict(m, te), np.array([r["label"] for r in te])
    pred = pt >= thr
    p, rc, f1, _ = precision_recall_fscore_support(yt, pred, average="binary", zero_division=0)
    per = {}
    for st in sorted({r["subtask"] for r in te}):
        idx = [i for i, r in enumerate(te) if r["subtask"] == st]
        per[st] = {"n": len(idx), "accuracy": float((pred[idx] == yt[idx]).mean()),
                   "f1_distorted": float(f1_score(yt[idx], pred[idx], zero_division=0))}
    m.eval()
    torch.onnx.export(m, torch.zeros(1, 3, SIZE, SIZE), str(REPORTS / "ohe_assess.onnx"), input_names=["image"],
                      output_names=["logits"], opset_version=17, dynamic_axes={"image": {0: "n"}, "logits": {0: "n"}})
    rep = {"name": "ohe_assess", "title": f"Photo-angle check (MobileNetV3-small, {EPOCHS} ep, {SIZE}px, CPU)",
           "threshold": float(thr), "classes": ["valid", "perspective_distorted"],
           "summary": f"EPDCL perspective_validation; train {len(tr)}, val {len(va)}, test {len(te)}; "
                      f"{(time.time() - t0) / 60:.1f} min.",
           "results": [{"metric": "accuracy (test)", "value": float((pred == yt).mean())},
                       {"metric": "precision, distorted", "value": float(p)}, {"metric": "recall, distorted", "value": float(rc)},
                       {"metric": "F1, distorted", "value": float(f1)}],
           "per_subtask_test": per, "counts": counts,
           "notes": ["Distribution poles photographed by APEPDCL linemen; railway masts need their own validation.",
                     "Used only to ask for a retake ('square-on'); it never changes an assessment."]}
    (REPORTS / "ohe_assess.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
