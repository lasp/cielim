"""Real-vs-generated image comparison plots.

Per image pair we emit three things: a **side-by-side view** of the two compared frames (so the
actual images can be eyeballed, not just their statistics), an intensity **histogram**, and a
difference **heatmap**. Cross-correlation and background masking are preprocessing toggles, not
figures: a batch is rendered in three variants so they can be compared side by side —

  * ``raw/``     — frames as-is (any real→generated offset preserved),
  * ``aligned/`` — the generated frame cross-correlated onto the real one,
  * ``masked/``  — (opt-in, off by default) aligned, then background zeroed so only the target (union
                   of both frames' foreground, with a small dilation halo) is compared. Useful for
                   small/faint disks; enable by passing ``modes=(..., "masked")`` to generate_batch.

For a batch of pairs each variant contains the individual side-by-side views, histograms and
heatmaps plus one **average histogram** aggregated across all pairs.

The side-by-side view is framed tightly on the target (so a few-pixel disk isn't lost in dark space)
and shows both panels bare — no axes, no markers — so only the imagery is compared. The annotated
view, with located peaks and the SPICE-predicted pixel, is plot_point_source_pair, for targets too
small to judge by eye.

Colormap convention (see plot_style): histograms use inferno-sampled series colors; the signed
difference heatmap uses a zero-centered diverging ramp (black = match, see DIFF_CMAP); scene images
shown for viewing use grayscale.
"""

from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from PIL import Image

from cielim.utils import plot_style as ps

THRESHOLD = 10

# Diverging colormap for the signed difference heatmap, centered on BLACK at zero so a perfect match
# is unmistakable. Both directions use the inferno ramp emanating from black — inferno for positive
# error, the mirror (reversed inferno) for negative — so the hue stays in the inferno family and
# brightness grows with the mismatch. Because the two halves share the ramp, color encodes the
# *magnitude* of the difference, not its sign (a large +err and a large -err are both bright yellow).
# The near-zero background falls at the black center on its own (the heatmap compares every pixel, no
# masking); set_bad black is just a safety for any NaN so it too blends with the zero-error center.
_INFERNO = plt.get_cmap("inferno")
DIFF_CMAP = ListedColormap(
    np.vstack([_INFERNO(np.linspace(1, 0, 128)), _INFERNO(np.linspace(0, 1, 128))]), name="diff_inferno"
)
DIFF_CMAP.set_bad("black")

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


