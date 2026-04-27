import cv2
import numpy as np
from pathlib import Path


def load_stamp_templates(stamps_dir: str) -> list[dict]:
    """Load all reference stamp images from stamps directory."""
    stamps_path = Path(stamps_dir)
    if not stamps_path.exists():
        return []

    templates = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff", "*.tif"):
        for stamp_path in stamps_path.glob(ext):
            img = cv2.imread(str(stamp_path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                templates.append({"name": stamp_path.stem, "image": img, "path": stamp_path})

    return templates


def _preprocess(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _detect_template(gray: np.ndarray, template: np.ndarray, threshold: float) -> dict | None:
    """Multi-scale template matching."""
    img_h, img_w = gray.shape
    t_h, t_w = template.shape

    best = {"val": 0.0, "loc": None, "size": (t_w, t_h)}

    # 12 scales instead of 25 — 2x faster, still covers realistic size variation
    scales = np.linspace(0.5, 1.5, 12)
    for scale in scales:
        new_w = int(t_w * scale)
        new_h = int(t_h * scale)

        if new_w > img_w or new_h > img_h or new_w < 10 or new_h < 10:
            continue

        resized = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > best["val"]:
            best = {"val": max_val, "loc": max_loc, "size": (new_w, new_h)}

        # Early exit — no point searching further once we have a strong hit
        if best["val"] >= 0.95:
            break

    if best["val"] >= threshold and best["loc"] is not None:
        x, y = best["loc"]
        w, h = best["size"]
        return {
            "method": "template",
            "confidence": round(float(best["val"]), 4),
            "bbox": (x, y, x + w, y + h),
        }
    return None


def _detect_orb(gray: np.ndarray, template: np.ndarray, min_good_matches: int = 20) -> dict | None:
    """ORB feature matching — stricter to avoid false positives."""
    orb = cv2.ORB_create(nfeatures=1500)
    kp1, des1 = orb.detectAndCompute(template, None)
    kp2, des2 = orb.detectAndCompute(gray, None)

    if des1 is None or des2 is None or len(des1) < 8 or len(des2) < 8:
        return None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(bf.match(des1, des2), key=lambda m: m.distance)
    # Stricter distance threshold (was 60, now 45)
    good = [m for m in matches if m.distance < 45]

    if len(good) < min_good_matches:
        return None

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if M is None:
        return None

    inliers = int(mask.sum()) if mask is not None else 0
    if inliers < min_good_matches:
        return None

    t_h, t_w = template.shape
    corners = np.float32([[0, 0], [t_w, 0], [t_w, t_h], [0, t_h]]).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(corners, M)

    xs = transformed[:, 0, 0]
    ys = transformed[:, 0, 1]
    x1, y1 = int(max(0, min(xs))), int(max(0, min(ys)))
    x2, y2 = int(max(xs)), int(max(ys))

    confidence = min(round(inliers / len(des1), 4), 1.0)
    return {
        "method": "ORB",
        "confidence": confidence,
        "bbox": (x1, y1, x2, y2),
    }


def detect_stamps(image: np.ndarray, templates: list[dict], threshold: float = 0.82) -> list[dict]:
    """
    Detect stamps using template matching + ORB fallback.
    Default threshold raised to 0.82 to reduce false positives.
    """
    gray = _preprocess(image)
    detections = []

    for tpl in templates:
        tpl_gray = _preprocess(tpl["image"])

        det = _detect_template(gray, tpl_gray, threshold)

        if det is None:
            det = _detect_orb(gray, tpl_gray)

        if det is not None:
            det["template_name"] = tpl["name"]
            detections.append(det)

    return detections
