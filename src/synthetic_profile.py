"""
Synthetic validation cases (single-tube NRRD masks under ``data/Synthetic Samples``).

Detected when ``patient_id.startswith("Synthetic_")``.

Phantom geometry matches ``notebooks/experiments/synthetic quantification/synthetic_data_gen.ipynb``.
Block 2 measures cross-sectional areas with the **same VMTK section pipeline** as ASOCA
cases (mesh + centerline → ``vmtkCenterlineSections``); the analytical πR² formula encoded
here is only used as a **ground-truth reference** in ``synthetic_validation_metrics`` to
quantify how well the geometry extraction recovers the known phantom.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
SYNTHETIC_DATA_ROOT = DATA_ROOT / "Synthetic Samples"

SYNTHETIC_ARTERY = "Synthetic"
SYNTHETIC_BRANCH_ID = 0
SYNTHETIC_SEGMENT_ID = 99
SYNTHETIC_SEGMENT_NAME = "Synthetic Vessel"
SYNTHETIC_SEGMENT_TAG = "Synthetic_Vessel"
SYNTHETIC_CAD_RADS_LABEL = "N/A (Synthetic Case)"

# --- Phantom geometry (1 mm isotropic grid, tube along index Z) -----------------
SYNTHETIC_CENTER_XY_MM = (50.0, 50.0)
SYNTHETIC_Z_START_MM = 15.0
SYNTHETIC_Z_END_MM = 85.0
SYNTHETIC_R_BASE_MM = 10.0
SYNTHETIC_Z_NARROW_LO_MM = 40.0
SYNTHETIC_Z_NARROW_HI_MM = 60.0
SYNTHETIC_Z_NARROW_MID_MM = 50.0
SYNTHETIC_R_MIN_MM = 5.0
# Exclude cap + junction zones from centerline / quantification (mm along axis).
SYNTHETIC_BODY_TRIM_MM = 12.0

SYNTHETIC_HEALTHY_ID = "Synthetic_1"
SYNTHETIC_STENOSIS_ID = "Synthetic_2"


def is_synthetic_patient(patient_id: str) -> bool:
    return str(patient_id).strip().startswith("Synthetic_")


def is_stenosis_synthetic_patient(patient_id: str) -> bool:
    return str(patient_id).strip() == SYNTHETIC_STENOSIS_ID


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path.resolve()
    return None


def _asoca_mask_candidates(patient_id: str) -> list[Path]:
    pid = str(patient_id).strip()
    if pid.startswith("Normal_"):
        return [
            DATA_ROOT / "ASOCA" / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
            DATA_ROOT / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
        ]
    if pid.startswith("Diseased_"):
        return [
            DATA_ROOT / "ASOCA" / "ASOCA Diseased" / f"{pid}.nrrd",
            DATA_ROOT / "ASOCA Diseased" / f"{pid}.nrrd",
        ]
    return [
        DATA_ROOT / "ASOCA" / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
        DATA_ROOT / "ASOCA" / "ASOCA Diseased" / f"{pid}.nrrd",
        DATA_ROOT / "ASOCA Normal" / "Annotations" / f"{pid}.nrrd",
        DATA_ROOT / "ASOCA Diseased" / f"{pid}.nrrd",
    ]


def resolve_mask_nrrd_path(patient_id: str) -> Path:
    """Return the segmentation mask ``.nrrd`` for the given patient (any cohort).

    Synthetic IDs are resolved locally because they live under ``data/Synthetic Samples``
    and the synthetic phantom code in this module is the only place that knows about them.
    All other IDs (ASOCA + MACS-18) are dispatched to :mod:`src.cohort_paths`, which has
    the proper per-cohort folder map and the ``MACS_PIPELINE_ENABLED`` gate.
    """
    pid = str(patient_id).strip()
    if is_synthetic_patient(pid):
        return (SYNTHETIC_DATA_ROOT / f"{pid}.nrrd").resolve()
    # Imported lazily to avoid a hard dependency for callers that only use the synthetic helpers.
    from src.cohort_paths import resolve_mask_nrrd_path as _resolve_cohort_mask

    return _resolve_cohort_mask(pid)


def apply_synthetic_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Populate placeholder anatomy / segment columns for synthetic single-tube cases."""
    out = df.copy()
    out["Artery_Type"] = SYNTHETIC_ARTERY
    out["Branch_ID"] = SYNTHETIC_BRANCH_ID
    out["Segment_ID"] = SYNTHETIC_SEGMENT_ID
    out["Segment_Name"] = SYNTHETIC_SEGMENT_NAME
    return out


