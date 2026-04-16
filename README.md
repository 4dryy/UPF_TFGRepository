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

<table>
  <tr>
    <th bgcolor="#37474F" align="center"><strong>Block</strong></th>
    <th bgcolor="#37474F" align="center"><strong>Name</strong></th>
    <th bgcolor="#37474F" align="center"><strong>Status</strong></th>
  </tr>
  <tr>
    <td align="center"><strong>B1</strong></td>
    <td>Automated Anatomy Extraction</td>
    <td bgcolor="#C8E6C9" align="center">Completed / Refactored</td>
  </tr>
  <tr>
    <td align="center"><strong>B2</strong></td>
    <td>Geometric Stenosis Quantification</td>
    <td bgcolor="#FFF9C4" align="center">Experimental</td>
  </tr>
  <tr>
    <td align="center"><strong>B3</strong></td>
    <td>CAD-RADS Scoring Prediction</td>
    <td bgcolor="#EEEEEE" align="center">Pending</td>
  </tr>
  <tr>
    <td align="center"><strong>B4</strong></td>
    <td>Visualization Dashboard</td>
    <td bgcolor="#EEEEEE" align="center">Pending</td>
  </tr>
</table>

---

## Development Progress Dashboard

The table below details the internal phases of each block. Phases highlighted in green have been implemented; phases in white remain pending. This table serves as a living roadmap — anyone continuing this project can immediately see what has been completed and what remains.

<table>
  <tr>
    <th bgcolor="#37474F" align="center"><strong>Block</strong></th>
    <th bgcolor="#37474F" align="center" colspan="9"><strong>Internal Phases</strong></th>
  </tr>
  <!-- ── BLOCK 1 ── -->
  <tr>
    <td rowspan="2" bgcolor="#E3F2FD" align="center"><strong>B1<br>Automated Anatomy<br>Extraction</strong></td>
    <td bgcolor="#C8E6C9" align="center">Image Loading</td>
    <td bgcolor="#C8E6C9" align="center">RCA/LCA Separation</td>
    <td bgcolor="#C8E6C9" align="center">Skeletonization</td>
    <td bgcolor="#C8E6C9" align="center">Endpoint Detection</td>
    <td bgcolor="#C8E6C9" align="center">Mesh Creation &amp; Smoothing</td>
    <td bgcolor="#C8E6C9" align="center">Centerline Extraction</td>
    <td bgcolor="#C8E6C9" align="center">Build DataFrame</td>
    <td align="center">Validation</td>
    <td align="center">Optimization</td>
  </tr>
  <tr>
    <td colspan="9" bgcolor="#F5F5F5"><em>Implementation complete. Validation and optimization pending.</em></td>
  </tr>
  <!-- ── BLOCK 2 ── -->
  <tr>
    <td rowspan="2" bgcolor="#FFF9C4" align="center"><strong>B2<br>Geometric Stenosis<br>Quantification</strong></td>
    <td align="center">Area Computation</td>
    <td align="center">Reference Value Computation</td>
    <td align="center">Stenosis % Computation</td>
    <td align="center">Data Aggregation</td>
    <td colspan="3"></td>
    <td align="center">Validation</td>
    <td align="center">Optimization</td>
  </tr>
  <tr>
    <td colspan="9" bgcolor="#F5F5F5"><em>Experimental — methodology defined, implementation next.</em></td>
  </tr>
  <!-- ── BLOCK 3 ── -->
  <tr>
    <td rowspan="2" bgcolor="#EEEEEE" align="center"><strong>B3<br>CAD-RADS Scoring<br>Prediction</strong></td>
    <td align="center" colspan="5"><em>Internal phases to be defined</em></td>
    <td colspan="2"></td>
    <td align="center">Validation</td>
    <td align="center">Optimization</td>
  </tr>
  <tr>
    <td colspan="9" bgcolor="#F5F5F5"><em>Pending — depends on Block 2 output.</em></td>
  </tr>
  <!-- ── BLOCK 4 ── -->
  <tr>
    <td rowspan="2" bgcolor="#EEEEEE" align="center"><strong>B4<br>Visualization<br>Dashboard</strong></td>
    <td align="center">3D Artery Mesh</td>
    <td align="center">Stenosis Visualizations</td>
    <td align="center">CAD-RADS Visualizations</td>
    <td align="center">Patient Information</td>
    <td colspan="3"></td>
    <td align="center">Validation</td>
    <td align="center">Optimization</td>
  </tr>
  <tr>
    <td colspan="9" bgcolor="#F5F5F5"><em>Pending — prototype concept designed.</em></td>
  </tr>
</table>

<table>
  <tr>
    <td bgcolor="#C8E6C9" width="20" align="center"></td>
    <td>Implemented</td>
    <td width="30"></td>
    <td bgcolor="#FFFFFF" width="20" align="center" border="1"></td>
    <td>Pending</td>
  </tr>
</table>

---

## Block 1 Methodology: Hybrid Centerline Extraction

Block 1 implements a **Hybrid Approach** that combines two complementary techniques to automatically extract coronary artery centerlines from binary segmentation masks, without any manual intervention.

### The Problem

VMTK's Voronoi-based centerline extraction produces sub-millimeter smooth centerlines with maximum inscribed sphere radii — the gold standard for geometric analysis. However, it requires manually selected seed points (source and target coordinates on the artery surface), which is impractical for an automated pipeline.

### The Solution: Scout + Math

The hybrid approach decouples the problem into two phases:

