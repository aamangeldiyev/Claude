"""
Stamp Detector — finds stamps in PDF and JPEG/PNG files.

Usage:
    python main.py <folder_to_scan> [options]

    # Scan a folder, output Excel report
    python main.py C:/docs --output report.xlsx

    # Custom threshold and stamps directory
    python main.py C:/docs -t 0.70 --stamps stamps/

    # After building with PyInstaller:
    stamp_detector.exe C:/docs --output report.xlsx
"""

import argparse
import sys
from pathlib import Path

from scanner import scan_folder
from reporter import generate_report


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="stamp_detector",
        description="Finds stamps in PDF/image files and generates an Excel report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("input_folder", help="Root folder to scan recursively")
    p.add_argument(
        "-o", "--output",
        default="stamp_report.xlsx",
        help="Output report path (default: stamp_report.xlsx)",
    )
    p.add_argument(
        "-t", "--threshold",
        type=float,
        default=0.75,
        help="Detection confidence threshold 0–1 (default: 0.75). Lower = more hits, more false positives.",
    )
    p.add_argument(
        "--stamps",
        default="stamps",
        help="Directory with reference stamp images (default: stamps/)",
    )
    p.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output",
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
        print(f"[ERROR] Stamps directory does not exist: {stamps_dir}", file=sys.stderr)
        print("       Create it and place reference stamp images (.jpg/.png) inside.", file=sys.stderr)
        sys.exit(1)

    if not (0.0 < args.threshold <= 1.0):
        print("[ERROR] Threshold must be between 0 and 1.", file=sys.stderr)
        sys.exit(1)

    print(f"Stamp Detector")
    print(f"  Input folder : {input_folder.resolve()}")
    print(f"  Stamps dir   : {stamps_dir.resolve()}")
    print(f"  Threshold    : {args.threshold}")
    print(f"  Output       : {args.output}")
    print()

    results = scan_folder(
        root_folder=input_folder,
        stamps_dir=stamps_dir,
        threshold=args.threshold,
        verbose=not args.quiet,
    )

    if not results:
        print("No stamps found.")
        sys.exit(0)

    generate_report(results, args.output)


if __name__ == "__main__":
    main()
