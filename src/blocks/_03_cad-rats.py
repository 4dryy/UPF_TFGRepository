"""
Block 3 (phase 1): label-enriched exports and segment-based QC figures.

Uses Block 1 centerlines + Segment_ID and Block 2 stenosis outputs.
Writes ``results/block3_results/label/<patient_id>/total_df_<id>.xlsx`` (aligned copy
of Block 2 merged table), ``branches/dataframes/*.xlsx``, and ``figures/`` QC PNGs.
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv

from src.pipeline_log import footer_block, phase, short_path, sub

logger = logging.getLogger(__name__)

sys.modules.setdefault(
    "vtkmodules.vtkRenderingMatplotlib",
    types.ModuleType("vtkmodules.vtkRenderingMatplotlib"),
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLOCK1_ROOT = PROJECT_ROOT / "results" / "block1_results"
BLOCK2_STENOSIS_ROOT = PROJECT_ROOT / "results" / "block2_results" / "stenosis"
BLOCK3_LABEL_ROOT = PROJECT_ROOT / "results" / "block3_results" / "label"


def _export_seg_tree_figure(
    *,
    title: str,
    meshes: dict[str, pv.PolyData],
    centerlines_colored: list[pv.PolyData],
    ostium_pts: np.ndarray,
    endpoint_pts: np.ndarray,
    out_path: Path,
) -> None:
    pl = pv.Plotter(off_screen=True, window_size=(1800, 1300))
    pl.set_background("white")
    for name, mesh in meshes.items():
        pl.add_mesh(mesh, color="lightgray", opacity=0.20, smooth_shading=True, name=f"mesh_{name}")
    for poly in centerlines_colored:
        if poly is None or poly.n_points < 2:
            continue
        pl.add_mesh(
            poly,
            scalars="Segment_ID",
            cmap="tab20",
            line_width=8,
            render_lines_as_tubes=True,
            scalar_bar_args={"title": "Segment ID"},
        )
    if ostium_pts is not None and len(ostium_pts) > 0:
        pl.add_points(
            ostium_pts,
            color="red",
            point_size=24,
            render_points_as_spheres=True,
            label="Ostium",
        )
    if endpoint_pts is not None and len(endpoint_pts) > 0:
        pl.add_points(
            endpoint_pts,
            color="yellow",
            point_size=14,
            render_points_as_spheres=True,
            label="Endpoint",
        )
    pl.add_title(title, font_size=12)
    pl.add_legend(bcolor="white")
    pl.add_axes()
    pl.show(screenshot=str(out_path), auto_close=True)


def _attach_segment_scalars(
    cl_poly: pv.PolyData, df_art: pd.DataFrame
) -> pv.PolyData | None:
    if "Segment_ID" not in df_art.columns or len(df_art) != cl_poly.n_points:
        logger.warning(
            "Segment_ID missing or row/point mismatch (df_rows=%s, centerline_pts=%s)",
            len(df_art),
            cl_poly.n_points,
        )
        return None
    out = cl_poly.copy(deep=True)
    out["Segment_ID"] = df_art["Segment_ID"].to_numpy(dtype=float)
    return out


def run_block3_phase1(patient_id: str) -> Path:
    """Mirror Block 2 stenosis spreadsheets under label/ + segment QC PNGs."""
    t0 = time.perf_counter()
    sample_name = patient_id
    phase(logger, "3", "Label phase · export + segment QC")

    b1 = BLOCK1_ROOT / sample_name
    b2_sten = BLOCK2_STENOSIS_ROOT / sample_name

    if not b1.exists():
        raise FileNotFoundError(f"Block 1 package not found: {b1}")
    if not b2_sten.exists():
        raise FileNotFoundError(f"Block 2 stenosis outputs not found: {b2_sten}")

    out_dir = BLOCK3_LABEL_ROOT / sample_name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = out_dir / "figures"
    branches_df_dir = out_dir / "branches" / "dataframes"
    fig_dir.mkdir(parents=True, exist_ok=True)
    branches_df_dir.mkdir(parents=True, exist_ok=True)

    # Branch tables — same filenames as Block 2 stenosis/branches/dataframes
    b2_branch_dir = b2_sten / "branches" / "dataframes"
    n_branch_copies = 0
    if b2_branch_dir.is_dir():
        for xlsx in sorted(b2_branch_dir.glob("*.xlsx")):
            shutil.copy2(xlsx, branches_df_dir / xlsx.name)
            n_branch_copies += 1
    sub(logger, "Copied %d branch spreadsheets → branches/dataframes/", n_branch_copies)

    # Single merged tree table — same name as ``results/block2_results/stenosis/<id>/``.
    total_src = b2_sten / f"total_df_{sample_name}.xlsx"
    total_out = out_dir / f"total_df_{sample_name}.xlsx"
    if total_src.exists():
        df_total = pd.read_excel(total_src)
        if "source_branch" in df_total.columns:
            df_total = df_total.drop(columns=["source_branch"])
        df_total.to_excel(total_out, index=False)
        sub(logger, "Total tree export: %d rows → %s", len(df_total), total_out.name)
    else:
        logger.warning("Missing Block 2 total_df — no merged export for label phase.")

    # QC figures — require Segment_ID aligned with Block 1 centerlines.
    meshes: dict[str, pv.PolyData] = {}
    centerlines_vis: list[pv.PolyData] = []
    ostium_all: list[np.ndarray] = []
    endpoint_all: list[np.ndarray] = []

    for artery in ("RCA", "LCA"):
        surf_p = b1 / f"surface_{artery}.vtp"
        cl_p = b1 / f"centerline_{artery}.vtp"
        art_xlsx = b1 / f"dataset_{artery}_{sample_name}.xlsx"
        if surf_p.exists():
            meshes[artery] = pv.read(str(surf_p))
        if not cl_p.exists() or not art_xlsx.exists():
            continue
        df_a = pd.read_excel(art_xlsx)
        cl = pv.read(str(cl_p))
        cc = _attach_segment_scalars(cl, df_a)
        if cc is not None:
            centerlines_vis.append(cc)
        if "PointType" in df_a.columns and "Segment_ID" in df_a.columns:
            pts_xyz = df_a[["Px", "Py", "Pz"]].to_numpy(dtype=float)
            pt_mask = df_a["PointType"].astype(str).values
            ostium_all.append(pts_xyz[pt_mask == "Ostium"])
            endpoint_all.append(pts_xyz[pt_mask == "Endpoint"])

        if cc is None:
            continue
        ost = df_a.loc[df_a["PointType"] == "Ostium", ["Px", "Py", "Pz"]].to_numpy(dtype=float)
        edp = df_a.loc[df_a["PointType"] == "Endpoint", ["Px", "Py", "Pz"]].to_numpy(dtype=float)
        _export_seg_tree_figure(
            title=f"{artery} segments + ostium ( {sample_name} )",
            meshes={artery: meshes[artery]} if artery in meshes else {},
            centerlines_colored=[cc],
            ostium_pts=ost,
            endpoint_pts=edp,
            out_path=fig_dir / f"qc_segments_{artery}_{sample_name}.png",
        )

    if centerlines_vis and meshes:
        os_cat = np.vstack(ostium_all) if ostium_all else np.empty((0, 3))
        ep_cat = np.vstack(endpoint_all) if endpoint_all else np.empty((0, 3))
        _export_seg_tree_figure(
            title=f"Coronary tree by segment ({sample_name})",
            meshes=meshes,
            centerlines_colored=centerlines_vis,
            ostium_pts=os_cat if len(os_cat) else np.empty((0, 3)),
            endpoint_pts=ep_cat if len(ep_cat) else np.empty((0, 3)),
            out_path=fig_dir / f"qc_segments_GLOBAL_{sample_name}.png",
        )

    elapsed = time.perf_counter() - t0
    footer_block(
        logger,
        block_id="3",
        title="labels",
        seconds=elapsed,
        parts=[
            short_path(out_dir),
            "total_df · branches/dataframes · figures",
        ],
    )
    return out_dir
