"""Image-quality gate vs field conditions.
Real railway images (Mendeley, India) are degraded with albumentations to emulate conditions from the
Phase 1 'Operating Conditions' sheet: darkness, motion blur (walking/head movement), rain, fog/dust,
low-sun glare. Ground truth: clean & mild => should PASS; severe => should be REJECTED.
Metrics: false-rejection rate on usable images; miss rate on unusable images."""
import sys
from pathlib import Path

import albumentations as A
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app import quality  # noqa: E402

from common import write_report  # noqa: E402
from datasets import find_images, mendeley_rail_defects  # noqa: E402

N = 200
CONDITIONS = {
    "clean": (None, "pass"),
    "dark_mild": (A.RandomBrightnessContrast(brightness_limit=(-0.35, -0.35), contrast_limit=0, p=1), "pass"),
    "dark_severe(night_no_torch)": (A.RandomBrightnessContrast(brightness_limit=(-0.8, -0.8), contrast_limit=(-0.5, -0.5), p=1), "reject"),
    "motion_blur_mild": (A.MotionBlur(blur_limit=(5, 5), p=1), "pass"),
    "motion_blur_severe(walking)": (A.MotionBlur(blur_limit=(41, 41), p=1), "reject"),
    "defocus_severe": (A.Defocus(radius=(12, 12), p=1), "reject"),
    "rain_drops": (A.RandomRain(brightness_coefficient=0.8, drop_width=2, blur_value=5, p=1), "pass"),
    "fog_dust_dense": (A.RandomFog(fog_coef_range=(0.9, 1.0), alpha_coef=0.2, p=1), "reject"),
    "glare_overexposed": (A.RandomBrightnessContrast(brightness_limit=(0.75, 0.75), contrast_limit=0, p=1), "reject"),
}


def main():
    try:
        imgs = find_images(mendeley_rail_defects(), N)
        source = "Mendeley 88sh5y3tmj v2 (Indian railway track images, CC BY 4.0)"
    except Exception as e:  # fall back so the gate is still exercised
        imgs, source = [], f"Mendeley download failed: {e}"
    if not imgs:
        raise SystemExit(f"No images available: {source}")
    rows = []
    for cond, (aug, expect) in CONDITIONS.items():
        decisions, sharp, bright = [], [], []
        for p in imgs:
            img = cv2.imread(str(p))
            if img is None:
                continue
            if aug is not None:
                img = cv2.cvtColor(aug(image=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))["image"], cv2.COLOR_RGB2BGR)
            r = quality.assess(img)
            decisions.append(r.passed)
            sharp.append(r.sharpness)
            bright.append(r.brightness)
        pr = float(np.mean(decisions))
        rows.append({"condition": cond, "expected": expect, "n": len(decisions), "pass_rate": pr,
                     "correct_rate": pr if expect == "pass" else 1 - pr,
                     "median_sharpness": float(np.median(sharp)), "median_brightness": float(np.median(bright))})
    usable = [r for r in rows if r["expected"] == "pass"]
    unusable = [r for r in rows if r["expected"] == "reject"]
    frr = 1 - np.mean([r["pass_rate"] for r in usable])
    miss = np.mean([r["pass_rate"] for r in unusable])
    write_report("quality_gate", "Image-quality gate under field conditions",
                 f"Source: {source}. False-rejection on usable images: {frr:.1%}. "
                 f"Unusable images wrongly passed: {miss:.1%}.", rows,
                 extra={"false_rejection_rate": frr, "miss_rate": miss},
                 notes=["Degradations are synthetic (albumentations) – field captures needed to confirm.",
                        "Thresholds from backend/app/config.py; tune on pilot data."])


if __name__ == "__main__":
    main()
