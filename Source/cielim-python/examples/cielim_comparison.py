import sys
from pathlib import Path

from cielim.utils import image_comparison_toolkit as image_comparison
from cielim.utils.image_comparison_toolkit import load_grayscale

HERE = Path(__file__).resolve().parent
CIELIM_ROOT = HERE.parent

sys.path.insert(0, str(CIELIM_ROOT))

BASE_DIR = CIELIM_ROOT / "support-data" / "giant-vesta"

SESSIONS = [1, 2, 3]


if __name__ == "__main__":
    # Build the batch of (real, generated) pairs: GIANT is the reference "real" render, cielim the
    # generated one. generate_batch crops each to the target ROI and writes raw/ and aligned/ sets,
    # each with individual histograms + heatmaps and one average histogram.
    pairs = []
    for session in SESSIONS:
        cielim_img = BASE_DIR / f"cielim_{session}.png"
        giant_img = BASE_DIR / f"giant_{session}.png"
        if not cielim_img.exists():
            raise FileNotFoundError(f"Missing: {cielim_img}")
        if not giant_img.exists():
            raise FileNotFoundError(f"Missing: {giant_img}")
        pairs.append((load_grayscale(giant_img), load_grayscale(cielim_img)))

    out_dir = BASE_DIR / "comparison_plots"
    image_comparison.generate_batch(pairs, out_dir, title_real="giant", title_generated="cielim")
    print(f"Done → {out_dir}/raw and {out_dir}/aligned")
