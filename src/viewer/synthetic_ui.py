"""Streamlit UI sections for synthetic single-tube validation cases."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st

from src.viewer.plots import (
    reference_window_mm,
    create_3d_artery_plot,
    create_synthetic_tube_geodesic_profile,
    discover_synthetic_branch_xlsx,
    load_concat_branch_centerlines,
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
        "<p>Use the geodesic profile below to compare measured <strong>%AS</strong> and "
        "<strong>Area</strong> against the known ground truth of the phantom.</p>"
        "</div>",
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
    branch_pairs = discover_synthetic_branch_xlsx(project_root, patient_id)
    branch_df = load_concat_branch_centerlines(branch_pairs)
    if branch_df.empty:
        branch_df = _filter_synthetic_vessel(total_df)
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
