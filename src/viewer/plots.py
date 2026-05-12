"""
Plotly-based 3D viewers for the Streamlit dashboard.

Meshes are read with PyVista; traces are built with Plotly for inline interaction.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pyvista as pv

# Branch viewer colors (match Streamlit dashboard + extrema highlights).
_BRANCH_PROFILE_ORANGE = "#f57c00"
_BRANCH_PROFILE_BLUE = "#0092c7"
_BRANCH_EXTREMA_PURPLE = "#a855f7"

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


def _mesh_to_mesh3d_traces(
    surf: pv.PolyData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Triangulate if needed; return x,y,z vertices and i,j,k face indices for Plotly Mesh3d."""
    if not surf.is_all_triangles:
        surf = surf.triangulate()
    pts = np.asarray(surf.points, dtype=float)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    faces_flat = np.asarray(surf.faces, dtype=np.int64)
    if faces_flat.size == 0:
        return x, y, z, np.array([], dtype=np.int64), np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    n_per = faces_flat[0]
    if n_per != 3:
        raise ValueError("Expected triangular faces for Mesh3d conversion")
    rest = faces_flat.reshape(-1, n_per + 1)
    if not np.all(rest[:, 0] == 3):
        raise ValueError("Mixed face sizes are not supported for Mesh3d")
    tri = rest[:, 1:4]
    i, j, k = tri[:, 0], tri[:, 1], tri[:, 2]
    return x, y, z, i, j, k


def _sort_branch_rows(g: pd.DataFrame) -> pd.DataFrame:
    """Order points along one branch polyline."""
    if g.empty:
        return g
    g2 = g.copy()
    if "gd" in g2.columns:
        return g2.sort_values("gd", ascending=True).reset_index(drop=True)
    if "Path_Point_Index" in g2.columns:
        return g2.sort_values("Path_Point_Index", ascending=True).reset_index(drop=True)
    return g2.sort_values(["Px", "Py", "Pz"]).reset_index(drop=True)


def _format_area(a: Any) -> str:
    try:
        v = float(a)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(v):
        return "n/a"
    return f"{v:.4f}"


def _format_pct(p: Any) -> str:
    try:
        v = float(p)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(v):
        return "n/a"
    return f"{v:.2f}"


def _segment_display_name(row: pd.Series) -> str:
    if "Segment_Name" in row.index and pd.notna(row.get("Segment_Name")):
        return str(row["Segment_Name"]).strip()
    sid = row.get("Segment_ID")
    return _segment_label(sid)


def _segment_id_display(row: pd.Series) -> str:
    sid = row.get("Segment_ID")
    if pd.isna(sid) or str(sid).strip() == "":
        return "—"
    try:
        return str(int(float(sid)))
    except (TypeError, ValueError):
        return str(sid)


def _artery_type_display(row: pd.Series) -> str:
    if "Artery_Type" in row.index and pd.notna(row.get("Artery_Type")):
        return str(row["Artery_Type"]).strip()
    return "—"


def _branch_sort_key(branch_id: Any) -> tuple[Any, ...]:
    """Stable ordering for Branch_ID (e.g. LCA_B01 … LCA_B10 without lexicographic B10<B2)."""
    s = str(branch_id).strip() if branch_id is not None else ""
    m = re.search(r"_B(\d+)$", s, flags=re.IGNORECASE)
    if m:
        prefix = s[: m.start()]
        return (prefix.upper(), int(m.group(1)))
    return (s.upper(), 0)


def _parse_branch_id_from_dataset_xlsx_name(filename: str, patient_id: str) -> str | None:
    """``dataset_<Branch_ID>_<patient_id>.xlsx`` → ``Branch_ID``."""
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


def discover_block3_label_branch_xlsx(project_root: Path, patient_id: str, artery: str) -> list[tuple[str, Path]]:
    """
    Branch spreadsheets (``dataset_<Branch_ID>_<patient_id>.xlsx``) under
    ``results/block3_results/label/<patient_id>/branches/dataframes/`` for ``artery`` ``LCA`` or ``RCA``.
    """
    art = str(artery).strip().upper()
    if art not in ("LCA", "RCA"):
        raise ValueError("artery must be 'LCA' or 'RCA'")
    base = project_root / "results" / "block3_results" / "label" / patient_id / "branches" / "dataframes"
    if not base.is_dir():
        return []
    prefix = f"{art}_"
    out: list[tuple[str, Path]] = []
    for p in sorted(base.glob("dataset_*.xlsx")):
        bid = _parse_branch_id_from_dataset_xlsx_name(p.name, patient_id)
        if bid and str(bid).strip().upper().startswith(prefix):
            out.append((str(bid).strip(), p.resolve()))
    out.sort(key=lambda t: _branch_sort_key(t[0]))
    return out


