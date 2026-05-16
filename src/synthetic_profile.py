"""
Synthetic validation cases (single-tube NRRD masks under ``data/Synthetic Samples``).

Detected when ``patient_id.startswith("Synthetic_")``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DATA_ROOT = PROJECT_ROOT / "data" / "Synthetic Samples"

SYNTHETIC_ARTERY = "Synthetic"
SYNTHETIC_BRANCH_ID = 0
# Numeric ID for VTK / pandas (not in AHA 1–17); ``Segment_Name`` holds the display label.
SYNTHETIC_SEGMENT_ID = 99
SYNTHETIC_SEGMENT_NAME = "Synthetic Vessel"
SYNTHETIC_SEGMENT_TAG = "Synthetic_Vessel"
SYNTHETIC_CAD_RADS_LABEL = "N/A (Synthetic Case)"


def is_synthetic_patient(patient_id: str) -> bool:
    return str(patient_id).strip().startswith("Synthetic_")


def resolve_mask_nrrd_path(patient_id: str) -> Path:
    """Return the segmentation mask path for ASOCA or synthetic cohorts."""
    pid = str(patient_id).strip()
    if is_synthetic_patient(pid):
        path = SYNTHETIC_DATA_ROOT / f"{pid}.nrrd"
    else:
        path = PROJECT_ROOT / "data" / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd"
    return path


def apply_synthetic_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Populate placeholder anatomy / segment columns for synthetic single-tube cases."""
    out = df.copy()
    out["Artery_Type"] = SYNTHETIC_ARTERY
    out["Branch_ID"] = SYNTHETIC_BRANCH_ID
    out["Segment_ID"] = SYNTHETIC_SEGMENT_ID
    out["Segment_Name"] = SYNTHETIC_SEGMENT_NAME
    return out


def synthetic_branch_file_stem() -> str:
    """Branch spreadsheet / centerline filename stem (``dataset_<stem>_<patient>.xlsx``)."""
    return f"{SYNTHETIC_ARTERY}_{SYNTHETIC_BRANCH_ID}"
