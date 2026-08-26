"""
Goal:
    Break a rendered frame's wall-clock time into what it is actually made of: generating the image,
    encoding it to PNG, and shipping it over the network.

    Three cumulative measurements answer that, each one the previous plus a further cost:

        cielim_mac_nopng.csv     raw image generation
        cielim_mac_withpng.csv   raw image generation + PNG encoding
        cielim_mac_roundtrip.csv the above + networking (written by speed_test_scenario.py)

    Differencing adjacent files gives the three additive contributions, drawn as a stacked area so
    the top boundary is the total frame time and each band's thickness is its own cost.

    The first two come from engine-side C++ instrumentation; the third is what the Python client
    measures. This script only reads and plots — running the renderer is speed_test_scenario.py's job.
"""

import csv
import os

import matplotlib as mpl
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.ticker import MaxNLocator

from cielim.utils import plot_style

current_file_path = os.path.dirname(__file__)

DATA_DIRECTORY = os.path.join(current_file_path, "images-speed-test")

# Cumulative, innermost cost first. Each file is the one before it plus one more stage.
RAW_CSV = "cielim_nopng.csv"
PNG_CSV = "cielim_withpng.csv"
ROUNDTRIP_CSV = "cielim_roundtrip.csv"

BAND_LABELS = ("Image generation", "PNG encoding", "Network round trip")

# Sampled from the repo's inferno convention. Checked with the dataviz palette validator against a
# light surface: lightness band, chroma floor, CVD separation (worst adjacent dE 16.3 deutan / 14.0
# tritan) and the normal-vision floor all pass. The one contrast warning, on the warm end, is
# relieved by the legend labelling every band directly.
BAND_COLORS = (mpl.cm.inferno(0.38), mpl.cm.inferno(0.58), mpl.cm.inferno(0.76))

# PDF, not PNG: the figure goes into a LaTeX paper, where a vector figure stays sharp at any
# zoom and its 12 pt text is real text rather than pixels.
OUTPUT_NAME = "speed_test_breakdown.pdf"


def read_frame_times(path: str) -> np.ndarray:
    """
    Read a single-column per-frame timing CSV and return seconds.

    Deliberately strict, unlike a keyword-sniffing reader: the unit comes from the header suffix and
    nothing else. A column named ``frame_time_ms`` read as seconds is a silent factor-of-1000 error
    that still plots a plausible-looking curve, so an unrecognised header is a hard failure.

    Args:
        path (str): Path to the CSV. One column, one header row, one row per frame.

    Returns:
        ndarray: Per-frame times in seconds.
    """
    with open(path, newline="") as handle:
        rows = [row for row in csv.reader(handle) if row and any(field.strip() for field in row)]

    if len(rows) < 2:
        raise ValueError(f"No data rows in {path}.")

    header = [field.strip().lower() for field in rows[0]]
    if len(header) != 1:
        raise ValueError(f"Expected a single column in {path}, found {len(header)}: {header}.")

    unit = header[0].rsplit("_", 1)[-1]
    scale = {"ms": 1e-3, "msec": 1e-3, "s": 1.0, "sec": 1.0, "seconds": 1.0}.get(unit)
    if scale is None:
        raise ValueError(
            f"Cannot tell the unit of column '{header[0]}' in {path}. "
            "Name it with a trailing _ms or _s so the scale is unambiguous."
        )

    values = np.empty(len(rows) - 1, dtype=float)
    for index, row in enumerate(rows[1:]):
        try:
            values[index] = float(row[0])
        except ValueError as error:
            # Dropping the row would shift every later frame's orbit position; interpolating would
            # hide a broken instrumentation run. Fail loudly instead.
            raise ValueError(f"Non-numeric value {row[0]!r} on row {index + 2} of {path}.") from error

    if not np.isfinite(values).all():
        raise ValueError(f"Non-finite values in {path}.")

    return values * scale


