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
  * The Development Progress Dashboard in the README is designed as a living table.
  * Documentation uses an "academic yet engineering-focused" tone with professional medical imaging terminology (CCTA, PACS, CAD-RADS, %DS) while remaining accessible to non-specialist readers through acronym legends and contextual explanations.

* **⏭️ Next Steps:**
  * Begin experimental work on Block 2 (Geometric Stenosis Quantification).
  * Define the interpolated healthy reference methodology for %DS calculation.
  * Create the `notebooks/block2_stenosis/` exploration notebooks before refactoring into `src/blocks/_02_stenosis.py`.

---

### 2026-04-20 — Block 2 · Task 1: Sectional Area Extraction (Exploratory Notebook)

* **🎯 Objectives:** Implement and validate the first sub-task of Block 2 — compute the **cross-sectional lumen area at every centerline point** for a single patient (both arteries) using VMTK's `vmtkCenterlineSections`, and integrate the result into the Block 1 dataframe as a new `Area (mm²)` column. The implementation lives in `notebooks/block2_stenosis/_04_sq_sectional_area.ipynb` (exploratory; later to be migrated into `src/blocks/_02_stenosis.py`).

* **✅ Progress & Tasks Completed:**
  * **Notebook scaffold (Block 1-style):** 20 cells organized into 6 sections (Imports & Configuration → Data Loading & Mesh Preparation → Cross-Sectional Area Computation → DataFrame Integration → Visual Validation → Export), mirroring the didactic green-banner style used in `03_centerline_extraction_hybrid.ipynb`.
  * **Robust I/O layer:** Auto-detection of the latest Block 1 dataframe (`.xlsx` or `.csv`), latest per-artery centerline `.vtp`, and validation of required columns (`Patient_ID, Artery_Type, Px, Py, Pz, Radius`).
  * **Mesh regeneration from mask:** Because Block 1 does not currently persist the smoothed surface, Block 2 rebuilds it from the original `.nrrd` using the exact Block 1 parameters (Marching Cubes level 0.5 + Taubin 20-iter, 0.1 passband) via the reused helpers `load_and_separate_mask` and `_numpy_to_vtk_image`. Coordinate system matches are explicitly verified per artery (bbox + point-count comparison).
  * **Defensive VMTK preprocessing:** Added `clean_triangulate_surface` (via `vtkTriangleFilter` + `vtkCleanPolyData`) and `prepare_centerline_for_sections` (`vmtkCenterlineSmoothing` 100-iter + `vmtkCenterlineResampling` 0.1 mm step) to prevent `vmtkCenterlineSections` from segfaulting on coincident centerline points or non-triangulated surfaces.
  * **Core section computation:** `compute_centerline_sections` wraps VMTK and returns `(sections_polydata, centerline_with_arrays)`. `extract_area_array` converts VMTK's `CenterlineSectionArea` into a clean `(N,)` float array, marking non-closed / zero-area / non-finite sections as `NaN` — the **robustness cornerstone** for diseased patients.
  * **DataFrame integration:** Row-aligned merge where possible, KDTree nearest-point fallback otherwise (always hit after resampling, which changes point count). Enriched sanity checks include: global NaN count, **per-artery NaN breakdown with row-level preview** of offending points (`Px/Py/Pz/Radius`), and a `corr(Radius, Area)` check per artery (expected strongly positive).
  * **Visual validation:**
    * **3D overview:** low-opacity surface mesh + centerline point cloud coloured by `Area (mm²)` — stenoses would appear as cold-coloured bands.
    * **2D cross-section QA plots:** for each artery, plot the actual lumen outline at three representative points (healthy-median, narrow-min, random). After iterating on the approach, the current implementation re-cuts the surface mesh directly at each QA point using the centerline-tangent plane (`vtkCutter` → `ClosestPointRegion` → `vtkStripper`), giving high-resolution, ordered 2D outlines aligned with VMTK's area values.
    * Added dedicated **§5c "QA Interpretation & Validation"** markdown with: root-cause explanation of the QA bugs encountered, plot semantics, definition of `centroid-dist` as a trust metric, per-pick verdict table for the current patient, and recommended downstream filters (trim tips, flag high `centroid_dist / Radius`, smooth the Area signal, define a per-artery healthy reference).
  * **Export:** New code cell writes `results/block2_results/dataframes/df_<Patient>_<date>.xlsx` with the `Area` column appended. First run produced `df_Normal_1_20260420.xlsx` (7,296 rows, 0 NaN).
  * **Quantitative validation on `Normal_1`:** Healthy sections satisfy `Area ≈ 1.2–1.4 · π·R²` (consistent with slightly oval lumens and the MIS radius being a lower bound); healthy `centroid_dist ≈ 0` mm; `corr(Radius, Area) = +0.895` (RCA) and `+0.745` (LCA) — signal quality is suitable for the downstream %AS / %DS step.
  * **Notebook polish:** Rewrote the Method Overview to match the actual §1–§6 layout (removed the obsolete Phase A/B/C/D diagram), updated the stale strategy comment at the top of the 2D QA cell to reflect the re-cut approach, trimmed redundant docstring narrative, tightened the Summary section to avoid duplicating §5c.

