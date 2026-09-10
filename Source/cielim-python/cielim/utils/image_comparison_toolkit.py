"""Real-vs-generated image comparison plots.

Per image pair we emit one **comparison row** — the real frame, the cielim frame and their
difference **heatmap** as three separate files, so a document can lay them out as a single row of
panels — plus an intensity **histogram**. Every file in the row is written :data:`PANEL_PX` pixels
tall and tagged with a print size that makes the three of them span the text width together, so the
row lines up and needs no scaling:

.. code-block:: latex

    \\begin{figure}
      \\includegraphics{raw/real_00}\\hfill
      \\includegraphics{raw/cielim_00}\\hfill
      \\includegraphics{raw/heatmap_00}
      \\caption{Real, cielim, and their signed difference (real - cielim).}
    \\end{figure}

Cross-correlation and background masking are preprocessing toggles, not
figures: a batch is rendered in three variants so they can be compared side by side —

  * ``raw/``     — frames as-is (any real→generated offset preserved),
  * ``aligned/`` — the generated frame cross-correlated onto the real one,
  * ``masked/``  — (opt-in, off by default) aligned, then background zeroed so only the target (union
                   of both frames' foreground, with a small dilation halo) is compared. Useful for
                   small/faint disks; enable by passing ``modes=(..., "masked")`` to generate_batch.

For a batch of pairs each variant contains the individual rows and histograms plus one **average
histogram** aggregated across all pairs. Every heatmap is captioned with the mean and standard
deviation of the pixel error it shows (real - generated, so positive = the render is too dark), and
the same numbers are tabulated per frame and per average batch in ``pixel_error_frames.csv`` /
``pixel_error_average.csv`` (see :func:`pixel_error_stats`), so the agreement can be quoted as a
number and not only read off a picture.

The two image panels share ONE window, framed tightly on the target (so a few-pixel disk isn't lost
in dark space) and identical between them, so a real→generated offset stays visible instead of each
frame being re-centered on its own disk. They are written bare — just the pixels, no axes, no
markers, no resampling blur — so only the imagery is compared. The annotated view, with located
peaks and the SPICE-predicted pixel, is plot_point_source_pair, for targets too small to judge by
eye.

Colormap convention (see plot_style): histograms use inferno-sampled series colors; the signed
difference heatmap uses a zero-centered diverging ramp (black = match, see DIFF_CMAP); scene images
shown for viewing use grayscale.
"""

import re
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

# --- comparison row geometry -------------------------------------------------------------------
# Each pair is emitted as three files meant to sit in ONE row of a LaTeX figure:
# real_NN | cielim_NN | heatmap_NN. Every one is written PANEL_PX pixels tall, so the row lines up
# whichever way it is placed, and each is tagged with the print size that makes the three of them
# span the text width at scale 1.0 (no \includegraphics scaling, so 12 pt stays 12 pt).
#
#   PAGE_W = 2 * ROW_PANEL_H  +  HEATMAP_ASPECT * ROW_PANEL_H
#            \_ the two square image panels _/    \_ heatmap: square + its colorbar _/
PANEL_PX = 1024
HEATMAP_ASPECT = 1.4  # heatmap width / height: 1 for the square image + 0.4 for the colorbar strip
ROW_PANEL_H = ps.PAGE_W / (2 + HEATMAP_ASPECT)

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


def _slug(text):
    """Filename-safe lowercase token from a panel title (``"cielim"`` -> ``cielim``)."""
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "panel"


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
            the sorted-by-time order, i.e. the same NN as ``histogram_NN`` / ``heatmap_NN``.

    Returns ``(number of matched pairs, error stats)``, the stats being what :func:`generate_batch`
    returns — pass them to :func:`format_error_stats` to report the mean error and its std.
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
    stats = generate_batch(
        pairs,
        output_dir,
        title_real=title_real,
        title_generated=title_generated,
        average_exclude=average_exclude,
        average_batches=average_batches,
    )
    return len(pairs), stats


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


def frame_pair(real, generated, mask=False):
    """Crop ``real`` and ``generated`` to ONE tight window around the target, ready to save.

    The window is centered between the two targets and sized to enclose both, so any real→generated
    location offset stays visible instead of each frame being re-centered on its own disk. Returns
    ``(real_crop, generated_crop)``, identical in shape — the two panels of a comparison row. With
    ``mask`` the background is zeroed first.
    """
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
    return real[y1:y2, x1:x2], generated[y1:y2, x1:x2]


