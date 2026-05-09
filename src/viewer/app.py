"""
Streamlit entrypoint for Block 4 visualization.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.viewer.plots import create_3d_artery_plot

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSION_PATH = PROJECT_ROOT / "results" / "current_session.json"

AUTHOR_NAME = "Adrià Cortés Cugat"
DEGREE_NAME = "Mathematical Engineering in Data Science"

COLOR_LABEL_TO_COLUMN = {
    "Percent Area Stenosis (%AS)": "pct_AS",
    "Cross-sectional Area": "Area",
}


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

    patient_id = _load_patient_id()
    if patient_id is None:
        st.warning(
            "No active session found at results/current_session.json. "
            "Run the pipeline first to select a patient."
        )
        patient_id = "Unknown Patient"

    st.title(f"Coronary Analysis: {patient_id}")

    st.subheader("Global Control")
    color_label = st.radio(
        "Color Mapping Variable",
        options=list(COLOR_LABEL_TO_COLUMN.keys()),
        horizontal=True,
        key="color_mapping_variable",
    )
    color_column = COLOR_LABEL_TO_COLUMN[color_label]

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
                col_lca, col_rca = st.columns(2)

                with col_lca:
                    st.subheader("Left Coronary Artery (LCA)")
                    if st.button("Reset view", key="reset_btn_lca"):
                        st.session_state.reset_lca += 1
                    try:
                        df_lca = _sort_centerline_subset(_filter_artery(total_df, "LCA"))
                        if df_lca.empty:
                            st.warning("LCA data not found or could not be loaded for this patient.")
                        else:
                            fig_lca = create_3d_artery_plot(
                                str(mesh_lca),
                                df_lca,
                                color_column,
                                trace_name="LCA centerline",
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
                    except Exception:
                        st.warning("LCA data not found or could not be loaded for this patient.")

                with col_rca:
                    st.subheader("Right Coronary Artery (RCA)")
                    if st.button("Reset view", key="reset_btn_rca"):
                        st.session_state.reset_rca += 1
                    try:
                        df_rca = _sort_centerline_subset(_filter_artery(total_df, "RCA"))
                        if df_rca.empty:
                            st.warning("RCA data not found or could not be loaded for this patient.")
                        else:
                            fig_rca = create_3d_artery_plot(
                                str(mesh_rca),
                                df_rca,
                                color_column,
                                trace_name="RCA centerline",
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
                    except Exception:
                        st.warning("RCA data not found or could not be loaded for this patient.")

    st.markdown("---")
    st.caption(f"Author: {AUTHOR_NAME}")
    st.caption(f"Degree: {DEGREE_NAME}")
    st.caption("Final Degree Project (TFG)")


if __name__ == "__main__":
    main()
