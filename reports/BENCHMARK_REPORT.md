# RVI Beta – Model Benchmark Report
All numbers produced by `ml/bench/*` in CI. Each section lists its data source, environment and failures.

## Image-quality gate under field conditions

Source: Mendeley 88sh5y3tmj v2 (Indian railway track images, CC BY 4.0). False-rejection on usable images: 29.0%. Unusable images wrongly passed: 6.4%.

| condition | expected | n | pass_rate | correct_rate | median_sharpness | median_brightness |
|---|---|---|---|---|---|---|
| clean | pass | 200 | 0.9300 | 0.9300 | 796.6249 | 141.7191 |
| dark_mild | pass | 200 | 0.9500 | 0.9500 | 668.0372 | 67.4631 |
| dark_severe(night_no_torch) | reject | 200 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| motion_blur_mild | pass | 200 | 0.9300 | 0.9300 | 234.6860 | 141.6956 |
| motion_blur_severe(walking) | reject | 200 | 0.3200 | 0.6800 | 38.9534 | 140.9139 |
| defocus_severe | reject | 200 | 0.0000 | 1.0000 | 2.1487 | 141.7311 |
| rain_drops | pass | 200 | 0.0300 | 0.0300 | 44.6797 | 117.5119 |
| fog_dust_dense | reject | 200 | 0.0000 | 1.0000 | 1.9970 | 184.6714 |
| glare_overexposed | reject | 200 | 0.0000 | 1.0000 | 61.8081 | 249.1174 |
- Degradations are synthetic (albumentations) – field captures needed to confirm.
- Thresholds from backend/app/config.py; tune on pilot data.

_Environment_: GitHub Actions 1000000051 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T04:44:17.788963+00:00

## OCR of km/OHE-mast markers (English & Hindi, synthetic plates)

Best clean-condition exact match: tesseract-5 en 100.0%.

| engine | condition | lang | n | exact_match | number_match | cer | median_latency_s |
|---|---|---|---|---|---|---|---|
| tesseract-5 | clean | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.0757 |
| tesseract-5 | clean | hi | 40 | 0.0000 | 0.1250 | 0.4609 | 0.0859 |
| tesseract-5 | perspective+blur | en | 80 | 0.8000 | 0.8250 | 0.1509 | 0.0785 |
| tesseract-5 | perspective+blur | hi | 40 | 0.1000 | 0.1250 | 0.3449 | 0.0921 |
| tesseract-5 | low_light | en | 80 | 0.9875 | 0.9875 | 0.0079 | 0.0747 |
| tesseract-5 | low_light | hi | 40 | 0.0250 | 0.1750 | 0.6087 | 0.0844 |
| tesseract-5 | weathered(noise+fade) | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.1713 |
| tesseract-5 | weathered(noise+fade) | hi | 40 | 0.0000 | 0.1250 | 0.4522 | 0.1971 |
| easyocr | clean | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.7986 |
| easyocr | clean | hi | 40 | 0.0000 | 1.0000 | 0.4145 | 0.6907 |
| easyocr | perspective+blur | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.6228 |
| easyocr | perspective+blur | hi | 40 | 0.0000 | 1.0000 | 0.4145 | 0.6987 |
| easyocr | low_light | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.6515 |
| easyocr | low_light | hi | 40 | 0.0000 | 1.0000 | 0.3913 | 0.6980 |
| easyocr | weathered(noise+fade) | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.6661 |
| easyocr | weathered(noise+fade) | hi | 40 | 0.0000 | 1.0000 | 0.4145 | 0.6827 |
| paddleocr | clean | en | 80 | 0.9875 | 1.0000 | 0.0016 | 0.0404 |
| paddleocr | clean | hi | 40 | 0.0000 | 0.8000 | 0.3449 | 0.0313 |
| paddleocr | perspective+blur | en | 80 | 0.9625 | 1.0000 | 0.0377 | 0.0375 |
| paddleocr | perspective+blur | hi | 40 | 0.0000 | 0.7250 | 0.3420 | 0.0316 |
| paddleocr | low_light | en | 80 | 0.8875 | 0.9875 | 0.0204 | 0.0370 |
| paddleocr | low_light | hi | 40 | 0.0000 | 0.7250 | 0.3681 | 0.0331 |
| paddleocr | weathered(noise+fade) | en | 80 | 1.0000 | 1.0000 | 0.0000 | 0.0377 |
| paddleocr | weathered(noise+fade) | hi | 40 | 0.0000 | 0.8250 | 0.3391 | 0.0329 |
- Synthetic plates: real Indian km-post photos must be collected in pilot (gap).
- On-device app uses ML Kit Text Recognition v2 (Latin + Devanagari); not runnable in CI – evaluate on device.

_Environment_: GitHub Actions 1000000051 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T04:53:20.831960+00:00

## asr

_Not run or failed before writing results._

## translation

_Not run or failed before writing results._

## Track-defect detection: zero-shot vs quick fine-tune (Indian railway images)

Dataset stats: {'split': 'provided (Roboflow train/valid/test)', 'classes': 10, 'per_split': {'train': 6681, 'val': 606, 'test': 300}, 'images': 7587, 'instances_per_class': {'Broken-rail': 138, 'Corrosion': 6028, 'Cracks': 4855, 'Flakings': 4737, 'Joints': 396, 'Missing-fastener': 510, 'Shelling': 6245, 'Spalling': 4945, 'Squats': 3654, 'Wheel-burn': 4041}}.

| approach | model | test_set | n_images | mAP50 | mAP50_95 | median_latency_s |
|---|---|---|---|---|---|---|
| zero-shot | google/owlv2-base-patch16-ensemble | clean | 200 | 0.0000 | 0.0000 | 12.0743 |
| zero-shot | IDEA-Research/grounding-dino-tiny | clean | 200 | 0.0000 | 0.0000 | 6.7046 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | clean | 300 | 0.1367 | 0.0458 | 0.0249 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | dark | 300 | 0.0482 | 0.0150 | 0.0246 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | motion_blur | 300 | 0.0780 | 0.0212 | 0.0247 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | rain | 300 | 0.0747 | 0.0254 | 0.0246 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | glare | 300 | 0.1109 | 0.0383 | 0.0247 |
- YOLO11n fine-tune wall time 35.6 min on CPU; ONNX export: best.onnx (10.6 MB)
- CI fine-tune is a feasibility indicator only (CPU, few epochs, data fraction). Full training on RTX 5070: ml/train/train_detector.py.
- YOLO11 is AGPL-3.0: production use needs an Enterprise licence or an Apache-2.0 alternative (RF-DETR, D-FINE).
- Capture viewpoint of the dataset is not documented; wearable/handheld eye-level imagery differs (domain shift).

_Environment_: GitHub Actions 1000000050 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T06:22:31.255526+00:00

## dedup

_Not run or failed before writing results._
