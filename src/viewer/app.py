"""
Streamlit entrypoint for Block 4 visualization.
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.viewer.plots import (
    create_3d_artery_plot,
    create_3d_mesh_branch_path_highlight,
    create_branch_centerline_metric_bars,
    discover_block3_label_branch_xlsx,
    load_concat_branch_centerlines,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEWER_FIGURES = Path(__file__).resolve().parent / "figures"
SESSION_PATH = PROJECT_ROOT / "results" / "current_session.json"

_SANT_PAU_LOGO_NAMES = (
    "sant pau logo.png",
    "sant_pau_logo.png",
    "sant-pau-logo.png",
    "Sant Pau logo.png",
)
_UPF_LOGO_NAMES = ("UPFt_rgb.png", "upf_rgb.png", "UPFt.png", "UPF_logo.png")


def _resolve_header_logo(names: tuple[str, ...]) -> Path | None:
    """First existing file under ``viewer/figures`` (handles renames / saves)."""
    for name in names:
        candidate = VIEWER_FIGURES / name
        if candidate.is_file():
            return candidate.resolve()
    return None


def _logo_data_uri(path: Path) -> str:
    """Inline image for header HTML (avoids Streamlit column DOM / stImage alignment quirks)."""
    ext = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"

AUTHOR_NAME = "Adrià Cortés Cugat"
DEGREE_NAME = "Mathematical Engineering in Data Science"

# Typography: Inter via Google Fonts; global CSS also sets a neutral dark app background.
_APP_STYLE = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    html, body {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        background-color: #121212 !important;
    }
    [class*="css"] {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
    }
    /* Neutral dark shell (Streamlit default dark theme reads blue-gray) */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > div,
    section[data-testid="stMain"],
    section[data-testid="stMain"] > div {
        background-color: #121212 !important;
    }
    header[data-testid="stHeader"] {
        background-color: #121212 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #161616 !important;
    }
    /* Header logos: raw HTML row (not st.columns) so UPF truly hugs the right edge */
    .header-logo-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
        min-height: 5rem;
        box-sizing: border-box;
    }
    .header-logo-row img.header-logo-sant-pau {
        height: 5rem;
        max-height: 5rem;
        width: auto;
        max-width: min(58vw, 560px);
        object-fit: contain;
        flex-shrink: 0;
        border-radius: 0.5rem;
        margin: 0;
        display: block;
    }
    .header-logo-row img.header-logo-upf {
        height: 5rem;
        max-height: 5rem;
        width: auto;
        max-width: min(58vw, 560px);
        object-fit: contain;
        flex-shrink: 0;
        margin: 0;
        display: block;
    }
    hr.title-above-rule,
    hr.title-below-rule {
        border: none !important;
        border-top: 1px solid #3d3d3d !important;
        height: 0 !important;
        background: transparent !important;
    }
    .logo-below-spacer {
        height: 0.85rem;
        min-height: 0.85rem;
        margin: 0;
        padding: 0;
        line-height: 0;
        font-size: 0;
        overflow: hidden;
        pointer-events: none;
    }
    hr.title-above-rule {
        margin: 0.35rem 0 1rem 0 !important;
    }
    hr.title-below-rule {
        margin: 0.5rem 0 0.55rem 0 !important;
    }
    hr.section-divider-branch-viz {
        border: none !important;
        border-top: 1px solid #3d3d3d !important;
        height: 0 !important;
        background: transparent !important;
        margin: 1.35rem 0 1.85rem 0 !important;
    }
    .branch-viz-title-spacer {
        height: 0.65rem;
        min-height: 0.65rem;
        margin: 0;
        padding: 0;
        line-height: 0;
        font-size: 0;
        overflow: hidden;
        pointer-events: none;
    }
    .branch-viz-artery-row-spacer {
        height: 0.85rem;
        min-height: 0.85rem;
        margin: 0;
        padding: 0;
        line-height: 0;
        font-size: 0;
        overflow: hidden;
        pointer-events: none;
    }
    .coronary-main-title {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 700;
        letter-spacing: 0.06em;
        line-height: 1.1;
        margin-top: 0.35rem;
        margin-bottom: 0 !important;
        padding-bottom: 0.45rem !important;
        color: #f2f2f2 !important;
        /* Large, responsive headline */
        font-size: clamp(2.5rem, 5.5vw, 4.25rem) !important;
    }
    /* Full-viewport width strip (breaks out of Streamlit main column padding) */
    .coronary-main-subtitle-wrap {
        width: 100vw;
        max-width: 100vw;
        margin-left: calc(50% - 50vw);
        margin-right: calc(50% - 50vw);
        margin-bottom: 0.85rem;
        padding-left: 1rem;
        padding-right: 1rem;
        box-sizing: border-box;
    }
    p.coronary-main-subtitle {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.03em;
        line-height: 1.45;
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        max-width: none !important;
        box-sizing: border-box !important;
        text-align: center;
        color: #bdbdbd !important;
        font-size: clamp(0.95rem, 0.82rem + 0.45vw, 1.08rem) !important;
    }
    /* Gap below lower title rule before colormap buttons */
    .title-to-controls-spacer {
        height: 1.75rem;
        min-height: 1.75rem;
        margin: 0;
        padding: 0;
        line-height: 0;
        font-size: 0;
        overflow: hidden;
        pointer-events: none;
    }
    h3.artery-plot-title {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        text-align: center;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin: 0 0 0.75rem 0;
        font-size: clamp(1.35rem, 1rem + 1.1vw, 1.65rem);
        color: #e8e8e8 !important;
    }
    /* Same size as section plot titles; left-aligned for branch picker column */
    h3.artery-plot-title.branch-panel-heading {
        text-align: left !important;
    }
    h3.artery-plot-title.branch-viz-heading-above-plot {
        text-align: left !important;
    }
    /* Push right-column “Branches” down to line up with plot (after title + LCA/RCA on left) */
    .branch-panel-align-with-plot-spacer {
        height: 10.85rem;
        min-height: 10.85rem;
        margin: 0;
        padding: 0;
        line-height: 0;
        font-size: 0;
        overflow: hidden;
        pointer-events: none;
    }
    /* Colormap + branch artery toggles: selected = orange, unselected = neutral tile */
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"],
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"],
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"],
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"] {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        line-height: 1.2 !important;
        font-size: 0.95rem !important;
        min-height: 3.75rem !important;
        padding: 1rem 1.25rem !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 0.5rem !important;
        background-color: #f57c00 !important;
        background-image: none !important;
        box-shadow: 0 0 0 2px rgba(255, 183, 77, 0.45) !important;
        outline: none !important;
        transition: background-color 0.18s ease, box-shadow 0.18s ease !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"],
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"],
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"],
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"] {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        line-height: 1.2 !important;
        font-size: 0.95rem !important;
        min-height: 3.75rem !important;
        padding: 1rem 1.25rem !important;
        color: #bdbdbd !important;
        border: 1px solid #5a5a5a !important;
        border-radius: 0.5rem !important;
        background-color: #353535 !important;
        background-image: none !important;
        box-shadow: none !important;
        outline: none !important;
        transition: background-color 0.18s ease, border-color 0.18s ease !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"] p,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"] p,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"] p,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"] p,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"] span,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"] span,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"] span,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"] span,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"] div,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"] div,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"] div,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"] div {
        font-family: inherit !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        line-height: 1.12 !important;
        font-size: clamp(1.05rem, 0.58rem + 1.7vw, 1.35rem) !important;
        color: #ffffff !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"] p,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"] p,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"] p,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"] p,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"] span,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"] span,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"] div,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"] div,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"] div,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"] div {
        font-family: inherit !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        line-height: 1.12 !important;
        font-size: clamp(0.95rem, 0.52rem + 1.35vw, 1.15rem) !important;
        color: #bdbdbd !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"]:hover,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"]:hover,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"]:hover,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"]:hover {
        filter: none !important;
        background-color: #ffb74d !important;
        background-image: none !important;
        color: #ffffff !important;
        box-shadow: 0 0 0 2px rgba(255, 224, 178, 0.55) !important;
        outline: none !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"]:hover,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"]:hover,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"]:hover,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"]:hover {
        filter: none !important;
        background-color: #424242 !important;
        border-color: #757575 !important;
        color: #e0e0e0 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"]:focus-visible {
        filter: none !important;
        background-color: #ffb74d !important;
        outline: none !important;
        box-shadow: 0 0 0 2px rgba(255, 224, 178, 0.55) !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"]:focus-visible {
        filter: none !important;
        background-color: #424242 !important;
        outline: none !important;
        box-shadow: none !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"]:active,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"]:active {
        filter: none !important;
        background-color: #e65100 !important;
        color: #ffffff !important;
        box-shadow: none !important;
        outline: none !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"]:active {
        filter: none !important;
        background-color: #2d2d2d !important;
        color: #ffffff !important;
        box-shadow: none !important;
        outline: none !important;
    }
    /* Branch list: selected = orange + ring, unselected = dark neutral */
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"],
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em !important;
        line-height: 1.2 !important;
        min-height: 2.5rem !important;
        padding: 0.45rem 0.65rem !important;
        border-radius: 0.45rem !important;
        outline: none !important;
        transition: background-color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"] {
        color: #ffffff !important;
        border: none !important;
        background-color: #f57c00 !important;
        background-image: none !important;
        box-shadow: 0 0 0 2px rgba(255, 183, 77, 0.45) !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] {
        color: #bdbdbd !important;
        border: 1px solid #5a5a5a !important;
        background-color: #353535 !important;
        background-image: none !important;
        box-shadow: none !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"] p,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"] span,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"] div {
        color: #ffffff !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] p,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] span,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] div {
        color: #bdbdbd !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"]:hover {
        background-color: #ffb74d !important;
        box-shadow: 0 0 0 2px rgba(255, 224, 178, 0.55) !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"]:hover {
        background-color: #424242 !important;
        border-color: #757575 !important;
        color: #e0e0e0 !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"]:focus-visible {
        outline: none !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"]:active {
        background-color: #e65100 !important;
        box-shadow: none !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"]:active {
        background-color: #2d2d2d !important;
        color: #ffffff !important;
    }
    /* Reset view (LCA/RCA/branch viz): Sant Pau–style cyan blue, bold label */
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="primary"],
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="secondary"],
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="primary"],
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="secondary"],
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="primary"],
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="secondary"] {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
        background-color: #0092c7 !important;
        background-image: none !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: none !important;
        border-radius: 0.5rem !important;
        outline: none !important;
        transition: background-color 0.18s ease !important;
    }
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="primary"] p,
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="secondary"] p,
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="primary"] p,
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="secondary"] p,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="primary"] p,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="secondary"] p,
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="primary"] span,
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="primary"] span,
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="primary"] span,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="secondary"] span {
        font-family: inherit !important;
        font-weight: 700 !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
        color: #ffffff !important;
    }
    [class*="st-key-"][class*="reset_btn_lca"] button:hover,
    [class*="st-key-"][class*="reset_btn_rca"] button:hover,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button:hover {
        background-color: #33b5e0 !important;
        background-image: none !important;
        color: #ffffff !important;
    }
    [class*="st-key-"][class*="reset_btn_lca"] button:focus-visible,
    [class*="st-key-"][class*="reset_btn_rca"] button:focus-visible,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button:focus-visible {
        background-color: #33b5e0 !important;
        background-image: none !important;
    }
    [class*="st-key-"][class*="reset_btn_lca"] button:active,
    [class*="st-key-"][class*="reset_btn_rca"] button:active,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button:active {
        background-color: #007099 !important;
        background-image: none !important;
        color: #ffffff !important;
    }
    /* Bottom-of-page author / degree lines — centered in the main content width */
    .footer-app-meta {
        text-align: center !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 0.35rem auto 0 auto !important;
        padding: 0 1rem 1.25rem 1rem !important;
        box-sizing: border-box !important;
    }
    .footer-app-meta p {
        margin: 0.2rem 0 !important;
        padding: 0 !important;
        color: #a3a3a3 !important;
        font-size: 0.875rem !important;
        line-height: 1.45 !important;
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
    }
</style>
"""


