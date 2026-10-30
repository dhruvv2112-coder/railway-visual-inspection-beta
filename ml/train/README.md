# Training on the ProArt P16 (RTX 5070 Laptop GPU, 8 GB VRAM, 32 GB RAM)

## Setup (Windows 11 or Linux)
```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128   # Blackwell (sm_120) needs CUDA 12.8 builds, PyTorch >= 2.7
pip install -r ml/train/requirements-train.txt
python -c "import torch;print(torch.cuda.get_device_name(0))"
```

## Gated models (accept the licence on Hugging Face first, then `huggingface-cli login`)
- IndicTrans2 distilled 200M (`ai4bharat/indictrans2-en-indic-dist-200M`, `...-indic-en-dist-200M`), MIT.
- IndicConformer Hindi (`ai4bharat/indicconformer_stt_hi_hybrid_ctc_rnnt_large`), via NeMo.
Run the same benchmark scripts with the extra models: `MT_EXTRA=indictrans2 python ml/bench/bench_translation.py`.

## Jobs (see ml/registry/models.yaml → train_on_laptop)
| ID | Command |
|---|---|
| T01 | `python ml/train/train_detector.py --arch rfdetr-small --epochs 50 --batch 4` |
| T02 | `python ml/train/train_detector.py --arch yolo11s --epochs 100` |
| T07 | `python ml/train/finetune_whisper_lora.py --train_manifest hi_train.jsonl --eval_manifest hi_eval.jsonl` |

8 GB VRAM: keep detector batch ≤ 8 at 560–640 px with AMP; use `grad_accum_steps` for a larger effective batch.
Export the best detector to ONNX and point the backend at it with `RVI_DETECTOR_ONNX=...` and `RVI_DETECTOR_LABELS=labels.json`.
Suggestions stay hidden (shadow mode) until the thresholds in docs/TEST_STRATEGY.md are met on field data.
