# OHE Visual AI Patrol — Solution Definition (build baseline)

Derived from: *OHE Visual AI Patrol Application — Research HLD, Asset Inspection Framework and Development Specification*, v1.0, 31 Oct 2026 (the HLD). Section numbers in brackets refer to the HLD. This file fixes what is built first, how deep each part goes, and what is deliberately left out. It supersedes the earlier keyman / combined-patrol scope for the OHE product.

## 1. What the product is

A phone capture app plus a backend visual-inspection service for Indian Railways OHE. Evidence is **only photographs and video frames**; capture time and location are association metadata; the asset registry, reference atlas and rule registry are static context (§1.1). Voice is for commands only; dictated notes live in an isolated store and never reach inspection (§1.1 I-06, §3.2).

Field interaction: start patrol → capture assets → follow occasional targeted recapture prompts → end patrol → reviewer signs the generated report (§1.3). **No per-asset human confirmation.** Humans act only on capture, recapture, exceptions, corrections and signing.

## 2. Detection scope and depth (what the AI decides)

The pipeline is a cascade, not one model (§6, §7):

| Stage | Output | Depth in this build | Model / method |
|---|---|---|---|
| 1 Quality / assessability | per-image and per-ROI reason codes; Q score | Built: deterministic metrics (sharpness, exposure, clipping, target pixel footprint) | OpenCV; MobileNetV3 head later (needs assessability labels) |
| 2 Component detection | component boxes in original pixel coordinates | **Trained now** on public OHE data: insulator, insulator defect, plus classes of the powerline dataset | YOLO11n (CI baseline); RT-DETRv2-R18 (Apache-2.0, HLD core baseline) on the RTX 5070 |
| 3 OCR + identity | candidate assets, selected ID or *unresolved*; A score | Built: registry corridor candidates + OCR string match against numbering grammar, explicit *unknown* candidate, margin rule | PP-OCRv5 adapter (plate fine-tune needs plate data) |
| 4 Condition | visual symptom per component; C score | Built for **insulator visible damage** (trained); other classes return *unsupported* | detector defect class + crop classifier later |
| 5 Anomaly (unknown defects) | anomaly score + map vs normal bank | **Trained now**: PatchCore-style memory bank on normal insulator crops, evaluated on defect crops | frozen pretrained CNN features + kNN |
| 6 Assessment policy | observation / hypothesis / recommendation; confidence vector Q·A·V·C·T·R; assessability state | Built: decision matrix §8.4, abstention reasons, priority as consequence rule | deterministic rules + calibration hook |
| 7 Routing | primary coordinator + contributors | Built: versioned rule registry (YAML) → departments; unresolved → OHE coordination queue | configuration, not AI |
| 8 Cycle report | canonical report JSON → HTML/PDF; revisions, signing | Built: RPT-01…RPT-13 skeleton, immutable hashed revisions, sign-once | deterministic renderer, no AI at export |
| 9 Temporal (P1) | new / persistent / not comparable | Deferred until stable identity (§11, Release C) | — |
| VLM narrative | — | Deferred (§14.1: not first milestone) | Qwen3-VL-4B candidate |

Assessability states used everywhere (§2.2): `assessable_no_visible_defect`, `assessable_defect`, `anomalous_unclassified`, `insufficient_resolution`, `occluded_or_missing_view`, `uncertain_identity`, `no_evidence`.

Claims are always split three ways (§2.1): **observed feature** (pixels), **supported hypothesis**, **recommended verification/action**. The system never states electrical continuity, tension, height/stagger in mm, internal insulator health, or remaining life.

## 3. Decision matrix implemented (§8.4)

| Situation | Automatic decision |
|---|---|
| Clear evidence, identity resolved, class supported | Accept scoped assessment, route by rules |
| Image clear but target too small / hidden | Abstain for that scope, targeted recapture prompt |
| Defect evidence, identity uncertain | Keep finding with candidate set; priority independent of identity |
| Unsupported class or anomaly only | `anomalous_unclassified`, exception queue |
| Possible consequential condition | Immediate alert record, not waiting for report signature |
| Repeated evidence of same issue | One finding, more observations (no frame-count inflation) |

