"""
Block 2 — Geometric stenosis: sectional area extraction and %AS (stenosis phase).

Reads Block 1 packaged outputs, computes cross-sectional area (VMTK), maps area to
global/artery/branch tables, then computes reference areas, ``pct_AS``, merges
branches with max-%AS deduplication, and exports figures (area + %AS).
"""

from __future__ import annotations

import logging
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, NamedTuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyvista as pv
import scipy.ndimage as ndi
from matplotlib.colors import LinearSegmentedColormap
from scipy.spatial import cKDTree
from vmtk import vmtkscripts
from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader
from vtkmodules.vtkFiltersCore import vtkTriangleFilter
from vtkmodules.vtkFiltersCore import vtkCleanPolyData

from src.pipeline_log import footer_block, phase, short_path
from src.pipeline_log import sub as log_detail
from src.synthetic_profile import (
    SYNTHETIC_ARTERY,
    apply_synthetic_metadata,
    is_synthetic_patient,
    resolve_mask_nrrd_path,
)

logger = logging.getLogger(__name__)


class Block2Outputs(NamedTuple):
    """Outputs from ``run_block2`` for downstream blocks (e.g. Block 3)."""

    df_global_area: pd.DataFrame
    """Area-mapped full-tree table (same rows as Block 1 ``dataset_global``)."""

    total_df_merged: pd.DataFrame
    """Merged branch points: max ``pct_AS`` per rounded coordinate **within each branch file**; empty if no branches."""

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
BLOCK1_PATIENT_DIR_ROOT = PROJECT_ROOT / "results" / "block1_results"
BLOCK2_AREA_PATIENT_DIR_ROOT = PROJECT_ROOT / "results" / "block2_results" / "area"
BLOCK2_STENOSIS_PATIENT_DIR_ROOT = PROJECT_ROOT / "results" / "block2_results" / "stenosis"
BLOCK2_AREA_STENOSIS_PLOTS_ROOT = PROJECT_ROOT / "results" / "block2_results" / "area_stenosis_plots"

# Stenosis reference / merge / %AS figures (``_05_sq_reference_values`` notebook parity)
# ``WINDOW_MM`` is imported by ``src.viewer.plots`` for branch-path reference markers — single source here.
# WINDOW_MM = 10.0
WINDOW_MM = 5.0
# WINDOW_MM = 2.5
COORD_ROUND = 6
A_REF_EPS = 1e-12
PCT_AS_VMIN = 0.0
PCT_AS_VMAX = 100.0

GREEN_YELLOW_RED_STENOSIS = LinearSegmentedColormap.from_list(
    "pct_as_gyr", ["#1a9850", "#fee08b", "#d73027"], N=64
)


def nearest_index_within_bounds(gd_values: np.ndarray, target_values: np.ndarray) -> np.ndarray:
    """
    Return nearest indices in gd_values for each target in target_values.
    Targets outside gd range are marked with -1.
    """
    idx = np.searchsorted(gd_values, target_values)
    idx = np.clip(idx, 0, len(gd_values) - 1)

    prev_idx = np.clip(idx - 1, 0, len(gd_values) - 1)

    dist_prev = np.abs(gd_values[prev_idx] - target_values)
    dist_curr = np.abs(gd_values[idx] - target_values)

    nearest_idx = np.where(dist_prev <= dist_curr, prev_idx, idx)

    out_of_bounds = (target_values < gd_values[0]) | (target_values > gd_values[-1])
    nearest_idx[out_of_bounds] = -1

    return nearest_idx


