"""OHE visual-inspection cascade (HLD §6–§8). Pure functions over image bytes + manifest + static registry.

Visual-only contract: this module never imports or receives notes (HLD §1.1 I-06, §3.2). Model adapters are
replaceable (HLD §6.4): each returns versioned, typed outputs with raw scores; nothing here is a calibrated
probability unless a calibration map is configured (HLD §8.1)."""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
import yaml

from .. import quality

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "shared" / "ohe_registry.yaml"
STATES = ("assessable_no_visible_defect", "assessable_defect", "anomalous_unclassified", "insufficient_resolution",
          "occluded_or_missing_view", "uncertain_identity", "no_evidence", "unsupported_class")


# ---------------------------------------------------------------- adapters
@dataclass
class Det:
    cls: str
    score: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in ORIGINAL pixel coordinates

    @property
    def short_side(self) -> float:
        return min(self.box[2] - self.box[0], self.box[3] - self.box[1])


class Detector(Protocol):
    version: str
    def detect(self, img: np.ndarray) -> list[Det]: ...


class OCR(Protocol):
    version: str
    def read(self, img: np.ndarray) -> list[tuple[str, float]]: ...


class Anomaly(Protocol):
    version: str
    threshold: float
    def score(self, crop: np.ndarray) -> float: ...


class NullDetector:
    version = "none"
    def detect(self, img):
        return []


class NullOCR:
    version = "none"
    def read(self, img):
        return []


class OnnxYoloDetector:
    """Ultralytics-exported ONNX detector (output 1 x (4+nc) x N). Letterbox to imgsz, NMS with OpenCV."""

    def __init__(self, path: str, names: list[str], imgsz: int = 640, conf: float = 0.25):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.names, self.imgsz, self.conf = names, imgsz, conf
        self.version = f"onnx:{Path(path).name}"

    def detect(self, img):
        import cv2
        h, w = img.shape[:2]
        r = self.imgsz / max(h, w)
        nh, nw = round(h * r), round(w * r)
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, np.uint8)
        canvas[:nh, :nw] = cv2.resize(img, (nw, nh))
        x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255
        out = self.sess.run(None, {self.sess.get_inputs()[0].name: x})[0][0].T  # N x (4+nc)
        cls_scores = out[:, 4:]
        cid, sc = cls_scores.argmax(1), cls_scores.max(1)
        keep = sc >= self.conf
        boxes = [[(cx - bw / 2) / r, (cy - bh / 2) / r, bw / r, bh / r] for cx, cy, bw, bh in out[keep, :4]]
        idx = cv2.dnn.NMSBoxes(boxes, sc[keep].tolist(), self.conf, 0.5) if boxes else []
        res = []
        for i in np.array(idx).flatten():
            x0, y0, bw, bh = boxes[i]
            res.append(Det(self.names[int(cid[keep][i])], float(sc[keep][i]), (x0, y0, x0 + bw, y0 + bh)))
        return res


