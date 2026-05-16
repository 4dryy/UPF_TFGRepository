"""Streamlit UI sections for synthetic single-tube validation cases."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.viewer.plots import (
    create_3d_artery_plot,
    create_branch_centerline_metric_bars,
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


def _branch_sort_key(branch_id: Any) -> tuple[Any, ...]:
    s = str(branch_id).strip() if branch_id is not None else ""
    m = re.search(r"_B(\d+)$", s, flags=re.IGNORECASE)
    if m:
        prefix = s[: m.start()]
        return (prefix.upper(), int(m.group(1)))
    return (s.upper(), 0)


def _parse_branch_id_from_dataset_xlsx_name(filename: str, patient_id: str) -> str | None:
    if not filename.lower().endswith(".xlsx"):
        return None
    stem = filename[:-5]
    suf = f"_{patient_id}"
    if not stem.endswith(suf):
        return None
    head = stem[: -len(suf)]
    if not head.startswith("dataset_"):
        return None
    return head[len("dataset_") :]


def _sort_branch_rows(g: pd.DataFrame) -> pd.DataFrame:
    if g.empty:
        return g
    g2 = g.copy()
    if "gd" in g2.columns:
        return g2.sort_values("gd", ascending=True).reset_index(drop=True)
    if "Path_Point_Index" in g2.columns:
        return g2.sort_values("Path_Point_Index", ascending=True).reset_index(drop=True)
    return g2.sort_values(["Px", "Py", "Pz"]).reset_index(drop=True)


def discover_synthetic_branch_xlsx(project_root: Path, patient_id: str) -> list[tuple[str, Path]]:
    """Branch spreadsheets for a synthetic single-tube case (``Artery_Type == Synthetic``)."""
    base = (
        project_root
        / "results"
        / "block3_results"
        / "label"
        / patient_id
        / "branches"
        / "dataframes"
    )
    if not base.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for p in sorted(base.glob("dataset_*.xlsx")):
        bid = _parse_branch_id_from_dataset_xlsx_name(p.name, patient_id)
        if not bid:
            continue
        try:
            df = pd.read_excel(p, nrows=1)
        except (OSError, ValueError):
            continue
        if df.empty or "Artery_Type" not in df.columns:
            continue
        if str(df["Artery_Type"].iloc[0]).strip() != "Synthetic":
            continue
        branch_key = str(df["Branch_ID"].iloc[0]).strip() if "Branch_ID" in df.columns else bid
        out.append((branch_key, p.resolve()))
    out.sort(key=lambda t: _branch_sort_key(str(t[0])))
    return out


def create_synthetic_tube_geodesic_profile(centerline_df: pd.DataFrame) -> go.Figure:
    """Single continuous Area + %AS profile along the synthetic vessel."""
    if centerline_df.empty:
        raise ValueError("Synthetic centerline dataframe is empty.")
    d = _sort_branch_rows(centerline_df.copy())
    if "Branch_ID" not in d.columns:
        d["Branch_ID"] = 0
    branch_key = str(d["Branch_ID"].iloc[0]).strip()
    return create_branch_centerline_metric_bars(
        d,
        selected_branch_id=branch_key,
        artery="Synthetic",
    )


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
        st.markdown(
            "<h3 class='artery-plot-title'>Synthetic validation vessel</h3>",
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
