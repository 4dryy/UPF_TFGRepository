<h1 align="center">Automated Geometric Stenosis Quantification & CAD-RADS Support<br>for Coronary Artery Disease Assessment</h1>

<p align="center"><strong>Final Degree Project (Treball de Fi de Grau)</strong><br>Universitat Pompeu Fabra (UPF), Barcelona</p>

<table align="center">
  <tr>
    <td bgcolor="#E3F2FD"><strong>Author</strong></td>
    <td>Adrià Cortés Cugat</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Degree</strong></td>
    <td>Mathematical Engineering in Data Science</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>University</strong></td>
    <td>Universitat Pompeu Fabra (UPF), Barcelona</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Collaborating Institution</strong></td>
    <td>Hospital de la Santa Creu i Sant Pau — Dimension Lab / PhySense</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Tutors</strong></td>
    <td>Pr. Oscar Camara Rey (UPF), César Acebes Pinilla (Hospital de Sant Pau)</td>
  </tr>
</table>

---

## Project Overview

Coronary Artery Disease (CAD) is the leading cause of death worldwide. At Hospital de Sant Pau, diagnosing CAD from Coronary CT Angiography (CCTA) images requires a clinician to manually assess 3D scans, quantify arterial stenosis, and write structured reports — a process that takes between **30 minutes (healthy patient) and 90 minutes (complex case)** per study.

This project develops an **end-to-end automated pipeline** that transforms raw coronary artery segmentation data into an interactive clinical visualization tool. The pipeline bridges the gap between the CCTA image acquisition and the radiologist's final report, aiming to **reduce the manual assessment bottleneck** and enable faster, more accurate patient prioritization.

The **final product** is a visualization dashboard that presents informative, quantitative data to the clinician, supporting faster and more confident decision-making. The **project itself** is the entire automated workflow that produces that dashboard — from input segmentation to clinical output.

---

## Project Architecture

The system follows a strict **4-block modular architecture**. Each block is a self-contained Python module under `src/blocks/` that receives the output of the previous block. The pipeline is orchestrated by `src/_pipeline.py`, which chains all blocks sequentially for a given patient.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     BLOCK 1     │     │     BLOCK 2     │     │     BLOCK 3     │     │     BLOCK 4     │
│    Automated    │────▶│    Geometric    │────▶│    CAD-RADS     │────▶│  Visualization  │
│    Anatomy      │     │    Stenosis     │     │    Scoring      │     │   Dashboard     │
│   Extraction    │     │ Quantification  │     │   Prediction    │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
  Input: .nrrd            Input: DataFrame        Input: %DS values       Input: Scores +
  binary mask             (centerline +           per segment             geometry data
                          geometry)
  Output: DataFrame       Output: Area + %AS       Output: CAD-RADS        Output: Interactive
  + .vtp centerlines      + merged locations       score per patient       clinical dashboard
