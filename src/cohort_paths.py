"""
Resolve input paths for ASOCA, MACS-18, and synthetic cohorts.

Patient IDs encode the dataset (no extra metadata tag is needed in results):
- ``Normal_1``, ``Diseased_1`` — ASOCA
- ``MACS_Normal_1``, ``MACS_Diseased_1`` — MACS-18 (re-annotated higher-precision version of ASOCA)
- ``Synthetic_1``, ``Synthetic_2`` — synthetic phantoms

All three cohorts share input formats (segmentation mask ``.nrrd`` with two RCA/LCA labels +
SCCT-18 segment label volume ``.nii.gz``), so Blocks 1-4 run with the *same* methodology on all of them.
The only thing that changes per cohort is where on disk the files live; that is what this
module encapsulates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

# Master switch for the MACS-18 cohort. Kept as a module-level flag (rather than removed)
# so a user can quickly disable MACS-18 lookups again if their disk copy is ever incomplete:
# when False, ``resolve_mask_nrrd_path`` / ``resolve_segment_label_path`` reject MACS IDs
# with a clear RuntimeError instead of silently failing later inside Block 1.
MACS_PIPELINE_ENABLED = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"

ASOCA_ROOT = DATA_ROOT / "ASOCA"
MACS_ROOT = DATA_ROOT / "MACS-18"
SYNTHETIC_DATA_ROOT = DATA_ROOT / "Synthetic Samples"

CohortKind = Literal["asoca", "macs", "synthetic"]


def patient_cohort(patient_id: str) -> CohortKind:
    pid = str(patient_id).strip()
    if pid.startswith("Synthetic_"):
        return "synthetic"
    if pid.startswith("MACS_"):
        return "macs"
    return "asoca"


def cohort_label(patient_id: str) -> str:
    """Human-readable cohort name for logs."""
    return {
        "synthetic": "Synthetic",
        "macs": "MACS-18",
        "asoca": "ASOCA",
    }[patient_cohort(patient_id)]


def is_macs_patient(patient_id: str) -> bool:
    return patient_cohort(patient_id) == "macs"


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path.resolve()
    return None


def _asoca_mask_candidates(patient_id: str) -> list[Path]:
    pid = str(patient_id).strip()
    if pid.startswith("Normal_"):
        return [
            ASOCA_ROOT / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
            DATA_ROOT / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
        ]
    if pid.startswith("Diseased_"):
        return [
            ASOCA_ROOT / "ASOCA Diseased" / f"{pid}.nrrd",
            DATA_ROOT / "ASOCA Diseased" / f"{pid}.nrrd",
        ]
    return [
        ASOCA_ROOT / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
        ASOCA_ROOT / "ASOCA Diseased" / f"{pid}.nrrd",
        DATA_ROOT / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
        DATA_ROOT / "ASOCA Diseased" / f"{pid}.nrrd",
    ]


def _macs_mask_candidates(patient_id: str) -> list[Path]:
    pid = str(patient_id).strip()
    if pid.startswith("MACS_Normal_"):
        return [MACS_ROOT / "MACS-18 Normal" / f"{pid}.nrrd"]
    if pid.startswith("MACS_Diseased_"):
        return [MACS_ROOT / "MACS-18 Diseased" / f"{pid}.nrrd"]
    return [
        MACS_ROOT / "MACS-18 Normal" / f"{pid}.nrrd",
        MACS_ROOT / "MACS-18 Diseased" / f"{pid}.nrrd",
    ]


def _asoca_label_candidates(patient_id: str) -> list[Path]:
    pid = str(patient_id).strip()
    candidates: list[Path] = []
    if pid.startswith("Normal_"):
        candidates.append(ASOCA_ROOT / "ASOCA Normal Labels" / f"{pid}.nii.gz")
    if pid.startswith("Diseased_"):
        candidates.append(ASOCA_ROOT / "ASOCA Diseased Labels" / f"{pid}.nii.gz")
    candidates.extend(
        [
            DATA_ROOT / "ASOCA Labels" / f"{pid}.nii.gz",
            DATA_ROOT / "ASOCA Normal Labels" / f"{pid}.nii.gz",
            DATA_ROOT / "ASOCA Diseased Labels" / f"{pid}.nii.gz",
        ]
    )
    if not pid.startswith("Normal_") and not pid.startswith("Diseased_"):
        candidates[:0] = [
            ASOCA_ROOT / "ASOCA Normal Labels" / f"{pid}.nii.gz",
            ASOCA_ROOT / "ASOCA Diseased Labels" / f"{pid}.nii.gz",
        ]
    return candidates


def _macs_label_candidates(patient_id: str) -> list[Path]:
    pid = str(patient_id).strip()
    if pid.startswith("MACS_Normal_"):
        return [MACS_ROOT / "MACS-18 Normal Labels" / f"{pid}.nii.gz"]
    if pid.startswith("MACS_Diseased_"):
        return [MACS_ROOT / "MACS-18 Diseased Labels" / f"{pid}.nii.gz"]
    return [
        MACS_ROOT / "MACS-18 Normal Labels" / f"{pid}.nii.gz",
        MACS_ROOT / "MACS-18 Diseased Labels" / f"{pid}.nii.gz",
    ]


def resolve_mask_nrrd_path(patient_id: str) -> Path:
    """Return the segmentation mask ``.nrrd`` for a patient (preferred path if several exist)."""
    pid = str(patient_id).strip()
    cohort = patient_cohort(pid)

    if cohort == "macs" and not MACS_PIPELINE_ENABLED:
        raise RuntimeError(
            f"MACS-18 cohort is disabled (patient_id={pid!r}). "
            "Use ASOCA (e.g. Normal_1) or Synthetic_1, or set MACS_PIPELINE_ENABLED=True in "
            "src/cohort_paths.py for experimental MACS runs."
        )

    if cohort == "synthetic":
        return (SYNTHETIC_DATA_ROOT / f"{pid}.nrrd").resolve()

    candidates = (
        _macs_mask_candidates(pid) if cohort == "macs" else _asoca_mask_candidates(pid)
    )
    found = _first_existing(candidates)
    if found is not None:
        return found
    return candidates[0].resolve()


def resolve_segment_label_path(patient_id: str) -> Path | None:
    """Return SCCT-18 segment label ``.nii.gz`` if present (``None`` for synthetic cases)."""
    pid = str(patient_id).strip()
    if patient_cohort(pid) == "synthetic":
        return None

    if patient_cohort(pid) == "macs" and not MACS_PIPELINE_ENABLED:
        raise RuntimeError(
            f"MACS-18 cohort is disabled (patient_id={pid!r}). "
            "Set MACS_PIPELINE_ENABLED=True in src/cohort_paths.py to resolve MACS labels."
        )

    candidates = (
        _macs_label_candidates(pid)
        if patient_cohort(pid) == "macs"
        else _asoca_label_candidates(pid)
    )
    return _first_existing(candidates)
