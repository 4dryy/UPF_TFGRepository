"""
Plotly-based 3D viewers for the Streamlit dashboard.

Meshes are read with PyVista; traces are built with Plotly for inline interaction.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative as plotly_qualitative
from plotly.subplots import make_subplots
import pyvista as pv

def _window_mm_from_block2_source() -> float | None:
    """Parse active ``WINDOW_MM = …`` from disk (ignores commented-out alternatives)."""
    from src.blocks import _02_stenosis as block2

    path = Path(block2.__file__).resolve()
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("WINDOW_MM"):
            _, _, rhs = stripped.partition("=")
            try:
                return float(rhs.strip())
            except ValueError:
                return None
    return None


def reference_window_mm() -> float:
    """Live Block 2 ``WINDOW_MM``; reload Block 2 if Streamlit still has a stale import cache."""
    from src.blocks._02_stenosis import reference_window_mm as _rw

    live = float(_rw())
    on_disk = _window_mm_from_block2_source()
    if on_disk is not None and abs(live - on_disk) > 1e-9:
        for mod_name in ("src.synthetic_profile", "src.blocks._02_stenosis"):
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
        import src.blocks._02_stenosis as block2

        live = float(block2.reference_window_mm())
    return live


# Branch viewer colors (match Streamlit dashboard + extrema highlights).
_BRANCH_PROFILE_ORANGE = "#f57c00"
_BRANCH_PROFILE_BLUE = "#0092c7"
PROFILE_QUANTIFIED_AREA_BLUE = _BRANCH_PROFILE_BLUE
_BRANCH_EXTREMA_PURPLE = "#a855f7"
_BRANCH_REF_WINDOW_GREEN = "#2e7d32"
_BRANCH_UNQUANTIFIED_BLACK = "#1a1a1a"  # %AS profile row: outside ±window reference (matches 3D unquantified)
_BRANCH_UNQUANTIFIED_AREA_GREY = "#9ca3af"  # Area profile row only: outside ±window (visible on dark background)
PROFILE_AREA_OUTSIDE_REFERENCE_GREY = _BRANCH_UNQUANTIFIED_AREA_GREY
_SEGMENT_3D_SELECTED_PATH = "#1c1c1c"  # selected segment overlay (line + markers; dark, not amber)
_SEGMENT_UNASSIGNED_MARKER = "#9e9e9e"

# %AS on 3D centerlines: custom greens — low stenosis stays a **visible light green** (not near-white).
_PCT_AS_3D_COLORSCALE: list[list[float | str]] = [
    [0.0, "rgb(175, 222, 175)"],
    [0.22, "rgb(138, 204, 138)"],
    [0.45, "rgb(92, 176, 95)"],
    [0.68, "rgb(45, 134, 55)"],
    [1.0, "rgb(8, 78, 22)"],
]

# Area on 3D centerlines: same idea as %AS — low values stay a **visible light blue** (not near-white).
_AREA_3D_COLORSCALE: list[list[float | str]] = [
    [0.0, "rgb(176, 214, 246)"],
    [0.22, "rgb(138, 187, 240)"],
    [0.45, "rgb(92, 156, 226)"],
    [0.68, "rgb(45, 118, 196)"],
    [1.0, "rgb(10, 62, 118)"],
]


def _discrete_plotly_color_list() -> tuple[str, ...]:
    parts: list[str] = []
    for name in ("Plotly", "Dark24", "Set2", "Pastel"):
        seq = getattr(plotly_qualitative, name, None)
        if isinstance(seq, (list, tuple)) and seq:
            parts.extend([str(c) for c in seq])
    if not parts:
        parts = list(plotly_qualitative.Plotly)
    return tuple(parts)


_DISCRETE_SEGMENT_COLORS: tuple[str, ...] = _discrete_plotly_color_list()

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
    """Format %AS for UI; negative values are shown as zero (not meaningful as stenosis)."""
    try:
        v = float(p)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(v):
        return "n/a"
    v = max(0.0, v)
    return f"{v:.2f}"


def _pct_as_viz_array(pct: np.ndarray | pd.Series) -> np.ndarray:
    """Clamp negative %AS to 0 for colors, bars, and argmax (NaN preserved)."""
    a = np.asarray(pd.to_numeric(pct, errors="coerce"), dtype=float)
    return np.where(np.isfinite(a), np.maximum(a, 0.0), np.nan)


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


def _discover_synthetic_branch_xlsx_in_dir(
    base: Path, patient_id: str
) -> list[tuple[str, Path]]:
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


def discover_synthetic_branch_xlsx(project_root: Path, patient_id: str) -> list[tuple[str, Path]]:
    """Stenosis branch tables (Block 2) preferred; Block 3 label mirror as fallback."""
    pid = str(patient_id).strip()
    candidates = [
        project_root
        / "results"
        / "block2_results"
        / "stenosis"
        / pid
        / "branches"
        / "dataframes",
        project_root
        / "results"
        / "block3_results"
        / "label"
        / pid
        / "branches"
        / "dataframes",
    ]
    for base in candidates:
        found = _discover_synthetic_branch_xlsx_in_dir(base, pid)
        if found:
            return found
    return []


def pct_as_ref_window_covered(sub: pd.DataFrame, window_mm: float | None = None) -> np.ndarray:
    """
    True where both proximal and distal reference sites exist within ±``window_mm`` along ``gd``
    (same contract as Block 2 ``ref_window_ok`` / ``compute_reference_columns``).
    """
    n = len(sub)
    if n == 0:
        return np.zeros(0, dtype=bool)
    if "ref_window_ok" in sub.columns:
        return (
            pd.to_numeric(sub["ref_window_ok"], errors="coerce").fillna(0).astype(bool).to_numpy()
        )
    w = float(reference_window_mm() if window_mm is None else window_mm)
    gd = _branch_geodesic_mm(sub)
    if len(gd) != n:
        return np.zeros(n, dtype=bool)
    prox_i = _nearest_index_within_bounds(gd, gd - w)
    dist_i = _nearest_index_within_bounds(gd, gd + w)
    return (prox_i >= 0) & (dist_i >= 0)


def discover_block3_label_branch_xlsx(project_root: Path, patient_id: str, artery: str) -> list[tuple[str, Path]]:
    """
    Branch spreadsheets (``dataset_<Branch_ID>_<patient_id>.xlsx``) under
    ``results/block3_results/label/<patient_id>/branches/dataframes/`` for ``artery`` ``LCA`` or ``RCA``.
    """
    art = str(artery).strip().upper()
    if art == "SYNTHETIC":
        return discover_synthetic_branch_xlsx(project_root, patient_id)
    if art not in ("LCA", "RCA"):
        raise ValueError("artery must be 'LCA', 'RCA', or 'Synthetic'")
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


def _area_3d_colormap_clim(values: np.ndarray) -> tuple[float, float, float, float]:
    """
    Robust Area colormap limits (5th–95th percentile) so a few large cross-sections do not
    compress the rest of the tree to one color. Returns ``(cmin, cmax, sample_min, sample_max)``.
    """
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0, 1.0, 0.0, 1.0
    sample_min = float(np.nanmin(v))
    sample_max = float(np.nanmax(v))
    cmin, cmax = _percentile_clim(v, 5.0, 95.0)
    if cmax <= cmin:
        cmin, cmax = sample_min, sample_max
        if cmax <= cmin:
            cmax = cmin + 1.0
    return cmin, cmax, sample_min, sample_max


def _sample_minmax_clim(
    values: np.ndarray,
    *,
    color_variable: str,
) -> tuple[float, float]:
    """Colormap limits = min/max of finite quantified samples (full sample range)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0, 1.0
    if color_variable == "pct_AS":
        cmin = 0.0
        cmax = float(np.nanmax(v))
    else:
        cmin = float(np.nanmin(v))
        cmax = float(np.nanmax(v))
    if not np.isfinite(cmin):
        cmin = 0.0
    if not np.isfinite(cmax) or cmax <= cmin:
        cmax = cmin + 1.0
    return cmin, cmax


def _area_values_match(a: float, b: float) -> bool:
    if not np.isfinite(a) or not np.isfinite(b):
        return False
    atol = max(1e-9, abs(float(b)) * 1e-5 + 1e-4)
    return abs(float(a) - float(b)) <= atol


def _ref_bar_index_on_polyline(
    area_y: np.ndarray,
    gd_line: np.ndarray,
    *,
    peak_ix: int,
    ref_area: float | None,
    gd_anchor: float,
    upstream: bool,
    downstream: bool,
) -> int | None:
    """
    Bar index on the plotted polyline whose Area equals ``ref_area`` and is closest in ``gd``
    to ``gd_anchor``. ``None`` if no row on this polyline has that reference Area (reference
    lies on another segment or outside the subset).
    """
    if ref_area is None or not np.isfinite(ref_area):
        return None
    n = len(area_y)
    if n == 0 or peak_ix < 0 or peak_ix >= n:
        return None
    gpk = float(gd_line[peak_ix])
    tgt = float(gd_anchor)
    best_j: int | None = None
    best_d = float("inf")
    for j in range(n):
        if j == peak_ix or not np.isfinite(area_y[j]):
            continue
        if not _area_values_match(float(area_y[j]), float(ref_area)):
            continue
        gj = float(gd_line[j])
        if upstream and gj >= gpk - 1e-6:
            continue
        if downstream and gj <= gpk + 1e-6:
            continue
        d = abs(gj - tgt)
        if d < best_d - 1e-9 or (np.isclose(d, best_d) and (best_j is None or j < best_j)):
            best_d = d
            best_j = j
    return best_j


