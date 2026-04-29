# PyInstaller spec — builds a standalone stamp_detector folder (no Python needed).
#
# Build:
#   pyinstaller stamp_detector.spec --clean --noconfirm
#
# Output: dist/stamp_detector/stamp_detector.exe
# Make sure stamps/ folder contains your stamp screenshots before building.

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None
project_root = Path(".").resolve()

fitz_datas = collect_data_files("fitz")
fitz_libs  = collect_dynamic_libs("fitz")

extra_datas = []
if (project_root / "stamps").exists():
    extra_datas.append(("stamps", "stamps"))

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=fitz_libs,
    datas=extra_datas + fitz_datas,
    hiddenimports=[
        "fitz", "fitz._fitz",
        "openpyxl", "openpyxl.styles",
        "cv2", "numpy", "tqdm",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas",
        "IPython", "jupyter", "torch", "torchvision",
        "ultralytics", "onnxruntime",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="stamp_detector",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    name="stamp_detector",
)
