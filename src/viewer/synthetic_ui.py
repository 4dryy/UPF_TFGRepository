"""Streamlit UI sections for synthetic single-tube validation cases."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import numpy as np

from src.synthetic_profile import (
    is_stenosis_synthetic_patient,
    synthetic_validation_metrics,
)
from src.viewer.plots import (
    _sort_branch_rows,
    reference_window_mm,
    create_3d_artery_plot,
    create_synthetic_tube_geodesic_profile,
    discover_synthetic_branch_xlsx,
    load_concat_branch_centerlines,
)

# Orange used to mark the centerline point with the largest |A_pred − A_theo|
# (matches the "Maximum Area Deviation" metric tile in the validation panel).
_MAX_AREA_DEV_ORANGE = "#ff6f00"
# Purple matches ``_BRANCH_EXTREMA_PURPLE`` in plots.py — same hue as the max-%AS bar.
_MAX_PCT_AS_PURPLE = "#a855f7"
# Blue matches ``_BRANCH_PROFILE_BLUE`` in plots.py — same hue as the Area bars.
_AREA_PROFILE_BLUE = "#0092c7"
# Red used for the maximum predicted area (label + corresponding Area bar).
_MAX_PRED_AREA_RED = "#ef4444"


def _load_validation_metrics(
    project_root: Path,
    patient_id: str,
    fallback_df: pd.DataFrame,
) -> dict:
    """Read the persisted synthetic validation metrics; recompute from total_df on miss."""
    json_path = (
        project_root
        / "results"
        / "block3_results"
        / "cad-rads"
        / patient_id
        / f"summary_metrics_{patient_id}.json"
    )
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            metrics = data.get("validation_metrics")
            if isinstance(metrics, dict) and metrics.get("ok"):
                return metrics
        except Exception:
            pass
    if fallback_df is not None and not fallback_df.empty:
        return synthetic_validation_metrics(fallback_df, patient_id)
    return {"ok": False, "reason": "no data available"}


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{float(value):.2f} %"


def _fmt_area(value: float | None) -> str:
    return "—" if value is None else f"{float(value):.2f} mm²"


_ARROW_OVER_GREEN = "#22c55e"
_ARROW_UNDER_RED = "#ef4444"


def _render_colored_metric_tile(
    label: str,
    value_text: str,
    color: str,
    *,
    help_text: str | None = None,
    delta_text: str | None = None,
    signed_delta: float | None = None,
) -> None:
    """`st.metric` replacement whose label is rendered in the given color.

    When ``signed_delta`` is provided, a small arrow is shown next to the value:
    ↑ green if predicted > theoretical, ↓ red if predicted < theoretical.
    """
    title_attr = f" title=\"{html.escape(help_text, quote=True)}\"" if help_text else ""
    delta_html = (
        "<div style='font-size: 0.82rem; color: rgba(0,0,0,0.55); "
        f"margin-top: 0.25rem;'>{html.escape(delta_text)}</div>"
        if delta_text
        else ""
    )

    arrow_html = ""
    if signed_delta is not None:
        try:
            sd = float(signed_delta)
        except (TypeError, ValueError):
            sd = float("nan")
        if np.isfinite(sd) and sd != 0.0:
            if sd > 0:
                arrow_char = "▲"
                arrow_color = _ARROW_OVER_GREEN
                arrow_title = "Predicted higher than theoretical"
            else:
                arrow_char = "▼"
                arrow_color = _ARROW_UNDER_RED
                arrow_title = "Predicted lower than theoretical"
            arrow_html = (
                f"<span style='font-size: 1.15rem; color: {arrow_color}; "
                f"margin-left: 0.45rem; vertical-align: middle;' "
                f"title='{html.escape(arrow_title, quote=True)}'>{arrow_char}</span>"
            )

    st.markdown(
        "<div style='padding: 0.25rem 0;'>"
        f"<div style='font-size: 0.875rem; color: {color}; font-weight: 600;'{title_attr}>"
        f"{html.escape(label)}</div>"
        "<div style='font-size: 2.0rem; color: #1a1a1a; font-weight: 600; "
        "line-height: 1.1; margin-top: 0.15rem;'>"
        f"{html.escape(value_text)}{arrow_html}</div>"
        f"{delta_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_max_area_deviation_tile(
    value: float | None,
    *,
    predicted: float | None = None,
    theoretical: float | None = None,
) -> None:
    """Maximum Area Deviation tile — orange label matches the highlighted bar in the Area profile.

    When the predicted / theoretical pair at the deviation point is provided, the muted line below
    shows the subtraction that produced the value (``|A_pred − A_theo|``).
    """
    delta_text: str | None = None
    if (
        predicted is not None
        and theoretical is not None
        and np.isfinite(float(predicted))
        and np.isfinite(float(theoretical))
    ):
        delta_text = (
            f"|A_pred − A_theo| = |{float(predicted):.2f} − {float(theoretical):.2f}| mm²"
        )
    _render_colored_metric_tile(
        "Maximum Area Deviation",
        _fmt_area(value),
        _MAX_AREA_DEV_ORANGE,
        help_text=(
            "Maximum of |A_predicted(z) − A_theoretical(z)| along the vessel tube. "
            "Identifies the centerline point where |A_predicted − A_theoretical| is largest."
        ),
        delta_text=delta_text,
    )


def _safe_signed_delta(predicted: float | None, theoretical: float | None) -> float | None:
    """``predicted - theoretical`` if both finite, else ``None`` (no arrow rendered)."""
    if predicted is None or theoretical is None:
        return None
    try:
        d = float(predicted) - float(theoretical)
    except (TypeError, ValueError):
        return None
    return d if np.isfinite(d) else None


def _render_pct_as_tile(
    label: str,
    value: float | None,
    *,
    signed_delta: float | None = None,
    help_text: str | None = None,
) -> None:
    """%AS validation tile — purple label matches the max-%AS bar in the geodesic profile."""
    delta_text = None if signed_delta is None else f"|Δ| {abs(float(signed_delta)):.2f} %"
    _render_colored_metric_tile(
        label,
        _fmt_pct(value),
        _MAX_PCT_AS_PURPLE,
        help_text=help_text,
        delta_text=delta_text,
        signed_delta=signed_delta,
    )


def _render_area_tile(
    label: str,
    value: float | None,
    *,
    signed_delta: float | None = None,
    help_text: str | None = None,
    color: str = _AREA_PROFILE_BLUE,
) -> None:
    """Area validation tile — blue label by default (override ``color`` for highlighted tiles)."""
    delta_text = None if signed_delta is None else f"|Δ| {abs(float(signed_delta)):.2f} mm²"
    _render_colored_metric_tile(
        label,
        _fmt_area(value),
        color,
        help_text=help_text,
        delta_text=delta_text,
        signed_delta=signed_delta,
    )


def _render_validation_metrics(metrics: dict, patient_id: str) -> None:
    """Three-column ground-truth vs predicted panel; layout depends on healthy/stenosis."""
    title = "Validation metrics — ground truth vs prediction"
    st.markdown(
        f"<h3 class='artery-plot-title' style='margin-top: 8px;'>{html.escape(title)}</h3>",
        unsafe_allow_html=True,
    )

    if not metrics or not metrics.get("ok"):
        reason = metrics.get("reason", "metrics not available") if isinstance(metrics, dict) else "metrics not available"
        st.warning(f"Validation metrics unavailable: {reason}. Re-run the pipeline for {patient_id}.")
        return

    is_stenosis = bool(metrics.get("is_stenosis") or is_stenosis_synthetic_patient(patient_id))

    if not is_stenosis:
        st.caption(
            "Healthy phantom (constant R = 10 mm) — peak %AS must approach 0 and the "
            "measured area should track πR² along the whole tube."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            _render_pct_as_tile(
                "Theoretical %AS",
                metrics["theoretical_max_pct_as"],
                help_text="Analytical peak %AS for the healthy phantom (constant R → 0%).",
            )
        with c2:
            _render_pct_as_tile(
                "Predicted %AS",
                metrics["predicted_max_pct_as"],
                signed_delta=_safe_signed_delta(
                    metrics["predicted_max_pct_as"],
                    metrics["theoretical_max_pct_as"],
                ),
                help_text=(
                    "Maximum %AS measured by the pipeline along the vessel "
                    "(purple bar in the %AS profile below). "
                    "Arrow: ▲ predicted > theoretical, ▼ predicted < theoretical."
                ),
            )
        with c3:
            _render_pct_as_tile(
                "|Abs. Error %AS|",
                metrics["abs_error_max_pct_as"],
                help_text="|Theoretical %AS − Predicted %AS|.",
            )

        c4, c5, c6 = st.columns(3)
        with c4:
            _render_area_tile(
                "Theoretical Area",
                metrics.get("theoretical_mean_area_mm2"),
                help_text="Analytical πR² along the healthy phantom (constant R = 10 mm → 314.16 mm²).",
            )
        with c5:
            _render_area_tile(
                "Predicted Mean Area",
                metrics.get("predicted_mean_area_mm2"),
                signed_delta=_safe_signed_delta(
                    metrics.get("predicted_mean_area_mm2"),
                    metrics.get("theoretical_mean_area_mm2"),
                ),
                help_text=(
                    "Mean of predicted lumen Area across all centerline samples on the vessel body. "
                    "Arrow: ▲ predicted > theoretical, ▼ predicted < theoretical."
                ),
            )
        with c6:
            _render_area_tile(
                "|Abs. Error Mean Area|",
                metrics.get("abs_error_mean_area_mm2"),
                help_text="|Theoretical Area − Predicted Mean Area|.",
            )

        c7, c8 = st.columns(2)
        with c7:
            _render_area_tile(
                "Mean Area Absolute Error",
                metrics["mean_area_abs_error_mm2"],
                help_text="Mean of |A_predicted(z) − A_theoretical(z)| along the vessel tube.",
            )
        with c8:
            _render_max_area_deviation_tile(
                metrics["max_area_abs_deviation_mm2"],
                predicted=metrics.get("max_area_deviation_predicted_mm2"),
                theoretical=metrics.get("max_area_deviation_theoretical_mm2"),
            )
    else:
        st.caption(
            "Stenosis phantom (cosine narrowing, R_min = 5 mm at Z = 50 mm) — peak %AS ≈ 75% "
            "and lumen area should range from 314.16 → 78.54 mm²."
        )
        st.markdown("**Maximum %AS**")
        c1, c2, c3 = st.columns(3)
        with c1:
            _render_pct_as_tile(
                "Theoretical Max %AS",
                metrics["theoretical_max_pct_as"],
                help_text="Analytical peak %AS for the stenosis phantom (cosine narrowing → 75%).",
            )
        with c2:
            _render_pct_as_tile(
                "Predicted Max %AS",
                metrics["predicted_max_pct_as"],
                signed_delta=_safe_signed_delta(
                    metrics["predicted_max_pct_as"],
                    metrics["theoretical_max_pct_as"],
                ),
                help_text=(
                    "Maximum %AS measured by the pipeline along the vessel "
                    "(purple bar in the %AS profile below). "
                    "Arrow: ▲ predicted > theoretical, ▼ predicted < theoretical."
                ),
            )
        with c3:
            _render_pct_as_tile(
                "|Abs. Error Max %AS|",
                metrics["abs_error_max_pct_as"],
                help_text="|Theoretical Max %AS − Predicted Max %AS|.",
            )

        st.markdown("**Maximum Area**")
        d1, d2, d3 = st.columns(3)
        with d1:
            _render_area_tile(
                "Theoretical Max Area",
                metrics["theoretical_max_area_mm2"],
                help_text="Analytical maximum cross-sectional area of the phantom body (πR_base²).",
            )
        with d2:
            _render_area_tile(
                "Predicted Max Area",
                metrics["predicted_max_area_mm2"],
                signed_delta=_safe_signed_delta(
                    metrics["predicted_max_area_mm2"],
                    metrics["theoretical_max_area_mm2"],
                ),
                help_text=(
                    "Maximum lumen Area measured along the vessel "
                    "(purple bar in the %AS profile marks peak stenosis). "
                    "Arrow: ▲ predicted > theoretical, ▼ predicted < theoretical."
                ),
                color=_MAX_PRED_AREA_RED,
            )
        with d3:
            _render_area_tile(
                "|Abs. Error Max Area|",
                metrics["abs_error_max_area_mm2"],
                help_text="|Theoretical Max Area − Predicted Max Area|.",
            )

        st.markdown("**Minimum Area**")
        e1, e2, e3 = st.columns(3)
        with e1:
            _render_area_tile(
                "Theoretical Min Area",
                metrics["theoretical_min_area_mm2"],
                help_text="Analytical minimum cross-sectional area at the stenosis neck (πR_min²).",
            )
        with e2:
            _render_area_tile(
                "Predicted Min Area",
                metrics["predicted_min_area_mm2"],
                signed_delta=_safe_signed_delta(
                    metrics["predicted_min_area_mm2"],
                    metrics["theoretical_min_area_mm2"],
                ),
                help_text=(
                    "Minimum lumen Area measured along the vessel. "
                    "Arrow: ▲ predicted > theoretical, ▼ predicted < theoretical."
                ),
            )
        with e3:
            _render_area_tile(
                "|Abs. Error Min Area|",
                metrics["abs_error_min_area_mm2"],
                help_text="|Theoretical Min Area − Predicted Min Area|.",
            )

        st.markdown("**Along-vessel area accuracy**")
        f1, f2 = st.columns(2)
        with f1:
            _render_area_tile(
                "Mean Area Absolute Error",
                metrics.get("mean_area_abs_error_mm2"),
                help_text="Mean of |A_predicted(z) − A_theoretical(z)| along the vessel tube.",
            )
        with f2:
            _render_max_area_deviation_tile(
                metrics.get("max_area_abs_deviation_mm2"),
                predicted=metrics.get("max_area_deviation_predicted_mm2"),
                theoretical=metrics.get("max_area_deviation_theoretical_mm2"),
            )


def _filter_synthetic_vessel(df: pd.DataFrame) -> pd.DataFrame:
    if "Artery_Type" not in df.columns:
        return df.copy()
    mask = df["Artery_Type"].astype(str).str.strip().str.upper() == "SYNTHETIC"
    return df.loc[mask].copy()


def _sort_centerline_subset(df: pd.DataFrame) -> pd.DataFrame:
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


def render_synthetic_dashboard(
    *,
    project_root: Path,
    patient_id: str,
    total_df: pd.DataFrame,
    color_column: str,
    plotly_config: dict,
) -> None:
    """Centered 3D vessel view, N/A CAD-RADS panel, and along-vessel geodesic profile."""
    mesh_synthetic = (
        project_root / "results" / "block1_results" / patient_id / "surface_Synthetic.vtp"
    )

    _pad_l, _col_syn, _pad_r = st.columns([1, 4, 1], gap="small")
    with _col_syn:
        _w_mm = reference_window_mm()
        _win_esc = html.escape(
            str(int(_w_mm)) if _w_mm == int(_w_mm) else f"{_w_mm:g}",
            quote=True,
        )
        st.markdown(
            "<div class='branch-viz-section-intro-fullwidth'>"
            "<h3 class='artery-plot-title branch-viz-section-title'>Synthetic validation vessel</h3>"
            "<p class='branch-viz-window-line'>"
            "<strong>REFERENCE WINDOW SIZE:</strong> "
            f"±{_win_esc} mm geodesic distance along the vessel "
            "(set <code>WINDOW_MM</code> in <code>src/blocks/_02_stenosis.py</code>)."
            "</p></div>",
            unsafe_allow_html=True,
        )
        try:
            df_syn = _sort_centerline_subset(_filter_synthetic_vessel(total_df))
            if df_syn.empty:
                st.warning("Synthetic vessel data not found in total_df.")
            elif not mesh_synthetic.is_file():
                st.warning(
                    f"Surface mesh not found: {mesh_synthetic}. "
                    "Re-run Block 1 for this synthetic case."
                )
            else:
                fig_syn = create_3d_artery_plot(
                    str(mesh_synthetic),
                    df_syn,
                    color_column,
                    trace_name="Synthetic",
                    is_synthetic=True,
                )
                _syn_kw = dict(
                    use_container_width=True,
                    config=plotly_config,
                    key=f"syn_plot_{st.session_state.get('reset_synthetic', 0)}",
                )
                try:
                    st.plotly_chart(fig_syn, **_syn_kw)
                except TypeError:
                    _syn_kw.pop("key", None)
                    st.plotly_chart(fig_syn, **_syn_kw)
                sr1, sr2, sr3 = st.columns([2, 1, 2])
                with sr2:
                    if st.button("RESET VIEW", key="reset_btn_synthetic"):
                        st.session_state.reset_synthetic = (
                            int(st.session_state.get("reset_synthetic", 0)) + 1
                        )
        except Exception as ex_syn:
            st.warning(f"Synthetic 3D view could not be built: {ex_syn}")

    st.markdown(
        "<hr class='section-divider-branch-viz' aria-hidden='true'>",
        unsafe_allow_html=True,
    )
    _na_label = html.escape("N/A (Synthetic)", quote=True)
    st.markdown(
        "<div class='cad-rads-summary-panel'>"
        f"<h3 class='cad-rads-main-title'>Patient CAD-RADS 2.0: {_na_label}</h3>"
        "<p><strong>Mode</strong>: Synthetic single-tube validation — clinical CAD-RADS, "
        "SIS, and AHA segment scoring are not applicable.</p>"
        "<p>Use the validation metrics and geodesic profile below to compare measured "
        "<strong>%AS</strong> and <strong>Area</strong> against the known ground truth "
        "of the phantom.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    branch_pairs = discover_synthetic_branch_xlsx(project_root, patient_id)
    branch_df = load_concat_branch_centerlines(branch_pairs)
    if branch_df.empty:
        branch_df = _filter_synthetic_vessel(total_df)

    metrics_source = branch_df if not branch_df.empty else _filter_synthetic_vessel(total_df)
    metrics = _load_validation_metrics(project_root, patient_id, metrics_source)
    _render_validation_metrics(metrics, patient_id)

    st.markdown(
        "<hr class='section-divider-branch-viz' aria-hidden='true'>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p class='branch-viz-window-line'>"
        f"<strong>REFERENCE WINDOW SIZE:</strong> ±{_win_esc} mm geodesic distance · "
        "<strong>Grey</strong> on the Area profile: outside the reference window (no %AS)."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h3 class='artery-plot-title'>Along-vessel geodesic profile</h3>",
        unsafe_allow_html=True,
    )

    try:
        fig_prof = create_synthetic_tube_geodesic_profile(branch_df)
        _prof_kw = dict(
            use_container_width=True,
            config=plotly_config,
            key=f"synthetic_profile_{patient_id}_{color_column}",
        )
        try:
            st.plotly_chart(fig_prof, **_prof_kw)
        except TypeError:
            _prof_kw.pop("key", None)
            st.plotly_chart(fig_prof, **_prof_kw)
    except Exception as ex_prof:
        st.caption(f"Along-vessel profile could not be built: {ex_prof}")