def _reference_location_hint(
    artery_df: pd.DataFrame | None,
    peak_row: pd.Series,
    ref_area: float | None,
    gd_anchor: float,
) -> str:
    """Note when a reference Area is not on the current segment polyline."""
    if artery_df is None or artery_df.empty or ref_area is None or not np.isfinite(ref_area):
        return "Reference sample is on another segment along the branch (not shown on this chart)."
    if "Branch_ID" not in artery_df.columns or "gd" not in artery_df.columns:
        return "Reference sample is on another segment along the branch (not shown on this chart)."
    area_col = _find_df_column(artery_df, "Area")
    if not area_col:
        return "Reference sample is on another segment along the branch (not shown on this chart)."
    branch = str(peak_row.get("Branch_ID", "")).strip()
    m = artery_df["Branch_ID"].astype(str).str.strip() == branch
    cand = artery_df.loc[m].copy()
    if cand.empty:
        return "Reference sample is on another segment along the branch (not shown on this chart)."
    gd_c = pd.to_numeric(cand["gd"], errors="coerce").to_numpy(dtype=float)
    area_c = pd.to_numeric(cand[area_col], errors="coerce").to_numpy(dtype=float)
    best_k = None
    best_d = float("inf")
    for k in range(len(cand)):
        if not np.isfinite(gd_c[k]) or not np.isfinite(area_c[k]):
            continue
        if not _area_values_match(float(area_c[k]), float(ref_area)):
            continue
        d = abs(float(gd_c[k]) - float(gd_anchor))
        if d < best_d:
            best_d = d
            best_k = k
    if best_k is None:
        return "Reference sample is on another segment along the branch (not shown on this chart)."
    row = cand.iloc[int(best_k)]
    seg_name = _segment_display_name(row)
    sid = row.get("Segment_ID", "")
    return f"Reference lies on {seg_name} (segment ID {sid}), not on this segment."


def _argmax_finite_index(values: np.ndarray) -> int | None:
    """Index of the maximum among finite values; ``None`` if none are finite."""
    v = np.asarray(values, dtype=float)
    mask = np.isfinite(v)
    if not mask.any():
        return None
    idx = np.flatnonzero(mask)
    j = int(np.argmax(v[mask]))
    return int(idx[j])


def _nearest_index_within_bounds(gd_values: np.ndarray, target_values: np.ndarray) -> np.ndarray:
    """Same contract as ``nearest_index_within_bounds`` in Block 2 stenosis."""
    if len(gd_values) == 0:
        return np.array([], dtype=np.int64)
    idx = np.searchsorted(gd_values, target_values)
    idx = np.clip(idx, 0, len(gd_values) - 1)
    prev_idx = np.clip(idx - 1, 0, len(gd_values) - 1)
    dist_prev = np.abs(gd_values[prev_idx] - target_values)
    dist_curr = np.abs(gd_values[idx] - target_values)
    nearest_idx = np.where(dist_prev <= dist_curr, prev_idx, idx).astype(np.int64, copy=False)
    out_of_bounds = (target_values < gd_values[0]) | (target_values > gd_values[-1])
    nearest_idx[out_of_bounds] = -1
    return nearest_idx


def _branch_geodesic_mm(g_sorted: pd.DataFrame) -> np.ndarray:
    """Cumulative arc length (mm) along the ordered branch; mirrors Block 2 ``gd``."""
    if "gd" in g_sorted.columns:
        gdv = pd.to_numeric(g_sorted["gd"], errors="coerce").to_numpy(dtype=float)
        if len(gdv) and bool(np.all(np.isfinite(gdv))):
            return gdv
    xyz = g_sorted[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    if len(xyz) == 0:
        return np.zeros(0, dtype=float)
    if len(xyz) == 1:
        return np.array([0.0], dtype=float)
    step = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(step)])


def prox_dist_ref_indices_for_pct_as(g_sorted: pd.DataFrame, window_mm: float) -> tuple[np.ndarray, np.ndarray]:
    """
    For each centerline row, indices of the nearest samples at geodesic ``± window_mm``
    (Block 2 ``Area_prox`` / ``Area_dist`` lookup). Invalid targets → ``-1``.
    """
    n = len(g_sorted)
    if n == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    gd_vals = _branch_geodesic_mm(g_sorted)
    prox_targets = gd_vals - float(window_mm)
    dist_targets = gd_vals + float(window_mm)
    prox_idx = _nearest_index_within_bounds(gd_vals, prox_targets)
    dist_idx = _nearest_index_within_bounds(gd_vals, dist_targets)
    return prox_idx.astype(np.int64, copy=False), dist_idx.astype(np.int64, copy=False)


def create_3d_mesh_branch_path_highlight(
    mesh_vtp_path: str,
    centerline_df: pd.DataFrame,
    *,
    selected_branch_id: str,
    trace_name: str = "LCA",
) -> go.Figure:
    """
    Artery mesh + full centerline tree (small black markers) with **one** branch path
    highlighted by ``pct_AS`` (custom light-to-deep green scale; low values stay visibly green). Color limits use the 5th–95th percentile of finite
    **display** %AS (values ``< 0`` are treated as ``0`` for the colormap) over **all**
    concatenated branch points.

    Adds a **purple diamond** at the branch centerline point with **maximum display %AS**
    (Area at that point is shown in the marker hover when available).

    **Green circles** mark the proximal/distal reference centerline samples used for ``A_ref``
    at that peak (nearest points ≈ ±``BRANCH_PCT_AS_REFERENCE_WINDOW_MM`` mm; same as Block 2).
    They are omitted when they coincide with the max index (purple only).

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
    viz_all = _pct_as_viz_array(raw_all)
    if "ref_window_ok" in d.columns:
        ref_ok = (
            pd.to_numeric(d["ref_window_ok"], errors="coerce").fillna(0).astype(bool).to_numpy()
        )
        valid_all = ref_ok & np.isfinite(raw_all)
    else:
        valid_all = np.isfinite(raw_all)
    if valid_all.any():
        cmin, cmax = _sample_minmax_clim(viz_all[valid_all], color_variable="pct_AS")
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

    # --- Selected branch: %AS coloring (sequential greens) ---
    g_sel = _sort_branch_rows(d_sel)
    xs_s = g_sel["Px"].to_numpy(dtype=float)
    ys_s = g_sel["Py"].to_numpy(dtype=float)
    zs_s = g_sel["Pz"].to_numpy(dtype=float)
    c_s = _pct_as_viz_array(g_sel["pct_AS"])

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
        colorscale=_PCT_AS_3D_COLORSCALE,
        cmin=cmin,
        cmax=cmax,
        showscale=True,
        colorbar=dict(
            title=dict(
                text=f"% area stenosis (range {cmin:.2g}–{cmax:.2g} %)",
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
            line=dict(color=c_s, colorscale=_PCT_AS_3D_COLORSCALE, cmin=cmin, cmax=cmax, width=6.5, showscale=False),
            marker=marker_sel,
            text=hover_sel,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    # --- Reference samples at peak (green circles, only when on this branch polyline) ---
    pk_branch = ordered_centerline_peak_reference_summary(g_sel)
    idx_max_pct = pk_branch.get("max_pct_index")

    if idx_max_pct is not None:
        ref_rows: list[tuple[int, str]] = []
        seen_ix: set[int] = set()
        for label, ix_key in (
            ("Proximal reference (peak %AS)", "prox_ref_highlight_index"),
            ("Distal reference (peak %AS)", "dist_ref_highlight_index"),
        ):
            ix = pk_branch.get(ix_key)
            if ix is None:
                continue
            ixi = int(ix)
            if 0 <= ixi < len(g_sel) and ixi not in seen_ix and ixi != int(idx_max_pct):
                seen_ix.add(ixi)
                ref_rows.append((ixi, label))
        if ref_rows:
            gx: list[float] = []
            gy: list[float] = []
            gz: list[float] = []
            gtext: list[str] = []
            for ix, ref_label in ref_rows:
                rrow = g_sel.iloc[ix]
                lines_g = [
                    f"<b>{sel} · %AS reference sample</b>",
                    ref_label,
                    f"<b>Centerline point</b> {ix + 1} (of {len(g_sel)})",
                    f"Artery: {_artery_type_display(rrow)}",
                    f"Segment: {_segment_display_name(rrow)}",
                    f"<b>Area</b>: {_format_area(rrow.get('Area'))} mm²",
                    f"<b>%AS at max-stenosis point</b>: {_format_pct(g_sel.iloc[idx_max_pct].get('pct_AS'))} %",
                ]
                gx.append(float(rrow["Px"]))
                gy.append(float(rrow["Py"]))
                gz.append(float(rrow["Pz"]))
                gtext.append("<br>".join(lines_g))
            traces.append(
                go.Scatter3d(
                    name=f"{trace_name} · {sel} · ref window",
                    x=np.asarray(gx, dtype=float),
                    y=np.asarray(gy, dtype=float),
                    z=np.asarray(gz, dtype=float),
                    mode="markers",
                    marker=dict(
                        size=18,
                        color=_BRANCH_REF_WINDOW_GREEN,
                        symbol="circle",
                        line=dict(color="#e8f5e9", width=2.5),
                        opacity=1.0,
                    ),
                    text=gtext,
                    hovertemplate="%{text}<extra></extra>",
                    showlegend=False,
                )
            )

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
    is_synthetic: bool = False,
) -> go.Figure:
    """
    Build an interactive 3D figure: translucent outer mesh + **one** centerline trace
    (all branches concatenated with coordinate ``NaN`` breaks so lines do not connect
    across the tree) + optional NaN marker cloud.

    Color scale for quantified points uses the 5th–95th percentile of ``color_variable``
    (finite values only) as ``cmin``/``cmax``. When ``color_variable`` is ``pct_AS``, values
    below zero are floored to zero for coloring and limits, and colors use a custom
    light-to-deep green ramp (low stenosis is visibly green, not near-white). When it is
    ``Area``, colors use a matching light-to-deep **blue** ramp (low area is visibly blue).
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
    if color_variable == "pct_AS":
        plot_color = _pct_as_viz_array(raw_color)
    else:
        plot_color = raw_color
    if color_variable == "pct_AS" and "ref_window_ok" in d.columns:
        ref_ok = (
            pd.to_numeric(d["ref_window_ok"], errors="coerce").fillna(0).astype(bool).to_numpy()
        )
        valid_mask = ref_ok & np.isfinite(raw_color)
    else:
        valid_mask = np.isfinite(raw_color)

    # Colormap limits: %AS = full sample max; Area = percentiles (clinical) or min–max (synthetic).
    if valid_mask.any():
        if color_variable == "Area" and not is_synthetic:
            cmin, cmax, area_smin, area_smax = _area_3d_colormap_clim(plot_color[valid_mask])
        else:
            cmin, cmax = _sample_minmax_clim(plot_color[valid_mask], color_variable=color_variable)
            area_smin = area_smax = None
    else:
        cmin, cmax = 0.0, 1.0
        area_smin = area_smax = None

    if color_variable == "pct_AS":
        colorscale: list[list[float | str]] | str = _PCT_AS_3D_COLORSCALE
    elif color_variable == "Area":
        colorscale = _AREA_3D_COLORSCALE
    else:
        colorscale = "Viridis"
    if color_variable == "pct_AS":
        cb_title = f"% area stenosis (range {cmin:.2g}–{cmax:.2g} %)"
    elif is_synthetic or area_smin is None or area_smax is None:
        cb_title = f"Cross-sectional area (range {cmin:.2g}–{cmax:.2g} mm²)"
    else:
        cb_title = (
            f"Cross-sectional area (color scale {cmin:.2g}–{cmax:.2g} mm², "
            f"5–95%; sample {area_smin:.2g}–{area_smax:.2g} mm²)"
        )

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
                cv = float(pd.to_numeric(row[color_variable], errors="coerce"))
                if color_variable == "pct_AS" and np.isfinite(cv):
                    cv = max(0.0, cv)
                c_list.append(cv)
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


