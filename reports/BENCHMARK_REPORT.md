# RVI Beta – Model Benchmark Report
All numbers produced by `ml/bench/*` in CI. Each section lists its data source, environment and failures.

## Image-quality gate under field conditions

Source: Mendeley 88sh5y3tmj v2 (Indian railway track images, CC BY 4.0). False-rejection on usable images: 5.0%. Unusable images wrongly passed: 1.7%.

| condition | expected | n | pass_rate | correct_rate | median_sharpness | median_brightness |
|---|---|---|---|---|---|---|
| clean | pass | 200 | 0.9300 | 0.9300 | 796.6249 | 141.7191 |
| dark_mild | pass | 200 | 0.9500 | 0.9500 | 668.0372 | 67.4631 |
| dark_severe(night_no_torch) | reject | 200 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| motion_blur_mild | pass | 200 | 0.9200 | 0.9200 | 212.7557 | 141.6725 |
| motion_blur_severe(walking) | reject | 200 | 0.0850 | 0.9150 | 25.0400 | 142.4538 |
| defocus_severe | reject | 200 | 0.0000 | 1.0000 | 2.1432 | 141.9178 |
| rain_drops | pass | 200 | 1.0000 | 1.0000 | 546.4613 | 126.6098 |
| fog_dust_dense | reject | 200 | 0.0000 | 1.0000 | 2.0742 | 211.0403 |
| glare_overexposed | reject | 200 | 0.0000 | 1.0000 | 61.8081 | 249.1174 |
- Degradations are synthetic (albumentations) – field captures needed to confirm.
- Thresholds from backend/app/config.py; tune on pilot data.

_Environment_: GitHub Actions 1000000055 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T06:40:58.533608+00:00

## OCR of km/OHE-mast markers (English & Hindi, synthetic plates)

Best clean-condition exact match: tesseract-5 en 100.0%.

| engine | condition | lang | n | exact_match | number_match | cer | median_latency_s |
|---|---|---|---|---|---|---|---|
| tesseract-5 | clean | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.1324 |
| tesseract-5 | clean | hi | 40 | 0.0000 | 0.1250 | 0.4609 | 0.1526 |
| tesseract-5 | perspective+blur | en | 80 | 0.8000 | 0.8250 | 0.1509 | 0.1351 |
| tesseract-5 | perspective+blur | hi | 40 | 0.1000 | 0.1250 | 0.3449 | 0.1601 |
| tesseract-5 | low_light | en | 80 | 0.9875 | 0.9875 | 0.0079 | 0.1288 |
| tesseract-5 | low_light | hi | 40 | 0.0250 | 0.1750 | 0.6087 | 0.1498 |
| tesseract-5 | weathered(noise+fade) | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.2512 |
| tesseract-5 | weathered(noise+fade) | hi | 40 | 0.0000 | 0.1250 | 0.4522 | 0.2943 |
| easyocr | clean | en | 80 | 1.0000 | 1.0000 | 0.0000 | 1.8926 |
| easyocr | clean | hi | 40 | 0.0000 | 1.0000 | 0.4145 | 1.6920 |
| easyocr | perspective+blur | en | 80 | 1.0000 | 1.0000 | 0.0000 | 1.4754 |
| easyocr | perspective+blur | hi | 40 | 0.0000 | 1.0000 | 0.4145 | 1.6546 |
| easyocr | low_light | en | 80 | 1.0000 | 1.0000 | 0.0000 | 1.5055 |
| easyocr | low_light | hi | 40 | 0.0000 | 1.0000 | 0.3913 | 1.6951 |
| easyocr | weathered(noise+fade) | en | 80 | 1.0000 | 1.0000 | 0.0000 | 1.5376 |
| easyocr | weathered(noise+fade) | hi | 40 | 0.0000 | 1.0000 | 0.4145 | 1.7234 |
| paddleocr | clean | en | 80 | 0.9875 | 1.0000 | 0.0016 | 0.0756 |
| paddleocr | clean | hi | 40 | 0.0000 | 0.8000 | 0.3449 | 0.0660 |
| paddleocr | perspective+blur | en | 80 | 0.9625 | 1.0000 | 0.0377 | 0.0720 |
| paddleocr | perspective+blur | hi | 40 | 0.0000 | 0.7250 | 0.3420 | 0.0696 |
| paddleocr | low_light | en | 80 | 0.8875 | 0.9875 | 0.0204 | 0.0729 |
| paddleocr | low_light | hi | 40 | 0.0000 | 0.7250 | 0.3681 | 0.0679 |
| paddleocr | weathered(noise+fade) | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.0696 |
| paddleocr | weathered(noise+fade) | hi | 40 | 0.0000 | 0.8250 | 0.3391 | 0.0673 |
- Synthetic plates: real Indian km-post photos must be collected in pilot (gap).
- On-device app uses ML Kit Text Recognition v2 (Latin + Devanagari); not runnable in CI – evaluate on device.

_Environment_: GitHub Actions 1000000055 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T07:01:51.063210+00:00

## asr

_Not run or failed before writing results._

## translation

_Not run or failed before writing results._

## detector

_Not run or failed before writing results._

## Same-asset re-identification for duplicate suppression

Synthetic re-captures of Indian railway images.

| model | gallery | recall@1 | recall@5 | sec_per_image_cpu |
|---|---|---|---|---|
| facebook/dinov2-small | 300 | 0.7367 | 0.9033 | 0.0880 |
| google/siglip-base-patch16-224 | 300 | 0.3800 | 0.6700 | 0.2297 |
- Gallery images of the same defect class look alike; GNSS distance gating is applied first in production.

_Environment_: GitHub Actions 1000000055 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T06:44:22.270194+00:00
