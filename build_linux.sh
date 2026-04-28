#!/usr/bin/env bash
# Build standalone stamp_detector binary for Linux.
# Run on a machine that has Python + internet, then copy dist/stamp_detector/
# to the target machine.

set -euo pipefail

echo "===================================================="
echo " Stamp Detector — PyInstaller build (Linux)"
echo "===================================================="

if [ ! -f models/stamp_detector.onnx ]; then
    echo
    echo "[WARN] models/stamp_detector.onnx does not exist yet."
    echo "       Build will succeed but the binary will not detect anything."
    echo "       Train the model first:"
    echo "           python train/augment_stamps.py"
    echo "           python train/train_model.py"
    echo
fi

if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "Building executable..."
pyinstaller stamp_detector.spec --clean --noconfirm

echo
echo "===================================================="
echo " Build complete!"
echo " Folder: dist/stamp_detector/"
echo
echo " To deploy on a machine without Python:"
echo "   1. Copy the entire dist/stamp_detector/ folder"
echo "   2. Run:"
echo "      ./stamp_detector /path/to/docs --output report.xlsx"
echo "===================================================="
