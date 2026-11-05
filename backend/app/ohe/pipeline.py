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


class RapidOcrAdapter:
    """PP-OCR detection + recognition on ONNX Runtime (rapidocr_onnxruntime, Apache-2.0). Zero-shot on mast plates
    until the plate fine-tune (needs pilot photos); the numbering grammar and corridor check guard its output."""
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR()
        self.version = "rapidocr-ppocr-zero-shot"

    def read(self, img):
        res, _ = self._ocr(img)
        return [(str(t).replace(" ", ""), float(sc)) for _, t, sc in (res or [])]


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
            res.append(Det(self.names[int(cid[keep][i])], float(sc[keep][i]),
                           (float(x0), float(y0), float(x0 + bw), float(y0 + bh))))  # plain floats: JSON-safe
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


class ViewCheck(Protocol):
    version: str
    threshold: float
    def p_distorted(self, img: np.ndarray) -> float: ...


class OnnxViewCheck:
    """Photo-angle (perspective) check: MobileNetV3-small trained on EPDCL PD-Defect perspective_validation (CC BY 4.0).
    Output is a recapture reason only; it never changes an assessment (deterministic gate unchanged)."""
    def __init__(self, path: str, threshold: float = 0.5, size: int = 224):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.inp = self.sess.get_inputs()[0].name
        self.threshold, self.size, self.version = threshold, size, f"onnx:{Path(path).name}"

    def p_distorted(self, img):
        import cv2
        x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (self.size, self.size)).astype(np.float32) / 255.0
        x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
        logits = self.sess.run(None, {self.inp: x.transpose(2, 0, 1)[None]})[0][0]
        e = np.exp(logits - logits.max())
        return float(e[1] / e.sum())   # classes: [valid, perspective_distorted]


class RotationTTA:
    """Looks at the photo at several rotations and merges what it finds, so a part is found whatever way the phone
    or the part is turned (sideways cantilever insulators, tilted shots, upside-down photos). Each rotated view is
    drawn on a canvas big enough to keep every pixel; boxes are mapped back to the original photo and merged per
    class (non-maximum suppression). Close-ups and partial views need nothing extra: the detector handles crops."""

    def __init__(self, base, angles=(0, 90, 180, 270, 45, 135, 225, 315), iou: float = 0.45):
        self.base, self.angles, self.iou = base, angles, iou
        self.version = f"{getattr(base, 'version', 'detector')}+rot{len(angles)}"
        self.conf = getattr(base, "conf", None)

    @staticmethod
    def _view(img, a):
        import cv2
        h, w = img.shape[:2]
        if a % 360 == 0:
            return img, None
        m = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
        c, s_ = abs(m[0, 0]), abs(m[0, 1])
        nw, nh = int(h * s_ + w * c), int(h * c + w * s_)
        m[0, 2] += nw / 2 - w / 2
        m[1, 2] += nh / 2 - h / 2
        return cv2.warpAffine(img, m, (nw, nh), borderValue=(114, 114, 114)), cv2.invertAffineTransform(m)

    def detect(self, img):
        h, w = img.shape[:2]
        found = []
        for a in self.angles:
            v, inv = self._view(img, a)
            for d in self.base.detect(v):
                x1, y1, x2, y2 = d.box
                if inv is not None:
                    pts = np.array([[x1, y1, 1], [x2, y1, 1], [x2, y2, 1], [x1, y2, 1]], float) @ inv.T
                    x1, y1 = pts[:, 0].min(), pts[:, 1].min()
                    x2, y2 = pts[:, 0].max(), pts[:, 1].max()
                    # a rotated box is wider than the object; shrink it back towards the centre by the rotation slack
                    k = 1.0 if a % 90 == 0 else 0.78
                    cx, cy, bw, bh = (x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) * k, (y2 - y1) * k
                    x1, y1, x2, y2 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
                box = (float(max(0, x1)), float(max(0, y1)), float(min(w, x2)), float(min(h, y2)))
                if box[2] - box[0] > 2 and box[3] - box[1] > 2:
                    found.append((d.cls, float(d.score), box, a))
        out = []
        for cls in {f[0] for f in found}:
            cand = sorted((f for f in found if f[0] == cls), key=lambda f: -f[1])
            while cand:
                best = cand.pop(0)
                out.append(Det(cls, best[1], best[2]))
                cand = [f for f in cand if _iou(f[2], best[2]) < self.iou]
        return sorted(out, key=lambda d: -d.score)


