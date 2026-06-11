"""
SCCT-18 coronary segment atlas (Leipsic et al., J Cardiovasc Comput Tomogr 2014).

Single source of truth for segment IDs, anatomical names, and CAD-RADS 2.0 territory
groupings used across Blocks 1, 3, and the Streamlit viewer. ASOCA and MACS-18 label
volumes share this integer encoding.
"""

from __future__ import annotations

import pandas as pd

# Ostium targets for deterministic label-driven seed selection (Block 1).
TARGET_SEGMENT_BY_ARTERY: dict[str, int] = {"RCA": 1, "LCA": 5}

LEFT_MAIN_SEGMENT_ID = 5
RAMUS_INTERMEDIUS_SEGMENT_ID = 17

# CAD-RADS 2.0 three-vessel rule — Ramus intermedius (17) is excluded.
TERRITORY_SEGMENTS: dict[str, set[int]] = {
    "RCA": {1, 2, 3, 4, 16},
    "LAD": {6, 7, 8, 9, 10},
    "LCX": {11, 12, 13, 14, 15, 18},
}

DEFAULT_SIS_DENOMINATOR = 16
SIS_DENOMINATOR_WITH_RI = 17

_SCCT18_ROWS: list[dict[str, object]] = [
    {
        "Segment_ID": 1,
        "Segment_Name": "Proximal RCA",
        "Definition": (
            "Originates at the right coronary ostium and extends to the origin of the "
            "first major branch, or one half the distance to the acute margin of the heart."
        ),
        "Artery_Type": "RCA",
        "Specific_Artery": "RCA",
    },
    {
        "Segment_ID": 2,
        "Segment_Name": "Mid RCA",
        "Definition": (
            "Extends from the termination of the proximal segment to the anatomical flexure "
            "at the acute margin of the heart."
        ),
        "Artery_Type": "RCA",
        "Specific_Artery": "RCA",
    },
    {
        "Segment_ID": 3,
        "Segment_Name": "Distal RCA",
        "Definition": (
            "Extends from the acute margin of the heart to the origin of the posterior "
            "descending artery."
        ),
        "Artery_Type": "RCA",
        "Specific_Artery": "RCA",
    },
    {
        "Segment_ID": 4,
        "Segment_Name": "Right posterior descending artery (R-PDA)",
        "Definition": (
            "Branches from the distal RCA and courses within the posterior interventricular groove."
        ),
        "Artery_Type": "RCA",
        "Specific_Artery": "RCA",
    },
    {
        "Segment_ID": 16,
        "Segment_Name": "Right posterolateral branch (R-PLB)",
        "Definition": (
            "Branches from the distal RCA posterior to the crux of the heart, supplying the "
            "posterolateral left ventricle."
        ),
        "Artery_Type": "RCA",
        "Specific_Artery": "RCA",
    },
    {
        "Segment_ID": 5,
        "Segment_Name": "Left main",
        "Definition": (
            "Originates at the left coronary ostium and terminates at the bifurcation into the "
            "left anterior descending and left circumflex arteries."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LCA",
    },
    {
        "Segment_ID": 6,
        "Segment_Name": "Proximal LAD",
        "Definition": (
            "Extends from the termination of the left main artery to the origin of the first "
            "major diagonal branch (D1) or the first large septal perforator, whichever is most proximal."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LAD",
    },
    {
        "Segment_ID": 7,
        "Segment_Name": "Mid LAD",
        "Definition": (
            "Extends from the termination of the proximal LAD to one half the remaining distance "
            "to the left ventricular apex."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LAD",
    },
    {
        "Segment_ID": 8,
        "Segment_Name": "Distal LAD",
        "Definition": (
            "Extends from the termination of the mid LAD to the anatomical endpoint at the "
            "left ventricular apex."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LAD",
    },
    {
        "Segment_ID": 9,
        "Segment_Name": "First diagonal (D1)",
        "Definition": "The first major lateral branch originating from the LAD.",
        "Artery_Type": "LCA",
        "Specific_Artery": "LAD",
    },
    {
        "Segment_ID": 10,
        "Segment_Name": "Second diagonal (D2)",
        "Definition": "The second major lateral branch originating from the LAD.",
        "Artery_Type": "LCA",
        "Specific_Artery": "LAD",
    },
    {
        "Segment_ID": 11,
        "Segment_Name": "Proximal LCx",
        "Definition": (
            "Extends from the termination of the left main artery to the origin of the first "
            "obtuse marginal branch (OM1)."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LCX",
    },
    {
        "Segment_ID": 12,
        "Segment_Name": "First obtuse marginal (OM1)",
        "Definition": (
            "The first major lateral branch originating from the LCx, coursing along the obtuse margin."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LCX",
    },
    {
        "Segment_ID": 13,
        "Segment_Name": "Distal LCx",
        "Definition": (
            "Extends from the origin of the OM1 to the termination of the vessel. In left dominant "
            "systems, it extends to the origin of the left posterior descending artery."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LCX",
    },
    {
        "Segment_ID": 14,
        "Segment_Name": "Second obtuse marginal (OM2)",
        "Definition": "The second major lateral branch originating from the LCx.",
        "Artery_Type": "LCA",
        "Specific_Artery": "LCX",
    },
    {
        "Segment_ID": 15,
        "Segment_Name": "Left posterior descending artery (L-PDA)",
        "Definition": (
            "In left dominant or codominant systems, branches from the distal LCx and courses "
            "within the posterior interventricular groove."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LCX",
    },
    {
        "Segment_ID": 18,
        "Segment_Name": "Left posterolateral branch (L-PLB)",
        "Definition": (
            "In left dominant systems, branches from the distal LCx to supply the posterolateral "
            "left ventricle."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "LCX",
    },
    {
        "Segment_ID": 17,
        "Segment_Name": "Ramus intermedius (RI)",
        "Definition": (
            "Present only in the anatomical variant of a left main trifurcation, originating "
            "between the LAD and LCx and coursing laterally."
        ),
        "Artery_Type": "LCA",
        "Specific_Artery": "RI",
    },
]

KNOWN_SCCT18_SEGMENT_IDS: set[int] = {int(row["Segment_ID"]) for row in _SCCT18_ROWS}

# Segments used for CAD-RADS territory / LM checks (excludes optional RI).
KNOWN_CADRADS_SEGMENTS: set[int] = (
    set().union(*TERRITORY_SEGMENTS.values(), {LEFT_MAIN_SEGMENT_ID})
)


def build_scct18_segment_dictionary() -> pd.DataFrame:
    """Return the full SCCT-18 segment table as a ``DataFrame``."""
    return pd.DataFrame(_SCCT18_ROWS).sort_values("Segment_ID").reset_index(drop=True)


def segment_id_to_name(segment_id: int) -> str | None:
    """Lookup anatomical name for a SCCT-18 segment ID, or ``None`` if unknown."""
    for row in _SCCT18_ROWS:
        if int(row["Segment_ID"]) == int(segment_id):
            return str(row["Segment_Name"])
    return None


def segment_name_map() -> dict[int, str]:
    """``{Segment_ID: Segment_Name}`` for UI labels."""
    return {int(row["Segment_ID"]): str(row["Segment_Name"]) for row in _SCCT18_ROWS}


def sis_denominator_for_segment_summary(segment_summary: pd.DataFrame) -> int:
    """SIS atlas denominator: 17 when Ramus intermedius (segment 17) is present, else 16."""
    if segment_summary is None or segment_summary.empty or "Segment_ID" not in segment_summary.columns:
        return DEFAULT_SIS_DENOMINATOR
    present = set(pd.to_numeric(segment_summary["Segment_ID"], errors="coerce").dropna().astype(int))
    if RAMUS_INTERMEDIUS_SEGMENT_ID in present:
        return SIS_DENOMINATOR_WITH_RI
    return DEFAULT_SIS_DENOMINATOR


__all__ = [
    "DEFAULT_SIS_DENOMINATOR",
    "KNOWN_CADRADS_SEGMENTS",
    "KNOWN_SCCT18_SEGMENT_IDS",
    "LEFT_MAIN_SEGMENT_ID",
    "RAMUS_INTERMEDIUS_SEGMENT_ID",
    "SIS_DENOMINATOR_WITH_RI",
    "TARGET_SEGMENT_BY_ARTERY",
    "TERRITORY_SEGMENTS",
    "build_scct18_segment_dictionary",
    "segment_id_to_name",
    "segment_name_map",
    "sis_denominator_for_segment_summary",
]
