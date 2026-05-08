"""
Streamlit entrypoint for Block 4 visualization.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSION_PATH = PROJECT_ROOT / "results" / "current_session.json"

AUTHOR_NAME = "Adrià Cortés Cugat"
DEGREE_NAME = "Mathematical Engineering in Data Science"


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


def main() -> None:
    st.set_page_config(layout="wide")

    patient_id = _load_patient_id()
    if patient_id is None:
        st.warning(
            "No active session found at results/current_session.json. "
            "Run the pipeline first to select a patient."
        )
        patient_id = "Unknown Patient"

    st.title(f"Coronary Analysis: {patient_id}")

    st.write("")
    st.write("")
    st.write("")

    st.markdown("---")
    st.caption(f"Author: {AUTHOR_NAME}")
    st.caption(f"Degree: {DEGREE_NAME}")
    st.caption("Final Degree Project (TFG)")


if __name__ == "__main__":
    main()