## 4. Process (end to end, as built)

1. `POST /ohe/sessions` — patrol start with territory and expected inventory.
2. `POST /ohe/sessions/{id}/media` — original bytes + manifest (capture time, lat/lon, accuracy, device). SHA-256 verified; same hash = idempotent (V07).
3. Pipeline runs per media: quality → detection → identity → condition/anomaly → assessment → routing; every model run stored with version.
4. `POST /ohe/sessions/{id}/end` — reconciliation: every expected asset gets a state; report revision 1 created (`READY_FOR_REVIEW`).
5. `POST /ohe/reports/{id}/sign` — authorised signer; revision hash frozen; any later change creates a new revision (V11).
6. Notes: `POST /ohe/sessions/{id}/notes` — separate table and endpoint; pipeline code has no import path to it; invariance test (V06).

## 5. Data and training plan (now)

| Dataset | Use | Licence → use |
|---|---|---|
| CPLID (corrected release, 845 UAV images, insulator + defect) | detector + insulator-damage + anomaly bank | upstream undetermined → research/benchmark only |
| Powerline components and faults (drone, YOLO format) | detector classes for OHE-like hardware | MIT → usable |
| Pilot OHE captures from phones (to be collected) | the production dataset for every class | Indian Railways owned |

Splits keep consecutive frames/chains together (§12.2). Metrics per class (§12.4): precision/recall, mAP@50, small-object recall; anomaly AUROC; no overall-mAP certification.

Domain warning: both public datasets are drone/transmission-line views, not 25 kV railway OHE from the ground. Results prove the pipeline and give starting weights; they are not field performance.

## 6. Out of scope for this build

Thermal/electrical inputs, SCADA, weather; VLM narrative; temporal forecasting; certificate-backed signing; Triton; national approval. Proposed HLD targets (99.5 % association precision, 95 % recall, ECE ≤ 0.05) are recorded as targets, not claims.

## 7. Results so far (CI run 41160563148, 31 Oct 2026, CPU)

Artifacts are on branch `ci-ohe-train`: `reports/ohe_detector.onnx` plus `names.json`, reports and logs.

**Detector:** yolo11n, 25 epochs, 640 px, 94 min on CPU. Held-out test split: 136 CPLID images, chain-grouped.

| Class | Precision | Recall | AP50 | AP50-95 |
|---|---|---|---|---|
| insulator | 0.972 | 0.952 | 0.988 | 0.861 |
| insulator_defect (missing cap) | 0.998 | 1.000 | 0.995 | 0.717 |

**Backend check:** the ONNX file loaded through `OnnxYoloDetector` produced detections on 20/20 test images.

**Anomaly branch** (insulator crops; 186 normal and 40 defective in test):
- AUROC 0.68.
- At the val-normal p95 threshold, it flags 15% of defective crops and 5.9% of normal crops.
- This is too weak to drive decisions. It stays an evidence signal that routes to `anomalous_unclassified` review only.

**Training data:**
- CPLID: 848 images, 1,321 insulators, 248 defects.
- Synthetic broken insulators (silera, CC BY): 203 images, train and val only.
- The powerline set (MIT) failed to load in this run. The loader is now fixed for its `bboxes`/`labels` columns (classes: Insulators, Broken Insulator, Vegetation).
- The Roboflow railway catenary/dropper/pantograph sets are skipped until the `ROBOFLOW_API_KEY` secret is set.

**What these numbers do and do not show:**
- CPLID consists of drone views of transmission-line insulators, and its defect images are composited on simple backgrounds. Near-perfect scores show only that the pipeline works end to end; they are not field accuracy on ground-level 25 kV OHE (HLD §12.1).
- Classes not yet trainable from public data: bird_nest, dropper, number_plate, catenary, pantograph. Until data exists for them, they return `unsupported_class` / `no_evidence`.