def _resample(values: np.ndarray, count: int) -> np.ndarray:
    """
    Put ``values`` onto ``count`` evenly spaced orbit-phase samples.

    Every run sweeps one full orbit evenly in time from apoapse, so row *i* of an *N*-row file is
    orbit fraction i/(N-1) regardless of N. Truncating a 400-row file to match a 100-row one would
    therefore compare the first quarter of one orbit against the whole of another — and the tail
    would look like a dramatic speed-up that never happened. Interpolate onto a shared phase grid.
    """
    if len(values) == count:
        return values
    return np.interp(np.linspace(0.0, 1.0, count), np.linspace(0.0, 1.0, len(values)), values)


def plot_speed_breakdown(
    directory: str = DATA_DIRECTORY,
    output_path: str | None = None,
    show: bool = False,
    skip_initial: int = 1,
    show_legend: bool = True,
    show_xlabel: bool = True,
) -> str:
    """
    Plot the stacked frame-time breakdown from the three cumulative timing CSVs.

    Args:
        directory (str): Folder holding the three CSVs.
        output_path (str, optional): Where the PNG goes. Defaults to the data directory.
        show (bool): Whether to show the figure interactively.
        skip_initial (int): Leading frames to drop. The first frame of a run carries shader
            compilation and pipeline warm-up -- 281 ms against an 8 ms median in cielim_nopng, 35x
            -- so it is not a steady-state rendering cost and would otherwise set the whole y scale.
            Dropped after resampling, where phase 0 is exactly each file's own first frame.
        show_legend (bool): Whether to name the bands inside the plot. Turn it off for figures that
            sit under one that already carries the legend, or where the caption names the bands.
        show_xlabel (bool): Whether to label the x axis. Turn it off for the upper figures of a
            vertical stack, where only the bottom one needs to carry the shared axis name. The tick
            numbers stay either way.

    Returns:
        str: The path the figure was written to.
    """
    engine_paths = [os.path.join(directory, name) for name in (RAW_CSV, PNG_CSV)]
    for path in engine_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Missing {path}. The engine-side timing CSVs come from the instrumented C++ build; "
                f"both {RAW_CSV} and {PNG_CSV} must sit in {directory}."
            )

    labels = list(BAND_LABELS)
    cumulative = [read_frame_times(path) for path in engine_paths]

    # The round-trip file is the one this repo produces, so it is legitimately absent until the
    # scenario has been run once. Degrade to the two engine bands rather than refusing to plot.
    roundtrip_path = os.path.join(directory, ROUNDTRIP_CSV)
    if os.path.exists(roundtrip_path):
        cumulative.append(read_frame_times(roundtrip_path))
    else:
        print(f"No {ROUNDTRIP_CSV} in {directory} — plotting without the networking band.")
        print("  Run examples/speed_test_scenario.py to generate it.")
        labels = labels[:2]

    lengths = [len(values) for values in cumulative]
    count = min(lengths)
    if count < 2:
        raise ValueError(f"Need at least 2 frames to plot; shortest file has {count}.")
    if len(set(lengths)) > 1:
        counts = ", ".join(str(n) for n in lengths)
        print(f"Frame counts differ ({counts}) — resampling onto {count} orbit-phase samples.")
    cumulative = [_resample(values, count) for values in cumulative]

    # Enforce a running maximum on the CUMULATIVE stages before differencing. The files come from
    # separate runs, so a later stage can dip below an earlier one on a noisy frame; fixing it here
    # keeps every band non-negative AND keeps the top boundary equal to the total, which clipping
    # the increments afterwards would not.
    adjusted = 0
    for index in range(1, len(cumulative)):
        below = cumulative[index] < cumulative[index - 1]
        adjusted += int(below.sum())
        cumulative[index] = np.maximum(cumulative[index], cumulative[index - 1])
    if adjusted:
        print(f"Raised {adjusted} frame(s) where a later stage measured faster than an earlier one.")

    # Drop the warm-up frames only now: on the resampled grid, phase 0 maps exactly to each file's
    # own frame 0, so a single slice removes the cold-start sample from every series at once.
    if skip_initial:
        if skip_initial >= count:
            raise ValueError(f"skip_initial={skip_initial} leaves nothing of {count} samples.")
        cumulative = [values[skip_initial:] for values in cumulative]
        count -= skip_initial
        print(f"Skipped the first {skip_initial} frame(s) as warm-up; plotting {count}.")

    bands = [cumulative[0]] + [cumulative[i] - cumulative[i - 1] for i in range(1, len(cumulative))]

    plot_style.apply_showcase_style()
    # Full text width, but short enough to stack three on one page: a US-letter text block is
    # 9 in tall, and three figures plus their captions and spacing (~0.5 in each) leaves ~2.5 in
    # per figure. The default 0.5 aspect would need 9.75 in for the figures alone.
    figure, axes = plt.subplots(figsize=plot_style.figsize_full(aspect=0.38))

    # Image number on the common grid, keeping the skipped frames' numbers so the axis still says
    # which image each sample is. When the files differ in length the grid is the coarsest of them,
    # so these are that run's image numbers and the longer runs are interpolated onto them.
    x = np.arange(count + skip_initial)[skip_initial:]
    # Milliseconds throughout: these frame times are tens of ms, so a seconds axis would put every
    # tick behind a leading "0.0".
    bands_ms = [band * 1e3 for band in bands]
    total_ms = cumulative[-1] * 1e3

    # Band names only. At 12 pt a "(mean NN ms)" suffix makes the legend 8.2 in wide against a
    # 5.8 in axes, so it can no longer be one row; the means are printed below and belong in the
    # figure caption, which is where a paper reader looks for them anyway.
    legend_labels = list(labels)
    # A surface-coloured gap between bands separates them cleanly when the frames are countable, but
    # on a long noisy run the boundary weaves through every spike and the fills read as stripes.
    edge_width = 0.6 if count <= 120 else 0.0
    axes.stackplot(
        x, *bands_ms, colors=BAND_COLORS[: len(bands)], labels=legend_labels, edgecolor="white", linewidth=edge_width
    )

    # The total as a thin neutral line. In the top band's own colour it would be invisible against
    # the fill it bounds, so it takes an ink tone instead of a fourth hue.
    axes.plot(x, total_ms, color="0.25", linewidth=0.7)

    if show_xlabel:
        axes.set_xlabel("Image number")
    axes.set_ylabel("Frame time [ms]")
    axes.set_xlim(float(x[0]), float(x[-1]))
    axes.xaxis.set_major_locator(MaxNLocator(integer=True))
    # A stacked area has to rest on zero, or the bands misrepresent their own proportions.
    axes.set_ylim(0.0, (1.28 if show_legend else 1.06) * float(total_ms.max()))

    axes.grid(True, linewidth=0.5, color="0.85", alpha=0.8)
    axes.set_axisbelow(True)
    axes.spines["top"].set_visible(False)
    for side in ("left", "bottom", "right"):
        axes.spines[side].set_linewidth(0.6)
        axes.spines[side].set_color("0.6")

    # stackplot returns its polygons bottom-first, so the default legend order is upside down
    # relative to the visual stack. Reverse it, and keep it inside the axes to stay compact.
    handles, handle_labels = axes.get_legend_handles_labels()
    if show_legend:
        axes.legend(
            handles[::-1],
            handle_labels[::-1],
            loc="upper left",
            ncol=len(bands),
            frameon=True,
            facecolor="white",
            framealpha=0.85,
            edgecolor="none",
            borderpad=0.3,
            handlelength=1.2,
            handletextpad=0.4,
            columnspacing=1.2,
        )

    # save_figure writes the canvas at its built size with no tight crop, so the labels must be laid
    # out first or they fall outside and are cut.
    figure.tight_layout()
    output_path = output_path or os.path.join(directory, OUTPUT_NAME)
    plot_style.save_figure(figure, output_path)

    if show:
        plt.show()
    else:
        plt.close(figure)

    total = cumulative[-1].mean()
    print(f"Mean frame time {total * 1e3:.0f} ms:")
    for name, band in zip(labels, bands):
        print(f"  {name:22s} {band.mean() * 1e3:7.1f} ms  ({100 * band.mean() / total:4.1f} %)")
    print(f"Saved frame time breakdown -> {output_path}")

    return output_path


if __name__ == "__main__":
    # Legend on; x axis unlabelled because this figure sits above others in a stack that share the
    # same x axis, so only the bottom one needs to name it. Tick numbers are kept.
    plot_speed_breakdown(show_legend=True, show_xlabel=False)