def synthetic_branch_file_stem() -> str:
    """Branch spreadsheet / centerline filename stem (``dataset_<stem>_<patient>.xlsx``)."""
    return f"{SYNTHETIC_ARTERY}_{SYNTHETIC_BRANCH_ID}"


def _radius_body_mm(z: np.ndarray, *, stenosis: bool) -> np.ndarray:
    """Radius on the cylindrical body segment [Z_START, Z_END]."""
    r = np.full_like(z, SYNTHETIC_R_BASE_MM, dtype=float)
    if not stenosis:
        return r
    in_narrow = (z >= SYNTHETIC_Z_NARROW_LO_MM) & (z <= SYNTHETIC_Z_NARROW_HI_MM)
    half_w = (SYNTHETIC_Z_NARROW_HI_MM - SYNTHETIC_Z_NARROW_LO_MM) / 2.0
    t = (z[in_narrow] - SYNTHETIC_Z_NARROW_MID_MM) / half_w
    r[in_narrow] = SYNTHETIC_R_MIN_MM + (SYNTHETIC_R_BASE_MM - SYNTHETIC_R_MIN_MM) * (
        1.0 - np.cos(np.pi * t)
    ) / 2.0
    return r


def synthetic_radius_mm(z_mm: np.ndarray | float, *, stenosis: bool) -> np.ndarray:
    """
    Ground-truth lumen radius (mm) for the capped-tube phantom at axial coordinate ``z_mm``.

    Union of cylindrical body and hemispherical end caps (same construction as mask notebook).
    """
    z = np.atleast_1d(np.asarray(z_mm, dtype=float))
    r_out = np.zeros_like(z, dtype=float)
    r_cap = SYNTHETIC_R_BASE_MM

    in_body = (z >= SYNTHETIC_Z_START_MM) & (z <= SYNTHETIC_Z_END_MM)
    if np.any(in_body):
        r_out[in_body] = _radius_body_mm(z[in_body], stenosis=stenosis)

    below = z < SYNTHETIC_Z_START_MM
    if np.any(below):
        dz = SYNTHETIC_Z_START_MM - z[below]
        ok = dz <= r_cap
        r_out[below] = 0.0
        r_out[np.where(below)[0][ok]] = np.sqrt(np.maximum(0.0, r_cap**2 - dz[ok] ** 2))

    above = z > SYNTHETIC_Z_END_MM
    if np.any(above):
        dz = z[above] - SYNTHETIC_Z_END_MM
        ok = dz <= r_cap
        r_out[above] = 0.0
        r_out[np.where(above)[0][ok]] = np.sqrt(np.maximum(0.0, r_cap**2 - dz[ok] ** 2))

    return r_out if r_out.size > 1 else r_out.astype(float)


