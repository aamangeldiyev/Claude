"""
Utility: generate a synthetic "Для служебного пользования" stamp image for testing.

Run:
    python create_test_stamp.py

Output: stamps/stamp_dsp_test.png

Replace with the real stamp scan once you have it.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    USE_PIL = True
except ImportError:
    USE_PIL = False


def create_stamp_opencv(output_path: Path) -> None:
    """Create a simple stamp using OpenCV (ASCII text only)."""
    h, w = 120, 340
    img = np.full((h, w, 3), 255, dtype=np.uint8)

    # Outer rectangle
    cv2.rectangle(img, (4, 4), (w - 5, h - 5), (0, 0, 0), 3)
    cv2.rectangle(img, (8, 8), (w - 9, h - 9), (0, 0, 0), 1)

    # Placeholder text (Latin, since OpenCV has no Cyrillic font)
    cv2.putText(img, "DSP - FOR OFFICIAL USE", (14, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(img, "Dlya sluzhebnogo", (40, 72),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "pol'zovaniya", (65, 98),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    cv2.imwrite(str(output_path), img)
    print(f"[OpenCV] Test stamp written to {output_path}")
    print("NOTE: This is a Latin placeholder. Replace with the real stamp scan.")


def create_stamp_pil(output_path: Path) -> None:
    """Create a stamp with Cyrillic text using Pillow."""
    w, h = 380, 130
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([4, 4, w - 5, h - 5], outline=(0, 0, 0), width=3)
    draw.rectangle([8, 8, w - 9, h - 9], outline=(0, 0, 0), width=1)

    # Try to use a system font that has Cyrillic support
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/times.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    font_large = font_small = None
    for fc in font_candidates:
        try:
            font_large = ImageFont.truetype(fc, 22)
            font_small = ImageFont.truetype(fc, 18)
            break
        except (IOError, OSError):
            continue

    if font_large is None:
        font_large = font_small = ImageFont.load_default()

    draw.text((w // 2, 38), "ДЛЯ СЛУЖЕБНОГО ПОЛЬЗОВАНИЯ",
              font=font_large, fill=(0, 0, 0), anchor="mm")
    draw.text((w // 2, 72), "Экз. №___",
              font=font_small, fill=(0, 0, 0), anchor="mm")
    draw.text((w // 2, 100), "Стр. _____ из _____",
              font=font_small, fill=(0, 0, 0), anchor="mm")

    img.save(str(output_path))
    print(f"[Pillow] Test stamp written to {output_path}")
    print("NOTE: This is a synthetic stamp. For best results, replace with the real scan.")


def main() -> None:
    out_dir = Path("stamps")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "stamp_dsp_test.png"

    if USE_PIL:
        create_stamp_pil(out_path)
    else:
        create_stamp_opencv(out_path)


if __name__ == "__main__":
    main()