* **🐛 Bugs & Challenges:**
  * *Issue:* `ModuleNotFoundError: No module named 'src'` on the first cell execution.
    *Cause:* `src/blocks/__init__.py` uses absolute imports (`from src.blocks._01_extraction import ...`), requiring **`PROJECT_ROOT`** on `sys.path`, not `PROJECT_ROOT / "src"`.
    *Fix:* Changed the path insertion to `sys.path.insert(0, str(PROJECT_ROOT))` and used the fully-qualified import.
  * *Issue:* Kernel crash (C++ segfault, no Python traceback) when calling `vmtkCenterlineSections`.
    *Cause:* VMTK cannot handle non-triangulated surfaces or centerlines with near-duplicate consecutive points (`AppendEndPoints=1` in Block 1 produces exactly this).
    *Fix:* Added defensive preprocessing — triangulate & clean the surface, smooth & uniformly resample the centerline (0.1 mm step) — which also improves tangent stability at bifurcations.
  * *Issue:* `IndexError: single positional indexer is out-of-bounds` in the 2D QA cell for LCA.
    *Cause:* `idx` indexed the *resampled* centerline (denser) but the code was using it against the original Block 1 dataframe subset for the radius lookup.
    *Fix:* Read the radius from the resampled centerline's `MaximumInscribedSphereRadius` point-data array (where values are correctly interpolated and aligned with `idx`).
  * *Issue:* First QA plots showed triangular shapes for every pick.
    *Cause:* `vmtkCenterlineSections` stores each section as a **triangulated patch** (~7–8 coplanar triangles); the initial code was picking the single nearest *triangle*, not the whole patch.
    *Fix attempt (failed):* Group patches with `vtkPolyDataConnectivityFilter` — failed because adjacent sections share vertex IDs inherited from the parent surface, so the whole `sections_pv` is one connected component.
    *Final fix:* Abandon `sections_pv` for QA and **re-cut the smoothed surface mesh** at each QA centerline point with a tangent-perpendicular plane. This reproduces VMTK's internal slicing and yields clean, ordered outlines. `Area` values in the titles still come from VMTK so the shape and number remain consistent.
  * *Issue:* Outline points plotted from `vtkStripper` looked jagged.
    *Cause:* `vtkStripper` returns a `vtkPolyData` whose `.points` array is not necessarily in traversal order; the ordered sequence lives in the `lines` connectivity.
    *Fix:* Rebuild the ordered sequence by following the first polyline cell's index list.

* **💡 Key Decisions:**
  * **Separation of concerns between authoritative area and QA visualization.** `CenterlineSectionArea` produced by VMTK is the single source of truth for the `Area` column. The QA re-cut is visualization-only; its purpose is exclusively to *inspect* the slice geometry, never to re-measure area. This avoids two disagreeing numbers in the dataframe vs. the plots.
  * **NaN is a first-class signal, not an error.** Non-closed sections, degenerate tangents, and near-total occlusions will all surface as `NaN` in the `Area` column. Downstream stenosis-detection code must interpret them as "missing data", not propagate them as `0 mm²`.
  * **The methodology is patient-agnostic; only the notebook wrapper is not.** All algorithmic components (mesh rebuild, defensive preprocessing, VMTK section call, NaN policy, KDTree merge) are parameter-free and generalize to Diseased patients. What is currently notebook-local (hardcoded `ASOCA Normal` path, single-patient scope) will be promoted to `src/blocks/_02_stenosis.py` as `run_block2(patient_id)` with auto-detection between `ASOCA Normal / Diseased` and a patient-loop driver.

