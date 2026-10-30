# Zero-shot defect detection (re-run with box-scaling and label-matching fixes)

Dataset stats: {'classes': 10, 'images': 7587, 'instances_per_class': {'Broken-rail': 138, 'Corrosion': 6028, 'Cracks': 4855, 'Flakings': 4737, 'Joints': 396, 'Missing-fastener': 510, 'Shelling': 6245, 'Spalling': 4945, 'Squats': 3654, 'Wheel-burn': 4041}, 'per_split': {'test': 300, 'train': 6681, 'val': 606}, 'split': 'provided (Roboflow train/valid/test)'}.

| approach | model | test_set | n_images | mAP50 | mAP50_95 | median_latency_s | agnostic_mAP50 | preds_per_image |
|---|---|---|---|---|---|---|---|---|
| zero-shot | google/owlv2-base-patch16-ensemble | clean | 100 | 0.0000 | 0.0000 | 10.5399 | 0.0000 | 13.5100 |
| zero-shot | IDEA-Research/grounding-dino-tiny | clean | 100 | 0.0000 | 0.0000 | 5.9442 | 0.0003 | 10.0800 |

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000054", "timestamp_utc": "2026-10-30T07:06:58.593977+00:00", "torch": "2.15.0+cpu", "cuda": false}`
