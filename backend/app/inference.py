"""Optional detector inference via ONNX Runtime.

Accepts any detector exported to ONNX in the Ultralytics/RF-DETR 'boxes+scores' layout
(output shape [1, 4 + n_classes, n_boxes], xywh in input pixels). Post-processing uses
cv2.dnn.NMSBoxes (standard) rather than custom NMS. When no model is configured the service
returns no candidates — the app then relies on the inspector's manual classification.
"""
import json
from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np

from .config import settings


@dataclass
class Candidate:
    class_id: str
    score: float
    box_xyxy: tuple[float, float, float, float]


@lru_cache
def _session():
    if not settings.detector_onnx or not settings.detector_onnx.exists():
        return None
    import onnxruntime as ort

    sess = ort.InferenceSession(str(settings.detector_onnx), providers=["CPUExecutionProvider"])
    labels = json.loads(settings.detector_labels.read_text()) if settings.detector_labels else None
    return sess, labels


def available() -> bool:
    return _session() is not None


def detect(image_bgr: np.ndarray) -> list[Candidate]:
    s = _session()
    if s is None:
        return []
    sess, labels = s
    inp = sess.get_inputs()[0]
    size = int(inp.shape[2]) if isinstance(inp.shape[2], int) else 640
    h, w = image_bgr.shape[:2]
    blob = cv2.dnn.blobFromImage(image_bgr, 1 / 255.0, (size, size), swapRB=True, crop=False)
    out = sess.run(None, {inp.name: blob})[0][0]  # [4+nc, N]
    out = out.T
    boxes, scores = out[:, :4], out[:, 4:]
    cls = scores.argmax(1)
    conf = scores.max(1)
    keep = conf >= settings.detector_conf
    boxes, cls, conf = boxes[keep], cls[keep], conf[keep]
    sx, sy = w / size, h / size
    xywh = [[(b[0] - b[2] / 2) * sx, (b[1] - b[3] / 2) * sy, b[2] * sx, b[3] * sy] for b in boxes]
    idx = cv2.dnn.NMSBoxes(xywh, conf.tolist(), settings.detector_conf, 0.5)
    res = []
    for i in np.array(idx).flatten():
        x, y, bw, bh = xywh[i]
        name = labels[int(cls[i])] if labels else str(int(cls[i]))
        res.append(Candidate(name, float(conf[i]), (x, y, x + bw, y + bh)))
    return res
