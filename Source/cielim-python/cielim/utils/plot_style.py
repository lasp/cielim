"""Shared matplotlib styling for cielim showcase / comparison figures.

One place to enforce the presentation look used across the comparison toolkit, the scenario
comparisons, and the feature-demo showcase tests:

  * 10 pt Helvetica (falls back to Arial -> DejaVu Sans if Helvetica isn't installed)
  * inferno as the default colormap for *numerical* figures (diff heatmaps, profiles, ...)
  * page-friendly figure sizes (fit a text column, side-by-side for image pairs)

**Print sizing.** Figures are BUILT at the paper's text width and SAVED at exactly that built size
-- no tight-bbox cropping, which would make every saved width depend on how much decoration the
figure happens to carry. So a figure dropped into the document at scale 1.0 spans the text block
exactly, its 10 pt text really prints at 10 pt, and stacked figures line up edge to edge. Build
every figure with the ``figsize_*`` helpers and save it with :func:`save_figure` /
:func:`save_showcase`; do not pass ``bbox_inches="tight"``.

Convention: numerical / analysis figures use inferno; a scene image shown on its own for viewing
(a render or a real frame, not a numerical comparison) is displayed with ``SCENE_CMAP`` (grayscale)
or its native color, so pass ``cmap=SCENE_CMAP`` explicitly on those ``imshow`` calls.

**Provenance.** The figures carry no settings text. What a figure set was rendered with is written
beside it as JSON by :func:`save_context`, so the record travels with the images instead of being
baked into them as small print or copied by hand into a document.
"""

import json
import os
import textwrap

import matplotlib as mpl
import matplotlib.pyplot as plt
from PIL import Image

# Page geometry, in inches. PAGE_W is the paper's text width (US letter with 1 in margins) -- a
# full-width figure is built at exactly this and needs no scaling when it is placed.
# HALF_W is one panel of a two-panel figure: the size a lone image gets (heatmaps, single renders)
# so two of them can also sit side by side.
PAGE_W = 6.5
HALF_W = PAGE_W / 2
SAVE_DPI = 200

# Every piece of figure text -- titles, axis and tick labels, legends, panel labels -- is BODY_PT.
# It matches the paper's body size so a figure included at scale 1.0 needs no rescaling: scaling
# a figure scales its text too, and 10 pt text in a figure shrunk to fit is no longer 10 pt on the
# page.
BODY_PT = 10

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
            "font.size": BODY_PT,
            "axes.titlesize": BODY_PT,
            "axes.labelsize": BODY_PT,
            "xtick.labelsize": BODY_PT,
            "ytick.labelsize": BODY_PT,
            "legend.fontsize": BODY_PT,
            "figure.titlesize": BODY_PT,
            "image.cmap": "inferno",
            "savefig.dpi": SAVE_DPI,
            # NOT "tight": the saved canvas must stay the size the figure was built at, or every
            # figure lands on the page at a slightly different width (and a different text scale).
            "savefig.bbox": "standard",
            # Embed TrueType rather than matplotlib's default Type 3 fonts: Type 3 is rejected
            # by many publishers' PDF checks, and vector output is the point of saving a PDF.
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _title_h(title_lines):
    """Height in inches needed for ``title_lines`` lines of BODY_PT text above an axes."""
    return title_lines * 1.35 * BODY_PT / 72


def figsize_full(aspect=0.5, title_lines=0):
    """A figure spanning the full text width (PAGE_W x aspect * PAGE_W, plus room for a title).

    The default aspect makes a full-width figure exactly as tall as one HALF_W panel, which is what
    lets side-by-side views, histograms and averages stack without their heights jumping around.
    ``title_lines`` adds height for a title above the axes — needed when the axes has a fixed aspect
    (an ``imshow``), because then tight_layout cannot shrink it to make room and the title is clipped.
    """
    return (PAGE_W, PAGE_W * aspect + _title_h(title_lines))


def figsize_half(aspect=1.0, title_lines=0):
    """A figure the size of ONE panel of a full-width two-panel figure (HALF_W x aspect * HALF_W).

    For a figure carrying a single image — a diff heatmap, a lone render — so it prints at the size
    of one side-by-side panel rather than blown up to the whole text width. See :func:`figsize_full`
    for ``title_lines``.
    """
    return (HALF_W, HALF_W * aspect + _title_h(title_lines))


# Back-compatible names: a "single" figure and a "pair" figure are both full text width.
figsize_single = figsize_full
figsize_pair = figsize_full


def figsize_strip(n, panel_aspect=1.0, title_lines=1, suptitle=True):
    """A horizontal filmstrip of ``n`` panels spanning the text width.

    Height leaves room for ``title_lines`` of BODY_PT text above each panel, plus a figure title when
    ``suptitle``, so the panel labels don't collide with the row above. Pass ``suptitle=False`` for an
    untitled strip, or the figure carries a band of blank paper where the title would have been.
    """
    panel_w = PAGE_W / max(n, 1)
    return (PAGE_W, panel_w * panel_aspect + _title_h(1.6 * (title_lines + (1 if suptitle else 0))))