```

| Block | Name | Status |
|-------|------|--------|
| **B1** | Automated Anatomy Extraction | Completed / Refactored |
| **B2** | Geometric Stenosis Quantification | Implemented: sectional area + reference window + **%AS** + merge |
| **B3** | Labeling + Segment Stenosis + CAD-RADS Scoring | Implemented in production pipeline |
| **B4** | Visualization Dashboard | Implemented (Streamlit launcher + session handoff; UI scaffold in progress) |

---

## Development Progress

The table below details the internal phases of each block. This table serves as a living roadmap — anyone continuing this project can immediately see what has been completed and what remains.

### B1 — Automated Anatomy Extraction

<table>
  <tr>
    <td bgcolor="#4CAF50">Image Loading</td>
    <td bgcolor="#4CAF50">RCA/LCA Separation</td>
    <td bgcolor="#4CAF50">Skeletonization</td>
    <td bgcolor="#4CAF50">Endpoint Detection</td>
    <td bgcolor="#4CAF50">Mesh Creation &amp; Smoothing</td>
    <td bgcolor="#4CAF50">Centerline Extraction</td>
    <td bgcolor="#4CAF50">Build DataFrame</td>
    <td>Validation</td>
    <td>Optimization</td>
  </tr>
  <tr>
    <td colspan="9"><em>Status: Implementation complete. Validation and optimization pending.</em></td>
  </tr>
</table>

### B2 — Geometric Stenosis Quantification

<table>
  <tr>
    <td bgcolor="#4CAF50">Area Computation</td>
    <td bgcolor="#4CAF50">Reference Value Computation</td>
    <td bgcolor="#4CAF50">Stenosis % Computation (%AS)</td>
    <td bgcolor="#4CAF50">Data Aggregation (merge)</td>
    <td>Validation</td>
    <td>Optimization</td>
  </tr>
  <tr>
    <td colspan="6"><em>Status: Core pipeline implemented in code (notebooks remain reference). Validation &amp; optimization ongoing.</em></td>
  </tr>
</table>

### B3 — CAD-RADS Scoring Prediction

<table>
  <tr>
    <td bgcolor="#4CAF50">Label Packaging</td>
    <td bgcolor="#4CAF50">Segment Stenosis Aggregation</td>
    <td bgcolor="#4CAF50">CAD-RADS 2.0 Rule Engine</td>
    <td>Validation</td>
    <td>Optimization</td>
  </tr>
  <tr>
    <td colspan="5"><em>Status: Implemented in code and integrated in pipeline. Validation and optimization ongoing.</em></td>
  </tr>
</table>

### B4 — Visualization Dashboard

<table>
  <tr>
    <td bgcolor="#4CAF50">Auto-launch Infrastructure</td>
    <td bgcolor="#4CAF50">Session Persistence</td>
    <td bgcolor="#4CAF50">Streamlit Base UI Scaffold</td>
    <td>Results Panels</td>
    <td>Validation</td>
    <td>Optimization</td>
  </tr>
  <tr>
    <td colspan="6"><em>Status: Infrastructure integrated in pipeline. Result visualization content under development.</em></td>
  </tr>
</table>

---

## Block 1 Methodology: Hybrid Centerline Extraction

Block 1 implements a **Hybrid Approach** that combines two complementary techniques to automatically extract coronary artery centerlines from binary segmentation masks, without any manual intervention.

### The Problem

VMTK's Voronoi-based centerline extraction produces sub-millimeter smooth centerlines with maximum inscribed sphere radii — the gold standard for geometric analysis. However, it requires manually selected seed points (source and target coordinates on the artery surface), which is impractical for an automated pipeline.

### The Solution: Scout + Math

The hybrid approach decouples the problem into two phases:

**Phase 1 — Pre-processing: Mask Loading and RCA/LCA Separation**
The `.nrrd` binary mask is loaded and split into Right Coronary Artery (RCA) and Left Coronary Artery (LCA) using connected component analysis and center-of-mass spatial sorting. The component with the smaller physical X-coordinate is assigned as RCA (anatomical convention).

**Phase 2 — The "Scout" (Maren's Voxel Skeletonization)**
For each artery component, `scikit-image` 3D morphological thinning reduces the binary volume to a one-voxel-wide skeleton. Degree-1 nodes (endpoints) are detected via neighbor counting. The **ostium** (proximal inlet) is identified as the endpoint deepest inside the vessel using the Euclidean Distance Transform (EDT). All remaining endpoints become distal branch targets. This phase eliminates the need for any manual seed selection.

**Phase 3 — The "Math" (VMTK Voronoi Centerlines)**
The binary mask is converted to a surface mesh via Marching Cubes, smoothed with Taubin passband filtering (20 iterations), and fed into VMTK's centerline extraction algorithm. The automated seed points from the Scout phase are projected onto the mesh surface using a **surface-normal-aware inward nudging strategy** to prevent VMTK "steepest descent" failures. VMTK then computes smooth centerlines with maximum inscribed sphere radii along the entire artery tree.

**Output package (per patient):**
- Global dataframe and per-artery dataframes with point-wise geometry/topology (`PointType`).
- Artery centerlines (`centerline_RCA.vtp`, `centerline_LCA.vtp`).
- Artery surfaces (`surface_RCA.vtp`, `surface_LCA.vtp`) for downstream Block 2 reuse.
- Branch-level centerlines/dataframes (ostium -> endpoint paths).
- QC figures (per-branch + full centerline tree with colored ostia/endpoints).

---

## Block 2 Methodology: Sectional Area, Reference Band, and %AS

Block 2 consumes the Block 1 sample package. Methodology aligns with the exploratory notebooks under `notebooks/block2_stenosis/` (especially sectional area and reference values).

### Phase A — Sectional area (`vmtkCenterlineSections`)

- **Centerline reuse:** reads `centerline_RCA.vtp` / `centerline_LCA.vtp` from Block 1.
- **Surface reuse:** reads `surface_RCA.vtp` / `surface_LCA.vtp` when present; otherwise rebuilds lumen surfaces from the same `.nrrd` mask used in Block 1.
- **Defensive preprocessing:** surface triangulation/cleaning; centerline smoothing + uniform resampling before sections (same intent as `_04_sq_sectional_area.ipynb`).
- **Area mapping:** per-point area is mapped onto global, artery, and branch tables (row-aligned when possible, KDTree nearest neighbour otherwise).

### Phase B — Reference window and % area stenosis (notebook parity)

Along each **branch** path (ordered rows): cumulative arc length **`gd`**, sliding-window reference **`A_ref`** from proximal/distal areas at ±10 mm on the path, then **`pct_AS = (1 − Area/A_ref)×100`** with safe handling of NaN/zero reference (see `_05_sq_reference_values.ipynb`).

### Phase C — Merge for a single patient-level map

Branch tables are stacked with a **`source_branch`** label; duplicate locations (coordinates rounded to 6 decimals) keep the row with **maximum `pct_AS`** (sort descending, `drop_duplicates`), producing **`total_df_<Patient>.xlsx`**.

### Output layout (two phases, same patient ID)

| Folder | Contents |
|--------|----------|
| **`results/block2_results/area/<Patient_ID>/`** | Area phase only: global + artery + branch spreadsheets with **`Area`**, area-colored figures (`fig_area_*`, branch `fig_<branch>.png`). |
| **`results/block2_results/stenosis/<Patient_ID>/`** | Enriched branch tables (`gd`, `A_ref`, `pct_AS`, …), **`total_df_<Patient>.xlsx`**, and **%AS** PyVista figures (unified tree + per branch). |

Re-running **`python -m src._pipeline`** for the same patient **removes and recreates** both `area/` and `stenosis/` trees for that patient (no duplicate samples).

### Pipeline API

- **`run_block1(patient_id)`** → centerline `DataFrame`.
- **`run_block2(patient_id)`** → **`Block2Outputs`** named tuple: **`df_global_area`** (full-tree table with `Area`), **`total_df_merged`** (merged %AS table; empty if Block 1 had no branch spreadsheets).

### Logging

Shared helpers in **`src/pipeline_log.py`** (`configure_logging`, banners, phase lines, footers) keep terminal output **short and consistent** across Block 1, Block 2, and the top-level pipeline.

---

## Block 3 Methodology: Label Packaging, Segment Stenosis, and CAD-RADS

Block 3 consumes Block 2 outputs and creates the patient-level clinical summary package:

- **Label phase:** consolidates per-branch stenosis-labelled dataframes and exports patient-level tree tables.
- **Segment stenosis phase:** aggregates stenosis metrics at segment level (AHA mapping), including handling of unmapped Segment IDs.
- **CAD-RADS phase:** applies the rule-based CAD-RADS 2.0 logic and exports:
  - `patient_report_<Patient_ID>.xlsx`
  - `patient_id_card_<Patient_ID>.png`

Outputs are written under:

- `results/block3_results/label/<Patient_ID>/`
- `results/block3_results/segment stenosis/<Patient_ID>/`
- `results/block3_results/cad-rads/<Patient_ID>/`

---

## Block 4 Methodology: Streamlit Visualization Launch Infrastructure

Block 4 provides the bridge between pipeline execution and interactive visualization:

- Persists current run context in `results/current_session.json` with the active `patient_id`.
- Launches Streamlit dashboard (`src/viewer/app.py`) automatically at pipeline end.
- Uses a deterministic local endpoint (`http://localhost:8501`) with readiness checks before opening the browser.
- Handles first-run Streamlit onboarding suppression and detached background execution so the pipeline can finish cleanly.

