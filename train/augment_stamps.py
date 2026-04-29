"""
Generate a synthetic YOLO training dataset from stamp reference images.

Reads each PNG/JPG stamp from stamps/, pastes it onto random paper-like
backgrounds with augmentation (rotation, scaling, brightness, noise, blur,
perspective). Produces YOLO-format labels.

Output:
    train/datasets/images/train/*.jpg
    train/datasets/images/val/*.jpg
    train/datasets/labels/train/*.txt
    train/datasets/labels/val/*.txt

Run:
    python train/augment_stamps.py
"""

import random
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAMPS_DIR = PROJECT_ROOT / "stamps"
OUTPUT_ROOT = PROJECT_ROOT / "train" / "datasets"

# Tweakable
SAMPLES_PER_STAMP = 40         # how many augmented variants per stamp image
VAL_FRACTION = 0.15            # 15% goes to val split
BG_SIZE_RANGE = (1200, 2000)   # synthetic page width/height range
STAMP_SCALE_RANGE = (0.12, 0.55)  # stamp width as fraction of page width
ROTATION_RANGE = (-15, 15)     # degrees
BRIGHTNESS_RANGE = (0.6, 1.3)
JPEG_QUALITY_RANGE = (55, 95)
NOISE_PROBABILITY = 0.6
BLUR_PROBABILITY = 0.4
PERSPECTIVE_PROBABILITY = 0.5
MULTI_STAMP_PROBABILITY = 0.2  # chance of placing 2 stamps on one page


