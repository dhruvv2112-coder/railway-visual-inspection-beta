# OHE dataset search log and catalogue (updated 1 Nov 2026)

The search ran one class and one platform at a time: web search, GitHub search, Hugging Face (keyword search run from CI, see `ml/ohe/survey_sources.py` → branch `ci-ohe-survey`), Zenodo API, figshare API, GitHub releases, FID move (OSDaR23), Kaggle and Roboflow Universe.

Every candidate is listed below with whether it can be fetched without a person signing in.

**Legend:**

| Mark | Meaning |
|---|---|
| ✅ | In the training pipeline |
| 🟡 | Downloadable; not yet used |
| 🔑 | Needs a key or login |
| ⛔ | Not obtainable (paper only, Baidu Pan, or on request) |

## Coverage of the HLD component classes

| HLD class | Best public data found | Status | Gap |
|---|---|---|---|
| insulator | CPLID; docmhvr powerline; MPID; EBIST railway cantilever insulator | ✅ | Railway 25 kV insulators are only a small eval set (EBIST) |
| insulator_defect | CPLID (missing cap); powerline broken insulator; VPMBGI broken glass; silera synthetic | ✅ | Flashover only in EPRI (by request) |
| vegetation | powerline "Vegetation"; EPDCL vegetation_conductor (phone, India) | ✅ | |
| bird_nest | RailFOD23 (railway lines, partly synthetic) | ✅ | RailCatFOD-DS (8,336 railway catenary nests) is Baidu Pan only ⛔ |
| foreign_object (kite, bag, balloon) | RailFOD23 | ✅ | Same as above |
| mast (pole/structure) | EPDCL pole_detection (phone, India, 11 kV poles); OSDaR23 catenary poles (rail view) | ✅ EPDCL; 🟡 OSDaR23 | No railway mast photos from the ground |
| corrosion | Corrosion RF100 (generic steel) | ✅ | Not OHE-specific |
| cantilever / registration / fittings | EBIST_cscuav (real railway cantilever parts, MVTec layout, crack masks) | ✅ anomaly eval only | Detector boxes need Roboflow catenary sets 🔑 or pilot |
| dropper | Chinese papers only (data on request); Roboflow railway-monitor/catenary 🔑 | ⛔/🔑 | **Pilot capture needed** |
| catenary / contact wire | Roboflow railway-monitor/catenary 🔑; OSDaR23 (no wire class) | 🔑 | |
| number_plate (mast number) | Roboflow utility-pole-label 🔑; PLAD "tower plate" (drone) 🟡 | 🟡/🔑 | **Pilot capture needed**; OCR uses PP-OCRv5 zero-shot until then |
| pantograph | Roboflow pantograph sets 🔑 | 🔑 | Not an on-foot patrol item |
| perspective / assessability (quality gate) | EPDCL perspective_validation (4,950 phone images: valid vs perspective-distorted) | 🟡 | Next: assessability head (HLD stage 1) |
| mast lean | EPDCL pole_lean_assessment (detection, classification and keypoints) | 🟡 | Next: lean is a condition; needs a railway validation set |

## Catalogue

