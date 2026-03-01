# TFG Development Diary

## Purpose of this File
This document serves as the chronological logbook for the development of the TFG: **Automated Geometric Stenosis Quantification and CAD-RADS Support**. 

The goal of this diary is to keep a detailed, "day-by-day" record of the project's progress. It tracks technical decisions, algorithm tests, bug fixes, and workflow updates. By maintaining this file, writing the final thesis memory will be significantly easier, as the entire evolution of the code and methodology will be documented here.

At the end of every coding session, Cursor AI will be prompted to summarize the work done and append a new entry using the standardized format below.

---

## 📝 Commit Entry Template
Every work session must be recorded using the following structure:

### [YYYY-MM-DD] - [Brief summary of the session's focus]
* **🎯 Objectives:** What was the main goal for today's session?
* **✅ Progress & Tasks Completed:** What was actually implemented, tested, or decided?
* **🐛 Bugs & Challenges:** What errors, environment issues, or mathematical roadblocks were encountered (and how were they solved)?
* **⏭️ Next Steps:** What is the immediate task for the next working session?

---

### 2026-02-23 - Environment Setup & Methodological Planning
* **🎯 Objectives:** Establish the technical foundation for the project and define the initial code architecture for centerline extraction.
* **✅ Progress & Tasks Completed:** * Defined the project scope and contextualized the work within the hospital's AI framework.
  * Created the `PROJECT_CONTEXT.md` to guide AI assistance (Cursor).
  * Successfully built a robust Conda environment (`tfg_adria`) with Python 3.10.
  * Installed heavy C++ medical imaging libraries (`vmtk`) via conda-forge to prevent compatibility issues.
  * Installed standard data science and visualization requirements (`pyvista`, `numpy`, `scikit-image`, `SimpleITK`).
* **🐛 Bugs & Challenges:** * *Issue:* Encountered a conflict installing VMTK because the initial environment defaulted to Python 3.14, which VMTK does not support.
  * *Fix:* Recreated the environment strictly locked to Python 3.10 and installed VMTK prior to other pip requirements.
* **⏭️ Next Steps:** Open `Method_1.ipynb`, use Cursor to generate the VMTK centerline extraction code, load a `.nrrd` Annotation file from the ASOCA dataset, and extract the first 3D coordinates.

---

### 2026-02-24 - VMTK Centerline Extraction Pipeline (Method 1, Steps 1–4)
* **🎯 Objectives:** Implement the first four steps of the VMTK-based centerline extraction pipeline in `01_centerline_extraction_1.ipynb` for a single ASOCA sample (`Normal_1`).
* **✅ Progress & Tasks Completed:**
  * Built the full notebook structure (20+ cells) covering: image loading, marching cubes, surface smoothing, seed point selection, VMTK centerline extraction, and results visualization.
  * **Critical architectural decision:** Rewrote the pipeline to stay entirely inside the VMTK/VTK C++ ecosystem (`vmtkImageReader` → `vmtkMarchingCubes` → `vmtkSurfaceSmoothing` → `vmtkCenterlines`). The initial version incorrectly used SimpleITK + scikit-image, which would have required complex NumPy-to-VTK conversions. Removing those libraries and using native VMTK scripts keeps the data as `vtkImageData`/`vtkPolyData` throughout, with seamless hand-offs between pipeline steps.
  * Successfully loaded `Normal_1.nrrd` (512×512×204 grid, 53.4M voxels, spacing 0.416×0.416×0.625 mm).
  * Successfully extracted the surface mesh via Marching Cubes (37,886 vertices, 75,768 triangles) and verified the bounds fall within the full CT volume.
  * Successfully smoothed the mesh with Taubin passband smoothing (500 iterations, passband 0.1) and confirmed vertex/triangle counts are preserved.
  * Added detailed educational markdown cells after each step explaining: image metadata parameters, how Marching Cubes works on binary masks, the sanity check on mesh bounds, and how Taubin smoothing preserves volume while removing voxel staircase artifacts.
* **🐛 Bugs & Challenges:**
  * *Issue:* `pv.set_jupyter_backend("trame")` crashed because `trame` is not installed in the conda environment, and the fallback to `"static"` also raised an uncaught `ImportError`.
  * *Fix:* Replaced with a loop that tries each backend and silently continues if both fail. PyVista still renders in a pop-out window.
  * *Issue:* `pv.Plotter()` crashed with `ModuleNotFoundError: No module named 'vtkmodules.vtkRenderingMatplotlib'` — the vmtk conda-forge build strips this VTK module.
  * *Fix:* Injected a dummy module in the imports cell via `sys.modules.setdefault("vtkmodules.vtkRenderingMatplotlib", types.ModuleType(...))` so PyVista skips it gracefully.
* **⏭️ Next Steps:** Continue with the remaining sections of `01_centerline_extraction_1.ipynb` (Steps 5–6): select seed points on the smoothed mesh, run `vmtkCenterlines`, inspect the extracted centerline data, and produce the final 3D visualization. Add explanatory markdown cells for those sections.

---

### 2026-03-01 - Smoothing Optimization & Automation Strategy
* **✅ Progress & Tasks Completed:** * Reviewed the `vmtkSurfaceSmoothing` step with the tutor.
  * Corrected the `NumberOfIterations` from 500 down to 20 to prevent over-smoothing and artificial shrinking of the distal branches, preserving true anatomical volume.
* **🧠 Strategic Pivot (Seed Point Automation):**
  * Discarded the manual, visual-based coordinate selection for VMTK seed points.
  * Decided to implement a fully automated hybrid approach combining VMTK's mathematical precision with topological skeletonization and graph theory.
* **⏭️ Next Steps:** * Tomorrow: Review Maren's original Python notebooks to confirm how she implemented the 3D voxel skeletonization ("peeling"), graph node degree calculation, and radius-based ostium identification.
  * Adapt her logic to automatically feed the `Source` and `Target` coordinates directly into the VMTK centerline extraction algorithm.