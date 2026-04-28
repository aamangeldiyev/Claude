# PyInstaller spec — builds a standalone stamp_detector folder (no Python needed).
#
# Build command (run in project root with venv active):
#   pyinstaller stamp_detector.spec --clean --noconfirm
#
# Output: dist/stamp_detector/stamp_detector(.exe)
# Make sure models/stamp_detector.onnx exists before building.

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None
project_root = Path(".").resolve()

# Bundle PyMuPDF assets
fitz_datas = collect_data_files("fitz")
fitz_libs = collect_dynamic_libs("fitz")

# Bundle ONNX Runtime native libs
ort_datas = collect_data_files("onnxruntime")
ort_libs = collect_dynamic_libs("onnxruntime")

# Bundle our model + reference stamps directory
extra_datas = []
if (project_root / "models").exists():
    extra_datas.append(("models", "models"))
if (project_root / "stamps").exists():
    extra_datas.append(("stamps", "stamps"))

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=fitz_libs + ort_libs,
    datas=extra_datas + fitz_datas + ort_datas,
    hiddenimports=[
        "fitz", "fitz._fitz",
        "openpyxl", "openpyxl.styles",
        "cv2", "numpy", "tqdm",
        "onnxruntime", "onnxruntime.capi._pybind_state",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas",
        "IPython", "jupyter", "torch", "torchvision",
        "ultralytics",  # not needed at inference time
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
    upx=False,            # UPX can corrupt onnxruntime binaries — leave off
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="stamp_detector",
)
