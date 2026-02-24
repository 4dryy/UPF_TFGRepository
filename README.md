# Automated Geometric Stenosis Quantification & CAD-RADS Support

Welcome to the main repository for my Final Degree Project (Treball de Fi de Grau) at Universitat Pompeu Fabra (UPF).

## 🏥 Project Description
This project focuses on developing interpretable, automated computational support for Coronary Artery Disease (CAD) assessment. Working in collaboration with the **Dimension Lab / PhySense at Hospital de la Santa Creu i Sant Pau**, this work aims to create robust and transparent tools for stenosis quantification from Coronary Computed Tomography Angiography (CCTA) data.

### Main Objectives:
* **Automate Clinical Workflow:** Implement an automated workflow to go from raw segmentation data to a visualization tool that helps the clinicians decision making with CADs.

* **Geometric Stenosis Quantification:** Explore and implement stenosis quanitifcation techniques as a key metric to add to the visualization tool


* **CAD-RADS Prediction:** Create CAD-RADS score assignment through quantitative predictions using and exploring machine learning approaches.

* **Visualization & Integration:** Develop interactive visualization tools to facilitate clinical interpretation and structure the quantitative outputs for seamless integration with existing patient prioritization systems.

This work builds upon previous contributions from the hospital's collaborative AI framework—including automatic coronary artery segment labeling and patient prioritization systems—bridging the gap between raw medical images and actionable clinical reports.

---

## 👨‍🎓 Author Information
* **Author:** Adrià Cortés Cugat
* **Degree:** Mathematical Engineering in Data Science
* **University:** Universitat Pompeu Fabra (UPF), Barcelona
* **Collaborators:** Hospital de la Santa Creu i Sant Pau

---

## ⚙️ Installation & Setup

**⚠️ CRITICAL:** This project relies on heavy C++ medical imaging libraries (like VMTK). It **cannot** be installed using a standard Python `venv`. You must use **Conda** (Miniconda or Anaconda) to manage the environment.

### 1. Create and Activate the Environment
Open your terminal and create a new Conda environment specifically locked to Python 3.10:
```bash
conda create -n tfg_adria python=3.10 -y
conda activate tfg_adria
```

### 2. Install VMTK (Must be done first)
Install the Vascular Modeling Toolkit via the `conda-forge` channel to ensure all C++ dependencies are correctly handled:
```bash
conda install -c conda-forge vmtk -y
```

### 3. Install Python Requirements
Once VMTK is successfully installed, install the rest of the data science and medical imaging libraries using `pip`:
```bash
pip install -r requirements.txt
```

---

## 🚀 Running Instructions

Whenever you open this project, ensure your Conda environment is active:
```bash
conda activate tfg_adria
```

**Verification Check:**
To verify the environment is correctly set up, run:
```bash
conda list vmtk
python --version
```

**Executing Code:**
* **Jupyter Notebooks:** Select the `tfg_adria` kernel in the top right corner of your VS Code / Cursor editor.
* **Python Scripts:** Run via the terminal using `python path/to/script.py` (e.g., `python src/_pipeline.py`).

---

## 📂 Project Structure
*(To be populated as the codebase expands)*
* `data/` - Placeholder for dataset inputs (e.g., ASOCA `.nrrd` files).
* `notebooks/` - Isolated Jupyter notebooks for methodology testing (e.g., `Method_1.ipynb`).
* `src/` - Core Python modules and pipeline scripts.
* `PROJECT_CONTEXT.md` - Detailed architectural and clinical context for AI assistance.
* `DIARY.md` - Chronological development logbook.