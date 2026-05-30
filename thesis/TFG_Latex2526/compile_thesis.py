import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
main = root / "main.tex"

for i, cmd in enumerate(
    [
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["bibtex", "main"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
    ],
    start=1,
):
    print(f"\n=== Step {i}: {' '.join(cmd)} ===")
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    sys.stdout.write(result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout)
    sys.stderr.write(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
    if result.returncode != 0 and i == 1:
        print(f"Exit code: {result.returncode}")

log = (root / "main.log").read_text(encoding="utf-8", errors="replace") if (root / "main.log").exists() else ""
if "Output written on main.pdf" in log:
    print("\nSUCCESS: main.pdf generated")
else:
    print("\nCheck main.log for errors")
    for line in log.splitlines():
        if line.startswith("!") or "Error" in line:
            print(line)
