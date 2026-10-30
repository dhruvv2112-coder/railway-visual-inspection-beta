# OCR of km/OHE-mast markers (English & Hindi, synthetic plates)

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

**Notes**

- Synthetic plates: real Indian km-post photos must be collected in pilot (gap).
- On-device app uses ML Kit Text Recognition v2 (Latin + Devanagari); not runnable in CI – evaluate on device.

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000055", "timestamp_utc": "2026-10-30T07:01:51.063210+00:00", "torch": "2.15.0+cpu", "cuda": false}`
