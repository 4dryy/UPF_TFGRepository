"""
Block 4 - Visualization launcher.

Stores the current pipeline session and starts the Streamlit dashboard.
"""

from __future__ import annotations

import json
import importlib.util
import logging
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from src.pipeline_log import phase, sub

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = PROJECT_ROOT / "results"
SESSION_PATH = RESULTS_ROOT / "current_session.json"
STREAMLIT_APP_PATH = PROJECT_ROOT / "src" / "viewer" / "app.py"
STREAMLIT_HOST = "127.0.0.1"
STREAMLIT_PORT = 8501
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"


def _is_port_open(host: str, port: int, timeout_s: float = 0.25) -> bool:
    """Return True if a TCP server is accepting connections on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex((host, port)) == 0


def run_block4(patient_id: str) -> None:
    """Persist current patient context and launch Streamlit in background."""
    phase(logger, "4", "Visualization dashboard")

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    session_payload = {"patient_id": patient_id}
    SESSION_PATH.write_text(json.dumps(session_payload, indent=2), encoding="utf-8")
    sub(logger, "Session file updated: %s", SESSION_PATH)

    if importlib.util.find_spec("streamlit") is None:
        sub(
            logger,
            "Streamlit is not installed in this Python env. Install with: %s -m pip install streamlit",
            sys.executable,
        )
        return

    if _is_port_open(STREAMLIT_HOST, STREAMLIT_PORT):
        sub(
            logger,
            "Streamlit already running on %s (same process keeps cached Python imports). "
            "Use 'Always rerun' / refresh the page after editing viewer code, or stop the server "
            "on port %s and run the pipeline again to guarantee the latest dashboard code.",
            STREAMLIT_URL,
            STREAMLIT_PORT,
        )
        webbrowser.open_new_tab(STREAMLIT_URL)
        sub(logger, "Opening dashboard URL: %s", STREAMLIT_URL)
        return

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(STREAMLIT_APP_PATH),
        "--browser.gatherUsageStats",
        "false",
        "--server.headless",
        "true",
        "--server.address",
        STREAMLIT_HOST,
        "--server.port",
        str(STREAMLIT_PORT),
    ]
    streamlit_env = os.environ.copy()
    streamlit_env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    popen_kwargs: dict[str, object] = {
        "cwd": PROJECT_ROOT,
        "env": streamlit_env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        popen_kwargs["start_new_session"] = True

    subprocess.Popen(cmd, **popen_kwargs)
    sub(logger, "Launching Streamlit app: %s", " ".join(cmd))

    for _ in range(30):
        if _is_port_open(STREAMLIT_HOST, STREAMLIT_PORT):
            webbrowser.open_new_tab(STREAMLIT_URL)
            sub(logger, "Opening dashboard URL: %s", STREAMLIT_URL)
            return
        time.sleep(0.25)

    sub(
        logger,
        "Streamlit was launched but did not become reachable at %s yet. Open it manually in a few seconds.",
        STREAMLIT_URL,
    )
