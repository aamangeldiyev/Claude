"""
Stamp Detector — entry point.

Default: launches the GUI window.
CLI mode: pass --cli to use the command-line interface.

Examples:
    stamp_detector.exe                          # opens GUI
    stamp_detector.exe --cli C:\\docs           # CLI scan with defaults
    stamp_detector.exe --cli C:\\docs -o r.xlsx
"""

import argparse
import io
import os
import sys

# When running as a windowed exe (or via pythonw), stdout/stderr can be None.
# tqdm and print() will crash with "NoneType has no attribute 'write'".
# Replace with discard buffers so library code keeps working.
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent


def _run_cli(argv: list[str]) -> None:
    p = argparse.ArgumentParser(prog="stamp_detector --cli")
    p.add_argument("input_folder", help="Root folder to scan recursively")
    p.add_argument("-o", "--output", default=str(BASE_DIR / "stamp_report.xlsx"))
    p.add_argument("--stamps", default=str(BASE_DIR / "stamps"))
    p.add_argument("-t", "--threshold", type=float, default=0.80)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--pdf-dpi", type=int, default=100)
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--log", default=str(BASE_DIR / "scan.log"))
    args = p.parse_args(argv)

    input_folder = Path(args.input_folder)
    if not input_folder.exists():
        print(f"[ERROR] Folder does not exist: {input_folder}", file=sys.stderr)
        sys.exit(1)

    stamps_dir = Path(args.stamps)
    if not stamps_dir.exists():
        print(f"[ERROR] Stamps folder not found: {stamps_dir}", file=sys.stderr)
        sys.exit(1)

    print("Stamp Detector (template matching, CLI mode)")
    print(f"  Input  : {input_folder.resolve()}")
    print(f"  Stamps : {stamps_dir.resolve()}")
    print(f"  Output : {args.output}")
    print()

    from scanner import scan_folder
    scan_folder(
        root_folder=input_folder,
        stamps_dir=stamps_dir,
        output_path=args.output,
        threshold=args.threshold,
        workers=args.workers,
        pdf_dpi=args.pdf_dpi,
        resume=not args.no_resume,
        log_path=args.log,
    )


def main() -> None:
    # No arguments → launch GUI. Any arguments → CLI mode.
    # Explicit --gui flag forces GUI even with other args.
    argv = sys.argv[1:]
    if not argv or "--gui" in argv:
        from gui import main as gui_main
        gui_main()
    else:
        # Strip --cli if present (kept for backwards compatibility)
        argv = [a for a in argv if a != "--cli"]
        _run_cli(argv)


if __name__ == "__main__":
    main()
