"""Speech recognition for voice commands and dictated notes (Hindi, English).
Real speech: FLEURS hi_in / en_us test (CC BY 4.0). Field noise: ESC-50 train/rain/wind/engine clips
mixed at 10, 5 and 0 dB SNR (trackside conditions). Engines: Vosk (Apache-2.0, on-device class) and
Whisper via faster-whisper (MIT). Metrics: WER, CER (jiwer), real-time factor."""
import json
import os
import random
import re
import time
import wave
import zipfile

import jiwer
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from common import DATA, write_report
from datasets import _get, esc50_noise, fleurs

N = int(os.environ.get("ASR_N", 60))
random.seed(0)
VOSK = {"hi": ["vosk-model-small-hi-0.22", "vosk-model-hi-0.22"], "en": ["vosk-model-small-en-in-0.4", "vosk-model-en-in-0.5"]}
WHISPER = os.environ.get("WHISPER_SIZES", "tiny,small,large-v3-turbo").split(",")
FLEURS_LANG = {"hi": "hi_in", "en": "en_us"}


def load16(p):
    a, sr = sf.read(p, dtype="float32", always_2d=True)
    a = a.mean(1)
    if sr != 16000:
        a = resample_poly(a, 16000, sr).astype("float32")
    return a


def mix(speech, noise, snr):
    if len(noise) < len(speech):
        noise = np.tile(noise, int(np.ceil(len(speech) / len(noise))))
    noise = noise[: len(speech)]
    ps, pn = np.mean(speech ** 2) + 1e-9, np.mean(noise ** 2) + 1e-9
    return np.clip(speech + noise * np.sqrt(ps / (pn * 10 ** (snr / 10))), -1, 1).astype("float32")


def norm(s):
    s = s.lower()
    s = re.sub(r"[।॥,.!?;:\"'()\-]", " ", s)
    return " ".join(s.split()) or "∅"


def vosk_engine(name):
    from vosk import KaldiRecognizer, Model, SetLogLevel
    SetLogLevel(-1)
    z = _get(f"https://alphacephei.com/vosk/models/{name}.zip", DATA / "vosk" / f"{name}.zip")
    d = DATA / "vosk" / name
    if not d.exists():
        with zipfile.ZipFile(z) as zz:
            zz.extractall(DATA / "vosk")
    model = Model(str(d))

    def run(audio, lang):
        rec = KaldiRecognizer(model, 16000)
        pcm = (audio * 32767).astype("<i2").tobytes()
        for i in range(0, len(pcm), 8000):
            rec.AcceptWaveform(pcm[i:i + 8000])
        return json.loads(rec.FinalResult()).get("text", "")
    return run


def whisper_engine(size):
    from faster_whisper import WhisperModel
    if os.environ.get("RVI_DEVICE") == "cuda":
        try:
            m = WhisperModel(size, device="cuda", compute_type="float16")
        except Exception:
            m = WhisperModel(size, device="cpu", compute_type="int8")
    else:
        m = WhisperModel(size, device="cpu", compute_type="int8")

    def run(audio, lang):
        segs, _ = m.transcribe(audio, language=lang, beam_size=1, vad_filter=False)
        return " ".join(s.text for s in segs)
    return run


def main():
    noises = [load16(p) for p in esc50_noise()]
    rows, notes = [], []
    for lang in ("hi", "en"):
        utts = fleurs(FLEURS_LANG[lang], "test", N)
        audios = [load16(u["wav"]) for u in utts]
        refs = [norm(u["norm"]) for u in utts]
        engines = {f"vosk:{n}": (lambda n=n: vosk_engine(n)) for n in VOSK[lang]}
        engines |= {f"whisper:{s}": (lambda s=s: whisper_engine(s)) for s in WHISPER}
        for ename, factory in engines.items():
            try:
                fn = factory()
            except Exception as e:
                notes.append(f"{ename} load failed: {type(e).__name__}: {str(e)[:150]}")
                continue
            for cond in ("clean", "noise_10dB", "noise_5dB", "noise_0dB"):
                hyps, dur, proc = [], 0.0, 0.0
                for a in audios:
                    x = a if cond == "clean" else mix(a, random.choice(noises), int(cond.split("_")[1][:-2]))
                    t = time.perf_counter()
                    try:
                        h = fn(x, lang)
                    except Exception as e:
                        h = ""
                        notes.append(f"{ename} decode error: {e}")
                    proc += time.perf_counter() - t
                    dur += len(x) / 16000
                    hyps.append(norm(h))
                rows.append({"lang": lang, "engine": ename, "condition": cond, "n": len(refs),
                             "wer": float(jiwer.wer(refs, hyps)), "cer": float(jiwer.cer(refs, hyps)),
                             "rtf": proc / dur})
    write_report("asr", "Speech recognition (Hindi, English) – clean and trackside noise",
                 "FLEURS test utterances; noise from ESC-50 (train, rain, wind, engine, bells). Lower WER/CER is better; RTF < 1 is faster than real time.",
                 rows, notes=notes + ["FLEURS is read speech (general domain); railway command vocabulary needs a recorded command set (see ml/data/COMMAND_SET.md).",
                                      "Android on-device SpeechRecognizer (Google) cannot run in CI – evaluate on target handsets with the same command set."])


if __name__ == "__main__":
    main()
