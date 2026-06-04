import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent
build_dir = root / "build"
compile_dir = build_dir / "_compile"
build_dir.mkdir(exist_ok=True)

# LaTeX writes into build/_compile/ during the run; only build/main.* remain afterward.
FINAL_JOB = "main"
COMPILE_DIR = compile_dir
BUILD_OUT_DIR = compile_dir.resolve().as_posix()

FINAL_PDF = build_dir / f"{FINAL_JOB}.pdf"
BUILD_PDF = compile_dir / f"{FINAL_JOB}.pdf"
BUILD_LOG = compile_dir / f"{FINAL_JOB}.log"
BUILD_AUX = compile_dir / f"{FINAL_JOB}.aux"

BUILD_SUFFIXES = (".aux", ".out", ".toc", ".lof", ".lot", ".log", ".blg", ".bbl", ".pdf")
LIGHT_CLEAN_SUFFIXES = (".aux", ".out", ".toc", ".lof", ".lot", ".log", ".blg")
CORRUPT_CLEAN_SUFFIXES = (".aux", ".out", ".toc", ".lof", ".lot", ".log", ".blg")

LOCK_RETRY_ATTEMPTS = 10
LOCK_RETRY_DELAY_SEC = 5.0
CONVERGENCE_PDFLATEX_PASSES = 3
LOCKED_OUTPUT_RE = re.compile(r"I can't write on file `([^']+)'")

COMPILE_ENV = {
    **os.environ,
    "MIKTEX_DISABLE_INSTALLER": "1",
}

LEGACY_ROOT_NAMES = (
    "main.aux",
    "main.out",
    "main.toc",
    "main.lof",
    "main.lot",
    "main.log",
    "main.blg",
    "main.bbl",
    "main.pdf",
)

