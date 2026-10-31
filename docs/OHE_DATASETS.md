# OHE dataset search log (31 Oct 2026)

Searched one source at a time. Every candidate is listed with what it is, whether it can be downloaded without a person signing in, and its use here.

| # | Source / query | What it is | Access | Licence | Used? |
|---|---|---|---|---|---|
| 1 | GitHub InsulatorData/InsulatorDataSet (CPLID) | 848 UAV images of transmission-line insulators; VOC boxes "insulator", "defect" (missing caps) | git clone | undetermined (user decided: use for training) | Yes – 848 imgs (553/159/136), 1,321 insulator + 248 defect boxes |
| 2 | HF KeenForgeAI/CPLID_Insulators-corrected | Cleaned CPLID with chain-aware splits | HF per-file download hit HTTP 429 | CC BY 4.0 on changes; pixels as CPLID | No – same images via #1 |
| 3 | HF docmhvr/powerline-components-and-faults | Drone images of power-line components and faults, parquet | `datasets` (parquet, 3 files) | MIT | Yes (run 4) – 1,618 imgs (1,500/77/41), xyxy pixel boxes: 6,050 insulator, 1,089 broken insulator, 274 vegetation |
| 4 | HF silera/broken-insulators-synthetic-detection | 203 synthetic images of broken insulators with boxes | `datasets` | CC BY 4.0 | Yes – 203 imgs (162 train / 41 val), 203 insulator_defect boxes; kept out of test |
| 5 | HF rohanath/insulator-defect-detection | ~3,040 images, 2-class image labels (no boxes) | `datasets` | not stated | Not yet – candidate for a crop condition classifier after licence check |
| 6 | HF introvoyz043/InsulatorDataSet | Mirror of CPLID | – | MIT tag | No – duplicate |
| 7 | Roboflow Universe railway-monitor/catenary | Railway catenary + dropper boxes | API key required | CC BY 4.0 | Wired in; runs when ROBOFLOW_API_KEY secret is set |
| 8 | Roboflow Universe object-detection-bmosq/panto-catenary | Pantograph, catenary, contact point | API key required | CC BY 4.0 | Wired in; same |
| 9 | Roboflow Universe insulator defect sets (IDD-IDID etc.) | Insulator defects | API key required | per project | Candidate |
| 10 | EPRI Insulator Defect Image Dataset (IEEE DataPort) | Broken / flashover / good insulator shells | approved competition login | not stated | No – gated |
| 11 | RailFOD23 (Scientific Data 2024) | Foreign objects on railway transmission lines | download page did not load in this session | check | Not yet |
| 12 | Catenary Insulator Defects (IEEE TIM 2024) | Inspection-vehicle catenary insulator images | paper only, data on request | check | No |
| 13 | Zenodo / MDPI railway sets (L4R_NLB, TurnoutSegmentation, intruder frames) | Track, switches, turnouts – not OHE | open | various | No – not OHE |
| 14 | 4TU catenary arches point clouds | Lidar point clouds, not images | open | check | No – not RGB |

Gap: no public set of ground-level phone photos of 25 kV railway OHE. Items 7–8 are the closest railway OHE images; a free Roboflow account key unlocks them. The production dataset remains the pilot capture.
