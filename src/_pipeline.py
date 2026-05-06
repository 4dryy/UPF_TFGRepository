"""

Project pipeline entrypoint.



Run all blocks sequentially for a given patient. Each block receives

the output of the previous one.



Usage:

    python -m src._pipeline

"""



from __future__ import annotations



import importlib.util

import logging

import time

from pathlib import Path



from src.blocks._01_extraction import run_block1

from src.blocks._02_stenosis import run_block2

from src.pipeline_log import banner_pipeline, banner_pipeline_done, configure_logging, sub





def _prompt_patient_id() -> str:

    """Ask the user for a patient ID until a non-empty value is provided."""

    while True:

        pid = input("Enter Patient ID (e.g. Normal_1): ").strip()

        if pid:

            return pid

        print("Patient ID cannot be empty. Please try again.")





def _resolve_segment_label_path(patient_id: str) -> Path | None:

    """Locate ``.nii.gz`` segment labels under ``data/ASOCA Labels`` (legacy + split cohort folders)."""

    root = Path(__file__).resolve().parents[1]

    candidates = [

        root / "data" / "ASOCA Labels" / f"{patient_id}.nii.gz",

        root / "data" / "ASOCA Normal Labels" / f"{patient_id}.nii.gz",

        root / "data" / "ASOCA Diseased Labels" / f"{patient_id}.nii.gz",

    ]

    for c in candidates:

        if c.is_file():

            return c.resolve()

    return None





def _load_block3_phase1():

    blocks_dir = Path(__file__).resolve().parent / "blocks"

    module_path = blocks_dir / "_03_cad-rats.py"

    spec = importlib.util.spec_from_file_location("block3_cadrats_label", module_path)

    if spec is None or spec.loader is None:

        raise ImportError(f"Cannot load Block 3 module from {module_path}")

    mod = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(mod)

    return mod





def main(patient_id: str) -> None:

    configure_logging()

    log = logging.getLogger("pipeline")

    t0 = time.perf_counter()



    banner_pipeline(log, patient_id)



    label_path = _resolve_segment_label_path(patient_id)

    if label_path is None:

        sub(log, "ASOCA label .nii.gz not found — Block 1 uses scout RCA/LCA pairing.")

    else:

        sub(log, "ASOCA labels: %s", label_path)



    run_block1(patient_id=patient_id, label_nii_path=label_path)



    run_block2(patient_id=patient_id)



    block3_mod = _load_block3_phase1()

    block3_mod.run_block3_phase1(patient_id)



    banner_pipeline_done(log, patient_id, time.perf_counter() - t0)





if __name__ == "__main__":

    pid = _prompt_patient_id()

    main(patient_id=pid)


