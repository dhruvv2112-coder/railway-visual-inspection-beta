# Same-asset re-identification for duplicate suppression

Synthetic re-captures of Indian railway images.

| model | gallery | recall@1 | recall@5 | sec_per_image_cpu |
|---|---|---|---|---|
| facebook/dinov2-small | 300 | 0.7367 | 0.9033 | 0.0880 |
| google/siglip-base-patch16-224 | 300 | 0.3800 | 0.6700 | 0.2297 |

**Notes**

- Gallery images of the same defect class look alike; GNSS distance gating is applied first in production.

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000055", "timestamp_utc": "2026-10-30T06:44:22.270194+00:00", "torch": "2.15.0+cpu", "cuda": false}`