# ---------------------------------------------------------------- registry and identity (HLD §5)
def load_registry(path: Path = REGISTRY_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _metres(lat1, lon1, lat2, lon2) -> float:
    k = math.pi / 180
    x = (lon2 - lon1) * k * math.cos((lat1 + lat2) * k / 2)
    return 6371000 * math.hypot(x, (lat2 - lat1) * k)


def candidates(reg: dict, lat: float | None, lon: float | None, acc: float | None) -> list[dict]:
    """Corridor candidates within plausible observation distance (+ location uncertainty). Never 'nearest = truth'."""
    if lat is None or lon is None:
        return []
    radius = reg["max_observation_m"] + (acc or 30)
    out = [{"asset_id": a["id"], "track": a["track"], "distance_m": round(_metres(lat, lon, a["lat"], a["lon"]), 1)}
           for a in reg["assets"]]
    return sorted([c for c in out if c["distance_m"] <= radius], key=lambda c: c["distance_m"])


def resolve_identity(reg: dict, cands: list[dict], ocr: list[tuple[str, float]]) -> dict:
    """Accept an asset only on grammar-valid OCR that agrees with the registry and the corridor; otherwise abstain
    and keep the candidate list (HLD §5.1, §5.3). Contradictions increase ambiguity rather than being averaged."""
    grammar = re.compile(reg["numbering_grammar"])
    known = {a["id"] for a in reg["assets"]}
    corridor = {c["asset_id"] for c in cands}
    reads = [(t.strip().upper().replace(" ", ""), s) for t, s in ocr]
    valid = [(t, s) for t, s in reads if grammar.match(t)]
    base = {"candidates": cands, "ocr_raw": [t for t, _ in reads], "selected_asset_id": None}
    if not valid:
        return base | {"state": "uncertain_identity", "A": 0.0, "basis": "no grammar-valid plate text"}
    texts = {t for t, _ in valid}
    if len(texts) > 1:
        return base | {"state": "uncertain_identity", "A": 0.0, "basis": f"conflicting plate readings {sorted(texts)}"}
    t, s = valid[0]
    if t not in known:
        return base | {"state": "uncertain_identity", "A": 0.0, "basis": f"plate {t} not in registry"}
    if cands and t not in corridor:
        return base | {"state": "uncertain_identity", "A": 0.0, "basis": f"plate {t} outside location corridor"}
    return base | {"state": "resolved", "A": round(min(1.0, s), 3), "selected_asset_id": t,
                   "basis": "plate OCR agrees with registry" + (" and corridor" if cands else " (no location)")}


# ---------------------------------------------------------------- condition + assessment (HLD §7, §8)
def _overlap(a, b) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (b[2] - b[0]) * (b[3] - b[1])
    return ix * iy / area if area else 0.0


@dataclass
class Observation:
    component: str
    box: tuple
    state: str
    condition: str | None = None
    raw_scores: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def assess_image(img: np.ndarray, reg: dict, det: Detector, ocr: OCR, anomaly: Anomaly | None = None,
                 lat=None, lon=None, acc=None) -> dict:
    q = quality.assess(img)
    comps = reg["components"]
    dets = det.detect(img) if img is not None else []
    cands = candidates(reg, lat, lon, acc)
    ident = resolve_identity(reg, cands, ocr.read(img) if img is not None else [])
    obs: list[Observation] = []
    defects = [d for d in dets if comps.get(d.cls, {}).get("symptom_of")]
    for d in dets:
        spec = comps.get(d.cls)
        if spec is None or spec.get("symptom_of"):
            continue  # symptom boxes are attached to their component below
        o = Observation(d.cls, tuple(round(v, 1) for v in d.box), "", raw_scores={"detector": round(d.score, 4)})
        if not spec.get("supported_conditions"):
            o.state, o.reasons = "unsupported_class", ["no validated condition model for this component"]
        elif d.short_side < reg["min_target_px"]:
            o.state, o.reasons = "insufficient_resolution", [f"target {d.short_side:.0f}px < {reg['min_target_px']}px"]
        elif not q.passed and set(q.reasons) & {"blurred", "too_dark", "overexposed"}:
            o.state, o.reasons = "insufficient_resolution", q.reasons
        else:
            hits = [s for s in defects if comps[s.cls]["symptom_of"] == d.cls and _overlap(d.box, s.box) > 0.5]
            if spec.get("presence_is_condition"):  # e.g. a nest or foreign object: its presence is the finding
                o.state, o.condition = "assessable_defect", spec["supported_conditions"][0]
            elif hits:
                best = max(hits, key=lambda s: s.score)
                o.state, o.condition = "assessable_defect", spec["supported_conditions"][0]
                o.raw_scores["defect"] = round(best.score, 4)
            else:
                o.state = "assessable_no_visible_defect"
                if anomaly is not None:
                    x1, y1, x2, y2 = map(int, d.box)
                    a = anomaly.score(img[max(0, y1):y2, max(0, x1):x2])
                    o.raw_scores["anomaly"] = round(a, 4)
                    if a > anomaly.threshold:
                        o.state, o.condition = "anomalous_unclassified", "anomaly"
        obs.append(o)
    # defect boxes without a parent component are kept (a defect must not disappear, HLD §5.3)
    for s in defects:
        parent = comps[s.cls]["symptom_of"]
        if not any(o.component == parent and _overlap(o.box, s.box) > 0.5 for o in obs):
            obs.append(Observation(parent, tuple(round(v, 1) for v in s.box), "assessable_defect",
                                   comps[parent]["supported_conditions"][0], {"defect": round(s.score, 4)},
                                   ["defect seen without a detected parent component"]))
    image_state = None
    if not obs:
        image_state = "insufficient_resolution" if not q.passed else "occluded_or_missing_view"
    return {"quality": asdict(q) | {"passed": q.passed}, "detections": [asdict(d) for d in dets], "identity": ident,
            "observations": [asdict(o) for o in obs], "image_state": image_state,
            "recapture_prompt": recapture_prompt(q, obs, ident, image_state),
            "model_versions": {"detector": det.version, "ocr": ocr.version,
                               "anomaly": anomaly.version if anomaly else "none", "quality": "opencv-rules-v2"}}


def recapture_prompt(q, obs, ident, image_state) -> str | None:
    """Smallest useful request (HLD §8.2). Never asks the user to approach live equipment."""
    if image_state == "insufficient_resolution" or any(o.state == "insufficient_resolution" for o in obs):
        return "Hold still and use optical zoom on the component; do not move closer to the OHE"
    if ident["state"] != "resolved" and any(o.state in ("assessable_defect", "anomalous_unclassified") for o in obs):
        return "Capture the mast number plate from where you stand"
    if image_state == "occluded_or_missing_view":
        return "Include the whole assembly in the frame"
    return None


def decide(obs: dict, ident: dict, q_passed: bool, reg: dict) -> dict:
    """Assessment for one observation: three claim types, confidence vector, priority as a consequence rule and
    deterministic routing (HLD §2.1, §8.1, §8.3). Raw scores are reported as 'uncalibrated'."""
    rule = next((r for r in reg["rules"] if r["condition"] == obs["condition"]), None) if obs["condition"] else None
    conf = {"Q": 1.0 if q_passed else 0.5, "A": ident["A"], "V": None, "C": obs["raw_scores"].get("defect")
            or obs["raw_scores"].get("detector"), "T": None, "R": 1.0 if rule else None, "calibration": "uncalibrated"}
    out = {"component": obs["component"], "state": obs["state"], "condition": obs["condition"], "box": obs["box"],
           "confidence": conf, "reasons": obs["reasons"]}
    if rule:
        out |= {"rule_id": rule["id"], "authority": rule["authority"], "observed_feature": rule["observed"],
                "hypothesis": rule["hypothesis"], "recommendation": rule["action"], "action_family": rule["action_family"],
                "limitations": rule["limitations"], "priority": rule["priority"],
                "routing": rule["route"] | {"registry_version": reg["version"]},
                "alert": rule["priority"] == "urgent"}
    return out
