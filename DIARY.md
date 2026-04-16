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

  ---

  ### 2026-03-02 - Hybrid Pipeline Architecture & Maren's Code Integration
* **🎯 Objectives:** Analyze Maren's baseline code, define the architecture for the automated hybrid approach, and generate the new extraction pipeline using Cursor.
* **✅ Progress & Tasks Completed:** * Reviewed Maren's notebooks (`rca_lca_separation`, `Skeletonization`, `voxels_to_points_df`) to understand her topological thinning and center-of-mass logic.
  * Designed a 3-Phase Hybrid Pipeline: 
    1. **Pre-processing:** Split RCA/LCA using `scipy.ndimage` connected components.
    2. **The "Scout":** Automate seed point detection using `skimage` skeletonization and exact distance transforms to identify the Ostium (thickest endpoint).
    3. **The Math:** Pass coordinates to VMTK for exact Voronoi centerline extraction and inscribed radii calculation.
  * Created a new notebook (`03_centerline_extraction_hybrid.ipynb`) to preserve the manual `Method_1` as a debugging fallback.
  * Engineered a massive, context-aware prompt for Cursor, directly linking Maren's notebooks to ensure accurate code adaptation.
* **⏭️ Next Steps:** Tomorrow, review the code generated by Cursor cell-by-cell. We will specifically verify the VTK-to-NumPy data bridge, the RCA/LCA spatial separation logic, and the final DataFrame construction.

---

### 2026-03-23 - Update 3 Presentation, Architecture Refactoring & Pipeline v1

* **🎯 Objectives:** Present the hybrid approach to the PhySense group, integrate feedback, and refactor the notebook prototype into a production-ready modular pipeline.

* **✅ Progress & Tasks Completed:**
  * **Update 3 Presentation:** Successfully presented the "Hybrid Centerline Extraction" approach to Oscar and the PhySense group, demonstrating how Maren's voxel skeletonization (automated scout) combined with VMTK's Voronoi math (sub-millimeter precision) eliminates manual seed initialization.
  * **Feedback Integration:** Received clinical and technical feedback — need to better define where the tool fits in the clinical triage workflow, improve terminology (use "discrete vs. continuous" instead of "mathematically weaker"), define all acronyms, and cite AI-generated image sources.
  * **Pipeline Architecture Refactoring:**
    * Refactored the entire `03_centerline_extraction_hybrid.ipynb` notebook into a production-ready module: `src/blocks/_01_extraction.py`.
    * Adopted a single-file-per-block strategy for simplicity and readability.
    * Created `src/_pipeline.py` as the main entrypoint — prompts the user for a Patient ID at runtime, then chains blocks sequentially.
    * Each block returns its output (DataFrame) to feed the next block in the pipeline.
  * **Seed Snapping Fix:** Implemented a surface-normal-aware inward nudging strategy in `_snap_seed_to_surface()` to mitigate VMTK "no steepest descent edge" failures. Instead of naive closest-vertex snapping, seeds are now projected onto the mesh and nudged inward along the vertex normal by a fraction of the average edge length, then re-snapped. Updated both the pipeline module and the notebook to match.
  * **Data Management:**
    * Established output naming convention: `centerline_<PatientID>_<ArteryType>_<YYYYMMDD>.vtp` and `df_<PatientID>_<YYYYMMDD>.xlsx`.
    * Implemented overwrite-on-rerun logic — re-executing the same patient deletes previous results to avoid duplicates.
    * Results stored under `results/block1_results/` with subfolders `dataframes/` and `centerlines/`.
  * **Validation:** Successfully ran the pipeline on `Normal_1` and `Normal_2`, producing correct centerline VTP files and Excel DataFrames.

* **🐛 Bugs & Challenges:**
  * *Issue:* `ModuleNotFoundError: No module named 'openpyxl'` when saving the DataFrame to Excel.
  * *Fix:* Installed `openpyxl` in the `tfg_adria` conda environment (`pip install openpyxl`). The package was already listed in `requirements.txt` but had not been installed.
  * *Issue:* VMTK "no steepest descent edge" warnings — some skeleton endpoints on tiny spurious branches land on poorly-connected regions of the Voronoi diagram.
  * *Mitigation:* Implemented the inward-nudge seed snapping strategy. Future work may add skeleton branch pruning or per-target retry logic.

* **💡 Feedback from Update 3 (Oscar & PhySense Group):**
  * Clinical Context: Need to better define where this tool fits in the "Master Clinical Workflow" (Prioritization/Triage).
  * Standards: Improve terminology and define all acronyms. Cite AI-generated image sources.
  * Evaluation: Discussed the future need to validate centerlines against ASOCA ground truth (Average Distance error).