def _symmetric_area_bar_base_and_height(area_y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Build ``go.Bar`` kwargs so each cross-sectional area ``A`` is drawn from ``-A/2`` to ``+A/2``
    (Plotly: ``base=-A/2``, ``y=A`` as the bar length), giving a symmetric “lumen profile” along
    the ordered samples.
    """
    a = np.asarray(area_y, dtype=float)
    base = np.full_like(a, np.nan, dtype=float)
    height = np.full_like(a, np.nan, dtype=float)
    m = np.isfinite(a)
    height[m] = a[m]
    base[m] = -0.5 * a[m]
    return height, base


def branch_ids_in_artery_table(
    centerline_df: pd.DataFrame,
    *,
    artery_prefix: str | None = None,
) -> list[str]:
    """Sorted ``Branch_ID`` values present in an artery-wide table (e.g. ``total_df``)."""
    if centerline_df.empty or "Branch_ID" not in centerline_df.columns:
        return []
    bids = [str(b).strip() for b in centerline_df["Branch_ID"].astype(str).unique() if str(b).strip()]
    if artery_prefix:
        p = str(artery_prefix).strip().upper() + "_"
        bids = [b for b in bids if b.upper().startswith(p)]
    bids.sort(key=_branch_sort_key)
    return bids


def branch_rows_for_artery_ui(
    centerline_df: pd.DataFrame,
    *,
    artery_prefix: str | None = None,
) -> list[tuple[str, float]]:
    """
    Branches for the artery tab: ``(Branch_ID, max %AS %)``, ordered by **descending** max %AS.

    Max %AS uses the same rule as profile bar charts: maximum among samples with a full
    ±``BRANCH_PCT_AS_REFERENCE_WINDOW_MM`` reference window when ``ref_window_ok`` is available;
    otherwise the maximum finite ``pct_AS`` on the branch path.
    """
    if centerline_df.empty or "Branch_ID" not in centerline_df.columns:
        return []
    d = centerline_df.copy()
    if artery_prefix:
        p = str(artery_prefix).strip().upper() + "_"
        d = d[d["Branch_ID"].astype(str).str.strip().str.upper().str.startswith(p)]
    if d.empty:
        return []

    pct_col = _find_df_column(d, "pct_AS", "Pct_AS", "PCT_AS")
    if not pct_col:
        return []

    bids = branch_ids_in_artery_table(d, artery_prefix=None)
    rows: list[tuple[str, float]] = []
    for bid in bids:
        sub = d.loc[d["Branch_ID"].astype(str).str.strip() == bid]
        if sub.empty:
            continue
        covered = pct_as_ref_window_covered(sub)
        raw = pd.to_numeric(sub[pct_col], errors="coerce").to_numpy(dtype=float)
        viz = _pct_as_viz_array(raw)
        if covered.any():
            mx = float(np.nanmax(np.where(covered, viz, np.nan)))
        elif np.isfinite(viz).any():
            mx = float(np.nanmax(viz))
        else:
            mx = 0.0
        if not np.isfinite(mx):
            mx = 0.0
        rows.append((bid, max(0.0, mx)))

    rows.sort(key=lambda t: (-t[1], _branch_sort_key(t[0])))
    return rows


def branch_peak_reference_summary(
    centerline_df: pd.DataFrame,
    branch_id: str,
    *,
    window_mm: float | None = None,
) -> dict[str, Any]:
    """Peak / reference summary for one branch path in an artery-wide table."""
    if centerline_df.empty or "Branch_ID" not in centerline_df.columns:
        return {"ok": False, "reason": "no_rows"}
    sel = str(branch_id).strip()
    d = centerline_df.copy()
    d["_branch_key"] = d["Branch_ID"].astype(str).str.strip()
    sub = d.loc[d["_branch_key"] == sel].drop(columns=["_branch_key"], errors="ignore")
    if sub.empty:
        return {"ok": False, "reason": "no_rows", "branch_id": sel}
    sub = _sort_branch_rows(sub)
    out = ordered_centerline_peak_reference_summary(sub, window_mm=window_mm)
    return {**out, "branch_id": sel}


def _create_centerline_profile_bars_figure(
    sub: pd.DataFrame,
    *,
    pk_summary: dict[str, Any],
    title_area: str,
    title_pct: str,
    x_axis_title_row2: str,
    point_label: str,
    chart_scope: str,
) -> go.Figure:
    """
    Shared Area / %AS bar profile (symmetric Area bars). Hover and callouts always use the same
    per-point ``Area`` / ``pct_AS`` arrays as the bar heights (via ``customdata``), not Plotly ``y``.
    """
    pct_col = _find_df_column(sub, "pct_AS", "Pct_AS", "PCT_AS")
    area_col = _find_df_column(sub, "Area")
    if not pct_col:
        raise ValueError("No %AS column found (expected pct_AS).")
    if not area_col:
        raise ValueError("No Area column found.")

    n = len(sub)
    x_labels = [str(i + 1) for i in range(n)]
    covered = pct_as_ref_window_covered(sub)
    raw_pct = pd.to_numeric(sub[pct_col], errors="coerce").to_numpy(dtype=float)
    pct_y = _pct_as_viz_array(raw_pct)
    area_y = pd.to_numeric(sub[area_col], errors="coerce").to_numpy(dtype=float)

    col_area, col_pct, idx_max_pct = _profile_bar_colors_from_summary(n, covered, pk_summary)
    pct_plot_y = pct_y.copy()
    pct_plot_y[~covered] = 0.0

    gd_vals = _branch_geodesic_mm(sub)
    has_gd = np.isfinite(gd_vals).any()
    if has_gd:
        custom_cd = np.column_stack([pct_y, area_y, gd_vals])
        gd_line = (
            f"<b>Along-branch distance (gd)</b>: %{{customdata[2]:.4f}} mm<br>"
            if chart_scope == "segment"
            else "<b>gd</b>: %{customdata[2]:.4f}<br>"
        )
    else:
        custom_cd = np.column_stack([pct_y, area_y])
        gd_line = ""

    hover_pct = (
        f"<b>Point %{{x}}</b> ({point_label})<br>"
        f"{gd_line}"
        "<b>%AS</b>: %{customdata[0]:.2f}<br>"
        "<b>Area</b>: %{customdata[1]:.4f} mm²<extra></extra>"
    )
    hover_area = (
        f"<b>Point %{{x}}</b> ({point_label})<br>"
        f"{gd_line}"
        "<b>Area</b>: %{customdata[1]:.4f} mm²<br>"
        "<b>%AS</b>: %{customdata[0]:.2f}<extra></extra>"
    )

    area_bar_h, area_bar_base = _symmetric_area_bar_base_and_height(area_y)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.17,
        subplot_titles=(title_area, title_pct),
    )
    fig.add_trace(
        go.Bar(
            x=x_labels,
            y=area_bar_h,
            base=area_bar_base,
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
            y=pct_plot_y,
            name="%AS",
            marker=dict(color=col_pct, line=dict(width=0), opacity=0.92),
            customdata=custom_cd,
            hovertemplate=hover_pct,
        ),
        row=2,
        col=1,
    )

    # Light Streamlit shell: dark axes/titles on transparent plot background.
    _axis_title_font = dict(color="#1a1a1a", size=13)
    _axis_tick_font = dict(color="#333333", size=11)
    grid_kw: dict[str, Any] = dict(
        showgrid=True,
        gridcolor="rgba(0, 0, 0, 0.12)",
        zeroline=True,
        zerolinecolor="rgba(0, 0, 0, 0.28)",
        zerolinewidth=1,
    )
    fig.update_xaxes(
        title_text=x_axis_title_row2,
        title_font=_axis_title_font,
        tickfont=_axis_tick_font,
        tickangle=-60 if n > 35 else -45,
        showline=True,
        linecolor="rgba(0, 0, 0, 0.35)",
        mirror=True,
        **grid_kw,
        row=2,
        col=1,
    )
    fig.update_xaxes(tickfont=_axis_tick_font, **grid_kw, row=1, col=1)
    fig.update_yaxes(
        title_text="Area (mm²)",
        title_font=_axis_title_font,
        tickfont=_axis_tick_font,
        showline=True,
        linecolor="rgba(0, 0, 0, 0.35)",
        mirror=True,
        **grid_kw,
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text="%AS",
        title_font=_axis_title_font,
        tickfont=_axis_tick_font,
        showline=True,
        linecolor="rgba(0, 0, 0, 0.35)",
        mirror=True,
        **grid_kw,
        row=2,
        col=1,
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#1a1a1a", family="Inter, Segoe UI, system-ui, sans-serif", size=12),
        margin=dict(t=88, r=24, b=56, l=64),
        hovermode="closest",
        hoverlabel=dict(bgcolor="#ffffff", font_color="#1a1a1a", font_size=12),
        showlegend=False,
        height=800,
        bargap=0.22,
    )
    fig.update_annotations(font=dict(color="#1a1a1a", size=13))
    # Nudge the lower subplot title up so it does not sit on the %AS grid.
    if len(fig.layout.annotations) >= 2:
        ann_pct = fig.layout.annotations[1]
        if ann_pct.y is not None:
            ann_pct.update(y=float(ann_pct.y) + 0.025)

    _add_peak_ref_area_row_annotations(
        fig,
        pk_summary=pk_summary,
        n=n,
        x_labels=x_labels,
        area_y=area_y,
        idx_max_pct=int(idx_max_pct) if idx_max_pct is not None else None,
        chart_scope=chart_scope,
    )
    _add_max_pct_as_peak_bar_annotations(
        fig,
        n=n,
        x_labels=x_labels,
        idx_max_pct=int(idx_max_pct) if idx_max_pct is not None else None,
        pct_y=pct_y,
        area_y=area_y,
    )
    return fig


def create_branch_centerline_metric_bars(
    centerline_df: pd.DataFrame,
    *,
    selected_branch_id: str,
    artery: str,
) -> go.Figure:
    """
    Interactive paired bar charts along the ordered centerline of **one** branch:
    row 1 — ``Area`` (cyan blue), each bar symmetric about ``y=0`` (``-A/2`` … ``+A/2`` for area ``A``);
    row 2 — ``pct_AS`` (orange). Transparent figure backgrounds.

    Bars at the **maximum finite %AS** index are purple on **both** rows (same centerline
    point: peak stenosis and its cross-sectional area). Proximal / distal reference areas at the
    peak match ``ordered_centerline_peak_reference_summary`` (``Area_prox`` / ``Area_dist`` from
    Block 2 when present, else ± ``BRANCH_PCT_AS_REFERENCE_WINDOW_MM`` mm along ``gd``), with the
    same **green** bars and callouts on the **Area** row as segment charts (not on the %AS row).

    Prefer ``centerline_df`` = artery-wide ``total_df`` (Block 2/3) so ``Area``, ``pct_AS``,
    ``Area_prox`` / ``Area_dist`` match the segment views; per-branch Excel under Block 3 label
    is a fallback only.
    """
    if centerline_df.empty or "Branch_ID" not in centerline_df.columns:
        raise ValueError("Branch dataframe is empty or missing Branch_ID.")

    sel = str(selected_branch_id).strip()
    d = centerline_df.copy()
    d["_branch_key"] = d["Branch_ID"].astype(str).str.strip()
    sub = d.loc[d["_branch_key"] == sel].drop(columns=["_branch_key"], errors="ignore")
    if sub.empty:
        raise ValueError(f"No rows for branch {sel!r}.")

    sub = _sort_branch_rows(sub)
    if len(sub) == 0:
        raise ValueError("Selected branch has no centerline points.")

    pk_summary = ordered_centerline_peak_reference_summary(sub, None)
    art = str(artery).strip().upper()
    return _create_centerline_profile_bars_figure(
        sub,
        pk_summary=pk_summary,
        title_area=f"Cross-sectional area along centerline · {art} · {sel}",
        title_pct=f"% area stenosis along centerline · {art} · {sel}",
        x_axis_title_row2="Centerline point index (1 = proximal)",
        point_label="proximal→distal",
        chart_scope="branch",
    )


def create_synthetic_tube_geodesic_profile(centerline_df: pd.DataFrame) -> go.Figure:
    """
    Single continuous Area + %AS profile along the synthetic vessel (one branch, no LCA/RCA split).
    """
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


def load_block3_cad_rads_patient_report_row(project_root: Path, patient_id: str) -> pd.Series | None:
    """First row of ``patient_report`` sheet under ``results/block3_results/cad-rads/``."""
    pid = str(patient_id).strip()
    path = project_root / "results" / "block3_results" / "cad-rads" / pid / f"patient_report_{pid}.xlsx"
    if not path.is_file():
        return None
    try:
        df = pd.read_excel(path, sheet_name="patient_report")
    except (OSError, ValueError):
        return None
    if df is None or df.empty:
        return None
    return df.iloc[0]


def load_block3_segment_stenosis_summary(project_root: Path, patient_id: str) -> pd.DataFrame | None:
    """``stenosis_summary_<patient>.xlsx`` under ``results/block3_results/segment stenosis/``."""
    pid = str(patient_id).strip()
    path = (
        project_root
        / "results"
        / "block3_results"
        / "segment stenosis"
        / pid
        / f"stenosis_summary_{pid}.xlsx"
    )
    if not path.is_file():
        return None
    try:
        df = pd.read_excel(path)
    except (OSError, ValueError):
        return None
    if df is None or df.empty:
        return None
    return df


def _segment_ids_present_in_centerline(centerline_df: pd.DataFrame) -> set[int]:
    if centerline_df.empty or "Segment_ID" not in centerline_df.columns:
        return set()
    s = pd.to_numeric(centerline_df["Segment_ID"], errors="coerce").fillna(0).astype(int)
    return {int(x) for x in s.unique() if int(x) > 0}


def segment_rows_for_artery_ui(
    seg_summary: pd.DataFrame | None,
    centerline_df: pd.DataFrame,
    artery: str,
) -> list[tuple[int, str, float]]:
    """
    Segments for the artery tab, ordered by **descending** ``Max_pct_AS`` (from summary when
    available, otherwise max ``pct_AS`` from centerline points). Only IDs present in ``centerline_df``.
    """
    art = str(artery).strip().upper()
    present = _segment_ids_present_in_centerline(centerline_df)
    if not present:
        return []

    if seg_summary is not None and not seg_summary.empty and "Artery_Type" in seg_summary.columns:
        ss = seg_summary.copy()
        ss["Segment_ID"] = pd.to_numeric(ss["Segment_ID"], errors="coerce").fillna(-1).astype(int)
        m = ss["Artery_Type"].astype(str).str.upper() == art
        sub = ss.loc[m & ss["Segment_ID"].isin(present) & (ss["Segment_ID"] > 0)].copy()
        if not sub.empty:
            sub["Max_pct_AS"] = pd.to_numeric(sub.get("Max_pct_AS"), errors="coerce")
            sub = sub.sort_values("Max_pct_AS", ascending=False, na_position="last")
            out: list[tuple[int, str, float]] = []
            for _, row in sub.iterrows():
                sid = int(row["Segment_ID"])
                name = str(row.get("Segment_Name") or "").strip() or _segment_label(sid)
                if pd.notna(row.get("Max_pct_AS")):
                    try:
                        mx = max(0.0, float(row["Max_pct_AS"]))
                    except (TypeError, ValueError):
                        mx = 0.0
                else:
                    mx = 0.0
                out.append((sid, name, mx))
            return out

    d = centerline_df.copy()
    d["_sid"] = pd.to_numeric(d["Segment_ID"], errors="coerce").fillna(0).astype(int)
    d = d.loc[d["_sid"].isin(present)]
    pct = pd.to_numeric(d.get("pct_AS", np.nan), errors="coerce")
    pct = np.where(np.isfinite(pct), np.maximum(pct, 0.0), np.nan)
    d = d.assign(_pct=pct)
    agg = d.groupby("_sid", as_index=False)["_pct"].max().rename(columns={"_sid": "Segment_ID", "_pct": "Max_pct_AS"})
    agg = agg.sort_values("Max_pct_AS", ascending=False, na_position="last")
    rows: list[tuple[int, str, float]] = []
    for _, row in agg.iterrows():
        sid = int(row["Segment_ID"])
        _mx = float(row["Max_pct_AS"]) if pd.notna(row["Max_pct_AS"]) else 0.0
        rows.append((sid, _segment_label(sid), max(0.0, _mx)))
    return rows


def _sort_multibranch_centerline(g: pd.DataFrame) -> pd.DataFrame:
    """Order points along the tree when a segment spans several ``Branch_ID`` groups."""
    if g.empty:
        return g
    g2 = g.copy()
    if "Branch_ID" in g2.columns and "gd" in g2.columns:
        g2["_sbk"] = g2["Branch_ID"].astype(str).map(_branch_sort_key)
        out = g2.sort_values(["_sbk", "gd"], ascending=True).drop(columns=["_sbk"], errors="ignore")
        return out.reset_index(drop=True)
    return _sort_branch_rows(g2)


def _arc_length_mm_along_sorted_xyz(g_sorted: pd.DataFrame) -> np.ndarray:
    n = len(g_sorted)
    if n == 0:
        return np.zeros(0, dtype=float)
    if n == 1:
        return np.array([0.0], dtype=float)
    xyz = g_sorted[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    step = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(step)])


def prox_dist_ref_indices_along_polyline(
    g_sorted: pd.DataFrame, window_mm: float
) -> tuple[np.ndarray, np.ndarray]:
    """Reference-window sample indices along cumulative Euclidean arc length (ordered ``g_sorted``)."""
    n = len(g_sorted)
    if n == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    gd_vals = _arc_length_mm_along_sorted_xyz(g_sorted)
    prox_targets = gd_vals - float(window_mm)
    dist_targets = gd_vals + float(window_mm)
    prox_idx = _nearest_index_within_bounds(gd_vals, prox_targets)
    dist_idx = _nearest_index_within_bounds(gd_vals, dist_targets)
    return prox_idx.astype(np.int64, copy=False), dist_idx.astype(np.int64, copy=False)


def _consecutive_branch_id_slices(sub: pd.DataFrame) -> list[tuple[int, int]]:
    """``(start, end)`` half-open slices of ``sub`` with constant ``Branch_ID`` (ordered rows)."""
    n = len(sub)
    if n == 0:
        return []
    if "Branch_ID" not in sub.columns:
        return [(0, n)]
    keys = sub["Branch_ID"].astype(str).str.strip()
    out: list[tuple[int, int]] = []
    a = 0
    cur = keys.iloc[0]
    for i in range(1, n + 1):
        if i == n or keys.iloc[i] != cur:
            out.append((a, i))
            if i < n:
                a = i
                cur = keys.iloc[i]
    return out


def _segment_prox_dist_ref_indices(sub: pd.DataFrame, window_mm: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Per-row proximal / distal reference indices for segment tables, aligned with Block 2
    ``compute_reference_columns`` (uses ``gd`` via ``prox_dist_ref_indices_for_pct_as``).

    Consecutive ``Branch_ID`` runs are processed separately so geodesic lookups stay on monotonic
    ``gd`` within each branch (same contract as branch bar charts / 3D highlights).
    """
    n = len(sub)
    if n == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    prox_out = np.full(n, -1, dtype=np.int64)
    dist_out = np.full(n, -1, dtype=np.int64)
    for a, b in _consecutive_branch_id_slices(sub):
        chunk = sub.iloc[a:b]
        pi, di = prox_dist_ref_indices_for_pct_as(chunk, window_mm)
        m = b - a
        for k in range(m):
            pk = int(pi[k]) if k < len(pi) else -1
            dk = int(di[k]) if k < len(di) else -1
            prox_out[a + k] = (a + pk) if 0 <= pk < m else -1
            dist_out[a + k] = (a + dk) if 0 <= dk < m else -1
    return prox_out, dist_out


def _peak_ref_area_matches_segment_bar(
    bar_ix: int | None,
    ref_area: object,
    area_y: np.ndarray,
) -> bool:
    """
    Whether ``ref_area`` (from the max-%AS row) is represented by the Area at ``bar_ix`` on this
    segment's bar chart (same tolerance as ``_segment_ref_bar_indices_at_peak`` value matching).

    ``ref_area`` None / non-finite → True (no value-specific disclaimer). ``bar_ix`` None with
    finite ref → False (reference cross-section not among this segment's samples).
    """
    if ref_area is None:
        return True
    try:
        tgt = float(ref_area)
    except (TypeError, ValueError):
        return True
    if not np.isfinite(tgt):
        return True
    if bar_ix is None:
        return False
    bi = int(bar_ix)
    if bi < 0 or bi >= len(area_y):
        return False
    yb = float(area_y[bi])
    if not np.isfinite(yb):
        return False
    atol = max(1e-9, abs(tgt) * 1e-7 + 1e-6)
    return abs(yb - tgt) <= atol


def _segment_ref_bar_indices_at_peak(
    sub: pd.DataFrame,
    idx_peak: int,
    area_y: np.ndarray,
    window_mm: float,
) -> tuple[int | None, int | None]:
    """
    Bar indices (into ordered ``sub``) for proximal / distal reference at the max-%AS point.

    ``Area_prox`` / ``Area_dist`` on the peak row define the reference **values**. Among segment
    rows whose Area matches (within tolerance), we pick the sample whose geodesic ``gd`` is closest
    to **gd_peak − window** (proximal) or **gd_peak + window** (distal), matching how Block 2
    chooses reference indices — **not** closest ``gd`` to the peak itself, which can swap sides when
    similar areas repeat along the segment.

    A value match is used only if it lies **upstream** of the peak (prox, lower index along
    increasing ``gd``) and **downstream** (dist, higher index): ``prox < idx_peak < dist``.
    Otherwise that side falls back to ``_segment_prox_dist_ref_indices`` at the peak.
    """
    n = len(sub)
    ipk = int(idx_peak)
    if n == 0 or not (0 <= ipk < n):
        return None, None

    w_f = float(window_mm)
    prox_col = _find_df_column(sub, "Area_prox", "area_prox")
    dist_col = _find_df_column(sub, "Area_dist", "area_dist")
    row_pk = sub.iloc[ipk]
    gd_line = _branch_geodesic_mm(sub)
    gpk = float(gd_line[ipk]) if ipk < len(gd_line) else 0.0

    def _tgt(col: str | None) -> float | None:
        if col is None:
            return None
        try:
            t = float(pd.to_numeric(row_pk.get(col), errors="coerce"))
        except (TypeError, ValueError):
            return None
        return t if np.isfinite(t) else None

    def _pick_for_target(tgt: float | None, gd_anchor: float) -> int | None:
        if tgt is None:
            return None
        try:
            anch = float(gd_anchor)
        except (TypeError, ValueError):
            anch = gpk
        if not np.isfinite(anch):
            anch = gpk
        atol = max(1e-9, abs(float(tgt)) * 1e-7 + 1e-6)
        best_j: int | None = None
        best_dgd = float("inf")
        for j in range(n):
            if j == ipk:
                continue
            if not np.isfinite(area_y[j]):
                continue
            if abs(float(area_y[j]) - float(tgt)) > atol:
                continue
            gj = float(gd_line[j]) if j < len(gd_line) else float(j)
            dgd = abs(gj - anch)
            if dgd < best_dgd - 1e-12 or (
                np.isclose(dgd, best_dgd) and (best_j is None or j < best_j)
            ):
                best_dgd = dgd
                best_j = j
        return best_j

    ap_t = _tgt(prox_col)
    ad_t = _tgt(dist_col)
    gd_anchor_prox = gpk - w_f
    gd_anchor_dist = gpk + w_f
    ip_m = _pick_for_target(ap_t, gd_anchor_prox)
    id_m = _pick_for_target(ad_t, gd_anchor_dist)

    prox_i, dist_i = _segment_prox_dist_ref_indices(sub, window_mm)
    out_p: int | None = None
    out_d: int | None = None
    if ipk < len(prox_i) and ipk < len(dist_i):
        ip2 = int(prox_i[ipk])
        id2 = int(dist_i[ipk])
        out_p = ip2 if 0 <= ip2 < n and ip2 != ipk else None
        out_d = id2 if 0 <= id2 < n and id2 != ipk else None

    use_p = ip_m if (ip_m is not None and ip_m < ipk) else out_p
    use_d = id_m if (id_m is not None and id_m > ipk) else out_d

    if use_p is not None and use_p >= ipk:
        use_p = out_p if (out_p is not None and out_p < ipk) else None
    if use_d is not None and use_d <= ipk:
        use_d = out_d if (out_d is not None and out_d > ipk) else None

    return use_p, use_d


def ordered_centerline_peak_reference_summary(
    sub_sorted: pd.DataFrame,
    window_mm: float | None = None,
) -> dict[str, Any]:
    """
    Peak **%AS** and proximal / distal reference areas for one **already-sorted** centerline table
    (one branch path or one segment polyline). Same contract as ``segment_pct_as_peak_reference_summary``
    without ``Segment_ID`` filtering.

    Returns ``ok`` / ``reason`` like the segment helper; omits ``segment_id``.
    """
    w = float(reference_window_mm() if window_mm is None else window_mm)
    sub = sub_sorted
    if sub.empty:
        return {"ok": False, "reason": "no_rows"}
    n = len(sub)
    pct_col = _find_df_column(sub, "pct_AS", "Pct_AS", "PCT_AS")
    area_col = _find_df_column(sub, "Area")
    if not pct_col:
        return {"ok": False, "reason": "no_pct_col"}

    covered = pct_as_ref_window_covered(sub, w)
    pct_y = pd.to_numeric(sub[pct_col], errors="coerce").to_numpy(dtype=float)
    pct_viz = _pct_as_viz_array(pct_y)
    idx_max = _argmax_finite_index(np.where(covered, pct_viz, np.nan))

    def _area_row(ix: int) -> float | None:
        if area_col is None or ix < 0 or ix >= n:
            return None
        v = sub.iloc[ix].get(area_col)
        try:
            a = float(pd.to_numeric(v, errors="coerce"))
        except (TypeError, ValueError):
            return None
        return a if np.isfinite(a) else None

    def _numeric_cell(ix: int, col: str | None) -> float | None:
        if col is None or ix < 0 or ix >= n:
            return None
        v = sub.iloc[ix].get(col)
        try:
            a = float(pd.to_numeric(v, errors="coerce"))
        except (TypeError, ValueError):
            return None
        return a if np.isfinite(a) else None

    prox_col = _find_df_column(sub, "Area_prox", "area_prox")
    dist_col = _find_df_column(sub, "Area_dist", "area_dist")
    ix_prox = ix_dist = None
    area_prox = area_dist = None
    prox_on_bar = dist_on_bar = False
    area_y_arr = (
        pd.to_numeric(sub[area_col], errors="coerce").to_numpy(dtype=float)
        if area_col is not None
        else np.array([], dtype=float)
    )
    gd_line = _branch_geodesic_mm(sub)

    if idx_max is not None:
        imx = int(idx_max)
        gd_peak = float(gd_line[imx]) if imx < len(gd_line) else 0.0
        if prox_col:
            area_prox = _numeric_cell(imx, prox_col)
        if dist_col:
            area_dist = _numeric_cell(imx, dist_col)

        prox_i, dist_i = _segment_prox_dist_ref_indices(sub, w)
        prox_seg_ix = dist_seg_ix = None
        if len(prox_i) > imx:
            ig = int(prox_i[imx])
            if 0 <= ig < n and ig != imx:
                prox_seg_ix = ig
        if len(dist_i) > imx:
            ig = int(dist_i[imx])
            if 0 <= ig < n and ig != imx:
                dist_seg_ix = ig

        if area_prox is None and prox_seg_ix is not None:
            ix_prox = prox_seg_ix
            area_prox = _area_row(prox_seg_ix)
        if area_dist is None and dist_seg_ix is not None:
            ix_dist = dist_seg_ix
            area_dist = _area_row(dist_seg_ix)

        if area_prox is not None and len(area_y_arr) == n:
            ix_match = _ref_bar_index_on_polyline(
                area_y_arr,
                gd_line,
                peak_ix=imx,
                ref_area=area_prox,
                gd_anchor=gd_peak - w,
                upstream=True,
                downstream=False,
            )
            if ix_match is not None:
                ix_prox = ix_match
                prox_on_bar = True
            else:
                prox_on_bar = False
        elif ix_prox is not None:
            prox_on_bar = True

        if area_dist is not None and len(area_y_arr) == n:
            ix_match = _ref_bar_index_on_polyline(
                area_y_arr,
                gd_line,
                peak_ix=imx,
                ref_area=area_dist,
                gd_anchor=gd_peak + w,
                upstream=False,
                downstream=True,
            )
            if ix_match is not None:
                ix_dist = ix_match
                dist_on_bar = True
            else:
                dist_on_bar = False
        elif ix_dist is not None:
            dist_on_bar = True

        prox_highlight = ix_prox if prox_on_bar else prox_seg_ix
        dist_highlight = ix_dist if dist_on_bar else dist_seg_ix
    else:
        prox_highlight = dist_highlight = None

    max_pct = float(pct_viz[idx_max]) if idx_max is not None and np.isfinite(pct_viz[idx_max]) else None
    area_max = _area_row(int(idx_max)) if idx_max is not None else None

    return {
        "ok": True,
        "n_points": n,
        "window_mm": w,
        "max_pct_as": max_pct,
        "area_at_max": area_max,
        "max_pct_index": int(idx_max) if idx_max is not None else None,
        "area_prox_ref": area_prox,
        "area_dist_ref": area_dist,
        "prox_ref_index": ix_prox,
        "dist_ref_index": ix_dist,
        "prox_ref_on_segment_bar": prox_on_bar,
        "dist_ref_on_segment_bar": dist_on_bar,
        "prox_ref_segment_window_index": prox_seg_ix if idx_max is not None else None,
        "dist_ref_segment_window_index": dist_seg_ix if idx_max is not None else None,
        "prox_ref_highlight_index": prox_highlight,
        "dist_ref_highlight_index": dist_highlight,
    }


def _profile_bar_colors_from_summary(
    n: int,
    covered: np.ndarray,
    pk_summary: dict[str, Any],
) -> tuple[list[str], list[str], int | None]:
    """Bar colors for Area / %AS rows from ``ordered_centerline_peak_reference_summary``."""
    col_area: list[str] = [_BRANCH_PROFILE_BLUE] * n
    col_pct: list[str] = [_BRANCH_PROFILE_ORANGE] * n
    for i in range(n):
        if not covered[i]:
            col_area[i] = _BRANCH_UNQUANTIFIED_AREA_GREY
            col_pct[i] = _BRANCH_UNQUANTIFIED_BLACK

    idx_max = pk_summary.get("max_pct_index")
    if idx_max is not None:
        bi = int(idx_max)
        if 0 <= bi < n:
            col_area[bi] = _BRANCH_EXTREMA_PURPLE
            col_pct[bi] = _BRANCH_EXTREMA_PURPLE

    for hkey in ("prox_ref_highlight_index", "dist_ref_highlight_index"):
        ix = pk_summary.get(hkey)
        if ix is None:
            continue
        j = int(ix)
        if 0 <= j < n and j != idx_max:
            col_area[j] = _BRANCH_REF_WINDOW_GREEN

    return col_area, col_pct, int(idx_max) if idx_max is not None else None


def _add_peak_ref_area_row_annotations(
    fig: go.Figure,
    *,
    pk_summary: dict[str, Any],
    n: int,
    x_labels: list[str],
    area_y: np.ndarray,
    idx_max_pct: int | None,
    chart_scope: str,
) -> None:
    """
    Green callouts on **row 1** (Area) only when the reference sample is on the plotted polyline.
    Off-segment references get a top callout (no misleading green bar).
    """
    if not pk_summary.get("ok"):
        return
    ap_ref = pk_summary.get("area_prox_ref")
    ad_ref = pk_summary.get("area_dist_ref")
    _fin_a = np.isfinite(area_y)
    if np.any(_fin_a):
        _half_span = 0.5 * float(np.nanmax(np.abs(area_y[_fin_a])))
        ymax_a = _half_span
        ymin_a = -_half_span
    else:
        ymax_a, ymin_a = 1.0, -1.0
    span_a = max(ymax_a - ymin_a, 1e-9)
    y_lbl_off = 0.06 * span_a

    prox_on = bool(pk_summary.get("prox_ref_on_segment_bar"))
    dist_on = bool(pk_summary.get("dist_ref_on_segment_bar"))
    ip = pk_summary.get("prox_ref_highlight_index")
    idist = pk_summary.get("dist_ref_highlight_index")

    def _add_peak_ref_label(
        bar_ix: int | None,
        title: str,
        ax_px: int,
    ) -> None:
        if bar_ix is None:
            return
        bi = int(bar_ix)
        if bi < 0 or bi >= n:
            return
        yb_full = float(area_y[bi])
        if not np.isfinite(yb_full):
            return
        yb = 0.5 * abs(yb_full)
        fig.add_annotation(
            x=x_labels[bi],
            y=yb + y_lbl_off,
            text=f"<b>{title}</b><br>{yb_full:.4f} mm²",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor=_BRANCH_REF_WINDOW_GREEN,
            ax=ax_px,
            ay=-42,
            bgcolor="rgba(10, 38, 16, 0.88)",
            bordercolor=_BRANCH_REF_WINDOW_GREEN,
            borderwidth=1,
            borderpad=4,
            font=dict(color="#e8f5e9", size=11),
            row=1,
            col=1,
        )

    if ip is not None:
        _add_peak_ref_label(
            ip,
            "Prox ref (peak)" if prox_on else "Prox ref (±window on chart)",
            -38,
        )
    if idist is not None:
        _add_peak_ref_label(
            idist,
            "Dist ref (peak)" if dist_on else "Dist ref (±window on chart)",
            38,
        )

    orphan_lines: list[str] = []
    if ap_ref is not None:
        try:
            ap_f = float(ap_ref)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            ap_f = float("nan")
    else:
        ap_f = float("nan")
    if ad_ref is not None:
        try:
            ad_f = float(ad_ref)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            ad_f = float("nan")
    else:
        ad_f = float("nan")
    if np.isfinite(ap_f) and not prox_on and ip is None:
        hint = pk_summary.get("prox_ref_location_hint")
        if not hint:
            hint = (
                "Reference used for %AS at peak is not on this "
                f"{chart_scope}&#39;s Area bars (another {chart_scope} along the branch)."
            )
        orphan_lines.append(
            f"<b>Prox ref (used for %AS at peak)</b>: {ap_f:.4f} mm²<br>"
            f"<span style=\"font-size:0.78em;opacity:0.88;line-height:1.25;\">{hint}</span>"
        )
    if np.isfinite(ad_f) and not dist_on and idist is None:
        hint = pk_summary.get("dist_ref_location_hint")
        if not hint:
            hint = (
                "Reference used for %AS at peak is not on this "
                f"{chart_scope}&#39;s Area bars (another {chart_scope} along the branch)."
            )
        orphan_lines.append(
            f"<b>Dist ref (used for %AS at peak)</b>: {ad_f:.4f} mm²<br>"
            f"<span style=\"font-size:0.78em;opacity:0.88;line-height:1.25;\">{hint}</span>"
        )
    if orphan_lines and idx_max_pct is not None:
        fig.add_annotation(
            xref="x domain",
            x=0.5,
            yref="y domain",
            y=1.06,
            yanchor="bottom",
            text="<br>".join(orphan_lines),
            showarrow=False,
            bgcolor="rgba(10, 38, 16, 0.78)",
            bordercolor=_BRANCH_REF_WINDOW_GREEN,
            borderwidth=1,
            borderpad=5,
            font=dict(color="#e8f5e9", size=11),
            align="center",
            row=1,
            col=1,
        )


def _add_max_pct_as_peak_bar_annotations(
    fig: go.Figure,
    *,
    n: int,
    x_labels: list[str],
    idx_max_pct: int | None,
    pct_y: np.ndarray,
    area_y: np.ndarray,
) -> None:
    """
    Purple callouts (same structure as green ref boxes) on **Area** and **%AS** rows at the
    peak-stenosis sample index, so the purple bars are easy to find when many points are similar.
    """
    if idx_max_pct is None:
        return
    bi = int(idx_max_pct)
    if bi < 0 or bi >= n:
        return

    _purple = _BRANCH_EXTREMA_PURPLE
    _bg = "rgba(48, 18, 72, 0.9)"
    _font = "#f3e8ff"

    # --- Row 1 (Area): symmetric bar top ---
    _fa = np.isfinite(area_y)
    if _fa.any():
        _half_span = 0.5 * float(np.nanmax(np.abs(area_y[_fa])))
        span_a = max(2.0 * _half_span, 1e-9)
    else:
        _half_span, span_a = 0.5, 1.0
    y_lbl_off_a = 0.06 * span_a
    a_full = float(area_y[bi]) if bi < len(area_y) else float("nan")
    if np.isfinite(a_full):
        y1 = 0.5 * abs(a_full) + y_lbl_off_a
        fig.add_annotation(
            x=x_labels[bi],
            y=y1,
            text=f"<b>Max %AS (peak)</b><br>Area {_format_area(a_full)} mm²",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor=_purple,
            ax=0,
            ay=-50,
            bgcolor=_bg,
            bordercolor=_purple,
            borderwidth=1,
            borderpad=4,
            font=dict(color=_font, size=11),
            row=1,
            col=1,
        )

    # --- Row 2 (%AS): bar top from baseline 0 ---
    _fp = np.isfinite(pct_y)
    ymax_p = float(np.nanmax(pct_y[_fp])) if _fp.any() else 0.0
    span_p = max(ymax_p, 1.0)
    y_lbl_off_p = 0.06 * span_p
    pv = float(pct_y[bi]) if bi < len(pct_y) else float("nan")
    if np.isfinite(pv):
        fig.add_annotation(
            x=x_labels[bi],
            y=pv + y_lbl_off_p,
            text=f"<b>Max %AS (peak)</b><br>{pv:.2f} %",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor=_purple,
            ax=0,
            ay=-52,
            bgcolor=_bg,
            bordercolor=_purple,
            borderwidth=1,
            borderpad=4,
            font=dict(color=_font, size=11),
            row=2,
            col=1,
        )


def segment_pct_as_peak_reference_summary(
    artery_centerline_df: pd.DataFrame,
    segment_id: int,
    *,
    window_mm: float | None = None,
) -> dict[str, Any]:
    """
    For one AHA ``segment_id``, on the ordered segment polyline: index of **max finite %AS**,
    **Area** at that point, and **Area** at proximal / distal references.

    When the table includes Block 2 columns ``Area_prox`` / ``Area_dist`` (e.g. ``total_df`` from
    ``results/block2_results/stenosis/``), those values on the **max-%AS row** are used — they match
    the reference band used to compute ``pct_AS`` on export.

    Otherwise (missing columns or non-finite values), reference areas fall back to the nearest
    centerline samples ≈ ±``window_mm`` along branch geodesic ``gd`` (per consecutive ``Branch_ID``
    run), same as segment bar charts.

    Boolean flags ``prox_ref_on_segment_bar`` / ``dist_ref_on_segment_bar`` indicate whether each
    reference area is represented on this segment's Area bars (same Area as a row in the segment
    subset). If ``False``, the reference cross-section typically lies on another AHA segment along
    the branch; the value is still the one used for ``pct_AS`` at the peak.
    """
    w = float(reference_window_mm() if window_mm is None else window_mm)
    sid = int(segment_id)
    d = artery_centerline_df.copy()
    d["_sid"] = pd.to_numeric(d["Segment_ID"], errors="coerce").fillna(0).astype(int)
    sub = d.loc[d["_sid"] == sid].drop(columns=["_sid"], errors="ignore")
    if sub.empty:
        return {"ok": False, "reason": "no_rows", "segment_id": sid}

    sub = _sort_multibranch_centerline(sub)
    out = ordered_centerline_peak_reference_summary(sub, window_mm=w)
    if out.get("ok") and out.get("max_pct_index") is not None:
        imx = int(out["max_pct_index"])
        peak_row = sub.iloc[imx]
        gd_line = _branch_geodesic_mm(sub)
        w_out = float(out.get("window_mm", w))
        gd_peak = float(gd_line[imx]) if imx < len(gd_line) else 0.0
        if not out.get("prox_ref_on_segment_bar") and out.get("area_prox_ref") is not None:
            out["prox_ref_location_hint"] = _reference_location_hint(
                artery_centerline_df,
                peak_row,
                out.get("area_prox_ref"),
                gd_peak - w_out,
            )
        if not out.get("dist_ref_on_segment_bar") and out.get("area_dist_ref") is not None:
            out["dist_ref_location_hint"] = _reference_location_hint(
                artery_centerline_df,
                peak_row,
                out.get("area_dist_ref"),
                gd_peak + w_out,
            )
    return {**out, "segment_id": sid}


def _color_map_for_segment_ids(segment_ids: Iterable[int]) -> dict[int, str]:
    u = sorted({int(x) for x in segment_ids if int(x) > 0})
    pal = _DISCRETE_SEGMENT_COLORS
    return {sid: pal[i % len(pal)] for i, sid in enumerate(u)}


def segment_id_hex_colors(centerline_df: pd.DataFrame) -> dict[int, str]:
    """
    Map each ``Segment_ID`` present in ``centerline_df`` to the same discrete hex/rgb string
    used in ``create_3d_mesh_segment_path_highlight`` / segment bar highlights (Plotly palette).
    """
    if centerline_df.empty or "Segment_ID" not in centerline_df.columns:
        return {}
    d = centerline_df.copy()
    d["_sid"] = pd.to_numeric(d["Segment_ID"], errors="coerce").fillna(0).astype(int)
    u = sorted({int(x) for x in d["_sid"].unique() if int(x) > 0})
    return _color_map_for_segment_ids(u)


def create_3d_mesh_segment_path_highlight(
    mesh_vtp_path: str,
    centerline_df: pd.DataFrame,
    *,
    selected_segment_id: int,
    trace_name: str = "LCA",
) -> go.Figure:
    """
    Artery mesh + centerline tree (dark gray line) with **markers colored by ``Segment_ID``**
    (discrete palette).     The **selected** segment is drawn again on top (dark line + markers with a
    **black** marker outline for contrast). When the segment spans more than one ``Branch_ID``,
    the polyline is split with ``NaN`` breaks so Plotly does not draw a chord between unrelated
    branch runs (same pattern as the full-tree centerline trace).

    A **purple diamond** marks the max-%AS point on the selected segment polyline. Proximal / distal
    **Area** reference samples are **not** drawn in 3D here; they remain visible on the companion
    **Area** bar chart (green markers).

    ``centerline_df`` must include ``Px``, ``Py``, ``Pz``, ``pct_AS``, and ``Segment_ID``; ``Area``
    and ``Branch_ID`` are recommended for tooltips and ordering.
    """
    path = Path(mesh_vtp_path)
    if not path.is_file():
        raise FileNotFoundError(f"Mesh not found: {path}")
    if centerline_df.empty:
        raise ValueError("Centerline dataframe has no rows.")

    required = {"Px", "Py", "Pz", "pct_AS", "Segment_ID"}
    missing = required - set(centerline_df.columns)
    if missing:
        raise ValueError(f"Segment highlight dataframe missing columns: {sorted(missing)}")

    d = centerline_df.copy()
    d["_seg"] = pd.to_numeric(d["Segment_ID"], errors="coerce").fillna(0).astype(int)
    seg_ids_in_data = [int(x) for x in d["_seg"].unique() if int(x) > 0]
    id_to_color = _color_map_for_segment_ids(seg_ids_in_data)

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

    d_tree = d.drop(columns=["_seg"], errors="ignore")
    branch_groups = list(d_tree.groupby("Branch_ID", sort=False)) if "Branch_ID" in d_tree.columns else [
        (trace_name, d_tree)
    ]
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
    col_m: list[str] = []
    hover_b: list[str] = []
    _nan = float("nan")
    for bi, (_bid, g) in enumerate(non_empty):
        if bi > 0:
            xs_b.append(_nan)
            ys_b.append(_nan)
            zs_b.append(_nan)
            col_m.append(_SEGMENT_UNASSIGNED_MARKER)
            hover_b.append("")
        for _, row in g.iterrows():
            xs_b.append(float(row["Px"]))
            ys_b.append(float(row["Py"]))
            zs_b.append(float(row["Pz"]))
            sid = int(pd.to_numeric(row.get("Segment_ID"), errors="coerce") or 0)
            col_m.append(id_to_color.get(sid, _SEGMENT_UNASSIGNED_MARKER) if sid > 0 else _SEGMENT_UNASSIGNED_MARKER)
            bid = str(row.get("Branch_ID", _bid)).strip()
            hover_b.append(
                f"<b>{trace_name}</b><br>"
                f"<b>Branch</b>: {html_escape_simple(bid)}<br>"
                f"Segment: {_segment_display_name(row)}<br>"
                f"Segment ID: {_segment_id_display(row)}<br>"
                f"Area: {_format_area(row.get('Area'))} mm²<br>"
                f"%AS: {_format_pct(row.get('pct_AS'))} %"
            )

    traces.append(
        go.Scatter3d(
            name=f"{trace_name} · tree by segment",
            x=np.asarray(xs_b, dtype=float),
            y=np.asarray(ys_b, dtype=float),
            z=np.asarray(zs_b, dtype=float),
            mode="lines+markers",
            line=dict(color="rgb(38,38,38)", width=2.5),
            marker=dict(
                size=6,
                color=col_m,
                line=dict(width=0),
            ),
            text=hover_b,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    sel = int(selected_segment_id)
    d_hi = d.loc[d["_seg"] == sel].drop(columns=["_seg"], errors="ignore")
    if not d_hi.empty:
        g_hi = _sort_multibranch_centerline(d_hi)
        _nan = float("nan")
        xs_h: list[float] = []
        ys_h: list[float] = []
        zs_h: list[float] = []
        hh: list[str] = []
        for run_i, (a, b) in enumerate(_consecutive_branch_id_slices(g_hi)):
            if run_i > 0:
                xs_h.append(_nan)
                ys_h.append(_nan)
                zs_h.append(_nan)
                hh.append("")
            chunk = g_hi.iloc[a:b]
            for _, row in chunk.iterrows():
                xs_h.append(float(row["Px"]))
                ys_h.append(float(row["Py"]))
                zs_h.append(float(row["Pz"]))
                hh.append(
                    f"<b>{trace_name} · selected segment</b><br>"
                    f"Segment: {_segment_display_name(row)}<br>"
                    f"Segment ID: {sel}<br>"
                    f"Area: {_format_area(row.get('Area'))} mm²<br>"
                    f"%AS: {_format_pct(row.get('pct_AS'))} %"
                )
        traces.append(
            go.Scatter3d(
                name=f"{trace_name} · segment {sel}",
                x=np.asarray(xs_h, dtype=float),
                y=np.asarray(ys_h, dtype=float),
                z=np.asarray(zs_h, dtype=float),
                mode="lines+markers",
                line=dict(color=_SEGMENT_3D_SELECTED_PATH, width=6.5),
                marker=dict(
                    size=11,
                    color=_SEGMENT_3D_SELECTED_PATH,
                    line=dict(color="#000000", width=2.5),
                ),
                text=hh,
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            )
        )

        area_col_hi = _find_df_column(g_hi, "Area")
        pk_seg = ordered_centerline_peak_reference_summary(g_hi)
        idx_max_pct = pk_seg.get("max_pct_index")

        if idx_max_pct is not None:
            row_m = g_hi.iloc[idx_max_pct]
            lines_h = [
                f"<b>{trace_name} · segment {sel} · max %AS · point {idx_max_pct + 1}</b>",
                f"Segment: {_segment_display_name(row_m)}",
                f"<b>Max %AS</b>: {_format_pct(row_m.get('pct_AS'))} %",
            ]
            if area_col_hi:
                lines_h.append(f"<b>Area at this point</b>: {_format_area(row_m.get(area_col_hi))} mm²")
            traces.append(
                go.Scatter3d(
                    name=f"{trace_name} · seg {sel} · max %AS",
                    x=np.asarray([float(row_m["Px"])], dtype=float),
                    y=np.asarray([float(row_m["Py"])], dtype=float),
                    z=np.asarray([float(row_m["Pz"])], dtype=float),
                    mode="markers",
                    marker=dict(
                        size=13,
                        color=_BRANCH_EXTREMA_PURPLE,
                        symbol="diamond",
                        line=dict(color="#fafafa", width=2),
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
        height=700,
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


def html_escape_simple(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def create_segment_centerline_metric_bars(
    artery_centerline_df: pd.DataFrame,
    *,
    selected_segment_id: int,
    artery: str,
) -> go.Figure:
    """
    Same layout as ``create_branch_centerline_metric_bars`` for **one AHA segment** (all points
    with that ``Segment_ID`` in the artery table), ordered along the tree. **Area** bars are
    symmetric about ``y=0`` (``-A/2`` … ``+A/2``). Purple marks max %AS
    on both Area and %AS rows. **Green** on the **Area** row only marks proximal / distal reference
    samples (± ``BRANCH_PCT_AS_REFERENCE_WINDOW_MM`` mm along branch geodesic ``gd`` when present,
    same as Block 2 / branch charts), per consecutive ``Branch_ID`` run, when those indices are valid
    and distinct from the peak.

    When reference areas for %AS at the peak are available (``segment_pct_as_peak_reference_summary``),
    the **Area** subplot shows small labels with those **Prox / Dist ref** values so they match the
    summary panel above the visualization. If a reference area is not represented on this segment’s
    Area bars (another segment along the branch), the same note appears on the chart and in the
    summary list (``prox_ref_on_segment_bar`` / ``dist_ref_on_segment_bar``).
    """
    if artery_centerline_df.empty:
        raise ValueError("Artery centerline dataframe is empty.")

    pct_col = _find_df_column(artery_centerline_df, "pct_AS", "Pct_AS", "PCT_AS")
    area_col = _find_df_column(artery_centerline_df, "Area")
    if not pct_col:
        raise ValueError("No %AS column found (expected pct_AS).")
    if not area_col:
        raise ValueError("No Area column found.")

    sid = int(selected_segment_id)
    d = artery_centerline_df.copy()
    d["_sid"] = pd.to_numeric(d["Segment_ID"], errors="coerce").fillna(0).astype(int)
    sub = d.loc[d["_sid"] == sid].drop(columns=["_sid"], errors="ignore")
    if sub.empty:
        raise ValueError(f"No rows for segment ID {sid}.")

    sub = _sort_multibranch_centerline(sub)
    if len(sub) == 0:
        raise ValueError("Selected segment has no centerline points.")

    pk_summary = segment_pct_as_peak_reference_summary(artery_centerline_df, sid)
    art = str(artery).strip().upper()
    seg_title = _segment_display_name(sub.iloc[0])
    return _create_centerline_profile_bars_figure(
        sub,
        pk_summary=pk_summary,
        title_area=f"Cross-sectional area along segment · {art} · {seg_title} (ID {sid})",
        title_pct=f"% area stenosis along segment · {art} · {seg_title} (ID {sid})",
        x_axis_title_row2="Along-segment sample index (1 = start of ordered polyline)",
        point_label="ordered along segment",
        chart_scope="segment",
    )
