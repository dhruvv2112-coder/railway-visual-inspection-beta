# Test and validation stages

Stages map to industry practice for safety-related, citizen- and employee-facing digital systems: software verification,
model validation, human-factors evaluation, then field validation. The app is a decision-support and record tool. It never
controls trains, so railway signalling safety-integrity levels do not apply to the software. They do apply to the
procedures it records, and that is why protection always comes first and stays human.

| Stage | What | Tooling | Gate to pass | Status |
|---|---|---|---|---|
| V1 Unit | Domain rules (command matching, quality gate, taxonomy), API business rules R1–R6 | JUnit, pytest | 100 % pass | Automated (CI) |
| V2 Static analysis | Android Lint, ruff | Gradle lint, ruff | No errors | Automated (CI) |
| V3 Build | Debug APK assembles for minSdk 26, target 35 | Gradle | Green | Automated (CI) |
| V4 Visual regression | Every screen, English + Hindi, rendered on JVM | Roborazzi | Baselines reviewed | Automated (CI) |
| V5 Model benchmark | Quality gate, OCR, ASR, MT, detection (zero-shot vs fine-tune), dedup under conditions | ml/bench | Thresholds below | Automated (CI) |
| V6 Accessibility | Touch targets ≥ 48 dp (HUD 60–88 dp), contrast ≥ 7:1 (white on #0B0B0C ≈ 19.5:1), TalkBack labels, font scale 200 % | Accessibility Scanner, manual | WCAG 2.2 AA (GIGW 3.0 for government apps) | Manual, pre-pilot |
| V7 Device matrix | 6 handsets (entry/mid/rugged), Android 10–15, on-device speech availability | Firebase Test Lab / manual | No crash; graceful fallback | Pre-pilot |
| V8 Security & privacy | OWASP MASVS L1, DPDP Act 2023, trackside imagery handling | MobSF, review | No high findings | Pre-pilot |
| V9 Human factors (closed track) | Seeded-defect walk, head-down time, glove use, noise | Observation, SUS, NASA-TLX | SUS ≥ 70; no added protection delay | Pilot phase A |
| V10 Field pilot | 2 zones, ≥ 20 beats, day/night/rain; paired with normal practice | TMS comparison | Phase 1 KPIs | Pilot phase B |

## Model acceptance thresholds (proposed – to agree with railway engineers)
- Quality gate: ≤ 10 % false rejection on usable images; ≤ 10 % unusable images passed.
- Detector suggestions (Category A classes): per-class recall ≥ 0.90 at precision ≥ 0.80 on field test data before suggestions are shown.
  Below that, the model runs in shadow mode (logged, not shown).
- Voice commands: intent accuracy ≥ 95 % in quiet, ≥ 85 % at 5 dB SNR trackside noise, per language; false-activation ≤ 1 per hour.
- OCR (km/mast plates): exact match ≥ 95 % on clean, ≥ 85 % on field captures; inspector always confirms.
- Translation: chrF++ reported per direction; supervisor sees the original text alongside the translation.
