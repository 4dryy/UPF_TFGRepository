"""
Project pipeline entrypoint.

Run all blocks sequentially for a given patient. Each block receives
the output of the previous one.

Usage:
    python -m src._pipeline
"""

from __future__ import annotations

import logging
import time

from src.blocks._01_extraction import run_block1
from src.blocks._02_stenosis import Block2Outputs, run_block2
from src.pipeline_log import banner_pipeline, banner_pipeline_done, configure_logging
# from src.blocks._03_ import run_block3
# from src.blocks._04_ import run_block4


def _prompt_patient_id() -> str:
    """Ask the user for a patient ID until a non-empty value is provided."""
    while True:
        pid = input("Enter Patient ID (e.g. Normal_1): ").strip()
        if pid:
            return pid
        print("Patient ID cannot be empty. Please try again.")


def main(patient_id: str) -> None:
    configure_logging()
    log = logging.getLogger("pipeline")
    t0 = time.perf_counter()

    banner_pipeline(log, patient_id)
    run_block1(patient_id=patient_id)
    block2_out: Block2Outputs = run_block2(patient_id=patient_id)
    _df_global_area = block2_out.df_global_area
    _total_df_merged = block2_out.total_df_merged

    # Future blocks can use area-aligned globals and/or merged %AS table:
    # df_stenosis = run_block3(_df_global_area, _total_df_merged)
    # ...

    banner_pipeline_done(log, patient_id, time.perf_counter() - t0)


if __name__ == "__main__":
    pid = _prompt_patient_id()
    main(patient_id=pid)