class Sectioned:
    """Inspect the whole photo AND each overlapping section of it (a grid sized to the photo), so small or partial
    parts anywhere in a large photo are seen at a useful size. Every section is inspected at several orientations;
    boxes are mapped back onto the full photo and merged (a part cut by a section edge keeps its largest box).
    `last_sections` records what each section held, for the report."""

    def __init__(self, base, full_angles=(0, 90, 180, 270, 45, 135, 225, 315), tile_angles=(0, 90, 270),
                 tile_px: int = 900, overlap: float = 0.25, iou: float = 0.45):
        self.full = RotationTTA(base, full_angles, iou)
        self.tile = RotationTTA(base, tile_angles, iou)
        self.tile_px, self.overlap, self.iou = tile_px, overlap, iou
        self.version = f"{getattr(base, 'version', 'detector')}+sections+rot{len(full_angles)}"
        self.conf = getattr(base, "conf", None)
        self.last_sections: list[dict] = []

    def grid(self, w: int, h: int) -> list[tuple[int, int, int, int]]:
        nx, ny = max(1, round(w / self.tile_px)), max(1, round(h / self.tile_px))
        if nx == 1 and ny == 1:
            return []
        tw, th = w / nx, h / ny
        ox, oy = tw * self.overlap / 2, th * self.overlap / 2
        return [(int(max(0, i * tw - ox)), int(max(0, j * th - oy)), int(min(w, (i + 1) * tw + ox)), int(min(h, (j + 1) * th + oy)))
                for j in range(ny) for i in range(nx)]

    def detect(self, img):
        h, w = img.shape[:2]
        found = [(d, -1) for d in self.full.detect(img)]
        secs = self.grid(w, h)
        for k, (x1, y1, x2, y2) in enumerate(secs):
            for d in self.tile.detect(img[y1:y2, x1:x2]):
                b = d.box
                found.append((Det(d.cls, d.score, (b[0] + x1, b[1] + y1, b[2] + x1, b[3] + y1)), k))
        out, where = [], []
        for cls in {d.cls for d, _ in found}:
            cand = sorted((f for f in found if f[0].cls == cls), key=lambda f: -f[0].score)
            while cand:
                best = cand.pop(0)
                group = [best] + [f for f in cand if _iou(f[0].box, best[0].box) >= self.iou or _inside(f[0].box, best[0].box) > 0.8
                                  or _inside(best[0].box, f[0].box) > 0.8]
                cand = [f for f in cand if f not in group]
                bx = (min(g[0].box[0] for g in group), min(g[0].box[1] for g in group),
                      max(g[0].box[2] for g in group), max(g[0].box[3] for g in group)) if len(group) > 1 else best[0].box
                out.append(Det(cls, best[0].score, tuple(float(v) for v in bx)))
                where.append(sorted({g[1] for g in group}))
        self.last_sections = [{"section": k, "box": list(b), "found": sorted(d.cls for d, ks in zip(out, where) if k in ks)}
                              for k, b in enumerate(secs)]
        return [d for d, _ in sorted(zip(out, where), key=lambda t: -t[0].score)]