Current UI is a scaffold (title + session read + footer metadata). Clinical visualization panels are the next development phase.

---

## Installation & Setup

> **Important:** This project relies on C++ medical imaging libraries (VMTK). It **cannot** be installed using a standard Python `venv`. You must use **Conda** (Miniconda or Anaconda).

### 1. Create and Activate the Conda Environment

```bash
conda create -n tfg_adria python=3.10 -y
conda activate tfg_adria
```

### 2. Install VMTK (must be done first)

```bash
conda install -c conda-forge vmtk -y
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Verification

```bash
conda list vmtk
python --version   # Should output Python 3.10.x
```

---

## Running the Pipeline

Ensure your Conda environment is active before running:

```bash
conda activate tfg_adria
```

Execute the full pipeline from the project root:

```bash
python -m src._pipeline
```

The pipeline prompts for a **Patient ID** (e.g., `Normal_1`) and runs **Block 1 → Block 2 → Block 3 → Block 4**.

Results are saved under per-patient packages:
- **Block 1:** `results/block1_results/<Patient_ID>/`
- **Block 2 — area phase:** `results/block2_results/area/<Patient_ID>/`
- **Block 2 — stenosis phase:** `results/block2_results/stenosis/<Patient_ID>/` (when branch dataframes are present)
- **Block 3 — label phase:** `results/block3_results/label/<Patient_ID>/`
- **Block 3 — segment stenosis phase:** `results/block3_results/segment stenosis/<Patient_ID>/`
- **Block 3 — CAD-RADS phase:** `results/block3_results/cad-rads/<Patient_ID>/`
- **Block 4 session pointer:** `results/current_session.json`

At the end of execution, the Streamlit app is launched automatically and opened in the browser at `http://localhost:8501`.

