import sys
from pathlib import Path

from cielim.utils import image_comparison_toolkit as image_comparison
from cielim.utils.image_comparison_toolkit import load_grayscale

here = Path(__file__).resolve().parent
cielim_root = here.parent

sys.path.insert(0, str(cielim_root))

base_dir = cielim_root / "support-data" / "giant-vesta"

sessions = [1, 2, 3]


if __name__ == "__main__":
    # GIANT is the reference "real" render, cielim the generated one.
    pairs = []
    for session in sessions:
        cielim_img = base_dir / f"cielim_{session}.png"
        giant_img = base_dir / f"giant_{session}.png"
        if not cielim_img.exists():
            raise FileNotFoundError(f"Missing: {cielim_img}")
        if not giant_img.exists():
            raise FileNotFoundError(f"Missing: {giant_img}")
        pairs.append((load_grayscale(giant_img), load_grayscale(cielim_img)))

    out_dir = base_dir / "comparison_plots"
    stats = image_comparison.generate_batch(pairs, out_dir, title_real="giant", title_generated="cielim")
    print(f"Done → {out_dir}/raw and {out_dir}/aligned")
    print(image_comparison.format_error_stats(stats, title_real="giant"))
