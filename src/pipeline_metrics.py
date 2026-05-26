"""
Pipeline evaluation metrics: per-sample counts and runtimes persisted under ``results/metrics/``.

Each pipeline execution upserts one row in ``pipeline_per_sample.xlsx`` (keyed by ``patient_id``).
Counts are stored as integers so manual ground-truth can be used later to compute rates in the report.
"""

from __future__ import annotations

import sys
import time
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
    "n_block2_cutter_fallback_arteries",
    "block2_cutter_fallback_arteries",
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
    block2_cutter_fallback_arteries: tuple[str, ...] = ()
    """Arteries (RCA, LCA, ...) for which Block 2 used the VTK plane-cut fallback because
    ``vmtkCenterlineSections`` crashed natively. Area values for those arteries are
    approximate (interpolated from a sub-sampled plane-cut, not exact VMTK loop areas)."""
    runtime_block1_s: float | None = None
    runtime_block2_s: float | None = None
    runtime_block3_s: float | None = None
    runtime_block4_s: float | None = None
    runtime_total_s: float | None = None

    def to_row(self) -> dict[str, Any]:
        ex = self.extraction
        ex.finalize_centerline_failures()
        fb = tuple(self.block2_cutter_fallback_arteries)
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
            "n_block2_cutter_fallback_arteries": len(fb),
            "block2_cutter_fallback_arteries": ",".join(fb),
            "runtime_block1_s": self.runtime_block1_s,
            "runtime_block2_s": self.runtime_block2_s,
            "runtime_block3_s": self.runtime_block3_s,
            "runtime_block4_s": self.runtime_block4_s,
            "runtime_total_s": self.runtime_total_s,
        }


_METRICS_WRITE_ATTEMPTS = 5
_METRICS_WRITE_BASE_DELAY_S = 0.5


def _robust_to_excel(df: pd.DataFrame, path: Path) -> bool:
    """Best-effort xlsx write resilient to transient Windows file-handle errors.

    On Windows the metrics workbook is touched on every pipeline run and can
    occasionally collide with OneDrive sync, Cursor's editor preview, Excel,
    or antivirus scanners. Those collisions surface as ``OSError [Errno 22]``
    or ``PermissionError [Errno 13]`` from ``open(...,"w+b")`` even though the
    pipeline itself has succeeded. We retry with exponential backoff and, if
    every attempt still fails, log a single warning and return ``False`` so the
    pipeline can still emit its closing banner cleanly.

    Returns:
        ``True`` if the file was written, ``False`` if all retries failed.
    """
    last_err: BaseException | None = None
    for attempt in range(_METRICS_WRITE_ATTEMPTS):
        try:
            df.to_excel(path, index=False)
            return True
        except (OSError, PermissionError) as exc:
            last_err = exc
            if attempt < _METRICS_WRITE_ATTEMPTS - 1:
                delay = _METRICS_WRITE_BASE_DELAY_S * (2 ** attempt)
                errno = getattr(exc, "errno", "?")
                print(
                    f"   metrics write: {type(exc).__name__} [Errno {errno}] — "
                    f"retrying in {delay:.1f}s "
                    f"({attempt + 1}/{_METRICS_WRITE_ATTEMPTS})",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(delay)
    print(
        f"   WARNING: could not update metrics workbook after "
        f"{_METRICS_WRITE_ATTEMPTS} attempts: {path}  "
        f"({type(last_err).__name__}: {last_err}). "
        f"Pipeline outputs for this sample are unaffected — close the file "
        f"in Cursor/Excel or pause OneDrive sync and re-run if you need the "
        f"audit row.",
        file=sys.stderr,
        flush=True,
    )
    return False


def upsert_sample_metrics(
    metrics: SamplePipelineMetrics,
    *,
    excel_path: Path | None = None,
) -> Path:
    """
    Append or update the row for ``metrics.patient_id`` and rewrite the Excel file.

    All samples (ASOCA and synthetic) share ``results/metrics/pipeline_per_sample.xlsx``.
    The workbook is fully rewritten on each call so all prior samples remain listed.

    The write is performed via :func:`_robust_to_excel`, which transparently
    retries on transient Windows file-handle errors and logs a warning instead
    of raising if every retry fails. ``upsert_sample_metrics`` therefore never
    raises on a write failure: callers always receive the destination ``path``.
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
    _robust_to_excel(out, path)
    return path
