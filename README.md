# Final Degree Project Repository

Welcome to the repository for my Final Degree Project at UPF.

## Project Structure

+++

## Project Description

This project focuses on developing interpretable automated computational support for coronary artery disease (CAD) assessment. Working in collaboration with Hospital de la Santa Creu i Sant Pau, I aim to create robust and transparent tools for stenosis quantification from coronary computed tomography angiography (CCTA) data.

The main objectives include implementing a stenosis quantification pipeline based on geometric formulations, analyzing and aggregating measurements at different anatomical levels (point, segment, and vessel), and supporting CAD-RADS assignment through quantitative measurements and exploratory machine learning approaches. Additionally, the project will develop visualization tools to facilitate clinical interpretation and structure quantitative outputs for integration with patient prioritization systems used in clinical practice.

This work builds upon previous contributions from the collaborative framework, including automatic coronary artery segment labeling and patient prioritization systems, while focusing specifically on the robust quantification of coronary stenosis and its transformation into clinically meaningful indicators.

## Authors

- Adrià Cortés Cugat
- Universitat Pompeu Fabra (UPF)
- Mathematical Engineering In Data Science

## Running Instructions

- Activate Virtual Environment .venv: .\.venv\Scripts\Activate
- Upgrade PIP & Install Requirements: º
    - python -m pip install --upgrade 
    - pip python -m pip install -r requirements.txt
- Verification Check:
    - pip list
    - where.exe python
- To Run a Scrpit: 
    - python src/_pipeline.py 
    - python -m src._pipeline
