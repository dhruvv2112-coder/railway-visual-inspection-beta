"""Train the track-defect detector on the ProArt P16 (RTX 5070 Laptop, 8 GB VRAM).

  pip install -r ml/train/requirements-train.txt   # PyTorch >= 2.7 cu128 (Blackwell sm_120)
  python ml/train/train_detector.py --arch rfdetr-small --epochs 50
  python ml/train/train_detector.py --arch yolo11s --epochs 100       # AGPL reference

Dataset: ml/bench/railds.py output (YOLO layout). RF-DETR expects COCO; we convert with the library's
own 'supervision' utilities (standard) rather than custom code.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
from railds import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default="rfdetr-small", choices=["rfdetr-nano", "rfdetr-small", "rfdetr-medium", "yolo11n", "yolo11s"])
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=560)
    ap.add_argument("--batch", type=int, default=4)
    args = ap.parse_args()
    yaml_path, names, stats = build()
    print("dataset", stats)
    out = Path("runs") / args.arch
    if args.arch.startswith("yolo"):
        from ultralytics import YOLO
        YOLO(f"{args.arch}.pt").train(data=str(yaml_path), epochs=args.epochs, imgsz=max(args.imgsz, 640), batch=16, amp=True,
                                      device=0, project=str(out.parent), name=out.name, cos_lr=True, close_mosaic=10)
        return
    import supervision as sv
    from rfdetr import RFDETRMedium, RFDETRNano, RFDETRSmall
    root = Path(yaml_path).parent
    coco = root.parent / "rail_coco"
    for split in ("train", "val", "test"):
        ds = sv.DetectionDataset.from_yolo(images_directory_path=str(root / split / "images"),
                                           annotations_directory_path=str(root / split / "labels"), data_yaml_path=str(yaml_path))
        target = coco / ("valid" if split == "val" else split)
        ds.as_coco(images_directory_path=str(target), annotations_path=str(target / "_annotations.coco.json"))
    model = {"rfdetr-nano": RFDETRNano, "rfdetr-small": RFDETRSmall, "rfdetr-medium": RFDETRMedium}[args.arch]()
    model.train(dataset_dir=str(coco), epochs=args.epochs, batch_size=args.batch, grad_accum_steps=4, resolution=args.imgsz,
                output_dir=str(out), early_stopping=True)
    model.export(output_dir=str(out))  # ONNX for backend/app/inference.py


if __name__ == "__main__":
    main()
