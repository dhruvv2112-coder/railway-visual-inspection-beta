"""Translation of free-text notes (Hindi <-> English) for supervisors.
Parallel test data: FLEURS hi_in and en_us share sentence IDs (FLoRes-derived) -> parallel pairs.
Models: Helsinki-NLP Opus-MT (CC-BY-4.0) and NLLB-200 distilled 600M (CC-BY-NC-4.0, research comparison only).
Metrics: chrF++ and BLEU (sacrebleu)."""
import os
import time

import sacrebleu
from transformers import pipeline

from common import write_report
from datasets import fleurs

N = int(os.environ.get("MT_N", 150))


def pairs():
    hi = {r["id"]: r["text"] for r in fleurs("hi_in", "test", 2000)}
    en = {r["id"]: r["text"] for r in fleurs("en_us", "test", 2000)}
    ids = sorted(set(hi) & set(en))[:N]
    return [hi[i] for i in ids], [en[i] for i in ids]


MODELS = {
    ("hi", "en"): [("Helsinki-NLP/opus-mt-hi-en", {}), ("facebook/nllb-200-distilled-600M", {"src_lang": "hin_Deva", "tgt_lang": "eng_Latn"})],
    ("en", "hi"): [("Helsinki-NLP/opus-mt-en-hi", {}), ("facebook/nllb-200-distilled-600M", {"src_lang": "eng_Latn", "tgt_lang": "hin_Deva"})],
}


def main():
    hi, en = pairs()
    rows, notes = [], []
    for (s, t), cands in MODELS.items():
        src, ref = (hi, en) if s == "hi" else (en, hi)
        for mid, kw in cands:
            try:
                p = pipeline("translation", model=mid, device=-1, **kw)
                t0 = time.perf_counter()
                hyp = [o["translation_text"] for o in p(src, batch_size=8, max_length=256)]
                dt = time.perf_counter() - t0
                rows.append({"direction": f"{s}->{t}", "model": mid, "n": len(src),
                             "chrF++": sacrebleu.corpus_chrf(hyp, [ref], word_order=2).score,
                             "BLEU": sacrebleu.corpus_bleu(hyp, [ref]).score, "sec_per_sentence": dt / len(src)})
            except Exception as e:
                notes.append(f"{mid} {s}->{t} failed: {type(e).__name__}: {str(e)[:150]}")
    write_report("translation", "Note translation Hindi <-> English",
                 f"{len(hi)} FLEURS/FLoRes parallel sentences (general domain).", rows,
                 notes=notes + ["IndicTrans2 (MIT) is gated on Hugging Face – run on the laptop with an accepted HF token: ml/train/README.md.",
                                "NLLB-200 is CC-BY-NC: comparison only, not deployable commercially.",
                                "Railway terminology needs a glossary-constrained evaluation set (gap)."])


if __name__ == "__main__":
    main()