def wrap_to_width(text, width_in, fontsize=BODY_PT, family="monospace"):
    """Wrap ``text`` to the number of characters that fits ``width_in`` inches at ``fontsize``.

    Monospace advances are ~0.6 em; the proportional fallback is ~0.5 em on average. Conservative by
    design — a wrapped title must not set the figure's width, since the canvas is not tight-cropped.
    """
    em_per_char = 0.6 if family == "monospace" else 0.5
    chars = max(int(width_in * 72 / (em_per_char * fontsize)), 20)
    return textwrap.fill(text, width=chars)


def showcase_dir():
    """Directory to save showcase PNGs into, from the ``showcase_dir`` env var (None if unset)."""
    d = os.environ.get("showcase_dir")
    return d if d else None


def save_context(name, facts, files=None, directory=None):
    """Write ``<directory>/<name>.json``: the record of what figure set ``name`` was rendered with.

    The figures themselves carry no settings text, so this is where the settings live — next to the
    images, in the same run that produced them, rather than transcribed into a document by hand
    where it can drift. Several of these values are derived (transition distances, thresholds,
    calibrated exposures), so they move whenever the model does.

    ``directory`` defaults to :func:`showcase_dir`, so this is a no-op returning None when the
    ``showcase_dir`` env var is unset — the same opt-in as :func:`save_showcase`.

    Args:
        name (str): Figure set name; also the JSON's stem.
        facts (dict): Settings to record. Insertion order is preserved in the file.
        files (list, optional): Image filenames this record describes.
        directory (str, optional): Where to write. Defaults to :func:`showcase_dir`.

    Returns:
        str | None: The path written, or None when there is nowhere to write.
    """
    out = directory or showcase_dir()
    if not out:
        return None
    os.makedirs(out, exist_ok=True)
    record = {"figure": name}
    if files is not None:
        record["files"] = list(files)
    record.update(facts)
    path = os.path.join(out, f"{name}.json")
    with open(path, "w") as handle:
        json.dump(record, handle, indent=2, default=str)
        handle.write("\n")
    return path


def save_figure(fig, path):
    """Save ``fig`` at exactly the size it was built at, at page dpi.

    No ``bbox_inches="tight"``: the PNG must come out at the declared figsize (and carries that as
    its dpi metadata) so the document can place it at scale 1.0 and figures of the same figsize stack
    flush. Anything laid out outside the canvas is simply cut.
    """
    os.makedirs(os.path.dirname(str(path)) or ".", exist_ok=True)
    fig.savefig(str(path), dpi=SAVE_DPI)
    return str(path)


def save_showcase(fig, name):
    """Save ``fig`` as ``<showcase_dir>/<name>.png`` at page dpi. No-op when showcase_dir is unset.

    Returns the saved path (or None). See :func:`save_figure` for why the canvas is not tight-cropped.
    """
    out = showcase_dir()
    if not out:
        return None
    os.makedirs(out, exist_ok=True)
    return save_figure(fig, os.path.join(out, f"{name}.png"))


def save_raster_panel(img, path, height_in, px=1024, exact_height=False):
    """Write a uint8 array as a bare image panel: just the pixels, no axes, margins or interpolation.

    For a figure that IS an image — a render, a crop — where matplotlib would only add margins and
    resampling blur. Tagged with the dpi that makes it ``height_in`` inches tall on the page, so the
    panel prints at its intended size with no scaling when it is placed.

    ``px`` is the target pixel height, and how strictly it is met is the caller's choice:

    * default — scale up by a WHOLE number of pixels, or not at all. A fractional scale lands one
      source pixel on 39 output pixels and its neighbour on 40, which is plainly visible on a panel
      whose subject IS individual pixels. Use this for a panel that stands on its own.
    * ``exact_height=True`` — land on exactly ``px`` tall, accepting uneven pixel blocks. Use this
      when the file has to match the height of something it cannot control, such as a matplotlib
      figure in the same row that can only be sized through its dpi.

    Either way the dpi is derived from the size actually written, so the print size is exact.
    """
    h, w = img.shape[:2]
    im = Image.fromarray(img)
    if exact_height and h != px:
        im = im.resize((max(int(round(w * px / h)), 1), px), Image.NEAREST if px >= h else Image.LANCZOS)
    elif not exact_height and h < px:
        factor = max(int(round(px / h)), 1)
        if factor > 1:
            im = im.resize((w * factor, h * factor), Image.NEAREST)
    dpi = im.size[1] / height_in
    os.makedirs(os.path.dirname(str(path)) or ".", exist_ok=True)
    im.save(str(path), dpi=(dpi, dpi))
    return str(path)


def save_showcase_raster(img, name, height_in, px=1024, exact_height=False):
    """Raster counterpart of :func:`save_showcase`: write ``img`` to ``<showcase_dir>/<name>.png``.

    No-op returning None when the showcase_dir env var is unset. ``name`` goes straight into the
    filename, so it must already be filesystem-safe.
    """
    out = showcase_dir()
    if not out:
        return None
    os.makedirs(out, exist_ok=True)
    return save_raster_panel(img, os.path.join(out, f"{name}.png"), height_in, px, exact_height)