def to_uint8_gray(arr, lo_pct=1, hi_pct=99):
    """Normalize an arbitrary 2-D array (e.g. float FITS data) to a 0–255 uint8 grayscale image.

    NaN-safe, contrast-stretched between the ``lo_pct`` and ``hi_pct`` percentiles. The default
    1st–99th percentile keeps a few hot/dead pixels from crushing the dynamic range. Pass
    ``lo_pct=0, hi_pct=100`` for a plain min/max stretch — the look the saved imsave PNG previews had
    (which preserves a resolved disk's gradient instead of clipping it to a white blob), but computed
    in-memory, so there's no colormap round-trip punching holes in the 8-bit histogram.
    """
    a = np.nan_to_num(np.asarray(arr, dtype=float))
    lo, hi = np.percentile(a, lo_pct), np.percentile(a, hi_pct)
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
    average_exclude=None,
    average_batches=None,
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
        average_exclude, average_batches: forwarded to :func:`generate_batch` (drop indices from the
            overall average / write extra labelled sub-batch averages). Indices are pair positions in
            the sorted-by-time order, i.e. the same NN as ``histogram_NN`` / ``images_NN``.

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
        real_path = real_entries[j][1]
        pairs.append((real_reader(real_path), load_grayscale(gp)))
    generate_batch(
        pairs,
        output_dir,
        title_real=title_real,
        title_generated=title_generated,
        average_exclude=average_exclude,
        average_batches=average_batches,
    )
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
    its own disk. The frames are shown bare: no markers and no axes, so nothing overlays the imagery
    being compared (:func:`plot_point_source_pair` is the annotated view, for targets too small to
    judge by eye). No titles (left = real, right = generated by convention); with ``mask`` the
    background is zeroed first.
    """
    ps.apply_showcase_style()
    real, generated = match_shapes(real, generated)
    rcx, rcy, rbw, rbh = get_cob_and_bbox(real)
    gcx, gcy, gbw, gbh = get_cob_and_bbox(generated)
    if mask:
        fg = foreground_mask(real, generated)
        real, generated = apply_mask(real, fg), apply_mask(generated, fg)

    # One window enclosing both targets so neither is cropped by the other's framing.
    cx0, cy0 = (rcx + gcx) // 2, (rcy + gcy) // 2
    marks = [(rcx, rcy), (gcx, gcy)]
    reach = max([max(rbw, rbh, gbw, gbh)] + [2 * abs(mx - cx0) for mx, my in marks] + [2 * abs(my - cy0) for mx, my in marks])
    x1, x2, y1, y2 = _frame_box(real, cx0, cy0, reach)
    extent = [x1 - 0.5, x2 - 0.5, y2 - 0.5, y1 - 0.5]  # bottom=y2, top=y1 keeps image orientation

    fig, axes = plt.subplots(1, 2, figsize=ps.figsize_pair())  # full text width, two HALF_W panels
    for ax, img in ((axes[0], real), (axes[1], generated)):
        ax.imshow(img[y1:y2, x1:x2], cmap=ps.SCENE_CMAP, extent=extent, interpolation="nearest", vmin=0, vmax=255)
        ax.set_axis_off()  # no ticks/labels — the panels are the imagery only
    fig.tight_layout()
    return fig


def locate_peak(img, center, search=15, blur=1.0):
    """Pixel ``(x, y)`` of the brightest spot within ±``search`` px of ``center``.

    A light Gaussian blur is applied first so a single noisy/hot pixel doesn't win — for locating a
    compact source near a known/expected position (e.g. a distant object at its SPICE-predicted pixel)
    without being fooled by field stars or render speckle elsewhere in the frame.
    """
    cx, cy = int(round(center[0])), int(round(center[1]))
    h, w = img.shape
    x0, x1 = max(cx - search, 0), min(cx + search + 1, w)
    y0, y1 = max(cy - search, 0), min(cy + search + 1, h)
    win = img[y0:y1, x0:x1].astype(float)
    if blur:
        win = cv2.GaussianBlur(win, (0, 0), blur)
    py, px = np.unravel_index(int(np.argmax(win)), win.shape)
    return x0 + int(px), y0 + int(py)


def _aperture_sum(img, cx, cy, r):
    """(summed, peak) intensity in a ±r px box around (cx, cy)."""
    sub = img[max(cy - r, 0):cy + r + 1, max(cx - r, 0):cx + r + 1].astype(float)
    return float(sub.sum()), float(sub.max())


def project_to_pixel(position, world_to_cam, fov, resolution, flip_x=False, flip_y=False):
    """Pixel where a target at the WORLD ORIGIN projects for a pinhole camera at ``position``.

    ``world_to_cam`` is the 3x3 world→camera-frame rotation (camera +z = boresight). Reproduces
    cielim's reversed-Z projection — NDC = (cot(fovx/2)·x/z, cot(fovy/2)·y/z), pixel =
    ((1+NDCx)/2·W, (1+NDCy)/2·H) — and mirrors the result when the scenario saved a flipped image
    (``flip_x`` for np.flip(image, 1), ``flip_y`` for axis 0). Validated against cielim's rendered
    Bennu peak to sub-pixel. ``fov`` is (fovx, fovy) in radians, ``resolution`` is (W, H). Returns
    (px, py) floats; the object's own extent/attitude is not modeled (center only).
    """
    d = np.asarray(world_to_cam, float) @ (-np.asarray(position, float))
    d = d / np.linalg.norm(d)
    w, h = resolution
    px = (1 + (d[0] / d[2]) / np.tan(fov[0] / 2)) / 2 * w
    py = (1 + (d[1] / d[2]) / np.tan(fov[1] / 2)) / 2 * h
    if flip_x:
        px = w - 1 - px
    if flip_y:
        py = h - 1 - py
    return px, py


def plot_point_source_pair(
    real, generated, real_anchor, gen_anchor=None, predicted_xy=None,
    search=15, zoom=25, aperture=6, title_real="real", title_generated="cielim",
):
    """Zoomed real-vs-generated comparison of a compact bright object near a known position.

    For distant-object frames where the target is only a few pixels and ordinary brightest-blob
    detection would grab a field star or render noise. The object is located in each image as the
    brightest lightly-blurred pixel within ±``search`` px of an anchor (see :func:`locate_peak`):
    ``real_anchor`` for the real frame and ``gen_anchor`` for the generated one (defaults to
    ``real_anchor``). Give them separately when the two are expected to sit apart — e.g. the real
    object at its measured/header centroid and cielim's at the SPICE-projected pixel.

    Both panels share one ±``zoom`` px window centered on the real object's peak. Each panel is marked
    with its located peak (orange +); if ``predicted_xy`` is given (the SPICE/ephemeris-projected
    pixel, e.g. from :func:`project_to_pixel`) it is drawn on both panels (cyan ○). The generated
    panel's + should sit on the ○ — cielim placing the object where SPICE asked — while any gap
    between the ○ and the real + is the ephemeris/pointing discrepancy, which is expected and does not
    indict cielim's placement.

    No titles (left = real, right = generated by convention). Returns ``(fig, info)`` where ``info``
    has the located peaks (``real_xy``, ``gen_xy``), ``offset`` (cielim − real, px), the ``predicted``
    pixel (or None), and the ±``aperture`` box sums (``real_flux``, ``gen_flux``). Intensities are in
    display (stretch) units, not calibrated radiometry — an apparent size/brightness cue only.
    """
    ps.apply_showcase_style()
    real, generated = match_shapes(real, generated)
    if gen_anchor is None:
        gen_anchor = real_anchor
    rx, ry = locate_peak(real, real_anchor, search)
    gx, gy = locate_peak(generated, gen_anchor, search)
    pred = None if predicted_xy is None else (int(round(predicted_xy[0])), int(round(predicted_xy[1])))

    h, w = real.shape
    x1, x2 = max(rx - zoom, 0), min(rx + zoom, w)
    y1, y2 = max(ry - zoom, 0), min(ry + zoom, h)
    extent = [x1 - 0.5, x2 - 0.5, y2 - 0.5, y1 - 0.5]  # bottom=y2, top=y1 keeps image orientation

    fig, axes = plt.subplots(1, 2, figsize=ps.figsize_pair())
    fluxes = []
    for ax, img, (px, py) in ((axes[0], real, (rx, ry)), (axes[1], generated, (gx, gy))):
        flux, _ = _aperture_sum(img, px, py, aperture)
        fluxes.append(flux)
        ax.imshow(img[y1:y2, x1:x2], cmap=ps.SCENE_CMAP, extent=extent, interpolation="nearest", vmin=0, vmax=255)
        if pred is not None:
            ax.plot(*pred, "o", mfc="none", mec="#00d0ff", markersize=13, markeredgewidth=1.5)  # SPICE-predicted
        ax.plot(px, py, "+", color=ps.SERIES_COLORS[1], markersize=12, markeredgewidth=1.5)  # located peak
        ax.set_xlabel("x (px)")
        ax.set_ylabel("y (px)")
    fig.tight_layout()
    info = {"real_xy": (rx, ry), "gen_xy": (gx, gy), "offset": (gx - rx, gy - ry),
            "predicted": pred, "real_flux": fluxes[0], "gen_flux": fluxes[1]}
    return fig, info


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

    fig, ax = plt.subplots(figsize=ps.figsize_full())
    ax.fill_between(centers, counts1, step="mid", alpha=0.45, color=c1, label=title1)
    ax.fill_between(centers, counts2, step="mid", alpha=0.45, color=c2, label=title2)
    ax.axvline(m1, color=c1, linestyle="--", linewidth=1.5, label=f"{title1} mean {m1:.0f}")
    ax.axvline(m2, color=c2, linestyle="--", linewidth=1.5, label=f"{title2} mean {m2:.0f}")

    ax.set_yscale("log")
    ax.set_xlim(0, 255)
    ax.set_xlabel("Pixel intensity (0–255)")
    ax.set_ylabel("Pixel count (log)")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_diff_heatmap(img1, img2, title1="real", title2="cielim"):
    """Signed pixel-difference heatmap (img1 − img2) on a zero-centered inferno diverging ramp.

    Uses :data:`DIFF_CMAP`: zero error is black, so matching regions (including the near-zero
    background) are obvious; brightness along the inferno ramp grows with the magnitude of the
    mismatch in both directions (a large +err and a large -err look the same — color encodes
    |difference|, not its sign; read the colorbar for sign). The difference is computed over *every*
    pixel (no THRESHOLD masking) so the background shows its true, near-zero difference.
    """
    ps.apply_showcase_style()
    img1, img2 = match_shapes(img1, img2)
    diff = img1.astype(float) - img2.astype(float)

    # Half text width: one image, printed at the size of a single side-by-side panel (and so two
    # heatmaps, or a heatmap and its pair's view, can sit next to each other on the page).
    fig, ax = plt.subplots(figsize=ps.figsize_half())
    im = ax.imshow(diff, cmap=DIFF_CMAP, vmin=-128, vmax=128)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(f"Difference ({title1} − {title2})")  # short: the label is 10 pt in HALF_W
    ax.axis("off")
    fig.tight_layout()
    return fig


def plot_average_histogram(cropped_pairs, title1="real", title2="cielim", bins=256, drop_zero_bin=False):
    """Average intensity histogram across a batch of (real, generated) grayscale pairs.

    Pairs are expected already aligned/masked (see :func:`generate_batch`). Each frame's histogram is
    normalized to a per-bin pixel *fraction* (so different crop sizes are comparable), then averaged
    across the batch; the shaded band is ±1σ across the batch. With ``drop_zero_bin`` the intensity-0
    bin is discarded before normalizing — for the masked variant, whose background is zeroed, this
    keeps the average from collapsing onto that one dominant bin. Which sub-batch this is (an index
    range) is documented by the caller's filename, not a title.
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

    fig, ax = plt.subplots(figsize=ps.figsize_full())
    ax.plot(centers, rm, color=c1, label=title1)
    ax.fill_between(centers, np.clip(rm - rs, 0, None), rm + rs, color=c1, alpha=0.2)
    ax.plot(centers, gm, color=c2, label=title2)
    ax.fill_between(centers, np.clip(gm - gs, 0, None), gm + gs, color=c2, alpha=0.2)

    ax.set_yscale("log")
    ax.set_xlim(0, 255)
    ax.set_xlabel("Pixel intensity (0–255)")
    ax.set_ylabel("Mean pixel fraction (log)")
    ax.legend()
    fig.tight_layout()
    return fig


