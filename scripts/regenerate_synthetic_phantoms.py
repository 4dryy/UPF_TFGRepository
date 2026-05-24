"""
Regenerate synthetic NRRD phantoms (notebook parity) into data/Synthetic Samples/.

Run from repo root:
    python scripts/regenerate_synthetic_phantoms.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import nrrd

from src.synthetic_profile import (
    SYNTHETIC_DATA_ROOT,
    SYNTHETIC_R_BASE_MM,
    SYNTHETIC_R_MIN_MM,
    SYNTHETIC_Z_END_MM,
    SYNTHETIC_Z_NARROW_HI_MM,
    SYNTHETIC_Z_NARROW_LO_MM,
    SYNTHETIC_Z_NARROW_MID_MM,
    SYNTHETIC_Z_START_MM,
    synthetic_radius_mm,
)

SHAPE = (100, 100, 100)
SPACING_MM = (1.0, 1.0, 1.0)
CENTER_XY = (50, 50)


def _radius_fn_healthy(z: np.ndarray) -> np.ndarray:
    r = np.zeros_like(z, dtype=float)
    in_tube = (z >= SYNTHETIC_Z_START_MM) & (z <= SYNTHETIC_Z_END_MM)
    r[in_tube] = SYNTHETIC_R_BASE_MM
    return r


def _radius_fn_stenosis(z: np.ndarray) -> np.ndarray:
    r = np.zeros_like(z, dtype=float)
    in_tube = (z >= SYNTHETIC_Z_START_MM) & (z <= SYNTHETIC_Z_END_MM)
    r[in_tube] = synthetic_radius_mm(z[in_tube], stenosis=True)
    return r


def build_tube_mask(radius_fn) -> np.ndarray:
    nz, ny, nx = SHAPE
    cx, cy = CENTER_XY
    z_1d = np.arange(nz, dtype=float)
    r_z = radius_fn(z_1d)
    r_start = float(radius_fn(np.array([SYNTHETIC_Z_START_MM]))[0])
    r_end = float(radius_fn(np.array([SYNTHETIC_Z_END_MM]))[0])

    z = z_1d[:, None, None]
    y = np.arange(ny, dtype=float)[None, :, None]
    x = np.arange(nx, dtype=float)[None, None, :]
    dist_xy = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    body = (z >= SYNTHETIC_Z_START_MM) & (z <= SYNTHETIC_Z_END_MM) & (dist_xy <= r_z[:, None, None])
    dist_prox = np.sqrt(dist_xy**2 + (z - SYNTHETIC_Z_START_MM) ** 2)
    dist_dist = np.sqrt(dist_xy**2 + (z - SYNTHETIC_Z_END_MM) ** 2)
    cap_prox = dist_prox <= r_start
    cap_dist = dist_dist <= r_end
    return (body | cap_prox | cap_dist).astype(np.uint8)


def _header() -> dict:
    return {
        "type": "uint8",
        "encoding": "gzip",
        "space": "left-posterior-superior",
        "space directions": [
            [SPACING_MM[0], 0.0, 0.0],
            [0.0, SPACING_MM[1], 0.0],
            [0.0, 0.0, SPACING_MM[2]],
        ],
        "space origin": (0.0, 0.0, 0.0),
        "kinds": ["domain", "domain", "domain"],
    }


def _save(mask_zyx: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nrrd.write(str(path), np.transpose(mask_zyx, (2, 1, 0)), header=_header())
    print(f"Saved {path}  voxels={int(mask_zyx.sum())}")


def main() -> None:
    _save(build_tube_mask(_radius_fn_healthy), SYNTHETIC_DATA_ROOT / "Synthetic_1.nrrd")
    _save(build_tube_mask(_radius_fn_stenosis), SYNTHETIC_DATA_ROOT / "Synthetic_2.nrrd")
    z = np.array([SYNTHETIC_Z_NARROW_LO_MM, SYNTHETIC_Z_NARROW_MID_MM, SYNTHETIC_Z_NARROW_HI_MM])
    print("Stenosis R at Z", z, "→", np.round(synthetic_radius_mm(z, stenosis=True), 4))


if __name__ == "__main__":
    main()
