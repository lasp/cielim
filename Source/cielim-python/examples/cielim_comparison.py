from pathlib import Path
import sys
import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
CIELIM_ROOT = HERE.parent

sys.path.insert(0, str(CIELIM_ROOT))

import context
from image_comparison_toolkit import generate_plots

BASE_DIR = CIELIM_ROOT / "support-data" / "giant-vesta"

PAD_SMALL = 1.4
PAD_LARGE = 0.20
SMALL_THRESHOLD = 50
DISPLAY_SIZE = 300
ALIGN = True  # flag to enable cross-correlation alignment
REFERENCE = 1  # 1 = img1 (cielim) is reference, 2 = img2 (giant) is reference

SESSIONS = [1, 2, 3]


def load_grayscale(path):
    return np.array(Image.open(path).convert("L"))


def get_cob_and_bbox(img):
    thresh_val = max(img.max() // 4, 10)
    _, thresh = cv2.threshold(img, thresh_val, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img.shape[1] // 2, img.shape[0] // 2, 0, 0
    largest = max(contours, key=cv2.contourArea)
    bx, by, bw, bh = cv2.boundingRect(largest)
    m = cv2.moments(thresh)
    cx = int(m["m10"] / m["m00"]) if m["m00"] > 0 else bx + bw // 2
    cy = int(m["m01"] / m["m00"]) if m["m00"] > 0 else by + bh // 2
    return cx, cy, bw, bh


def detect_pad(img):
    _, _, bw, bh = get_cob_and_bbox(img)
    obj_size = max(bw, bh)
    pad = PAD_SMALL if obj_size < SMALL_THRESHOLD else PAD_LARGE
    return pad, obj_size


def crop_roi(img, pad_frac):
    cx, cy, bw, bh = get_cob_and_bbox(img)
    pad = int(max(bw, bh) * pad_frac)
    half = max(bw, bh) // 2 + pad
    x1 = max(cx - half, 0)
    x2 = min(cx + half, img.shape[1])
    y1 = max(cy - half, 0)
    y2 = min(cy + half, img.shape[0])
    crop = img[y1:y2, x1:x2]
    if max(crop.shape) < DISPLAY_SIZE:
        crop = np.array(Image.fromarray(crop).resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.NEAREST))
    return crop


if __name__ == "__main__":
    for session in SESSIONS:
        cielim_img = BASE_DIR / f"cielim_{session}.png"
        giant_img = BASE_DIR / f"giant_{session}.png"
        out_dir = BASE_DIR / "comparison_plots" / f"session_{session}"

        if not cielim_img.exists():
            raise FileNotFoundError(f"Missing: {cielim_img}")
        if not giant_img.exists():
            raise FileNotFoundError(f"Missing: {giant_img}")

        img_c = load_grayscale(cielim_img)
        img_g = load_grayscale(giant_img)

        pad_c, _ = detect_pad(img_c)
        pad_g, _ = detect_pad(img_g)

        crop_c = crop_roi(img_c, pad_c)
        crop_g = crop_roi(img_g, pad_g)

        generate_plots(
            crop_c,
            crop_g,
            title1=cielim_img.stem,
            title2=giant_img.stem,
            output_dir=out_dir,
            align=ALIGN,
            reference=REFERENCE,
        )

        print(f"Session {session} done → {out_dir}")