def load_concat_branch_centerlines(branch_pairs: list[tuple[str, Path]]) -> pd.DataFrame:
    """Read each branch Excel and concatenate; inject ``Branch_ID`` from the filename if missing."""
    pieces: list[pd.DataFrame] = []
    for bid, path in branch_pairs:
        try:
            df = pd.read_excel(path)
        except (OSError, ValueError):
            continue
        if df.empty:
            continue
        df = df.copy()
        if "Branch_ID" not in df.columns:
            df["Branch_ID"] = bid
        df["Branch_ID"] = df["Branch_ID"].astype(str).str.strip()
        pieces.append(df)
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, ignore_index=True)


def _percentile_clim(values: np.ndarray, p_low: float = 5.0, p_high: float = 95.0) -> tuple[float, float]:
    """Robust color limits from percentiles; fallback when degenerate."""
    v = values[np.isfinite(values)]
    if v.size == 0:
        return 0.0, 1.0
    cmin = float(np.percentile(v, p_low))
    cmax = float(np.percentile(v, p_high))
    if not np.isfinite(cmin) or not np.isfinite(cmax) or abs(cmax - cmin) < 1e-12:
        cmin = float(np.nanmin(v))
        cmax = float(np.nanmax(v))
        if abs(cmax - cmin) < 1e-12:
            cmax = cmin + 1.0
    return cmin, cmax


def _argmax_finite_index(values: np.ndarray) -> int | None:
    """Index of the maximum among finite values; ``None`` if none are finite."""
    v = np.asarray(values, dtype=float)
    mask = np.isfinite(v)
    if not mask.any():
        return None
    idx = np.flatnonzero(mask)
    j = int(np.argmax(v[mask]))
    return int(idx[j])