def _load_patient_id() -> str | None:
    if not SESSION_PATH.exists():
        return None
    try:
        payload = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    patient_id = payload.get("patient_id")
    if isinstance(patient_id, str) and patient_id.strip():
        return patient_id.strip()
    return None


def _resolve_total_df_path(patient_id: str) -> Path | None:
    """Prefer Block 3 label export; fall back to Block 2 stenosis merged table."""
    candidates = [
        PROJECT_ROOT / "results" / "block3_results" / "label" / patient_id / f"total_df_{patient_id}.xlsx",
        PROJECT_ROOT / "results" / "block2_results" / "stenosis" / patient_id / f"total_df_{patient_id}.xlsx",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _sort_centerline_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Order points along vessels (matches pipeline branch ordering when columns exist)."""
    if df.empty:
        return df
    cols: list[str] = []
    if "Branch_ID" in df.columns:
        cols.append("Branch_ID")
    if "gd" in df.columns:
        return df.sort_values(cols + ["gd"], ascending=True).reset_index(drop=True)
    if "Path_Point_Index" in df.columns:
        return df.sort_values(cols + ["Path_Point_Index"], ascending=True).reset_index(drop=True)
    return df.sort_values(["Px", "Py", "Pz"]).reset_index(drop=True)


def _set_branch_viz_selected_branch(bid: str) -> None:
    """Session update before script body so the plot column sees the new branch on one click."""
    st.session_state.branch_viz_selected = bid


def _filter_artery(df: pd.DataFrame, artery: str) -> pd.DataFrame:
    if "Artery_Type" not in df.columns:
        raise ValueError("Column Artery_Type is required to split LCA/RCA.")
    mask = df["Artery_Type"].astype(str).str.upper() == artery.upper()
    return df.loc[mask].copy()


def main() -> None:
    st.set_page_config(layout="wide")

    if "reset_lca" not in st.session_state:
        st.session_state.reset_lca = 0
    if "reset_rca" not in st.session_state:
        st.session_state.reset_rca = 0
    if "reset_branch_viz" not in st.session_state:
        st.session_state.reset_branch_viz = 0
    if "branch_viz_artery" not in st.session_state:
        st.session_state.branch_viz_artery = "LCA"
    if "branch_viz_selected" not in st.session_state:
        st.session_state.branch_viz_selected = None
    if "color_column" not in st.session_state:
        st.session_state.color_column = "pct_AS"

    patient_id = _load_patient_id()
    if patient_id is None:
        st.warning(
            "No active session found at results/current_session.json. "
            "Run the pipeline first to select a patient."
        )
        patient_id = "Unknown Patient"

    st.markdown(_APP_STYLE, unsafe_allow_html=True)

    logo_sant_pau = _resolve_header_logo(_SANT_PAU_LOGO_NAMES)
    logo_upf = _resolve_header_logo(_UPF_LOGO_NAMES)
    if logo_sant_pau is None or logo_upf is None:
        _missing = [n for n, p in (("Sant Pau", logo_sant_pau), ("UPF", logo_upf)) if p is None]
        st.caption(
            f"Missing header logo(s): {', '.join(_missing)}. "
            f"Place images in `{VIEWER_FIGURES}` (e.g. `sant pau logo.png`, `UPFt_rgb.png`)."
        )

    if logo_sant_pau is not None or logo_upf is not None:
        _imgs: list[str] = []
        if logo_sant_pau is not None:
            _sp = html.escape(_logo_data_uri(logo_sant_pau), quote=True)
            _imgs.append(
                f'<img class="header-logo-sant-pau" alt="Sant Pau" src="{_sp}" />'
            )
        if logo_upf is not None:
            _up = html.escape(_logo_data_uri(logo_upf), quote=True)
            _imgs.append(
                f'<img class="header-logo-upf" alt="Universitat Pompeu Fabra" src="{_up}" />'
            )
        _n = len(_imgs)
        if _n == 2:
            _justify = "space-between"
        elif logo_upf is not None:
            _justify = "flex-end"
        else:
            _justify = "flex-start"
        st.markdown(
            f'<div class="header-logo-row" style="justify-content:{_justify};">'
            f'{"".join(_imgs)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="logo-below-spacer" aria-hidden="true">&nbsp;</div>',
        unsafe_allow_html=True,
    )

    title_safe = html.escape(patient_id, quote=True)
    st.markdown(
        "<hr class='title-above-rule' aria-hidden='true'>"
        f"<h1 class='coronary-main-title' style='text-align: center; text-transform: uppercase;'>"
        f"Coronary Analysis: {title_safe}</h1>"
        "<div class='coronary-main-subtitle-wrap'>"
        "<p class='coronary-main-subtitle'>"
        "This tool integrates interactive 3D coronary anatomy with automated metrics to serve as a "
        "clinical decision-support aid. It is designed to streamline structured reviews and reduce "
        "assessment time, while all final diagnostic and treatment decisions remain strictly with the "
        "medical team."
        "</p></div>"
        "<hr class='title-below-rule' aria-hidden='true'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="title-to-controls-spacer" aria-hidden="true">&nbsp;</div>',
        unsafe_allow_html=True,
    )

    pad_l, box_pct, box_area, pad_r = st.columns([1, 2, 2, 1], gap="medium")
    with box_pct:
        is_pct = st.session_state.color_column == "pct_AS"
        if st.button(
            "PERCENT AREA STENOSIS (%AS)",
            key="color_btn_pct_as",
            use_container_width=True,
            type="primary" if is_pct else "secondary",
        ):
            st.session_state.color_column = "pct_AS"
    with box_area:
        is_area = st.session_state.color_column == "Area"
        if st.button(
            "CROSS-SECTIONAL AREA",
            key="color_btn_area",
            use_container_width=True,
            type="primary" if is_area else "secondary",
        ):
            st.session_state.color_column = "Area"
    color_column = st.session_state.color_column

    plotly_config = {
        "displayModeBar": True,
        "displaylogo": False,
        "scrollZoom": True,
    }

    if patient_id != "Unknown Patient":
        total_path = _resolve_total_df_path(patient_id)
        mesh_lca = PROJECT_ROOT / "results" / "block1_results" / patient_id / "surface_LCA.vtp"
        mesh_rca = PROJECT_ROOT / "results" / "block1_results" / patient_id / "surface_RCA.vtp"

        if total_path is None:
            st.warning(
                f"Could not find total_df spreadsheet for patient {patient_id!r}. "
                "Expected under results/block3_results/label/ or results/block2_results/stenosis/."
            )
        else:
            try:
                total_df = pd.read_excel(total_path)
            except Exception as e:
                st.error(f"Failed to read {total_path}: {e}")
                total_df = None

            if total_df is not None:
                col_lca, col_rca = st.columns(2, gap="small", vertical_alignment="top")
                with col_lca:
                    st.markdown(
                        "<h3 class='artery-plot-title'>Left Coronary Artery (LCA)</h3>",
                        unsafe_allow_html=True,
                    )
                    try:
                        df_lca = _sort_centerline_subset(_filter_artery(total_df, "LCA"))
                        if df_lca.empty:
                            st.warning("LCA data not found or could not be loaded for this patient.")
                        else:
                            fig_lca = create_3d_artery_plot(
                                str(mesh_lca),
                                df_lca,
                                color_column,
                                trace_name="LCA",
                            )
                            _chart_kwargs = dict(
                                use_container_width=True,
                                config=plotly_config,
                                key=f"lca_plot_{st.session_state.reset_lca}",
                            )
                            try:
                                st.plotly_chart(fig_lca, **_chart_kwargs)
                            except TypeError:
                                _chart_kwargs.pop("key", None)
                                st.plotly_chart(fig_lca, **_chart_kwargs)
                            rl1, rl2, rl3 = st.columns([2, 1, 2])
                            with rl2:
                                if st.button("RESET VIEW", key="reset_btn_lca"):
                                    st.session_state.reset_lca += 1
                    except Exception:
                        st.warning("LCA data not found or could not be loaded for this patient.")

                with col_rca:
                    st.markdown(
                        "<h3 class='artery-plot-title'>Right Coronary Artery (RCA)</h3>",
                        unsafe_allow_html=True,
                    )
                    try:
                        df_rca = _sort_centerline_subset(_filter_artery(total_df, "RCA"))
                        if df_rca.empty:
                            st.warning("RCA data not found or could not be loaded for this patient.")
                        else:
                            fig_rca = create_3d_artery_plot(
                                str(mesh_rca),
                                df_rca,
                                color_column,
                                trace_name="RCA",
                            )
                            _chart_kwargs_r = dict(
                                use_container_width=True,
                                config=plotly_config,
                                key=f"rca_plot_{st.session_state.reset_rca}",
                            )
                            try:
                                st.plotly_chart(fig_rca, **_chart_kwargs_r)
                            except TypeError:
                                _chart_kwargs_r.pop("key", None)
                                st.plotly_chart(fig_rca, **_chart_kwargs_r)
                            rr1, rr2, rr3 = st.columns([2, 1, 2])
                            with rr2:
                                if st.button("RESET VIEW", key="reset_btn_rca"):
                                    st.session_state.reset_rca += 1
                    except Exception:
                        st.warning("RCA data not found or could not be loaded for this patient.")

                st.markdown(
                    "<hr class='section-divider-branch-viz' aria-hidden='true'>",
                    unsafe_allow_html=True,
                )
                # --- Branch path viewer (LCA/RCA, Block 3 branch spreadsheets) ---
                # Left: section title + LCA/RCA above the 3D plot; right: branch list (offset to plot top)
                row2_l, row2_r = st.columns([2.85, 2.55], gap="medium", vertical_alignment="top")
                with row2_l:
                    st.markdown(
                        "<h3 class='artery-plot-title branch-viz-heading-above-plot'>"
                        "Coronary branch paths</h3>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        '<div class="branch-viz-title-spacer" aria-hidden="true">&nbsp;</div>',
                        unsafe_allow_html=True,
                    )
                    _ab_lca, _ab_rca = st.columns(2, gap="small")
                    with _ab_lca:
                        if st.button(
                            "LCA",
                            key="branch_viz_btn_lca",
                            use_container_width=True,
                            type="primary"
                            if str(st.session_state.branch_viz_artery).strip().upper() == "LCA"
                            else "secondary",
                        ):
                            st.session_state.branch_viz_artery = "LCA"
                            st.session_state.branch_viz_selected = None
                    with _ab_rca:
                        if st.button(
                            "RCA",
                            key="branch_viz_btn_rca",
                            use_container_width=True,
                            type="primary"
                            if str(st.session_state.branch_viz_artery).strip().upper() == "RCA"
                            else "secondary",
                        ):
                            st.session_state.branch_viz_artery = "RCA"
                            st.session_state.branch_viz_selected = None
                    st.markdown(
                        '<div class="branch-viz-artery-row-spacer" aria-hidden="true">&nbsp;</div>',
                        unsafe_allow_html=True,
                    )
                    # Re-read artery after button clicks (same run)
                    _bv_art = str(st.session_state.branch_viz_artery).strip().upper()
                    if _bv_art not in ("LCA", "RCA"):
                        _bv_art = "LCA"
                        st.session_state.branch_viz_artery = _bv_art
                    _bv_mesh = mesh_lca if _bv_art == "LCA" else mesh_rca
                    branch_pairs = discover_block3_label_branch_xlsx(PROJECT_ROOT, patient_id, _bv_art)
                    branch_df_all = load_concat_branch_centerlines(branch_pairs)
                    _branch_viz_ok = (
                        bool(branch_pairs)
                        and not branch_df_all.empty
                        and _bv_mesh.is_file()
                        and {"Px", "Py", "Pz", "pct_AS", "Branch_ID"}.issubset(branch_df_all.columns)
                    )
                    if not _branch_viz_ok:
                        if not branch_pairs or branch_df_all.empty:
                            st.caption(
                                f"No {_bv_art} branch spreadsheets under "
                                f"`results/block3_results/label/{patient_id}/branches/dataframes/` "
                                f"(expected `dataset_{_bv_art}_B##_{patient_id}.xlsx`)."
                            )
                        elif not _bv_mesh.is_file():
                            st.caption(f"{_bv_art} surface mesh missing; branch path viewer skipped.")
                        else:
                            st.warning(
                                "Branch dataframes are missing required columns "
                                "(Px, Py, Pz, pct_AS, Branch_ID). Cannot build branch highlight plot."
                            )
                    else:
                        branch_ids = [b for b, _ in branch_pairs]
                        if (
                            st.session_state.branch_viz_selected is None
                            or st.session_state.branch_viz_selected not in branch_ids
                        ):
                            st.session_state.branch_viz_selected = branch_ids[0]
                        _sel_bid = st.session_state.branch_viz_selected

                        try:
                            fig_br = create_3d_mesh_branch_path_highlight(
                                str(_bv_mesh),
                                branch_df_all,
                                selected_branch_id=str(_sel_bid),
                                trace_name=_bv_art,
                            )
                            _bk = dict(
                                use_container_width=True,
                                config=plotly_config,
                                key=(
                                    f"branch_viz_plot_{st.session_state.reset_branch_viz}_"
                                    f"{_bv_art}_{_sel_bid}"
                                ),
                            )
                            try:
                                st.plotly_chart(fig_br, **_bk)
                            except TypeError:
                                _bk.pop("key", None)
                                st.plotly_chart(fig_br, **_bk)
                            br1, br2, br3 = st.columns([2, 1, 2])
                            with br2:
                                if st.button("RESET VIEW", key="reset_btn_branch_viz"):
                                    st.session_state.reset_branch_viz += 1
                        except Exception as e:
                            st.warning(f"Branch path visualization could not be built: {e}")

                with row2_r:
                    st.markdown(
                        '<div class="branch-panel-align-with-plot-spacer" aria-hidden="true">&nbsp;</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        "<h3 class='artery-plot-title branch-panel-heading'>Branches</h3>",
                        unsafe_allow_html=True,
                    )
                    if _branch_viz_ok:
                        _sel_r = st.session_state.branch_viz_selected
                        for bid, _p in branch_pairs:
                            st.button(
                                bid,
                                key=f"branch_pick_btn_{_bv_art}_{bid}",
                                use_container_width=True,
                                type="primary" if _sel_r == bid else "secondary",
                                on_click=_set_branch_viz_selected_branch,
                                args=(bid,),
                            )
                    elif not branch_pairs:
                        st.caption("No branch files for this artery.")
                    else:
                        st.caption("Load branch tables or mesh to enable selection.")

                if _branch_viz_ok:
                    st.markdown(
                        '<div class="branch-viz-artery-row-spacer" aria-hidden="true">&nbsp;</div>',
                        unsafe_allow_html=True,
                    )
                    try:
                        _sel_prof = str(st.session_state.branch_viz_selected)
                        fig_prof = create_branch_centerline_metric_bars(
                            branch_df_all,
                            selected_branch_id=_sel_prof,
                            artery=_bv_art,
                        )
                        _prof_kw = dict(
                            use_container_width=True,
                            config=plotly_config,
                            key=(
                                f"branch_profile_bars_{patient_id}_{_bv_art}_{_sel_prof}_"
                                f"{st.session_state.reset_branch_viz}"
                            ),
                        )
                        try:
                            st.plotly_chart(fig_prof, **_prof_kw)
                        except TypeError:
                            _prof_kw.pop("key", None)
                            st.plotly_chart(fig_prof, **_prof_kw)
                    except Exception as ex_prof:
                        st.caption(f"Along-branch %AS / Area charts could not be built: {ex_prof}")

    st.markdown("---")
    _au_f = html.escape(AUTHOR_NAME, quote=True)
    _deg_f = html.escape(DEGREE_NAME, quote=True)
    st.markdown(
        "<div class='footer-app-meta'>"
        f"<p>Author: {_au_f}</p>"
        f"<p>Degree: {_deg_f}</p>"
        "<p>Final Degree Project (TFG)</p>"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
