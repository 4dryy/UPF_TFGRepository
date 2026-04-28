"""
Project pipeline entrypoint.

Run all blocks sequentially for a given patient. Each block receives
the output of the previous one.

Usage:
    python -m src._pipeline
"""

from __future__ import annotations

import logging

from src.blocks._01_extraction import run_block1
from src.blocks._02_stenosis import run_block2
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    logging.info("Pipeline started for patient: %s", patient_id)

    df_centerlines = run_block1(patient_id=patient_id)
    df_area = run_block2(patient_id=patient_id)

    # Future blocks receive the dataframe from the previous block:
    # df_stenosis = run_block3(df_area)
    # ...

    logging.info("Pipeline finished for patient: %s", patient_id)


if __name__ == "__main__":
    pid = _prompt_patient_id()
    main(patient_id=pid)
