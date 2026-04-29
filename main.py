"""
Stamp Detector — finds stamps in PDF and image files using template matching.

Drop real stamp screenshots into stamps/ and run:
    python main.py <folder_to_scan>
    stamp_detector.exe <folder_to_scan>

No training required. The scan can be interrupted (Ctrl+C) and resumed —
progress is saved automatically next to the output report.
"""

import argparse
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="stamp_detector",
        description="Find stamps in PDF/image files using template matching.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("input_folder", help="Root folder to scan recursively")
    p.add_argument(
        "-o", "--output",
        default=str(BASE_DIR / "stamp_report.xlsx"),
        help="Output report path (default: stamp_report.xlsx next to the exe)",
    )
    p.add_argument(
        "--stamps",
        default=str(BASE_DIR / "stamps"),
        help="Folder with stamp screenshot images (default: stamps/ next to the exe)",
    )
    p.add_argument(
        "-t", "--threshold",
        type=float, default=0.80,
        help="Match confidence 0–1 (default: 0.80). Lower = more hits, more false positives.",
    )
    p.add_argument(
        "--workers",
        type=int, default=max(1, (os.cpu_count() or 2) - 1),
        help="Parallel worker processes (default: CPU count − 1)",
    )
    p.add_argument(
        "--pdf-dpi",
        type=int, default=100,
        help="DPI for PDF rendering (default: 100). Use 150 for better quality.",
    )
    p.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing checkpoint and rescan everything from scratch",
    )
    p.add_argument(
        "--log",
        default=str(BASE_DIR / "scan.log"),
        help="Log file path (default: scan.log next to the exe)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    input_folder = Path(args.input_folder)
    if not input_folder.exists():
        print(f"[ERROR] Folder does not exist: {input_folder}", file=sys.stderr)
        sys.exit(1)

    stamps_dir = Path(args.stamps)
    if not stamps_dir.exists():
        print(f"[ERROR] Stamps folder not found: {stamps_dir}", file=sys.stderr)
        print( "        Create it and put stamp screenshot images inside.", file=sys.stderr)
        sys.exit(1)

    if not (0.0 < args.threshold <= 1.0):
        print("[ERROR] Threshold must be between 0 and 1.", file=sys.stderr)
        sys.exit(1)

    print("Stamp Detector (template matching)")
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


if __name__ == "__main__":
    main()