def compute_reference_columns(df_branch: pd.DataFrame, window_mm: float) -> pd.DataFrame:
    df_out = df_branch.copy()

    xyz = df_out[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    delta_xyz = np.diff(xyz, axis=0)
    step_dist = np.linalg.norm(delta_xyz, axis=1)
    step_dist = np.insert(step_dist, 0, 0.0)

    df_out["gd"] = np.cumsum(step_dist)

    gd_vals = df_out["gd"].to_numpy(dtype=float)
    area_vals = df_out["Area"].to_numpy(dtype=float)

    prox_targets = gd_vals - window_mm
    dist_targets = gd_vals + window_mm

    prox_idx = nearest_index_within_bounds(gd_vals, prox_targets)
    dist_idx = nearest_index_within_bounds(gd_vals, dist_targets)

    area_prox = np.full(len(df_out), np.nan, dtype=float)
    area_dist = np.full(len(df_out), np.nan, dtype=float)

    prox_valid = prox_idx >= 0
    dist_valid = dist_idx >= 0

    area_prox[prox_valid] = area_vals[prox_idx[prox_valid]]
    area_dist[dist_valid] = area_vals[dist_idx[dist_valid]]

    df_out["Area_prox"] = area_prox
    df_out["Area_dist"] = area_dist
    df_out["A_ref"] = (df_out["Area_prox"] + df_out["Area_dist"]) / 2.0

    return df_out


def add_pct_as(df_branch: pd.DataFrame, eps: float = A_REF_EPS) -> pd.DataFrame:
    """Append % area stenosis (pct_AS). NaN A_ref and near-zero A_ref yield NaN pct_AS."""
    df_out = df_branch.copy()
    a_ref = df_out["A_ref"].to_numpy(dtype=float)
    area = df_out["Area"].to_numpy(dtype=float)
    valid = np.isfinite(a_ref) & (np.abs(a_ref) > eps)

    ratio = np.full(len(df_out), np.nan, dtype=float)
    ratio[valid] = area[valid] / a_ref[valid]
    df_out["pct_AS"] = (1.0 - ratio) * 100.0

    return df_out


def merge_branches_max_pct_as(
    processed_branch_data: dict[str, pd.DataFrame],
    coord_round: int = COORD_ROUND,
) -> pd.DataFrame:
    """Concatenate branches, dedupe rounded (Px,Py,Pz) **per branch spreadsheet**, max ``pct_AS``.

    Deduplication is **not** global on coordinates alone: samples from different branch files can
    round to identical ``(Px,Py,Pz)`` near bifurcations while carrying different ``Area`` /
    ``Segment_ID`` / ``pct_AS``. Collapsing them kept one full row (max ``pct_AS``), which could
    produce merged rows that never appeared in any single branch export. Tagging each row with its
    source spreadsheet key restricts deduplication to **within** the same ``dataset_*`` table.
    """
    branch_frames: list[pd.DataFrame] = []
    for stem, df in processed_branch_data.items():
        dfc = df.copy()
        dfc["__branch_source__"] = str(stem)
        branch_frames.append(dfc)
    total_concat = pd.concat(branch_frames, ignore_index=True)
    total_concat["_Px_g"] = np.round(total_concat["Px"].to_numpy(dtype=float), coord_round)
    total_concat["_Py_g"] = np.round(total_concat["Py"].to_numpy(dtype=float), coord_round)
    total_concat["_Pz_g"] = np.round(total_concat["Pz"].to_numpy(dtype=float), coord_round)

    _dedup_subset = ["_Px_g", "_Py_g", "_Pz_g", "__branch_source__"]
    # Sort so max pct_AS wins ties; preserves Branch_ID, Segment_ID, and other cols from retained row.
    return (
        total_concat.sort_values("pct_AS", ascending=False, na_position="last")
        .drop_duplicates(subset=_dedup_subset, keep="first")
        .drop(columns=_dedup_subset)
    )


def infer_artery_type(branch_or_df_name: str, df_plot: pd.DataFrame | None = None) -> str | None:
    if df_plot is not None and "Artery_Type" in df_plot.columns and len(df_plot) > 0:
        v = df_plot["Artery_Type"].iloc[0]
        if pd.notna(v):
            sv = str(v).strip().upper()
            if sv in ("RCA", "LCA", SYNTHETIC_ARTERY.upper()):
                return sv if sv != SYNTHETIC_ARTERY.upper() else SYNTHETIC_ARTERY
    bn = branch_or_df_name.upper()
    if SYNTHETIC_ARTERY.upper() in bn:
        return SYNTHETIC_ARTERY
    if "LCA" in bn:
        return "LCA"
    if "RCA" in bn:
        return "RCA"
    return None


def plot_pct_as_tree_pyvista(
    df_plot: pd.DataFrame,
    title: str,
    surfaces: dict[str, pv.PolyData],
    surface_keys: tuple[str, ...],
    *,
    ordered_branch_paths: dict[str, pd.DataFrame] | None = None,
    window_size: tuple[int, int] = (1500, 1100),
    out_path: Path | None = None,
) -> None:
    """Render optional hulls, gray centerline tube(s), and colored point cloud.

    If ``ordered_branch_paths`` is set (unified-tree mode), one polyline is drawn
    per branch dict entry in **path order** — never a single line through the
    concatenated global table, which would incorrectly connect unrelated segments.
    """
    off_screen = out_path is not None
    plotter = pv.Plotter(off_screen=off_screen, window_size=window_size)
    plotter.set_background("white")

    pts = df_plot[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    pct = df_plot["pct_AS"].to_numpy(dtype=float)

    for _sk in surface_keys:
        surf = surfaces.get(_sk)
        if surf is not None:
            plotter.add_mesh(
                surf,
                opacity=0.15,
                color="lightgray",
                show_edges=False,
                smooth_shading=True,
                name=f"hull_{_sk}",
            )

    # Gray backbone: one continuous line only when df_plot rows are one ordered path.
    # Unified ``total_df`` is *not* a single path → use ``ordered_branch_paths``.
    if ordered_branch_paths is not None:
        for _bpath_name in sorted(ordered_branch_paths.keys()):
            bb = ordered_branch_paths[_bpath_name][["Px", "Py", "Pz"]].to_numpy(dtype=float)
            if bb.shape[0] >= 2:
                _ln = pv.lines_from_points(bb, close=False)
                plotter.add_mesh(
                    _ln,
                    color="dimgray",
                    line_width=4,
                    opacity=0.35,
                    render_lines_as_tubes=True,
                    name=f"backbone_{_bpath_name}",
                )
    elif pts.shape[0] >= 2:
        backbone = pv.lines_from_points(pts, close=False)
        plotter.add_mesh(
            backbone,
            color="dimgray",
            line_width=4,
            opacity=0.40,
            render_lines_as_tubes=True,
            name="centerline_backbone",
        )

    cloud = pv.PolyData(pts)
    cloud["pct_AS"] = pct

    plotter.add_mesh(
        cloud,
        scalars="pct_AS",
        cmap=GREEN_YELLOW_RED_STENOSIS,
        clim=[PCT_AS_VMIN, PCT_AS_VMAX],
        point_size=6,
        render_points_as_spheres=True,
        nan_color="lightgray",
        scalar_bar_args={"title": "% Area stenosis (pct_AS)"},
    )

    plotter.add_text(title, font_size=11, color="black")
    plotter.add_axes()
    plotter.camera_position = "iso"
    if out_path is not None:
        plotter.show(screenshot=str(out_path), auto_close=True)
    else:
        plotter.show()


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


def _slug_branch(df_b: pd.DataFrame, fallback: str) -> str:
    """Stable short name for filenames."""
    if "Branch_ID" in df_b.columns and len(df_b) > 0:
        sid = df_b["Branch_ID"].iloc[0]
        if pd.notna(sid):
            return str(sid).strip()
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in fallback)[:120]


def _order_branch_like_centerline(df: pd.DataFrame) -> pd.DataFrame:
    sdf = df.copy()
    cols = []
    if "Branch_ID" in sdf.columns:
        cols.append("Branch_ID")
    if "gd" in sdf.columns:
        return sdf.sort_values(cols + ["gd"], ascending=True).reset_index(drop=True)
    if "Path_Point_Index" in sdf.columns:
        return sdf.sort_values(cols + ["Path_Point_Index"], ascending=True).reset_index(drop=True)
    return sdf.reset_index(drop=True)


def _histogram_with_max_vline(
    values: np.ndarray,
    *,
    out_path: Path,
    title: str,
    xlabel: str,
    color: str = "#3949ab",
) -> None:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    fig, ax = plt.subplots(figsize=(9.5, 5.25), dpi=160)
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fcfcfc")
    if len(v) == 0:
        ax.text(0.5, 0.5, "No valid finite values", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    else:
        n_bins = int(np.clip(round(np.sqrt(len(v))), 12, 64))
        ax.hist(v, bins=n_bins, color=color, alpha=0.88, edgecolor="white", linewidth=0.6)
        vmax = float(np.nanmax(v))
        ax.axvline(vmax, color="#c62828", linestyle="--", linewidth=2.2, label=f"Max = {vmax:.2f}")
        ax.legend(frameon=True, loc="upper right", fontsize=10)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel("Count", fontsize=11)
        ax.grid(True, alpha=0.35, linestyle=":")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.patch.get_facecolor())
    plt.close(fig)


def _plot_area_stenosis_profile_along_branch(
    df: pd.DataFrame,
    *,
    out_path: Path,
    title: str,
) -> None:
    sdf = _order_branch_like_centerline(df).reset_index(drop=True)
    if "Area" not in sdf.columns or "pct_AS" not in sdf.columns:
        return

    y_area = sdf["Area"].to_numpy(dtype=float)
    y_pct = sdf["pct_AS"].to_numpy(dtype=float)
    n = len(sdf)
    if n == 0:
        return

    x = np.arange(n)
    fig_w = float(np.clip(8.0 + 0.03 * n, 10.5, 22.0))
    fig, (ax_a, ax_p) = plt.subplots(
        2,
        1,
        figsize=(fig_w, 6.8),
        dpi=165,
        sharex=True,
        gridspec_kw={"height_ratios": [1.05, 1.0], "hspace": 0.14},
    )
    fig.patch.set_facecolor("#fafafa")
    ax_a.set_facecolor("#fcfcfc")
    ax_p.set_facecolor("#fcfcfc")
    fig.suptitle(title, fontsize=12, fontweight="bold")

    ax_a.bar(x, y_area, width=0.92, color="#388e3c", edgecolor="white", linewidth=0.35, align="center")
    ax_a.set_ylabel("Area (mm²)", fontsize=11)
    ax_a.grid(axis="y", alpha=0.35, linestyle=":")
    fa = np.isfinite(y_area)
    if fa.any():
        c_a = np.flatnonzero(fa)
        imx_a = int(c_a[np.argmax(y_area[c_a])])
        ax_a.scatter(
            imx_a,
            y_area[imx_a],
            color="#bf360c",
            s=54,
            zorder=5,
            edgecolors="white",
            linewidths=0.6,
        )

    ax_p.bar(x, y_pct, width=0.92, color="#fb8c00", edgecolor="white", linewidth=0.35, align="center")
    ax_p.set_ylabel("% area stenosis (pct_AS)", fontsize=11)
    ax_p.set_xlabel("Centerline point index (proximal→distal)", fontsize=11)
    ax_p.grid(axis="y", alpha=0.35, linestyle=":")
    fp = np.isfinite(y_pct)
    if fp.any():
        c_p = np.flatnonzero(fp)
        imx_p = int(c_p[np.argmax(y_pct[c_p])])
        ax_p.scatter(
            imx_p,
            y_pct[imx_p],
            color="#b71c1c",
            s=54,
            zorder=5,
            edgecolors="white",
            linewidths=0.6,
        )

    if n > 80:
        ax_p.set_xticks([])
    else:
        ax_p.set_xticks(x[:: max(1, n // 25)])
    fig.subplots_adjust(top=0.90, bottom=0.08, left=0.09, right=0.97)
    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.patch.get_facecolor())
    plt.close(fig)


def _save_area_plot(
    points_xyz: np.ndarray,
    area: np.ndarray,
    out_path: Path,
    title: str,
    mesh: pv.PolyData | None = None,
    extra_hulls: Iterable[pv.PolyData] | None = None,
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
    if extra_hulls is not None:
        for hm in extra_hulls:
            if hm is not None:
                pl.add_mesh(hm, color="lightgray", opacity=0.20, smooth_shading=True)
    elif mesh is not None:
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


def run_block2(
    patient_id: str,
    block1_dir: Path | None = None,
    *,
    is_synthetic: bool = False,
) -> Block2Outputs:
    """Run Block 2: area extraction, optional stenosis columns + merge + figures.

    **Area phase** → ``results/block2_results/area/<patient_id>/``:

    - ``dataset_global_<patient>.xlsx``, artery-level excels (``Area`` mapped).
    - ``branches/dataframes/dataset_*_<patient>.xlsx`` with ``Area`` only (Block 1 rows).
    - Area colormap figures under ``figures/`` and ``branches/figures/``
      (plus Matplotlib: full-tree / branch Area histograms & along-centerline bars).

    **Stenosis phase** (when branch spreadsheets exist) →
    ``results/block2_results/stenosis/<patient_id>/``:

    - Enriched branch tables (``gd``, ``A_ref``, ``pct_AS``, …) and ``total_df_<patient>.xlsx``.
    - ``fig_pct_AS_*`` exports under ``figures/`` and ``branches/figures/``
      (plus Matplotlib: %AS histograms for full tree / branches and along-branch bar charts).

    Re-running for the same ``patient_id`` replaces both folders (no duplicate samples).

    Returns:
        Block2Outputs with ``df_global_area`` (full-tree area table) and
        ``total_df_merged`` (empty dataframe if no branch spreadsheets).
    """
    sample_name = patient_id
    t_start = time.perf_counter()
    is_synthetic = bool(is_synthetic or is_synthetic_patient(patient_id))
    arteries: tuple[str, ...] = (SYNTHETIC_ARTERY,) if is_synthetic else ("RCA", "LCA")
    if block1_dir is None:
        block1_dir = BLOCK1_PATIENT_DIR_ROOT / sample_name
    if not block1_dir.exists():
        raise FileNotFoundError(f"Block 1 sample folder not found: {block1_dir}")

    out_area_dir = BLOCK2_AREA_PATIENT_DIR_ROOT / sample_name
    out_stenosis_dir = BLOCK2_STENOSIS_PATIENT_DIR_ROOT / sample_name
    out_area_stenosis_plots_dir = BLOCK2_AREA_STENOSIS_PLOTS_ROOT / sample_name
    for patient_root in (out_area_dir, out_stenosis_dir, out_area_stenosis_plots_dir):
        if patient_root.exists():
            shutil.rmtree(patient_root)

    out_branches_df_dir = out_area_dir / "branches" / "dataframes"
    out_fig_dir = out_area_dir / "figures"
    out_branch_fig_dir = out_area_dir / "branches" / "figures"
    for d in (out_area_dir, out_branches_df_dir, out_fig_dir, out_branch_fig_dir):
        d.mkdir(parents=True, exist_ok=True)

    phase(logger, "2", "Sectional area · %AS · merge")
    log_detail(logger, "Block1 ← %s  ·  write area → %s", short_path(block1_dir), short_path(out_area_dir))

    artery_surfaces_vtk: dict[str, object] = {}
    artery_surfaces_pv: dict[str, pv.PolyData] = {}
    loaded_vtk, loaded_pv = _load_surfaces_from_block1(block1_dir)
    artery_surfaces_vtk.update(loaded_vtk)
    artery_surfaces_pv.update(loaded_pv)

    missing_surface_arteries = [a for a in arteries if a not in artery_surfaces_vtk]
    if missing_surface_arteries:
        nrrd_path = resolve_mask_nrrd_path(patient_id)
        if not nrrd_path.exists():
            raise FileNotFoundError(f"Mask not found: {nrrd_path}")
        log_detail(logger, "Surfaces: rebuild from NRRD (%s)", ", ".join(missing_surface_arteries))
        if is_synthetic:
            from src.blocks._01_extraction import _load_single_mask

            full_mask, spacing, origin = _load_single_mask(nrrd_path)
            artery_arrays = {SYNTHETIC_ARTERY: full_mask}
        else:
            artery_arrays, spacing, origin = _load_and_separate_mask(nrrd_path)
        for name in missing_surface_arteries:
            surf_vtk, surf_pv = _build_surface_from_mask(artery_arrays[name], spacing, origin)
            artery_surfaces_vtk[name] = surf_vtk
            artery_surfaces_pv[name] = surf_pv
    else:
        log_detail(
            logger,
            "Surfaces: reuse Block1 (%s)",
            "+".join(arteries),
        )

    centerlines: dict[str, pv.PolyData] = {}
    ref_points: dict[str, np.ndarray] = {}
    ref_area: dict[str, np.ndarray] = {}
    for artery in arteries:
        cl_path = block1_dir / f"centerline_{artery}.vtp"
        if not cl_path.exists():
            raise FileNotFoundError(f"Missing Block 1 centerline: {cl_path}")
        cl_vtk = _read_vtp_as_vtk(cl_path)
        cl_vtk_prep = _prepare_centerline_for_sections(
            cl_vtk,
            resample_step=0.1,
            smoothing_factor=0.15,
            iterations=20,
        )
        cl_poly = pv.wrap(cl_vtk_prep)
        centerlines[artery] = cl_poly
        ref_points[artery] = np.asarray(cl_poly.points, dtype=float)

        surface_clean_vtk = _clean_triangulate_surface(artery_surfaces_vtk[artery])
        ref_area[artery] = _compute_centerline_area(cl_vtk_prep, surface_clean_vtk)

        a = ref_area[artery]
        valid = np.isfinite(a)
        log_detail(
            logger,
            "%s sections: n=%d valid=%d nan=%d  A[%.3f–%.3f] mm² med=%.3f",
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
    global_bits: list[str] = []
    for artery in arteries:
        mask = df_global["Artery_Type"].astype(str).values == artery
        if not np.any(mask):
            continue
        mapped_df, mode = _map_area_to_df(df_global.loc[mask].copy(), ref_points[artery], ref_area[artery])
        df_global.loc[mask, "Area"] = mapped_df["Area"].values
        global_bits.append(f"{artery} {int(np.count_nonzero(mask))} rows [{mode}]")
    df_global.to_excel(out_area_dir / f"dataset_global_{sample_name}.xlsx", index=False)
    if global_bits:
        log_detail(logger, "Map Area → global: %s", " · ".join(global_bits))

    # Artery dataframes
    artery_dfs: dict[str, pd.DataFrame] = {}
    art_bits: list[str] = []
    for artery in arteries:
        artery_in = block1_dir / f"dataset_{artery}_{sample_name}.xlsx"
        if not artery_in.exists():
            raise FileNotFoundError(f"Missing artery dataframe: {artery_in}")
        df_art = pd.read_excel(artery_in)
        df_art, mode = _map_area_to_df(df_art, ref_points[artery], ref_area[artery])
        art_bits.append(f"{artery} {len(df_art)} [{mode}]")
        df_art.to_excel(out_area_dir / f"dataset_{artery}_{sample_name}.xlsx", index=False)
        artery_dfs[artery] = df_art
    if art_bits:
        log_detail(logger, "Map Area → artery: %s", " · ".join(art_bits))

    # Branch dataframes (area mapping); stash copies for stenosis phase (no re-read).
    processed_branch_data: dict[str, pd.DataFrame] = {}
    branch_map_modes: list[str] = []
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
            branch_map_modes.append(mode)
            df_b.to_excel(out_branches_df_dir / branch_file.name, index=False)
            processed_branch_data[branch_file.stem] = df_b.copy()

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
            bid = _slug_branch(df_b, branch_file.stem)
            _histogram_with_max_vline(
                df_b["Area"].to_numpy(dtype=float),
                out_path=out_branch_fig_dir / f"hist_Area_branch_{bid}_{sample_name}.png",
                title=f"{sample_name} · {bid} · Area distribution",
                xlabel="Cross-sectional area (mm²)",
                color="#1b5e20",
            )
    if branch_map_modes:
        mc = Counter(branch_map_modes)
        mode_summary = ", ".join(f"{k}×{v}" for k, v in sorted(mc.items()))
        log_detail(
            logger,
            "Map Area → branches: %d tables (%s)",
            len(branch_map_modes),
            mode_summary,
        )

    _histogram_with_max_vline(
        df_global["Area"].to_numpy(dtype=float),
        out_path=out_fig_dir / f"hist_Area_full_tree_{sample_name}.png",
        title=f"{sample_name} · Full coronary tree · Area distribution",
        xlabel="Cross-sectional area (mm²)",
        color="#283593",
    )

    total_df_merged = pd.DataFrame()
    if processed_branch_data:
        out_stenosis_branches_df_dir = out_stenosis_dir / "branches" / "dataframes"
        out_stenosis_fig_dir = out_stenosis_dir / "figures"
        out_stenosis_branch_fig_dir = out_stenosis_dir / "branches" / "figures"
        out_area_stenosis_branch_fig_dir = out_area_stenosis_plots_dir / "branches" / "figures"
        for d in (
            out_stenosis_dir,
            out_stenosis_branches_df_dir,
            out_stenosis_fig_dir,
            out_stenosis_branch_fig_dir,
            out_area_stenosis_branch_fig_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

        log_detail(
            logger,
            "Stenosis: window ±%.0f mm · %d branch tables → %s",
            WINDOW_MM,
            len(processed_branch_data),
            short_path(out_stenosis_dir),
        )
        for key in list(processed_branch_data.keys()):
            d = compute_reference_columns(processed_branch_data[key], WINDOW_MM)
            processed_branch_data[key] = add_pct_as(d)

        total_df_merged = merge_branches_max_pct_as(processed_branch_data)
        n_valid_pct = int(total_df_merged["pct_AS"].notna().sum())
        n_br_st = len(processed_branch_data)
        pct_finite = total_df_merged["pct_AS"].to_numpy(dtype=float)
        pct_fin = np.isfinite(pct_finite)
        pct_rng = (
            f"{float(np.nanmin(pct_finite[pct_fin])):.1f}–{float(np.nanmax(pct_finite[pct_fin])):.1f}"
            if pct_fin.any()
            else "n/a"
        )
        log_detail(
            logger,
            "Merge (max %%AS / site **per branch**): %d rows · %d valid pct_AS · range %s %%",
            len(total_df_merged),
            n_valid_pct,
            pct_rng,
        )

        total_path = out_stenosis_dir / f"total_df_{sample_name}.xlsx"
        total_df_merged.to_excel(total_path, index=False)

        for key in sorted(processed_branch_data.keys()):
            branch_xlsx = out_stenosis_branches_df_dir / f"{key}.xlsx"
            processed_branch_data[key].to_excel(branch_xlsx, index=False)

        surfaces_pv = artery_surfaces_pv
        if not surfaces_pv:
            logger.warning("%AS plots: no hull meshes (surfaces missing)")

        unified_path = out_stenosis_fig_dir / f"fig_pct_AS_tree_{sample_name}.png"
        plot_pct_as_tree_pyvista(
            total_df_merged,
            title=f"{sample_name} — Unified tree — %AS (max per location)",
            surfaces=surfaces_pv,
            surface_keys=arteries,
            ordered_branch_paths=processed_branch_data,
            out_path=unified_path,
        )

        for branch_key in sorted(processed_branch_data.keys()):
            dfb = processed_branch_data[branch_key]
            art = infer_artery_type(branch_key, dfb)
            surf_keys: tuple[str, ...] = (art,) if art is not None else tuple()
            pct_fig = out_stenosis_branch_fig_dir / f"fig_pct_AS_{branch_key.replace('dataset_', '')}.png"
            plot_pct_as_tree_pyvista(
                dfb,
                title=f"{sample_name} — {branch_key} — %AS",
                surfaces=surfaces_pv,
                surface_keys=surf_keys,
                out_path=pct_fig,
            )

        concat_pct = pd.concat(processed_branch_data.values(), ignore_index=True)
        _histogram_with_max_vline(
            concat_pct["pct_AS"].to_numpy(dtype=float),
            out_path=out_stenosis_fig_dir / f"hist_pct_AS_full_tree_{sample_name}.png",
            title=f"{sample_name} · Full coronary tree · % area stenosis (all branch points)",
            xlabel="% area stenosis (pct_AS)",
            color="#5c6bc0",
        )

        for branch_key in sorted(processed_branch_data.keys()):
            dfb_w = processed_branch_data[branch_key]
            bid = _slug_branch(dfb_w, branch_key)
            _histogram_with_max_vline(
                dfb_w["pct_AS"].to_numpy(dtype=float),
                out_path=out_stenosis_branch_fig_dir / f"hist_pct_AS_branch_{bid}_{sample_name}.png",
                title=f"{sample_name} · {bid} · % area stenosis distribution",
                xlabel="% area stenosis (pct_AS)",
                color="#3949ab",
            )
            _plot_area_stenosis_profile_along_branch(
                dfb_w,
                out_path=out_area_stenosis_branch_fig_dir / f"fig_area_stenosis_branch_{bid}_{sample_name}.png",
                title=f"{sample_name} — {bid} ({len(dfb_w)} points)",
            )

        log_detail(logger, "%%AS figures: 1 tree + %d branch → %s", n_br_st, short_path(out_stenosis_dir))

    # Figures: full tree + artery-level (area colormap)
    tree_hulls = tuple(h for k in arteries if (h := artery_surfaces_pv.get(k)) is not None)
    _save_area_plot(
        points_xyz=df_global[["Px", "Py", "Pz"]].to_numpy(dtype=float),
        area=df_global["Area"].to_numpy(dtype=float),
        out_path=out_fig_dir / f"fig_area_tree_{sample_name}.png",
        title=f"{sample_name} - Area (full tree)",
        mesh=None,
        extra_hulls=tree_hulls if tree_hulls else None,
    )
    for artery in arteries:
        df_art = artery_dfs[artery]
        _save_area_plot(
            points_xyz=df_art[["Px", "Py", "Pz"]].to_numpy(dtype=float),
            area=df_art["Area"].to_numpy(dtype=float),
            out_path=out_fig_dir / f"fig_area_{artery}_{sample_name}.png",
            title=f"{sample_name} - {artery} Area",
            mesh=artery_surfaces_pv.get(artery),
        )

    if is_synthetic:
        df_global = apply_synthetic_metadata(df_global)
        df_global.to_excel(out_area_dir / f"dataset_global_{sample_name}.xlsx", index=False)
        for artery in arteries:
            artery_dfs[artery] = apply_synthetic_metadata(artery_dfs[artery])
            artery_dfs[artery].to_excel(
                out_area_dir / f"dataset_{artery}_{sample_name}.xlsx", index=False
            )
        for key in list(processed_branch_data.keys()):
            processed_branch_data[key] = apply_synthetic_metadata(processed_branch_data[key])
            processed_branch_data[key].to_excel(
                out_branches_df_dir / f"{key}.xlsx", index=False
            )
        if not total_df_merged.empty:
            total_df_merged = apply_synthetic_metadata(total_df_merged)
            stenosis_path = out_stenosis_dir / f"total_df_{sample_name}.xlsx"
            if stenosis_path.parent.exists():
                total_df_merged.to_excel(stenosis_path, index=False)
                for key in processed_branch_data:
                    branch_xlsx = out_stenosis_dir / "branches" / "dataframes" / f"{key}.xlsx"
                    if branch_xlsx.parent.exists():
                        processed_branch_data[key].to_excel(branch_xlsx, index=False)

    av = df_global["Area"].to_numpy(dtype=float)
    n_area_ok = int(np.sum(np.isfinite(av) & (av > 0)))
    parts2 = [
        f"{len(df_global)} rows · Area valid {n_area_ok}",
        f"area → {short_path(out_area_dir)}",
    ]
    if processed_branch_data:
        parts2.append(
            f"stenosis → {short_path(out_stenosis_dir)}",
        )
    footer_block(
        logger,
        block_id="2",
        title="area+stenosis",
        seconds=time.perf_counter() - t_start,
        parts=parts2,
    )
    return Block2Outputs(df_global_area=df_global, total_df_merged=total_df_merged)
