"""Real-vs-generated image comparison plots.

Per image pair we emit three things: a **side-by-side view** of the two compared frames (so the
actual images can be eyeballed, not just their statistics), an intensity **histogram**, and a
difference **heatmap**. Cross-correlation and background masking are preprocessing toggles, not
figures: a batch is rendered in three variants so they can be compared side by side —

  * ``raw/``     — frames as-is (any real→generated offset preserved),
  * ``aligned/`` — the generated frame cross-correlated onto the real one,
  * ``masked/``  — aligned, then background zeroed so only the target (union of both frames'
                   foreground, with a small dilation halo) is compared. Particularly useful for
                   small/faint disks, where background pixels would otherwise swamp the statistics.

For a batch of pairs each variant contains the individual side-by-side views, histograms and
heatmaps plus one **average histogram** aggregated across all pairs.

The side-by-side view is framed tightly on the target (so a few-pixel disk isn't lost in dark
space) and labels each panel with that frame's center-of-brightness pixel, so the target's location
can be compared directly between real and cielim.

Colormap convention (see plot_style): numerical figures (heatmaps, histograms) use inferno; scene
images shown for viewing use grayscale.
"""

from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

from cielim.utils import plot_style as ps

THRESHOLD = 10

# Region-of-interest cropping (shared by the scenario comparisons). Small, faint disks get a large
# relative pad so they aren't a speck in the frame; large disks get a tight pad. Sub-DISPLAY_SIZE
# crops are upscaled (nearest) so the comparison panels are legible.
PAD_SMALL = 1.4
PAD_LARGE = 0.20
SMALL_THRESHOLD = 50
DISPLAY_SIZE = 300

# Tight framing for the side-by-side view: pad the target by this fraction of its size, but never
# show a window smaller than MIN_FRAME_HALF px each side so a single-pixel disk still gets context.
FRAME_PAD = 0.6
MIN_FRAME_HALF = 6

# Background masking (the ``masked`` variant): keep pixels above THRESHOLD in either frame, grown by
# MASK_DILATE px so the target's faint edge isn't clipped; everything else is zeroed out.
MASK_DILATE = 2

# The three comparison variants and their preprocessing. ``masked`` builds on ``aligned`` because you
# want the target registered before isolating it from the background.
MODES = {
    "raw": {"align": False, "mask": False},
    "aligned": {"align": True, "mask": False},
    "masked": {"align": True, "mask": True},
}


# --- image loading / coercion ------------------------------------------------------------------


def load_grayscale(path):
    return np.array(Image.open(path).convert("L"))


