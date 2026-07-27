"""Shared matplotlib styling for cielim showcase / comparison figures.

One place to enforce the presentation look used across the comparison toolkit, the scenario
comparisons, and the feature-demo showcase tests:

  * 10 pt Helvetica (falls back to Arial -> DejaVu Sans if Helvetica isn't installed)
  * inferno as the default colormap for *numerical* figures (diff heatmaps, profiles, ...)
  * page-friendly figure sizes (fit a text column, side-by-side for image pairs)

Convention: numerical / analysis figures use inferno; a scene image shown on its own for viewing
(a render or a real frame, not a numerical comparison) is displayed with ``SCENE_CMAP`` (grayscale)
or its native color, so pass ``cmap=SCENE_CMAP`` explicitly on those ``imshow`` calls.
"""

import os

import matplotlib as mpl
import matplotlib.pyplot as plt

# Page geometry. PAGE_W is a typical text-column width in inches; figure helpers below keep figures
# within it so they drop onto a page (or side-by-side) without rescaling.
PAGE_W = 6.5
SAVE_DPI = 200

# Colormap for scene-image displays (a render/real frame shown for viewing, not a numeric compare).
SCENE_CMAP = "gray"

# Two inferno-sampled colors for two-series overlays (e.g. the paired histograms), so they read as
# the inferno palette while staying visually distinct. Low = dark purple, high = warm orange.
SERIES_COLORS = (mpl.cm.inferno(0.30), mpl.cm.inferno(0.72))


def apply_showcase_style():
    """Apply the shared presentation style to matplotlib rcParams. Idempotent — safe to call often."""
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "axes.titlesize": 10,
            "axes.labelsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.titlesize": 10,
            "image.cmap": "inferno",
            "savefig.dpi": SAVE_DPI,
            "savefig.bbox": "tight",
        }
    )


def figsize_single(aspect=0.62):
    """A single figure sized to a full text column (width PAGE_W, height = aspect * width)."""
    return (PAGE_W, PAGE_W * aspect)


def figsize_pair(aspect=0.5):
    """A figure holding two panels side-by-side across a text column (each panel ~half width)."""
    return (PAGE_W, PAGE_W * aspect)


def figsize_strip(n, panel_aspect=1.0):
    """A horizontal filmstrip of ``n`` panels spanning the column width."""
    panel_w = PAGE_W / max(n, 1)
    return (PAGE_W, panel_w * panel_aspect + 0.4)


def showcase_dir():
    """Directory to save showcase PNGs into, from the ``showcase_dir`` env var (None if unset)."""
    d = os.environ.get("showcase_dir")
    return d if d else None


def save_showcase(fig, name):
    """Save ``fig`` as ``<showcase_dir>/<name>.png`` at page dpi. No-op when showcase_dir is unset.

    Returns the saved path (or None). Applies the shared style first so a caller that forgot to call
    apply_showcase_style() still gets consistent output.
    """
    out = showcase_dir()
    if not out:
        return None
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{name}.png")
    fig.savefig(path, dpi=SAVE_DPI, bbox_inches="tight")
    return path
