"""
Train YOLOv8-nano on the augmented stamp dataset and export to ONNX.

Prerequisites:
    pip install ultralytics

Run after generating the dataset:
    python train/augment_stamps.py
    python train/train_model.py

Output:
    runs/detect/train*/   ← Ultralytics training artefacts
    models/stamp_detector.onnx  ← deployable model (~6 MB)
"""

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_YAML = PROJECT_ROOT / "train" / "dataset.yaml"
MODELS_DIR = PROJECT_ROOT / "models"

# Tweakable
BASE_MODEL = "yolov8n.pt"   # nano: ~3 MB, good speed/quality balance
EPOCHS = 80
IMG_SIZE = 640
BATCH_SIZE = 16
PATIENCE = 15               # early stopping patience


def main() -> None:
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] ultralytics not installed.", file=sys.stderr)
        print("        Run: pip install ultralytics", file=sys.stderr)
        sys.exit(1)

    if not DATASET_YAML.exists():
        print(f"[ERROR] Dataset config not found: {DATASET_YAML}", file=sys.stderr)
        print("        Run: python train/augment_stamps.py first", file=sys.stderr)
        sys.exit(1)

    dataset_root = PROJECT_ROOT / "train" / "datasets" / "images" / "train"
    if not dataset_root.exists() or not any(dataset_root.iterdir()):
        print(f"[ERROR] No training images found in {dataset_root}", file=sys.stderr)
        print("        Run: python train/augment_stamps.py first", file=sys.stderr)
        sys.exit(1)

    print(f"Training {BASE_MODEL} on {DATASET_YAML} for {EPOCHS} epochs...")
    print(f"  Image size: {IMG_SIZE}")
    print(f"  Batch:      {BATCH_SIZE}")
    print()

    model = YOLO(BASE_MODEL)
    results = model.train(
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
    print(f"Training metrics: see {PROJECT_ROOT / 'runs' / 'detect' / 'stamp'}")


if __name__ == "__main__":
    main()
