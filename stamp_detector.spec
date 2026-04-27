# PyInstaller spec — builds a standalone stamp_detector folder (no Python needed).
#
# Build command (run in project root with venv active):
#   pyinstaller stamp_detector.spec
#
# Output: dist/stamp_detector/stamp_detector.exe  (Windows)
#         dist/stamp_detector/stamp_detector       (Linux)

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Collect PyMuPDF binary data (fonts, etc.)
fitz_datas = collect_data_files("fitz")
fitz_libs  = collect_dynamic_libs("fitz")

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=fitz_libs,
    datas=[
        # Bundle stamp templates into the exe folder
        ("stamps", "stamps"),
        *fitz_datas,
    ],
    hiddenimports=[
        "fitz",
        "fitz._fitz",
        "openpyxl",
        "openpyxl.styles",
        "cv2",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="stamp_detector",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # keep console so progress is visible
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="stamp_detector",
)
