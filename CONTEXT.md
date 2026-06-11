# Clinical Context & Project Motivation

This document describes the clinical workflow at Hospital de la Santa Creu i Sant Pau for Coronary Artery Disease (CAD) diagnosis, identifies the manual bottleneck that this project addresses, and defines the proposed automated workflow.

---

## 1. Project Identity

| | |
|---|---|
| **Author** | Adrià Cortés Cugat (Mathematical Engineering in Data Science) |
| **University** | Universitat Pompeu Fabra (UPF), Barcelona |
| **Collaborating Institution** | Hospital de la Santa Creu i Sant Pau — Dimension Lab / PhySense |
| **Tutors** | Pr. Oscar Camara Rey (UPF), César Acebes Pinilla (Hospital de Sant Pau) |
| **Project Title** | Automated Geometric Stenosis Quantification and CAD-RADS Support for Coronary Artery Disease Assessment and Patient Prioritization |
| **Technical Environment** | Conda Environment (`tfg_adria`), Python 3.10, VMTK via conda-forge |

---

## 2. Current Clinical Workflow at Hospital de Sant Pau

CAD and myocardial infarctions account for approximately 32% of all deaths worldwide. At Hospital de Sant Pau, diagnosing CAD follows a well-established clinical pathway involving multiple professionals and hospital systems:

### Step-by-Step Patient Journey

1. **Patient Presentation:** A patient arrives at the hospital presenting chest pain symptoms.
2. **CCTA Request and Programming:** The referring physician evaluates the symptoms and requests a Coronary CT Angiography (CCTA). The hospital's internal administration system programs the acquisition.
3. **CCTA Acquisition:** The Cardiac Imaging Unit acquires the CCTA images and uploads them to PACS (Picture Archiving and Communication System) for storage and access.
4. **CCTA Assessment and Reporting:** A cardiac imaging expert (radiologist) retrieves the images from PACS and performs a manual analysis. This involves visually inspecting the 3D coronary artery tree, identifying and quantifying stenoses, characterizing plaques, and noting other clinical findings. The observations are manually annotated into a template-based clinical report, which is then uploaded to RIS (Radiology Information System).
5. **CAD Diagnosis:** The referring physician reviews the structured report in RIS and makes a final diagnosis — the patient is either discharged as healthy, classified as diseased and referred for further intervention, or directed to additional tests.

### The Actors

| Actor | Role |
|-------|------|
| **Patient** | Presents with symptoms |
| **Referring Physician + Administration** | Requests the CCTA and programs the study |
| **Cardiac Imaging Unit** | Acquires the CCTA images |
| **Cardiac Imaging Expert (Radiologist)** | Analyzes images, extracts features, writes the clinical report |
| **Referring Physician** | Reads the report and makes the final diagnosis |

---

## 3. The Manual Bottleneck

The critical bottleneck in this workflow is **Step 4: CCTA Assessment and Reporting**. This step is performed entirely by hand by the cardiac imaging expert and consists of:

- **Visual image analysis** of the 3D coronary artery tree across hundreds of CT slices.
- **Manual feature extraction:** The radiologist must mentally (and sometimes with basic measurement tools) assess artery segmentation, quantify stenosis severity at multiple locations, characterize plaque composition, and identify other clinical findings.
- **Manual data introduction:** All observations are manually typed into the clinical database and into a template-based reporting system.

### Time Impact

| Patient Complexity | Approximate Assessment Time |
|---|---|
| Healthy patient (no significant findings) | ~30 minutes |
| Complex case (multiple stenoses, calcifications) | ~60–90 minutes |

This means a single radiologist can process at most **8–16 patients per day**, creating a significant queue. The manual nature of this process also introduces inter-observer variability — different experts may quantify the same stenosis differently, affecting reproducibility.

### What Is Currently Manual

The following image analysis features are extracted manually and visually during Step 4:

- **Artery Segmentation** — Identifying and tracing the coronary artery tree.
- **Stenosis Quantification** — Measuring the degree of arterial narrowing at each location.
- **Plaque Quantification** — Characterizing plaque type and extent.
- **Other Clinical Findings** — Anomalies, calcification scores, and anatomical variants.

The expert must recognize findings for all of the previous features for a patient and then manually introduce them into the reporting system, one field at a time.

In this project we aim to automate some of these feature extractions.

---

## 4. Proposed Workflow: Automated Support for CAD Assessment

This project proposes inserting an **automated computational layer** between the CCTA image acquisition and the radiologist's assessment. Instead of performing every analysis step manually, the clinician would receive pre-computed quantitative results presented through an interactive visualization tool.

### What Changes

This project does **not** attempt to automate the full visual image analysis performed by the radiologist. Clinical expertise and the expert eye remain central to diagnosis. Instead, the project introduces mathematical and computational approaches that extract selected quantitative features (such as stenosis-related metrics) directly from the segmented coronary anatomy, so that when the clinician visually analyzes the image, they can find diseases faster and with a quantitative reference already available.

