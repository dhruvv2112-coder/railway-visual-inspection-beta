"""Unknown-defect branch (HLD §6.2, §6.5 step 5): PatchCore-style memory bank built ONLY from normal insulator crops
(no defect box inside), scored on held-out normal vs defective crops. Output is anomaly evidence, not a diagnosis.

Feature extractor: torchvision ResNet-18 (BSD-3, ImageNet weights) layers 2+3, 3x3 neighbourhood average,
random coreset. Metric: image-level AUROC on test crops; threshold = 95th percentile of validation normal scores."""
import json
import os
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
import torchvision
from sklearn.metrics import roc_auc_score

DATA = Path(os.environ.get("OHE_DATA", ".cache/ohe")) / "ohe_yolo"
REPORTS = Path(os.environ.get("RVI_REPORTS", "reports"))
INS, DEF = 0, 1  # class indices in ohe_yolo (insulator, insulator_defect)
torch.manual_seed(0)
np.random.seed(0)


def crops(split: str):
    """Yield (crop, is_defective) for every insulator box; defective if a defect box centre lies inside it."""
    for lab in sorted((DATA / split / "labels").glob("*.txt")):
        img_p = next((DATA / split / "images").glob(lab.stem + ".*"), None)
        rows = [list(map(float, r.split())) for r in lab.read_text().split("\n") if r.strip()]
        ins = [r for r in rows if int(r[0]) == INS]
        dfs = [r for r in rows if int(r[0]) == DEF]
        if not ins or img_p is None:
            continue
        img = cv2.imread(str(img_p))
        h, w = img.shape[:2]
        for _, cx, cy, bw, bh in ins:
            x1, y1, x2, y2 = int((cx - bw / 2) * w), int((cy - bh / 2) * h), int((cx + bw / 2) * w), int((cy + bh / 2) * h)
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
            if min(x2 - x1, y2 - y1) < 24:
                continue
            bad = any(x1 <= dx * w <= x2 and y1 <= dy * h <= y2 for _, dx, dy, _, _ in dfs)
            yield cv2.resize(img[y1:y2, x1:x2], (224, 224)), bad


class Features(torch.nn.Module):
    def __init__(self):
        super().__init__()
        m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1).eval()
        self.stem = torch.nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
        self.l2, self.l3 = m.layer2, m.layer3
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

    @torch.no_grad()
    def forward(self, bgr: np.ndarray) -> torch.Tensor:
        x = torch.from_numpy(bgr[:, :, ::-1].copy()).permute(2, 0, 1)[None].float() / 255
        f2 = self.l2(self.stem((x - self.mean) / self.std))
        f3 = self.l3(f2)
        f = torch.cat([F.avg_pool2d(f2, 3, 1, 1), F.interpolate(F.avg_pool2d(f3, 3, 1, 1), size=f2.shape[-2:], mode="bilinear")], 1)
        return f[0].permute(1, 2, 0).reshape(-1, f.shape[1])  # patches x dims


def railway_eval(fx) -> list:
    """Same method on real railway catenary support components (github jsxr32/EBIST_cscuav, MVTec layout:
    train/good, test/good, test/<defect>). Licence not stated by the authors: used for evaluation only.
    Per component: bank from its own train/good crops; AUROC of test good vs defective."""
    import subprocess
    import zipfile
    d = DATA.parent / "ebist"
    try:
        if not d.exists():
            subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/jsxr32/EBIST_cscuav", str(d / "repo")], check=True)
            zipfile.ZipFile(next((d / "repo").glob("*.zip"))).extractall(d)
    except Exception as e:
        return [{"error": str(e)[:200]}]
    out = []
    for comp in sorted(p for p in d.rglob("*") if p.is_dir() and (p / "train" / "good").is_dir()):
        def load(ps):
            return [cv2.resize(cv2.imread(str(x)), (224, 224)) for x in sorted(ps)]
        good = load((comp / "train" / "good").glob("*.png"))
        if not good:
            continue
        bank = torch.cat([fx(c) for c in good])
        t = [(c, 0) for c in load((comp / "test" / "good").glob("*.png"))]
        defect_dirs = [x for x in (comp / "test").iterdir() if x.is_dir() and x.name != "good"]
        for dd in defect_dirs:
            t += [(c, 1) for c in load(dd.glob("*.png"))]
        sc = [float(torch.cdist(fx(c), bank).min(1).values.max()) for c, _ in t]
        y = [b for _, b in t]
        out.append({"component": comp.name, "defect": ",".join(x.name for x in defect_dirs), "train_good": len(good),
                    "test_good": len(y) - sum(y), "test_defect": sum(y),
                    "AUROC": roc_auc_score(y, sc) if 0 < sum(y) < len(y) else float("nan")})
    return out


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    fx = Features()
    train = [c for c, bad in crops("train") if not bad]
    bank = torch.cat([fx(c) for c in train[:400]])
    keep = torch.randperm(len(bank))[: max(2000, len(bank) // 10)]
    bank = bank[keep]

    def score(c):
        d = torch.cdist(fx(c), bank).min(1).values
        return float(d.max())

    val_normal = [score(c) for c, bad in crops("val") if not bad]
    test = [(score(c), bad) for c, bad in crops("test")]
    thr = float(np.percentile(val_normal, 95)) if val_normal else float("nan")
    y = [int(b) for _, b in test]
    s = [v for v, _ in test]
    auroc = roc_auc_score(y, s) if 0 < sum(y) < len(y) else float("nan")
    tpr = float(np.mean([v > thr for v, b in test if b])) if sum(y) else float("nan")
    fpr = float(np.mean([v > thr for v, b in test if not b])) if len(y) - sum(y) else float("nan")
    rep = {"name": "ohe_anomaly", "title": "Insulator anomaly branch (PatchCore-style, ResNet-18 features, insulator crops from all detector sources)",
           "summary": f"Memory bank from {len(train[:400])} normal training crops ({len(bank)} patches). Test: {len(y) - sum(y)} normal, "
                      f"{sum(y)} defective crops.",
           "results": [{"metric": "AUROC (test crops)", "value": auroc},
                       {"metric": "Defective flagged at val-normal p95 threshold", "value": tpr},
                       {"metric": "Normal flagged at the same threshold", "value": fpr},
                       {"metric": "Threshold (anomaly distance)", "value": thr}],
           "notes": ["Anomaly score is evidence of difference from the normal bank, not a defect class (HLD §6.2).",
                     "CPLID 'defect' marks missing insulator caps on transmission lines; railway OHE insulators need their own bank.",
                     "railway_catenary_components: real railway cantilever parts (EBIST_cscuav), about 10 images per split; "
                     "small-sample indicator, evaluation only (licence not stated)."]}
    rep["railway_catenary_components"] = railway_eval(fx)
    (REPORTS / "ohe_anomaly.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
