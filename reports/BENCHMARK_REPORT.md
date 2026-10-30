# RVI Beta – Model Benchmark Report
All numbers produced by `ml/bench/*` in CI. Each section lists its data source, environment and failures.

## Image-quality gate under field conditions

Source: Mendeley 88sh5y3tmj v2 (Indian railway track images, CC BY 4.0). False-rejection on usable images: 24.4%. Unusable images wrongly passed: 2.7%.

| condition | expected | n | pass_rate | correct_rate | median_sharpness | median_brightness |
|---|---|---|---|---|---|---|
| clean | pass | 200 | 0.9300 | 0.9300 | 796.6249 | 141.7191 |
| dark_mild | pass | 200 | 0.1850 | 0.1850 | 668.0372 | 67.4631 |
| dark_severe(night_no_torch) | reject | 200 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| motion_blur_mild | pass | 200 | 0.9100 | 0.9100 | 211.9664 | 141.6688 |
| motion_blur_severe(walking) | reject | 200 | 0.1350 | 0.8650 | 24.1548 | 141.6431 |
| defocus_severe | reject | 200 | 0.0000 | 1.0000 | 2.1457 | 142.0483 |
| rain_drops | pass | 200 | 1.0000 | 1.0000 | 543.7116 | 126.5760 |
| fog_dust_dense | reject | 200 | 0.0000 | 1.0000 | 2.0540 | 211.7872 |
| glare_overexposed | reject | 200 | 0.0000 | 1.0000 | 61.8081 | 249.1174 |
- Degradations are synthetic (albumentations) – field captures needed to confirm.
- Thresholds from backend/app/config.py; tune on pilot data.

_Environment_: GitHub Actions 1000000042 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T02:57:48.378067+00:00

## OCR of km/OHE-mast markers (English & Hindi, synthetic plates)

Best clean-condition exact match: tesseract-5 en 100.0%.

| engine | condition | lang | n | exact_match | cer | median_latency_s |
|---|---|---|---|---|---|---|
| tesseract-5 | clean | en | 80 | 1.0000 | 0.0000 | 0.1337 |
| tesseract-5 | clean | hi | 40 | 0.0000 | 0.4609 | 0.1534 |
| tesseract-5 | perspective+blur | en | 80 | 0.6500 | 0.2594 | 0.1365 |
| tesseract-5 | perspective+blur | hi | 40 | 0.1750 | 0.2754 | 0.1622 |
| tesseract-5 | low_light | en | 80 | 0.9875 | 0.0079 | 0.1310 |
| tesseract-5 | low_light | hi | 40 | 0.0250 | 0.6087 | 0.1519 |
| tesseract-5 | weathered(noise+fade) | en | 80 | 0.0000 | 0.9827 | 0.1886 |
| tesseract-5 | weathered(noise+fade) | hi | 40 | 0.0000 | 0.9942 | 0.2335 |
| easyocr | clean | en | 80 | 1.0000 | 0.0000 | 1.7930 |
| easyocr | clean | hi | 40 | 0.0000 | 0.4145 | 1.6911 |
| easyocr | perspective+blur | en | 80 | 0.9875 | 0.0016 | 1.4865 |
| easyocr | perspective+blur | hi | 40 | 0.0000 | 0.4145 | 1.6777 |
| easyocr | low_light | en | 80 | 1.0000 | 0.0000 | 1.5195 |
| easyocr | low_light | hi | 40 | 0.0000 | 0.3913 | 1.6711 |
| easyocr | weathered(noise+fade) | en | 80 | 1.0000 | 0.0000 | 1.5627 |
| easyocr | weathered(noise+fade) | hi | 40 | 0.0000 | 0.4174 | 1.6999 |
- paddleocr/clean/en failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- paddleocr/clean/hi failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- paddleocr/perspective+blur/en failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- paddleocr/perspective+blur/hi failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- paddleocr/low_light/en failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- paddleocr/low_light/hi failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- paddleocr/weathered(noise+fade)/en failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- paddleocr/weathered(noise+fade)/hi failed: NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/in
- Synthetic plates: real Indian km-post photos must be collected in pilot (gap).
- On-device app uses ML Kit Text Recognition v2 (Latin + Devanagari); not runnable in CI – evaluate on device.

_Environment_: GitHub Actions 1000000042 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T03:13:14.147810+00:00

## Speech recognition (Hindi, English) – clean and trackside noise

FLEURS test utterances; noise from ESC-50 (train, rain, wind, engine, bells). Lower WER/CER is better; RTF < 1 is faster than real time.

