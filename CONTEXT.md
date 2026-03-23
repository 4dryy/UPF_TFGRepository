# PROJECT_CONTEXT.md

## 1. Project Identity and Meta-Information
* **Author:** Adrià Cortés Cugat (Mathematical Engineering in Data Science)
* **University:** Universitat Pompeu Fabra (UPF), Barcelona
* **Collaborating Institution:** Hospital de la Santa Creu i Sant Pau (Dimension Lab / PhySense)
* **Tutors:** Pr. Oscar Camara Rey (UPF), César Acebes Pinilla (Hospital de Sant Pau)
* **Project Title:** Automated Geometric Stenosis Quantification and CAD-RADS Support for Coronary Artery Disease Assessment and Patient Prioritization.
* **Technical Environment:** Conda Environment (`tfg_adria`) running Python 3.10 to support heavy C++ medical imaging libraries (specifically VMTK).

## 2. Project Overview & Clinical Justification
Coronary Artery Disease (CAD) and myocardial infarctions cause 32% of all deaths worldwide. Currently, the diagnosis workflow in radiology departments involves a significant bottleneck: clinicians must manually analyze 3D Computed Tomography Angiography (CCTA) scans to measure arterial narrowing (stenosis) and write structured reports.

**The Goal of this TFG:** To build an automated pipeline that bridges the gap between raw AI-segmented medical images and the final patient prioritization report. The pipeline will automatically extract 3D geometries from artery segmentations, compute mathematical cross-sections to quantify stenosis (%DS), map these values to clinical CAD-RADS scores, and present them in an interactive 3D visualization tool for doctors.

## 3. The "Surroundings": Previous & Concurrent Works
This project does not exist in a vacuum; it is the "missing link" in a larger AI Framework designed by César Acebes. My pipeline builds upon and connects the work of previous students:
* **The "Input" Layer (Maren Clapers, 2025):** Focuses on the Deep Learning segmentation and topological labeling of the Left and Right Coronary Arteries (LCA, RCA). *Takeaway for my TFG:* I do not need to train segmentation models. I assume the input data is already segmented (binary masks).
* **The "Algorithmic" Baseline (Ela Burrull, 2024):** Defined the mathematical formulas for stenosis quantification, specifically calculating the Percentage Diameter Stenosis (%DS) using proximal/distal reference diameters ($D_{fit}$, $D_{min}$, $Area$).
* **The "Output" Layer (Eva Ferrer, 2024):** Developed a prioritization reporting system that takes clinical data and CAD-RADS scores to organize the patient queue. *Takeaway for my TFG:* My pipeline must output data compatible with Eva's system.

## 4. Technical Workflow (The Pipeline)
The project is implemented as a modular pipeline (`src/_pipeline.py`) where each block is a self-contained Python module under `src/blocks/`. Each block receives the output of the previous one and produces versioned, timestamped results.

1. **Block 1 — Centerline Extraction (`_01_extraction.py`):** *(Implemented)* Loads the `.nrrd` binary mask, separates RCA/LCA via center-of-mass, discovers seed points through 3D skeletonization (Maren's "Scout"), and extracts VMTK Voronoi centerlines with maximum inscribed sphere radii. Outputs a DataFrame (`Patient_ID`, `Artery_Type`, `Px`, `Py`, `Pz`, `Radius`) and `.vtp` centerline files.
2. **Block 2 — Stenosis Quantification (`_02_stenosis.py`):** *(Planned)* Generates cross-sectional planes perpendicular to the centerline to calculate local vessel areas and diameters, then applies geometric heuristics to compute %DS.
3. **Block 3 — CAD-RADS Scoring:** *(Planned)* Maps the %DS to the standardized CAD-RADS clinical scale (e.g., 50-69% stenosis = CAD-RADS 3), exploring machine learning approaches.
4. **Block 4 — Visualization Dashboard:** *(Planned)* Interactive 3D tool (using PyVista/Trimesh/Streamlit) for clinicians to visualize the artery mesh, centerline, and stenosis locations.


## 5. Dataset Information: ASOCA
* **Source:** MICCAI 2020 Challenge (Automated Segmentation of Coronary Arteries).
* **Data:** 40 cases (20 Healthy "Normal", 20 with CAD "Diseased").
* **Target Files:** We are specifically using the **Annotations** files (e.g., `Normal_1.nrrd`). These are binary masks where the coronary artery tree is labeled as `1` and the background is `0`.

## 6. Current Development Phase: Pipeline Refactoring & Validation
**Block 1 (Centerline Extraction) is implemented and operational.** The research phase compared two methodologies in isolated notebooks, and the conclusion was a **Hybrid Approach** that combines both:

* **The "Scout" (Maren's Voxel Skeletonization):** Uses `scikit-image` 3D morphological thinning to automatically discover all skeleton endpoints and identify the ostium (deepest endpoint via EDT). This eliminates the need for manual seed selection.
* **The "Math" (VMTK Voronoi Centerlines):** Uses the Vascular Modeling Toolkit to compute sub-millimeter smooth centerlines with maximum inscribed sphere radii from the automated seed points.

The hybrid approach has been refactored from `notebooks/03_centerline_extraction_hybrid.ipynb` into a production-ready module at `src/blocks/_01_extraction.py`. The pipeline is executed via `python -m src._pipeline`, which prompts for a Patient ID at runtime.

**Output convention:** Results are stored under `results/block1_results/` with naming `centerline_<PatientID>_<ArteryType>_<YYYYMMDD>.vtp` and `df_<PatientID>_<YYYYMMDD>.xlsx`. Re-running the same patient overwrites previous results.

**Current focus:** Validating the pipeline across multiple ASOCA patients and investigating VMTK "steepest descent" failures caused by seed snapping on narrow vessel tips. A surface-normal-aware inward nudging strategy has been implemented to mitigate this.

## 7. Instructions for Cursor AI
When assisting with this repository, Cursor must adhere strictly to the following rules:
1. **Context Awareness:** Always refer back to this file to understand the broader clinical and mathematical goals of the pipeline.
2. **Environment:** Assume all code is running in a Conda environment (`tfg_adria`) with Python 3.10.
3. **Libraries:** Prefer `pyvista`, `vmtk` (for Method 1), `SimpleITK`, `nibabel`, `numpy`, and `scikit-image` (for Method 2).
4. **Medical Constraints:** Always remember that medical images have physical spacing (voxel size in mm). Matrix indices MUST be converted to physical spatial coordinates using the image header/affine matrix for any geometric calculation.
5. **DIARY.md Maintenance:** At the end of a coding session, when prompted, you must update the `DIARY.md` file with a structured log of what was tested, what bugs were fixed, and what the next immediate step is.