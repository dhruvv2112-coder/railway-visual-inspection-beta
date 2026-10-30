import cv2
import numpy as np

from app import quality


def _textured(h=960, w=1280, seed=0):
    rng = np.random.default_rng(seed)
    img = (rng.random((h, w)) * 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    for x in range(0, w, 40):
        cv2.line(img, (x, 0), (x, h), 255, 2)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_sharp_image_passes():
    assert quality.assess(_textured()).passed


def test_blurred_image_rejected():
    blurred = cv2.GaussianBlur(_textured(), (31, 31), 12)
    r = quality.assess(blurred)
    assert "blurred" in r.reasons


def test_dark_image_rejected():
    dark = (_textured() * 0.12).astype(np.uint8)
    assert "too_dark" in quality.assess(dark).reasons


def test_overexposed_image_rejected():
    bright = np.clip(_textured().astype(int) + 200, 0, 255).astype(np.uint8)
    r = quality.assess(bright)
    assert {"overexposed", "clipped_highlights"} & set(r.reasons)


def test_low_resolution_rejected():
    assert "resolution_too_low" in quality.assess(_textured(320, 400)).reasons


def test_unreadable():
    assert quality.decode(b"not an image") is None
    assert not quality.assess(None).passed


def test_mildly_dark_but_usable_image_passes():
    # regression for benchmark finding: shadows must not count as clipping
    img = _textured()
    img = (img.astype(np.float32) * 0.45).astype(np.uint8)
    img[:200] = 0  # deep shadow band
    r = quality.assess(img)
    assert "clipped_highlights" not in r.reasons
