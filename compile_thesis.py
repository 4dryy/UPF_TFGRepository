"""Compile the LaTeX thesis from the repository root."""
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent
thesis_dir = repo_root / "thesis" / "TFG_Latex2526"
script = thesis_dir / "compile_thesis.py"

if not script.is_file():
    sys.stderr.write(f"ERROR: thesis compile script not found at {script}\n")
    sys.exit(1)

result = subprocess.run([sys.executable, str(script)], cwd=thesis_dir)
sys.exit(result.returncode)