* **⏭️ Next Steps:**
  * Validate the pipeline across more ASOCA patients to stress-test the seed snapping fix.
  * Create "Level 1" clinical workflow diagrams (Current vs. Future Hospital Workflow) for the upcoming 1-on-1 meeting with Oscar.
  * Investigate additional VMTK troubleshooting strategies: skeleton branch pruning and surface capping for narrow vessel segments.
  * Begin work on Block 2 (Stenosis Quantification).

---

### 2026-04-16 — Documentation Refactoring & Workflow Diagrams as Methodology Foundation

* **🎯 Objectives:** Refactor all project documentation to align with the "Workflow as a Product" approach and the formalized 4-block modular architecture, establishing a professional and consistent documentation baseline before starting Block 2.

* **✅ Progress & Tasks Completed:**
  * **Workflow Diagrams Created:** Designed and completed a comprehensive set of 15 workflow diagrams (`Workflow Diagrams 16_04.pdf`) that formalize the entire project architecture. These diagrams cover:
    * The current clinical workflow at Hospital de Sant Pau for CAD diagnosis (patient journey from chest pain to final report).
    * The manual image analysis bottleneck (detailing how the radiologist currently extracts features by hand).
    * The proposed automated workflow with the support visualization tool and patient prioritization loop.
    * The master E2E pipeline architecture showing all 4 blocks and their data flow.
    * The development progress dashboard with internal phases for each block.
    * Detailed flow diagrams for Block 1 (hybrid extraction), Block 2 (geometric stenosis quantification), Block 3 (CAD-RADS prediction), and Block 4 (visualization dashboard).
  * **README.md — Full Rewrite:**
    * Added a professional header with author and institution information.
    * Created a "Project Architecture" section with a visual ASCII diagram of the 4-block pipeline.
    * Built an HTML-based Development Progress Dashboard table (matching the workflow diagrams slide 8) with green-highlighted cells for completed phases — designed as a living roadmap for future contributors.
    * Wrote a detailed "Block 1 Methodology" section explaining the Hybrid Approach (Scout + Math) with its three phases: Pre-processing, Voxel Skeletonization, and VMTK Voronoi Centerlines.
    * Documented pipeline execution instructions (`python -m src._pipeline`), output naming conventions, and standalone block execution.
    * Added an Acronym Legend for all medical imaging and technical terms used.
  * **CONTEXT.md — Full Rewrite:**
    * Structured around three core sections: Current Workflow, Manual Bottleneck, and Proposed Workflow.
    * Described the complete 5-step patient journey at Hospital de Sant Pau (from chest pain presentation to CAD diagnosis).
    * Deepened the clinical motivation by quantifying the bottleneck: ~30 minutes per healthy patient, ~60–90 minutes per complex case, limiting throughput to 8–16 patients per radiologist per day.
    * Explained how the proposed automated pipeline reduces assessment time, enables patient prioritization, improves reproducibility, and integrates with existing hospital systems.
    * Added the surrounding research ecosystem (Maren Clapers, Ela Burrull, Eva Ferrer) to contextualize this project within the larger AI framework.
    * Included Cursor AI instructions and Acronym Legend for consistency.
  * **DIARY.md — Updated:**
    * Added this comprehensive entry documenting the documentation refactoring session.
  * **Conceptual Shift Documented:** The project narrative has evolved from "a collection of experimental notebooks" to "a structured medical engineering system where the workflow itself is the product." The final deliverable is the visualization dashboard, but the project encompasses the entire automated pipeline from segmentation input to clinical output.

* **💡 Key Decisions:**
  * The workflow diagrams are now the single source of truth for the project's architecture. All documentation files reference and align with these diagrams.
  * The Development Progress Dashboard in the README is designed as a living table — phases will be colored green as they are implemented, providing immediate visibility to anyone continuing the project.
  * Documentation uses an "academic yet engineering-focused" tone with professional medical imaging terminology (CCTA, PACS, CAD-RADS, %DS) while remaining accessible to non-specialist readers through acronym legends and contextual explanations.

* **⏭️ Next Steps:**
  * Begin experimental work on Block 2 (Geometric Stenosis Quantification): implement cross-sectional area computation along the centerline using perpendicular planes.
  * Define the interpolated healthy reference methodology for %DS calculation.
  * Create the `notebooks/block2_stenosis/` exploration notebooks before refactoring into `src/blocks/_02_stenosis.py`.

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