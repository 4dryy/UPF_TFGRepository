import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent


def auxiliary_files_look_corrupt() -> bool:
    """Detect aux files truncated by an interrupted pdflatex run (causes ?? refs)."""
    aux = root / "main.aux"
    if not aux.exists():
        return False
    text = aux.read_text(encoding="utf-8", errors="replace")
    # A successful thesis run records many labels and citation keys.
    return len(text) < 2000 or "\\newlabel" not in text


def remove_stale_auxiliary_files() -> None:
    for name in ("main.aux", "main.out"):
        path = root / name
        if path.exists():
            path.unlink()
            print(f"Removed stale {name}")


if auxiliary_files_look_corrupt():
    print("Stale or truncated auxiliary files detected; cleaning before build.")
    remove_stale_auxiliary_files()

commands = [
    ["pdflatex", "-interaction=nonstopmode", "main.tex"],
    ["bibtex", "main"],
    ["pdflatex", "-interaction=nonstopmode", "main.tex"],
    ["pdflatex", "-interaction=nonstopmode", "main.tex"],
    ["pdflatex", "-interaction=nonstopmode", "main.tex"],
]

for i, cmd in enumerate(commands, start=1):
    print(f"\n=== Step {i}: {' '.join(cmd)} ===")
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    tail = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
    sys.stdout.write(tail)
    if result.stderr:
        sys.stderr.write(result.stderr[-1000:])
    if result.returncode != 0:
        print(f"Exit code: {result.returncode}")
        sys.exit(result.returncode)

log_path = root / "main.log"
log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
if "Output written on main.pdf" in log:
    print("\nSUCCESS: main.pdf generated")
    undefined_cites = [line for line in log.splitlines() if "Citation" in line and "undefined" in line]
    undefined_refs = [line for line in log.splitlines() if "Reference" in line and "undefined" in line]
    if undefined_cites:
        print(f"WARNING: {len(undefined_cites)} undefined citation(s) remain")
        for line in undefined_cites[:5]:
            print(line)
    else:
        print("All citations resolved.")
    if undefined_refs:
        print(f"WARNING: {len(undefined_refs)} undefined reference(s) remain")
        for line in undefined_refs[:5]:
            print(line)
    else:
        print("All cross-references resolved.")
else:
    print("\nCheck main.log for errors")
    for line in log.splitlines():
        if line.startswith("!") or "Error" in line:
            print(line)
