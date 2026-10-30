# OCR of km/OHE-mast markers (English & Hindi, synthetic plates)

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

**Notes**

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

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000042", "timestamp_utc": "2026-10-30T03:13:14.147810+00:00", "torch": "2.15.0+cpu", "cuda": false}`
