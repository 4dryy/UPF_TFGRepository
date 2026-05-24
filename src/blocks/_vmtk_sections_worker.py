"""
Run ``vmtkCenterlineSections`` in an isolated process (avoids killing the pipeline on access violation).

Usage::
    python -m src.blocks._vmtk_sections_worker <centerline.vtp> <surface.vtp> <out.npz>
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pyvista as pv
from vmtk import vmtkscripts
from vtkmodules.vtkFiltersCore import vtkCleanPolyData, vtkTriangleFilter
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader


def _clean_surface(surface_vtk: object) -> object:
    tri = vtkTriangleFilter()
    tri.SetInputData(surface_vtk)
    tri.PassLinesOff()
    tri.PassVertsOff()
    tri.Update()
    clean = vtkCleanPolyData()
    clean.SetInputData(tri.GetOutput())
    clean.PointMergingOn()
    clean.Update()
    return clean.GetOutput()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        print("usage: vmtk_sections_worker <centerline.vtp> <surface.vtp> <out.npz>", file=sys.stderr)
        return 2

    cl_path, surf_path, out_path = (Path(a) for a in args)

    reader = vtkXMLPolyDataReader()
    reader.SetFileName(str(cl_path))
    reader.Update()
    centerline = reader.GetOutput()
    if centerline is None or centerline.GetNumberOfPoints() < 2:
        print("invalid centerline", file=sys.stderr)
        return 3

    reader.SetFileName(str(surf_path))
    reader.Update()
    surface = reader.GetOutput()
    if surface is None or surface.GetNumberOfPoints() < 3:
        print("invalid surface", file=sys.stderr)
        return 4

    surface = _clean_surface(surface)
    sections = vmtkscripts.vmtkCenterlineSections()
    sections.Surface = surface
    sections.Centerlines = centerline
    sections.Execute()

    out_cl = pv.wrap(sections.Centerlines)
    if "CenterlineSectionArea" not in out_cl.point_data:
        print("missing CenterlineSectionArea", file=sys.stderr)
        return 5

    area = np.asarray(out_cl.point_data["CenterlineSectionArea"], dtype=float).copy()
    if "CenterlineSectionClosed" in out_cl.point_data:
        closed = np.asarray(out_cl.point_data["CenterlineSectionClosed"], dtype=float)
        area[closed < 0.5] = np.nan
    area[~np.isfinite(area)] = np.nan
    area[area <= 0.0] = np.nan
    pts = np.asarray(out_cl.points, dtype=float)
    np.savez_compressed(out_path, points=pts, area=area)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