* **⏭️ Next Steps:**
  * **Block 2 · Task 2 — Healthy Reference Values:** Start `_05_sq_reference_values.ipynb` (already created as empty placeholder). Define a robust per-artery healthy reference radius/area (e.g. rolling median over proximal third with outlier clipping), respecting §5c's filtering recommendations (trim tips, exclude points with `centroid_dist / Radius > 0.3`).
  * **Block 2 · Task 3 — %AS / %DS computation** against the healthy reference, with NaN-aware smoothing (Savitzky–Golay or rolling median) of the `Area` signal before identifying local minima.
  * **Refactor trigger:** Once the next two sub-tasks validate the current `Area` signal, promote the exploratory helpers to `src/blocks/_02_stenosis.py` behind a `run_block2(patient_id)` entry point mirroring `run_block1`, and optionally add a one-line Block 1 improvement (`results/block1_results/meshes/surface_<Patient>_<Artery>_<date>.vtp`) to eliminate the NRRD-based mesh reconstruction from Block 2.

---

### 2026-04-21 — Update 4 Presentation Preparation & Block 2 Visual QA Tuning

* **🎯 Objectives:** Finalize material for the 4th update meeting with Oscar and the PhySense group, and improve the interpretability of the 3D area visualization in Block 2 so lumen-width variation is easier to inspect visually.

* **✅ Progress & Tasks Completed:**
  * Prepared the new presentation for tomorrow's follow-up meeting and added it to the project documentation folder as `PhySense Update 4 _ Adrià Cortés Cugat.pdf`, continuing the update-series record.
  * Updated `notebooks/block2_stenosis/_04_sq_sectional_area.ipynb` (cell §5a, 3D overview) to replace the default `viridis` palette with a clinically intuitive red↔green scale:
    * **Red** for narrower lumen sections (lower `Area`).
    * **Green** for wider lumen sections (higher `Area`).
  * Increased color-change sensitivity in the same cell by introducing percentile-based display limits:
    * `vmin = nanpercentile(Area, 5)` and `vmax = nanpercentile(Area, 95)`.
    * Applied through `clim=[vmin, vmax]` so outliers do not compress most points into a near-uniform color.
  * Smoothed visual transitions while preserving interpretability using a controlled discrete gradient (`N=64`) in a custom `LinearSegmentedColormap`.
  * Result: the 3D centerline-area map now better highlights subtle local changes in vessel caliber instead of showing most of the artery in the same red range.

* **🐛 Bugs & Challenges:**
  * *Issue:* Initial red/green remap still appeared dominated by red tones, with only small green patches.
  * *Cause:* Global min/max scaling was overly influenced by a small number of extreme area values.
  * *Fix:* Switched to robust percentile clipping (`5th–95th`) before color mapping.

* **⏭️ Next Steps:**
  * Deliver Update 4 presentation and capture feedback from Oscar/PhySense on Block 2 progress and methodology framing.
  * If visual feedback still suggests low contrast, tune sensitivity window (`10–90` for more contrast, `2–98` for less aggressive clipping) and standardize one default for all patients.
  * Continue with Block 2 Task 2 in `_05_sq_reference_values.ipynb` (healthy reference definition) before implementing `%AS/%DS`.

---

### 2026-04-28 — Block 1 Packaging Finalization + Block 2 Area Pipeline Integration

* **🎯 Objectives:** Finalize Block 1 as a robust patient-package generator and migrate Block 2 phase 1 (sectional area) from notebook methodology into the production pipeline, including data propagation and visualization outputs.

* **✅ Progress & Tasks Completed:**
  * **Block 1 package consolidation (`src/blocks/_01_extraction.py`):**
    * Finalized sample-centric output layout under `results/block1_results/<Patient_ID>/`.
    * Persisted global, artery-level, and branch-level dataframes/centerlines with overwrite-on-rerun behavior.
    * Added branch QC figures and global centerline-tree figure (colored ostia/endpoints).
    * Added saving of artery surface meshes (`surface_RCA.vtp`, `surface_LCA.vtp`) to support downstream reuse.
  * **Block 2 phase 1 implementation (`src/blocks/_02_stenosis.py`):**
    * Implemented `run_block2(patient_id)` as first production version of geometric stenosis quantification (area extraction).
    * Reads Block 1 package and computes per-point `Area` via `vmtkCenterlineSections` on full RCA/LCA trees.
    * Propagates area values to:
      * global dataframe,
      * artery dataframes,
      * branch dataframes.
    * Mapping policy implemented:
      * direct row-aligned assignment when possible,
      * KDTree nearest-point fallback otherwise.
    * Exports Block 2 outputs under `results/block2_results/area/<Patient_ID>/` with overwrite-on-rerun.
    * Added area-colored visual outputs (full tree, artery-level, and branch-level).
  * **Pipeline wiring (`src/_pipeline.py`):**
    * Activated Block 2 call after Block 1 so both phases run in one E2E command.

