# TFG Development Diary

## Purpose of this File
This document serves as the chronological logbook for the development of the TFG: **Automated Geometric Stenosis Quantification and CAD-RADS Support**. 

The goal of this diary is to keep a detailed, day-by-day record of the project's progress. It tracks technical decisions, algorithm tests, bug fixes, and workflow updates. By maintaining this file, writing the final thesis memory will be significantly easier, as the entire evolution of the code and methodology will be documented here.

At the end of every coding session, Cursor AI will be prompted to summarize the work done and append a new entry using the standardized format below.

---

## 📝 Daily Entry Template
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