| Current Workflow | Proposed Workflow |
|---|---|
| Visual image analysis (manual) | Visual image analysis (still manual), now supported by pre-computed quantitative references |
| Manual feature extraction for every feature | Automated extraction of **some** useful features (e.g., geometric stenosis), while other features remain manual |
| Manual data introduction to report | Manual data introduction **facilitated** by the support tool (not automated; clinician still enters findings) |
| Radiologist works from raw images | Radiologist works from a **support visualization tool** with pre-computed metrics as an initial reference |

The key idea is to provide a **support visualization tool** that the clinician can use as a reference starting point to accelerate assessment and enable patient prioritization, maximizing diagnostic efficiency without replacing the clinician's expertise.

### The Proposed Pipeline

The automated layer is implemented as a 4-block modular pipeline (`python -m src._pipeline`):

1. **Block 1 — Automated Anatomy Extraction:** Extracts centerlines and geometric properties (3D coordinates, vessel radii) from the binary segmentation mask. **ASOCA / MACS-18:** RCA/LCA split, automated ostium scout, branching, optional **SCCT-18** segment labels. **Synthetic:** single-tube path — one centerline, one branch, no coronary tree logic.
2. **Block 2 — Geometric Stenosis Quantification:** Computes cross-sectional **Area** (VMTK sections) and **%AS** via a sliding geodesic reference window (±5 mm in production code). **ASOCA:** processes RCA and LCA. **Synthetic:** processes the `Synthetic` artery only.
3. **Block 3 — CAD-RADS & segment reporting:** **ASOCA / MACS-18:** label mirror, **SCCT-18** segment stenosis aggregation (`src/segment_atlas.py`), CAD-RADS 2.0 patient report and ID card. **Synthetic:** placeholder segment summary, `patient_report` with `N/A (Synthetic Case)`, and `summary_metrics_<Patient>.json` — no territory or SIS scoring.
4. **Block 4 — Visualization Dashboard:** Writes `results/current_session.json` (`patient_id`, `is_synthetic`) and launches Streamlit (`src/viewer/app.py`). **ASOCA:** dual LCA/RCA 3D views, segment and branch explorers, CAD-RADS panel. **Synthetic:** `src/viewer/synthetic_ui.py` — centered single-vessel 3D plot, N/A KPI row, continuous along-vessel profile.

Shared configuration lives in `src/synthetic_profile.py` (mask paths, placeholder columns, CAD-RADS label constants).

### What This Enables

- **Reduced assessment time:** The radiologist no longer starts from scratch with raw images. Pre-computed stenosis values and severity scores significantly reduce the analysis burden.
- **Patient prioritization:** With automated CAD-RADS scores, patients can be triaged by severity before the radiologist even opens their study, enabling the most critical cases to be reviewed first.
- **Reproducibility:** Automated geometric quantification removes inter-observer variability, producing consistent measurements regardless of which clinician reviews the case.
- **Seamless integration:** The pipeline outputs structured data compatible with existing hospital systems (the reporting templates and the patient prioritization framework developed by concurrent work at the hospital).

### Important Clarification

This tool is designed as a **clinical support system**, not a replacement for the radiologist. The automated output assists and accelerates the expert's decision-making, but the final diagnosis always remains in the hands of the clinician.

---

## 5. The Surrounding Research Ecosystem

This project does not exist in isolation. It is part of a larger AI framework designed by César Acebes at Hospital de Sant Pau. The pipeline builds upon and connects the work of previous students:

| Contributor | Focus | Relevance to This Project |
|---|---|---|
| **Maren Clapers (2025)** | Deep Learning segmentation and topological labeling of LCA/RCA | Provides the input layer: this project assumes the segmentation data is already available as binary masks. |
| **Ela Burrull (2024)** | Mathematical formulas for stenosis quantification (%DS using proximal/distal reference diameters) | Defines the algorithmic baseline for Block 2. |
| **Eva Ferrer (2024)** | Patient prioritization reporting system using clinical data and CAD-RADS scores | Defines the output layer: this project must produce data compatible with Eva's prioritization system. |

---

## 6. Datasets

### 6.1 ASOCA (primary clinical cohort)

| | |
|---|---|
| **Source** | MICCAI 2020 Challenge — Automated Segmentation of Coronary Arteries |
| **Cases** | 40 total: 20 Healthy ("Normal") + 20 with CAD ("Diseased") |
| **Input Format** | `.nrrd` binary masks where coronary artery voxels = 1, background = 0 |
| **Mask location** | `data/ASOCA Normal/Annotations/` (and Diseased cohort when used) |
| **Optional labels** | `data/ASOCA Labels/` (or Normal/Diseased label folders) — SCCT-18 `.nii.gz` segment volumes for segment-aware Block 1 |
| **Usage** | End-to-end pipeline validation, CAD-RADS scoring, Streamlit clinical layout (LCA + RCA) |