def synthetic_axial_coord_mm(points_xyz: np.ndarray) -> tuple[np.ndarray, int]:
    """
    Infer the dominant tube axis (mm) for centerline points.

    Phantoms are built along index **Z** with 1 mm spacing and origin 0 → physical ``Pz``
    is the axial coordinate in the usual LPS load order.
    """
    pts = np.asarray(points_xyz, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError("points_xyz must be (N, 3)")
    spans = [float(np.ptp(pts[:, i])) for i in range(3)]
    axis = int(np.argmax(spans))
    return pts[:, axis], axis


def synthetic_analytical_area_mm2(
    points_xyz: np.ndarray,
    patient_id: str,
) -> np.ndarray:
    """Ground-truth cross-sectional area πR(z)² along the phantom (validation cohort only)."""
    z_mm, _ = synthetic_axial_coord_mm(points_xyz)
    stenosis = is_stenosis_synthetic_patient(patient_id)
    r_mm = synthetic_radius_mm(z_mm, stenosis=stenosis)
    return np.pi * np.square(r_mm)


def _theoretical_max_pct_as(patient_id: str) -> float:
    """Analytical peak %AS for the phantom (0 for healthy, 75% for cosine stenosis)."""
    if not is_stenosis_synthetic_patient(patient_id):
        return 0.0
    return float((1.0 - (SYNTHETIC_R_MIN_MM / SYNTHETIC_R_BASE_MM) ** 2) * 100.0)


def _theoretical_area_bounds_mm2(patient_id: str) -> tuple[float, float]:
    """(A_max, A_min) ground-truth areas along the body (healthy → both = πR_base²)."""
    a_max = float(np.pi * SYNTHETIC_R_BASE_MM**2)
    if is_stenosis_synthetic_patient(patient_id):
        a_min = float(np.pi * SYNTHETIC_R_MIN_MM**2)
    else:
        a_min = a_max
    return a_max, a_min


def synthetic_validation_metrics(
    centerline_df: pd.DataFrame,
    patient_id: str,
) -> dict:
    """
    Compare predicted ``Area`` / ``pct_AS`` against the analytical phantom ground truth.

    Used by the Streamlit synthetic dashboard to display validation values that match
    the geodesic profile plotted from the same centerline dataframe. The %AS reduction
    convention mirrors the viewer (`np.maximum(pct, 0)`), so ``predicted_max_pct_as``
    equals the peak rendered in the along-vessel chart.

    Returns a JSON-serializable dict. Missing values are ``None``.
    """
    out: dict = {
        "patient_id": str(patient_id),
        "is_stenosis": bool(is_stenosis_synthetic_patient(patient_id)),
        "ok": False,
    }
    if centerline_df is None or len(centerline_df) == 0:
        out["reason"] = "empty centerline"
        return out
    required = {"Px", "Py", "Pz", "Area"}
    if not required.issubset(centerline_df.columns):
        out["reason"] = f"missing columns: {sorted(required - set(centerline_df.columns))}"
        return out

    pts = centerline_df[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    area_pred = pd.to_numeric(centerline_df["Area"], errors="coerce").to_numpy(dtype=float)
    area_theo = synthetic_analytical_area_mm2(pts, patient_id)

    finite = np.isfinite(area_pred) & np.isfinite(area_theo) & (area_theo > 0.0)
    if not np.any(finite):
        out["reason"] = "no finite predicted areas"
        return out

    a_pred = area_pred[finite]
    a_theo = area_theo[finite]
    diff = np.abs(a_pred - a_theo)
    mean_a_pred = float(np.mean(a_pred))
    mean_a_theo = float(np.mean(a_theo))

    # Sample-level peak |A_pred − A_theo| (kept inside the finite subset to stay self-consistent).
    finite_idx = np.where(finite)[0]
    rel_idx = int(np.argmax(diff))
    deviation_global_idx = int(finite_idx[rel_idx])
    a_pred_at_dev = float(a_pred[rel_idx])
    a_theo_at_dev = float(a_theo[rel_idx])

    # Predicted %AS — mirror viewer convention (clamp negatives, ignore NaN).
    pct_max_pred: float | None = None
    if "pct_AS" in centerline_df.columns:
        pct_raw = pd.to_numeric(centerline_df["pct_AS"], errors="coerce").to_numpy(dtype=float)
        pct_clamped = np.where(np.isfinite(pct_raw), np.maximum(pct_raw, 0.0), np.nan)
        if np.any(np.isfinite(pct_clamped)):
            pct_max_pred = float(np.nanmax(pct_clamped))

    theo_max_pct = _theoretical_max_pct_as(patient_id)
    theo_a_max, theo_a_min = _theoretical_area_bounds_mm2(patient_id)
    pred_a_max = float(np.max(a_pred))
    pred_a_min = float(np.min(a_pred))

    abs_err_max_pct = None if pct_max_pred is None else float(abs(theo_max_pct - pct_max_pred))

    out.update(
        {
            "ok": True,
            "n_points": int(len(centerline_df)),
            "n_valid_points": int(finite.sum()),
            "theoretical_max_pct_as": float(theo_max_pct),
            "predicted_max_pct_as": pct_max_pred,
            "abs_error_max_pct_as": abs_err_max_pct,
            "theoretical_max_area_mm2": float(theo_a_max),
            "theoretical_min_area_mm2": float(theo_a_min),
            "theoretical_mean_area_mm2": mean_a_theo,
            "predicted_max_area_mm2": pred_a_max,
            "predicted_min_area_mm2": pred_a_min,
            "predicted_mean_area_mm2": mean_a_pred,
            "abs_error_max_area_mm2": float(abs(theo_a_max - pred_a_max)),
            "abs_error_min_area_mm2": float(abs(theo_a_min - pred_a_min)),
            "abs_error_mean_area_mm2": float(abs(mean_a_theo - mean_a_pred)),
            "mean_area_abs_error_mm2": float(np.mean(diff)),
            "max_area_abs_deviation_mm2": float(np.max(diff)),
            "max_area_deviation_predicted_mm2": a_pred_at_dev,
            "max_area_deviation_theoretical_mm2": a_theo_at_dev,
            "max_area_deviation_index": deviation_global_idx,
            "axial_extent_mm": [
                float(np.min(pts[:, 2])),
                float(np.max(pts[:, 2])),
            ],
        }
    )
    return out


def synthetic_body_axial_bounds_mm() -> tuple[float, float]:
    """Axial range (mm) used to trim VMTK centerlines to the cylindrical body (no caps)."""
    margin = float(SYNTHETIC_BODY_TRIM_MM)
    return SYNTHETIC_Z_START_MM + margin, SYNTHETIC_Z_END_MM - margin


def trim_synthetic_centerline_dict(out: dict) -> dict:
    """
    Drop centerline samples in hemispherical caps / junction artifacts.

    Keeps only points whose axial coordinate lies in the cylindrical body plateau.
    """
    df = out.get("df_artery")
    if df is None or df.empty:
        return out
    pts = df[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    z_mm, _ = synthetic_axial_coord_mm(pts)
    z_lo, z_hi = synthetic_body_axial_bounds_mm()
    keep = (z_mm >= z_lo) & (z_mm <= z_hi)
    if not np.any(keep):
        return out

    df_trim = df.loc[keep].reset_index(drop=True)
    if "Path_Point_Index" in df_trim.columns:
        df_trim["Path_Point_Index"] = np.arange(len(df_trim), dtype=int)
    if "PointType" in df_trim.columns and len(df_trim) > 0:
        ptype = np.array(["Path"] * len(df_trim), dtype=object)
        ptype[0] = "Ostium"
        if len(ptype) > 1:
            ptype[-1] = "Endpoint"
        df_trim["PointType"] = ptype

    branch_pts = df_trim[["Px", "Py", "Pz"]].to_numpy(dtype=float)
    branch_poly = pv.lines_from_points(branch_pts, close=False)
    if "Radius" in df_trim.columns:
        branch_poly.point_data["MaximumInscribedSphereRadius"] = df_trim["Radius"].to_numpy(dtype=float)

    branch_id = synthetic_branch_file_stem()
    out["df_artery"] = df_trim
    out["branches"] = [{"branch_id": branch_id, "poly": branch_poly, "df": df_trim}]
    if "centerline_poly" in out:
        out["centerline_poly"] = branch_poly
    return out
