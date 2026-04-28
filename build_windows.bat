@echo off
REM Build standalone stamp_detector.exe for Windows.
REM Run on a machine that has Python + internet (the dev machine).
REM Output folder dist\stamp_detector\ is then copied to the target machine.

echo ====================================================
echo  Stamp Detector  - PyInstaller build (Windows)
echo ====================================================

if not exist models\stamp_detector.onnx (
    echo.
    echo [WARN] models\stamp_detector.onnx does not exist yet.
    echo        Build will succeed but the exe will not detect anything.
    echo        Train the model first:
    echo            python train\augment_stamps.py
    echo            python train\train_model.py
    echo.
)

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo Building executable...
pyinstaller stamp_detector.spec --clean --noconfirm

echo.
echo ====================================================
echo  Build complete!
echo  Folder: dist\stamp_detector\
echo.
echo  To deploy on a machine without Python:
echo    1. Copy the entire dist\stamp_detector\ folder
echo    2. Run:
echo       stamp_detector.exe C:\path\to\docs --output report.xlsx
echo ====================================================
pause