def _make_paper_background(w: int, h: int) -> np.ndarray:
    """Generate a paper-like background — white/cream with subtle noise."""
    base_color = random.choice([
        (255, 255, 255),  # pure white
        (252, 248, 240),  # cream
        (245, 245, 240),  # off-white
        (250, 245, 235),  # aged paper
    ])
    bg = np.full((h, w, 3), base_color, dtype=np.uint8)
    # Subtle paper texture
    noise = np.random.normal(0, 4, (h, w, 3))
    bg = np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    # Occasional random text-like marks to make backgrounds more realistic
    if random.random() < 0.7:
        for _ in range(random.randint(3, 12)):
            y = random.randint(50, h - 50)
            cv2.line(bg,
                     (random.randint(50, w // 2), y),
                     (random.randint(w // 2, w - 50), y),
                     color=(random.randint(50, 100),) * 3,
                     thickness=random.randint(1, 3))
    return bg


def _rotate_with_alpha(img: np.ndarray, angle: float) -> np.ndarray:
    """Rotate an RGBA image keeping full canvas (no cropping)."""
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(M[0, 0]); sin = abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2
    return cv2.warpAffine(img, M, (new_w, new_h),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(0, 0, 0, 0))


def _stamp_to_rgba(stamp_bgr: np.ndarray) -> np.ndarray:
    """Convert a stamp image to BGRA, treating near-white pixels as transparent."""
    if stamp_bgr.shape[2] == 4:
        return stamp_bgr
    gray = cv2.cvtColor(stamp_bgr, cv2.COLOR_BGR2GRAY)
    # Pixels brighter than ~230 → transparent (assumes stamps are darker than paper)
    _, mask = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)
    # Soften edges
    mask = cv2.GaussianBlur(mask, (3, 3), 0)
    rgba = cv2.cvtColor(stamp_bgr, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = mask
    return rgba


def _paste_rgba(bg: np.ndarray, fg_rgba: np.ndarray, x: int, y: int) -> None:
    """Alpha-composite fg_rgba onto bg at (x,y). Modifies bg in place."""
    h, w = fg_rgba.shape[:2]
    bg_h, bg_w = bg.shape[:2]

    x1 = max(0, x); y1 = max(0, y)
    x2 = min(bg_w, x + w); y2 = min(bg_h, y + h)
    if x1 >= x2 or y1 >= y2:
        return

    fg_x1 = x1 - x; fg_y1 = y1 - y
    fg_x2 = fg_x1 + (x2 - x1); fg_y2 = fg_y1 + (y2 - y1)

    fg_rgb = fg_rgba[fg_y1:fg_y2, fg_x1:fg_x2, :3]
    alpha = fg_rgba[fg_y1:fg_y2, fg_x1:fg_x2, 3:4].astype(np.float32) / 255.0

    bg_region = bg[y1:y2, x1:x2].astype(np.float32)
    blended = bg_region * (1 - alpha) + fg_rgb.astype(np.float32) * alpha
    bg[y1:y2, x1:x2] = blended.astype(np.uint8)


def _apply_perspective(img: np.ndarray, max_offset_frac: float = 0.05) -> np.ndarray:
    h, w = img.shape[:2]
    offset = int(min(h, w) * max_offset_frac)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([
        [random.randint(0, offset), random.randint(0, offset)],
        [w - random.randint(0, offset), random.randint(0, offset)],
        [w - random.randint(0, offset), h - random.randint(0, offset)],
        [random.randint(0, offset), h - random.randint(0, offset)],
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderValue=(255, 255, 255))


def _augment_full_image(img: np.ndarray) -> np.ndarray:
    """Whole-page augmentations applied AFTER stamps are placed."""
    if random.random() < BLUR_PROBABILITY:
        k = random.choice([3, 3, 5])
        img = cv2.GaussianBlur(img, (k, k), 0)

    if random.random() < NOISE_PROBABILITY:
        sigma = random.uniform(2, 8)
        noise = np.random.normal(0, sigma, img.shape)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # Brightness/contrast
    alpha = random.uniform(0.85, 1.15)
    beta = random.uniform(-15, 15)
    img = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

    if random.random() < PERSPECTIVE_PROBABILITY:
        img = _apply_perspective(img)

    return img


def _imread_unicode(path: Path, flags: int = cv2.IMREAD_UNCHANGED) -> np.ndarray | None:
    """cv2.imread replacement that handles Unicode/Cyrillic paths on Windows."""
    try:
        data = path.read_bytes()
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, flags)
    except Exception:
        return None


def _save_jpeg(path: Path, img: np.ndarray) -> None:
    quality = random.randint(*JPEG_QUALITY_RANGE)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        path.write_bytes(buf.tobytes())


def _yolo_label(box: tuple[int, int, int, int], img_w: int, img_h: int) -> str:
    """Convert (x1,y1,x2,y2) to YOLO format: class cx cy w h (normalized)."""
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2 / img_w
    cy = (y1 + y2) / 2 / img_h
    bw = (x2 - x1) / img_w
    bh = (y2 - y1) / img_h
    return f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def _generate_one_sample(stamp_rgba: np.ndarray, second_stamp_rgba: np.ndarray | None) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    bg_w = random.randint(*BG_SIZE_RANGE)
    bg_h = random.randint(*BG_SIZE_RANGE)
    bg = _make_paper_background(bg_w, bg_h)
    boxes = []

    for stamp in (s for s in (stamp_rgba, second_stamp_rgba) if s is not None):
        scale = random.uniform(*STAMP_SCALE_RANGE)
        target_w = int(bg_w * scale)
        sh, sw = stamp.shape[:2]
        target_h = int(sh * (target_w / sw))
        resized = cv2.resize(stamp, (target_w, target_h), interpolation=cv2.INTER_AREA)

        angle = random.uniform(*ROTATION_RANGE)
        rotated = _rotate_with_alpha(resized, angle)
        rh, rw = rotated.shape[:2]

        # Random brightness on the stamp itself (faded ink)
        brightness = random.uniform(*BRIGHTNESS_RANGE)
        rotated[:, :, :3] = np.clip(rotated[:, :, :3].astype(np.float32) * brightness, 0, 255).astype(np.uint8)

        if rw >= bg_w or rh >= bg_h:
            continue

        x = random.randint(0, bg_w - rw)
        y = random.randint(0, bg_h - rh)
        _paste_rgba(bg, rotated, x, y)

        # Compute tight bbox from alpha channel
        alpha_mask = rotated[:, :, 3] > 30
        if not alpha_mask.any():
            continue
        ys, xs = np.where(alpha_mask)
        bx1 = x + int(xs.min()); by1 = y + int(ys.min())
        bx2 = x + int(xs.max()); by2 = y + int(ys.max())
        boxes.append((bx1, by1, bx2, by2))

    bg = _augment_full_image(bg)
    return bg, boxes


def main() -> None:
    if not STAMPS_DIR.exists():
        print(f"[ERROR] Stamps directory not found: {STAMPS_DIR}", file=sys.stderr)
        sys.exit(1)

    stamp_files = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
        stamp_files.extend(STAMPS_DIR.glob(ext))

    if not stamp_files:
        print(f"[ERROR] No stamp images in {STAMPS_DIR}. Add PNG/JPG files.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(stamp_files)} stamp(s): {[p.name for p in stamp_files]}")

    # Clean old dataset
    if OUTPUT_ROOT.exists():
        print(f"Removing old dataset at {OUTPUT_ROOT}")
        shutil.rmtree(OUTPUT_ROOT)

    for split in ("train", "val"):
        (OUTPUT_ROOT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_ROOT / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Pre-load stamps as RGBA
    stamps_rgba = []
    for sp in stamp_files:
        img = _imread_unicode(sp, cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"[WARN] Cannot read {sp.name}, skipping", file=sys.stderr)
            continue
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape[2] == 3:
            img = _stamp_to_rgba(img)
        stamps_rgba.append((sp.stem, img))

    if not stamps_rgba:
        print("[ERROR] No usable stamp images.", file=sys.stderr)
        sys.exit(1)

    total = len(stamps_rgba) * SAMPLES_PER_STAMP
    print(f"Generating {total} samples ({SAMPLES_PER_STAMP} per stamp)...")

    sample_idx = 0
    for stamp_name, stamp_rgba in stamps_rgba:
        for i in range(SAMPLES_PER_STAMP):
            second = None
            if random.random() < MULTI_STAMP_PROBABILITY and len(stamps_rgba) > 1:
                second = random.choice([s for s in stamps_rgba if s[0] != stamp_name])[1]

            img, boxes = _generate_one_sample(stamp_rgba, second)
            if not boxes:
                continue

            split = "val" if random.random() < VAL_FRACTION else "train"
            stem = f"{stamp_name}_{i:04d}"
            img_path = OUTPUT_ROOT / "images" / split / f"{stem}.jpg"
            lbl_path = OUTPUT_ROOT / "labels" / split / f"{stem}.txt"

            _save_jpeg(img_path, img)
            with open(lbl_path, "w") as f:
                for box in boxes:
                    f.write(_yolo_label(box, img.shape[1], img.shape[0]) + "\n")

            sample_idx += 1
            if sample_idx % 100 == 0:
                print(f"  {sample_idx}/{total}...", end="\r")

    print(f"\nDone. Wrote {sample_idx} samples to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