def save_image_panel(img, path, height_in=None):
    """Write one image panel of a comparison row — see :func:`plot_style.save_raster_panel`.

    Same bare-pixels writer, with this module's row geometry as the defaults: :data:`PANEL_PX` tall
    and :data:`ROW_PANEL_H` inches on the page. ``exact_height`` because the row's third file is a
    matplotlib heatmap that can only be sized through its dpi — these two have to match it exactly,
    not land on a convenient whole-pixel multiple.
    """
    height_in = ROW_PANEL_H if height_in is None else height_in
    return ps.save_raster_panel(img, path, height_in, px=PANEL_PX, exact_height=True)


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


def plot_diff_heatmap(img1, img2, title1="real", title2="cielim", mask=None):
    """Signed pixel-difference heatmap (img1 − img2) on a zero-centered inferno diverging ramp.

    Uses :data:`DIFF_CMAP`: zero error is black, so matching regions (including the near-zero
    background) are obvious; brightness along the inferno ramp grows with the magnitude of the
    mismatch in both directions (a large +err and a large -err look the same — color encodes
    |difference|, not its sign; read the colorbar for sign). The difference is computed over *every*
    pixel (no THRESHOLD masking) so the background shows its true, near-zero difference.

    The panel is captioned with the mean and standard deviation of the very pixels it shows
    (:func:`pixel_error_stats`), so the map can be read quantitatively: mean ± σ separates a uniform
    brightness offset from a structural mismatch that averages away. ``mask`` restricts those two
    numbers (not the displayed map) to the target's pixels.
    """
    ps.apply_showcase_style()
    img1, img2 = match_shapes(img1, img2)
    diff = img1.astype(float) - img2.astype(float)
    st = pixel_error_stats(img1, img2, mask)

    # Third panel of a real | cielim | heatmap row: exactly as tall as the two image panels beside
    # it, and wider only by its colorbar strip. The axes are placed explicitly rather than by
    # tight_layout so the diff image spans the FULL figure height — with a margin above and below it
    # the target would render smaller here than in the panels next to it and the row would not read
    # across. The colorbar carries numeric ticks but no label: a rotated label needs more height
    # than the row has, and what the numbers mean (the sign convention, title1 − title2) belongs in
    # the figure's LaTeX caption.
    fig = plt.figure(figsize=(HEATMAP_ASPECT * ROW_PANEL_H, ROW_PANEL_H))
    img_frac = 1.0 / HEATMAP_ASPECT  # square image axes, full height
    ax = fig.add_axes((0.0, 0.0, img_frac, 1.0))
    im = ax.imshow(diff, cmap=DIFF_CMAP, vmin=-128, vmax=128)  # aspect stays equal: never distorted
    ax.axis("off")
    # The mean/σ ride INSIDE the image: the axes fill the canvas, so there is no margin to caption,
    # and the top-left corner of a target-centered crop is background. White on a translucent black
    # box stays legible over both ends of the ramp.
    ax.text(0.02, 0.98, f"μ = {st['mean_error']:+.1f} DN\nσ = {st['std_error']:.1f} DN",
            transform=ax.transAxes, ha="left", va="top", color="white", fontsize=ps.BODY_PT,
            linespacing=1.3, bbox=dict(facecolor="black", edgecolor="none", alpha=0.55, pad=2.5))
    cax = fig.add_axes((img_frac + 0.03, 0.04, 0.035, 0.92))
    fig.colorbar(im, cax=cax)
    return fig


def _bin_centers(bins=256):
    edges = np.linspace(0, 255, bins + 1)
    return (edges[:-1] + edges[1:]) / 2


def _intensity_fractions(img, bins=256, drop_zero_bin=False):
    """One frame's intensity histogram as per-bin pixel *fractions*, so crops of different sizes (and
    the masked variant, whose foreground area varies frame to frame) are directly comparable.

    ``drop_zero_bin`` discards intensity 0 before normalizing — for the masked variant, whose
    background is zeroed, that one bin would otherwise hold nearly every pixel.
    """
    counts, _ = np.histogram(img.flatten(), bins=bins, range=(0, 255))
    if drop_zero_bin:
        counts[0] = 0
    return counts / max(counts.sum(), 1)


