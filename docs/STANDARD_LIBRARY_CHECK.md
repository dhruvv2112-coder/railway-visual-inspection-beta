# Standard-library-first check

Rule: before building a capability, look for a maintained standard library or platform API. Write custom code only
when no standard option fits, and record why. This log is reviewed in every pull request.

| Capability | Standard option chosen | Custom code? | Reason / rejected alternative |
|---|---|---|---|
| Android UI | Jetpack Compose + Material 3 | No | Google-recommended UI toolkit |
| Translucent "glass" surfaces | Compose `Modifier.blur`, alpha fills, `BorderStroke` | ~60 lines of composables | Haze (third-party backdrop blur) rejected for Beta: API churn across 0.7→1.x; revisit for true backdrop blur |
| Navigation | Navigation Compose | No | |
| Dependency injection | Manual container (`AppContainer`) | ~10 lines | Android guide "Manual DI"; Hilt adds KSP/kapt cost for a one-module Beta |
| Local storage (offline-first) | Room + DataStore | No | |
| Background sync, retries | WorkManager (constraints, exponential backoff) | No | |
| Networking | Retrofit + OkHttp + kotlinx.serialization | No | |
| Camera | CameraX (Preview, ImageCapture) | No | |
| Location | Fused Location Provider | No | |
| Speech to text | Android `SpeechRecognizer` (on-device API 31+) | No | Bundled Vosk is the offline fallback (Apache-2.0) |
| Command matching | Apache Commons Text `LevenshteinDistance` | ~40 lines (phrase table) | No standard intent matcher for a closed bilingual vocabulary |
| Text to speech | Android `TextToSpeech` | No | |
| Per-app language | AppCompat `setApplicationLocales` + `generateLocaleConfig` | No | Google multilingual guidance |
| OCR on device | ML Kit Text Recognition v2 (Devanagari) | No | |
| Image-quality gate (device) | — | ~40 lines | OpenCV-Android adds ~30 MB for two statistics; parity with backend OpenCV is unit-tested |
| Image-quality gate (server) | OpenCV (`Laplacian`, `mean`) | No | |
| API server | FastAPI + Pydantic + SQLModel | No | |
| NMS / pre-processing | `cv2.dnn.NMSBoxes`, `cv2.dnn.blobFromImage` | No | |
| Model inference (server) | ONNX Runtime | No | |
| Audit trail | `hashlib` SHA-256 chain | ~25 lines | No standard append-only ledger in stdlib; DB-level options deferred |
| Detection metrics | torchmetrics `MeanAveragePrecision` (COCO protocol) | No | |
| ASR metrics | jiwer | No | |
| MT metrics | sacrebleu | No | |
| Augmentation / condition simulation | albumentations | No | |
| Detector training | rfdetr, ultralytics | No | |
| ASR fine-tune | transformers + peft | No | |
| Screenshot / visual regression | Roborazzi + Robolectric | No | |
