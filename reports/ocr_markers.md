# OCR of km/OHE-mast markers (English & Hindi, synthetic plates)

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

**Notes**

- Synthetic plates: real Indian km-post photos must be collected in pilot (gap).
- On-device app uses ML Kit Text Recognition v2 (Latin + Devanagari); not runnable in CI – evaluate on device.

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000051", "timestamp_utc": "2026-10-30T04:53:20.831960+00:00", "torch": "2.15.0+cpu", "cuda": false}`