def _inside(a, b) -> float:
    """Share of box a that lies inside box b."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (a[2] - a[0]) * (a[3] - a[1])
    return ix * iy / area if area > 0 else 0.0


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


def mast_lean(img: np.ndarray, box, roll_deg: float | None) -> tuple[float | None, str]:
    """Screening angle of a mast from vertical (degrees, + = top leans right in the photo), corrected for the
    phone's roll at capture. Uses the long straight edges inside the mast box (OpenCV Hough). Returns (None, reason)
    when it cannot be measured honestly: no phone tilt reading, phone not upright, mast too small or off-centre
    (perspective makes off-centre verticals converge), or no clear straight edges."""
    import cv2
    if roll_deg is None:
        return None, "no phone tilt reading for this photo"
    if abs(roll_deg) > 30:
        return None, "phone was not held upright"
    h, w = img.shape[:2]
    x1, y1, x2, y2 = (int(max(0, v)) for v in box)
    x2, y2 = min(x2, w), min(y2, h)
    if y2 - y1 < max(160, 0.3 * h):
        return None, "mast too small in the photo to measure lean"
    if abs((x1 + x2) / 2 - w / 2) > 0.2 * w:
        return None, "mast off-centre; take it square-on in the middle of the photo"
    crop = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(crop, (5, 5), 0), 50, 150)
    lines = cv2.HoughLinesP(edges, 2, np.pi / 360, threshold=60, minLineLength=int(0.4 * (y2 - y1)), maxLineGap=25)
    if lines is None:
        return None, "no clear mast edges"
    angs, wts = [], []
    for lx1, ly1, lx2, ly2 in np.asarray(lines).reshape(-1, 4).tolist():
        if ly2 < ly1:
            lx1, ly1, lx2, ly2 = lx2, ly2, lx1, ly1
        a = math.degrees(math.atan2(lx1 - lx2, ly2 - ly1))  # angle from vertical, + = top to the right
        if abs(a) <= 20:
            angs.append(a)
            wts.append(math.hypot(lx2 - lx1, ly2 - ly1))
    if len(angs) < 2:
        return None, "no clear mast edges"
    order = np.argsort(angs)
    cw = np.cumsum(np.array(wts)[order])
    measured = float(np.array(angs)[order][np.searchsorted(cw, cw[-1] / 2)])  # length-weighted median
    return round(measured + roll_deg, 2), "mast edges, corrected for phone tilt"


def calibrate(score: float, cls: str, calib: dict | None) -> float | None:
    """Platt scaling per class fitted on the held-out test split (ohe_calibration.json): p = 1/(1+e^-(a*logit(s)+b))."""
    c = (calib or {}).get("classes", {}).get(cls)
    if not c:
        return None
    s = min(max(score, 1e-6), 1 - 1e-6)
    z = c["a"] * math.log(s / (1 - s)) + c["b"]
    return round(1 / (1 + math.exp(-z)), 4)


def assess_image(img: np.ndarray, reg: dict, det: Detector, ocr: OCR, anomaly: Anomaly | None = None,
                 lat=None, lon=None, acc=None, view: ViewCheck | None = None, roll_deg: float | None = None,
                 calib: dict | None = None) -> dict:
    q = quality.assess(img)
    view_res = None
    if view is not None and img is not None:
        p = view.p_distorted(img)
        view_res = {"p_perspective_distorted": round(p, 4), "flag": p >= view.threshold, "model": view.version}
    comps = reg["components"]
    dets = det.detect(img) if img is not None else []
    cands = candidates(reg, lat, lon, acc)
    reads = ocr.read(img) if img is not None else []
    ident = resolve_identity(reg, cands, reads)
    obs: list[Observation] = []
    defects = [d for d in dets if comps.get(d.cls, {}).get("symptom_of")]
    for d in dets:
        spec = comps.get(d.cls)
        if spec is not None and spec.get("symptom_of"):
            continue  # symptom boxes are attached to their component below
        o = Observation(d.cls, tuple(round(v, 1) for v in d.box), "", raw_scores={"detector": round(d.score, 4)})
        cal = calibrate(d.score, d.cls, calib)
        if cal is not None:
            o.raw_scores["calibrated"] = cal
        if spec is None:  # a design or part the registry does not know: never a generic pass (HLD V12)
            o.state, o.reasons = "unsupported_class", ["component or design not in the asset registry"]
        elif not spec.get("supported_conditions"):
            o.state, o.reasons = "unsupported_class", ["no validated condition model for this component"]
        elif d.short_side < reg["min_target_px"]:
            o.state, o.reasons = "insufficient_resolution", [f"target {d.short_side:.0f}px < {reg['min_target_px']}px"]
        elif not q.passed and set(q.reasons) & {"blurred", "too_dark", "overexposed"}:
            o.state, o.reasons = "insufficient_resolution", q.reasons
        else:
            if spec.get("lean_check"):
                lean, why = mast_lean(img, d.box, roll_deg)
                o.raw_scores["lean_deg"] = lean
                if lean is None:   # lean not measurable on this view: no claim either way, and no retake demanded
                    o.state, o.reasons = "unsupported_class", [f"lean not measured: {why}"]
                elif abs(lean) > reg.get("mast_lean_screen_deg", 3.0):
                    o.state, o.condition, o.reasons = "assessable_defect", "mast_lean", [f"{why}: {lean:+.1f} deg"]
                else:
                    o.state, o.reasons = "assessable_no_visible_defect", [f"{why}: {lean:+.1f} deg"]
                obs.append(o)
                continue
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
            "ocr_texts": [t for t, _ in reads],
            "observations": [asdict(o) for o in obs], "image_state": image_state,
            "view_check": view_res,
            "sections": {"inspected": 1 + len(getattr(det, "last_sections", [])), "grid": getattr(det, "last_sections", [])},
            "recapture_prompt": recapture_prompt(q, obs, ident, image_state),   # view check is information only now
            "model_versions": {"detector": det.version, "ocr": ocr.version,
                               "anomaly": anomaly.version if anomaly else "none", "quality": "opencv-rules-v2",
                               "view_check": view.version if view else "none"}}


def recapture_prompt(q, obs, ident, image_state) -> str | None:
    """Smallest useful request (HLD §8.2). Never asks the user to approach live equipment, and never asks for a
    framing the field cannot give: partial views, close-ups and any orientation are accepted as they are. Only a
    photo nothing could be judged on asks for zoom/steadiness, and a finding asks for the plate to tie it to a mast."""
    judged = [o for o in obs if o.state in ("assessable_defect", "anomalous_unclassified", "assessable_no_visible_defect")]
    if not judged and (image_state == "insufficient_resolution" or any(o.state == "insufficient_resolution" for o in obs)):
        return "Hold still and use optical zoom on the component; do not move closer to the OHE"
    if ident["state"] != "resolved" and any(o.state in ("assessable_defect", "anomalous_unclassified") for o in obs):
        return "Capture the mast number plate from where you stand"
    return None


def decide(obs: dict, ident: dict, q_passed: bool, reg: dict) -> dict:
    """Assessment for one observation: three claim types, confidence vector, priority as a consequence rule and
    deterministic routing (HLD §2.1, §8.1, §8.3). Raw scores are reported as 'uncalibrated'."""
    rule = next((r for r in reg["rules"] if r["condition"] == obs["condition"]), None) if obs["condition"] else None
    cal = obs["raw_scores"].get("calibrated")
    conf = {"Q": 1.0 if q_passed else 0.5, "A": ident["A"], "V": None, "C": cal if cal is not None else
            (obs["raw_scores"].get("defect") or obs["raw_scores"].get("detector")), "T": None, "R": 1.0 if rule else None,
            "calibration": "platt-per-class (public test split)" if cal is not None else "uncalibrated"}
    out = {"component": obs["component"], "state": obs["state"], "condition": obs["condition"], "box": obs["box"],
           "confidence": conf, "reasons": obs["reasons"]}
    if rule:
        out |= {"rule_id": rule["id"], "authority": rule["authority"], "observed_feature": rule["observed"],
                "hypothesis": rule["hypothesis"], "recommendation": rule["action"], "action_family": rule["action_family"],
                "limitations": rule["limitations"], "priority": rule["priority"],
                "routing": rule["route"] | {"registry_version": reg["version"]},
                "alert": rule["priority"] == "urgent"}
    return out
