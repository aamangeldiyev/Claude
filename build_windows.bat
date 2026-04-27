@echo off
REM Build standalone stamp_detector.exe for Windows
REM Run this script on the machine that HAS Python + internet (dev machine).
REM The output folder dist\stamp_detector\ is then copied to the target machine.

echo ====================================================
echo  Stamp Detector — PyInstaller build (Windows)
echo ====================================================

REM Create and activate virtual environment
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
echo  Executable folder: dist\stamp_detector\
echo.
echo  To deploy on the target machine (no Python needed):
echo    1. Copy the entire dist\stamp_detector\ folder
echo    2. Copy your stamp images into stamps\  (already bundled,
echo       but you can add more next to stamp_detector.exe)
echo    3. Run:
echo       stamp_detector.exe C:\path\to\docs --output report.xlsx
echo ====================================================

pause
