"""Image-quality gate. Standard OpenCV operations only (no custom model).

Returns 'pass' or the list of reasons the image is insufficient evidence. The gate runs before any
model inference so that a poor image yields 'insufficient evidence', never a confident wrong label.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

from .config import settings


@dataclass
class QualityReport:
    sharpness: float
    brightness: float
    clipped_fraction: float
    width: int
    height: int
    reasons: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.reasons


def _normalise(gray: np.ndarray, long_side: int = 1024) -> np.ndarray:
    h, w = gray.shape[:2]
    scale = long_side / max(h, w)
    if scale < 1:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return gray


def assess(image_bgr: np.ndarray) -> QualityReport:
    if image_bgr is None or image_bgr.size == 0:
        return QualityReport(0, 0, 1, 0, 0, ["unreadable_image"])
    h, w = image_bgr.shape[:2]
    gray = _normalise(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY))
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    clipped = float(((gray <= 2) | (gray >= 253)).mean())
    rep = QualityReport(sharp, bright, clipped, w, h)
    if min(h, w) < 480:
        rep.reasons.append("resolution_too_low")
    if sharp < settings.min_sharpness:
        rep.reasons.append("blurred")
    if bright < settings.min_brightness:
        rep.reasons.append("too_dark")
    if bright > settings.max_brightness:
        rep.reasons.append("overexposed")
    if clipped > settings.max_clipped_fraction:
        rep.reasons.append("clipped_highlights_or_shadows")
    return rep


def decode(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)
