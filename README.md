# RVI Beta – Railway Visual Inspection (Android + backend + model benchmarks)

Beta of the inspection assistant defined in the Phase 1 Problem Definition Report. Smart-glasses integration is **out of
scope for Beta**. The phone camera and voice replace it, using the same workflow and record model.

```
android/   Kotlin · Jetpack Compose · Material 3 · Room · WorkManager · CameraX · SpeechRecognizer · ML Kit OCR
backend/   FastAPI · SQLModel · OpenCV quality gate · ONNX Runtime (optional detector) · hash-chained audit log
shared/    taxonomy.json – 98 defect classes from Phase 1 D02 (67 enabled for Beta, English + Hindi labels)
ml/bench/  benchmarks of pre-trained models under field conditions (run in CI) → reports/
ml/train/  training scripts for the RTX 5070 laptop
ml/registry/ model and dataset registries
docs/      standard-library check, test strategy
```

## Principles
1. **Protect first.** No screen, voice command or model can report a protect-first defect before line protection and
   the Station Master notification are recorded. Protection itself stays a human duty.
2. **AI suggests, people decide.** Model output is stored as candidates only. Severity is assigned by JE/SSE/ADEN.
3. **Offline first.** Everything is saved on the phone and synced by WorkManager when a network is available.
4. **Standard libraries first.** See `docs/STANDARD_LIBRARY_CHECK.md`.

## Run
```bash
# backend
cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload && pytest
# android (Android Studio, or):
cd android && gradle :app:assembleDebug :app:testDebugUnitTest :app:recordRoborazziDebug
# benchmarks (CPU) – GitHub Actions 'ml-bench', or locally:
pip install -r ml/requirements-bench.txt && cd ml/bench && python bench_quality_gate.py
# training on the laptop (RTX 5070, CUDA 12.8 PyTorch)
pip install -r ml/train/requirements-train.txt && python ml/train/train_detector.py --arch rfdetr-small
```

The Gradle wrapper jar is not committed. CI uses `gradle/actions/setup-gradle` (Gradle 8.11.1). Locally, Android Studio
or `gradle wrapper --gradle-version 8.11.1` generates it.

## Licences
App code: proprietary (TBD by owner). Fonts: JetBrains Mono (SIL OFL 1.1, `docs/FONT_LICENSE_OFL.txt`). Third-party
model and dataset licences are listed in `ml/registry/*.yaml`. Several datasets are **research-only**.