def _error_moments(real, gen, mask=None):
    """Raw sums of one pair's per-pixel error ``real - generated``.

    Sums rather than the arrays themselves: a batch is pooled by adding these up, so the batch
    statistics are over every pixel of every frame exactly, with no per-frame arrays kept around and
    no averaging of averages (frames whose crops differ in size would otherwise be weighted wrong).
    ``mask`` (a boolean foreground array) restricts the count to those pixels — for the masked
    variant, where the zeroed background would otherwise pull the mean error toward zero.
    """
    real, gen = match_shapes(real, gen)
    r = real.astype(float)
    g = gen.astype(float)
    r, g = (r[mask], g[mask]) if mask is not None else (r.ravel(), g.ravel())
    err = r - g
    return {"n": int(err.size), "sum_r": float(r.sum()), "sum_g": float(g.sum()),
            "sum_e": float(err.sum()), "sum_e2": float(np.square(err).sum()),
            "sum_abs_e": float(np.abs(err).sum())}


def _stats_from_moments(moments):
    """Turn a list of per-frame :func:`_error_moments` into the reported statistics."""
    n = sum(m["n"] for m in moments)
    if n == 0:
        return {k: 0.0 for k in ("real_mean", "gen_mean", "mean_error", "std_error", "mae", "rmse",
                                 "frame_mean_std")} | {"frames": len(moments), "pixels": 0}
    mean_e = sum(m["sum_e"] for m in moments) / n
    mean_e2 = sum(m["sum_e2"] for m in moments) / n
    frame_means = [m["sum_e"] / m["n"] for m in moments if m["n"]]
    return {
        "frames": len(moments),
        "pixels": n,
        "real_mean": sum(m["sum_r"] for m in moments) / n,
        "gen_mean": sum(m["sum_g"] for m in moments) / n,
        "mean_error": mean_e,
        # Population std over the pixels themselves — the spread of the error map, which is what the
        # heatmap shows. max(., 0) guards the rounding of a variance that is numerically zero.
        "std_error": float(np.sqrt(max(mean_e2 - mean_e**2, 0.0))),
        "mae": sum(m["sum_abs_e"] for m in moments) / n,
        "rmse": float(np.sqrt(mean_e2)),
        # Frame-to-frame scatter of the per-frame mean error: whether the offset is a repeatable bias
        # or varies frame by frame. Zero for a single frame, which has no scatter to report.
        "frame_mean_std": float(np.std(frame_means, ddof=1)) if len(frame_means) > 1 else 0.0,
    }


def pixel_error_stats(real, gen, mask=None):
    """Per-pixel error statistics of ONE (real, generated) pair — the numbers on its heatmap.

    The error is ``real - generated`` at every pixel, the sign convention of the difference heatmap:
    a POSITIVE ``mean_error`` means the render is too dark. ``std_error`` is the spread of that error
    map over its pixels, so mean ± std describes the heatmap directly: a large mean with a small std
    is a uniform brightness offset, a near-zero mean with a large std is a structural mismatch that
    cancels in the average. ``mae``/``rmse`` do not let positive and negative error cancel, so they
    are the ones to quote as accuracy.

    Both frames must be the same window (they are resized onto each other if not). Pass ``mask`` to
    count only the target's pixels.
    """
    return _stats_from_moments([_error_moments(real, gen, mask)])


def batch_pixel_error(pairs, masks=None):
    """Pixel error statistics pooled over a batch of (real, generated) pairs.

    Every pixel of every frame counts once, so the batch mean is the true mean pixel error and not an
    average of per-frame averages. ``masks``, when given, is one foreground array per pair (or None
    for an unmasked pair). ``pairs`` must be non-empty; see :func:`pixel_error_stats` for the meaning
    of each statistic and :func:`format_error_stats` for a printable summary.
    """
    masks = masks if masks is not None else [None] * len(pairs)
    return _stats_from_moments([_error_moments(r, g, m) for (r, g), m in zip(pairs, masks)])


# Columns of the per-mode error CSVs, in order. Kept as constants so the header and the rows cannot
# drift apart, and so a table in the paper can be built straight off them. Every column after the
# first is a key of the stats dict, so the header names the statistic it holds.
FRAME_ERROR_CSV_COLUMNS = ("frame", "pixels", "real_mean", "gen_mean", "mean_error",
                           "std_error", "mae", "rmse")
BATCH_ERROR_CSV_COLUMNS = ("batch", "frames", "pixels", "real_mean", "gen_mean", "mean_error",
                           "std_error", "mae", "rmse", "frame_mean_std")


