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
  Output: DataFrame       Output: %DS per         Output: CAD-RADS        Output: Interactive
  + .vtp centerlines      artery segment          score per patient       clinical dashboard
```

| Block | Name | Status |
|-------|------|--------|
| **B1** | Automated Anatomy Extraction | Completed / Refactored |
| **B2** | Geometric Stenosis Quantification | Experimental |
| **B3** | CAD-RADS Scoring Prediction | Pending |
| **B4** | Visualization Dashboard | Pending |

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
    <td>Area Computation</td>
    <td>Reference Value Computation</td>
    <td>Stenosis % Computation</td>
    <td>Data Aggregation</td>
    <td>Validation</td>
    <td>Optimization</td>
  </tr>
  <tr>
    <td colspan="6"><em>Status: Experimental — methodology defined, implementation next.</em></td>
  </tr>
</table>

### B3 — CAD-RADS Scoring Prediction

<table>
  <tr>
    <td colspan="3"><em>Internal phases to be defined</em></td>
    <td>Validation</td>
    <td>Optimization</td>
  </tr>
  <tr>
    <td colspan="5"><em>Status: Pending — depends on Block 2 output.</em></td>
  </tr>
</table>

### B4 — Visualization Dashboard

<table>
  <tr>
    <td>3D Artery Mesh</td>
    <td>Stenosis Visualizations</td>
    <td>CAD-RADS Visualizations</td>
    <td>Patient Information</td>
    <td>Validation</td>
    <td>Optimization</td>
  </tr>
  <tr>
    <td colspan="6"><em>Status: Pending — prototype concept designed.</em></td>
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

**Output:** A DataFrame containing columns `[Patient_ID, Artery_Type, Px, Py, Pz, Radius]` and `.vtp` centerline polydata files for downstream geometric analysis.

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

The pipeline will prompt for a **Patient ID** (e.g., `Normal_1`). It then runs all implemented blocks sequentially. Currently only Block 1 is active — future blocks will be chained automatically as they are implemented.

Results are saved under `results/` with the following naming convention:
- **Centerlines:** `results/block1_results/centerlines/centerline_<PatientID>_<ArteryType>_<YYYYMMDD>.vtp`
- **DataFrames:** `results/block1_results/dataframes/df_<PatientID>_<YYYYMMDD>.xlsx`

Re-running the pipeline for the same patient overwrites previous results to avoid duplicates.

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
│   ├── _pipeline.py                  # Main entrypoint — chains all blocks
│   └── blocks/
│       ├── __init__.py
│       ├── _01_extraction.py         # Block 1: Hybrid centerline extraction (implemented)
│       ├── _02_stenosis.py           # Block 2: Stenosis quantification (planned)
│       ├── _03_.py                   # Block 3: CAD-RADS scoring (planned)
│       └── _04_.py                   # Block 4: Visualization dashboard (planned)
├── results/
│   └── block1_results/
│       ├── dataframes/               # df_<PatientID>_<YYYYMMDD>.xlsx
│       └── centerlines/              # centerline_<PatientID>_<ArteryType>_<YYYYMMDD>.vtp
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
| **ASOCA** | Automated Segmentation of Coronary Arteries (MICCAI 2020) |
