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

## 4. Proposed Technical Workflow (The Pipeline)
The project is divided into the following sequential modules:
1. **Input Data Ingestion:** Reading binary segmentation masks from the ASOCA dataset in `.nrrd` format.
2. **Centerline & Geometry Extraction:** Transforming the 3D voxel mask into a continuous mathematical representation, extracting the centerline coordinates $\{P_x, P_y, P_z\}$, and computing the maximum inscribed sphere radii.
3. **Area Computation:** Generating cross-sectional planes perpendicular to the centerline to calculate local vessel areas and diameters along the artery. 

4. **Stenosis Quantification:** Applying geometric heuristics (referencing healthy vs. narrowed sections) to calculate the %DS.
5. **CAD-RADS Scoring:** Mapping the %DS to the standardized CAD-RADS clinical scale (e.g., 50-69% stenosis = CAD-RADS 3).
6. **Visualization Dashboard:** Creating a 3D interactive tool (using PyVista/Trimesh/Streamlit) for clinicians to visualize the 3D artery mesh, the centerline, and highlight the stenosis locations. 


## 5. Dataset Information: ASOCA
* **Source:** MICCAI 2020 Challenge (Automated Segmentation of Coronary Arteries).
* **Cohort:** 40 cases (20 Healthy "Normal", 20 with CAD "Diseased").
* **Target Files:** We are specifically using the **Annotations** files (e.g., `Normal_1.nrrd`). These are binary masks where the coronary artery tree is labeled as `1` and the background is `0`.

## 6. Current Development Phase: Centerline Extraction
We are currently at **Step 2** of the pipeline: extracting the centerline from a single ASOCA `.nrrd` annotation. 
We are taking a scientific approach by implementing and comparing two distinct methodologies in isolated Jupyter Notebooks:

* **Method 1 (Oscar's Recommended Method - Mesh/VMTK):**
  Uses the Vascular Modeling Toolkit (`vmtk`). It reads the `.nrrd` file, converts the discrete voxels into a continuous 3D surface mesh using Marching Cubes, smooths it, and uses Voronoi diagrams to extract a mathematically smooth centerline and maximum inscribed radii. This requires user interaction to select source/target points.
* **Method 2 (Maren's Method - Voxel Skeletonization):**
  Uses pure Python image processing (`scikit-image`). It relies on 3D morphological thinning (skeletonization) directly on the voxel grid to peel away the artery until a 1-voxel thick line remains, then maps the matrix indices to physical coordinates using the affine matrix.

## 7. Instructions for Cursor AI
When assisting with this repository, Cursor must adhere strictly to the following rules:
1. **Context Awareness:** Always refer back to this file to understand the broader clinical and mathematical goals of the pipeline.
2. **Environment:** Assume all code is running in a Conda environment (`tfg_adria`) with Python 3.10.
3. **Libraries:** Prefer `pyvista`, `vmtk` (for Method 1), `SimpleITK`, `nibabel`, `numpy`, and `scikit-image` (for Method 2).
4. **Medical Constraints:** Always remember that medical images have physical spacing (voxel size in mm). Matrix indices MUST be converted to physical spatial coordinates using the image header/affine matrix for any geometric calculation.
5. **DIARY.md Maintenance:** At the end of a coding session, when prompted, you must update the `DIARY.md` file with a structured log of what was tested, what bugs were fixed, and what the next immediate step is.