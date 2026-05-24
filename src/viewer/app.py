"""
Streamlit entrypoint for Block 4 visualization.
"""

from __future__ import annotations

import base64
import html
import importlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_VIEWER_PLOTS = "src.viewer.plots"
_VIEWER_SYNTHETIC_UI = "src.viewer.synthetic_ui"
_SYNTHETIC_PROFILE = "src.synthetic_profile"
_STENOSIS_BLOCK = "src.blocks._02_stenosis"

# Reload order: Block 2 imports synthetic_profile; viewer imports Block 2 constants.
_MODULE_RELOAD_ORDER: tuple[str, ...] = (
    _SYNTHETIC_PROFILE,
    _STENOSIS_BLOCK,
    _VIEWER_PLOTS,
    _VIEWER_SYNTHETIC_UI,
)


def _module_file_mtime(mod_name: str) -> float | None:
    spec = importlib.util.find_spec(mod_name)
    if spec is None or not getattr(spec, "origin", None):
        return None
    path = Path(str(spec.origin))
    if not path.is_file():
        return None
    return path.stat().st_mtime


def _reload_modules_in_order(mod_names: tuple[str, ...]) -> None:
    for mod_name in mod_names:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


def _ensure_viewer_modules_fresh() -> None:
    """
    Streamlit re-executes this script on each run, but Python keeps imported modules in
    ``sys.modules``. Reload pipeline/viewer modules when Block 2 (or dependencies) change on
    disk so ``WINDOW_MM`` and viewer code stay in sync without restarting the server.
    """
    stenosis_mtime = _module_file_mtime(_STENOSIS_BLOCK)
    last_stenosis_mtime = st.session_state.get("_pipeline_stenosis_mtime")

    for mod_name in _MODULE_RELOAD_ORDER:
        if mod_name not in sys.modules:
            importlib.import_module(mod_name)

    if stenosis_mtime is not None and last_stenosis_mtime != stenosis_mtime:
        _reload_modules_in_order(_MODULE_RELOAD_ORDER)
        st.session_state["_pipeline_stenosis_mtime"] = stenosis_mtime
    elif last_stenosis_mtime is None and stenosis_mtime is not None:
        st.session_state["_pipeline_stenosis_mtime"] = stenosis_mtime


_ensure_viewer_modules_fresh()

from src.viewer.plots import (
    reference_window_mm,
    create_3d_artery_plot,
    create_3d_mesh_branch_path_highlight,
    create_3d_mesh_segment_path_highlight,
    PROFILE_AREA_OUTSIDE_REFERENCE_GREY,
    PROFILE_QUANTIFIED_AREA_BLUE,
    branch_peak_reference_summary,
    branch_rows_for_artery_ui,
    create_branch_centerline_metric_bars,
    create_segment_centerline_metric_bars,
    discover_block3_label_branch_xlsx,
    load_block3_cad_rads_patient_report_row,
    load_block3_segment_stenosis_summary,
    load_concat_branch_centerlines,
    segment_id_hex_colors,
    segment_pct_as_peak_reference_summary,
    segment_rows_for_artery_ui,
)

from src.synthetic_profile import is_synthetic_patient

# Align import cache with ``WINDOW_MM`` on disk (fixes stale 5 mm after editing Block 2).
reference_window_mm()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEWER_FIGURES = Path(__file__).resolve().parent / "figures"
SESSION_PATH = PROJECT_ROOT / "results" / "current_session.json"


def _segment_button_label_text_color(css_color: str) -> str:
    """Dark or light label for a filled segment button (handles #hex and rgb/rgba)."""
    s = (css_color or "").strip()
    r = g = b = 80
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            try:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            except ValueError:
                pass
    elif s.lower().startswith("rgb"):
        try:
            i0 = s.index("(")
            i1 = s.index(")")
            parts = [p.strip() for p in s[i0 + 1 : i1].split(",")[:3]]
            r, g, b = (int(float(parts[i])) for i in range(3))
        except (ValueError, IndexError):
            pass
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return "#0d0d0d" if lum > 0.58 else "#ffffff"


def _pipeline_reference_window_mm() -> float:
    """Always match ``WINDOW_MM`` in ``src/blocks/_02_stenosis.py``."""
    return reference_window_mm()


def _reference_window_mm_label() -> str:
    w = _pipeline_reference_window_mm()
    return str(int(w)) if w == int(w) else f"{w:g}"


def _reference_window_line_html() -> str:
    esc = html.escape(_reference_window_mm_label(), quote=True)
    return (
        "<p class='branch-viz-window-line'>"
        "<strong>REFERENCE WINDOW SIZE:</strong> "
        f"±{esc} mm geodesic distance along each branch."
        "</p>"
    )


def _profile_legend_item_html(color: str, body_html: str) -> str:
    c = html.escape(color, quote=True)
    return (
        "<div class='branch-viz-legend-col-wrap'>"
        "<div class='branch-viz-legend-col-inner'>"
        f"<span class='branch-viz-legend-swatch' style='background:{c};'></span>"
        f"<div class='branch-viz-legend-col-text'>{body_html}</div>"
        "</div></div>"
    )


def _profile_area_outside_window_legend_html() -> str:
    return _profile_legend_item_html(
        PROFILE_AREA_OUTSIDE_REFERENCE_GREY,
        "<strong>Grey</strong>: samples on the <strong>Area</strong> profile outside the ±window "
        "reference band (typically branch endpoints); <strong>%AS</strong> is not computed there.",
    )