def to_uint8_gray(arr):
    """Normalize an arbitrary 2-D array (e.g. float FITS data) to a 0–255 uint8 grayscale image.

    NaN-safe, contrast-stretched on the 1st–99th percentile so a few hot/dead pixels don't crush the
    dynamic range. Matches how the scenarios' _fits_to_png previews the real frames.
    """
    a = np.nan_to_num(np.asarray(arr, dtype=float))
    lo, hi = np.percentile(a, 1), np.percentile(a, 99)
    if hi <= lo:
        lo, hi = float(a.min()), float(a.max())
    if hi <= lo:
        return np.zeros(a.shape, np.uint8)
    return np.clip((a - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)


def _as_gray(img):
    """Coerce an image (path, BGR array, or grayscale array) to a uint8 grayscale array."""
    if isinstance(img, np.ndarray):
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return load_grayscale(img)


def compute_disk_stats(img, threshold=THRESHOLD):
    pixels = img[img > threshold]
    return {
        "pixels": pixels,
        "mean": float(np.mean(pixels)) if pixels.size else 0.0,
        "std": float(np.std(pixels)) if pixels.size else 0.0,
    }


# --- ROI cropping ------------------------------------------------------------------------------


def get_cob_and_bbox(img):
    """Center-of-brightness (cx, cy) and bounding box (w, h) of the brightest connected blob."""
    thresh_val = max(int(img.max()) // 4, 10)
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
    """Choose a crop pad fraction from the object size (large pad for small/faint disks)."""
    _, _, bw, bh = get_cob_and_bbox(img)
    obj_size = max(bw, bh)
    pad = PAD_SMALL if obj_size < SMALL_THRESHOLD else PAD_LARGE
    return pad, obj_size


def _crop_box(img, pad_frac=None):
    """Return the (x1, x2, y1, y2) ROI box around the target's center-of-brightness."""
    if pad_frac is None:
        pad_frac, _ = detect_pad(img)
    cx, cy, bw, bh = get_cob_and_bbox(img)
    if max(bw, bh) == 0:  # no disk detected — keep the whole frame
        return 0, img.shape[1], 0, img.shape[0]
    pad = int(max(bw, bh) * pad_frac)
    half = max(bw, bh) // 2 + pad
    return max(cx - half, 0), min(cx + half, img.shape[1]), max(cy - half, 0), min(cy + half, img.shape[0])


def _upscale_small(crop):
    if crop.size and max(crop.shape) < DISPLAY_SIZE:
        return np.array(Image.fromarray(crop).resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.NEAREST))
    return crop


def crop_roi(img, pad_frac=None):
    """Crop a square ROI around the target's own center-of-brightness (auto pad if not given)."""
    x1, x2, y1, y2 = _crop_box(img, pad_frac)
    return _upscale_small(img[y1:y2, x1:x2])


def crop_pair(real, generated):
    """Crop ``real`` and ``generated`` with the SAME window (taken from the real frame's ROI).

    Cropping each image on its own center-of-brightness would silently cancel any real-vs-generated
    offset, making the un-aligned comparison meaningless. Using one common window instead preserves
    that offset so the raw heatmap shows it and cross-correlation (the aligned variant) can register
    it. The generated frame is first resized to the real frame's resolution.
    """
    real, generated = match_shapes(real, generated)
    x1, x2, y1, y2 = _crop_box(real)
    return _upscale_small(real[y1:y2, x1:x2]), _upscale_small(generated[y1:y2, x1:x2])


# --- registration (cross-correlation) ----------------------------------------------------------


def match_shapes(img1, img2):
    if img1.shape != img2.shape:
        img2 = np.array(Image.fromarray(img2).resize((img1.shape[1], img1.shape[0]), Image.BILINEAR))
    return img1, img2


def cross_correlate_fft(img1, img2):
    i1 = img1.astype(float) - img1.mean()
    i2 = img2.astype(float) - img2.mean()
    corr = np.fft.ifftshift(np.real(np.fft.ifft2(np.fft.fft2(i1) * np.conj(np.fft.fft2(i2)))))
    peak = np.unravel_index(np.argmax(corr), corr.shape)
    shift_y = peak[0] - corr.shape[0] // 2
    shift_x = peak[1] - corr.shape[1] // 2
    return shift_y, shift_x, corr


def apply_shift(img, shift_y, shift_x):
    return np.roll(np.roll(img, shift_y, axis=0), shift_x, axis=1)


def align_pair(real, generated):
    """Register ``generated`` onto ``real`` by integer-pixel FFT cross-correlation. Both grayscale."""
    real, generated = match_shapes(real, generated)
    shift_y, shift_x, _ = cross_correlate_fft(real, generated)
    return apply_shift(generated, shift_y, shift_x)


# --- background masking ------------------------------------------------------------------------


def foreground_mask(img1, img2, threshold=THRESHOLD, dilate=MASK_DILATE):
    """Boolean target mask: pixels above ``threshold`` in *either* frame, grown by ``dilate`` px.

    The union keeps a pixel that is bright in one frame but dark in the other (exactly the real-vs-
    generated discrepancies worth seeing); the dilation adds a small halo so the target's faint edge
    survives instead of being cropped to the hard threshold.
    """
    m = (img1 > threshold) | (img2 > threshold)
    if dilate:
        k = np.ones((2 * dilate + 1, 2 * dilate + 1), np.uint8)
        m = cv2.dilate(m.astype(np.uint8), k).astype(bool)
    return m


def apply_mask(img, mask):
    """Zero every pixel outside ``mask`` (background), leaving the target untouched."""
    out = np.zeros_like(img)
    out[mask] = img[mask]
    return out


def compare_saved(
    generated_dir,
    gen_time,
    real_entries,
    real_reader,
    output_dir,
    title_real="real",
    title_generated="cielim",
    tol_s=2.0,
    pattern="*.png",
):
    """Read the saved generated images, pair each with the real frame taken at the same time, and
    run :func:`generate_batch` on the result.

    Comparing the images **as written to disk** (rather than an in-memory array) guarantees the exact
    saved orientation/flip is what gets compared. Pairing is by observation time, read from each
    file's name/header — not by list position.

    Args:
        generated_dir: directory of saved generated images named with a timestamp.
        gen_time(path) -> float | None: time parsed from a generated filename (same scale as
            ``real_entries``, i.e. SPICE ephemeris seconds).
        real_entries: list of ``(time, real_path)``.
        real_reader(path) -> uint8 grayscale array: load a real frame from its path.
        tol_s: max |time difference| for a match.

    Returns the number of matched pairs.
    """
    real_times = [e[0] for e in real_entries]
    pairs = []
    for gp in sorted(Path(generated_dir).glob(pattern)):
        t = gen_time(gp)
        if t is None:
            continue
        j = nearest_time_index(t, real_times, tol_s)
        if j is None:
            continue
        pairs.append((real_reader(real_entries[j][1]), load_grayscale(gp)))
    generate_batch(pairs, output_dir, title_real=title_real, title_generated=title_generated)
    return len(pairs)


def nearest_time_index(target_et, ets, tol_s=None):
    """Index into ``ets`` whose time is closest to ``target_et`` (all in SPICE ephemeris seconds).

    Used to pair a generated frame (rendered at a known time) with the real image taken at the same
    time, rather than by list position. Returns None if ``ets`` is empty or the closest match is
    farther than ``tol_s`` seconds (when a tolerance is given).
    """
    if len(ets) == 0:
        return None
    diffs = np.abs(np.asarray(ets, dtype=float) - float(target_et))
    j = int(np.argmin(diffs))
    if tol_s is not None and diffs[j] > tol_s:
        return None
    return j


# --- individual plots --------------------------------------------------------------------------


def _frame_box(img, cx, cy, obj_size):
    """Tight square window around ``(cx, cy)`` for the side-by-side view (no big dark border)."""
    half = max(int((obj_size / 2) * (1 + FRAME_PAD)), MIN_FRAME_HALF)
    h, w = img.shape
    return max(cx - half, 0), min(cx + half, w), max(cy - half, 0), min(cy + half, h)


def plot_side_by_side(real, generated, title1="real", title2="cielim", mask=False):
    """Grayscale side-by-side of the two compared frames, tightly framed on the target.

    Both panels share one tight window (centered between the two targets and sized to enclose both),
    so any real→generated location offset stays visible instead of each frame being re-centered on
    its own disk. Each panel is labeled with, and marked at, that frame's center-of-brightness pixel
    ``(cx, cy)`` in the common frame — so the target's position can be read off and compared even
    when the disk is only a few pixels across. With ``mask`` the background is zeroed first.
    """
    ps.apply_showcase_style()
    real, generated = match_shapes(real, generated)
    rcx, rcy, rbw, rbh = get_cob_and_bbox(real)
    gcx, gcy, gbw, gbh = get_cob_and_bbox(generated)
    if mask:
        fg = foreground_mask(real, generated)
        real, generated = apply_mask(real, fg), apply_mask(generated, fg)

    # One window enclosing both targets and their separation, so the offset is in-frame for both.
    obj = max(rbw, rbh, gbw, gbh, abs(gcx - rcx) * 2, abs(gcy - rcy) * 2)
    x1, x2, y1, y2 = _frame_box(real, (rcx + gcx) // 2, (rcy + gcy) // 2, obj)
    extent = [x1 - 0.5, x2 - 0.5, y2 - 0.5, y1 - 0.5]  # bottom=y2, top=y1 keeps image orientation

    fig, axes = plt.subplots(1, 2, figsize=ps.figsize_pair(aspect=0.6))
    fig.suptitle("Compared frames", fontweight="bold")
    for ax, img, (cx, cy), title in (
        (axes[0], real, (rcx, rcy), title1),
        (axes[1], generated, (gcx, gcy), title2),
    ):
        ax.imshow(img[y1:y2, x1:x2], cmap=ps.SCENE_CMAP, extent=extent, interpolation="nearest", vmin=0, vmax=255)
        ax.plot(cx, cy, "+", color=ps.SERIES_COLORS[1], markersize=10, markeredgewidth=1.5)
        ax.set_title(f"{title}\ncenter (px): ({cx}, {cy})")
        ax.set_xlabel("x (px)")
        ax.set_ylabel("y (px)")
    plt.tight_layout()
    return fig


def plot_histogram(img1, img2, title1="real", title2="cielim", bins=256, mask=None):
    """Overlaid pixel-intensity histograms of two images, with each disk's mean marked.

    When ``mask`` (a boolean foreground array) is given, only those pixels are counted, so a masked
    comparison isn't dominated by the huge background-zero bin.
    """
    ps.apply_showcase_style()
    c1, c2 = ps.SERIES_COLORS

    v1 = img1[mask] if mask is not None else img1.flatten()
    v2 = img2[mask] if mask is not None else img2.flatten()
    centers = (np.linspace(0, 255, bins + 1)[:-1] + np.linspace(0, 255, bins + 1)[1:]) / 2
    counts1, _ = np.histogram(v1, bins=bins, range=(0, 255))
    counts2, _ = np.histogram(v2, bins=bins, range=(0, 255))
    m1 = compute_disk_stats(img1)["mean"]
    m2 = compute_disk_stats(img2)["mean"]

    fig, ax = plt.subplots(figsize=ps.figsize_single(aspect=0.55))
    fig.suptitle("Pixel intensity histogram", fontweight="bold")
    ax.fill_between(centers, counts1, step="mid", alpha=0.45, color=c1, label=title1)
    ax.fill_between(centers, counts2, step="mid", alpha=0.45, color=c2, label=title2)
    ax.axvline(m1, color=c1, linestyle="--", linewidth=1.5, label=f"{title1} mean {m1:.0f}")
    ax.axvline(m2, color=c2, linestyle="--", linewidth=1.5, label=f"{title2} mean {m2:.0f}")

    ax.set_yscale("log")
    ax.set_xlim(0, 255)
    ax.set_xlabel("Pixel intensity (0–255)")
    ax.set_ylabel("Pixel count (log)")
    ax.legend()
    plt.tight_layout()
    return fig


def plot_diff_heatmap(img1, img2, title1="real", title2="cielim"):
    """Signed pixel-difference heatmap (img1 − img2) on the inferno ramp."""
    ps.apply_showcase_style()
    img1, img2 = match_shapes(img1, img2)
    mask = (img1 > THRESHOLD) | (img2 > THRESHOLD)
    diff = np.zeros_like(img1, dtype=float)
    diff[mask] = img1[mask].astype(float) - img2[mask].astype(float)

    fig, ax = plt.subplots(figsize=ps.figsize_single(aspect=0.85))
    fig.suptitle(f"Difference heatmap — {title1} minus {title2}", fontweight="bold")
    im = ax.imshow(diff, cmap="inferno", vmin=-128, vmax=128)
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(f"Intensity difference ({title1} − {title2})")
    ax.set_title(f"bright = {title1} brighter  |  dark = {title2} brighter")
    ax.axis("off")
    plt.tight_layout()
    return fig


def plot_average_histogram(cropped_pairs, title1="real", title2="cielim", bins=256, drop_zero_bin=False):
    """Average intensity histogram across a batch of (real, generated) grayscale pairs.

    Pairs are expected already aligned/masked (see :func:`generate_batch`). Each frame's histogram is
    normalized to a per-bin pixel *fraction* (so different crop sizes are comparable), then averaged
    across the batch; the shaded band is ±1σ across the batch. With ``drop_zero_bin`` the intensity-0
    bin is discarded before normalizing — for the masked variant, whose background is zeroed, this
    keeps the average from collapsing onto that one dominant bin.
    """
    ps.apply_showcase_style()
    c1, c2 = ps.SERIES_COLORS
    centers = (np.linspace(0, 255, bins + 1)[:-1] + np.linspace(0, 255, bins + 1)[1:]) / 2

    def fractions(img):
        counts, _ = np.histogram(img.flatten(), bins=bins, range=(0, 255))
        if drop_zero_bin:
            counts[0] = 0
        return counts / max(counts.sum(), 1)

    real_frac, gen_frac = [], []
    for real, gen in cropped_pairs:
        real_frac.append(fractions(real))
        gen_frac.append(fractions(gen))
    real_frac = np.array(real_frac)
    gen_frac = np.array(gen_frac)
    rm, rs = real_frac.mean(0), real_frac.std(0)
    gm, gs = gen_frac.mean(0), gen_frac.std(0)

    fig, ax = plt.subplots(figsize=ps.figsize_single(aspect=0.55))
    fig.suptitle(f"Average intensity histogram — batch of {len(cropped_pairs)}", fontweight="bold")
    ax.plot(centers, rm, color=c1, label=title1)
    ax.fill_between(centers, np.clip(rm - rs, 0, None), rm + rs, color=c1, alpha=0.2)
    ax.plot(centers, gm, color=c2, label=title2)
    ax.fill_between(centers, np.clip(gm - gs, 0, None), gm + gs, color=c2, alpha=0.2)

    ax.set_yscale("log")
    ax.set_xlim(0, 255)
    ax.set_xlabel("Pixel intensity (0–255)")
    ax.set_ylabel("Mean pixel fraction (log)")
    ax.legend()
    plt.tight_layout()
    return fig


# --- batch driver ------------------------------------------------------------------------------


def generate_batch(pairs, output_dir, title_real="real", title_generated="cielim", modes=("raw", "aligned", "masked")):
    """Emit the comparison set for a batch of (real, generated) image pairs.

    ``pairs`` is a list of (real, generated); each item may be a path, a BGR array, or a grayscale
    array. Both sides are coerced to grayscale and the generated frame resized onto the real one. For
    every mode in ``modes`` (default: ``"raw"``, ``"aligned"``, ``"masked"`` — see the module
    docstring) a subdirectory is written containing per-pair ``images_NN.png`` (side-by-side view),
    ``histogram_NN.png`` and ``heatmap_NN.png`` plus one ``histogram_average.png``.
    """
    ps.apply_showcase_style()
    output_dir = Path(output_dir)

    # Full-resolution matched grayscale pairs, kept for the side-by-side view so its pixel-coordinate
    # annotations are in the true image frame; the numeric figures use a padded ROI crop of the pair.
    full = [match_shapes(_as_gray(r), _as_gray(g)) for r, g in pairs]
    if not full:
        return

    for mode in modes:
        cfg = MODES[mode]
        mode_dir = output_dir / mode
        mode_dir.mkdir(parents=True, exist_ok=True)

        cropped = []  # collected for the batch-average histogram
        for i, (real, gen) in enumerate(full):
            gg = align_pair(real, gen) if cfg["align"] else gen

            # The two compared frames, saved together as one tightly-framed side-by-side view.
            fig = plot_side_by_side(real, gg, title_real, title_generated, mask=cfg["mask"])
            fig.savefig(mode_dir / f"images_{i:02d}.png", dpi=ps.SAVE_DPI, bbox_inches="tight")
            plt.close(fig)

            # ROI crop (common window preserves any offset); zero the background for the masked mode.
            rc, gc = crop_pair(real, gg)
            fg = foreground_mask(rc, gc) if cfg["mask"] else None
            if fg is not None:
                rc, gc = apply_mask(rc, fg), apply_mask(gc, fg)
            cropped.append((rc, gc))

            fig = plot_histogram(rc, gc, title_real, title_generated, mask=fg)
            fig.savefig(mode_dir / f"histogram_{i:02d}.png", dpi=ps.SAVE_DPI, bbox_inches="tight")
            plt.close(fig)
            fig = plot_diff_heatmap(rc, gc, title_real, title_generated)
            fig.savefig(mode_dir / f"heatmap_{i:02d}.png", dpi=ps.SAVE_DPI, bbox_inches="tight")
            plt.close(fig)

        fig = plot_average_histogram(cropped, title_real, title_generated, drop_zero_bin=cfg["mask"])
        fig.savefig(mode_dir / "histogram_average.png", dpi=ps.SAVE_DPI, bbox_inches="tight")
        plt.close(fig)
