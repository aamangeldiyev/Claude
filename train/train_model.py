"""
Train YOLOv8-nano on the augmented stamp dataset and export to ONNX.

Prerequisites:
    pip install ultralytics

Run after generating the dataset:
    python train/augment_stamps.py
    python train/train_model.py            # fresh start
    python train/train_model.py --resume   # continue after Ctrl+C

Output:
    runs/detect/stamp/   ← Ultralytics training artefacts
    models/stamp_detector.onnx  ← deployable model (~6 MB)
"""

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_YAML = PROJECT_ROOT / "train" / "dataset.yaml"
MODELS_DIR = PROJECT_ROOT / "models"
LAST_CHECKPOINT = PROJECT_ROOT / "runs" / "detect" / "stamp" / "weights" / "last.pt"

BASE_MODEL = "yolov8n.pt"
EPOCHS = 80
IMG_SIZE = 640
BATCH_SIZE = 16
PATIENCE = 15


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true",
                        help="Resume training from last checkpoint (runs/detect/stamp/weights/last.pt)")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] ultralytics not installed.", file=sys.stderr)
        print("        Run: pip install ultralytics", file=sys.stderr)
        sys.exit(1)

    if args.resume:
        if not LAST_CHECKPOINT.exists():
            print(f"[ERROR] No checkpoint found at {LAST_CHECKPOINT}", file=sys.stderr)
            print("        Start fresh: python train/train_model.py", file=sys.stderr)
            sys.exit(1)
        print(f"Resuming from {LAST_CHECKPOINT} ...")
        model = YOLO(str(LAST_CHECKPOINT))
        model.train(resume=True)
    else:
        if not DATASET_YAML.exists():
            print(f"[ERROR] Dataset config not found: {DATASET_YAML}", file=sys.stderr)
            print("        Run: python train/augment_stamps.py first", file=sys.stderr)
            sys.exit(1)

        dataset_root = PROJECT_ROOT / "train" / "datasets" / "images" / "train"
        if not dataset_root.exists() or not any(dataset_root.iterdir()):
            print(f"[ERROR] No training images in {dataset_root}", file=sys.stderr)
            print("        Run: python train/augment_stamps.py first", file=sys.stderr)
            sys.exit(1)

        print(f"Training {BASE_MODEL} for {EPOCHS} epochs...")
        model = YOLO(BASE_MODEL)
        model.train(
            data=str(DATASET_YAML),
            epochs=EPOCHS,
            imgsz=IMG_SIZE,
            batch=BATCH_SIZE,
            patience=PATIENCE,
            project=str(PROJECT_ROOT / "runs" / "detect"),
            name="stamp",
            exist_ok=True,
            verbose=True,
        )

    print("\nExporting to ONNX...")
    onnx_path = model.export(
        format="onnx",
        opset=12,
        dynamic=False,
        imgsz=IMG_SIZE,
        simplify=True,
    )

    MODELS_DIR.mkdir(exist_ok=True)
    final_path = MODELS_DIR / "stamp_detector.onnx"
    shutil.copy(onnx_path, final_path)
    size_mb = final_path.stat().st_size / 1024 / 1024
    print(f"\nDone. Model written to {final_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

