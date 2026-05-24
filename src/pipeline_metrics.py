"""
Pipeline evaluation metrics: per-sample counts and runtimes persisted under ``results/metrics/``.

Each pipeline execution upserts one row in ``pipeline_per_sample.xlsx`` (keyed by ``patient_id``).
Counts are stored as integers so manual ground-truth can be used later to compute rates in the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = PROJECT_ROOT / "results" / "metrics"
DEFAULT_METRICS_XLSX = METRICS_DIR / "pipeline_per_sample.xlsx"

PIPELINE_METRICS_COLUMNS: list[str] = [
    "patient_id",
    "executed_at_utc",
    "is_synthetic",
    "execution_success",
    "error_message",
    "n_endpoints_detected",
    "n_ostiums_identified",
    "n_centerline_paths_attempted",
    "n_centerline_paths_success",
    "n_centerline_paths_failed",
    "runtime_block1_s",
    "runtime_block2_s",
    "runtime_block3_s",
    "runtime_block4_s",
    "runtime_total_s",
]


@dataclass
class Block1ExtractionMetrics:
    """Counts gathered during Block 1 (hybrid scout + VMTK + branch packaging)."""

    n_endpoints_detected: int = 0
    n_ostiums_identified: int = 0
    n_centerline_paths_attempted: int = 0
    n_centerline_paths_success: int = 0
    n_centerline_paths_failed: int = 0

    def finalize_centerline_failures(self) -> None:
        """Set failed path count from attempted minus successful extractions."""
        self.n_centerline_paths_failed = max(
            0,
            int(self.n_centerline_paths_attempted) - int(self.n_centerline_paths_success),
        )


@dataclass
class SamplePipelineMetrics:
    """One row of pipeline evaluation data for a single patient run."""

    patient_id: str
    execution_success: bool = False
    is_synthetic: bool = False
    error_message: str = ""
    executed_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    extraction: Block1ExtractionMetrics = field(default_factory=Block1ExtractionMetrics)
    runtime_block1_s: float | None = None
    runtime_block2_s: float | None = None
    runtime_block3_s: float | None = None
    runtime_block4_s: float | None = None
    runtime_total_s: float | None = None

    def to_row(self) -> dict[str, Any]:
        ex = self.extraction
        ex.finalize_centerline_failures()
        return {
            "patient_id": self.patient_id,
            "executed_at_utc": self.executed_at_utc,
            "is_synthetic": bool(self.is_synthetic),
            "execution_success": bool(self.execution_success),
            "error_message": self.error_message or "",
            "n_endpoints_detected": int(ex.n_endpoints_detected),
            "n_ostiums_identified": int(ex.n_ostiums_identified),
            "n_centerline_paths_attempted": int(ex.n_centerline_paths_attempted),
            "n_centerline_paths_success": int(ex.n_centerline_paths_success),
            "n_centerline_paths_failed": int(ex.n_centerline_paths_failed),
            "runtime_block1_s": self.runtime_block1_s,
            "runtime_block2_s": self.runtime_block2_s,
            "runtime_block3_s": self.runtime_block3_s,
            "runtime_block4_s": self.runtime_block4_s,
            "runtime_total_s": self.runtime_total_s,
        }


def upsert_sample_metrics(
    metrics: SamplePipelineMetrics,
    *,
    excel_path: Path | None = None,
) -> Path:
    """
    Append or update the row for ``metrics.patient_id`` and rewrite the Excel file.

    All samples (ASOCA and synthetic) share ``results/metrics/pipeline_per_sample.xlsx``.
    The workbook is fully rewritten on each call so all prior samples remain listed.
    """
    path = excel_path or DEFAULT_METRICS_XLSX
    path.parent.mkdir(parents=True, exist_ok=True)

    row = metrics.to_row()
    new_df = pd.DataFrame([row], columns=PIPELINE_METRICS_COLUMNS)

    if path.is_file():
        try:
            existing = pd.read_excel(path)
        except Exception:
            existing = pd.DataFrame(columns=PIPELINE_METRICS_COLUMNS)
        for col in PIPELINE_METRICS_COLUMNS:
            if col not in existing.columns:
                existing[col] = pd.NA
        existing = existing[PIPELINE_METRICS_COLUMNS]
        existing = existing[existing["patient_id"].astype(str) != str(metrics.patient_id)]
        out = pd.concat([existing, new_df], ignore_index=True)
    else:
        out = new_df

    out = out.sort_values("patient_id").reset_index(drop=True)
    out.to_excel(path, index=False)
    return path