* **🐛 Bugs & Challenges:**
  * *Issue:* Pipeline appeared to stop after Block 1 with no Python traceback and no Block 2 outputs.
  * *Cause:* Native VTK/VMTK failure around `vmtkCenterlineSections` (silent crash/hang behavior).
  * *Fixes applied:*
    * Switched Block 2 section computation path to VTK-native inputs.
    * Added defensive preprocessing from notebook methodology:
      * surface triangulation + cleaning,
      * centerline smoothing + uniform resampling.
    * Added granular log checkpoints around area computation.
    * Reused Block 1 saved surfaces to reduce recomputation and improve geometric consistency.

* **💡 Key Decisions:**
  * Block interfaces are now artifact-based by patient package, enabling reproducibility and resumability.
  * Block 2 uses full-artery area computation (RCA/LCA trees) and then maps to branch dataframes, preserving a globally consistent geometry signal.
  * Mesh persistence in Block 1 is preferred over rebuilding in Block 2 for efficiency and reduced divergence between blocks.

* **⏭️ Next Steps:**
  * Begin Block 2 phase 2: healthy reference definition per artery/path.
  * Implement `%AS/%DS` computation over the new `Area` signal with robust NaN and outlier handling.
  * Add optional summary report per patient (mapping modes, NaN stats, area ranges) for QA traceability.

---

### 2026-05-05 — Block 2 stenosis integration, split results layout, unified pipeline logging

* **🎯 Objectives:** Finish Block 2 in production code so it matches the reference notebooks (sliding-window reference, **%AS**, merge per rounded 3D location), separate area vs. stenosis artifacts on disk, keep one module per block, and make pipeline logs concise and consistent.

* **✅ Progress & Tasks Completed:**
  * **Block 2 (`src/blocks/_02_stenosis.py`):**
    * Single-module implementation (no extra submodule): helpers for **`gd`**, **`Area_prox` / `Area_dist`**, **`A_ref`** (±10 mm window), **`pct_AS`**, and **merge** (rounded coordinates, max **%AS** per site, **`source_branch`**), aligned with `notebooks/block2_stenosis/_05_sq_reference_values.ipynb`.
    * **In-memory branch dict** during the area loop — stenosis does not re-read area Excel from disk.
    * **`run_block2` → `Block2Outputs`**: returns **`df_global_area`** (Block-1–aligned rows + `Area`) and **`total_df_merged`** (merged table; empty if no branch spreadsheets).
  * **Results layout:**
    * **`results/block2_results/area/<Patient>/`** — area phase only: global/artery/branch tables with **`Area`**, area colormap figures.
    * **`results/block2_results/stenosis/<Patient>/`** — enriched branches, **`total_df_<Patient>.xlsx`**, unified + per-branch **%AS** PyVista figures (GYR colormap, grey backbone polylines + hulls when surfaces exist).
    * Start of **`run_block2`** deletes **both** patient folders under `area/` and `stenosis/` so reruns **overwrite** cleanly (no duplicated samples).
  * **Pipeline (`src/_pipeline.py`):** Uses **`Block2Outputs`**; leaves hooks for a future Block 3 consuming **`df_global_area`** / **`total_df_merged`**.
  * **Logging (`src/pipeline_log.py` + blocks):** Shared **`configure_logging`**, pipeline **banners**, **`>> Block N`** phase lines, indented metrics, **`footer_block`** summaries; reduced noisy per-file/per-step logs while keeping ostium scores, section stats, mapping modes, merge counts, and timings.

* **🐛 Bugs & Challenges:**
  * Variable naming in Block 2 briefly shadowed the logging helper **`sub`** during dataframe unpacking — fixed by renaming unpacked columns (e.g. **`mapped_df`**) and aliasing **`sub`** as **`log_detail`** where needed.

* **💡 Key Decisions:**
  * **Two-folder Block 2 layout** preserves a clear **area-only** snapshot for downstream steps that need Block-1 row counts, while **stenosis** holds the richer analytic exports.
  * **Terminal UX:** one visual language for Block 1, Block 2, and top-level pipeline (rules, phase headers, footers with seconds).

* **⏭️ Next Steps:**
  * Block 3: CAD-RADS or segment-level scoring using **`total_df_merged`** / **`df_global_area`** as inputs.
  * Optional QA notebook or report comparing merged row counts vs. notebook runs on identical inputs.
  * Extend pipeline logging once Block 3/4 exist (same `pipeline_log` patterns).

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
| **MIS** | Maximum Inscribed Sphere (radius) |
| **QA** | Quality Assurance (visual/numeric sanity checking) |
| **ASOCA** | Automated Segmentation of Coronary Arteries (MICCAI 2020) |