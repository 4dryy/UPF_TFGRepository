"""
Plotly-based 3D viewers for the Streamlit dashboard.

Meshes are read with PyVista; traces are built with Plotly for inline interaction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pyvista as pv

# AHA 17-segment names (aligned with Block 3; unmapped IDs get a fallback label).
_SEGMENT_ID_TO_NAME: dict[int, str] = {
    1: "Proximal RCA",
    2: "Mid RCA",
    3: "Distal RCA",
    4: "Right PDA",
    5: "Left Main",
    6: "Proximal LAD",
    7: "Mid LAD",
    8: "Distal LAD",
    9: "First diagonal (D1)",
    10: "Second diagonal (D2)",
    11: "Proximal LCX",
    12: "First obtuse marginal (OM1)",
    13: "Distal LCX",
    14: "Second obtuse marginal (OM2)",
    15: "Left coronary PDA",
    16: "LCX inferolateral branch",
    17: "LCX posterolateral branch",
}


def _segment_label(sid: Any) -> str:
    try:
        i = int(sid)
    except (TypeError, ValueError):
        return "—"
    if i == 0:
        return "Unassigned"
    return _SEGMENT_ID_TO_NAME.get(i, f"Unmapped segment {i}")


def _mesh_to_mesh3d_traces(surf: pv.PolyData) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Triangulate if needed; return x,y,z vertices and i,j,k face indices for Plotly Mesh3d."""
    if not surf.is_all_triangles:
        surf = surf.triangulate()
    pts = np.asarray(surf.points, dtype=float)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    faces_flat = np.asarray(surf.faces, dtype=np.int64)
    if faces_flat.size == 0:
        return x, y, z, np.array([], dtype=np.int64), np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    # PyVista: [n, v0, v1, v2, n, v0, ...] for triangles n=3
    n_per = faces_flat[0]
    if n_per != 3:
        raise ValueError("Expected triangular faces for Mesh3d conversion")
    rest = faces_flat.reshape(-1, n_per + 1)
    if not np.all(rest[:, 0] == 3):
        raise ValueError("Mixed face sizes are not supported for Mesh3d")
    tri = rest[:, 1:4]
    i, j, k = tri[:, 0], tri[:, 1], tri[:, 2]
    return x, y, z, i, j, k


def create_3d_artery_plot(
    mesh_vtp_path: str,
    centerline_df: pd.DataFrame,
    color_variable: str,
    *,
    trace_name: str = "Centerline",
) -> go.Figure:
    """
    Build an interactive 3D figure: translucent outer mesh + colored centerline polyline.

    Parameters
    ----------
    mesh_vtp_path
        Path to ``surface_*.vtp`` from Block 1.
    centerline_df
        Rows for one artery; must include ``Px``, ``Py``, ``Pz``, ``Area``, ``pct_AS``,
        and ideally ``Segment_ID``.
    color_variable
        Column used for coloring: ``'pct_AS'`` or ``'Area'``.
    """
    path = Path(mesh_vtp_path)
    if not path.is_file():
        raise FileNotFoundError(f"Mesh not found: {path}")

    if centerline_df.empty:
        raise ValueError("Centerline dataframe has no rows.")

    required = {"Px", "Py", "Pz", color_variable}
    missing = required - set(centerline_df.columns)
    if missing:
        raise ValueError(f"Centerline dataframe missing columns: {sorted(missing)}")

    for col in ("Area", "pct_AS"):
        if col not in centerline_df.columns:
            raise ValueError(f"Centerline dataframe must include '{col}' for hover.")

    surf = pv.read(str(path))
    mx, my, mz, mi, mj, mk = _mesh_to_mesh3d_traces(surf)

    mesh_trace = go.Mesh3d(
        x=mx,
        y=my,
        z=mz,
        i=mi,
        j=mj,
        k=mk,
        color="lightgrey",
        opacity=0.2,
        flatshading=True,
        lighting=dict(ambient=0.85, diffuse=0.4, specular=0.15),
        hoverinfo="skip",
        showscale=False,
    )

    d = centerline_df.copy()
    x_cl = d["Px"].to_numpy(dtype=float)
    y_cl = d["Py"].to_numpy(dtype=float)
    z_cl = d["Pz"].to_numpy(dtype=float)

    seg_ids = d["Segment_ID"].to_numpy() if "Segment_ID" in d.columns else np.full(len(d), np.nan)
    seg_names: list[str] = []
    for idx in range(len(d)):
        if "Segment_Name" in d.columns and pd.notna(d["Segment_Name"].iloc[idx]):
            seg_names.append(str(d["Segment_Name"].iloc[idx]))
        else:
            seg_names.append(_segment_label(seg_ids[idx]))

    area_v = pd.to_numeric(d["Area"], errors="coerce")
    pct_v = pd.to_numeric(d["pct_AS"], errors="coerce")

    area_disp: list[str] = []
    pct_disp: list[str] = []
    for a, p in zip(area_v, pct_v):
        area_disp.append(f"{float(a):.4f}" if pd.notna(a) and np.isfinite(float(a)) else "n/a")
        pct_disp.append(f"{float(p):.2f}" if pd.notna(p) and np.isfinite(float(p)) else "n/a")

    raw_color = pd.to_numeric(d[color_variable], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(raw_color)
    if finite.any():
        cmin = float(np.nanmin(raw_color[finite]))
        cmax = float(np.nanmax(raw_color[finite]))
        if abs(cmax - cmin) < 1e-12:
            cmax = cmin + 1.0
    else:
        cmin, cmax = 0.0, 1.0

    display_color = raw_color.copy()
    display_color[~finite] = cmin

    colorscale = "Reds" if color_variable == "pct_AS" else "Viridis"

    seg_id_str: list[str] = []
    for s in seg_ids:
        if pd.isna(s) or str(s).strip() == "":
            seg_id_str.append("—")
        else:
            try:
                seg_id_str.append(str(int(float(s))))
            except (TypeError, ValueError):
                seg_id_str.append(str(s))

    customdata = np.stack(
        [
            np.array(seg_names, dtype=object),
            np.array(seg_id_str, dtype=object),
            np.array(area_disp, dtype=object),
            np.array(pct_disp, dtype=object),
        ],
        axis=1,
    )

    hovertemplate = (
        "<b>%{fullData.name}</b><br>"
        "Segment: %{customdata[0]}<br>"
        "Segment ID: %{customdata[1]}<br>"
        "Area: %{customdata[2]} mm²<br>"
        "%AS: %{customdata[3]}%"
        "<extra></extra>"
    )

    cb_title = "% area stenosis (pct_AS)" if color_variable == "pct_AS" else "Cross-sectional area (mm²)"

    centerline_trace = go.Scatter3d(
        name=trace_name,
        x=x_cl,
        y=y_cl,
        z=z_cl,
        mode="lines+markers",
        line=dict(
            color=display_color,
            colorscale=colorscale,
            cmin=cmin,
            cmax=cmax,
            width=5,
            showscale=False,
        ),
        marker=dict(
            size=5,
            color=display_color,
            colorscale=colorscale,
            cmin=cmin,
            cmax=cmax,
            showscale=True,
            colorbar=dict(title=cb_title, len=0.7),
        ),
        customdata=customdata,
        hovertemplate=hovertemplate,
    )

    fig = go.Figure(data=[mesh_trace, centerline_trace])
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, b=0, t=0),
        paper_bgcolor="white",
        scene=dict(
            aspectmode="data",
            xaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            yaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            zaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            bgcolor="white",
        ),
    )
    return fig
