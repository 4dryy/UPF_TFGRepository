"""
Worker process: reproduces Block 2's pre-section pipeline for ONE (patient, artery)
pair so the parent can detect native VTK/VMTK crashes via the child's exit code.

Steps mirror src/blocks/_02_stenosis.py run_block2() lines 1075-1102:
    1. Read centerline_<artery>.vtp
    2. vmtkCenterlineSmoothing
    3. vmtkCenterlineResampling (fixed 0.1 mm — same as the default ASOCA path)
    4. Read surface_<artery>.vtp
    5. vtkTriangleFilter + vtkCleanPolyData
    6. vmtkCenterlineSections.Execute()   <-- the most likely native crash

Each step prints "STEP n start" then "STEP n ok" with stdout flushed. If the
process dies natively, the parent's tail line will be "STEP n start" with no
matching "ok" — that tells us exactly which step killed it.

Invocation:
    python _diag_block2_steps_worker.py <patient_id> <RCA|LCA>

Exit codes:
    0  = ALL_OK (full pipeline up to and including vmtkCenterlineSections)
    2  = bad arguments
    3  = missing centerline file
    4  = missing surface file
    5..9 = step-specific Python exception (raised, not native crash)
    other (typically 3221225477 on Windows = STATUS_ACCESS_VIOLATION) = native crash
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent / "results" / "block1_results"


def log(msg: str) -> None:
    print(msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: _diag_block2_steps_worker.py <patient_id> <RCA|LCA>", file=sys.stderr)
        return 2
    patient, artery = args
    pdir = ROOT / patient
    cl_path = pdir / f"centerline_{artery}.vtp"
    sf_path = pdir / f"surface_{artery}.vtp"
    if not cl_path.is_file():
        log(f"MISSING_CL {cl_path}")
        return 3
    if not sf_path.is_file():
        log(f"MISSING_SURF {sf_path}")
        return 4

    log(f"PATIENT={patient} ARTERY={artery}")

    # ----- Step 1: read centerline VTP -----
    log("STEP 1 start: read centerline VTP")
    from vtkmodules.vtkIOXML import vtkXMLPolyDataReader

    rd = vtkXMLPolyDataReader()
    rd.SetFileName(str(cl_path))
    rd.Update()
    cl = rd.GetOutput()
    if cl is None or cl.GetNumberOfPoints() < 2:
        log("STEP 1 FAIL: invalid centerline")
        return 5
    log(f"STEP 1 ok: n_pts={cl.GetNumberOfPoints()} n_cells={cl.GetNumberOfCells()}")

    # ----- Step 2: vmtkCenterlineSmoothing -----
    log("STEP 2 start: vmtkCenterlineSmoothing (factor=0.15, iters=20)")
    from vmtk import vmtkscripts

    smooth = vmtkscripts.vmtkCenterlineSmoothing()
    smooth.Centerlines = cl
    smooth.SmoothingFactor = 0.15
    smooth.NumberOfSmoothingIterations = 20
    smooth.Execute()
    log(f"STEP 2 ok: n_pts={smooth.Centerlines.GetNumberOfPoints()}")

    # ----- Step 3: vmtkCenterlineResampling at fixed 0.1 mm -----
    log("STEP 3 start: vmtkCenterlineResampling step=0.1 mm")
    res = vmtkscripts.vmtkCenterlineResampling()
    res.Centerlines = smooth.Centerlines
    res.Length = 0.1
    res.Execute()
    n_resampled = res.Centerlines.GetNumberOfPoints()
    log(f"STEP 3 ok: n_pts={n_resampled}")

    # ----- Step 4: read surface VTP -----
    log("STEP 4 start: read surface VTP")
    rd2 = vtkXMLPolyDataReader()
    rd2.SetFileName(str(sf_path))
    rd2.Update()
    surf = rd2.GetOutput()
    if surf is None or surf.GetNumberOfPoints() < 3:
        log("STEP 4 FAIL: invalid surface")
        return 6
    log(f"STEP 4 ok: n_pts={surf.GetNumberOfPoints()} n_cells={surf.GetNumberOfCells()}")

    # ----- Step 5: clean + triangulate surface -----
    log("STEP 5 start: vtkTriangleFilter + vtkCleanPolyData")
    from vtkmodules.vtkFiltersCore import vtkCleanPolyData, vtkTriangleFilter

    tri = vtkTriangleFilter()
    tri.SetInputData(surf)
    tri.PassLinesOff()
    tri.PassVertsOff()
    tri.Update()
    clean = vtkCleanPolyData()
    clean.SetInputConnection(tri.GetOutputPort())
    clean.ConvertLinesToPointsOff()
    clean.ConvertPolysToLinesOff()
    clean.PointMergingOn()
    clean.Update()
    surf_clean = clean.GetOutput()
    log(f"STEP 5 ok: n_pts={surf_clean.GetNumberOfPoints()} n_cells={surf_clean.GetNumberOfCells()}")

    # ----- Step 6: vmtkCenterlineSections (the suspect call) -----
    log("STEP 6 start: vmtkCenterlineSections.Execute()  <-- THIS IS THE SUSPECT")
    sections = vmtkscripts.vmtkCenterlineSections()
    sections.Surface = surf_clean
    sections.Centerlines = res.Centerlines
    sections.Execute()

    import pyvista as pv

    out_cl = pv.wrap(sections.Centerlines)
    if "CenterlineSectionArea" not in out_cl.point_data:
        log("STEP 6 FAIL: CenterlineSectionArea missing")
        return 7
    area = np.asarray(out_cl.point_data["CenterlineSectionArea"], dtype=float)
    finite = np.isfinite(area)
    n_valid = int(np.count_nonzero(finite))
    rng = (
        f"[{float(np.nanmin(area[finite])):.3f},{float(np.nanmax(area[finite])):.3f}]"
        if n_valid
        else "n/a"
    )
    log(f"STEP 6 ok: n_sections={len(area)} valid={n_valid} area_mm2={rng}")

    log("ALL_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(9)
