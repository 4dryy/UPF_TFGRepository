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
from src.blocks._04_visualization import run_block4
from src.pipeline_log import banner_pipeline, banner_pipeline_done, configure_logging, sub
from src.pipeline_metrics import SamplePipelineMetrics, upsert_sample_metrics
from src.synthetic_profile import is_synthetic_patient, resolve_mask_nrrd_path


def _prompt_patient_id() -> str:
    """Ask the user for a patient ID until a non-empty value is provided."""
    while True:
        pid = input("Enter Patient ID (e.g. Normal_1, Synthetic_1): ").strip()
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
        root / "data" / "ASOCA" / "ASOCA Normal Labels" / f"{patient_id}.nii.gz",
        root / "data" / "ASOCA" / "ASOCA Diseased Labels" / f"{patient_id}.nii.gz",
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return None


def _load_block3():
    blocks_dir = Path(__file__).resolve().parent / "blocks"
    module_path = blocks_dir / "_03_cad-rats.py"
    spec = importlib.util.spec_from_file_location("block3_cadrats", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Block 3 module from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(patient_id: str) -> None:
    configure_logging()
    log = logging.getLogger("pipeline")
    t0_total = time.perf_counter()
    is_synthetic = is_synthetic_patient(patient_id)
    sample_metrics = SamplePipelineMetrics(
        patient_id=patient_id,
        is_synthetic=is_synthetic,
    )

    banner_pipeline(log, patient_id)

    try:
        if is_synthetic:
            sub(log, "Synthetic validation case — single-tube mode (no RCA/LCA split).")
            sub(log, "Synthetic mask: %s", resolve_mask_nrrd_path(patient_id))
        else:
            label_path = _resolve_segment_label_path(patient_id)
            if label_path is None:
                sub(log, "ASOCA label .nii.gz not found — Block 1 uses scout RCA/LCA pairing.")
            else:
                sub(log, "ASOCA labels: %s", label_path)

        t1 = time.perf_counter()
        block1_out = run_block1(
            patient_id=patient_id,
            label_nii_path=None if is_synthetic else _resolve_segment_label_path(patient_id),
            nrrd_path=resolve_mask_nrrd_path(patient_id) if is_synthetic else None,
            is_synthetic=is_synthetic,
        )
        sample_metrics.runtime_block1_s = time.perf_counter() - t1
        sample_metrics.extraction = block1_out.extraction_metrics

        t2 = time.perf_counter()
        run_block2(patient_id=patient_id, is_synthetic=is_synthetic)
        sample_metrics.runtime_block2_s = time.perf_counter() - t2

        block3_mod = _load_block3()
        t3 = time.perf_counter()
        block3_mod.run_block3(patient_id, is_synthetic=is_synthetic)
        sample_metrics.runtime_block3_s = time.perf_counter() - t3

        t4 = time.perf_counter()
        run_block4(patient_id=patient_id, is_synthetic=is_synthetic)
        sample_metrics.runtime_block4_s = time.perf_counter() - t4

        sample_metrics.execution_success = True

    except Exception as exc:
        sample_metrics.execution_success = False
        sample_metrics.error_message = f"{type(exc).__name__}: {exc}"
        log.exception("Pipeline failed for %s", patient_id)
        raise

    finally:
        sample_metrics.runtime_total_s = time.perf_counter() - t0_total
        metrics_path = upsert_sample_metrics(sample_metrics)
        sub(
            log,
            "Metrics saved: %s (success=%s)",
            metrics_path,
            sample_metrics.execution_success,
        )

    banner_pipeline_done(log, patient_id, sample_metrics.runtime_total_s or 0.0)


if __name__ == "__main__":
    main(patient_id=_prompt_patient_id())