| lang | engine | condition | n | wer | cer | rtf |
|---|---|---|---|---|---|---|
| hi | vosk:vosk-model-small-hi-0.22 | clean | 60 | 0.1480 | 0.0638 | 0.1391 |
| hi | vosk:vosk-model-small-hi-0.22 | noise_10dB | 60 | 0.2721 | 0.1712 | 0.2330 |
| hi | vosk:vosk-model-small-hi-0.22 | noise_5dB | 60 | 0.4236 | 0.3237 | 0.2721 |
| hi | vosk:vosk-model-small-hi-0.22 | noise_0dB | 60 | 0.7430 | 0.6804 | 0.3126 |
| hi | vosk:vosk-model-hi-0.22 | clean | 60 | 0.0932 | 0.0397 | 0.1412 |
| hi | vosk:vosk-model-hi-0.22 | noise_10dB | 60 | 0.1528 | 0.0917 | 0.1794 |
| hi | vosk:vosk-model-hi-0.22 | noise_5dB | 60 | 0.3550 | 0.2822 | 0.2326 |
| hi | vosk:vosk-model-hi-0.22 | noise_0dB | 60 | 0.5223 | 0.4820 | 0.2255 |
| hi | whisper:tiny | clean | 60 | 1.0713 | 0.9689 | 0.3694 |
| hi | whisper:tiny | noise_10dB | 60 | 1.0877 | 0.9817 | 0.4503 |
| hi | whisper:tiny | noise_5dB | 60 | 1.2399 | 1.1053 | 0.4611 |
| hi | whisper:tiny | noise_0dB | 60 | 1.1556 | 1.0098 | 0.5365 |
| hi | whisper:small | clean | 60 | 0.6038 | 0.2745 | 0.6858 |
| hi | whisper:small | noise_10dB | 60 | 0.6765 | 0.3337 | 0.8868 |
| hi | whisper:small | noise_5dB | 60 | 0.7087 | 0.3653 | 1.0004 |
| hi | whisper:small | noise_0dB | 60 | 0.8060 | 0.4928 | 1.3868 |
| hi | whisper:large-v3-turbo | clean | 60 | 0.3365 | 0.1322 | 1.1486 |
| hi | whisper:large-v3-turbo | noise_10dB | 60 | 0.3914 | 0.1742 | 1.1351 |
| hi | whisper:large-v3-turbo | noise_5dB | 60 | 0.4373 | 0.1995 | 1.0985 |
| hi | whisper:large-v3-turbo | noise_0dB | 60 | 0.5483 | 0.2852 | 1.1778 |
| en | vosk:vosk-model-small-en-in-0.4 | clean | 60 | 0.8966 | 0.8477 | 0.0946 |
| en | vosk:vosk-model-small-en-in-0.4 | noise_10dB | 60 | 0.9458 | 0.9106 | 0.0953 |
| en | vosk:vosk-model-small-en-in-0.4 | noise_5dB | 60 | 0.9588 | 0.9294 | 0.0894 |
| en | vosk:vosk-model-small-en-in-0.4 | noise_0dB | 60 | 0.9877 | 0.9736 | 0.0877 |
| en | vosk:vosk-model-en-in-0.5 | clean | 60 | 0.8496 | 0.8115 | 0.1452 |
| en | vosk:vosk-model-en-in-0.5 | noise_10dB | 60 | 0.9205 | 0.8718 | 0.2004 |
| en | vosk:vosk-model-en-in-0.5 | noise_5dB | 60 | 0.9219 | 0.8787 | 0.1915 |
| en | vosk:vosk-model-en-in-0.5 | noise_0dB | 60 | 0.9761 | 0.9489 | 0.2149 |
| en | whisper:tiny | clean | 60 | 0.1967 | 0.0944 | 0.0526 |
| en | whisper:tiny | noise_10dB | 60 | 0.2552 | 0.1363 | 0.0610 |
| en | whisper:tiny | noise_5dB | 60 | 0.3463 | 0.1884 | 0.0627 |
| en | whisper:tiny | noise_0dB | 60 | 0.5242 | 0.3291 | 0.0872 |
| en | whisper:small | clean | 60 | 0.0860 | 0.0483 | 0.2537 |
| en | whisper:small | noise_10dB | 60 | 0.0962 | 0.0537 | 0.2515 |
| en | whisper:small | noise_5dB | 60 | 0.1569 | 0.0917 | 0.2569 |
| en | whisper:small | noise_0dB | 60 | 0.2762 | 0.1732 | 0.2530 |
| en | whisper:large-v3-turbo | clean | 60 | 0.0701 | 0.0448 | 1.1289 |
| en | whisper:large-v3-turbo | noise_10dB | 60 | 0.0795 | 0.0487 | 1.1306 |
| en | whisper:large-v3-turbo | noise_5dB | 60 | 0.1034 | 0.0633 | 1.1030 |
| en | whisper:large-v3-turbo | noise_0dB | 60 | 0.1396 | 0.0908 | 1.1171 |
- FLEURS is read speech (general domain); railway command vocabulary needs a recorded command set (see ml/data/COMMAND_SET.md).
- Android on-device SpeechRecognizer (Google) cannot run in CI – evaluate on target handsets with the same command set.

