# Note translation Hindi <-> English

150 FLEURS/FLoRes parallel sentences (general domain).

| direction | model | n | chrF++ | BLEU | sec_per_sentence |
|---|---|---|---|---|---|
| hi->en | Helsinki-NLP/opus-mt-hi-en | 150 | 43.4157 | 18.9104 | 0.2582 |
| hi->en | facebook/nllb-200-distilled-600M | 150 | 62.2894 | 38.6857 | 2.0036 |
| en->hi | Helsinki-NLP/opus-mt-en-hi | 150 | 32.4988 | 12.8944 | 0.2501 |
| en->hi | facebook/nllb-200-distilled-600M | 150 | 52.3539 | 29.1874 | 2.4109 |

**Notes**

- IndicTrans2 (MIT) is gated on Hugging Face – run on the laptop with an accepted HF token: ml/train/README.md.
- NLLB-200 is CC-BY-NC: comparison only, not deployable commercially.
- Railway terminology needs a glossary-constrained evaluation set (gap).

_Environment_: `{"python": "3.11.17", "machine": "x86_64", "processor": "x86_64", "cpu_count": 4, "runner": "GitHub Actions 1000000041", "timestamp_utc": "2026-10-30T03:08:31.990002+00:00", "torch": "2.15.0+cpu", "cuda": false}`
