"""Load the exported detector through the backend adapter and run it on held-out test images (HLD §6.5 step 8 parity)."""
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.ohe.pipeline import OnnxYoloDetector  # noqa: E402

rep = Path(sys.argv[1])
data = Path(sys.argv[2])
det = OnnxYoloDetector(str(rep / "ohe_detector.onnx"), json.loads((rep / "ohe_detector.names.json").read_text()))
out = []
for img in sorted((data / "test" / "images").glob("cplid_*"))[:20]:
    d = det.detect(cv2.imread(str(img)))
    gt = len([r for r in (data / "test" / "labels" / (img.stem + ".txt")).read_text().splitlines() if r.strip()])
    out.append({"image": img.name, "ground_truth_boxes": gt, "detections": [(x.cls, round(x.score, 2)) for x in d]})
res = {"adapter": det.version, "images": len(out), "images_with_detections": sum(bool(o["detections"]) for o in out), "sample": out[:5]}
(rep / "ohe_onnx_backend_check.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
