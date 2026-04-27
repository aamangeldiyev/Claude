#!/usr/bin/env bash
# Build standalone stamp_detector binary for Linux.
# Run on a machine with Python + internet, then copy dist/stamp_detector/ to target.

set -euo pipefail

echo "===================================================="
echo " Stamp Detector — PyInstaller build (Linux)"
echo "===================================================="

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

echo ""
echo "===================================================="
echo " Build complete!"
echo " Executable folder: dist/stamp_detector/"
echo ""
echo " To deploy on the target machine (no Python needed):"
echo "   1. Copy the entire dist/stamp_detector/ folder"
echo "   2. Run:"
echo "      ./stamp_detector /path/to/docs --output report.xlsx"
echo "===================================================="