def _error_csv(columns, rows):
    """CSV text for ``rows`` of ``(label, stats)``, one column per name in ``columns``."""
    out = [",".join(columns)]
    for label, st in rows:
        values = [label] + [f"{st[c]:.4f}" if isinstance(st[c], float) else str(st[c])
                            for c in columns[1:]]
        out.append(",".join(values))
    return "\n".join(out) + "\n"


def format_error_stats(stats, title_real="real", title_generated="cielim"):
    """One printable line per batch of the nested ``{mode: {label: stats}}`` :func:`generate_batch`
    returns, for a scenario to echo after it writes its comparison set."""
    lines = []
    for mode, batches in stats.items():
        for label, st in batches.items():
            lines.append(
                f"  {mode}/{label}: mean pixel error ({title_real} − {title_generated}) = "
                f"{st['mean_error']:+.2f} ± {st['std_error']:.2f} DN over {st['frames']} frames "
                f"({st['pixels']} px), MAE {st['mae']:.2f}, RMSE {st['rmse']:.2f} DN, "
                f"frame-to-frame scatter {st['frame_mean_std']:.2f} DN"
            )
    return "\n".join(lines)


def plot_average_histogram(cropped_pairs, title1="real", title2="cielim", bins=256, drop_zero_bin=False,
                           error_stats=None):
    """Average intensity histogram across a batch of (real, generated) grayscale pairs.

    Pairs are expected already aligned/masked (see :func:`generate_batch`). Each frame's histogram is
    normalized to a per-bin pixel *fraction* (so different crop sizes are comparable), then averaged
    across the batch; the shaded band is ±1σ across the batch. With ``drop_zero_bin`` the intensity-0
    bin is discarded before normalizing — for the masked variant, whose background is zeroed, this
    keeps the average from collapsing onto that one dominant bin. Which sub-batch this is (an index
    range) is documented by the caller's filename, not a title.

    Pass ``error_stats`` — what :func:`batch_pixel_error` returns for the same batch — to put the
    batch's mean pixel error ± σ in the legend, so the figure is quotable without its CSV beside it.
    :func:`generate_batch` measures that error on the comparison row's window rather than on this
    plot's tighter ROI crop, so one error figure describes the whole row: the heatmaps, the CSVs and
    this legend are all the same number.
    """
    ps.apply_showcase_style()
    c1, c2 = ps.SERIES_COLORS
    centers = _bin_centers(bins)

    real_frac = np.array([_intensity_fractions(r, bins, drop_zero_bin) for r, _ in cropped_pairs])
    gen_frac = np.array([_intensity_fractions(g, bins, drop_zero_bin) for _, g in cropped_pairs])
    rm, rs = real_frac.mean(0), real_frac.std(0)
    gm, gs = gen_frac.mean(0), gen_frac.std(0)

    fig, ax = plt.subplots(figsize=ps.figsize_full())
    ax.plot(centers, rm, color=c1, label=title1)
    ax.fill_between(centers, np.clip(rm - rs, 0, None), rm + rs, color=c1, alpha=0.2)
    ax.plot(centers, gm, color=c2, label=title2)
    ax.fill_between(centers, np.clip(gm - gs, 0, None), gm + gs, color=c2, alpha=0.2)
    if error_stats is not None:
        # The error goes in the legend rather than a floating text box: it is a third entry in the
        # same frame, so it can never land on top of a curve whatever the batch looks like.
        ax.plot([], [], " ", label=(f"error ({title1} − {title2}) {error_stats['mean_error']:+.1f} ± "
                                   f"{error_stats['std_error']:.1f} DN, {error_stats['frames']} frames"))

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
    background-zeroed variant — see the module docstring) a subdirectory is written containing, per
    pair, the three files of one comparison row — ``real_NN.png``, ``cielim_NN.png`` and
    ``heatmap_NN.png``, all :data:`PANEL_PX` tall — plus ``histogram_NN.png`` and one overall
    ``histogram_average.png``.

    ``average_exclude`` is an iterable of pair indices to drop from the overall average (their
    individual per-pair figures are still written). ``average_batches`` is an optional list of
    ``(label, indices)`` sub-batches; each writes an extra ``histogram_average_<label>.png`` averaged
    over just those indices (also respecting ``average_exclude``). The overall average is always
    written, so sub-batches are additive.

    Each mode also gets the numbers behind its figures, measured on the pixels of the comparison
    row's window (see :func:`pixel_error_stats`):

      * ``pixel_error_frames.csv``  — one row per pair, columns :data:`FRAME_ERROR_CSV_COLUMNS`; the
        mean/σ of row ``NN`` are the pair captioned on ``heatmap_NN.png``,
      * ``pixel_error_average.csv`` — one row per average batch, columns
        :data:`BATCH_ERROR_CSV_COLUMNS`, pooled over every pixel of every frame in the batch.

    The batch rows are also returned, as a nested ``{mode: {batch label: stats}}`` dict with the
    overall average keyed ``"all"``; :func:`format_error_stats` turns it into printable lines.
    """
    ps.apply_showcase_style()
    output_dir = Path(output_dir)
    stats = {}

    # Full-resolution matched grayscale pairs; the numeric figures use a padded ROI crop of the pair.
    full = [match_shapes(_as_gray(r), _as_gray(g)) for r, g in pairs]
    if not full:
        return stats

    # The panels are named for what they hold, so a LaTeX row reads real | cielim | heatmap.
    real_name = _slug(title_real)
    gen_name = _slug(title_generated)

    for mode in modes:
        cfg = MODES[mode]
        mode_dir = output_dir / mode
        mode_dir.mkdir(parents=True, exist_ok=True)

        cropped = []  # collected for the batch-average histogram
        moments = []  # per-pair error sums, in the same order, pooled into the batch averages
        for i, (real, gen) in enumerate(full):
            gg = align_pair(real, gen) if cfg["align"] else gen

            # The two compared frames, one tight window shared between them, as separate files so
            # they can be placed individually alongside the heatmap.
            rp, gp = frame_pair(real, gg, mask=cfg["mask"])
            save_image_panel(rp, mode_dir / f"{real_name}_{i:02d}.png")
            save_image_panel(gp, mode_dir / f"{gen_name}_{i:02d}.png")

            # The pixel error is measured on this window — the pixels the row actually shows — so the
            # heatmap's caption, the CSVs and the average all describe one and the same field of
            # view. In the masked variant only the target counts: its zeroed background matches
            # perfectly by construction and would drag the mean error toward zero.
            frame_fg = ((rp > 0) | (gp > 0)) if cfg["mask"] else None
            moments.append(_error_moments(rp, gp, frame_fg))

            # The heatmap is the third panel of the row, so it takes the SAME window as the two
            # image panels — the row has to show one field of view across all three.
            fig = plot_diff_heatmap(rp, gp, title_real, title_generated, mask=frame_fg)
            fig.savefig(mode_dir / f"heatmap_{i:02d}.png", dpi=PANEL_PX / ROW_PANEL_H)
            plt.close(fig)

            # The histograms keep their own, tighter ROI crop (see crop_pair): they are disk
            # statistics, and the row's window deliberately carries more background for context.
            rc, gc = crop_pair(real, gg)
            fg = foreground_mask(rc, gc) if cfg["mask"] else None
            if fg is not None:
                rc, gc = apply_mask(rc, fg), apply_mask(gc, fg)
            cropped.append((rc, gc))

            fig = plot_histogram(rc, gc, title_real, title_generated, mask=fg)
            ps.save_figure(fig, mode_dir / f"histogram_{i:02d}.png")
            plt.close(fig)

        (mode_dir / "pixel_error_frames.csv").write_text(
            _error_csv(FRAME_ERROR_CSV_COLUMNS,
                       [(f"{i:02d}", _stats_from_moments([m])) for i, m in enumerate(moments)])
        )

        exclude = set(average_exclude or ())
        mode_stats = {}

        def _avg(indices, suffix, label):
            keep = [i for i in indices if 0 <= i < len(cropped) and i not in exclude]
            if not keep:
                return
            # The batch's error pools the same frames the average histogram is drawn from, so the
            # figure, the CSV row and the printed line are one number.
            batch = _stats_from_moments([moments[i] for i in keep])
            fig = plot_average_histogram([cropped[i] for i in keep], title_real, title_generated,
                                         drop_zero_bin=cfg["mask"], error_stats=batch)
            ps.save_figure(fig, mode_dir / f"histogram_average{suffix}.png")
            plt.close(fig)
            mode_stats[label] = batch

        _avg(range(len(cropped)), "", "all")  # overall average (respecting average_exclude)
        for label, indices in average_batches or []:
            _avg(indices, f"_{label}", label)  # the label documents the sub-batch in the filename

        if mode_stats:
            (mode_dir / "pixel_error_average.csv").write_text(
                _error_csv(BATCH_ERROR_CSV_COLUMNS, list(mode_stats.items()))
            )
            stats[mode] = mode_stats

    return stats
