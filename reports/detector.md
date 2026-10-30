# Track-defect detection: zero-shot vs quick fine-tune (Indian railway images)

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

**Notes**

- YOLO11n fine-tune wall time 35.6 min on CPU; ONNX export: best.onnx (10.6 MB)
- CI fine-tune is a feasibility indicator only (CPU, few epochs, data fraction). Full training on RTX 5070: ml/train/train_detector.py.
- YOLO11 is AGPL-3.0: production use needs an Enterprise licence or an Apache-2.0 alternative (RF-DETR, D-FINE).
- Capture viewpoint of the dataset is not documented; wearable/handheld eye-level imagery differs (domain shift).

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000050", "timestamp_utc": "2026-10-30T06:22:31.255526+00:00", "torch": "2.15.0+cpu", "cuda": false}`