def _profile_quantified_blue_legend_html() -> str:
    return _profile_legend_item_html(
        PROFILE_QUANTIFIED_AREA_BLUE,
        "<strong>Blue</strong>: quantified centerline samples on the profile <strong>Area</strong> row "
        "(inside the ±window reference band, with <strong>Area</strong> and <strong>%AS</strong> computed).",
    )


def _profile_bar_legends_block_html(*items: str) -> str:
    return (
        "<div class='seg-viz-legends-fullwidth branch-viz-legend' role='note'>"
        + "".join(items)
        + "</div>"
    )


def _segment_pick_button_style_block(
    artery: str, seg_rows: list[tuple[int, str, float]], id_to_hex: dict[int, str]
) -> str:
    """Per-segment Streamlit button colors (matches 3D discrete segment palette)."""
    art = str(artery).strip().upper()
    sel_bg = "#101010"
    sel_bg_hover = "#1c1c1c"
    chunks: list[str] = []
    for sid, _name, _mx in seg_rows:
        key_fragment = f"seg_pick_btn_{art}_{int(sid)}"
        bc = id_to_hex.get(int(sid), "#404040")
        tc = _segment_button_label_text_color(bc)
        base = f'div[class*="st-key-"][class*="{key_fragment}"]'
        chunks.append(
            f"{base} button[kind=\"secondary\"]{{background-color:{bc}!important;"
            f"background-image:none!important;border:1px solid rgba(255,255,255,0.28)!important;"
            f"color:{tc}!important;box-shadow:none!important;}}"
            f"{base} button[kind=\"secondary\"] p,{base} button[kind=\"secondary\"] span,"
            f"{base} button[kind=\"secondary\"] div{{color:{tc}!important;}}"
            f"{base} button[kind=\"secondary\"]:hover{{filter:brightness(1.12)!important;"
            f"border-color:rgba(255,255,255,0.45)!important;}}"
            f"{base} button[kind=\"primary\"]{{background-color:{sel_bg}!important;"
            f"background-image:none!important;border:2px solid {bc}!important;"
            f"box-shadow:inset 0 0 0 1px rgba(0,0,0,0.55)!important;color:#ececec!important;}}"
            f"{base} button[kind=\"primary\"] p,{base} button[kind=\"primary\"] span,"
            f"{base} button[kind=\"primary\"] div{{color:#ececec!important;}}"
            f"{base} button[kind=\"primary\"]:hover{{background-color:{sel_bg_hover}!important;"
            f"filter:none!important;border-color:{bc}!important;}}"
        )
    return "".join(chunks)


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
        /* Top margin + subtitle wrap padding-bottom: ~symmetric with title-above-rule gap (1rem) */
        margin: 1rem 0 0.55rem 0 !important;
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
    .branch-viz-legend {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        font-size: 0.875rem;
        line-height: 1.45;
        color: #bdbdbd !important;
        margin: 0;
        max-width: none;
        width: 100%;
        box-sizing: border-box;
    }
    .branch-viz-section-intro-fullwidth {
        width: 100vw;
        max-width: 100vw;
        margin-left: calc(50% - 50vw);
        margin-right: calc(50% - 50vw);
        margin-bottom: 0.75rem;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-bottom: 1.25rem;
        box-sizing: border-box;
    }
    .branch-viz-section-intro-fullwidth h3.branch-viz-section-title {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        text-align: center;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin: 0 0 0.5rem 0 !important;
        font-size: clamp(1.35rem, 1rem + 1.1vw, 1.65rem);
        color: #e8e8e8 !important;
    }
    p.branch-viz-window-line {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-size: clamp(0.8rem, 0.72rem + 0.3vw, 0.9rem) !important;
        color: #a3a3a3 !important;
        line-height: 1.5 !important;
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        max-width: none !important;
        box-sizing: border-box !important;
        text-align: center;
    }
    p.branch-viz-window-line code {
        font-size: inherit !important;
        color: #d0d0d0 !important;
        background: rgba(255,255,255,0.06);
        padding: 0.08rem 0.3rem;
        border-radius: 0.25rem;
    }
    /* Purple (left col) / green (right col): full column width, swatch + text row */
    .branch-viz-legend-col-wrap {
        width: 100%;
        box-sizing: border-box;
        margin: 0.35rem 0 0.5rem 0;
        padding: 0;
    }
    .branch-viz-legend-col-wrap .branch-viz-legend-col-inner {
        display: flex;
        flex-direction: row;
        align-items: flex-start;
        justify-content: flex-start;
        gap: 0.5rem;
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
        text-align: left;
    }
    .branch-viz-legend-col-wrap .branch-viz-legend-swatch {
        flex-shrink: 0;
        width: 0.65rem;
        height: 0.65rem;
        margin-top: 0.32em;
        border-radius: 2px;
    }
    .branch-viz-legend-col-wrap .branch-viz-legend-col-text {
        flex: 1 1 auto;
        min-width: 0;
        width: 100%;
        max-width: none;
        line-height: 1.5;
        overflow-wrap: anywhere;
        word-wrap: break-word;
        color: #bdbdbd !important;
    }
    .branch-viz-legend-col-wrap .branch-viz-legend-col-text strong,
    .branch-viz-legend-col-wrap .branch-viz-legend-col-text em {
        color: #bdbdbd !important;
    }
    /* Streamlit column markdown wrappers often cap width; stretch only our legend blocks */
    div[data-testid="column"] [data-testid="stMarkdownContainer"]:has(.branch-viz-legend-col-wrap),
    div[data-testid="column"] [data-testid="element-container"]:has(.branch-viz-legend-col-wrap) {
        width: 100% !important;
        max-width: 100% !important;
    }
    div[data-testid="column"] [data-testid="stMarkdownContainer"]:has(.branch-viz-legend-col-wrap) > div,
    div[data-testid="column"] [data-testid="element-container"]:has(.branch-viz-legend-col-wrap) > div {
        width: 100% !important;
        max-width: 100% !important;
    }
    .branch-viz-legend code {
        font-size: 0.82em;
        color: #d0d0d0 !important;
        background: rgba(255,255,255,0.06);
        padding: 0.1rem 0.35rem;
        border-radius: 0.25rem;
    }
    /* Segment 3D + bars: purple + green legend rows, full main width above the two columns */
    .seg-viz-legends-fullwidth {
        width: 100%;
        max-width: 100%;
        margin: 0 0 0.55rem 0;
        padding: 0;
        box-sizing: border-box;
    }
    .seg-viz-legends-fullwidth .branch-viz-legend-col-wrap {
        margin: 0.2rem 0 0.35rem 0;
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
        margin-bottom: 0;
        padding-left: 1rem;
        padding-right: 1rem;
        /* Padding avoids margin-collapse with hr.title-below-rule so gap stays visible */
        padding-bottom: 0.75rem;
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
    /* Minimal top offset for branch list column (section title/legend are full-width above). */
    .branch-panel-align-with-plot-spacer {
        height: 0.45rem;
        min-height: 0.45rem;
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
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"],
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="primary"],
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="primary"] {
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
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"],
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="secondary"],
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="secondary"] {
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
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="primary"] p,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="primary"] p,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"] span,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"] span,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"] span,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"] span,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="primary"] span,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="primary"] span,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"] div,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"] div,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"] div,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"] div,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="primary"] div,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="primary"] div {
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
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="secondary"] p,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="secondary"] p,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"] span,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"] span,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"] div,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"] div,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"] div,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"] div,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="secondary"] div,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="secondary"] div {
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
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"]:hover,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="primary"]:hover,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="primary"]:hover {
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
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"]:hover,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="secondary"]:hover,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="secondary"]:hover {
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
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="primary"]:focus-visible {
        filter: none !important;
        background-color: #ffb74d !important;
        outline: none !important;
        box-shadow: 0 0 0 2px rgba(255, 224, 178, 0.55) !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="secondary"]:focus-visible {
        filter: none !important;
        background-color: #424242 !important;
        outline: none !important;
        box-shadow: none !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="primary"]:active,
    [class*="st-key-"][class*="color_btn_area"] button[kind="primary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="primary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="primary"]:active,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="primary"]:active,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="primary"]:active {
        filter: none !important;
        background-color: #e65100 !important;
        color: #ffffff !important;
        box-shadow: none !important;
        outline: none !important;
    }
    [class*="st-key-"][class*="color_btn_pct_as"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="color_btn_area"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_lca"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="branch_viz_btn_rca"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="seg_viz_btn_lca"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="seg_viz_btn_rca"] button[kind="secondary"]:active {
        filter: none !important;
        background-color: #2d2d2d !important;
        color: #ffffff !important;
        box-shadow: none !important;
        outline: none !important;
    }
    /* Branch list (LCA_B01…): bold labels; segment grid keeps its own weight below */
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"],
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.03em !important;
        line-height: 1.2 !important;
        min-height: 2.5rem !important;
        padding: 0.45rem 0.65rem !important;
        border-radius: 0.45rem !important;
        outline: none !important;
        transition: background-color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease !important;
    }
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"],
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] {
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
    /* Segment ID grid: taller buttons, louder label typography */
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"],
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] {
        min-height: 3.45rem !important;
        padding: 0.68rem 0.85rem !important;
        font-size: 0.88rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"] {
        color: #ffffff !important;
        border: none !important;
        background-color: #f57c00 !important;
        background-image: none !important;
        box-shadow: 0 0 0 2px rgba(255, 183, 77, 0.45) !important;
    }
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"] {
        color: #f0f0f0 !important;
        border: 1px solid rgba(255, 255, 255, 0.32) !important;
        background-color: #121212 !important;
        background-image: none !important;
        box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.55) !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"],
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] {
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
        font-weight: 700 !important;
    }
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"] p,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"] span,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"] div {
        color: #ececec !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] p,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] span,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"] div {
        color: #bdbdbd !important;
        font-weight: 700 !important;
    }
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] p,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] span,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] div {
        color: #bdbdbd !important;
    }
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"] p,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"] span,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"] div,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] p,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] span,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"] div {
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"]:hover {
        background-color: #ffb74d !important;
        box-shadow: 0 0 0 2px rgba(255, 224, 178, 0.55) !important;
    }
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"]:hover {
        background-color: #1e1e1e !important;
        border-color: rgba(255, 255, 255, 0.45) !important;
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06) !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"]:hover,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"]:hover {
        background-color: #424242 !important;
        border-color: #757575 !important;
        color: #e0e0e0 !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"]:focus-visible,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"]:focus-visible,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"]:focus-visible {
        outline: none !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="primary"]:active {
        background-color: #e65100 !important;
        box-shadow: none !important;
    }
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="primary"]:active {
        background-color: #0a0a0a !important;
        box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.65) !important;
    }
    [class*="st-key-"][class*="branch_pick_btn_"] button[kind="secondary"]:active,
    [class*="st-key-"][class*="seg_pick_btn_"] button[kind="secondary"]:active {
        background-color: #2d2d2d !important;
        color: #ffffff !important;
    }
    /* Reset view (LCA/RCA/branch / segment viz): Sant Pau–style cyan blue, bold label */
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="primary"],
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="secondary"],
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="primary"],
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="secondary"],
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="primary"],
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="secondary"],
    [class*="st-key-"][class*="reset_btn_seg_viz"] button[kind="primary"],
    [class*="st-key-"][class*="reset_btn_seg_viz"] button[kind="secondary"] {
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
    [class*="st-key-"][class*="reset_btn_seg_viz"] button[kind="primary"] p,
    [class*="st-key-"][class*="reset_btn_seg_viz"] button[kind="secondary"] p,
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="primary"] span,
    [class*="st-key-"][class*="reset_btn_lca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="primary"] span,
    [class*="st-key-"][class*="reset_btn_rca"] button[kind="secondary"] span,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="primary"] span,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button[kind="secondary"] span,
    [class*="st-key-"][class*="reset_btn_seg_viz"] button[kind="primary"] span,
    [class*="st-key-"][class*="reset_btn_seg_viz"] button[kind="secondary"] span {
        font-family: inherit !important;
        font-weight: 700 !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
        color: #ffffff !important;
    }
    [class*="st-key-"][class*="reset_btn_lca"] button:hover,
    [class*="st-key-"][class*="reset_btn_rca"] button:hover,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button:hover,
    [class*="st-key-"][class*="reset_btn_seg_viz"] button:hover {
        background-color: #33b5e0 !important;
        background-image: none !important;
        color: #ffffff !important;
    }
    [class*="st-key-"][class*="reset_btn_lca"] button:focus-visible,
    [class*="st-key-"][class*="reset_btn_rca"] button:focus-visible,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button:focus-visible,
    [class*="st-key-"][class*="reset_btn_seg_viz"] button:focus-visible {
        background-color: #33b5e0 !important;
        background-image: none !important;
    }
    [class*="st-key-"][class*="reset_btn_lca"] button:active,
    [class*="st-key-"][class*="reset_btn_rca"] button:active,
    [class*="st-key-"][class*="reset_btn_branch_viz"] button:active,
    [class*="st-key-"][class*="reset_btn_seg_viz"] button:active {
        background-color: #007099 !important;
        background-image: none !important;
        color: #ffffff !important;
    }
    /* Sant Pau–style institutional purple (aligned with logo burgundy/violet) */
    .cad-rads-summary-panel {
        max-width: 52rem;
        margin: 0 auto 1.35rem auto;
        padding: 1.25rem 1.5rem 1.35rem 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 0.5rem;
        background: #5b2d78;
        box-sizing: border-box;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.28);
    }
    .cad-rads-summary-panel h3.cad-rads-main-title {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        text-align: center;
        text-transform: uppercase;
        font-weight: 800 !important;
        letter-spacing: 0.06em;
        margin: 0 0 1rem 0 !important;
        font-size: clamp(1.85rem, 1.25rem + 2vw, 2.55rem) !important;
        line-height: 1.18 !important;
        color: #ffffff !important;
    }
    .cad-rads-summary-panel p {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-size: clamp(1.05rem, 0.95rem + 0.45vw, 1.22rem) !important;
        line-height: 1.55 !important;
        color: rgba(255, 255, 255, 0.94) !important;
        margin: 0.5rem 0 !important;
    }
    .cad-rads-summary-panel code {
        font-size: 0.92em !important;
        color: rgba(255, 255, 255, 0.96) !important;
        background: rgba(0, 0, 0, 0.22) !important;
        padding: 0.12rem 0.4rem !important;
        border-radius: 0.28rem !important;
    }
    .seg-ref-summary-panel {
        max-width: 100%;
        margin: 0.25rem 0 0.75rem 0;
        padding: 0.55rem 0.9rem 0.65rem 0.9rem;
        border: 1px solid #4a4a4a;
        border-radius: 0.45rem;
        background: rgba(255, 255, 255, 0.03);
        box-sizing: border-box;
    }
    .seg-ref-summary-panel p {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-size: 0.88rem !important;
        line-height: 1.5 !important;
        color: #c8c8c8 !important;
        margin: 0.28rem 0 !important;
    }
    p.seg-viz-section-intro {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        font-size: clamp(1.02rem, 0.92rem + 0.55vw, 1.2rem) !important;
        line-height: 1.52 !important;
        color: #d6d6d6 !important;
        margin: 0.2rem 0 1rem 0 !important;
        max-width: none !important;
        width: 100% !important;
        padding: 0 !important;
        text-align: left;
        box-sizing: border-box;
    }
    .seg-ref-summary-panel ul.seg-ref-metrics {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
        list-style: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .seg-ref-summary-panel ul.seg-ref-metrics li {
        font-size: clamp(0.98rem, 0.88rem + 0.4vw, 1.08rem) !important;
        line-height: 1.52 !important;
        color: #e4e4e4 !important;
        margin: 0.4rem 0 !important;
        padding: 0 !important;
    }
    .seg-ref-summary-panel ul.seg-ref-metrics li .seg-ref-off-seg {
        font-size: 0.86em !important;
        color: #a8c4a8 !important;
        font-style: italic !important;
        font-weight: 400 !important;
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


def _load_session() -> tuple[str | None, bool]:
    """Return (patient_id, is_synthetic) from current_session.json."""
    if not SESSION_PATH.exists():
        return None, False
    try:
        payload = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, False
    patient_id = payload.get("patient_id")
    if not isinstance(patient_id, str) or not patient_id.strip():
        return None, False
    pid = patient_id.strip()
    is_syn = bool(payload.get("is_synthetic"))
    if not is_syn:
        is_syn = is_synthetic_patient(pid)
    return pid, is_syn


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


def _set_seg_viz_selected_segment(sid: int) -> None:
    st.session_state.seg_viz_selected = int(sid)


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
    if "reset_seg_viz" not in st.session_state:
        st.session_state.reset_seg_viz = 0
    if "reset_synthetic" not in st.session_state:
        st.session_state.reset_synthetic = 0
    if "seg_viz_artery" not in st.session_state:
        st.session_state.seg_viz_artery = "LCA"
    if "seg_viz_selected" not in st.session_state:
        st.session_state.seg_viz_selected = None
    if "color_column" not in st.session_state:
        st.session_state.color_column = "pct_AS"

    patient_id, is_synthetic = _load_session()
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

    if is_synthetic and patient_id != "Unknown Patient":
        _sk1, _sk2, _sk3 = st.columns(3, gap="medium")
        with _sk1:
            st.metric("CAD-RADS 2.0", "N/A (Synthetic)")
        with _sk2:
            st.metric("Case type", "Single-tube phantom")
        with _sk3:
            st.metric("Clinical scores", "Not applicable")
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

    if patient_id != "Unknown Patient":
        st.markdown(
            "<div class='branch-viz-section-intro-fullwidth'>"
            "<h3 class='artery-plot-title branch-viz-section-title'>Coronary artery trees</h3>"
            f"{_reference_window_line_html()}"
            "</div>",
            unsafe_allow_html=True,
        )

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
                if is_synthetic:
                    from src.viewer.synthetic_ui import render_synthetic_dashboard

                    render_synthetic_dashboard(
                        project_root=PROJECT_ROOT,
                        patient_id=patient_id,
                        total_df=total_df,
                        color_column=color_column,
                        plotly_config=plotly_config,
                    )
                else:
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
                    # --- CAD-RADS 2.0 + AHA segment viewer (Block 3 exports) ---
                    _cad = load_block3_cad_rads_patient_report_row(PROJECT_ROOT, patient_id)
                    if _cad is not None:
                        _cat_raw = _cad.get("CAD_RADS_Category")
                        if (
                            _cat_raw is None
                            or (isinstance(_cat_raw, float) and pd.isna(_cat_raw))
                            or str(_cat_raw).strip() == ""
                        ):
                            _cat_disp = "—"
                        else:
                            _cat_disp = str(_cat_raw).strip()
                        _cat_esc = html.escape(_cat_disp, quote=True)
                        _rat = html.escape(str(_cad.get("CAD_RADS_Rationale", "—")), quote=True)
                        _hl = html.escape(str(_cad.get("Highest_Stenosis_Location", "—")), quote=True)
                        try:
                            _hp = float(_cad.get("Highest_Stenosis_pct_AS"))
                            if not math.isfinite(_hp):
                                _hp_s = "—"
                            else:
                                _hp_s = html.escape(f"{max(0.0, _hp):.2f}", quote=True)
                        except (TypeError, ValueError):
                            _hp_s = "—"
                        try:
                            _ss = _cad.get("SIS_Score")
                            _sd = _cad.get("SIS_Denominator")
                            if _ss is not None and pd.notna(_ss):
                                _ss_i = int(float(_ss))
                                if _sd is not None and pd.notna(_sd):
                                    _sis_disp = f"{_ss_i} / {int(float(_sd))}"
                                else:
                                    _sis_disp = str(_ss_i)
                                _sis_esc = html.escape(_sis_disp, quote=True)
                            else:
                                _sis_esc = "—"
                        except (TypeError, ValueError):
                            _sis_esc = "—"
                        _cad_html = [
                            "<div class='cad-rads-summary-panel'>",
                            f"<h3 class='cad-rads-main-title'>Patient CAD-RADS 2.0: {_cat_esc}</h3>",
                            f"<p><strong>Rationale</strong>: {_rat}</p>",
                            f"<p><strong>Leading stenosis location</strong>: {_hl} "
                            f"(highest segment %AS ≈ {_hp_s}%).</p>",
                            f"<p><strong>SIS (Segment Involvement Score)</strong>: {_sis_esc}</p>",
                            "</div>",
                        ]
                    else:
                        _cad_html = [
                            "<div class='cad-rads-summary-panel'>",
                            "<h3 class='cad-rads-main-title'>Patient CAD-RADS 2.0: —</h3>",
                            "<p>No CAD-RADS report found. Expected "
                            f"<code>results/block3_results/cad-rads/{html.escape(patient_id, quote=True)}/"
                            f"patient_report_{html.escape(patient_id, quote=True)}.xlsx</code>.</p>",
                            "</div>",
                        ]
                    st.markdown("".join(_cad_html), unsafe_allow_html=True)

                    seg_summary_df = load_block3_segment_stenosis_summary(PROJECT_ROOT, patient_id)
                    st.markdown(
                        "<div class='branch-viz-section-intro-fullwidth'>"
                        "<h3 class='artery-plot-title branch-viz-section-title'>"
                        "Coronary artery colored segments</h3>"
                        f"{_reference_window_line_html()}"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        "<p class='seg-viz-section-intro'>"
                        "Segments are ordered by descending max %AS. Use buttons to select the specific segment "
                        "and artery. The 3D view colors centerline markers by segment ID; the selected segment path "
                        "is redrawn in dark tones with purple at max %AS. Proximal / distal Area reference samples are shown in green "
                        "on the Area bar chart only."
                        "</p>",
                        unsafe_allow_html=True,
                    )

                    _rsl, _rsr = st.columns(2, gap="small")
                    with _rsl:
                        if st.button(
                            "LCA",
                            key="seg_viz_btn_lca",
                            use_container_width=True,
                            type="primary"
                            if str(st.session_state.seg_viz_artery).strip().upper() == "LCA"
                            else "secondary",
                        ):
                            st.session_state.seg_viz_artery = "LCA"
                            st.session_state.seg_viz_selected = None
                    with _rsr:
                        if st.button(
                            "RCA",
                            key="seg_viz_btn_rca",
                            use_container_width=True,
                            type="primary"
                            if str(st.session_state.seg_viz_artery).strip().upper() == "RCA"
                            else "secondary",
                        ):
                            st.session_state.seg_viz_artery = "RCA"
                            st.session_state.seg_viz_selected = None

                    _sv_art = str(st.session_state.seg_viz_artery).strip().upper()
                    if _sv_art not in ("LCA", "RCA"):
                        _sv_art = "LCA"
                        st.session_state.seg_viz_artery = _sv_art
                    try:
                        df_seg_art = _sort_centerline_subset(_filter_artery(total_df, _sv_art))
                    except Exception:
                        df_seg_art = pd.DataFrame()
                    seg_rows = segment_rows_for_artery_ui(seg_summary_df, df_seg_art, _sv_art)
                    seg_ids = [t[0] for t in seg_rows]
                    _seg_mesh = mesh_lca if _sv_art == "LCA" else mesh_rca
                    _seg_ok = (
                        _seg_mesh.is_file()
                        and not df_seg_art.empty
                        and {"Px", "Py", "Pz", "pct_AS", "Area", "Segment_ID"}.issubset(df_seg_art.columns)
                        and bool(seg_ids)
                    )
                    if _seg_ok:
                        if (
                            st.session_state.seg_viz_selected is None
                            or int(st.session_state.seg_viz_selected) not in seg_ids
                        ):
                            st.session_state.seg_viz_selected = int(seg_ids[0])
                        _sel_seg = int(st.session_state.seg_viz_selected)
                    else:
                        _sel_seg = 0
                        if not seg_ids:
                            st.caption(
                                f"No labeled segment IDs (> 0) in {_sv_art} centerline data, "
                                "or mesh / columns missing."
                            )

                    if _seg_ok:
                        _seg_id_colors = segment_id_hex_colors(df_seg_art)
                        st.markdown(
                            f"<style>{_segment_pick_button_style_block(_sv_art, seg_rows, _seg_id_colors)}</style>",
                            unsafe_allow_html=True,
                        )
                        _seg_btns_per_row = 6
                        for _row0 in range(0, len(seg_rows), _seg_btns_per_row):
                            _chunk = seg_rows[_row0 : _row0 + _seg_btns_per_row]
                            _bcols = st.columns(_seg_btns_per_row)
                            for _j, (_sid, _sname, _mx) in enumerate(_chunk):
                                short = (_sname[:22] + "…") if len(_sname) > 23 else _sname
                                btn_lbl = f"{_sid}: {short} ({_mx:.1f}%)"
                                with _bcols[_j]:
                                    st.button(
                                        btn_lbl,
                                        key=f"seg_pick_btn_{_sv_art}_{_sid}",
                                        use_container_width=True,
                                        type="primary" if _sel_seg == _sid else "secondary",
                                        on_click=_set_seg_viz_selected_segment,
                                        args=(int(_sid),),
                                    )

                        _pk = segment_pct_as_peak_reference_summary(df_seg_art, _sel_seg)
                        if _pk.get("ok"):

                            def _fmt_area_ui(v: object) -> str:
                                if v is None:
                                    return "—"
                                try:
                                    x = float(v)
                                except (TypeError, ValueError):
                                    return "—"
                                return f"{x:.4f} mm²" if math.isfinite(x) else "—"

                            def _fmt_pct_ui(v: object) -> str:
                                if v is None:
                                    return "—"
                                try:
                                    x = float(v)
                                except (TypeError, ValueError):
                                    return "—"
                                if not math.isfinite(x):
                                    return "—"
                                x = max(0.0, x)
                                return f"{x:.2f} %"

                            _m_pct = html.escape(_fmt_pct_ui(_pk.get("max_pct_as")), quote=True)
                            _m_area = html.escape(_fmt_area_ui(_pk.get("area_at_max")), quote=True)
                            _m_prox = html.escape(_fmt_area_ui(_pk.get("area_prox_ref")), quote=True)
                            _m_dist = html.escape(_fmt_area_ui(_pk.get("area_dist_ref")), quote=True)
                            _prox_hint = ""
                            _dist_hint = ""
                            if not _pk.get("prox_ref_on_segment_bar", True) and _pk.get(
                                "area_prox_ref"
                            ) is not None:
                                try:
                                    _apx = float(_pk.get("area_prox_ref"))  # type: ignore[arg-type]
                                except (TypeError, ValueError):
                                    _apx = float("nan")
                                if math.isfinite(_apx):
                                    if _pk.get("prox_ref_highlight_index") is not None:
                                        _prox_hint = (
                                            ' <span class="seg-ref-off-seg">(Value used for %AS at peak; '
                                            "green bar marks the ±window sample on this segment.)</span>"
                                        )
                                    else:
                                        _loc = _pk.get("prox_ref_location_hint")
                                        if _loc:
                                            _prox_hint = (
                                                f' <span class="seg-ref-off-seg">({html.escape(str(_loc), quote=True)})</span>'
                                            )
                                        else:
                                            _prox_hint = (
                                                ' <span class="seg-ref-off-seg">(Reference is on another segment '
                                                "along the branch — not shown on this segment’s Area bars.)</span>"
                                            )
                            if not _pk.get("dist_ref_on_segment_bar", True) and _pk.get(
                                "area_dist_ref"
                            ) is not None:
                                try:
                                    _adx = float(_pk.get("area_dist_ref"))  # type: ignore[arg-type]
                                except (TypeError, ValueError):
                                    _adx = float("nan")
                                if math.isfinite(_adx):
                                    if _pk.get("dist_ref_highlight_index") is not None:
                                        _dist_hint = (
                                            ' <span class="seg-ref-off-seg">(Value used for %AS at peak; '
                                            "green bar marks the ±window sample on this segment.)</span>"
                                        )
                                    else:
                                        _loc = _pk.get("dist_ref_location_hint")
                                        if _loc:
                                            _dist_hint = (
                                                f' <span class="seg-ref-off-seg">({html.escape(str(_loc), quote=True)})</span>'
                                            )
                                        else:
                                            _dist_hint = (
                                                ' <span class="seg-ref-off-seg">(Reference is on another segment '
                                                "along the branch — not shown on this segment’s Area bars.)</span>"
                                            )
                            st.markdown(
                                "<div class='seg-ref-summary-panel'>"
                                "<ul class='seg-ref-metrics'>"
                                f"<li><strong>Max %AS</strong>: {_m_pct}</li>"
                                f"<li><strong>Area at peak</strong>: {_m_area}</li>"
                                f"<li><strong>Proximal Reference Area</strong>: {_m_prox}{_prox_hint}</li>"
                                f"<li><strong>Distal Reference Area</strong>: {_m_dist}{_dist_hint}</li>"
                                "</ul></div>",
                                unsafe_allow_html=True,
                            )
                        elif _pk.get("reason") == "no_pct_col":
                            st.caption("Reference Area summary skipped: no %AS column in segment rows.")

                        st.markdown(
                            _profile_bar_legends_block_html(
                                _profile_legend_item_html(
                                    "#a855f7",
                                    "<strong>Purple</strong>: maximum %AS on the segment — <strong>3D</strong>: diamond; "
                                    "<strong>bar charts</strong>: purple on both Area and %AS rows.",
                                ),
                                _profile_legend_item_html(
                                    "#2e7d32",
                                    "<strong>Green</strong>: proximal / distal <strong>Area</strong> reference samples "
                                    "that lie <em>on this segment</em> — <strong>bar charts</strong> only (Area row). "
                                    "If a reference is on another segment, it is listed in the summary above, "
                                    "not as a green bar.",
                                ),
                                _profile_area_outside_window_legend_html(),
                                _profile_quantified_blue_legend_html(),
                            ),
                            unsafe_allow_html=True,
                        )

                        seg_plot_3d_col, seg_bars_col = st.columns([0.82, 1.38], gap="medium", vertical_alignment="top")
                        with seg_plot_3d_col:
                            try:
                                fig_seg = create_3d_mesh_segment_path_highlight(
                                    str(_seg_mesh),
                                    df_seg_art,
                                    selected_segment_id=_sel_seg,
                                    trace_name=_sv_art,
                                )
                                _sk_seg = dict(
                                    use_container_width=True,
                                    config=plotly_config,
                                    key=f"seg_viz_plot_{st.session_state.reset_seg_viz}_{_sv_art}_{_sel_seg}",
                                )
                                try:
                                    st.plotly_chart(fig_seg, **_sk_seg)
                                except TypeError:
                                    _sk_seg.pop("key", None)
                                    st.plotly_chart(fig_seg, **_sk_seg)
                                sg1, sg2, sg3 = st.columns([2, 1, 2])
                                with sg2:
                                    if st.button("RESET VIEW", key="reset_btn_seg_viz"):
                                        st.session_state.reset_seg_viz += 1
                            except Exception as e:
                                st.warning(f"Segment 3D visualization could not be built: {e}")

                        with seg_bars_col:
                            try:
                                fig_seg_bars = create_segment_centerline_metric_bars(
                                    df_seg_art,
                                    selected_segment_id=_sel_seg,
                                    artery=_sv_art,
                                )
                                _sk_b = dict(
                                    use_container_width=True,
                                    config=plotly_config,
                                    key=(
                                        f"seg_profile_bars_{patient_id}_{_sv_art}_{_sel_seg}_"
                                        f"{st.session_state.reset_seg_viz}"
                                    ),
                                )
                                try:
                                    st.plotly_chart(fig_seg_bars, **_sk_b)
                                except TypeError:
                                    _sk_b.pop("key", None)
                                    st.plotly_chart(fig_seg_bars, **_sk_b)
                            except Exception as ex_s:
                                st.caption(f"Along-segment Area / %AS charts could not be built: {ex_s}")
                    else:
                        st.caption("Load Block 3 label `total_df` with Segment_ID, Area, and pct_AS to enable.")

                    st.markdown(
                        "<hr class='section-divider-branch-viz' aria-hidden='true'>",
                        unsafe_allow_html=True,
                    )
                    # --- Branch path viewer: full-width title + window line; purple/green in each column ---
                    st.markdown(
                        "<div class='branch-viz-section-intro-fullwidth'>"
                        "<h3 class='artery-plot-title branch-viz-section-title'>Coronary branch paths</h3>"
                        f"{_reference_window_line_html()}"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    row2_l, row2_r = st.columns([2.85, 2.55], gap="medium", vertical_alignment="top")
                    with row2_l:
                        st.markdown(
                            "<div class='branch-viz-legend' role='note'>"
                            + _profile_legend_item_html(
                                "#a855f7",
                                "<strong>Purple</strong>: maximum %AS on the branch — <strong>3D</strong>: diamond; "
                                "<strong>bar charts</strong>: purple on both Area and %AS rows.",
                            )
                            + _profile_area_outside_window_legend_html()
                            + "</div>",
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
                        try:
                            branch_df_all = _sort_centerline_subset(_filter_artery(total_df, _bv_art))
                        except Exception:
                            branch_df_all = pd.DataFrame()
                        branch_pairs = discover_block3_label_branch_xlsx(PROJECT_ROOT, patient_id, _bv_art)
                        branch_rows = branch_rows_for_artery_ui(
                            branch_df_all, artery_prefix=_bv_art
                        )
                        branch_ids = [b for b, _ in branch_rows]
                        if not branch_ids and branch_pairs:
                            branch_df_all = load_concat_branch_centerlines(branch_pairs)
                            branch_rows = branch_rows_for_artery_ui(
                                branch_df_all, artery_prefix=_bv_art
                            )
                            branch_ids = [b for b, _ in branch_rows]
                            if not branch_ids:
                                branch_ids = [b for b, _ in branch_pairs]
                                branch_rows = [(b, 0.0) for b in branch_ids]
                        _branch_viz_ok = (
                            bool(branch_ids)
                            and not branch_df_all.empty
                            and _bv_mesh.is_file()
                            and {"Px", "Py", "Pz", "pct_AS", "Branch_ID", "Area"}.issubset(
                                branch_df_all.columns
                            )
                        )
                        if not _branch_viz_ok:
                            if branch_df_all.empty and not branch_pairs:
                                st.caption(
                                    f"No {_bv_art} branches in total_df and no branch spreadsheets under "
                                    f"`results/block3_results/label/{patient_id}/branches/dataframes/`."
                                )
                            elif not _bv_mesh.is_file():
                                st.caption(f"{_bv_art} surface mesh missing; branch path viewer skipped.")
                            else:
                                st.warning(
                                    "Branch dataframes are missing required columns "
                                    "(Px, Py, Pz, pct_AS, Branch_ID). Cannot build branch highlight plot."
                                )
                        else:
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
                            "<div class='branch-viz-legend' role='note'>"
                            + _profile_legend_item_html(
                                "#2e7d32",
                                "<strong>Green</strong>: proximal / distal <strong>Area</strong> at the peak "
                                "(same sample as the bar chart when on this branch). "
                                "<strong>3D</strong>: green <strong>circles</strong>; "
                                "<strong>Area</strong> bar row only (not %AS).",
                            )
                            + _profile_quantified_blue_legend_html()
                            + "</div>",
                            unsafe_allow_html=True,
                        )
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
                            for bid, _mx_br in branch_rows:
                                _br_lbl = f"{bid} ({_mx_br:.1f}%)"
                                st.button(
                                    _br_lbl,
                                    key=f"branch_pick_btn_{_bv_art}_{bid}",
                                    use_container_width=True,
                                    type="primary" if _sel_r == bid else "secondary",
                                    on_click=_set_branch_viz_selected_branch,
                                    args=(bid,),
                                )
                        elif not branch_ids:
                            st.caption("No branches for this artery in total_df.")
                        else:
                            st.caption("Load branch tables or mesh to enable selection.")

                    if _branch_viz_ok:
                        st.markdown(
                            '<div class="branch-viz-artery-row-spacer" aria-hidden="true">&nbsp;</div>',
                            unsafe_allow_html=True,
                        )
                        try:
                            _sel_prof = str(st.session_state.branch_viz_selected)
                            _pk_br = branch_peak_reference_summary(branch_df_all, _sel_prof)
                            if _pk_br.get("ok"):

                                def _fmt_area_br(v: object) -> str:
                                    if v is None:
                                        return "—"
                                    try:
                                        x = float(v)
                                    except (TypeError, ValueError):
                                        return "—"
                                    return f"{x:.4f} mm²" if math.isfinite(x) else "—"

                                def _fmt_pct_br(v: object) -> str:
                                    if v is None:
                                        return "—"
                                    try:
                                        x = float(v)
                                    except (TypeError, ValueError):
                                        return "—"
                                    if not math.isfinite(x):
                                        return "—"
                                    return f"{max(0.0, x):.2f} %"

                                _br_prox_h = ""
                                _br_dist_h = ""
                                if not _pk_br.get("prox_ref_on_segment_bar", True) and _pk_br.get(
                                    "area_prox_ref"
                                ) is not None:
                                    if _pk_br.get("prox_ref_highlight_index") is not None:
                                        _br_prox_h = (
                                            ' <span class="seg-ref-off-seg">(A_ref at peak; green bar = '
                                            "±window sample on this branch.)</span>"
                                        )
                                if not _pk_br.get("dist_ref_on_segment_bar", True) and _pk_br.get(
                                    "area_dist_ref"
                                ) is not None:
                                    if _pk_br.get("dist_ref_highlight_index") is not None:
                                        _br_dist_h = (
                                            ' <span class="seg-ref-off-seg">(A_ref at peak; green bar = '
                                            "±window sample on this branch.)</span>"
                                        )
                                st.markdown(
                                    "<div class='seg-ref-summary-panel'>"
                                    "<ul class='seg-ref-metrics'>"
                                    f"<li><strong>Max %AS</strong>: {html.escape(_fmt_pct_br(_pk_br.get('max_pct_as')), quote=True)}</li>"
                                    f"<li><strong>Area at peak</strong>: {html.escape(_fmt_area_br(_pk_br.get('area_at_max')), quote=True)}</li>"
                                    f"<li><strong>Proximal Reference Area</strong>: "
                                    f"{html.escape(_fmt_area_br(_pk_br.get('area_prox_ref')), quote=True)}{_br_prox_h}</li>"
                                    f"<li><strong>Distal Reference Area</strong>: "
                                    f"{html.escape(_fmt_area_br(_pk_br.get('area_dist_ref')), quote=True)}{_br_dist_h}</li>"
                                    "</ul></div>",
                                    unsafe_allow_html=True,
                                )

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
