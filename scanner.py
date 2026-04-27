import sys
import cv2
import numpy as np
from pathlib import Path
from detector import load_stamp_templates, detect_stamps

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
PDF_EXTENSIONS = {".pdf"}

# DPI for rendering PDF pages (150 is good balance of speed vs quality)
PDF_DPI = 150
PDF_MATRIX_SCALE = PDF_DPI / 72


def _process_image_file(file_path: Path, templates: list[dict], threshold: float) -> list[dict]:
    img = cv2.imread(str(file_path))
    if img is None:
        return []

    detections = detect_stamps(img, templates, threshold)
    if not detections:
        return []

    return [{
        "file": str(file_path),
        "file_name": file_path.name,
        "folder": str(file_path.parent),
        "file_type": "IMAGE",
        "page": 1,
        "total_pages": 1,
        "detections": detections,
    }]


def _process_pdf_file(file_path: Path, templates: list[dict], threshold: float) -> list[dict]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(f"\n[WARN] PyMuPDF not installed — skipping PDF: {file_path.name}", file=sys.stderr)
        return []

    results = []
    try:
        doc = fitz.open(str(file_path))
        mat = fitz.Matrix(PDF_MATRIX_SCALE, PDF_MATRIX_SCALE)
        total = len(doc)

        for page_num in range(total):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)

            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

            if pix.n == 4:
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            elif pix.n == 1:
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            else:
                img_bgr = img_array  # already RGB/BGR-ish; OpenCV handles it

            detections = detect_stamps(img_bgr, templates, threshold)
            if detections:
                results.append({
                    "file": str(file_path),
                    "file_name": file_path.name,
                    "folder": str(file_path.parent),
                    "file_type": "PDF",
                    "page": page_num + 1,
                    "total_pages": total,
                    "detections": detections,
                })

        doc.close()
    except Exception as exc:
        print(f"\n[ERROR] Failed to process {file_path.name}: {exc}", file=sys.stderr)

    return results


def scan_folder(
    root_folder: str | Path,
    stamps_dir: str | Path,
    threshold: float = 0.75,
    verbose: bool = True,
) -> list[dict]:
    """
    Recursively scan root_folder for images and PDFs and detect stamps.
    Returns list of result dicts, one per file+page combination that has detections.
    """
    root = Path(root_folder)
    templates = load_stamp_templates(str(stamps_dir))

    if not templates:
        print(f"[WARN] No stamp templates found in '{stamps_dir}'. "
              "Place reference stamp images (.jpg/.png) in that folder.", file=sys.stderr)
        return []

    if verbose:
        print(f"Loaded {len(templates)} stamp template(s): {[t['name'] for t in templates]}")

    all_files = [
        f for f in root.rglob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS | PDF_EXTENSIONS
    ]

    if verbose:
        print(f"Found {len(all_files)} file(s) to process in '{root}'")

    results = []
    for idx, file_path in enumerate(all_files, 1):
        if verbose:
            print(f"  [{idx:>4}/{len(all_files)}] {file_path.relative_to(root)}", end="\r")

        ext = file_path.suffix.lower()
        if ext in PDF_EXTENSIONS:
            file_results = _process_pdf_file(file_path, templates, threshold)
        else:
            file_results = _process_image_file(file_path, templates, threshold)

        results.extend(file_results)

    if verbose:
        print()  # newline after progress line
        files_with_stamps = len({r["file"] for r in results})
        total_hits = sum(len(r["detections"]) for r in results)
        print(f"Done. Files with stamps: {files_with_stamps} | Total detections: {total_hits}")

    return results
