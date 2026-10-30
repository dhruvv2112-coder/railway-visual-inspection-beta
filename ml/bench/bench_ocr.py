"""OCR for location markers (km/hectometre posts, OHE mast numbers) in English and Hindi.
No public dataset of Indian km posts exists (gap). We render synthetic marker plates with real fonts
(DejaVu Sans, Noto Sans Devanagari) and degrade them, then compare standard OCR engines.
Metrics: exact-match rate, character error rate (jiwer), latency."""
import random
import time

import albumentations as A
import cv2
import jiwer
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from common import write_report

random.seed(0)
FONT_EN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_HI = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
N = 120


def plates():
    out = []
    for i in range(N):
        km, sub = random.randint(100, 1999), random.randint(0, 9)
        mast = f"{km}/{random.randint(1, 40)}"
        kind = i % 3
        if kind == 0:
            out.append(("en", f"{km}/{sub}", FONT_EN))          # km/hectometre post
        elif kind == 1:
            out.append(("en", f"OHE {mast}", FONT_EN))          # OHE mast plate
        else:
            out.append(("hi", f"किमी {km}", FONT_HI))           # Hindi km marker
    return out


def render(text, font_path):
    font = ImageFont.truetype(font_path, 72)
    w = int(font.getlength(text)) + 80
    img = Image.new("RGB", (w, 140), (250, 250, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, w - 5, 135], outline=(20, 20, 20), width=6)
    d.text((40, 25), text, font=font, fill=(15, 15, 15))
    bg = np.full((480, max(640, w + 200), 3), 120, np.uint8)
    arr = np.array(img)[:, :, ::-1]
    bg[170:170 + arr.shape[0], 100:100 + arr.shape[1]] = arr
    return bg


CONDS = {
    "clean": None,
    "perspective+blur": A.Compose([A.Perspective(scale=(0.05, 0.08), p=1), A.MotionBlur(blur_limit=(7, 7), p=1)]),
    "low_light": A.RandomBrightnessContrast(brightness_limit=(-0.55, -0.55), contrast_limit=(-0.3, -0.3), p=1),
    "weathered(noise+fade)": A.Compose([A.GaussNoise(std_range=(0.08, 0.12), p=1),
                                        A.RandomBrightnessContrast(brightness_limit=0, contrast_limit=(-0.5, -0.5), p=1)]),
}


def eng_tesseract(img, lang):
    import pytesseract
    code = "hin+eng" if lang == "hi" else "eng"
    return pytesseract.image_to_string(img, lang=code, config="--psm 7").strip()


_easy = {}


def eng_easyocr(img, lang):
    import easyocr
    key = "hi" if lang == "hi" else "en"
    if key not in _easy:
        _easy[key] = easyocr.Reader(["hi", "en"] if key == "hi" else ["en"], gpu=False, verbose=False)
    return " ".join(r[1] for r in _easy[key].readtext(img)).strip()


_paddle = {}


def eng_paddle(img, lang):
    from paddleocr import PaddleOCR
    key = "hi" if lang == "hi" else "en"
    if key not in _paddle:
        _paddle[key] = PaddleOCR(lang="hi" if key == "hi" else "en", use_textline_orientation=False)
    res = _paddle[key].predict(img)
    return " ".join(res[0]["rec_texts"]).strip() if res else ""


ENGINES = {"tesseract-5": eng_tesseract, "easyocr": eng_easyocr, "paddleocr": eng_paddle}


def norm(s):
    return " ".join(s.replace("|", "/").split())


def main():
    data = plates()
    rows, notes = [], []
    for ename, fn in ENGINES.items():
        for cname, aug in CONDS.items():
            for lang in ("en", "hi"):
                refs, hyps, lat = [], [], []
                try:
                    for l, text, font in data:
                        if l != lang:
                            continue
                        img = render(text, font)
                        if aug is not None:
                            img = aug(image=img)["image"]
                        t = time.perf_counter()
                        hyp = fn(img, lang)
                        lat.append(time.perf_counter() - t)
                        refs.append(norm(text))
                        hyps.append(norm(hyp) or "∅")
                    rows.append({"engine": ename, "condition": cname, "lang": lang, "n": len(refs),
                                 "exact_match": float(np.mean([a == b for a, b in zip(refs, hyps)])),
                                 "cer": float(jiwer.cer(refs, hyps)), "median_latency_s": float(np.median(lat))})
                except Exception as e:
                    notes.append(f"{ename}/{cname}/{lang} failed: {type(e).__name__}: {str(e)[:160]}")
    best = max((r for r in rows if r["condition"] == "clean"), key=lambda r: r["exact_match"], default=None)
    write_report("ocr_markers", "OCR of km/OHE-mast markers (English & Hindi, synthetic plates)",
                 f"Best clean-condition exact match: {best['engine']} {best['lang']} {best['exact_match']:.1%}." if best else "No engine ran.",
                 rows, notes=notes + ["Synthetic plates: real Indian km-post photos must be collected in pilot (gap).",
                                      "On-device app uses ML Kit Text Recognition v2 (Latin + Devanagari); not runnable in CI – evaluate on device."])


if __name__ == "__main__":
    main()
