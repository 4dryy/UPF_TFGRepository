"""
Block 1 — Hybrid centerline extraction with branch packaging.

For one patient mask (.nrrd), this block:
- separates RCA/LCA,
- runs scout-based ostium/target selection + VMTK centerlines,
- classifies points with topology-based PointType,
- splits centerline into ostium->endpoint branch paths,
- exports outputs in the same structure used in the notebook.
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv
import scipy.ndimage as ndi
from skimage.morphology import skeletonize
from src.pipeline_log import configure_logging, footer_block, phase, short_path, sub
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


def _sample_numeric_id(patient_id: str) -> int:
    tail = patient_id.split("_")[-1]
    return int(tail) if tail.isdigit() else -1


def _find_skeleton_endpoints(skeleton: np.ndarray) -> np.ndarray:
    kernel = np.ones((3, 3, 3), dtype=int)
    kernel[1, 1, 1] = 0
    neighbor_count = ndi.convolve(skeleton.astype(int), kernel, mode="constant", cval=0)
    endpoint_mask = (skeleton > 0) & (neighbor_count == 1)
    return np.argwhere(endpoint_mask)


def _identify_ostium(
    endpoints_zyx: np.ndarray,
    skeleton: np.ndarray,
    binary_mask: np.ndarray,
    edt_weight: float = 0.35,
    centroid_weight: float = 0.15,
    caliber_weight: float = 0.30,
    calib_steps: int = 10,
) -> tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Robust ostium selection combining local and global skeleton cues."""
    dist_transform = ndi.distance_transform_edt(binary_mask)
    dists_edt = dist_transform[
        endpoints_zyx[:, 0], endpoints_zyx[:, 1], endpoints_zyx[:, 2]
    ].astype(float)

    sk = np.asarray(skeleton > 0)
    sk_coords = np.argwhere(sk)
    node_of = {tuple(c): i for i, c in enumerate(sk_coords)}
    endpoint_nodes = np.array(
        [node_of.get((int(p[0]), int(p[1]), int(p[2])), -1) for p in endpoints_zyx],
        dtype=int,
    )

    if np.any(endpoint_nodes < 0) or len(sk_coords) == 0:
        total_geo = np.zeros_like(dists_edt)
        caliber_sum = dists_edt.copy()
        score = dists_edt.copy()
        return int(np.argmax(score)), dists_edt, total_geo, caliber_sum, score

    from heapq import heappop, heappush

    neigh = []
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dz == 0 and dy == 0 and dx == 0:
                    continue
                w = float(np.sqrt(dx * dx + dy * dy + dz * dz))
                neigh.append((dz, dy, dx, w))

    adjacency: list[set[int]] = [set() for _ in range(len(sk_coords))]
    for u, (z, y, x) in enumerate(sk_coords):
        for dz, dy, dx, _ in neigh:
            key = (int(z + dz), int(y + dy), int(x + dx))
            v = node_of.get(key)
            if v is None or v == u:
                continue
            adjacency[u].add(int(v))

    def dijkstra_from(src_idx: int) -> np.ndarray:
        dist = np.full(len(sk_coords), np.inf, dtype=float)
        dist[src_idx] = 0.0
        pq = [(0.0, int(src_idx))]
        while pq:
            d, u = heappop(pq)
            if d > dist[u]:
                continue
            z, y, x = sk_coords[u]
            for dz, dy, dx, w in neigh:
                key = (int(z + dz), int(y + dy), int(x + dx))
                v = node_of.get(key)
                if v is None:
                    continue
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heappush(pq, (nd, int(v)))
        return dist

    def local_caliber_integral(start_node: int, max_steps: int) -> float:
        prev = -1
        cur = int(start_node)
        total = 0.0
        for _ in range(max(1, int(max_steps))):
            z, y, x = sk_coords[cur]
            edt_here = float(dist_transform[int(z), int(y), int(x)])
            total += float(np.pi) * edt_here * edt_here

            next_nodes = [v for v in adjacency[cur] if v != prev]
            if len(next_nodes) != 1:
                break
            nxt = int(next_nodes[0])
            prev, cur = cur, nxt
        return float(total)

    m = len(endpoint_nodes)
    pairwise = np.full((m, m), np.inf, dtype=float)
    for i in range(m):
        dist_all = dijkstra_from(int(endpoint_nodes[i]))
        pairwise[i, :] = dist_all[endpoint_nodes]

    total_geo = np.sum(pairwise, axis=1)
    caliber_sum = np.array(
        [local_caliber_integral(int(node), int(calib_steps)) for node in endpoint_nodes],
        dtype=float,
    )

    def _z(v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=float)
        return (v - np.mean(v)) / (np.std(v) + 1e-8)

    mask_pts = np.argwhere(np.asarray(binary_mask) > 0)
    if len(mask_pts) > 0:
        centroid_zyx = mask_pts.mean(axis=0)
        d_centroid = np.linalg.norm(
            endpoints_zyx.astype(float) - centroid_zyx.astype(float), axis=1
        )
    else:
        d_centroid = np.zeros(len(endpoints_zyx), dtype=float)

    z_edt = _z(dists_edt)
    z_geo = _z(total_geo)
    z_centroid = _z(d_centroid)
    z_caliber = _z(caliber_sum)

    w_edt = float(np.clip(edt_weight, 0.0, 1.0))
    w_ctr = float(np.clip(centroid_weight, 0.0, 1.0))
    w_cal = float(np.clip(caliber_weight, 0.0, 1.0))
    w_geo = max(0.0, 1.0 - w_edt - w_ctr - w_cal)

    score = w_edt * z_edt - w_geo * z_geo - w_ctr * z_centroid + w_cal * z_caliber
    ostium_idx = int(np.argmax(score))
    return ostium_idx, dists_edt, total_geo, caliber_sum, score