STALE_HYPERREF_MARKERS = (
    "table.2.2",
    "subsection.2.2.3",
    "tab:cohort-comparison",
    "subsec:dataset-macs",
    "subsec:dataset-asoca",
)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def remove_file(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        path.unlink()
        print(f"Removed {path.relative_to(root)}")
        return True
    except OSError:
        print(
            f"Could not remove {path.relative_to(root)} (file may be open in a viewer or synced by OneDrive).",
            file=sys.stderr,
        )
        return False


def remove_legacy_artifacts() -> None:
    for name in LEGACY_ROOT_NAMES:
        remove_file(root / name)
    for suffix in BUILD_SUFFIXES:
        remove_file(build_dir / f"thesis_output{suffix}")


def remove_stale_duplicate_build_files() -> None:
    """Drop main_compile.* and other leftovers from earlier compile script versions."""
    for suffix in BUILD_SUFFIXES:
        remove_file(build_dir / f"main_compile{suffix}")
    staging = build_dir / f"{FINAL_JOB}.pdf.new"
    remove_file(staging)
    if compile_dir.exists():
        shutil.rmtree(compile_dir, ignore_errors=True)
    compile_dir.mkdir(parents=True, exist_ok=True)


def auxiliary_files_look_corrupt() -> bool:
    if not BUILD_AUX.exists():
        return False
    text = read_text(BUILD_AUX)
    return len(text) < 500 or "\\newlabel" not in text


def hyperref_bookmarks_look_stale() -> bool:
    out_file = compile_dir / f"{FINAL_JOB}.out"
    text = read_text(out_file)
    return bool(text and any(marker in text for marker in STALE_HYPERREF_MARKERS))


def clean_compile_workspace(
    *,
    full: bool = True,
    corrupt: bool = False,
) -> None:
    if corrupt:
        suffixes = CORRUPT_CLEAN_SUFFIXES
    elif full:
        suffixes = BUILD_SUFFIXES
    else:
        suffixes = LIGHT_CLEAN_SUFFIXES
    for suffix in suffixes:
        remove_file(compile_dir / f"{FINAL_JOB}{suffix}")


def path_is_writable(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        with path.open("a"):
            pass
        return True
    except OSError:
        return False


def resolve_locked_output_path(name: str) -> Path:
    candidate = Path(name)
    if candidate.is_absolute():
        return candidate
    if (compile_dir / candidate.name).exists():
        return compile_dir / candidate.name
    return build_dir / candidate.name


def locked_outputs_from_log(log: str) -> list[Path]:
    names = LOCKED_OUTPUT_RE.findall(log)
    return [resolve_locked_output_path(name) for name in names]


def preflight_pdflatex_outputs() -> list[Path]:
    blocked: list[Path] = []
    for suffix in (".pdf", ".lof", ".lot", ".toc", ".aux", ".out", ".log"):
        path = compile_dir / f"{FINAL_JOB}{suffix}"
        if not path_is_writable(path):
            blocked.append(path)
    return blocked


def pdflatex_failed_due_to_locked_output(log: str) -> bool:
    return "I can't write on file `" in log


def pdflatex_succeeded(log: str) -> bool:
    if "Emergency stop" in log or "Fatal error" in log:
        return False
    if "Output written on" not in log:
        return False
    return BUILD_PDF.exists()


def read_log() -> str:
    return read_text(BUILD_LOG)


def pdf_was_written(log: str | None = None) -> bool:
    log = log if log is not None else read_log()
    return pdflatex_succeeded(log)


def log_has_undefined_citations(log: str) -> bool:
    return any("Citation" in line and "undefined" in line for line in log.splitlines())


def log_has_undefined_references(log: str) -> bool:
    return any("Reference" in line and "undefined" in line for line in log.splitlines())


def log_needs_rerun(log: str) -> bool:
    if log_has_undefined_citations(log) or log_has_undefined_references(log):
        return True
    markers = (
        "Rerun to get citations correct",
        "Rerun to get cross-references right",
        "Label(s) may have changed",
    )
    return any(m in log for m in markers)


def log_has_natbib_author_warnings(log: str) -> bool:
    return "Author undefined for citation" in log


def promote_build_outputs() -> bool:
    """Copy build/_compile/main.* to build/main.* and remove the temporary workspace."""
    if not BUILD_PDF.exists():
        return False

    promoted_any = False
    for suffix in BUILD_SUFFIXES:
        src = compile_dir / f"{FINAL_JOB}{suffix}"
        if not src.exists():
            continue
        dst = build_dir / f"{FINAL_JOB}{suffix}"
        staging = dst.with_name(dst.name + ".new")
        try:
            shutil.copy2(src, staging)
            staging.replace(dst)
            promoted_any = True
        except OSError:
            if staging.exists():
                staging.unlink(missing_ok=True)
            print(
                f"Could not update {dst.relative_to(root)} (close any preview of that file).",
                file=sys.stderr,
            )
            return False

    shutil.rmtree(compile_dir, ignore_errors=True)
    return promoted_any


def report_build_status() -> bool:
    log = read_text(build_dir / f"{FINAL_JOB}.log")
    if not log:
        log = read_log()

    if not FINAL_PDF.exists():
        print(f"\nCheck {BUILD_LOG.relative_to(root)} for errors")
        for line in log.splitlines():
            if line.startswith("!") or "Emergency stop" in line or "Fatal error" in line:
                print(line)
        return False

    print(f"\nSUCCESS: {FINAL_PDF.relative_to(root)} generated")
    undefined_cites = [line for line in log.splitlines() if "Citation" in line and "undefined" in line]
    undefined_refs = [line for line in log.splitlines() if "Reference" in line and "undefined" in line]
    stale_dest = [line for line in log.splitlines() if "pdfTeX warning (dest)" in line]

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

    if stale_dest:
        print(
            "WARNING: stale PDF bookmarks detected; run compile again to refresh hyperref destinations.",
            file=sys.stderr,
        )

    if log_has_natbib_author_warnings(log):
        print(
            "WARNING: \\citeauthor is undefined for at least one entry (common with plain.bst + numeric natbib).",
            file=sys.stderr,
        )

    print(f"Open the thesis PDF at: {FINAL_PDF}")
    ok = not undefined_cites and not undefined_refs and not stale_dest
    return ok and not log_has_natbib_author_warnings(log)


def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, env=COMPILE_ENV)


def print_command_output(result: subprocess.CompletedProcess[str]) -> None:
    tail = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
    sys.stdout.write(tail)
    if result.stderr:
        sys.stderr.write(result.stderr[-1000:])


def print_locked_file_help(locked: list[Path]) -> None:
    rel = ", ".join(str(p.relative_to(root)) for p in locked)
    print(
        f"\nLaTeX could not write: {rel}.\n"
        f"Close any preview of build/{FINAL_JOB}.pdf, then run compile again.\n"
        "If the project is under OneDrive, pause sync briefly or exclude build/ from sync.",
        file=sys.stderr,
    )


def run_pdflatex_with_retries(cmd: list[str], step_index: int) -> tuple[subprocess.CompletedProcess[str], str]:
    blocked = preflight_pdflatex_outputs()
    if blocked:
        print_locked_file_help(blocked)

    last_result: subprocess.CompletedProcess[str] | None = None
    last_log = ""

    for attempt in range(1, LOCK_RETRY_ATTEMPTS + 1):
        if attempt > 1:
            print(f"Retrying Step {step_index} (attempt {attempt}/{LOCK_RETRY_ATTEMPTS})...")
            time.sleep(LOCK_RETRY_DELAY_SEC)

        last_result = run_command(cmd)
        last_log = read_log()

        if pdflatex_succeeded(last_log) and not pdflatex_failed_due_to_locked_output(last_log):
            return last_result, last_log

        if not pdflatex_failed_due_to_locked_output(last_log):
            return last_result, last_log

        locked = locked_outputs_from_log(last_log)
        if locked:
            print_locked_file_help(locked)

    assert last_result is not None
    return last_result, last_log


def run_convergence_passes(cmd: list[str], start_step: int) -> None:
    log = read_log()
    for extra in range(1, CONVERGENCE_PDFLATEX_PASSES + 1):
        if not log_needs_rerun(log):
            break
        step_no = start_step + extra
        print(
            f"\n=== Convergence pass {extra}/{CONVERGENCE_PDFLATEX_PASSES} "
            f"(pdflatex — resolve citations/cross-refs) ==="
        )
        result, log = run_pdflatex_with_retries(cmd, step_no)
        print_command_output(result)
        if not pdflatex_succeeded(log):
            break


def build_pdflatex_cmd() -> list[str]:
    return [
        "pdflatex",
        "-interaction=nonstopmode",
        "-synctex=0",
        "-jobname",
        FINAL_JOB,
        f"-output-directory={BUILD_OUT_DIR}",
        "main.tex",
    ]


def main() -> int:
    remove_legacy_artifacts()
    remove_stale_duplicate_build_files()

    blocked = preflight_pdflatex_outputs()
    if blocked:
        print_locked_file_help(blocked)
        print("\nAborting before compile. Close the locked files and rerun.", file=sys.stderr)
        return 1

    corrupt = auxiliary_files_look_corrupt()
    stale = hyperref_bookmarks_look_stale()
    if corrupt:
        print("Cleaning build/_compile/ (truncated aux); keeping bibliography if present.")
        clean_compile_workspace(corrupt=True)
    elif stale:
        print("Cleaning build/_compile/ (stale bookmarks).")
        clean_compile_workspace(full=False)

    pdflatex_cmd = build_pdflatex_cmd()
    bibtex_target = (compile_dir / FINAL_JOB).relative_to(root).as_posix()
    commands: list[tuple[str, list[str]]] = [
        ("pdflatex", pdflatex_cmd),
        ("bibtex", ["bibtex", bibtex_target]),
        ("pdflatex", pdflatex_cmd),
        ("pdflatex", pdflatex_cmd),
    ]

    print(
        "Compiling in build/_compile/, then updating build/main.pdf and related files.\n"
        "Tip: open only build/main.pdf (not files inside _compile/).\n"
    )

    for i, (kind, cmd) in enumerate(commands, start=1):
        print(f"\n=== Step {i}: {' '.join(cmd)} ===")

        if kind == "pdflatex":
            result, log = run_pdflatex_with_retries(cmd, i)
        else:
            result = run_command(cmd)
            log = read_log()

        print_command_output(result)

        if kind == "pdflatex" and not pdflatex_succeeded(log):
            print(f"pdflatex did not produce a valid PDF (exit code {result.returncode}).")
            if i == 1:
                print(
                    "\nNote: undefined citation/reference warnings on Step 1 are normal "
                    "before bibtex and later pdflatex passes.",
                    file=sys.stderr,
                )
            if pdflatex_failed_due_to_locked_output(log):
                print_locked_file_help(locked_outputs_from_log(log) or preflight_pdflatex_outputs())
            return result.returncode if result.returncode else 1

        if kind == "bibtex" and result.returncode != 0:
            print(f"bibtex failed (exit code {result.returncode}).", file=sys.stderr)
            return result.returncode

    run_convergence_passes(pdflatex_cmd, start_step=len(commands))

    if not promote_build_outputs():
        print(
            "\nCompile finished in build/_compile/ but could not update build/main.pdf.",
            file=sys.stderr,
        )
        print(f"Open: {BUILD_PDF.relative_to(root)}", file=sys.stderr)
        return 1

    return 0 if report_build_status() else 1


if __name__ == "__main__":
    sys.exit(main())