Re-running for the same patient **overwrites** that patient’s Block 1/2/3 outputs (no duplicate artifacts for that sample), while keeping other patients' folders intact. `results/current_session.json` is always updated to the latest executed patient.

### Running Block 1 Standalone

```bash
python -m src.blocks._01_extraction Normal_1
```

### Jupyter Notebooks

The research notebooks used during the experimental phase are preserved under `notebooks/`. To run them, select the `tfg_adria` kernel in your VS Code / Cursor editor.

---

## Project Structure

```
UPF_TFGRepository/
├── data/
│   └── ASOCA Normal/
│       ├── Annotations/              # Input .nrrd binary masks (Normal_1.nrrd, ...)
│       └── Centerlines/              # ASOCA ground-truth centerlines (.vtp)
├── notebooks/
│   └── block1_extraction/
│       ├── 00_data_exploration.ipynb
│       ├── 01_centerline_extraction_1.ipynb    # Method 1: Manual VMTK
│       ├── 02_centerline_extraction_2.ipynb    # Method 2: Maren's skeletonization
│       └── 03_centerline_extraction_hybrid.ipynb  # Hybrid approach (research prototype)
├── src/
│   ├── _pipeline.py                  # Main entrypoint — chains all blocks + shared log style
│   ├── pipeline_log.py               # Concise banners / phase lines / footers for terminal logs
│   ├── viewer/
│   │   └── app.py                    # Streamlit dashboard entrypoint (reads current_session.json)
│   └── blocks/
│       ├── __init__.py
│       ├── _01_extraction.py         # Block 1: Hybrid centerline extraction
│       ├── _02_stenosis.py           # Block 2: Area + reference + %AS + merge (single module)
│       ├── _03_cad-rats.py           # Block 3: Label + segment stenosis + CAD-RADS exports
│       └── _04_visualization.py      # Block 4: Streamlit launch + session persistence
├── results/
│   ├── block1_results/
│   │   └── <Patient_ID>/             # Global/artery/branch data + centerlines + surfaces + QC figures
│   └── block2_results/
│       ├── area/<Patient_ID>/        # Area-mapped tables + area figures
│       └── stenosis/<Patient_ID>/    # Enriched branches + total_df + %AS figures
│   ├── block3_results/
│   │   ├── label/<Patient_ID>/             # Label-enriched exports + total tables
│   │   ├── segment stenosis/<Patient_ID>/  # Segment-level summaries
│   │   └── cad-rads/<Patient_ID>/          # CAD-RADS report + patient ID card
│   └── current_session.json          # Last pipeline execution patient context for viewer
├── maren work/                       # Reference notebooks from Maren Clapers
├── CONTEXT.md                        # Clinical context and workflow documentation
├── DIARY.md                          # Chronological development logbook
├── requirements.txt                  # Python dependencies
└── README.md
```

---

## Dataset: ASOCA

The project uses the **ASOCA** (Automated Segmentation of Coronary Arteries) dataset from the MICCAI 2020 Challenge:
- **40 cases:** 20 healthy ("Normal") + 20 with CAD ("Diseased").
- **Input files:** Binary masks in `.nrrd` format (e.g., `Normal_1.nrrd`) where coronary artery voxels are labeled `1` and background is `0`.

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
