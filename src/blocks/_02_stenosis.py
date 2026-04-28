"""
Block 2 — Geometric stenosis (phase 1): sectional area extraction.

This block reads Block 1 packaged outputs, computes per-point cross-sectional
area for full RCA/LCA centerlines with VMTK, propagates area values to global,
artery and branch dataframes, and exports an area package for downstream phases.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv
import scipy.ndimage as ndi
from scipy.spatial import cKDTree
from vmtk import vmtkscripts
from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader
from vtkmodules.vtkFiltersCore import vtkTriangleFilter
from vtkmodules.vtkFiltersCore import vtkCleanPolyData

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
BLOCK1_SAMPLES_DIR = PROJECT_ROOT / "results" / "block1_results" / "samples"
BLOCK2_AREA_SAMPLES_DIR = PROJECT_ROOT / "results" / "block2_results" / "area" / "samples"


def _sample_numeric_id(patient_id: str) -> int:
    tail = patient_id.split("_")[-1]
    return int(tail) if tail.isdigit() else -1


def _numpy_to_vtk_image(array_zyx: np.ndarray, spacing: np.ndarray, origin: np.ndarray) -> vtkImageData:
    nz, ny, nx = array_zyx.shape
    vtk_img = vtkImageData()
    vtk_img.SetDimensions(nx, ny, nz)
    vtk_img.SetSpacing(float(spacing[0]), float(spacing[1]), float(spacing[2]))
    vtk_img.SetOrigin(float(origin[0]), float(origin[1]), float(origin[2]))
    flat = np.ascontiguousarray(array_zyx.flatten(), dtype=np.float64)
    vtk_arr = numpy_to_vtk(flat)
    vtk_arr.SetName("ImageScalars")
    vtk_img.GetPointData().SetScalars(vtk_arr)
    return vtk_img


def _load_and_separate_mask(nrrd_path: Path) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    reader = vmtkscripts.vmtkImageReader()
    reader.InputFileName = str(nrrd_path)
    reader.Execute()

    vtk_image = reader.Image
    spacing = np.array(vtk_image.GetSpacing())
    origin = np.array(vtk_image.GetOrigin())
    dims = vtk_image.GetDimensions()
    vtk_scalars = vtk_image.GetPointData().GetScalars()
    mask = vtk_to_numpy(vtk_scalars).reshape(dims[2], dims[1], dims[0]).astype(np.uint8)

    labeled, num_components = ndi.label(mask)
    if num_components < 2:
        raise RuntimeError(f"Expected at least 2 connected components, found {num_components}")

    component_sizes = ndi.sum(mask, labeled, range(1, num_components + 1))
    sorted_labels = np.argsort(component_sizes)[::-1] + 1
    label_a, label_b = sorted_labels[0], sorted_labels[1]

    com_a = ndi.center_of_mass(mask, labeled, label_a)
    com_b = ndi.center_of_mass(mask, labeled, label_b)
    phys_x_a = origin[0] + com_a[2] * spacing[0]
    phys_x_b = origin[0] + com_b[2] * spacing[0]

    if phys_x_a < phys_x_b:
        rca_label, lca_label = label_a, label_b
    else:
        rca_label, lca_label = label_b, label_a

    artery_arrays = {
        "RCA": (labeled == rca_label).astype(np.uint8),
        "LCA": (labeled == lca_label).astype(np.uint8),
    }
    return artery_arrays, spacing, origin


def _build_surface_from_mask(
    artery_mask: np.ndarray,
    spacing: np.ndarray,
    origin: np.ndarray,
) -> tuple[object, pv.PolyData]:
    vtk_artery = _numpy_to_vtk_image(artery_mask, spacing, origin)
    mc = vmtkscripts.vmtkMarchingCubes()
    mc.Image = vtk_artery
    mc.Level = 0.5
    mc.Execute()

    smoother = vmtkscripts.vmtkSurfaceSmoothing()
    smoother.Surface = mc.Surface
    smoother.NumberOfIterations = 20
    smoother.PassBand = 0.1
    smoother.Execute()
    return smoother.Surface, pv.wrap(smoother.Surface)


def _read_vtp_as_vtk(vtp_path: Path) -> object:
    reader = vtkXMLPolyDataReader()
    reader.SetFileName(str(vtp_path))
    reader.Update()
    out = reader.GetOutput()
    if out is None or out.GetNumberOfPoints() == 0:
        raise RuntimeError(f"Failed to read centerline polydata: {vtp_path}")
    return out


def _load_surfaces_from_block1(block1_dir: Path) -> tuple[dict[str, object], dict[str, pv.PolyData]]:
    """Load persisted artery surfaces from Block 1 package when available."""
    out_vtk: dict[str, object] = {}
    out_pv: dict[str, pv.PolyData] = {}
    for artery in ("RCA", "LCA"):
        p = block1_dir / f"surface_{artery}.vtp"
        if not p.exists():
            continue
        out_vtk[artery] = _read_vtp_as_vtk(p)
        out_pv[artery] = pv.read(str(p))
    return out_vtk, out_pv


def _compute_centerline_area(centerline_vtk: object, surface_vtk: object) -> np.ndarray:
    sections = vmtkscripts.vmtkCenterlineSections()
    sections.Surface = surface_vtk
    sections.Centerlines = centerline_vtk
    sections.Execute()

    out_cl = pv.wrap(sections.Centerlines)
    pd_arrays = out_cl.point_data
    if "CenterlineSectionArea" not in pd_arrays:
        raise RuntimeError("vmtkCenterlineSections missing CenterlineSectionArea array")

    area = np.asarray(pd_arrays["CenterlineSectionArea"], dtype=float).copy()
    if "CenterlineSectionClosed" in pd_arrays:
        closed = np.asarray(pd_arrays["CenterlineSectionClosed"], dtype=float)
        area[closed < 0.5] = np.nan
    area[~np.isfinite(area)] = np.nan
    area[area <= 0.0] = np.nan
    return area


def _clean_triangulate_surface(surface_vtk: object) -> object:
    tri = vtkTriangleFilter()
    tri.SetInputData(surface_vtk)
    tri.PassLinesOff()
    tri.PassVertsOff()
    tri.Update()

    clean = vtkCleanPolyData()
    clean.SetInputConnection(tri.GetOutputPort())
    clean.ConvertLinesToPointsOff()
    clean.ConvertPolysToLinesOff()
    clean.PointMergingOn()
    clean.Update()
    return clean.GetOutput()


def _prepare_centerline_for_sections(
    centerlines_vtk: object,
    resample_step: float = 0.1,
    smoothing_factor: float = 0.15,
    iterations: int = 20,
) -> object:
    smooth = vmtkscripts.vmtkCenterlineSmoothing()
    smooth.Centerlines = centerlines_vtk
    smooth.SmoothingFactor = float(smoothing_factor)
    smooth.NumberOfSmoothingIterations = int(iterations)
    smooth.Execute()

    resample = vmtkscripts.vmtkCenterlineResampling()
    resample.Centerlines = smooth.Centerlines
    resample.Length = float(resample_step)
    resample.Execute()
    return resample.Centerlines


def _map_area_to_df(df: pd.DataFrame, ref_points: np.ndarray, ref_area: np.ndarray) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    pts = out[["Px", "Py", "Pz"]].to_numpy(dtype=float)

    if len(out) == len(ref_points) and np.allclose(pts, ref_points, atol=1e-6):
        out["Area"] = ref_area
        return out, "row_aligned"

    tree = cKDTree(ref_points)
    _, idx = tree.query(pts, k=1)
    out["Area"] = ref_area[np.asarray(idx, dtype=int)]
    return out, "kdtree"


def _save_area_plot(
    points_xyz: np.ndarray,
    area: np.ndarray,
    out_path: Path,
    title: str,
    mesh: pv.PolyData | None = None,
) -> None:
    if len(points_xyz) == 0:
        return

    cloud = pv.PolyData(points_xyz)
    cloud["Area"] = np.asarray(area, dtype=float)
    finite = np.isfinite(cloud["Area"])
    if finite.any():
        q1, q99 = np.nanpercentile(cloud["Area"][finite], [1, 99])
        clim = (float(q1), float(q99)) if q99 > q1 else None
    else:
        clim = None

    pl = pv.Plotter(off_screen=True, window_size=(1500, 1100))
    pl.set_background("white")
    if mesh is not None:
        pl.add_mesh(mesh, color="lightgray", opacity=0.20, smooth_shading=True)
    pl.add_mesh(
        cloud,
        render_points_as_spheres=True,
        point_size=8,
        scalars="Area",
        cmap="RdYlGn",
        clim=clim,
        nan_color="gray",
        scalar_bar_args={"title": "Area (mm^2)"},
    )
    pl.add_axes()
    pl.add_text(title, font_size=11, position="upper_left")
    pl.show(screenshot=str(out_path), auto_close=True)


def run_block2(patient_id: str, block1_dir: Path | None = None) -> pd.DataFrame:
    sample_name = patient_id
    if block1_dir is None:
        block1_dir = BLOCK1_SAMPLES_DIR / sample_name
    if not block1_dir.exists():
        raise FileNotFoundError(f"Block 1 sample folder not found: {block1_dir}")

    out_sample_dir = BLOCK2_AREA_SAMPLES_DIR / sample_name
    if out_sample_dir.exists():
        shutil.rmtree(out_sample_dir)
    out_branches_df_dir = out_sample_dir / "branches" / "dataframes"
    out_fig_dir = out_sample_dir / "figures"
    out_branch_fig_dir = out_sample_dir / "branches" / "figures"
    for d in (out_sample_dir, out_branches_df_dir, out_fig_dir, out_branch_fig_dir):
        d.mkdir(parents=True, exist_ok=True)

    logger.info("[Block2] Starting area phase for %s", patient_id)
    logger.info("[Block2] Using Block1 package: %s", block1_dir)
    logger.info("[Block2] Output package: %s", out_sample_dir)

    artery_surfaces_vtk: dict[str, object] = {}
    artery_surfaces_pv: dict[str, pv.PolyData] = {}
    loaded_vtk, loaded_pv = _load_surfaces_from_block1(block1_dir)
    artery_surfaces_vtk.update(loaded_vtk)
    artery_surfaces_pv.update(loaded_pv)

    missing_surface_arteries = [a for a in ("RCA", "LCA") if a not in artery_surfaces_vtk]
    if missing_surface_arteries:
        nrrd_path = DATA_ROOT / "ASOCA Normal" / "Annotations" / f"{patient_id}.nrrd"
        if not nrrd_path.exists():
            raise FileNotFoundError(f"Mask not found: {nrrd_path}")
        logger.info(
            "[Block2] Missing stored surfaces for %s. Rebuilding from mask.",
            ", ".join(missing_surface_arteries),
        )
        artery_arrays, spacing, origin = _load_and_separate_mask(nrrd_path)
        for name in missing_surface_arteries:
            surf_vtk, surf_pv = _build_surface_from_mask(artery_arrays[name], spacing, origin)
            artery_surfaces_vtk[name] = surf_vtk
            artery_surfaces_pv[name] = surf_pv
    else:
        logger.info("[Block2] Reusing stored Block1 surfaces: RCA, LCA")

    centerlines: dict[str, pv.PolyData] = {}
    ref_points: dict[str, np.ndarray] = {}
    ref_area: dict[str, np.ndarray] = {}
    for artery in ("RCA", "LCA"):
        cl_path = block1_dir / f"centerline_{artery}.vtp"
        if not cl_path.exists():
            raise FileNotFoundError(f"Missing Block 1 centerline: {cl_path}")
        logger.info("[%s][Area] Loading centerline: %s", artery, cl_path)
        cl_vtk = _read_vtp_as_vtk(cl_path)
        logger.info("[%s][Area] Preprocessing centerline (smooth+resample)", artery)
        cl_vtk_prep = _prepare_centerline_for_sections(
            cl_vtk,
            resample_step=0.1,
            smoothing_factor=0.15,
            iterations=20,
        )
        cl_poly = pv.wrap(cl_vtk_prep)
        centerlines[artery] = cl_poly
        ref_points[artery] = np.asarray(cl_poly.points, dtype=float)

        logger.info("[%s][Area] Preprocessing surface (triangulate+clean)", artery)
        surface_clean_vtk = _clean_triangulate_surface(artery_surfaces_vtk[artery])
        logger.info("[%s][Area] Running vmtkCenterlineSections", artery)
        ref_area[artery] = _compute_centerline_area(cl_vtk_prep, surface_clean_vtk)

        a = ref_area[artery]
        valid = np.isfinite(a)
        logger.info(
            "[%s][Area] points=%d valid=%d nan=%d range=[%.3f, %.3f] median=%.3f",
            artery,
            len(a),
            int(np.count_nonzero(valid)),
            int(np.count_nonzero(~valid)),
            float(np.nanmin(a)) if valid.any() else float("nan"),
            float(np.nanmax(a)) if valid.any() else float("nan"),
            float(np.nanmedian(a)) if valid.any() else float("nan"),
        )

    # Global dataframe
    global_in = block1_dir / f"dataset_global_{sample_name}.xlsx"
    if not global_in.exists():
        raise FileNotFoundError(f"Missing global dataframe: {global_in}")
    df_global = pd.read_excel(global_in)
    df_global["Area"] = np.nan
    for artery in ("RCA", "LCA"):
        mask = df_global["Artery_Type"].astype(str).values == artery
        if not np.any(mask):
            continue
        sub, mode = _map_area_to_df(df_global.loc[mask].copy(), ref_points[artery], ref_area[artery])
        df_global.loc[mask, "Area"] = sub["Area"].values
        logger.info("[Global][%s] mapping=%s rows=%d", artery, mode, int(np.count_nonzero(mask)))
    df_global.to_excel(out_sample_dir / f"dataset_global_{sample_name}.xlsx", index=False)

    # Artery dataframes
    artery_dfs: dict[str, pd.DataFrame] = {}
    for artery in ("RCA", "LCA"):
        artery_in = block1_dir / f"dataset_{artery}_{sample_name}.xlsx"
        if not artery_in.exists():
            raise FileNotFoundError(f"Missing artery dataframe: {artery_in}")
        df_art = pd.read_excel(artery_in)
        df_art, mode = _map_area_to_df(df_art, ref_points[artery], ref_area[artery])
        logger.info("[Artery][%s] mapping=%s rows=%d", artery, mode, len(df_art))
        df_art.to_excel(out_sample_dir / f"dataset_{artery}_{sample_name}.xlsx", index=False)
        artery_dfs[artery] = df_art

    # Branch dataframes
    branch_in_dir = block1_dir / "branches" / "dataframes"
    if branch_in_dir.exists():
        for branch_file in sorted(branch_in_dir.glob("dataset_*_*.xlsx")):
            df_b = pd.read_excel(branch_file)
            if "Artery_Type" not in df_b.columns or len(df_b) == 0:
                continue
            artery = str(df_b["Artery_Type"].iloc[0])
            if artery not in ref_points:
                continue
            df_b, mode = _map_area_to_df(df_b, ref_points[artery], ref_area[artery])
            logger.info("[Branch][%s][%s] mapping=%s rows=%d", artery, branch_file.name, mode, len(df_b))
            df_b.to_excel(out_branches_df_dir / branch_file.name, index=False)

            pts_b = df_b[["Px", "Py", "Pz"]].to_numpy(dtype=float)
            area_b = df_b["Area"].to_numpy(dtype=float)
            fig_name = f"fig_{branch_file.stem.replace('dataset_', '')}.png"
            _save_area_plot(
                points_xyz=pts_b,
                area=area_b,
                out_path=out_branch_fig_dir / fig_name,
                title=f"{sample_name} - {branch_file.stem}",
                mesh=artery_surfaces_pv.get(artery),
            )

    # Figures: full tree + artery-level
    _save_area_plot(
        points_xyz=df_global[["Px", "Py", "Pz"]].to_numpy(dtype=float),
        area=df_global["Area"].to_numpy(dtype=float),
        out_path=out_fig_dir / f"fig_area_tree_{sample_name}.png",
        title=f"{sample_name} - Area (full tree)",
        mesh=None,
    )
    for artery in ("RCA", "LCA"):
        df_art = artery_dfs[artery]
        _save_area_plot(
            points_xyz=df_art[["Px", "Py", "Pz"]].to_numpy(dtype=float),
            area=df_art["Area"].to_numpy(dtype=float),
            out_path=out_fig_dir / f"fig_area_{artery}_{sample_name}.png",
            title=f"{sample_name} - {artery} Area",
            mesh=artery_surfaces_pv.get(artery),
        )

    logger.info("[Save] Block 2 area package -> %s", out_sample_dir)
    return df_global
