# Voice command set – recording protocol (gap: no public railway command corpus)

Purpose: measure intent accuracy of the on-device recogniser + `CommandMatcher` in field conditions.

- Speakers: ≥ 30 track staff (keymen, mates, JE/SSE) across ≥ 2 zones; record gender, age band and home language.
- Utterances: each command in `android/.../VoiceCommands.kt` × 3 repetitions × {Hindi, English, Hinglish}, plus 20 free-form notes.
- Conditions: quiet room; trackside (no train); passing train at ~30 m; rain/wind; with hearing protection where issued.
- Devices: the Beta handsets (V7 matrix); app logging mode stores audio only with written consent (DPDP Act 2023).
- Metrics: intent accuracy, false activations per hour of ambient audio, latency to action.
- Storage: 16 kHz mono WAV; manifest JSONL `{audio, text, intent, speaker, condition, device}`.