| # | Source | What it is | Access | Licence | Use |
|---|---|---|---|---|---|
| 1 | GitHub InsulatorData/InsulatorDataSet (CPLID) | 848 UAV images of transmission-line insulators; VOC boxes "insulator", "defect" (missing caps) | git clone | Undetermined; you decided to use it for training | ✅ 848 imgs (553/159/136); 1,321 insulator and 248 defect boxes |
| 2 | HF KeenForgeAI/CPLID_Insulators-corrected | Cleaned CPLID | HF | CC BY 4.0 on changes | No – same images as #1 |
| 3 | HF docmhvr/powerline-components-and-faults | Drone power-line components and faults | HF parquet | MIT | ✅ 1,618 imgs; xyxy boxes: 6,050 insulator, 1,089 broken insulator, 274 vegetation |
| 4 | HF silera/broken-insulators-synthetic-detection | 203 synthetic broken insulators | HF parquet | CC BY 4.0 | ✅ train/val only |
| 5 | HF rohanath/insulator-defect-detection | ~3,040 images, image-level labels | HF zip | Not stated | Candidate crop classifier, after a licence check |
| 6 | **HF EPDCL/pd-defect (PD-Defect)** | 20,476 field smartphone photos of power distribution infrastructure (APEPDCL, Andhra Pradesh). Modules: pole_detection (2,252 imgs), pole_lean_assessment, crossarm/top-cleat tilt (1,686 crops), vegetation_conductor, dtr_plinth_clearance, voltage_level, perspective_validation (4,950) | HF | CC BY 4.0 | ✅ pole_detection → mast; vegetation_conductor → vegetation. 🟡 perspective, lean and crossarm next. **Closest public domain to the HLD: Indian, phone, ground level** |
| 7 | **figshare RailFOD23 (24180738)** | Foreign objects on railway transmission lines (bird nest, kite, balloon, plastic); COCO; 6.5 GB; partly synthesised | Direct download | CC BY 4.0 | ✅ bird_nest, foreign_object |
| 8 | **GitHub jsxr32/EBIST_cscuav** | Real railway catenary support components (insulator, locator base, connector sleeve, casing base, locator tube connector, sleeve double-ear); MVTec format with crack/drop masks; ~10 imgs per split | git clone | Not stated | ✅ Railway anomaly evaluation only |
| 9 | GitHub phd-benel/VPMBGI (release) | 1,010 broken glass insulator images (Vietnam; ground patrol staff and helicopter); YOLOv7 | Release zip, 71 MB | CC BY 4.0 | ✅ insulator_defect |
| 10 | GitHub phd-benel/BGI (release) | Earlier 544-image version of #9 | Release rar | CC BY 4.0 | No – superseded by #9 |
| 11 | Zenodo 14604384 MPID | Merged public insulator dataset (porcelain, composite, glass); 3.9 GB | Direct | CC BY 4.0 | 🟡 More insulator variety if needed |
| 12 | HF LibreYOLO/corrosion-bi3q3 (Roboflow 100) | 1,249 imgs; corrosion, crack, slippage | HF | CC BY 4.0 | ✅ corrosion only |
| 13 | HF iamcloud/Corrosion_Dataset; khoaliamle/Corrosion_Rust | Corrosion images | HF | Apache-2.0 / MIT | 🟡 |
| 14 | FID move OSDaR23 | DB rail multi-sensor sequences from a train (Hamburg); RGB + lidar; 27,706 "catenary pole" boxes; per-sequence zips | Direct (download.data.fid-move.de) | Images CC BY-SA 3.0 DE; labels CC0 | 🟡 Mast detection from rail view (multi-GB per sequence) |
| 15 | RAIL-BENCH (KIT) | Benchmark that includes a "catenary pole" class | Site | Check | 🟡 |
| 16 | GitHub andreluizbvs/PLAD | 133 high-res UAV images; tower, insulator, spacer, **tower plate**, Stockbridge damper | Release zip, 989 MB | GPL-3.0 (repo) | 🟡 Plate detection reference; licence to clear |
| 17 | GitHub Elizbellou/TIC-Powerline | 2,056 aerial imgs; tower, insulator, conductor | Google Drive | See repo | 🟡 |
| 18 | HF ToXiN0/Powerlines-detection | 7,988 imgs, YOLO | HF | Apache-2.0 | 🟡 Class list to read |
| 19 | HF UPNAdroneLab/powerline_towers | 1,022 tower images | HF | CC BY-NC-SA 4.0 | No – non-commercial |
| 20 | Zenodo 4015912 | Supplementary files, bird's nest detection on transmission lines (UAV); 3 × 2.1 GB WeTransfer zips | Direct | CC BY 4.0 | 🟡 Contents unlisted; second bird-nest source |
| 21 | Zenodo 11287111 | Synthetic HV insulator images (classification, segmentation); 17 GB | Direct | CC BY 4.0 | No – synthetic, large |
| 22 | Zenodo 7781388 | Aerial power infrastructure detection; 12 GB | Direct | CC BY 4.0 | 🟡 |
| 23 | RailCatFOD-DS (Sci Rep 2026; github dashgfuidng/CPSSFOdataset) | 7,638 railway catenary images: nests (8,420), light debris (6,378) | Baidu Pan only | Not stated | ⛔ Ask the authors for another mirror |
| 24 | Catenary Insulator Defects (IEEE TIM 2024) | Inspection-vehicle catenary insulators | On request | – | ⛔ |
| 25 | Dropper defect papers (C2T-HR3D, 1D-CNN Birmingham) | High-speed rail droppers | Not released | – | ⛔ |
| 26 | EPRI Insulator Defect Image Dataset (IDID v1.1) | 1,596 imgs; flashover, broken, good shells | Email orders@epri.com (export control) | Not stated | ⛔ Unless you request it |
| 27 | Roboflow Universe: railway-monitor/catenary, panto-catenary, pantograph-detection, utility-pole-label, bird-nest sets, vgv2/polivegV3 (vegetation by power lines) | Railway catenary, dropper, pantograph, pole labels, nests, vegetation | API key | CC BY 4.0 (most) | 🔑 Wired in for catenary and panto; runs when the ROBOFLOW_API_KEY secret is set |
| 28 | RailSem19 | Rail scene segmentation incl. poles | Registration (wilddash.cc) | Research | 🔑 |
| 29 | IIIT Indic Scene Text / signboard text sets | Indic and English scene text | Registration | Research | 🔑 Possible OCR fine-tune pre-training for plates |
| 30 | 4TU catenary arches (point clouds); Dutch railway laser scans | Lidar | Open | Check | No – not RGB |
| 31 | Kaggle | Only mirrors of the above (searched: bird nest, catenary, pantograph) | Kaggle login | – | No new data |

## Remaining gaps

These classes can only come from pilot phone captures on Indian Railways sections:

- railway mast number plates;
- droppers;
- contact and catenary wire;
- railway-type cantilever fittings, seen from the ground.

Fastest public unlocks, in order of value:

1. A free Roboflow API key: catenary, dropper and pole-label sets.
2. Contact the RailCatFOD-DS authors for a non-Baidu mirror: railway nests.
3. Email EPRI for IDID: flashover.
