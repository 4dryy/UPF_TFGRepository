"""
Block 3: label-enriched exports, segment-wise stenosis aggregation, and CAD-RADS 2.0.

Phase 1 mirrors Block 2 stenosis under ``label/`` and emits segment QC figures.
Phase 2 aggregates ``pct_AS`` by ``Segment_ID`` (SCCT-18 atlas) to ``segment stenosis/``.
Phase 3 scores CAD-RADS 2.0 and writes ``cad-rads/`` report + patient ID card.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import textwrap
import time
import types
from pathlib import Path
from typing import Any, NamedTuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

import numpy as np
import pandas as pd
import pyvista as pv
import seaborn as sns

from src.pipeline_log import footer_block, phase, short_path, sub
from src.segment_atlas import (
    KNOWN_SCCT18_SEGMENT_IDS,
    LEFT_MAIN_SEGMENT_ID,
    TERRITORY_SEGMENTS,
    build_scct18_segment_dictionary,
    sis_denominator_for_segment_summary,
)
from src.synthetic_profile import (
    SYNTHETIC_ARTERY,
    SYNTHETIC_CAD_RADS_LABEL,
    SYNTHETIC_SEGMENT_ID,
    SYNTHETIC_SEGMENT_NAME,
    apply_synthetic_metadata,
    is_stenosis_synthetic_patient,
    is_synthetic_patient,
    synthetic_validation_metrics,
)

logger = logging.getLogger(__name__)

sys.modules.setdefault(
    "vtkmodules.vtkRenderingMatplotlib",
    types.ModuleType("vtkmodules.vtkRenderingMatplotlib"),
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLOCK1_ROOT = PROJECT_ROOT / "results" / "block1_results"
BLOCK2_STENOSIS_ROOT = PROJECT_ROOT / "results" / "block2_results" / "stenosis"
BLOCK3_LABEL_ROOT = PROJECT_ROOT / "results" / "block3_results" / "label"
BLOCK3_LABELS_ALT = PROJECT_ROOT / "results" / "block3_results" / "labels"
BLOCK3_SEGMENT_STENOSIS_ROOT = PROJECT_ROOT / "results" / "block3_results" / "segment stenosis"
BLOCK3_CADRADS_ROOT = PROJECT_ROOT / "results" / "block3_results" / "cad-rads"

RISK_PRIORITY_MAP: dict[str, dict[str, object]] = {
    "0": {"Priority_Risk_Score": 0, "Priority_Risk_Label": "Very low priority"},
    "1": {"Priority_Risk_Score": 1, "Priority_Risk_Label": "Low priority"},
    "2": {"Priority_Risk_Score": 2, "Priority_Risk_Label": "Low-moderate priority"},
    "3": {"Priority_Risk_Score": 3, "Priority_Risk_Label": "Moderate priority"},
    "4A": {"Priority_Risk_Score": 4, "Priority_Risk_Label": "High priority"},
    "4B": {"Priority_Risk_Score": 5, "Priority_Risk_Label": "Very high priority"},
    "5": {"Priority_Risk_Score": 6, "Priority_Risk_Label": "Critical priority"},
}


class Block3Outputs(NamedTuple):
    """Paths and primary CAD-RADS string from ``run_block3``."""

    label_dir: Path
    stenosis_summary_path: Path
    patient_report_path: Path
    patient_id_card_path: Path
    final_cad_rads_code: str


def resolve_global_tree_path(sample_name: str) -> Path:
    candidates = [
        BLOCK3_LABEL_ROOT / sample_name / f"total_df_{sample_name}.xlsx",
        BLOCK3_LABEL_ROOT / sample_name / f"total_df_merged_{sample_name}.xlsx",
        BLOCK3_LABELS_ALT / sample_name / f"total_df_{sample_name}.xlsx",
        BLOCK3_LABELS_ALT / sample_name / f"total_df_merged_{sample_name}.xlsx",
        BLOCK2_STENOSIS_ROOT / sample_name / f"total_df_{sample_name}.xlsx",
        PROJECT_ROOT / f"total_df_{sample_name}.xlsx",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(
        f"Could not find the global tree spreadsheet for {sample_name}. Checked:\n{searched}"
    )


def resolve_pct_as_column(df: pd.DataFrame) -> str:
    aliases = [
        "pct_AS",
        "pct_as",
        "Percent_AS",
        "percent_AS",
        "%AS",
        "AS_percent",
        "Area_Stenosis_Percent",
    ]
    for alias in aliases:
        if alias in df.columns:
            return alias
    raise KeyError("No percent area stenosis column found. Expected one of: " + ", ".join(aliases))


def classify_segment_stenosis_severity(max_pct_as: float) -> pd.Series:
    """Per _07_segment_stenosis: segment-level grade/label from maximum %AS (CAD-RADS 2.0 bins)."""
    if pd.isna(max_pct_as):
        return pd.Series(
            {"Stenosis_Severity_Grade": pd.NA, "Stenosis_Severity_Label": "Not assessable"}
        )

    value = float(np.clip(max_pct_as, 0, 100))
    if value == 0:
        grade, label = 0, "No visible stenosis"
    elif value < 25:
        grade, label = 1, "Minimal stenosis"
    elif value < 50:
        grade, label = 2, "Mild stenosis"
    elif value < 70:
        grade, label = 3, "Moderate stenosis"
    elif value < 100:
        grade, label = 4, "Severe stenosis"
    else:
        grade, label = 5, "Total occlusion"

    return pd.Series({"Stenosis_Severity_Grade": grade, "Stenosis_Severity_Label": label})


def classify_segment_stenosis(max_pct_as: float) -> pd.Series:
    """Same bins as ``classify_segment_stenosis_severity`` (_08 naming)."""
    return classify_segment_stenosis_severity(max_pct_as)


def top_segment_label(df: pd.DataFrame) -> str:
    if df.empty or df["Max_pct_AS_Clipped"].dropna().empty:
        return "Not present"
    row = df.sort_values(["Max_pct_AS_Clipped", "Segment_ID"], ascending=[False, True]).iloc[0]
    return f"{row['Segment_Name']} (segment {int(row['Segment_ID'])})"


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


def _segment_id_vtk_scalars(seg: pd.Series) -> np.ndarray:
    """Map ``Segment_ID`` column to float scalars for PyVista (handles synthetic string placeholders)."""
    numeric = pd.to_numeric(seg, errors="coerce")
    if numeric.notna().all():
        return numeric.to_numpy(dtype=float)
    # Legacy / placeholder string IDs (e.g. ``Synthetic_Vessel``) → single color bucket.
    return np.ones(len(seg), dtype=float)


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
    out["Segment_ID"] = _segment_id_vtk_scalars(df_art["Segment_ID"])
    return out


def run_block3_phase1(patient_id: str, *, emit_footer: bool = True) -> Path:
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

    b2_branch_dir = b2_sten / "branches" / "dataframes"
    n_branch_copies = 0
    if b2_branch_dir.is_dir():
        for xlsx in sorted(b2_branch_dir.glob("*.xlsx")):
            shutil.copy2(xlsx, branches_df_dir / xlsx.name)
            n_branch_copies += 1
    sub(logger, "Copied %d branch spreadsheets → branches/dataframes/", n_branch_copies)

    total_src = b2_sten / f"total_df_{sample_name}.xlsx"
    total_out = out_dir / f"total_df_{sample_name}.xlsx"
    if total_src.exists():
        df_total = pd.read_excel(total_src)
        if "source_branch" in df_total.columns:
            df_total = df_total.drop(columns=["source_branch"])
        if is_synthetic_patient(sample_name):
            df_total = apply_synthetic_metadata(df_total)
        df_total.to_excel(total_out, index=False)
        sub(logger, "Total tree export: %d rows → %s", len(df_total), total_out.name)
    else:
        logger.warning("Missing Block 2 total_df — no merged export for label phase.")

    meshes: dict[str, pv.PolyData] = {}
    centerlines_vis: list[pv.PolyData] = []
    ostium_all: list[np.ndarray] = []
    endpoint_all: list[np.ndarray] = []

    artery_keys = (SYNTHETIC_ARTERY,) if is_synthetic_patient(sample_name) else ("RCA", "LCA")
    for artery in artery_keys:
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
    if emit_footer:
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


def run_segment_stenosis_phase(patient_id: str, segment_dictionary: pd.DataFrame) -> tuple[pd.DataFrame, Path]:
    """Aggregate by segment; write ``stenosis_summary_{id}.xlsx`` (_07 notebook parity)."""
    sample_name = patient_id
    phase(logger, "3b", "Segment stenosis · SCCT-18 aggregation")

    tree_path = resolve_global_tree_path(sample_name)
    total_df_merged = pd.read_excel(tree_path)

    if "Segment_ID" not in total_df_merged.columns:
        raise KeyError("Input table must contain Segment_ID (Block 3 label enrichment / Block 1).")

    pct_col = resolve_pct_as_column(total_df_merged)
    total_df_merged["Segment_ID"] = (
        pd.to_numeric(total_df_merged["Segment_ID"], errors="coerce").fillna(0).astype(int)
    )
    total_df_merged[pct_col] = pd.to_numeric(total_df_merged[pct_col], errors="coerce")

    present = set(total_df_merged.loc[total_df_merged["Segment_ID"] != 0, "Segment_ID"].unique())
    defined = set(segment_dictionary["Segment_ID"].unique())
    unmapped_present = sorted(present - defined)
    if unmapped_present:
        logger.warning(
            "Segment_ID values in data not listed in the SCCT-18 dictionary: %s — "
            "they will be summarized as unmapped segments.",
            unmapped_present,
        )

    foreground_df = total_df_merged.loc[total_df_merged["Segment_ID"] != 0].copy()

    segment_aggregation = (
        foreground_df.groupby("Segment_ID", as_index=False)
        .agg(
            Max_pct_AS=(pct_col, "max"),
            Mean_pct_AS=(pct_col, "mean"),
            Point_Count=(pct_col, "size"),
            Valid_pct_AS_Count=(pct_col, "count"),
        )
        .sort_values("Segment_ID")
    )

    seg_sum = segment_aggregation.merge(segment_dictionary, on="Segment_ID", how="left")
    seg_sum["Segment_Name"] = seg_sum["Segment_Name"].fillna(
        "Unmapped segment " + seg_sum["Segment_ID"].astype(str)
    )
    seg_sum["Artery_Type"] = seg_sum["Artery_Type"].fillna("Unmapped")
    seg_sum["Specific_Artery"] = seg_sum["Specific_Artery"].fillna("Unmapped")

    seg_sum[["Stenosis_Severity_Grade", "Stenosis_Severity_Label"]] = seg_sum["Max_pct_AS"].apply(
        classify_segment_stenosis_severity
    )
    seg_sum["Max_pct_AS"] = seg_sum["Max_pct_AS"].clip(lower=0, upper=100)
    seg_sum["Mean_pct_AS"] = seg_sum["Mean_pct_AS"].clip(lower=0, upper=100)

    seg_sum = seg_sum.sort_values(
        ["Stenosis_Severity_Grade", "Max_pct_AS", "Segment_ID"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    out_dir = BLOCK3_SEGMENT_STENOSIS_ROOT / sample_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_xlsx = out_dir / f"stenosis_summary_{sample_name}.xlsx"

    export_columns = [
        "Segment_ID",
        "Segment_Name",
        "Artery_Type",
        "Specific_Artery",
        "Max_pct_AS",
        "Stenosis_Severity_Grade",
        "Stenosis_Severity_Label",
        "Point_Count",
        "Valid_pct_AS_Count",
    ]
    seg_sum[export_columns].to_excel(out_xlsx, index=False)

    fig_prof = out_dir / "figures"
    fig_prof.mkdir(parents=True, exist_ok=True)

    def _sort_segment_points(d: pd.DataFrame) -> pd.DataFrame:
        key_cols: list[str] = []
        if "Branch_ID" in d.columns:
            key_cols.append("Branch_ID")
        if "gd" in d.columns:
            return d.sort_values(key_cols + ["gd"], ascending=True).reset_index(drop=True)
        if "Path_Point_Index" in d.columns:
            return d.sort_values(key_cols + ["Path_Point_Index"], ascending=True).reset_index(drop=True)
        return d.sort_values(["Px", "Py", "Pz"]).reset_index(drop=True)

    if "Area" not in foreground_df.columns:
        logger.warning("Segment profile figures skipped: Area not in labeled tree dataframe.")
    else:
        for row in seg_sum.itertuples(index=False):
            sid = int(row.Segment_ID)
            sname = str(row.Segment_Name)
            sdf_raw = foreground_df.loc[foreground_df["Segment_ID"] == sid].copy()
            if sdf_raw.empty:
                continue
            sdf = _sort_segment_points(sdf_raw)
            y_a = sdf["Area"].to_numpy(dtype=float)
            y_p = sdf[pct_col].to_numpy(dtype=float)
            n = len(sdf)
            xv = np.arange(n)
            fig_pr, (ax_a, ax_p) = plt.subplots(
                2,
                1,
                figsize=(12, 7.0),
                dpi=165,
                sharex=True,
                gridspec_kw={"height_ratios": [1.05, 1.0], "hspace": 0.14},
            )
            fig_pr.patch.set_facecolor("#fafafa")
            for ax_k in (ax_a, ax_p):
                ax_k.set_facecolor("#fcfcfc")
            fig_pr.suptitle(
                f"{sample_name} — {sname} · segment ID {sid} ({n} points)",
                fontsize=12,
                fontweight="bold",
                color="#14532d",
            )
            ax_a.bar(xv, y_a, color="#00897b", edgecolor="white", linewidth=0.35)
            ax_a.set_ylabel("Area (mm²)", fontsize=11)
            ax_a.grid(axis="y", alpha=0.35, linestyle=":")
            fa = np.isfinite(y_a)
            if fa.any():
                c_a = np.flatnonzero(fa)
                imx = int(c_a[np.argmax(y_a[c_a])])
                ax_a.scatter(imx, y_a[imx], color="#bf360c", s=54, zorder=5, edgecolors="white", linewidths=0.6)

            ax_p.bar(xv, y_p, color="#fb8c00", edgecolor="white", linewidth=0.35)
            ax_p.set_ylabel("% area stenosis (pct_AS)", fontsize=11)
            ax_p.set_xlabel("Along-segment sample index (proximal → distal)", fontsize=11)
            ax_p.grid(axis="y", alpha=0.35, linestyle=":")
            fp = np.isfinite(y_p)
            if fp.any():
                c_p = np.flatnonzero(fp)
                imp = int(c_p[np.argmax(y_p[c_p])])
                ax_p.scatter(imp, y_p[imp], color="#b71c1c", s=54, zorder=5, edgecolors="white", linewidths=0.6)

            fig_pr.subplots_adjust(top=0.90, bottom=0.08, left=0.09, right=0.97)
            out_png = fig_prof / f"fig_segment_profiles_id{sid}_{sample_name}.png"
            fig_pr.savefig(out_png, bbox_inches="tight", facecolor=fig_pr.patch.get_facecolor())
            plt.close(fig_pr)

    sub(
        logger,
        "Segment stenosis: %d segments · %s → %s",
        len(seg_sum),
        short_path(tree_path),
        short_path(out_xlsx),
    )
    return seg_sum, out_xlsx


def _prepare_segment_summary_for_cadrads(segment_summary: pd.DataFrame) -> pd.DataFrame:
    """Normalize dtypes and recompute grades from clipped %AS (_08 notebook)."""
    ss = segment_summary.copy()
    legacy_renames = {
        "CADRADS_Category": "Stenosis_Severity_Grade",
        "CADRADS_Label": "Stenosis_Severity_Label",
        "Artery": "Specific_Artery",
    }
    ss = ss.rename(columns={k: v for k, v in legacy_renames.items() if k in ss.columns})

    ss["Segment_ID"] = pd.to_numeric(ss["Segment_ID"], errors="coerce").astype("Int64")
    ss["Max_pct_AS"] = pd.to_numeric(ss["Max_pct_AS"], errors="coerce")
    ss["Max_pct_AS_Clipped"] = ss["Max_pct_AS"].clip(lower=0, upper=100)

    ss[["Stenosis_Severity_Grade", "Stenosis_Severity_Label"]] = ss["Max_pct_AS_Clipped"].apply(
        classify_segment_stenosis
    )
    ss["Stenosis_Severity_Grade"] = pd.to_numeric(
        ss["Stenosis_Severity_Grade"], errors="coerce"
    ).astype("Int64")

    for optional_col in ("Artery_Type", "Specific_Artery"):
        if optional_col not in ss.columns:
            ss[optional_col] = "Unknown"
    return ss


def compute_cad_rads_patient_level(segment_summary: pd.DataFrame) -> dict[str, Any]:
    """Patient-level CAD-RADS 2.0 + SIS + territory flags (_08 notebook)."""
    ss = _prepare_segment_summary_for_cadrads(segment_summary)

    territory_rows: list[dict[str, object]] = []
    for territory_name, segment_ids in TERRITORY_SEGMENTS.items():
        territory_df = ss.loc[ss["Segment_ID"].isin(segment_ids)]
        max_pct = territory_df["Max_pct_AS_Clipped"].max() if not territory_df.empty else np.nan
        max_grade = territory_df["Stenosis_Severity_Grade"].max() if not territory_df.empty else pd.NA
        max_pct_for_flags = 0.0 if pd.isna(max_pct) else float(max_pct)
        territory_rows.append(
            {
                "Territory": territory_name,
                "Segments": ", ".join(str(x) for x in sorted(segment_ids)),
                "Highest_Stenosis_Location": top_segment_label(territory_df),
                "Territory_Max_pct_AS": max_pct,
                "Territory_Max_Grade": max_grade,
                "Obstructive_50plus": max_pct_for_flags >= 50,
                "Severe_70plus": max_pct_for_flags >= 70,
            }
        )

    territory_summary = pd.DataFrame(territory_rows)
    vessel_obstructive_count_50 = int(territory_summary["Obstructive_50plus"].sum())
    vessel_severe_count_70 = int(territory_summary["Severe_70plus"].sum())
    three_vessel_severe_70 = bool(territory_summary["Severe_70plus"].all())

    lm_df = ss.loc[ss["Segment_ID"] == LEFT_MAIN_SEGMENT_ID]
    lm_max_pct = lm_df["Max_pct_AS_Clipped"].max() if not lm_df.empty else np.nan
    lm_stenosis_50plus = bool(pd.notna(lm_max_pct) and float(lm_max_pct) >= 50)

    unmapped_for_territories = ss.loc[~ss["Segment_ID"].isin(KNOWN_SCCT18_SEGMENT_IDS)].copy()
    if not unmapped_for_territories.empty:
        logger.warning(
            "Segment_ID values not in the SCCT-18 atlas: %s",
            sorted(unmapped_for_territories["Segment_ID"].dropna().unique().tolist()),
        )

    assessable_segments = ss.dropna(subset=["Max_pct_AS_Clipped"]).copy()
    if assessable_segments.empty:
        raise ValueError("No assessable segment stenosis values were found for CAD-RADS.")

    highest_row = assessable_segments.sort_values(
        ["Max_pct_AS_Clipped", "Segment_ID"], ascending=[False, True]
    ).iloc[0]
    highest_stenosis_pct = float(highest_row["Max_pct_AS_Clipped"])
    highest_stenosis_location = f"{highest_row['Segment_Name']} (segment {int(highest_row['Segment_ID'])})"
    max_segment_grade = int(assessable_segments["Stenosis_Severity_Grade"].max())
    has_total_occlusion = bool((assessable_segments["Max_pct_AS_Clipped"] >= 100).any())

    if has_total_occlusion:
        cad_rads_category = "5"
        cad_rads_rationale = "At least one segment has 100% stenosis: total coronary occlusion."
    elif lm_stenosis_50plus:
        cad_rads_category = "4B"
        cad_rads_rationale = "Left main stenosis is >=50%, meeting the CAD-RADS 4B criterion."
    elif three_vessel_severe_70:
        cad_rads_category = "4B"
        cad_rads_rationale = "RCA, LAD, and LCX each have at least one segment with >=70% stenosis."
    elif max_segment_grade <= 3:
        cad_rads_category = str(max_segment_grade)
        cad_rads_rationale = f"Highest segment severity grade is {max_segment_grade}."
    elif max_segment_grade == 4:
        cad_rads_category = "4A"
        cad_rads_rationale = "Severe stenosis is present, but CAD-RADS 4B criteria are not met."
    else:
        cad_rads_category = str(max_segment_grade)
        cad_rads_rationale = f"Highest segment severity grade is {max_segment_grade}."

    plaque_segments = ss.loc[ss["Max_pct_AS_Clipped"] > 0].copy()
    sis_score = int(plaque_segments["Segment_ID"].nunique())
    sis_denominator = sis_denominator_for_segment_summary(ss)

    if sis_score == 0:
        plaque_modifier = None
        plaque_category = "No visible plaque/stenosis"
    elif sis_score <= 2:
        plaque_modifier = "P1"
        plaque_category = "Mild plaque burden"
    elif sis_score <= 4:
        plaque_modifier = "P2"
        plaque_category = "Moderate plaque burden"
    elif sis_score <= 7:
        plaque_modifier = "P3"
        plaque_category = "Severe plaque burden"
    else:
        plaque_modifier = "P4"
        plaque_category = "Extensive plaque burden"

    final_cad_rads_code = f"CAD-RADS {cad_rads_category}"
    if plaque_modifier is not None:
        final_cad_rads_code = f"{final_cad_rads_code}/{plaque_modifier}"

    priority = RISK_PRIORITY_MAP[cad_rads_category]
    priority_risk_score = int(priority["Priority_Risk_Score"])  # type: ignore[arg-type]
    priority_risk_label = str(priority["Priority_Risk_Label"])

    sis_mod = f", {plaque_modifier}" if plaque_modifier else ""
    clinical_interpretation = (
        f"{cad_rads_rationale}\n\n"
        f"Plaque burden: {plaque_category} (SIS {sis_score} / {sis_denominator}{sis_mod}). "
        "Automated CAD-RADS 2.0 triage from CCTA-derived segment stenosis; confirm clinically."
    )

    patient_report = pd.DataFrame(
        [
            {
                "Sample_Name": "",
                "Final_CAD_RADS_Code": final_cad_rads_code,
                "CAD_RADS_Category": cad_rads_category,
                "CAD_RADS_Rationale": cad_rads_rationale,
                "Highest_Stenosis_Location": highest_stenosis_location,
                "Highest_Stenosis_pct_AS": highest_stenosis_pct,
                "Vessel_Involvement_Count_50plus": vessel_obstructive_count_50,
                "Severe_Vessel_Count_70plus": vessel_severe_count_70,
                "Left_Main_50plus": lm_stenosis_50plus,
                "Three_Vessel_Severe_70plus": three_vessel_severe_70,
                "SIS_Score": sis_score,
                "SIS_Denominator": sis_denominator,
                "Plaque_Modifier": plaque_modifier if plaque_modifier else "Not required",
                "Plaque_Category": plaque_category,
                "Priority_Risk_Score": priority_risk_score,
                "Priority_Risk_Label": priority_risk_label,
            }
        ]
    )

    return {
        "segment_summary_scoring": ss,
        "territory_summary": territory_summary,
        "unmapped_for_territories": unmapped_for_territories,
        "patient_report": patient_report,
        "cad_rads_category": cad_rads_category,
        "cad_rads_rationale": cad_rads_rationale,
        "final_cad_rads_code": final_cad_rads_code,
        "highest_stenosis_location": highest_stenosis_location,
        "highest_stenosis_pct": highest_stenosis_pct,
        "sis_score": sis_score,
        "sis_denominator": sis_denominator,
        "plaque_modifier": plaque_modifier,
        "plaque_category": plaque_category,
        "clinical_interpretation": clinical_interpretation,
        "priority_risk_score": priority_risk_score,
        "priority_risk_label": priority_risk_label,
        "vessel_obstructive_count_50": vessel_obstructive_count_50,
        "vessel_severe_count_70": vessel_severe_count_70,
    }


def render_patient_id_card_png(
    out_path: Path,
    sample_name: str,
    *,
    cad_rads_category: str,
    plaque_modifier: str | None,
    plaque_category: str,
    sis_score: int,
    sis_denominator: int,
    top_segments: pd.DataFrame,
    cad_rads_rationale: str,
    highest_location: str,
    highest_pct: float,
) -> None:
    """Clean CAD-RADS + SIS patient summary (matplotlib; CAD-RADS and SIS visually separated)."""
    sns.set_theme(style="ticks")
    fig = plt.figure(figsize=(11, 10), dpi=200)
    fig.patch.set_facecolor("#eef2f3")

    def _pill_axis(ax_bbox: tuple[float, float, float, float]) -> plt.Axes:
        ax_k = fig.add_axes(ax_bbox)
        ax_k.axis("off")
        return ax_k

    fig.text(0.5, 0.965, sample_name + " — Patient summary card", fontsize=15, ha="center", fontweight="bold", color="#1b4332")

    # Left: CAD-RADS category only
    ax_c = _pill_axis((0.07, 0.765, 0.41, 0.155))
    ax_c.add_patch(
        FancyBboxPatch(
            (0.04, 0.08),
            0.92,
            0.84,
            boxstyle="round,pad=0.02",
            linewidth=1.35,
            edgecolor="#0d47a1",
            facecolor="#ffffff",
            transform=ax_c.transAxes,
        )
    )
    ax_c.text(0.5, 0.75, "CAD-RADS category", fontsize=11, ha="center", va="center", color="#546e7a", transform=ax_c.transAxes)
    ax_c.text(0.5, 0.38, cad_rads_category, fontsize=38, ha="center", va="center", fontweight="bold", color="#0d47a1", transform=ax_c.transAxes)

    # Right: SIS (no P-letter here)
    ax_s = _pill_axis((0.52, 0.765, 0.41, 0.155))
    ax_s.add_patch(
        FancyBboxPatch(
            (0.04, 0.08),
            0.92,
            0.84,
            boxstyle="round,pad=0.02",
            linewidth=1.35,
            edgecolor="#2e7d32",
            facecolor="#ffffff",
            transform=ax_s.transAxes,
        )
    )
    ax_s.text(0.5, 0.75, "Segment involvement score (SIS)", fontsize=11, ha="center", va="center", color="#546e7a", transform=ax_s.transAxes)
    ax_s.text(
        0.5,
        0.42,
        str(sis_score),
        fontsize=44,
        ha="center",
        va="center",
        fontweight="bold",
        color="#14532d",
        transform=ax_s.transAxes,
    )
    ax_s.text(
        0.5,
        0.09,
        f"Atlas denominator for plaque burden tiers: {sis_denominator}",
        fontsize=9.5,
        ha="center",
        va="center",
        color="#546e7a",
        transform=ax_s.transAxes,
    )

    # Plaque line — separate row
    pm = plaque_modifier if plaque_modifier else "(none)"
    fig.text(
        0.5,
        0.695,
        f"Plaque burden modifier — {pm}",
        fontsize=12,
        ha="center",
        color="#37474f",
        fontweight="semibold",
    )
    fig.text(0.5, 0.665, plaque_category, fontsize=10.5, ha="center", color="#455a64", style="italic")

    fig.text(
        0.5,
        0.598,
        f"Peak stenosis · {highest_location} ({highest_pct:.2f}% AS)",
        fontsize=11,
        ha="center",
        color="#263238",
        fontweight="bold",
    )

    ax_tbl = fig.add_axes((0.08, 0.28, 0.84, 0.295))
    ax_tbl.axis("off")
    ax_tbl.text(0.0, 1.06, "Most affected segments", fontsize=11, fontweight="bold", color="#1b5e20", transform=ax_tbl.transAxes)
    disp = top_segments[
        ["Segment_ID", "Segment_Name", "Max_pct_AS_Clipped", "Stenosis_Severity_Label"]
    ].rename(columns={"Max_pct_AS_Clipped": "Max %AS"})
    if not disp.empty:
        disp = disp.copy()
        disp["Segment_ID"] = disp["Segment_ID"].astype("object")
        disp["Max %AS"] = disp["Max %AS"].map(lambda x: "" if pd.isna(x) else f"{float(x):.2f}")
        tab = ax_tbl.table(
            cellText=disp.values,
            colLabels=list(disp.columns),
            cellLoc="center",
            loc="upper center",
        )
        tab.auto_set_font_size(False)
        tab.set_fontsize(9)
        tab.scale(1.02, 1.42)
        for k, cell in tab.get_celld().items():
            if k[0] == 0:
                cell.set_facecolor("#dcefe0")
                cell.set_text_props(fontweight="bold")
    else:
        ax_tbl.text(0.5, 0.6, "(no segments to list)", fontsize=10, ha="center", va="center", transform=ax_tbl.transAxes)

    ax_footer = fig.add_axes((0.08, 0.05, 0.84, 0.205))
    ax_footer.axis("off")
    ax_footer.add_patch(
        FancyBboxPatch(
            (0.0, 0.06),
            1.0,
            0.88,
            boxstyle="round,pad=0.015",
            linewidth=1.0,
            edgecolor="#b0bec5",
            facecolor="#ffffff",
            transform=ax_footer.transAxes,
        )
    )
    ax_footer.text(0.04, 0.88, "Automated rationale (CAD-RADS 2.0 rules)", fontsize=10, fontweight="bold", transform=ax_footer.transAxes)
    wrapped_single = cad_rads_rationale.replace("\n", " ").strip()
    ax_footer.text(
        0.05,
        0.74,
        "\n".join(textwrap.wrap(wrapped_single, width=118)),
        fontsize=9.5,
        va="top",
        color="#37474f",
        linespacing=1.38,
        transform=ax_footer.transAxes,
    )

    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.patch.get_facecolor())
    plt.close(fig)
    sns.reset_defaults()


def run_cad_rads_export_phase(patient_id: str, segment_summary: pd.DataFrame) -> tuple[Path, Path, str]:
    """Write ``patient_report_*.xlsx`` + ``patient_id_card_*.png``."""
    sample_name = patient_id
    phase(logger, "3c", "CAD-RADS 2.0 · patient report")

    cad = compute_cad_rads_patient_level(segment_summary)
    patient_df = cad["patient_report"].copy()
    patient_df["Sample_Name"] = sample_name

    out_dir = BLOCK3_CADRADS_ROOT / sample_name
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"patient_report_{sample_name}.xlsx"

    ss_out = cad["segment_summary_scoring"].sort_values("Segment_ID")
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        patient_df.to_excel(writer, sheet_name="patient_report", index=False)
        cad["territory_summary"].to_excel(writer, sheet_name="territory_summary", index=False)
        ss_out.to_excel(writer, sheet_name="segment_summary", index=False)
        unm = cad["unmapped_for_territories"]
        if not unm.empty:
            unm.to_excel(writer, sheet_name="unmapped_segments", index=False)

    top_n = cad["segment_summary_scoring"].sort_values(
        ["Stenosis_Severity_Grade", "Max_pct_AS_Clipped", "Segment_ID"],
        ascending=[False, False, True],
    ).head(8)
    card_path = out_dir / f"patient_id_card_{sample_name}.png"
    render_patient_id_card_png(
        card_path,
        sample_name,
        cad_rads_category=str(cad["cad_rads_category"]),
        plaque_modifier=cad["plaque_modifier"] if cad["plaque_modifier"] else None,
        plaque_category=str(cad["plaque_category"]),
        sis_score=int(cad["sis_score"]),
        sis_denominator=int(cad["sis_denominator"]),
        top_segments=top_n,
        cad_rads_rationale=str(cad["cad_rads_rationale"]),
        highest_location=str(cad["highest_stenosis_location"]),
        highest_pct=float(cad["highest_stenosis_pct"]),
    )

    sub(logger, "CAD-RADS report → %s", short_path(report_path))
    sub(logger, "Patient ID card → %s", short_path(card_path))
    return report_path, card_path, str(cad["final_cad_rads_code"])


def _fmt_opt_pct(value: float | None) -> str:
    """Format optional float as ``'12.34'`` or ``'n/a'`` for log output."""
    return "n/a" if value is None else f"{float(value):.2f}"


def run_block3_synthetic(patient_id: str) -> Block3Outputs:
    """Label mirror + placeholder segment summary and CAD-RADS for synthetic validation cases."""
    t0 = time.perf_counter()
    sample_name = patient_id
    phase(logger, "3", "Synthetic clinical placeholders")

    label_dir = run_block3_phase1(patient_id, emit_footer=False)

    tree_path = resolve_global_tree_path(sample_name)
    df_tree = pd.read_excel(tree_path)
    pct_col = resolve_pct_as_column(df_tree)
    max_pct = float(df_tree[pct_col].max()) if len(df_tree) else float("nan")
    if not np.isfinite(max_pct):
        max_pct = float("nan")

    seg_summary = pd.DataFrame(
        [
            {
                "Segment_ID": SYNTHETIC_SEGMENT_ID,
                "Segment_Name": SYNTHETIC_SEGMENT_NAME,
                "Artery_Type": SYNTHETIC_ARTERY,
                "max_pct_AS": max_pct,
                "Stenosis_Severity_Grade": pd.NA,
                "Stenosis_Severity_Label": "Synthetic validation (not scored)",
                "n_points": int(len(df_tree)),
            }
        ]
    )
    st_dir = BLOCK3_SEGMENT_STENOSIS_ROOT / sample_name
    st_dir.mkdir(parents=True, exist_ok=True)
    st_path = st_dir / f"stenosis_summary_{sample_name}.xlsx"
    seg_summary.to_excel(st_path, index=False)

    cad_dir = BLOCK3_CADRADS_ROOT / sample_name
    cad_dir.mkdir(parents=True, exist_ok=True)
    na_label = SYNTHETIC_CAD_RADS_LABEL
    patient_report = pd.DataFrame(
        [
            {
                "Sample_Name": sample_name,
                "Final_CAD_RADS_Code": na_label,
                "CAD_RADS_Category": na_label,
                "CAD_RADS_Rationale": (
                    "Synthetic single-tube validation case. Clinical CAD-RADS 2.0 scoring "
                    "and territory rules are not applicable."
                ),
                "Highest_Stenosis_Location": SYNTHETIC_SEGMENT_NAME,
                "Highest_Stenosis_pct_AS": max_pct,
                "Vessel_Involvement_Count_50plus": pd.NA,
                "Severe_Vessel_Count_70plus": pd.NA,
                "Left_Main_50plus": pd.NA,
                "Three_Vessel_Severe_70plus": pd.NA,
                "SIS_Score": pd.NA,
                "SIS_Denominator": pd.NA,
                "Plaque_Modifier": "N/A",
                "Plaque_Category": "N/A (Synthetic)",
                "Priority_Risk_Score": pd.NA,
                "Priority_Risk_Label": "N/A (Synthetic)",
            }
        ]
    )
    report_path = cad_dir / f"patient_report_{sample_name}.xlsx"
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        patient_report.to_excel(writer, sheet_name="patient_report", index=False)

    validation = synthetic_validation_metrics(df_tree, sample_name)
    summary_json = {
        "patient_id": sample_name,
        "is_synthetic": True,
        "is_stenosis_synthetic": bool(is_stenosis_synthetic_patient(sample_name)),
        "cad_rads_category": na_label,
        "final_cad_rads_code": na_label,
        "highest_stenosis_location": SYNTHETIC_SEGMENT_NAME,
        "highest_stenosis_pct_as": None if not np.isfinite(max_pct) else float(max_pct),
        "sis_score": None,
        "clinical_scores_note": "Placeholder — synthetic validation only.",
        "validation_metrics": validation,
    }
    json_path = cad_dir / f"summary_metrics_{sample_name}.json"
    json_path.write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    if validation.get("ok"):
        if validation["is_stenosis"]:
            sub(
                logger,
                "Validation (Synthetic_2): max %%AS theo=%.2f pred=%s err=%s · "
                "Area max theo=%.2f pred=%.2f · min theo=%.2f pred=%.2f mm^2",
                validation["theoretical_max_pct_as"],
                _fmt_opt_pct(validation["predicted_max_pct_as"]),
                _fmt_opt_pct(validation["abs_error_max_pct_as"]),
                validation["theoretical_max_area_mm2"],
                validation["predicted_max_area_mm2"],
                validation["theoretical_min_area_mm2"],
                validation["predicted_min_area_mm2"],
            )
        else:
            sub(
                logger,
                "Validation (Synthetic_1): %%AS theo=0.00 pred=%s err=%s · "
                "mean |dA|=%.2f mm^2 · max |dA|=%.2f mm^2",
                _fmt_opt_pct(validation["predicted_max_pct_as"]),
                _fmt_opt_pct(validation["abs_error_max_pct_as"]),
                validation["mean_area_abs_error_mm2"],
                validation["max_area_abs_deviation_mm2"],
            )
    else:
        sub(logger, "Validation metrics unavailable (%s)", validation.get("reason", "unknown"))

    card_path = cad_dir / f"patient_id_card_{sample_name}.png"
    if not card_path.exists():
        fig, ax = plt.subplots(figsize=(8, 3), dpi=150)
        ax.axis("off")
        ax.text(
            0.5,
            0.55,
            sample_name,
            ha="center",
            va="center",
            fontsize=16,
            fontweight="bold",
        )
        ax.text(
            0.5,
            0.35,
            na_label,
            ha="center",
            va="center",
            fontsize=12,
            color="#555555",
        )
        fig.savefig(card_path, bbox_inches="tight", facecolor="#eef2f3")
        plt.close(fig)

    sub(logger, "Synthetic CAD-RADS: %s", na_label)
    sub(logger, "Summary JSON → %s", short_path(json_path))

    footer_block(
        logger,
        block_id="3",
        title="synthetic placeholders",
        seconds=time.perf_counter() - t0,
        parts=[short_path(label_dir), short_path(st_path.parent), na_label],
    )
    return Block3Outputs(
        label_dir=label_dir,
        stenosis_summary_path=st_path,
        patient_report_path=report_path,
        patient_id_card_path=card_path,
        final_cad_rads_code=na_label,
    )


def run_block3(patient_id: str, *, is_synthetic: bool = False) -> Block3Outputs:
    """
    Full Block 3: phase 1 labels/QC, segment stenosis table, CAD-RADS + exports.

    Terminal log ends with the final CAD-RADS string (``sub``).
    """
    if is_synthetic or is_synthetic_patient(patient_id):
        return run_block3_synthetic(patient_id)

    t0 = time.perf_counter()
    sample_name = patient_id

    segment_dictionary = build_scct18_segment_dictionary()

    label_dir = run_block3_phase1(patient_id, emit_footer=False)
    seg_summary, st_path = run_segment_stenosis_phase(patient_id, segment_dictionary)

    report_path, card_path, final_code = run_cad_rads_export_phase(patient_id, seg_summary)

    sub(logger, "Final CAD-RADS: %s", final_code)

    footer_block(
        logger,
        block_id="3",
        title="label · segment stenosis · CAD-RADS",
        seconds=time.perf_counter() - t0,
        parts=[
            short_path(label_dir),
            short_path(st_path.parent),
            short_path(report_path.parent),
            final_code,
        ],
    )
    return Block3Outputs(
        label_dir=label_dir,
        stenosis_summary_path=st_path,
        patient_report_path=report_path,
        patient_id_card_path=card_path,
        final_cad_rads_code=final_code,
    )


__all__ = [
    "run_block3",
    "run_block3_phase1",
    "Block3Outputs",
    "build_scct18_segment_dictionary",
]
