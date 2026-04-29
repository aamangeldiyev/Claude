"""
Template matching detector using real stamp screenshots.

Loads all images from stamps/ as reference templates and uses
multi-scale OpenCV template matching to find them in document pages.

No training required — just drop real stamp screenshots into stamps/.

Public API:
    load_templates(stamps_dir) -> list[dict]
    detect_stamps(image, templates, threshold=0.80) -> list[dict]
"""

from pathlib import Path

import cv2
import numpy as np

# Templates are normalised to this width on load.
# Smaller = faster matching; 200px is enough to distinguish stamp patterns.
TEMPLATE_WIDTH = 200

# 3 scales around 1.0 — covers stamps that appear slightly larger/smaller
# than the reference screenshot. Keeps 50 templates × 3 = 150 ops/page fast.
SCALES = [0.7, 1.0, 1.3]

DEFAULT_THRESHOLD = 0.80


def _imread_unicode(path: Path, flags: int = cv2.IMREAD_UNCHANGED) -> np.ndarray | None:
    """Read image from a path that may contain Unicode/Cyrillic characters."""
    try:
        data = path.read_bytes()
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, flags)
    except Exception:
        return None


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _normalise(gray: np.ndarray) -> np.ndarray:
    """Light contrast normalisation so faded ink still matches."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def load_templates(stamps_dir: str | Path) -> list[dict]:
    """
    Load all stamp screenshots from stamps_dir.
    Each image is converted to greyscale and resized to TEMPLATE_WIDTH.
    Returns list of dicts: {name, image (gray), orig_size}.
    """
    stamps_path = Path(stamps_dir)
    if not stamps_path.exists():
        return []

    templates = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
        for p in stamps_path.glob(ext):
            img = _imread_unicode(p, cv2.IMREAD_UNCHANGED)
            if img is None:
                continue
            gray = _to_gray(img)
            orig_h, orig_w = gray.shape
            # Resize to standard width, keep aspect ratio
            new_w = TEMPLATE_WIDTH
            new_h = max(10, int(orig_h * (new_w / orig_w)))
            resized = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
            templates.append({
                "name": p.stem,
                "image": _normalise(resized),
                "orig_size": (orig_w, orig_h),
            })

    return templates


def detect_stamps(
    image: np.ndarray,
    templates: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict]:
    """
    Run multi-scale template matching for every template.
    Returns list of detections: {template_name, method, confidence, bbox}.
    """
    if image is None or image.size == 0 or not templates:
        return []

    gray = _normalise(_to_gray(image))
    img_h, img_w = gray.shape
    detections = []

    for tpl in templates:
        t = tpl["image"]
        t_h, t_w = t.shape
        best_val = 0.0
        best_loc = None
        best_size = (t_w, t_h)

        for scale in SCALES:
            sw = max(8, int(t_w * scale))
            sh = max(8, int(t_h * scale))
            if sw > img_w or sh > img_h:
                continue

            scaled = cv2.resize(t, (sw, sh), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_size = (sw, sh)

            # Early exit — no point trying other scales
            if best_val >= 0.95:
                break

        if best_val >= threshold and best_loc is not None:
            x, y = best_loc
            w, h = best_size
            detections.append({
                "method": "template",
                "confidence": round(float(best_val), 4),
                "bbox": (x, y, x + w, y + h),
                "template_name": tpl["name"],
            })

    return detections
