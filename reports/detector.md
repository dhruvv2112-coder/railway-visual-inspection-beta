# Track-defect detection: zero-shot vs quick fine-tune (Indian railway images)

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

**Notes**

- YOLO11n fine-tune wall time 21.7 min on CI CPU; ONNX export: best.onnx (10.6 MB)
- CI fine-tune is a feasibility indicator only (CPU, few epochs, data fraction). Full training on RTX 5070: ml/train/train_detector.py.
- YOLO11 is AGPL-3.0: production use needs an Enterprise licence or an Apache-2.0 alternative (RF-DETR, D-FINE).
- Capture viewpoint of the dataset is not documented; wearable/handheld eye-level imagery differs (domain shift).

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000040", "timestamp_utc": "2026-10-30T04:14:00.487612+00:00", "torch": "2.15.0+cpu", "cuda": false}`