def _voxel_to_physical(coords_zyx: np.ndarray, origin: np.ndarray, spacing: np.ndarray) -> np.ndarray:
    phys_x = origin[0] + coords_zyx[:, 2] * spacing[0]
    phys_y = origin[1] + coords_zyx[:, 1] * spacing[1]
    phys_z = origin[2] + coords_zyx[:, 0] * spacing[2]
    return np.column_stack([phys_x, phys_y, phys_z])


def _numpy_to_vtk_image(array_zyx: np.ndarray, spacing: np.ndarray, origin: np.ndarray) -> vtkImageData:
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


def _snap_seed_to_surface(mesh: pv.PolyData, point: np.ndarray, inward_fraction: float = 0.3) -> list[float]:
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
        boundary_edges=False, non_manifold_edges=False, feature_edges=False, manifold_edges=True,
    )
    if edges.n_points > 1:
        avg_edge_len = np.mean(np.linalg.norm(np.diff(edges.points[:100], axis=0), axis=1))
    else:
        avg_edge_len = 0.2

    to_center = np.array(point, dtype=float) - surface_pt
    inward_normal = normal if np.dot(to_center, normal) > 0 else -normal
    nudged = surface_pt + inward_fraction * avg_edge_len * inward_normal
    return mesh.points[mesh.find_closest_point(nudged)].tolist()