<table>
  <tr>
    <th bgcolor="#37474F" align="left"><strong>Phase</strong></th>
    <th bgcolor="#37474F" align="left"><strong>Description</strong></th>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD" align="center"><strong>Phase 1</strong><br>Pre-processing</td>
    <td>The <code>.nrrd</code> binary mask is loaded and split into Right Coronary Artery (RCA) and Left Coronary Artery (LCA) using connected component analysis and center-of-mass spatial sorting. The component with the smaller physical X-coordinate is assigned as RCA (anatomical convention).</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD" align="center"><strong>Phase 2</strong><br>The "Scout"<br><em>(Maren's Voxel Skeletonization)</em></td>
    <td>For each artery component, <code>scikit-image</code> 3D morphological thinning reduces the binary volume to a one-voxel-wide skeleton. Degree-1 nodes (endpoints) are detected via neighbor counting. The <strong>ostium</strong> (proximal inlet) is identified as the endpoint deepest inside the vessel using the Euclidean Distance Transform (EDT). All remaining endpoints become distal branch targets. This eliminates the need for any manual seed selection.</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD" align="center"><strong>Phase 3</strong><br>The "Math"<br><em>(VMTK Voronoi Centerlines)</em></td>
    <td>The binary mask is converted to a surface mesh via Marching Cubes, smoothed with Taubin passband filtering (20 iterations), and fed into VMTK's centerline extraction algorithm. The automated seed points from the Scout phase are projected onto the mesh surface using a <strong>surface-normal-aware inward nudging strategy</strong> to prevent VMTK "steepest descent" failures. VMTK then computes smooth centerlines with maximum inscribed sphere radii along the entire artery tree.</td>
  </tr>
  <tr>
    <td bgcolor="#C8E6C9" align="center"><strong>Output</strong></td>
    <td>A DataFrame with columns <code>[Patient_ID, Artery_Type, Px, Py, Pz, Radius]</code> and <code>.vtp</code> centerline polydata files for downstream geometric analysis.</td>
  </tr>
</table>

---

## Installation & Setup

> **Important:** This project relies on C++ medical imaging libraries (VMTK). It **cannot** be installed using a standard Python `venv`. You must use **Conda** (Miniconda or Anaconda).

<table>
  <tr>
    <th bgcolor="#37474F" align="left"><strong>Step</strong></th>
    <th bgcolor="#37474F" align="left"><strong>Command</strong></th>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>1. Create &amp; activate Conda env</strong></td>
    <td><code>conda create -n tfg_adria python=3.10 -y && conda activate tfg_adria</code></td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>2. Install VMTK (must be first)</strong></td>
    <td><code>conda install -c conda-forge vmtk -y</code></td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>3. Install Python dependencies</strong></td>
    <td><code>pip install -r requirements.txt</code></td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>4. Verify installation</strong></td>
    <td><code>conda list vmtk && python --version</code> (should output Python 3.10.x)</td>
  </tr>
</table>

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

<table>
  <tr>
    <th bgcolor="#37474F" align="left"><strong>Output</strong></th>
    <th bgcolor="#37474F" align="left"><strong>Path &amp; Naming Convention</strong></th>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Centerlines</strong></td>
    <td><code>results/block1_results/centerlines/centerline_&lt;PatientID&gt;_&lt;ArteryType&gt;_&lt;YYYYMMDD&gt;.vtp</code></td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>DataFrames</strong></td>
    <td><code>results/block1_results/dataframes/df_&lt;PatientID&gt;_&lt;YYYYMMDD&gt;.xlsx</code></td>
  </tr>
</table>

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

<table>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Source</strong></td>
    <td>MICCAI 2020 Challenge — Automated Segmentation of Coronary Arteries</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Cases</strong></td>
    <td>40 total: 20 Healthy ("Normal") + 20 with CAD ("Diseased")</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Input Format</strong></td>
    <td><code>.nrrd</code> binary masks where coronary artery voxels = 1, background = 0</td>
  </tr>
  <tr>
    <td bgcolor="#E3F2FD"><strong>Usage</strong></td>
    <td>Development and validation of the automated pipeline</td>
  </tr>
</table>

---

## Acronym Legend

<table>
  <tr>
    <th bgcolor="#37474F" align="left"><strong>Acronym</strong></th>
    <th bgcolor="#37474F" align="left"><strong>Definition</strong></th>
  </tr>
  <tr><td bgcolor="#E3F2FD"><strong>CAD</strong></td><td>Coronary Artery Disease</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>CAD-RADS</strong></td><td>Coronary Artery Disease — Reporting and Data System</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>CCTA</strong></td><td>Coronary Computed Tomography Angiography</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>CT</strong></td><td>Computed Tomography</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>EDT</strong></td><td>Euclidean Distance Transform</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>LCA</strong></td><td>Left Coronary Artery</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>PACS</strong></td><td>Picture Archiving and Communication System</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>RCA</strong></td><td>Right Coronary Artery</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>RIS</strong></td><td>Radiology Information System</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>TFG</strong></td><td>Treball de Fi de Grau (Final Degree Project)</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>VMTK</strong></td><td>Vascular Modeling Toolkit</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>%DS</strong></td><td>Percentage Diameter Stenosis</td></tr>
  <tr><td bgcolor="#E3F2FD"><strong>ASOCA</strong></td><td>Automated Segmentation of Coronary Arteries (MICCAI 2020)</td></tr>
</table>
