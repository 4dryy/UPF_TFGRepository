"""Streamlit UI sections for synthetic single-tube validation cases."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.synthetic_profile import (
    is_stenosis_synthetic_patient,
    synthetic_validation_metrics,
)
from src.viewer.plots import (
    reference_window_mm,
    create_3d_artery_plot,
    create_synthetic_tube_geodesic_profile,
    discover_synthetic_branch_xlsx,
    load_concat_branch_centerlines,
)


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
        c1.metric("Theoretical %AS", _fmt_pct(metrics["theoretical_max_pct_as"]))
        c2.metric(
            "Predicted %AS",
            _fmt_pct(metrics["predicted_max_pct_as"]),
            delta=None if metrics["abs_error_max_pct_as"] is None else f"|Δ| {metrics['abs_error_max_pct_as']:.2f} %",
            delta_color="off",
        )
        c3.metric("|Abs. Error %AS|", _fmt_pct(metrics["abs_error_max_pct_as"]))

        c4, c5, c6 = st.columns(3)
        c4.metric(
            "Theoretical Area",
            _fmt_area(metrics.get("theoretical_mean_area_mm2")),
            help="Analytical πR² along the healthy phantom (constant R = 10 mm → 314.16 mm²).",
        )
        c5.metric(
            "Predicted Mean Area",
            _fmt_area(metrics.get("predicted_mean_area_mm2")),
            delta=(
                None
                if metrics.get("abs_error_mean_area_mm2") is None
                else f"|Δ| {metrics['abs_error_mean_area_mm2']:.2f} mm²"
            ),
            delta_color="off",
            help="Mean of predicted lumen Area across all centerline samples on the vessel body.",
        )
        c6.metric(
            "|Abs. Error Mean Area|",
            _fmt_area(metrics.get("abs_error_mean_area_mm2")),
        )

        c7, c8 = st.columns(2)
        c7.metric(
            "Mean Area Absolute Error",
            _fmt_area(metrics["mean_area_abs_error_mm2"]),
            help="Mean of |A_predicted(z) − A_theoretical(z)| along the vessel tube.",
        )
        c8.metric(
            "Maximum Area Deviation",
            _fmt_area(metrics["max_area_abs_deviation_mm2"]),
            help="Maximum of |A_predicted(z) − A_theoretical(z)| along the vessel tube.",
        )
    else:
        st.caption(
            "Stenosis phantom (cosine narrowing, R_min = 5 mm at Z = 50 mm) — peak %AS ≈ 75% "
            "and lumen area should range from 314.16 → 78.54 mm²."
        )
        st.markdown("**Maximum %AS**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Theoretical Max %AS", _fmt_pct(metrics["theoretical_max_pct_as"]))
        c2.metric(
            "Predicted Max %AS",
            _fmt_pct(metrics["predicted_max_pct_as"]),
            delta=None if metrics["abs_error_max_pct_as"] is None else f"|Δ| {metrics['abs_error_max_pct_as']:.2f} %",
            delta_color="off",
        )
        c3.metric("|Abs. Error Max %AS|", _fmt_pct(metrics["abs_error_max_pct_as"]))

        st.markdown("**Maximum Area**")
        d1, d2, d3 = st.columns(3)
        d1.metric("Theoretical Max Area", _fmt_area(metrics["theoretical_max_area_mm2"]))
        d2.metric(
            "Predicted Max Area",
            _fmt_area(metrics["predicted_max_area_mm2"]),
            delta=f"|Δ| {metrics['abs_error_max_area_mm2']:.2f} mm²",
            delta_color="off",
        )
        d3.metric("|Abs. Error Max Area|", _fmt_area(metrics["abs_error_max_area_mm2"]))

        st.markdown("**Minimum Area**")
        e1, e2, e3 = st.columns(3)
        e1.metric("Theoretical Min Area", _fmt_area(metrics["theoretical_min_area_mm2"]))
        e2.metric(
            "Predicted Min Area",
            _fmt_area(metrics["predicted_min_area_mm2"]),
            delta=f"|Δ| {metrics['abs_error_min_area_mm2']:.2f} mm²",
            delta_color="off",
        )
        e3.metric("|Abs. Error Min Area|", _fmt_area(metrics["abs_error_min_area_mm2"]))


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
