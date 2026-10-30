"""T07 – Whisper-small + LoRA for Hindi/English dictation with railway vocabulary (RTX 5070, 8 GB).
Standard stack: transformers Seq2SeqTrainer + peft LoRA + datasets. Data: IndicVoices Hindi (CC BY 4.0)
plus the recorded railway command/notes set (ml/data/COMMAND_SET.md).

  python ml/train/finetune_whisper_lora.py --train_manifest data/hi_train.jsonl --eval_manifest data/hi_eval.jsonl
Manifest lines: {"audio": "path.wav", "text": "..."}
"""
import argparse

from datasets import Audio, load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (Seq2SeqTrainer, Seq2SeqTrainingArguments, WhisperForConditionalGeneration, WhisperProcessor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="openai/whisper-small")
    ap.add_argument("--train_manifest", required=True)
    ap.add_argument("--eval_manifest", required=True)
    ap.add_argument("--language", default="hindi")
    ap.add_argument("--out", default="runs/whisper-small-lora-hi")
    a = ap.parse_args()
    proc = WhisperProcessor.from_pretrained(a.base, language=a.language, task="transcribe")
    model = WhisperForConditionalGeneration.from_pretrained(a.base)
    model = get_peft_model(model, LoraConfig(r=32, lora_alpha=64, target_modules=["q_proj", "v_proj"], lora_dropout=0.05))
    ds = load_dataset("json", data_files={"train": a.train_manifest, "eval": a.eval_manifest}).cast_column("audio", Audio(sampling_rate=16000))

    def prep(b):
        b["input_features"] = proc.feature_extractor(b["audio"]["array"], sampling_rate=16000).input_features[0]
        b["labels"] = proc.tokenizer(b["text"]).input_ids
        return b

    ds = ds.map(prep, remove_columns=ds["train"].column_names)

    def collate(feats):
        x = proc.feature_extractor.pad([{"input_features": f["input_features"]} for f in feats], return_tensors="pt")
        y = proc.tokenizer.pad([{"input_ids": f["labels"]} for f in feats], return_tensors="pt")
        x["labels"] = y["input_ids"].masked_fill(y.attention_mask.ne(1), -100)
        return x

    args = Seq2SeqTrainingArguments(a.out, per_device_train_batch_size=8, gradient_accumulation_steps=2, learning_rate=1e-4,
                                    num_train_epochs=5, fp16=True, eval_strategy="epoch", save_strategy="epoch",
                                    predict_with_generate=True, remove_unused_columns=False, label_names=["labels"])
    Seq2SeqTrainer(model=model, args=args, train_dataset=ds["train"], eval_dataset=ds["eval"], data_collator=collate).train()
    model.save_pretrained(a.out)


if __name__ == "__main__":
    main()
