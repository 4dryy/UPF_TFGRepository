"""
Block 1 — Hybrid Centerline Extraction.

Loads a patient's .nrrd coronary mask, separates RCA/LCA via center-of-mass,
discovers seed points through 3D skeletonization, and extracts VMTK Voronoi
centerlines with maximum inscribed sphere radii.

Outputs:
    - Excel (.xlsx) DataFrame with columns: Patient_ID, Artery_Type, Px, Py, Pz, Radius
    - VTP (.vtp) centerline polydata for each artery
"""

from __future__ import annotations

import logging
import sys
import time
import types
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv
import scipy.ndimage as ndi
from skimage.morphology import skeletonize
from vmtk import vmtkscripts
from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
from vtkmodules.vtkCommonDataModel import vtkImageData

sys.modules.setdefault(
    "vtkmodules.vtkRenderingMatplotlib",
    types.ModuleType("vtkmodules.vtkRenderingMatplotlib"),
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
RESULTS_ROOT = PROJECT_ROOT / "results" / "block1_results"
DF_DIR = RESULTS_ROOT / "dataframes"
CL_DIR = RESULTS_ROOT / "centerlines"


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _find_skeleton_endpoints(skeleton: np.ndarray) -> np.ndarray:
    """Return (N, 3) array of [z, y, x] voxel indices for degree-1 skeleton nodes."""
    kernel = np.ones((3, 3, 3), dtype=int)
    kernel[1, 1, 1] = 0
    neighbor_count = ndi.convolve(skeleton.astype(int), kernel, mode="constant", cval=0)
    endpoint_mask = (skeleton > 0) & (neighbor_count == 1)
    return np.argwhere(endpoint_mask)


def _identify_ostium(endpoints_zyx: np.ndarray, binary_mask: np.ndarray) -> tuple[int, np.ndarray]:
    """Return (index, distances) for the endpoint deepest inside the vessel (max EDT)."""
    dist_transform = ndi.distance_transform_edt(binary_mask)
    dists = dist_transform[endpoints_zyx[:, 0], endpoints_zyx[:, 1], endpoints_zyx[:, 2]]
    return int(np.argmax(dists)), dists


def _voxel_to_physical(coords_zyx: np.ndarray, origin: np.ndarray, spacing: np.ndarray) -> np.ndarray:
    """Convert voxel indices (z, y, x) to physical coordinates (X, Y, Z) in mm."""
    phys_x = origin[0] + coords_zyx[:, 2] * spacing[0]
    phys_y = origin[1] + coords_zyx[:, 1] * spacing[1]
    phys_z = origin[2] + coords_zyx[:, 0] * spacing[2]
    return np.column_stack([phys_x, phys_y, phys_z])


def _numpy_to_vtk_image(array_zyx: np.ndarray, spacing: np.ndarray, origin: np.ndarray) -> vtkImageData:
    """Pack a (Z, Y, X) NumPy array into a vtkImageData with correct metadata."""
    nz, ny, nx = array_zyx.shape
    vtk_img = vtkImageData()
    vtk_img.SetDimensions(nx, ny, nz)
    vtk_img.SetSpacing(float(spacing[0]), float(spacing[1]), float(spacing[2]))
    vtk_img.SetOrigin(float(origin[0]), float(origin[1]), float(origin[2]))
    flat = np.ascontiguousarray(array_zyx.flatten(), dtype=np.float64)
    vtk_arr = numpy_to_vtk(flat)
    vtk_arr.SetName("ImageScalars")
    vtk_img.GetPointData().SetScalars(vtk_arr)
    return vtk_img


def _snap_seed_to_surface(
    mesh: pv.PolyData,
    point: np.ndarray,
    inward_fraction: float = 0.3,
) -> list[float]:
    """
    Project a seed point onto the mesh surface, then nudge it slightly inward
    along the vertex normal so it sits inside the tubular geometry.

    VMTK's Voronoi-based centerline tracer needs seeds that lie *on or just
    inside* the surface.  A naive closest-vertex snap can land on the outer
    shell, causing "no steepest descent edge" failures.

    Parameters
    ----------
    mesh : pv.PolyData
        The smoothed surface mesh (must have point normals or they will be
        computed).
    point : array-like
        The (x, y, z) seed in physical coordinates.
    inward_fraction : float
        Fraction of the local edge length used to push the point inward.
        Kept small (default 0.3) so the seed stays very close to the surface.
    """
    idx = mesh.find_closest_point(point)
    surface_pt = mesh.points[idx].copy()

    if mesh.point_normals is not None:
        normal = mesh.point_normals[idx]
    else:
        mesh_with_normals = mesh.compute_normals(
            point_normals=True, cell_normals=False, consistent_normals=True,
        )
        normal = mesh_with_normals.point_normals[idx]

    norm_len = np.linalg.norm(normal)
    if norm_len < 1e-12:
        return surface_pt.tolist()

    normal = normal / norm_len

    edges = mesh.extract_feature_edges(
        boundary_edges=False, non_manifold_edges=False,
        feature_edges=False, manifold_edges=True,
    )
    if edges.n_points > 1:
        avg_edge_len = np.mean(np.linalg.norm(np.diff(edges.points[:100], axis=0), axis=1))
    else:
        avg_edge_len = np.mean(mesh.spacing) if hasattr(mesh, "spacing") else 0.2

    to_center = np.array(point, dtype=float) - surface_pt
    if np.dot(to_center, normal) > 0:
        inward_normal = normal
    else:
        inward_normal = -normal

    nudged = surface_pt + inward_fraction * avg_edge_len * inward_normal

    final_idx = mesh.find_closest_point(nudged)
    return mesh.points[final_idx].tolist()


# ── Phase 1: Mask loading & RCA/LCA separation ───────────────────────────────

def load_and_separate_mask(nrrd_path: Path) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """
    Load a binary .nrrd coronary mask and separate it into RCA and LCA.

    Returns
    -------
    artery_arrays : dict mapping ``"RCA"`` / ``"LCA"`` to binary uint8 arrays (Z, Y, X).
    spacing : image spacing in mm.
    origin  : image origin in mm.
    """
    logger.info("Loading mask from %s", nrrd_path)

    reader = vmtkscripts.vmtkImageReader()
    reader.InputFileName = str(nrrd_path)
    reader.Execute()

    vtk_image = reader.Image
    spacing = np.array(vtk_image.GetSpacing())
    origin = np.array(vtk_image.GetOrigin())
    dims = vtk_image.GetDimensions()

    vtk_scalars = vtk_image.GetPointData().GetScalars()
    mask = vtk_to_numpy(vtk_scalars).reshape(dims[2], dims[1], dims[0]).astype(np.uint8)
    logger.info("Mask shape (Z,Y,X)=%s  spacing=%s  origin=%s", mask.shape, spacing, origin)

    labeled, num_components = ndi.label(mask)
    logger.info("Connected components found: %d", num_components)

    component_sizes = ndi.sum(mask, labeled, range(1, num_components + 1))
    sorted_labels = np.argsort(component_sizes)[::-1] + 1
    label_a, label_b = sorted_labels[0], sorted_labels[1]

    com_a = ndi.center_of_mass(mask, labeled, label_a)
    com_b = ndi.center_of_mass(mask, labeled, label_b)
    phys_x_a = origin[0] + com_a[2] * spacing[0]
    phys_x_b = origin[0] + com_b[2] * spacing[0]

    if phys_x_a < phys_x_b:
        rca_label, lca_label = label_a, label_b
    else:
        rca_label, lca_label = label_b, label_a

    artery_arrays = {
        "RCA": (labeled == rca_label).astype(np.uint8),
        "LCA": (labeled == lca_label).astype(np.uint8),
    }
    for name, arr in artery_arrays.items():
        logger.info("%s: %s voxels", name, f"{np.count_nonzero(arr):,}")

    return artery_arrays, spacing, origin


# ── Phase 2 & 3: Scout + VMTK per artery ─────────────────────────────────────

def extract_single_artery(
    artery_name: str,
    artery_mask: np.ndarray,
    spacing: np.ndarray,
    origin: np.ndarray,
    patient_id: str,
    smoothing_iterations: int = 20,
    smoothing_passband: float = 0.1,
) -> tuple[pd.DataFrame, pv.PolyData] | None:
    """
    Run the full hybrid pipeline on one artery.

    Returns ``(dataframe, centerline_polydata)`` or ``None`` if fewer than
    2 endpoints are found.
    """
    # ── Phase 2: Scout ────────────────────────────────────────────────────
    logger.info("[%s] Running 3D skeletonization", artery_name)
    skeleton = skeletonize(artery_mask)
    logger.info("[%s] Skeleton voxels: %s", artery_name, f"{np.count_nonzero(skeleton):,}")

    endpoints_zyx = _find_skeleton_endpoints(skeleton)
    logger.info("[%s] Endpoints found: %d", artery_name, len(endpoints_zyx))

    if len(endpoints_zyx) < 2:
        logger.warning("[%s] Fewer than 2 endpoints — skipping.", artery_name)
        return None

    ostium_idx, dists = _identify_ostium(endpoints_zyx, artery_mask)
    logger.info("[%s] Ostium = endpoint #%d (EDT=%.2f voxels)", artery_name, ostium_idx, dists[ostium_idx])

    source_zyx = endpoints_zyx[ostium_idx : ostium_idx + 1]
    target_mask_bool = np.ones(len(endpoints_zyx), dtype=bool)
    target_mask_bool[ostium_idx] = False
    targets_zyx = endpoints_zyx[target_mask_bool]

    source_phys = _voxel_to_physical(source_zyx, origin, spacing)
    targets_phys = _voxel_to_physical(targets_zyx, origin, spacing)
    logger.info("[%s] Source (mm): %s", artery_name, source_phys[0])
    logger.info("[%s] Targets: %d branch tips", artery_name, len(targets_phys))

    # ── Phase 3a: Surface mesh ────────────────────────────────────────────
    logger.info("[%s] Building surface mesh (MarchingCubes + Taubin smoothing)", artery_name)
    vtk_artery = _numpy_to_vtk_image(artery_mask, spacing, origin)

    mc = vmtkscripts.vmtkMarchingCubes()
    mc.Image = vtk_artery
    mc.Level = 0.5
    mc.Execute()

    smoother = vmtkscripts.vmtkSurfaceSmoothing()
    smoother.Surface = mc.Surface
    smoother.NumberOfIterations = smoothing_iterations
    smoother.PassBand = smoothing_passband
    smoother.Execute()

    mesh_smooth = pv.wrap(smoother.Surface)
    logger.info("[%s] Surface: %s vertices, %s triangles",
                artery_name, f"{mesh_smooth.n_points:,}", f"{mesh_smooth.n_cells:,}")

    source_flat = _snap_seed_to_surface(mesh_smooth, source_phys[0])
    targets_flat: list[float] = []
    for t in targets_phys:
        targets_flat.extend(_snap_seed_to_surface(mesh_smooth, t))

    # ── Phase 3b: VMTK Centerlines ───────────────────────────────────────
    logger.info("[%s] Extracting VMTK centerlines", artery_name)
    cl = vmtkscripts.vmtkCenterlines()
    cl.Surface = smoother.Surface
    cl.SeedSelectorName = "pointlist"
    cl.SourcePoints = source_flat
    cl.TargetPoints = targets_flat
    cl.AppendEndPoints = 1
    cl.Execute()

    centerlines = pv.wrap(cl.Centerlines)
    cl_points = centerlines.points
    cl_radii = centerlines.point_data["MaximumInscribedSphereRadius"]
    logger.info("[%s] Centerline points: %d", artery_name, len(cl_points))
    logger.info("[%s] Radius range: [%.3f , %.3f] mm", artery_name, cl_radii.min(), cl_radii.max())

    df_artery = pd.DataFrame({
        "Patient_ID": patient_id,
        "Artery_Type": artery_name,
        "Px": cl_points[:, 0],
        "Py": cl_points[:, 1],
        "Pz": cl_points[:, 2],
        "Radius": cl_radii,
    })

    return df_artery, centerlines


# ── Public entry-point ────────────────────────────────────────────────────────

def run_block1(patient_id: str, nrrd_path: Path | None = None) -> pd.DataFrame:
    """
    Execute the full Block 1 pipeline for a single patient.

    Parameters
    ----------
    patient_id : str
        Patient identifier, e.g. ``"Normal_1"``.
    nrrd_path : Path, optional
        Explicit path to the ``.nrrd`` file.  When ``None`` the path is
        resolved as ``data/ASOCA Normal/Annotations/<patient_id>.nrrd``.

    Returns
    -------
    pd.DataFrame
        Combined centerline data for RCA and LCA.
    """
    t_start = time.perf_counter()
    timestamp = datetime.now().strftime("%Y%m%d")

    if nrrd_path is None:
        nrrd_path = DATA_ROOT / "ASOCA Normal" / "Annotations" / f"{patient_id}.nrrd"

    if not nrrd_path.exists():
        raise FileNotFoundError(f"Mask not found: {nrrd_path}")

    DF_DIR.mkdir(parents=True, exist_ok=True)
    CL_DIR.mkdir(parents=True, exist_ok=True)

    # Remove previous results for this patient to avoid duplicates
    for old in CL_DIR.glob(f"centerline_{patient_id}_*.vtp"):
        old.unlink()
        logger.info("[Cleanup] Removed %s", old.name)
    for old in DF_DIR.glob(f"df_{patient_id}_*.xlsx"):
        old.unlink()
        logger.info("[Cleanup] Removed %s", old.name)

    artery_arrays, spacing, origin = load_and_separate_mask(nrrd_path)

    all_dfs: list[pd.DataFrame] = []
    for artery_name, artery_mask in artery_arrays.items():
        result = extract_single_artery(artery_name, artery_mask, spacing, origin, patient_id)
        if result is None:
            continue
        df_artery, centerline_polydata = result
        all_dfs.append(df_artery)

        vtp_path = CL_DIR / f"centerline_{patient_id}_{artery_name}_{timestamp}.vtp"
        centerline_polydata.save(str(vtp_path))
        logger.info("[Save] %s -> %s", artery_name, vtp_path)

    if not all_dfs:
        raise RuntimeError(f"No centerlines extracted for patient {patient_id}")

    df_centerlines = pd.concat(all_dfs, ignore_index=True)

    xlsx_path = DF_DIR / f"df_{patient_id}_{timestamp}.xlsx"
    df_centerlines.to_excel(str(xlsx_path), index=False)
    logger.info("[Save] DataFrame -> %s", xlsx_path)

    elapsed = time.perf_counter() - t_start
    logger.info("Block 1 Execution Time: %.1f seconds", elapsed)
    print(f"\nBlock 1 Execution Time: {elapsed:.1f} seconds")

    return df_centerlines


# ── Standalone execution ──────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    pid = sys.argv[1] if len(sys.argv) > 1 else "Normal_1"
    df = run_block1(patient_id=pid)

    print(f"\nTotal centerline points: {len(df)}")
    print(f"  RCA: {(df['Artery_Type'] == 'RCA').sum()} points")
    print(f"  LCA: {(df['Artery_Type'] == 'LCA').sum()} points")
    print(df.head(10))