def create_3d_mesh_branch_path_highlight(
    mesh_vtp_path: str,
    centerline_df: pd.DataFrame,
    *,
    selected_branch_id: str,
    trace_name: str = "LCA",
) -> go.Figure:
    """
    Artery mesh + full centerline tree (small black markers) with **one** branch path
    highlighted by ``pct_AS`` (Reds). Color limits use the 5th–95th percentile of finite
    ``pct_AS`` over **all** concatenated branch points.

    Adds a **purple diamond** at the branch centerline point with **maximum finite %AS**
    (Area at that point is shown in the marker hover when available).

    ``centerline_df`` must include ``Px``, ``Py``, ``Pz``, ``pct_AS``, and ``Branch_ID``.
    ``trace_name`` is used in trace labels (typically ``LCA`` or ``RCA``).
    """
    path = Path(mesh_vtp_path)
    if not path.is_file():
        raise FileNotFoundError(f"Mesh not found: {path}")
    if centerline_df.empty:
        raise ValueError("Centerline dataframe has no rows.")

    required = {"Px", "Py", "Pz", "pct_AS", "Branch_ID"}
    missing = required - set(centerline_df.columns)
    if missing:
        raise ValueError(f"Branch highlight dataframe missing columns: {sorted(missing)}")

    d = centerline_df.copy()
    d["_branch_key"] = d["Branch_ID"].astype(str).str.strip()
    sel = str(selected_branch_id).strip()
    d_sel = d.loc[d["_branch_key"] == sel].copy().drop(columns=["_branch_key"], errors="ignore")
    if d_sel.empty:
        raise ValueError(f"No rows for selected branch {sel!r}.")

    raw_all = pd.to_numeric(d["pct_AS"], errors="coerce").to_numpy(dtype=float)
    valid_all = np.isfinite(raw_all)
    if valid_all.any():
        cmin, cmax = _percentile_clim(raw_all[valid_all], 5.0, 95.0)
    else:
        cmin, cmax = 0.0, 1.0

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
        showlegend=False,
        showscale=False,
    )

    traces: list[go.BaseTraceType] = [mesh_trace]

    # --- Full tree in black (same branch order / NaN breaks as main artery plot) ---
    d_tree = d.drop(columns=["_branch_key"], errors="ignore")
    branch_groups = list(d_tree.groupby("Branch_ID", sort=False))
    non_empty: list[tuple[Any, pd.DataFrame]] = []
    for _bid, g_raw in branch_groups:
        g_sorted = _sort_branch_rows(g_raw)
        if len(g_sorted) >= 1:
            non_empty.append((_bid, g_sorted))
    if not non_empty:
        g_fallback = _sort_branch_rows(d_tree)
        if len(g_fallback) >= 1:
            non_empty = [(trace_name, g_fallback)]
    non_empty.sort(key=lambda t: _branch_sort_key(t[0]))

    xs_b: list[float] = []
    ys_b: list[float] = []
    zs_b: list[float] = []
    _nan = float("nan")
    for bi, (_bid, g) in enumerate(non_empty):
        if bi > 0:
            xs_b.append(_nan)
            ys_b.append(_nan)
            zs_b.append(_nan)
        for _, row in g.iterrows():
            xs_b.append(float(row["Px"]))
            ys_b.append(float(row["Py"]))
            zs_b.append(float(row["Pz"]))

    traces.append(
        go.Scatter3d(
            name=f"{trace_name} · tree",
            x=np.asarray(xs_b, dtype=float),
            y=np.asarray(ys_b, dtype=float),
            z=np.asarray(zs_b, dtype=float),
            mode="lines+markers",
            line=dict(color="rgb(0,0,0)", width=2.5),
            marker=dict(size=2.5, color="rgb(0,0,0)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # --- Selected branch: %AS coloring (Reds) ---
    g_sel = _sort_branch_rows(d_sel)
    xs_s = g_sel["Px"].to_numpy(dtype=float)
    ys_s = g_sel["Py"].to_numpy(dtype=float)
    zs_s = g_sel["Pz"].to_numpy(dtype=float)
    c_s = pd.to_numeric(g_sel["pct_AS"], errors="coerce").to_numpy(dtype=float)

    hover_sel: list[str] = []
    for _, row in g_sel.iterrows():
        hover_sel.append(
            f"<b>{sel}</b><br>"
            f"Artery: {_artery_type_display(row)}<br>"
            f"Segment: {_segment_display_name(row)}<br>"
            f"Segment ID: {_segment_id_display(row)}<br>"
            f"Area: {_format_area(row.get('Area'))} mm²<br>"
            f"pct AS: {_format_pct(row.get('pct_AS'))} %"
        )

    marker_sel: dict[str, Any] = dict(
        size=8,
        color=c_s,
        colorscale="Reds",
        cmin=cmin,
        cmax=cmax,
        showscale=True,
        colorbar=dict(
            title=dict(
                text="% area stenosis (pct_AS)",
                side="right",
                font=dict(color="black", size=13),
            ),
            tickfont=dict(color="black", size=12),
            len=0.65,
        ),
    )

    traces.append(
        go.Scatter3d(
            name=f"{trace_name} · {sel}",
            x=xs_s,
            y=ys_s,
            z=zs_s,
            mode="lines+markers",
            line=dict(color=c_s, colorscale="Reds", cmin=cmin, cmax=cmax, width=6.5, showscale=False),
            marker=marker_sel,
            text=hover_sel,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    # --- Branch maximum %AS (purple diamond); Area at same point shown in hover ---
    pct_num = pd.to_numeric(g_sel["pct_AS"], errors="coerce").to_numpy(dtype=float)
    idx_max_pct = _argmax_finite_index(pct_num)

    if idx_max_pct is not None:
        row = g_sel.iloc[idx_max_pct]
        lines_h = [
            f"<b>{sel} · max %AS · centerline point {idx_max_pct + 1}</b>",
            f"Artery: {_artery_type_display(row)}",
            f"<b>Max %AS on branch</b>: {_format_pct(row.get('pct_AS'))} %",
        ]
        if "Area" in g_sel.columns:
            lines_h.append(f"<b>Area at this point</b>: {_format_area(row.get('Area'))} mm²")
        traces.append(
            go.Scatter3d(
                name=f"{trace_name} · {sel} · max %AS",
                x=np.asarray([float(row["Px"])], dtype=float),
                y=np.asarray([float(row["Py"])], dtype=float),
                z=np.asarray([float(row["Pz"])], dtype=float),
                mode="markers",
                marker=dict(
                    size=20,
                    color=_BRANCH_EXTREMA_PURPLE,
                    symbol="diamond",
                    line=dict(color="#fafafa", width=2.5),
                    opacity=1.0,
                ),
                text=["<br>".join(lines_h)],
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            )
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        showlegend=False,
        autosize=True,
        height=560,
        margin=dict(l=0, r=0, b=0, t=0),
        paper_bgcolor="white",
        scene=dict(
            aspectmode="data",
            domain=dict(x=[0.0, 1.0], y=[0.0, 1.0]),
            xaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            yaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            zaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            bgcolor="white",
        ),
    )
    return fig


def create_3d_artery_plot(
    mesh_vtp_path: str,
    centerline_df: pd.DataFrame,
    color_variable: str,
    *,
    trace_name: str = "Centerline",
) -> go.Figure:
    """
    Build an interactive 3D figure: translucent outer mesh + **one** centerline trace
    (all branches concatenated with coordinate ``NaN`` breaks so lines do not connect
    across the tree) + optional NaN marker cloud.

    Color scale for quantified points uses the 5th–95th percentile of ``color_variable``
    (finite values only) as ``cmin``/``cmax``.
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
        showlegend=False,
        showscale=False,
    )

    d = centerline_df.copy()
    raw_color = pd.to_numeric(d[color_variable], errors="coerce").to_numpy(dtype=float)
    valid_mask = np.isfinite(raw_color)

    # Global colormap limits from sample (5th–95th percentile of quantified points).
    if valid_mask.any():
        cmin, cmax = _percentile_clim(raw_color[valid_mask], 5.0, 95.0)
    else:
        cmin, cmax = 0.0, 1.0

    colorscale = "Reds" if color_variable == "pct_AS" else "Viridis"
    cb_title = "% area stenosis (pct_AS)" if color_variable == "pct_AS" else "Cross-sectional area (mm²)"

    traces: list[go.BaseTraceType] = [mesh_trace]

    d_valid = d.loc[valid_mask].copy()
    d_nan = d.loc[~valid_mask].copy()

    # --- Single centerline trace: branches in order, separated by NaN (no cross-branch lines) ---
    if not d_valid.empty:
        if "Branch_ID" in d_valid.columns:
            branch_groups = list(d_valid.groupby("Branch_ID", sort=False))
        else:
            branch_groups = [(trace_name, d_valid)]

        non_empty_branches: list[tuple[Any, pd.DataFrame]] = []
        for _bid, g_raw in branch_groups:
            g_sorted = _sort_branch_rows(g_raw)
            if len(g_sorted) >= 1:
                non_empty_branches.append((_bid, g_sorted))

        if not non_empty_branches:
            g_fallback = _sort_branch_rows(d_valid)
            if len(g_fallback) >= 1:
                non_empty_branches = [(trace_name, g_fallback)]

        non_empty_branches.sort(key=lambda t: _branch_sort_key(t[0]))

        xs_list: list[float] = []
        ys_list: list[float] = []
        zs_list: list[float] = []
        c_list: list[float] = []
        hover_texts: list[str] = []
        _nan = float("nan")

        for bi, (_bid, g) in enumerate(non_empty_branches):
            if bi > 0:
                xs_list.append(_nan)
                ys_list.append(_nan)
                zs_list.append(_nan)
                c_list.append(_nan)
                hover_texts.append("")

            for _, row in g.iterrows():
                xs_list.append(float(row["Px"]))
                ys_list.append(float(row["Py"]))
                zs_list.append(float(row["Pz"]))
                c_list.append(float(pd.to_numeric(row[color_variable], errors="coerce")))
                hover_texts.append(
                    f"<b>{trace_name}</b><br>"
                    f"Artery: {_artery_type_display(row)}<br>"
                    f"Segment: {_segment_display_name(row)}<br>"
                    f"Segment ID: {_segment_id_display(row)}<br>"
                    f"Area: {_format_area(row.get('Area'))} mm²<br>"
                    f"%AS: {_format_pct(row.get('pct_AS'))} %"
                )

        xs_arr = np.asarray(xs_list, dtype=float)
        ys_arr = np.asarray(ys_list, dtype=float)
        zs_arr = np.asarray(zs_list, dtype=float)
        c_arr = np.asarray(c_list, dtype=float)

        # Plotly hovertemplate treats "%" as special; literal "%AS" / trailing "%" broke tooltips.
        hovertemplate = "%{text}<extra></extra>"

        marker_kw: dict[str, Any] = dict(
            size=6,
            color=c_arr,
            colorscale=colorscale,
            cmin=cmin,
            cmax=cmax,
            showscale=True,
            colorbar=dict(
                title=dict(text=cb_title, side="right", font=dict(color="black", size=13)),
                tickfont=dict(color="black", size=12),
                len=0.65,
            ),
        )

        traces.append(
            go.Scatter3d(
                name=trace_name,
                x=xs_arr,
                y=ys_arr,
                z=zs_arr,
                mode="lines+markers",
                line=dict(
                    color=c_arr,
                    colorscale=colorscale,
                    cmin=cmin,
                    cmax=cmax,
                    width=5,
                    showscale=False,
                ),
                marker=marker_kw,
                text=hover_texts,
                hovertemplate=hovertemplate,
                showlegend=False,
            )
        )

    # --- NaN / out-of-range color variable: markers only ---
    if not d_nan.empty:
        xs_n = d_nan["Px"].to_numpy(dtype=float)
        ys_n = d_nan["Py"].to_numpy(dtype=float)
        zs_n = d_nan["Pz"].to_numpy(dtype=float)

        hover_nan_texts: list[str] = []
        for _, row in d_nan.iterrows():
            hover_nan_texts.append(
                "<b>Unquantified</b><br>"
                f"Artery: {_artery_type_display(row)}<br>"
                f"Segment: {_segment_display_name(row)}<br>"
                f"Segment ID: {_segment_id_display(row)}<br>"
                f"Area: {_format_area(row.get('Area'))} mm²<br>"
                "<b>Value Out of Calculation Range</b>"
            )

        traces.append(
            go.Scatter3d(
                name=f"{trace_name} · unquantified",
                x=xs_n,
                y=ys_n,
                z=zs_n,
                mode="markers",
                marker=dict(color="black", size=5),
                text=hover_nan_texts,
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            )
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        showlegend=False,
        autosize=True,
        height=560,
        margin=dict(l=0, r=0, b=0, t=0),
        paper_bgcolor="white",
        scene=dict(
            aspectmode="data",
            domain=dict(x=[0.0, 1.0], y=[0.0, 1.0]),
            xaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            yaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            zaxis=dict(visible=False, showgrid=False, zeroline=False, showticklabels=False, showbackground=False),
            bgcolor="white",
        ),
    )
    return fig


def _find_df_column(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return first present column, matching case-insensitively if needed."""
    if df.empty or not len(df.columns):
        return None
    exact = set(df.columns)
    for c in candidates:
        if c in exact:
            return c
    lower = {str(col).lower(): col for col in df.columns}
    for c in candidates:
        cl = c.lower()
        if cl in lower:
            return str(lower[cl])
    return None


def create_branch_centerline_metric_bars(
    centerline_df: pd.DataFrame,
    *,
    selected_branch_id: str,
    artery: str,
) -> go.Figure:
    """
    Interactive paired bar charts along the ordered centerline of **one** branch:
    row 1 — ``Area`` (cyan blue); row 2 — ``pct_AS`` (orange). Transparent figure backgrounds.

    Bars at the **maximum finite %AS** index are purple on **both** rows (same centerline
    point: peak stenosis and its cross-sectional area). Hovers show both metrics at each point.

    ``centerline_df`` is the concatenated Block 3 label branch table (must include
    ``Branch_ID``; rows are ordered with ``gd`` or ``Path_Point_Index`` when present).
    """
    if centerline_df.empty or "Branch_ID" not in centerline_df.columns:
        raise ValueError("Branch dataframe is empty or missing Branch_ID.")

    pct_col = _find_df_column(centerline_df, "pct_AS", "Pct_AS", "PCT_AS")
    area_col = _find_df_column(centerline_df, "Area")
    if not pct_col:
        raise ValueError("No %AS column found (expected pct_AS).")
    if not area_col:
        raise ValueError("No Area column found in branch spreadsheet.")

    sel = str(selected_branch_id).strip()
    d = centerline_df.copy()
    d["_branch_key"] = d["Branch_ID"].astype(str).str.strip()
    sub = d.loc[d["_branch_key"] == sel].drop(columns=["_branch_key"], errors="ignore")
    if sub.empty:
        raise ValueError(f"No rows for branch {sel!r}.")

    sub = _sort_branch_rows(sub)
    n = len(sub)
    if n == 0:
        raise ValueError("Selected branch has no centerline points.")

    x_labels = [str(i + 1) for i in range(n)]
    pct_y = pd.to_numeric(sub[pct_col], errors="coerce").to_numpy(dtype=float)
    area_y = pd.to_numeric(sub[area_col], errors="coerce").to_numpy(dtype=float)

    idx_max_pct = _argmax_finite_index(pct_y)

    col_area: list[str] = [_BRANCH_PROFILE_BLUE] * n
    col_pct: list[str] = [_BRANCH_PROFILE_ORANGE] * n
    if idx_max_pct is not None:
        col_area[idx_max_pct] = _BRANCH_EXTREMA_PURPLE
        col_pct[idx_max_pct] = _BRANCH_EXTREMA_PURPLE

    if "gd" in sub.columns and np.isfinite(pd.to_numeric(sub["gd"], errors="coerce").to_numpy(dtype=float)).any():
        gd_vals = pd.to_numeric(sub["gd"], errors="coerce").to_numpy(dtype=float)
        custom_cd = np.column_stack([pct_y, area_y, gd_vals])
        hover_pct = (
            "<b>Point %{x}</b> (proximal→distal)<br>"
            "<b>gd</b>: %{customdata[2]:.4f}<br>"
            "<b>%AS</b>: %{y:.2f}<br>"
            "<b>Area</b>: %{customdata[1]:.4f} mm²<extra></extra>"
        )
        hover_area = (
            "<b>Point %{x}</b> (proximal→distal)<br>"
            "<b>gd</b>: %{customdata[2]:.4f}<br>"
            "<b>Area</b>: %{y:.4f} mm²<br>"
            "<b>%AS</b>: %{customdata[0]:.2f}<extra></extra>"
        )
    else:
        custom_cd = np.column_stack([pct_y, area_y])
        hover_pct = (
            "<b>Point %{x}</b> (proximal→distal)<br>"
            "<b>%AS</b>: %{y:.2f}<br>"
            "<b>Area</b>: %{customdata[1]:.4f} mm²<extra></extra>"
        )
        hover_area = (
            "<b>Point %{x}</b><br>"
            "<b>Area</b>: %{y:.4f} mm²<br>"
            "<b>%AS</b>: %{customdata[0]:.2f}<extra></extra>"
        )

    art = str(artery).strip().upper()
    title_area = f"Cross-sectional area along centerline · {art} · {sel}"
    title_pct = f"% area stenosis along centerline · {art} · {sel}"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.11,
        subplot_titles=(title_area, title_pct),
    )

    fig.add_trace(
        go.Bar(
            x=x_labels,
            y=area_y,
            name="Area",
            marker=dict(color=col_area, line=dict(width=0), opacity=0.92),
            customdata=custom_cd,
            hovertemplate=hover_area,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=x_labels,
            y=pct_y,
            name="%AS",
            marker=dict(color=col_pct, line=dict(width=0), opacity=0.92),
            customdata=custom_cd,
            hovertemplate=hover_pct,
        ),
        row=2,
        col=1,
    )

    grid_kw: dict[str, Any] = dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.14)",
        zeroline=True,
        zerolinecolor="rgba(255,255,255,0.28)",
        zerolinewidth=1,
    )
    fig.update_xaxes(
        title_text="Centerline point index (1 = proximal)",
        tickangle=-60 if n > 35 else -45,
        showline=True,
        linecolor="rgba(255,255,255,0.35)",
        mirror=True,
        **grid_kw,
        row=2,
        col=1,
    )
    fig.update_xaxes(**grid_kw, row=1, col=1)
    fig.update_yaxes(
        title_text="Area (mm²)",
        title_font=dict(color="#f0f0f0", size=13),
        showline=True,
        linecolor="rgba(255,255,255,0.35)",
        mirror=True,
        **grid_kw,
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text="%AS",
        title_font=dict(color="#f0f0f0", size=13),
        showline=True,
        linecolor="rgba(255,255,255,0.35)",
        mirror=True,
        **grid_kw,
        row=2,
        col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e8e8e8", family="Inter, Segoe UI, system-ui, sans-serif", size=12),
        margin=dict(t=72, r=24, b=56, l=64),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#2d2d2d", font_size=12),
        showlegend=False,
        height=640,
        bargap=0.22,
    )
    fig.update_annotations(font=dict(color="#e0e0e0", size=13))
    return fig
