"""
Sequential batch runner for the coronary CAD-RADS pipeline.

Runs ``python -m src._pipeline --patient <id> --no-streamlit`` once per patient,
each in its own subprocess so that:

* a native crash on one sample (e.g. the rare ``vmtkCenterlineSections``
  fault on Windows) cannot abort the rest of the batch,
* VTK / VMTK heap state and Python memory are fully reclaimed between samples
  (each run starts from a fresh interpreter, exactly as if the user had
  typed the patient ID manually),
* the per-sample metrics workbook is rewritten between samples just like in a
  manual sequence of runs.

Typical usage from the repo root (with the ``tfg_adria`` conda environment active):

    # All 40 MACS-18 samples (re-annotated higher-precision cohort)::
    python scripts/run_batch.py --cohort macs

    # Subset (only the diseased half of MACS-18)::
    python scripts/run_batch.py --cohort macs --include diseased

    # All 40 ASOCA samples::
    python scripts/run_batch.py --cohort asoca

    # Both synthetic validation phantoms::
    python scripts/run_batch.py --cohort synthetic

    # An explicit list (any cohort, any prefix)::
    python scripts/run_batch.py --patients MACS_Normal_1 MACS_Diseased_3 Normal_2

    # Resume an interrupted batch (skip patients whose last run succeeded)::
    python scripts/run_batch.py --cohort macs --skip-existing

    # Force a full re-run (ignore the metrics workbook)::
    python scripts/run_batch.py --cohort macs --no-skip-existing

A timestamped batch log is written to ``results/metrics/batch_<YYYYmmdd_HHMMSS>.log``
recording, for each sample, exit status and wall time. The pipeline still updates the
shared ``results/metrics/pipeline_per_sample.xlsx`` workbook on every run, exactly as
in interactive mode, so all sample-level analysis (CAD-RADS, fallback usage, etc.)
remains in one place.

The Streamlit dashboard is **disabled** during the batch (``--no-streamlit``) so the
40 runs do not open 40 browser tabs. After the batch finishes, the last patient's
session is in ``results/current_session.json``; either re-run the pipeline manually
with that patient ID for the dashboard, or pick any sample from the metrics workbook
and run the pipeline interactively to inspect it.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Importing from src ensures the runner uses the same cohort path map as the pipeline.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cohort_paths import (  # noqa: E402  (import after sys.path tweak)
    ASOCA_ROOT,
    MACS_ROOT,
    MACS_PIPELINE_ENABLED,
    SYNTHETIC_DATA_ROOT,
    resolve_mask_nrrd_path,
)

DEFAULT_METRICS_XLSX = PROJECT_ROOT / "results" / "metrics" / "pipeline_per_sample.xlsx"
BATCH_LOG_DIR = PROJECT_ROOT / "results" / "metrics"
BLOCK1_RESULTS_ROOT = PROJECT_ROOT / "results" / "block1_results"

# Match the trailing integer in IDs so we sort Normal_2 before Normal_10.
_TRAILING_INT = re.compile(r"(\d+)$")


def _numeric_key(patient_id: str) -> tuple[int, str]:
    m = _TRAILING_INT.search(patient_id)
    if m is None:
        return (10**9, patient_id)
    return (int(m.group(1)), patient_id)


def _discover_macs_patients() -> list[str]:
    """Scan ``data/MACS-18/MACS-18 {Normal,Diseased}/MACS_*.nrrd`` for available IDs."""
    out: list[str] = []
    for sub in ("MACS-18 Normal", "MACS-18 Diseased"):
        folder = MACS_ROOT / sub
        if not folder.is_dir():
            continue
        for p in folder.glob("MACS_*.nrrd"):
            out.append(p.stem)
    return sorted(set(out), key=_numeric_key)


def _discover_asoca_patients() -> list[str]:
    """Scan the ASOCA folder layout for available patient IDs."""
    out: list[str] = []
    normal_dir = ASOCA_ROOT / "ASOCA Normal" / "Annotations"
    diseased_dir = ASOCA_ROOT / "ASOCA Diseased"
    for folder, expected_prefix in (
        (normal_dir, "Normal_"),
        (diseased_dir, "Diseased_"),
    ):
        if not folder.is_dir():
            continue
        for p in folder.glob(f"{expected_prefix}*.nrrd"):
            out.append(p.stem)
    return sorted(set(out), key=_numeric_key)


def _discover_synthetic_patients() -> list[str]:
    """Scan ``data/Synthetic Samples/Synthetic_*.nrrd`` for validation phantoms."""
    if not SYNTHETIC_DATA_ROOT.is_dir():
        return []
    return sorted(
        {p.stem for p in SYNTHETIC_DATA_ROOT.glob("Synthetic_*.nrrd")},
        key=_numeric_key,
    )


def _has_block1_artifacts(patient_id: str) -> bool:
    """Return True if Block 1 outputs for this patient still exist on disk."""
    sample_dir = BLOCK1_RESULTS_ROOT / patient_id
    return (sample_dir / f"dataset_global_{patient_id}.xlsx").is_file()


def _filter_include(patient_ids: list[str], include: str | None) -> list[str]:
    """Apply the ``--include`` filter (``normal`` / ``diseased`` / ``all``)."""
    if include in (None, "all"):
        return patient_ids
    needle = include.lower()
    if needle == "normal":
        return [pid for pid in patient_ids if "Normal_" in pid]
    if needle == "diseased":
        return [pid for pid in patient_ids if "Diseased_" in pid]
    raise SystemExit(f"--include must be one of 'normal', 'diseased', 'all' (got {include!r})")


def _load_successful_ids(metrics_xlsx: Path) -> set[str]:
    """Return the set of ``patient_id`` values whose last recorded run succeeded.

    Returns an empty set if the workbook does not exist or pandas is unavailable.
    """
    if not metrics_xlsx.is_file():
        return set()
    try:
        import pandas as pd  # local import: pandas may take 1-2 s to load on Windows
    except Exception:
        return set()
    try:
        df = pd.read_excel(metrics_xlsx)
    except Exception:
        return set()
    if "patient_id" not in df.columns or "execution_success" not in df.columns:
        return set()
    df["execution_success"] = df["execution_success"].astype(str).str.lower().isin({"true", "1", "yes"})
    return set(df.loc[df["execution_success"], "patient_id"].astype(str).str.strip())


@dataclass
class _RunResult:
    patient_id: str
    returncode: int
    elapsed_s: float
    skipped: bool = False

    @property
    def status(self) -> str:
        if self.skipped:
            return "SKIP"
        return "OK" if self.returncode == 0 else f"FAIL({self.returncode})"


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:5.1f}s"
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes:>3d}m{secs:02d}s"


def _build_pipeline_command(patient_id: str) -> list[str]:
    """Command used to launch one pipeline run as a child Python process."""
    return [
        sys.executable,
        "-m",
        "src._pipeline",
        "--patient",
        patient_id,
        "--no-streamlit",
    ]


def _run_one(
    patient_id: str,
    *,
    log_handle,
    index: int,
    total: int,
) -> _RunResult:
    """Execute the pipeline for one patient and stream output to the parent terminal."""
    banner = f"[{index}/{total}] {patient_id}"
    bar = "=" * max(40, len(banner) + 6)
    print(f"\n{bar}\n  {banner}\n{bar}\n", flush=True)
    log_handle.write(f"\n{bar}\n  {banner}\n{bar}\n")
    log_handle.flush()

    cmd = _build_pipeline_command(patient_id)
    print("  $ " + " ".join(cmd), flush=True)
    log_handle.write("  $ " + " ".join(cmd) + "\n")
    log_handle.flush()

    t0 = time.perf_counter()
    try:
        # Stdout/stderr inherited so the user sees live block-by-block progress.
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            check=False,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        rc = int(proc.returncode)
    except KeyboardInterrupt:
        elapsed = time.perf_counter() - t0
        log_handle.write(
            f"  patient={patient_id}  ABORTED by user (KeyboardInterrupt) after {_format_elapsed(elapsed)}\n"
        )
        log_handle.flush()
        raise
    elapsed = time.perf_counter() - t0
    line = f"  patient={patient_id}  exit={rc}  elapsed={_format_elapsed(elapsed)}\n"
    print(line, end="", flush=True)
    log_handle.write(line)
    log_handle.flush()
    return _RunResult(patient_id=patient_id, returncode=rc, elapsed_s=elapsed)


def _print_summary(results: list[_RunResult], log_handle) -> None:
    total = len(results)
    n_ok = sum(r.returncode == 0 and not r.skipped for r in results)
    n_skipped = sum(r.skipped for r in results)
    n_fail = total - n_ok - n_skipped

    bar = "=" * 70
    summary_lines = [
        bar,
        f"  BATCH SUMMARY  |  total={total}  ok={n_ok}  failed={n_fail}  skipped={n_skipped}",
        bar,
    ]
    for r in results:
        summary_lines.append(
            f"  {r.status:<10s}  {r.patient_id:<20s}  {_format_elapsed(r.elapsed_s)}"
        )
    summary_lines.append(bar)
    text = "\n".join(summary_lines) + "\n"
    print(text, flush=True)
    log_handle.write(text)
    log_handle.flush()


def _resolve_patient_list(args: argparse.Namespace) -> list[str]:
    if args.patients:
        return [pid.strip() for pid in args.patients if pid.strip()]
    if args.cohort == "macs":
        if not MACS_PIPELINE_ENABLED:
            raise SystemExit(
                "MACS_PIPELINE_ENABLED is False in src/cohort_paths.py — set it to True before "
                "batching MACS-18 (this should already be the case after the MACS-18 enablement patch)."
            )
        ids = _discover_macs_patients()
    elif args.cohort == "asoca":
        ids = _discover_asoca_patients()
    elif args.cohort == "synthetic":
        ids = _discover_synthetic_patients()
    elif args.cohort == "all":
        ids = (
            _discover_asoca_patients()
            + _discover_macs_patients()
            + _discover_synthetic_patients()
        )
    else:
        raise SystemExit(f"Unknown --cohort value: {args.cohort!r}")
    return _filter_include(ids, args.include)


def _check_inputs_exist(patient_ids: list[str]) -> list[str]:
    """Raise SystemExit if any patient ID has no readable mask file on disk."""
    missing: list[tuple[str, Path]] = []
    for pid in patient_ids:
        try:
            mask = resolve_mask_nrrd_path(pid)
        except Exception as exc:  # cohort gate raised RuntimeError
            missing.append((pid, Path(str(exc))))
            continue
        if not mask.exists():
            missing.append((pid, mask))
    if missing:
        lines = ["Cannot find input masks for the following patients:"]
        for pid, p in missing:
            lines.append(f"  - {pid}: {p}")
        lines.append(
            "Either copy the missing files into place, drop those IDs from the batch, "
            "or pass an explicit --patients list."
        )
        raise SystemExit("\n".join(lines))
    return patient_ids


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python scripts/run_batch.py",
        description="Run the full pipeline for many patients sequentially, "
        "each in its own subprocess.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--cohort",
        choices=("asoca", "macs", "synthetic", "all"),
        help="Auto-discover all available patients of the chosen cohort under data/.",
    )
    src.add_argument(
        "--patients",
        nargs="+",
        metavar="PATIENT_ID",
        help="Explicit list of patient IDs (Normal_1, MACS_Normal_3, Synthetic_1, ...).",
    )
    parser.add_argument(
        "--include",
        choices=("all", "normal", "diseased"),
        default="all",
        help="When using --cohort, restrict to the Normal- or Diseased-prefixed half. "
        "Ignored when --patients is used. Default: all.",
    )
    parser.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        default=True,
        help="Skip patients that already have execution_success=True in "
        "results/metrics/pipeline_per_sample.xlsx AND still have Block 1 outputs "
        "under results/block1_results/<patient_id>/. Default: ON. If you deleted "
        "results/ but kept the metrics workbook, those patients are re-run automatically.",
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Force re-run even if a previous run succeeded. Overwrites the audit row.",
    )
    parser.add_argument(
        "--metrics-xlsx",
        type=Path,
        default=DEFAULT_METRICS_XLSX,
        help=f"Path to the metrics workbook used for skip-existing checks "
        f"(default: {DEFAULT_METRICS_XLSX}).",
    )
    parser.add_argument(
        "--no-streamlit",
        action="store_true",
        default=False,
        help="Compatibility flag accepted for convenience. Batch mode already forces "
        "`python -m src._pipeline --no-streamlit` for every sample.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    patient_ids = _resolve_patient_list(args)
    if not patient_ids:
        raise SystemExit(
            "No patient IDs to run. Either no files matched on disk, or --include filtered "
            "everything out."
        )
    patient_ids = _check_inputs_exist(patient_ids)

    successful_ids = _load_successful_ids(args.metrics_xlsx) if args.skip_existing else set()
    queued: list[str] = []
    pre_skipped: list[_RunResult] = []
    for pid in patient_ids:
        if pid in successful_ids and _has_block1_artifacts(pid):
            pre_skipped.append(
                _RunResult(patient_id=pid, returncode=0, elapsed_s=0.0, skipped=True)
            )
        else:
            queued.append(pid)

    BATCH_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = BATCH_LOG_DIR / f"batch_{stamp}.log"

    print(
        f"Batch runner: {len(patient_ids)} requested · {len(pre_skipped)} skipped (already OK) · "
        f"{len(queued)} to run\n  log: {log_path}",
        flush=True,
    )
    if not queued:
        print("Nothing to run. Use --no-skip-existing to force re-runs.", flush=True)
        return 0

    results: list[_RunResult] = list(pre_skipped)
    t_batch = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log_handle:
        log_handle.write(
            f"Batch runner started at {datetime.now(timezone.utc).isoformat()} (UTC)\n"
            f"Project root: {PROJECT_ROOT}\n"
            f"Python: {sys.executable}\n"
            f"Skip existing: {args.skip_existing}  Cohort: {args.cohort}  "
            f"Include: {args.include}\n"
            f"Pre-skipped (already OK): {[r.patient_id for r in pre_skipped]}\n"
            f"Queued ({len(queued)}): {queued}\n"
        )
        log_handle.flush()

        try:
            for i, pid in enumerate(queued, start=1):
                results.append(
                    _run_one(pid, log_handle=log_handle, index=i, total=len(queued))
                )
        except KeyboardInterrupt:
            print(
                "\nBatch interrupted by user. Partial results are in the metrics workbook; "
                "re-run with --skip-existing to resume from where you stopped.",
                flush=True,
            )
            log_handle.write("\nBatch interrupted by KeyboardInterrupt.\n")

        total_elapsed = time.perf_counter() - t_batch
        log_handle.write(f"\nTotal batch elapsed: {_format_elapsed(total_elapsed)}\n")
        _print_summary(results, log_handle)

    print(f"\nBatch log: {log_path}", flush=True)

    n_fail = sum(r.returncode != 0 and not r.skipped for r in results)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
