"""
Driver: runs _diag_block2_steps_worker.py as a child process for every
(patient, artery) pair so a native VMTK / VTK access-violation in the child
does NOT kill the driver. Reports per-artery PASS/CRASH and the exact last
step the child reached before dying.

Run from the project root:

    python _diag_block2_crash.py                # auto-runs reported crash list
                                                  vs control samples
    python _diag_block2_crash.py Normal_5       # one patient (both arteries)
    python _diag_block2_crash.py --all          # every block1_results/* folder

Output columns:
    <patient>  <artery>  <result>  last_step="..."  (sections=N if survived)

Result legend:
    PASS               - vmtkCenterlineSections completed
    CRASH(exit=N)      - child died; on Windows exit=3221225477 is
                          STATUS_ACCESS_VIOLATION (the silent native fault)
    TIMEOUT            - child stuck >900 s (also a likely native hang)
    PY_ERR             - child raised a Python exception (will print traceback)
    NO_FILES           - patient folder is missing centerline/surface VTPs
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "block1_results"
WORKER = ROOT / "_diag_block2_steps_worker.py"
TIMEOUT_S = 900

CRASHING = [
    "Normal_5", "Normal_14", "Normal_16", "Normal_17",
    "Diseased_2", "Diseased_3", "Diseased_5", "Diseased_12",
    "Diseased_14", "Diseased_16",
]


def last_step_line(stdout: str) -> str:
    """Return the last non-empty line written by the worker."""
    if not stdout:
        return ""
    lines = [ln.rstrip() for ln in stdout.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def run_one(patient: str, artery: str) -> tuple[str, str, str]:
    cmd = [sys.executable, str(WORKER), patient, artery]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired as e:
        return "TIMEOUT", "", last_step_line(e.stdout or "")

    last = last_step_line(proc.stdout)
    if proc.returncode == 0:
        return "PASS", proc.stderr, last
    if proc.returncode in (3, 4):
        return "NO_FILES", proc.stderr, last
    if proc.returncode == 9:
        return "PY_ERR", proc.stderr, last
    return f"CRASH(exit={proc.returncode})", proc.stderr, last


def fmt_row(patient: str, artery: str, status: str, last: str) -> str:
    return f"{patient:14s} {artery:3s}  {status:18s}  last={last}"


def driver_main() -> int:
    argv = sys.argv[1:]
    if "--all" in argv:
        argv.remove("--all")
        targets = sorted(p.name for p in RESULTS.iterdir() if p.is_dir())
    elif argv:
        targets = argv
    else:
        found = sorted(p.name for p in RESULTS.iterdir() if p.is_dir())
        crashing = [p for p in CRASHING if p in found]
        controls = [p for p in found if p not in CRASHING and not p.startswith("Synthetic")]
        targets = crashing + ["---CONTROLS---"] + controls

    py_errs: list[tuple[str, str, str]] = []
    print("=" * 110)
    print("BLOCK 2 SUBPROCESS-ISOLATED CRASH TEST")
    print("(child = _diag_block2_steps_worker.py; if it native-crashes, exit code != 0)")
    print("=" * 110)
    for t in targets:
        if t == "---CONTROLS---":
            print()
            print("# --- CONTROLS (samples not on your reported crash list) ---")
            continue
        for art in ("RCA", "LCA"):
            status, stderr, last = run_one(t, art)
            print(fmt_row(t, art, status, last), flush=True)
            if status == "PY_ERR":
                py_errs.append((t, art, stderr))
    if py_errs:
        print()
        print("=" * 110)
        print("Python tracebacks collected from PY_ERR runs:")
        print("=" * 110)
        for pid, art, tb in py_errs:
            print(f"\n--- {pid} {art} ---")
            print(tb)
    return 0


if __name__ == "__main__":
    raise SystemExit(driver_main())