### 6.2 Synthetic single-tube phantoms (algorithm validation)

| | |
|---|---|
| **Purpose** | Controlled ground-truth validation of centerline extraction, sectional **Area**, and **%AS** without coronary branching or SCCT segment anatomy |
| **Patient IDs** | `Synthetic_1` (healthy straight tube), `Synthetic_2` (cosine stenosis phantom) — any ID starting with `Synthetic_` |
| **Input Format** | `.nrrd` binary masks under `data/Synthetic Samples/{Patient_ID}.nrrd` |
| **Geometry** | 100×100×100 voxels, 1 mm isotropic spacing; single vertical cylinder along Z (see `notebooks/experiments/synthetic quantification/synthetic_data_gen.ipynb`) |
| **Pipeline mode** | Detected automatically in `src/_pipeline.py` via `is_synthetic_patient()`; blocks receive `is_synthetic=True` |
| **Clinical scoring** | **Not applicable** — CAD-RADS, SIS, and SCCT-18 segment rules are bypassed; outputs use placeholders (`N/A (Synthetic Case)`) |
| **Metadata placeholders** | `Artery_Type=Synthetic`, `Branch_ID=0`, `Segment_ID=99`, `Segment_Name=Synthetic Vessel` (numeric segment ID required for VTK/PyVista scalars) |

Synthetic cases exercise the **same** Blocks 1–2 geometry stack as ASOCA but skip RCA/LCA connected-component splitting, coronary branching, and label-driven segment classification. Block 3 writes a minimal label mirror plus placeholder reports; Block 4 opens a **single-vessel** Streamlit layout (centered 3D plot + along-vessel Area/%AS profile).

### 6.3 MACS-18 (re-annotated clinical cohort)

| | |
|---|---|
| **Source** | Hospital de la Santa Creu i Sant Pau — expert-refined re-segmentation of the 40 ASOCA volumes |
| **Cases** | 40 total: 20 Healthy + 20 with CAD (same patient IDs as ASOCA, prefixed `MACS_`) |
| **Input Format** | `.nrrd` lumen masks + `.nii.gz` SCCT-18 segment labels under `data/MACS-18/` |
| **Segment encoding** | Same integer SCCT-18 atlas as production (`src/segment_atlas.py`); shared with ASOCA label volumes |
| **Usage** | End-to-end pipeline validation on improved lumen connectivity; batch runner via `scripts/run_batch.py --cohort macs` |

---

## 7. Instructions for Cursor AI

When assisting with this repository, Cursor must adhere to the following rules:

1. **Context Awareness:** Always refer to this file and the `README.md` to understand the clinical goals, the 4-block architecture, and the current development phase.
2. **Environment:** Assume all code runs in the Conda environment `tfg_adria` with Python 3.10.
3. **Libraries:** Prefer `pyvista`, `vmtk`, `SimpleITK`, `nibabel`, `numpy`, `scipy`, and `scikit-image`.
4. **Medical Constraints:** Medical images have physical spacing (voxel size in mm). Matrix indices must always be converted to physical spatial coordinates using the image header/affine matrix before any geometric calculation.
5. **Diary Maintenance:** At the end of each coding session, when prompted, update `DIARY.md` with a structured log following the established entry format.
6. **Documentation Consistency:** Any architectural changes must be reflected across all three documentation files (`README.md`, `CONTEXT.md`, `DIARY.md`).

---

## Acronym Legend

| Acronym | Definition |
|---------|-----------|
| **CAD** | Coronary Artery Disease |
| **CAD-RADS** | Coronary Artery Disease — Reporting and Data System |
| **CCTA** | Coronary Computed Tomography Angiography |
| **CT** | Computed Tomography |
| **EDT** | Euclidean Distance Transform |
| **LCA** | Left Coronary Artery |
| **PACS** | Picture Archiving and Communication System |
| **RCA** | Right Coronary Artery |
| **RIS** | Radiology Information System |
| **TFG** | Treball de Fi de Grau (Final Degree Project) |
| **VMTK** | Vascular Modeling Toolkit |
| **%DS** | Percentage Diameter Stenosis |
| **%AS** | Percentage Area Stenosis |
| **ASOCA** | Automated Segmentation of Coronary Arteries (MICCAI 2020) |
| **SCCT** | Society of Cardiovascular Computed Tomography (18-segment coronary model; production atlas in `src/segment_atlas.py`) |
| **MACS-18** | Multiclass Anatomical Coronary Segmentation — re-annotated ASOCA cohort at Sant Pau |
| **SIS** | Segment Involvement Score (CAD-RADS modifier) |
| **VTK** | Visualization Toolkit (underlying VMTK/PyVista geometry) |