def _edge_topology_from_polydata(
    poly: pv.PolyData,
    tol_mm: float = 0.05,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pts_xyz = np.asarray(poly.points, dtype=np.float64)
    n_pts = len(pts_xyz)
    if n_pts == 0:
        z = np.zeros(0, dtype=np.int32)
        return z, z, z

    scale = max(float(tol_mm), 1e-6)
    voxel = np.round(pts_xyz / scale).astype(np.int64)

    key_to_node: dict[tuple[int, int, int], int] = {}
    point_to_node = np.empty(n_pts, dtype=np.int32)
    node_count = 0
    for i in range(n_pts):
        key = (int(voxel[i, 0]), int(voxel[i, 1]), int(voxel[i, 2]))
        node = key_to_node.get(key)
        if node is None:
            node = node_count
            key_to_node[key] = node
            node_count += 1
        point_to_node[i] = node

    adjacency = [set() for _ in range(node_count)]
    lines_flat = np.asarray(poly.lines, dtype=np.int64)
    idx = 0
    while idx < len(lines_flat):
        seg_len = int(lines_flat[idx])
        seg_pts = lines_flat[idx + 1 : idx + 1 + seg_len]
        for k in range(len(seg_pts) - 1):
            a = int(seg_pts[k])
            b = int(seg_pts[k + 1])
            na = int(point_to_node[a])
            nb = int(point_to_node[b])
            if na == nb:
                continue
            adjacency[na].add(nb)
            adjacency[nb].add(na)
        idx += seg_len + 1

    node_degree = np.array([len(neigh) for neigh in adjacency], dtype=np.int32)
    point_degree = node_degree[point_to_node]
    return point_degree, point_to_node, node_degree


def _point_types_from_topology(
    point_degree: np.ndarray,
    point_to_node: np.ndarray,
    node_degree: np.ndarray,
    ostium_idx: int,
    points_xyz: np.ndarray,
    radii_mm: np.ndarray | None = None,
    bif_merge_mm: float | None = None,
) -> list[str]:
    n = len(point_degree)
    out = np.full(n, "Standard", dtype=object)
    out[point_degree == 0] = "Isolated"

    end_mask = point_degree == 1
    out[end_mask] = "Endpoint"
    if 0 <= int(ostium_idx) < n:
        out[int(ostium_idx)] = "Ostium"

    bif_nodes = np.where(node_degree > 2)[0]
    cand_idx: list[int] = []
    cand_score: list[float] = []
    radii = np.asarray(radii_mm, dtype=float).ravel() if radii_mm is not None else None

    for node_id in bif_nodes:
        idxs = np.where(point_to_node == node_id)[0]
        if len(idxs) == 0:
            continue
        centroid = points_xyz[idxs].mean(axis=0)
        rep = int(idxs[np.argmin(np.linalg.norm(points_xyz[idxs] - centroid, axis=1))])
        r = float(radii[rep]) if radii is not None and rep < len(radii) else 0.0
        cand_idx.append(rep)
        cand_score.append(float(node_degree[node_id]) + 0.01 * r)

    if len(cand_idx) == 0:
        return out.tolist()

    if bif_merge_mm is None:
        d = np.linalg.norm(np.diff(points_xyz, axis=0), axis=1)
        d = d[np.isfinite(d) & (d > 0)]
        step = float(np.median(d)) if len(d) else 0.3
        bif_merge_mm = float(np.clip(2.0 * step, 0.4, 1.5))

    order = np.argsort(-np.asarray(cand_score, dtype=float))
    kept: list[int] = []
    for oi in order:
        i = cand_idx[int(oi)]
        pi = points_xyz[i]
        if any(float(np.linalg.norm(pi - points_xyz[j])) <= float(bif_merge_mm) for j in kept):
            continue
        kept.append(i)

    for rep in kept:
        if out[rep] != "Ostium":
            out[rep] = "Bifurcation"

    return out.tolist()


def _split_centerline_paths(
    centerlines: pv.PolyData,
    sample_id: int,
    artery_name: str,
    point_types: list[str] | np.ndarray,
    ostium_point_mm: np.ndarray,
    min_points: int = 20,
    ostium_start_tol_mm: float = 4.0,
) -> tuple[list[dict], dict]:
    cl_points = np.asarray(centerlines.points)
    cl_radii = np.asarray(centerlines.point_data["MaximumInscribedSphereRadius"])
    pt_types = np.asarray(point_types, dtype=object)
    ost = np.asarray(ostium_point_mm, dtype=float)

    branches: list[dict] = []
    dropped = {"too_short": 0, "far_from_ostium": 0, "bad_terminal": 0}

    lines_flat = np.asarray(centerlines.lines, dtype=np.int64)
    idx = 0
    branch_num = 1
    while idx < len(lines_flat):
        npts = int(lines_flat[idx])
        seg_ids = np.asarray(lines_flat[idx + 1 : idx + 1 + npts], dtype=np.int64)
        idx += npts + 1
        if len(seg_ids) < 2:
            continue

        seg_pts_raw = cl_points[seg_ids]
        d0 = float(np.linalg.norm(seg_pts_raw[0] - ost))
        d1 = float(np.linalg.norm(seg_pts_raw[-1] - ost))
        if d1 < d0:
            seg_ids = seg_ids[::-1]
            seg_pts_raw = seg_pts_raw[::-1]
            d0, d1 = d1, d0

        seg_pts = cl_points[seg_ids]
        seg_rad = cl_radii[seg_ids]
        seg_ptt_global = pt_types[seg_ids]

        if len(seg_ids) < int(min_points):
            dropped["too_short"] += 1
            continue
        if d0 > float(ostium_start_tol_mm):
            dropped["far_from_ostium"] += 1
            continue
        if str(seg_ptt_global[-1]) != "Endpoint":
            dropped["bad_terminal"] += 1
            continue

        # Branch-local semantic labels:
        # force start/end to represent ostium->endpoint path intent, even when
        # sampled polyline endpoints are near (but not exactly at) global ostium point.
        seg_ptt = np.asarray(seg_ptt_global, dtype=object).copy()
        if len(seg_ptt) > 0:
            seg_ptt[0] = "Ostium"
            seg_ptt[-1] = "Endpoint"

        branch_id = f"{artery_name}_B{branch_num:02d}"
        branch_num += 1

        branch_poly = pv.lines_from_points(seg_pts, close=False)
        branch_poly.point_data["MaximumInscribedSphereRadius"] = seg_rad

        df_branch = pd.DataFrame(
            {
                "Sample_ID": sample_id,
                "Artery_Type": artery_name,
                "Branch_ID": branch_id,
                "Path_Point_Index": np.arange(len(seg_ids), dtype=int),
                "Px": seg_pts[:, 0],
                "Py": seg_pts[:, 1],
                "Pz": seg_pts[:, 2],
                "Radius": seg_rad,
                "PointType": seg_ptt,
            }
        )
        branches.append({"branch_id": branch_id, "poly": branch_poly, "df": df_branch})

    return branches, dropped


def _load_and_separate_mask(
    nrrd_path: Path,
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    reader = vmtkscripts.vmtkImageReader()
    reader.InputFileName = str(nrrd_path)
    reader.Execute()

    vtk_image = reader.Image
    spacing = np.array(vtk_image.GetSpacing())
    origin = np.array(vtk_image.GetOrigin())
    dims = vtk_image.GetDimensions()
    vtk_scalars = vtk_image.GetPointData().GetScalars()
    mask = vtk_to_numpy(vtk_scalars).reshape(dims[2], dims[1], dims[0]).astype(np.uint8)

    labeled, num_components = ndi.label(mask)
    if num_components < 2:
        raise RuntimeError(f"Expected at least 2 connected components, found {num_components}")

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
    return artery_arrays, spacing, origin


load_and_separate_mask = _load_and_separate_mask


def _process_artery(
    artery_name: str,
    artery_mask: np.ndarray,
    spacing: np.ndarray,
    origin: np.ndarray,
    sample_id: int,
    source_zyx: np.ndarray,
    targets_zyx: np.ndarray,
) -> dict | None:
    source_phys = _voxel_to_physical(source_zyx, origin, spacing)
    targets_phys = _voxel_to_physical(targets_zyx, origin, spacing)

    vtk_artery = _numpy_to_vtk_image(artery_mask, spacing, origin)
    mc = vmtkscripts.vmtkMarchingCubes()
    mc.Image = vtk_artery
    mc.Level = 0.5
    mc.Execute()

    smoother = vmtkscripts.vmtkSurfaceSmoothing()
    smoother.Surface = mc.Surface
    smoother.NumberOfIterations = 20
    smoother.PassBand = 0.1
    smoother.Execute()

    surface_smooth = smoother.Surface
    mesh_smooth = pv.wrap(surface_smooth)
    source_flat = _snap_seed_to_surface(mesh_smooth, source_phys[0])
    targets_flat: list[float] = []
    for t in targets_phys:
        targets_flat.extend(_snap_seed_to_surface(mesh_smooth, t))

    cl = vmtkscripts.vmtkCenterlines()
    cl.Surface = surface_smooth
    cl.SeedSelectorName = "pointlist"
    cl.SourcePoints = source_flat
    cl.TargetPoints = targets_flat
    cl.AppendEndPoints = 1
    cl.Execute()

    centerlines = pv.wrap(cl.Centerlines)
    cl_points = centerlines.points
    cl_radii = centerlines.point_data["MaximumInscribedSphereRadius"]

    point_degree, point_to_node, node_degree = _edge_topology_from_polydata(centerlines, tol_mm=0.05)
    ostium_idx = int(np.linalg.norm(cl_points - np.asarray(source_phys[0], dtype=float), axis=1).argmin())
    point_types = _point_types_from_topology(
        point_degree,
        point_to_node,
        node_degree,
        ostium_idx,
        cl_points,
        radii_mm=cl_radii,
        bif_merge_mm=None,
    )

    df_artery = pd.DataFrame(
        {
            "Sample_ID": sample_id,
            "Artery_Type": artery_name,
            "Px": cl_points[:, 0],
            "Py": cl_points[:, 1],
            "Pz": cl_points[:, 2],
            "Radius": cl_radii,
            "PointType": point_types,
        }
    )

    branch_items, dropped_stats = _split_centerline_paths(
        centerlines,
        sample_id=sample_id,
        artery_name=artery_name,
        point_types=point_types,
        ostium_point_mm=np.asarray(source_phys[0], dtype=float),
        min_points=20,
        ostium_start_tol_mm=4.0,
    )

    sub(
        logger,
        "%s centerline: %d pts → %d branches (drop short=%d far=%d bad_term=%d)",
        artery_name,
        len(cl_points),
        len(branch_items),
        dropped_stats["too_short"],
        dropped_stats["far_from_ostium"],
        dropped_stats["bad_terminal"],
    )

    return {
        "centerline_poly": centerlines,
        "mesh_smooth": mesh_smooth,
        "df_artery": df_artery,
        "source_phys": np.asarray(source_phys[0], dtype=float),
        "branches": branch_items,
    }


def _export_branch_qc_figures(sample_dir: Path, sample_name: str, artery_outputs: dict[str, dict]) -> int:
    fig_dir = sample_dir / "branches" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for artery_name, info in artery_outputs.items():
        vessel_mesh = info.get("mesh_smooth")
        if vessel_mesh is None:
            continue

        for b in info["branches"]:
            branch_id = b["branch_id"]
            pts = np.asarray(b["poly"].points)
            if len(pts) < 2:
                continue

            ost_pt = pts[0]
            tip_pt = pts[-1]
            png_path = fig_dir / f"fig_{branch_id}_{sample_name}.png"

            pl = pv.Plotter(off_screen=True, window_size=(1600, 1200))
            pl.set_background("white")
            pl.add_mesh(vessel_mesh, color="lightgray", opacity=0.20, smooth_shading=True)
            pl.add_mesh(b["poly"], color="black", line_width=7)
            pl.add_mesh(pv.PolyData(ost_pt), color="red", point_size=22, render_points_as_spheres=True)
            pl.add_mesh(pv.PolyData(tip_pt), color="blue", point_size=22, render_points_as_spheres=True)
            pl.add_axes()
            pl.show(screenshot=str(png_path), auto_close=True)
            saved += 1

    return saved


def _export_centerline_tree_figure(
    sample_dir: Path, sample_name: str, artery_outputs: dict[str, dict]
) -> dict[str, int | Path] | None:
    """Save one full coronary centerline tree figure with key points highlighted."""
    if not artery_outputs:
        return None

    png_path = sample_dir / f"fig_centerline_tree_{sample_name}.png"
    pl = pv.Plotter(off_screen=True, window_size=(1800, 1300))
    pl.set_background("white")

    n_lines = 0
    n_ostium = 0
    n_endpoints = 0

    for info in artery_outputs.values():
        centerline_poly = info.get("centerline_poly")
        df_artery = info.get("df_artery")
        if centerline_poly is None or df_artery is None or len(df_artery) == 0:
            continue

        pl.add_mesh(centerline_poly, color="black", line_width=4)
        n_lines += 1

        pts = df_artery[["Px", "Py", "Pz"]].to_numpy(dtype=float)
        ptype = df_artery["PointType"].astype(str).to_numpy()

        ost_mask = ptype == "Ostium"
        end_mask = ptype == "Endpoint"

        if np.any(ost_mask):
            pl.add_mesh(
                pv.PolyData(pts[ost_mask]),
                color="red",
                point_size=24,
                render_points_as_spheres=True,
                label="Ostium",
            )
            n_ostium += int(np.count_nonzero(ost_mask))

        if np.any(end_mask):
            pl.add_mesh(
                pv.PolyData(pts[end_mask]),
                color="blue",
                point_size=18,
                render_points_as_spheres=True,
                label="Endpoint",
            )
            n_endpoints += int(np.count_nonzero(end_mask))

    if n_lines == 0:
        pl.close()
        return None

    pl.add_axes()
    pl.add_legend(size=(0.2, 0.12), bcolor="white", border=True)
    pl.show(screenshot=str(png_path), auto_close=True)
    return {
        "lines": n_lines,
        "ostia": n_ostium,
        "endpoints": n_endpoints,
        "path": png_path,
    }


def run_block1(patient_id: str, nrrd_path: Path | None = None) -> pd.DataFrame:
    t_start = time.perf_counter()
    sample_name = patient_id
    sample_id = _sample_numeric_id(patient_id)
    phase(logger, "1", "Centerlines · branching · export")

    if nrrd_path is None:
        nrrd_path = DATA_ROOT / "ASOCA Normal" / "Annotations" / f"{patient_id}.nrrd"
    if not nrrd_path.exists():
        raise FileNotFoundError(f"Mask not found: {nrrd_path}")

    artery_arrays, spacing, origin = _load_and_separate_mask(nrrd_path)

    scout_cache: dict[str, dict] = {}
    for artery_name, artery_mask in artery_arrays.items():
        skeleton = skeletonize(artery_mask)
        endpoints_zyx = _find_skeleton_endpoints(skeleton)
        if len(endpoints_zyx) < 2:
            logger.warning("[%s] Fewer than 2 endpoints — skipping.", artery_name)
            continue

        ost0_idx, d_edt, d_geo, d_calib, score = _identify_ostium(
            endpoints_zyx,
            skeleton,
            artery_mask,
            edt_weight=0.35,
            centroid_weight=0.15,
            caliber_weight=0.30,
            calib_steps=10,
        )
        rank = np.argsort(score)[::-1]
        topk = rank[: min(4, len(rank))]
        endpoints_phys = _voxel_to_physical(endpoints_zyx, origin, spacing)

        scout_cache[artery_name] = {
            "artery_mask": artery_mask,
            "endpoints_zyx": endpoints_zyx,
            "endpoints_phys": endpoints_phys,
            "dists_edt": d_edt,
            "total_geo": d_geo,
            "caliber_sum": d_calib,
            "ost_score": score,
            "topk": topk,
            "ostium_idx_default": int(ost0_idx),
        }

    if not scout_cache:
        raise RuntimeError(f"No valid artery endpoints found for {patient_id}")

    ostium_choice: dict[str, int] = {k: int(v["ostium_idx_default"]) for k, v in scout_cache.items()}
    if ("RCA" in scout_cache) and ("LCA" in scout_cache):
        rc = scout_cache["RCA"]
        lc = scout_cache["LCA"]
        s_r = (rc["ost_score"] - np.mean(rc["ost_score"])) / (np.std(rc["ost_score"]) + 1e-8)
        s_l = (lc["ost_score"] - np.mean(lc["ost_score"])) / (np.std(lc["ost_score"]) + 1e-8)

        pairs: list[tuple[int, int, float]] = []
        for i in rc["topk"]:
            for j in lc["topk"]:
                d = float(np.linalg.norm(rc["endpoints_phys"][i] - lc["endpoints_phys"][j]))
                pairs.append((int(i), int(j), d))

        d_all = np.array([p[2] for p in pairs], dtype=float)
        d_z = (d_all - np.mean(d_all)) / (np.std(d_all) + 1e-8)
        best_obj = np.inf
        best_idx: tuple[int, int] | None = None
        for k, (i, j, _) in enumerate(pairs):
            obj = 1.00 * d_z[k] - 0.60 * (s_r[i] + s_l[j])
            if obj < best_obj:
                best_obj = obj
                best_idx = (int(i), int(j))
        if best_idx is not None:
            ostium_choice["RCA"], ostium_choice["LCA"] = best_idx

    all_centerlines_data: list[pd.DataFrame] = []
    artery_outputs: dict[str, dict] = {}
    for artery_name, cache in scout_cache.items():
        endpoints_zyx = cache["endpoints_zyx"]
        ostium_idx = int(ostium_choice.get(artery_name, cache["ostium_idx_default"]))

        source_zyx = endpoints_zyx[ostium_idx : ostium_idx + 1]
        target_mask = np.ones(len(endpoints_zyx), dtype=bool)
        target_mask[ostium_idx] = False
        targets_zyx = endpoints_zyx[target_mask]

        sub(
            logger,
            "%s ostium #%d | score=%.2f | EDT=%.2fm geo=%.1f cal=%.1f",
            artery_name,
            ostium_idx,
            float(cache["ost_score"][ostium_idx]),
            float(cache["dists_edt"][ostium_idx]),
            float(cache["total_geo"][ostium_idx]),
            float(cache["caliber_sum"][ostium_idx]),
        )

        out = _process_artery(
            artery_name=artery_name,
            artery_mask=cache["artery_mask"],
            spacing=spacing,
            origin=origin,
            sample_id=sample_id,
            source_zyx=source_zyx,
            targets_zyx=targets_zyx,
        )
        if out is None:
            continue
        artery_outputs[artery_name] = out
        all_centerlines_data.append(out["df_artery"])

    if not all_centerlines_data:
        raise RuntimeError(f"No centerlines extracted for patient {patient_id}")

    df_centerlines = pd.concat(all_centerlines_data, ignore_index=True)
    if "PointType" in df_centerlines.columns:
        vc = df_centerlines["PointType"].value_counts().sort_index()
        sub(logger, "PointType: %s", ", ".join(f"{k}={int(v)}" for k, v in vc.items()))

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    sample_dir = RESULTS_ROOT / sample_name
    if sample_dir.exists():
        shutil.rmtree(sample_dir)
    branches_center_dir = sample_dir / "branches" / "centerlines"
    branches_df_dir = sample_dir / "branches" / "dataframes"
    for d in (sample_dir, branches_center_dir, branches_df_dir):
        d.mkdir(parents=True, exist_ok=True)

    global_xlsx = sample_dir / f"dataset_global_{sample_name}.xlsx"
    df_centerlines.to_excel(global_xlsx, index=False)

    for artery_name, info in artery_outputs.items():
        centerline_path = sample_dir / f"centerline_{artery_name}.vtp"
        surface_path = sample_dir / f"surface_{artery_name}.vtp"
        artery_df_xlsx = sample_dir / f"dataset_{artery_name}_{sample_name}.xlsx"
        info["centerline_poly"].save(str(centerline_path))
        info["mesh_smooth"].save(str(surface_path))
        info["df_artery"].to_excel(artery_df_xlsx, index=False)

        for b in info["branches"]:
            branch_id = b["branch_id"]
            branch_vtp = branches_center_dir / f"centerline_{branch_id}_{sample_name}.vtp"
            branch_xlsx = branches_df_dir / f"dataset_{branch_id}_{sample_name}.xlsx"
            b["poly"].save(str(branch_vtp))
            b["df"].to_excel(branch_xlsx, index=False)

    n_qc_png = _export_branch_qc_figures(sample_dir, sample_name, artery_outputs)
    tree_meta = _export_centerline_tree_figure(sample_dir, sample_name, artery_outputs)
    fig_bits: list[str] = []
    if tree_meta is not None:
        fig_bits.append(
            f"tree({tree_meta['lines']}L·{tree_meta['ostia']}O·{tree_meta['endpoints']}E)"
        )
    fig_bits.append(f"branch_QC×{n_qc_png}")
    sub(logger, "Figures: %s → %s", " · ".join(fig_bits), short_path(sample_dir))

    elapsed = time.perf_counter() - t_start
    n_branches = sum(len(v["branches"]) for v in artery_outputs.values())
    rca_n = int((df_centerlines["Artery_Type"] == "RCA").sum()) if "Artery_Type" in df_centerlines.columns else 0
    lca_n = int((df_centerlines["Artery_Type"] == "LCA").sum()) if "Artery_Type" in df_centerlines.columns else 0
    footer_block(
        logger,
        block_id="1",
        title="centerlines",
        seconds=elapsed,
        parts=[
            f"{len(df_centerlines)} pts",
            f"RCA {rca_n} · LCA {lca_n}",
            f"{n_branches} branches",
            f"out {short_path(sample_dir)}",
        ],
    )
    return df_centerlines


if __name__ == "__main__":
    configure_logging()
    pid = sys.argv[1] if len(sys.argv) > 1 else "Normal_1"
    out_df = run_block1(patient_id=pid)
    print(f"\nTotal centerline points: {len(out_df)}")
    if "Artery_Type" in out_df.columns:
        print(f"  RCA: {(out_df['Artery_Type'] == 'RCA').sum()} points")
        print(f"  LCA: {(out_df['Artery_Type'] == 'LCA').sum()} points")