# --- batch driver ------------------------------------------------------------------------------


def generate_batch(
    pairs,
    output_dir,
    title_real="real",
    title_generated="cielim",
    modes=("raw", "aligned"),
    average_exclude=None,
    average_batches=None,
):
    """Emit the comparison set for a batch of (real, generated) image pairs.

    ``pairs`` is a list of (real, generated); each item may be a path, a BGR array, or a grayscale
    array. Both sides are coerced to grayscale and the generated frame resized onto the real one. For
    every mode in ``modes`` (default: ``"raw"``, ``"aligned"``; pass ``"masked"`` too to also emit the
    background-zeroed variant — see the module docstring) a subdirectory is written containing per-pair
    ``images_NN.png`` (side-by-side view),
    ``histogram_NN.png`` and ``heatmap_NN.png`` plus one overall ``histogram_average.png``.

    ``average_exclude`` is an iterable of pair indices to drop from the overall average (their
    individual per-pair figures are still written). ``average_batches`` is an optional list of
    ``(label, indices)`` sub-batches; each writes an extra ``histogram_average_<label>.png`` averaged
    over just those indices (also respecting ``average_exclude``). The overall average is always
    written, so sub-batches are additive.
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
            ps.save_figure(fig, mode_dir / f"images_{i:02d}.png")
            plt.close(fig)

            # ROI crop (common window preserves any offset); zero the background for the masked mode.
            rc, gc = crop_pair(real, gg)
            fg = foreground_mask(rc, gc) if cfg["mask"] else None
            if fg is not None:
                rc, gc = apply_mask(rc, fg), apply_mask(gc, fg)
            cropped.append((rc, gc))

            fig = plot_histogram(rc, gc, title_real, title_generated, mask=fg)
            ps.save_figure(fig, mode_dir / f"histogram_{i:02d}.png")
            plt.close(fig)
            fig = plot_diff_heatmap(rc, gc, title_real, title_generated)
            ps.save_figure(fig, mode_dir / f"heatmap_{i:02d}.png")
            plt.close(fig)

        exclude = set(average_exclude or ())

        def _avg(indices, suffix):
            sel = [cropped[i] for i in indices if 0 <= i < len(cropped) and i not in exclude]
            if not sel:
                return
            fig = plot_average_histogram(sel, title_real, title_generated, drop_zero_bin=cfg["mask"])
            ps.save_figure(fig, mode_dir / f"histogram_average{suffix}.png")
            plt.close(fig)

        _avg(range(len(cropped)), "")  # overall average (respecting average_exclude)
        for label, indices in average_batches or []:
            _avg(indices, f"_{label}")  # the label documents the sub-batch in the filename
