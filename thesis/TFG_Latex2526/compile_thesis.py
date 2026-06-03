import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
build_dir = root / "build"
build_dir.mkdir(exist_ok=True)


def auxiliary_files_look_corrupt() -> bool:
    aux = build_dir / "main.aux"
    if not aux.exists():
        return False
    text = aux.read_text(encoding="utf-8", errors="replace")
    return len(text) < 2000 or "\\newlabel" not in text


def remove_stale_auxiliary_files() -> None:
    for name in ("main.aux", "main.out"):
        path = build_dir / name
        if path.exists():
            path.unlink()
            print(f"Removed stale build/{name}")


def read_log() -> str:
    log_path = build_dir / "main.log"
    return log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""


def report_build_status() -> bool:
    log = read_log()
    pdf_path = build_dir / "main.pdf"

    if "Output written on" not in log or not pdf_path.exists():
        print("\nCheck build/main.log for errors")
        for line in log.splitlines():
            if line.startswith("!") or "Error" in line:
                print(line)
        return False

    print(f"\nSUCCESS: {pdf_path} generated")
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
    return not undefined_cites and not undefined_refs


def copy_pdf_to_root() -> None:
    source = build_dir / "main.pdf"
    target = root / "main.pdf"
    if not source.exists():
        return
    try:
        shutil.copy2(source, target)
        print(f"Updated {target}")
    except OSError:
        print(
            f"Could not overwrite {target} because it is open in your PDF viewer.\n"
            f"Read the fresh PDF from: {source}",
            file=sys.stderr,
        )


if auxiliary_files_look_corrupt():
    print("Stale or truncated auxiliary files detected; cleaning build/ before compile.")
    remove_stale_auxiliary_files()

commands = [
    ["pdflatex", "-interaction=nonstopmode", "-output-directory=build", "main.tex"],
    ["bibtex", "build/main"],
    ["pdflatex", "-interaction=nonstopmode", "-output-directory=build", "main.tex"],
    ["pdflatex", "-interaction=nonstopmode", "-output-directory=build", "main.tex"],
]

print("Compiling into build/ (safe even when main.pdf is open in the IDE).")

for i, cmd in enumerate(commands, start=1):
    print(f"\n=== Step {i}: {' '.join(cmd)} ===")
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    tail = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
    sys.stdout.write(tail)
    if result.stderr:
        sys.stderr.write(result.stderr[-1000:])
    if result.returncode != 0:
        print(f"Exit code: {result.returncode}")
        if i == 1:
            print(
                "\nNote: undefined citation/reference warnings on Step 1 are normal "
                "before bibtex and later pdflatex passes.",
                file=sys.stderr,
            )
        if report_build_status():
            copy_pdf_to_root()
            sys.exit(0)
        sys.exit(result.returncode)

    if cmd[0] == "bibtex":
        generated_bbl = build_dir / "main.bbl"
        if generated_bbl.exists():
            shutil.copy2(generated_bbl, root / "main.bbl")

    if cmd[0] == "pdflatex":
        generated_aux = build_dir / "main.aux"
        if generated_aux.exists():
            shutil.copy2(generated_aux, root / "main.aux")

copy_pdf_to_root()
sys.exit(0 if report_build_status() else 1)