_Environment_: GitHub Actions 1000000043 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T06:29:00.655730+00:00

## Note translation Hindi <-> English

150 FLEURS/FLoRes parallel sentences (general domain).

| direction | model | n | chrF++ | BLEU | sec_per_sentence |
|---|---|---|---|---|---|
| hi->en | Helsinki-NLP/opus-mt-hi-en | 150 | 43.4157 | 18.9104 | 0.2582 |
| hi->en | facebook/nllb-200-distilled-600M | 150 | 62.2894 | 38.6857 | 2.0036 |
| en->hi | Helsinki-NLP/opus-mt-en-hi | 150 | 32.4988 | 12.8944 | 0.2501 |
| en->hi | facebook/nllb-200-distilled-600M | 150 | 52.3539 | 29.1874 | 2.4109 |
- IndicTrans2 (MIT) is gated on Hugging Face – run on the laptop with an accepted HF token: ml/train/README.md.
- NLLB-200 is CC-BY-NC: comparison only, not deployable commercially.
- Railway terminology needs a glossary-constrained evaluation set (gap).

_Environment_: GitHub Actions 1000000041 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T03:08:31.990002+00:00

## Track-defect detection: zero-shot vs quick fine-tune (Indian railway images)

Dataset stats: {'images': 7587, 'classes': 10, 'per_split': {'train': 6069, 'val': 759, 'test': 759}, 'instances_per_class': {'0': 138, '1': 6028, '2': 4855, '3': 4737, '4': 396, '5': 510, '6': 6245, '7': 4945, '8': 3654, '9': 4041}}.

| approach | model | test_set | n_images | mAP50 | mAP50_95 | median_latency_s_cpu |
|---|---|---|---|---|---|---|
| zero-shot | google/owlv2-base-patch16-ensemble | clean | 200 | 0.0000 | 0.0000 | 10.6202 |
| zero-shot | IDEA-Research/grounding-dino-tiny | clean | 200 | 0.0000 | 0.0000 | 5.7771 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | clean | 759 | 0.1384 | 0.0510 | 0.0124 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | dark | 759 | 0.0471 | 0.0165 | 0.0125 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | motion_blur | 759 | 0.0813 | 0.0229 | 0.0125 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | rain | 759 | 0.0707 | 0.0238 | 0.0124 |
| fine-tuned (8 ep, 40% train, CPU) | yolo11n | glare | 759 | 0.1128 | 0.0410 | 0.0124 |
- YOLO11n fine-tune wall time 21.7 min on CI CPU; ONNX export: best.onnx (10.6 MB)
- CI fine-tune is a feasibility indicator only (CPU, few epochs, data fraction). Full training on RTX 5070: ml/train/train_detector.py.
- YOLO11 is AGPL-3.0: production use needs an Enterprise licence or an Apache-2.0 alternative (RF-DETR, D-FINE).
- Capture viewpoint of the dataset is not documented; wearable/handheld eye-level imagery differs (domain shift).

_Environment_: GitHub Actions 1000000040 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T04:14:00.487612+00:00

## Same-asset re-identification for duplicate suppression

Synthetic re-captures of Indian railway images.

| model | gallery | recall@1 | recall@5 | sec_per_image_cpu |
|---|---|---|---|---|
| facebook/dinov2-small | 300 | 0.7467 | 0.9067 | 0.0887 |
| google/siglip-base-patch16-224 | 300 | 0.3867 | 0.6733 | 0.2246 |
- Gallery images of the same defect class look alike; GNSS distance gating is applied first in production.

_Environment_: GitHub Actions 1000000042 · 4 CPU · torch 2.15.0+cpu · 2026-10-30T03:16:36.530924+00:00
