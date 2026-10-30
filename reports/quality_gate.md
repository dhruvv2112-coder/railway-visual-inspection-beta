# Image-quality gate under field conditions

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

**Notes**

- Degradations are synthetic (albumentations) – field captures needed to confirm.
- Thresholds from backend/app/config.py; tune on pilot data.

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000055", "timestamp_utc": "2026-10-30T06:40:58.533608+00:00", "torch": "2.15.0+cpu", "cuda": false}`
