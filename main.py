"""
Stamp Detector — finds stamps in PDF and image files using a YOLO ONNX model.

Usage:
    python main.py <folder_to_scan> [options]
    stamp_detector.exe <folder_to_scan> [options]

The model is loaded from <exe_dir>/models/stamp_detector.onnx by default.
Use --model to point to a different file.

The scan can be interrupted (Ctrl+C) and resumed — progress is checkpointed
next to the output report. Re-running the same command picks up where it
stopped.
"""

import argparse
import os
import sys
from pathlib import Path

# Resolve "next to me" directory (works for both PyInstaller exe and python script)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="stamp_detector",
        description="Find stamps in PDF/image files using a trained YOLO model.",
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
        "--model",
        default=str(BASE_DIR / "models" / "stamp_detector.onnx"),
        help="Path to the YOLO ONNX model (default: models/stamp_detector.onnx)",
    )
    p.add_argument(
        "-t", "--threshold",
        type=float, default=0.35,
        help="Detection confidence threshold 0–1 (default: 0.35)",
    )
    p.add_argument(
        "--workers",
        type=int, default=max(1, (os.cpu_count() or 2) - 1),
        help="Parallel worker processes (default: CPU count − 1)",
    )
    p.add_argument(
        "--pdf-dpi",
        type=int, default=150,
        help="DPI for PDF page rendering (default: 150)",
    )
    p.add_argument(
        "--imgsz",
        type=int, default=640,
        help="YOLO input size (default: 640)",
    )
    p.add_argument(
        "--prefilter",
        action="store_true",
        help="Skip near-blank pages quickly (small speedup, tiny risk of misses)",
    )
    p.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing checkpoint and rescan everything",
    )
    p.add_argument(
        "--log",
        default=str(BASE_DIR / "scan.log"),
        help="Path to the log file (default: scan.log next to the exe)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    input_folder = Path(args.input_folder)
    if not input_folder.exists():
        print(f"[ERROR] Folder does not exist: {input_folder}", file=sys.stderr)
        sys.exit(1)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[ERROR] Model file not found: {model_path}", file=sys.stderr)
        print("        Train one with: python train/train_model.py", file=sys.stderr)
        print("        Or copy stamp_detector.onnx into the models/ folder.", file=sys.stderr)
        sys.exit(1)

    if not (0.0 < args.threshold <= 1.0):
        print("[ERROR] Threshold must be between 0 and 1.", file=sys.stderr)
        sys.exit(1)

    print("Stamp Detector (YOLO ONNX)")
    print(f"  Input folder : {input_folder.resolve()}")
    print(f"  Model        : {model_path.resolve()}")
    print(f"  Threshold    : {args.threshold}")
    print(f"  Workers      : {args.workers}")
    print(f"  PDF DPI      : {args.pdf_dpi}")
    print(f"  Img size     : {args.imgsz}")
    print(f"  Prefilter    : {'on' if args.prefilter else 'off'}")
    print(f"  Output       : {args.output}")
    print()

    # Import here so that --help is fast and doesn't initialise heavy libs
    from scanner import scan_folder

    scan_folder(
        root_folder=input_folder,
        model_path=model_path,
        output_path=args.output,
        threshold=args.threshold,
        imgsz=args.imgsz,
        workers=args.workers,
        pdf_dpi=args.pdf_dpi,
        prefilter=args.prefilter,
        resume=not args.no_resume,
        log_path=args.log,
    )


if __name__ == "__main__":
    main()
