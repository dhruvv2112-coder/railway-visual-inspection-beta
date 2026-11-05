"""Build the whole-photo inventory model: YOLO-World v2 (open vocabulary) with the railway + debris vocabulary
baked in, exported to ONNX so the laptop server runs it with onnxruntime (no PyTorch, no internet).
usage: python export_scene.py <out dir>"""
import json
import shutil
import sys
from pathlib import Path

import yaml
from ultralytics import YOLOWorld

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
voc = yaml.safe_load((Path(__file__).parent / "vocabulary.yaml").read_text())
prompts = [c["prompt"] for c in voc["classes"]]
m = YOLOWorld("yolov8s-worldv2.pt")
m.set_classes(prompts)
f = m.export(format="onnx", imgsz=640, opset=12)
shutil.copy(f, out / "scene_detector.onnx")
(out / "scene_detector.names.json").write_text(json.dumps(prompts))
(out / "scene_vocabulary.json").write_text(json.dumps(voc))
print("exported", len(prompts), "classes ->", out)
