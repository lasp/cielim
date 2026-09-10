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

data_directory = os.path.join(current_file_path, "images-speed-test")

raw_csv = "cielim_nopng.csv"
png_csv = "cielim_withpng.csv"
roundtrip_csv = "cielim_roundtrip.csv"

band_labels = ("Image generation", "PNG encoding", "Network round trip")

# Inferno-sampled. CVD-checked; the one contrast warning on the warm end is relieved by the
# legend labelling every band directly.
band_colors = (mpl.cm.inferno(0.38), mpl.cm.inferno(0.58), mpl.cm.inferno(0.76))

# PDF, not PNG: the figure goes into a LaTeX paper, where a vector figure stays sharp at any
# zoom and its 12 pt text is real text rather than pixels.
output_name = "speed_test_breakdown.pdf"

figure_px = 1024

y_limit_ms = (0.0, 110.0)


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
    directory: str = data_directory,
    output_path: str | None = None,
    show: bool = False,
    skip_initial: int = 1,
    show_legend: bool = True,
    show_xlabel: bool = True,
    show_ylabel: bool = True,
    ylim: tuple[float, float] | None = y_limit_ms,
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
        show_ylabel (bool): Whether to label the y axis. Turn it off for the right-hand figure of a
            side-by-side pair, where the left one already names the shared scale.
        ylim (tuple, optional): Fixed (low, high) y range in ms, so separate runs share one scale
            and can be compared by eye. None sizes the axis to the data and leaves room for the
            legend. Values above the top are clipped, and the clipping is reported.

    Returns:
        str: The path the figure was written to.
    """
    engine_paths = [os.path.join(directory, name) for name in (raw_csv, png_csv)]
    for path in engine_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Missing {path}. The engine-side timing CSVs come from the instrumented C++ build; "
                f"both {raw_csv} and {png_csv} must sit in {directory}."
            )

    labels = list(band_labels)
    cumulative = [read_frame_times(path) for path in engine_paths]

    roundtrip_path = os.path.join(directory, roundtrip_csv)
    if os.path.exists(roundtrip_path):
        cumulative.append(read_frame_times(roundtrip_path))
    else:
        print(f"No {roundtrip_csv} in {directory} — plotting without the networking band.")
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

    # Running maximum on the cumulative stages before differencing: separate runs let a later stage
    # dip below an earlier one, and fixing it here keeps the top boundary equal to the total.
    adjusted = 0
    for index in range(1, len(cumulative)):
        below = cumulative[index] < cumulative[index - 1]
        adjusted += int(below.sum())
        cumulative[index] = np.maximum(cumulative[index], cumulative[index - 1])
    if adjusted:
        print(f"Raised {adjusted} frame(s) where a later stage measured faster than an earlier one.")

    if skip_initial:
        if skip_initial >= count:
            raise ValueError(f"skip_initial={skip_initial} leaves nothing of {count} samples.")
        cumulative = [values[skip_initial:] for values in cumulative]
        count -= skip_initial
        print(f"Skipped the first {skip_initial} frame(s) as warm-up; plotting {count}.")

    bands = [cumulative[0]] + [cumulative[i] - cumulative[i - 1] for i in range(1, len(cumulative))]

    plot_style.apply_showcase_style()
    side_in = figure_px / plot_style.save_dpi
    figure, axes = plt.subplots(figsize=(side_in, side_in))

    # Image number on the common grid, which is the coarsest file; longer runs are interpolated.
    x = np.arange(count + skip_initial)[skip_initial:]
    bands_ms = [band * 1e3 for band in bands]
    total_ms = cumulative[-1] * 1e3

    # Band names only: a "(mean NN ms)" suffix makes the legend too wide to stay one row.
    legend_labels = list(labels)
    edge_width = 0.6 if count <= 120 else 0.0
    axes.stackplot(
        x, *bands_ms, colors=band_colors[: len(bands)], labels=legend_labels, edgecolor="white", linewidth=edge_width
    )

    axes.plot(x, total_ms, color="0.25", linewidth=0.7)

    # Blank label, not no label: a rotated y label reserves its line height whatever the text says,
    # so " " holds the same margin and every cut of this figure keeps an identical plot area.
    axes.set_xlabel("Image number" if show_xlabel else " ")
    axes.set_ylabel("Frame time [ms]" if show_ylabel else " ")
    axes.set_xlim(float(x[0]), float(x[-1]))
    width_in = figure.get_size_inches()[0]
    axes.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=max(4, int(width_in * 1.6))))
    axes.set_ylim(*ylim) if ylim else axes.set_ylim(0.0, 1.06 * float(total_ms.max()))

    axes.grid(True, linewidth=0.5, color="0.85", alpha=0.8)
    axes.set_axisbelow(True)
    axes.spines["top"].set_visible(False)
    for side in ("left", "bottom", "right"):
        axes.spines[side].set_linewidth(0.6)
        axes.spines[side].set_color("0.6")

    handles, handle_labels = axes.get_legend_handles_labels()
    if show_legend:
        legend_style = dict(
            loc="upper left",
            frameon=True,
            facecolor="white",
            framealpha=0.85,
            edgecolor="none",
            borderpad=0.3,
            handlelength=1.2,
            handletextpad=0.4,
            columnspacing=1.2,
        )
        # Measured rather than guessed: draw one row, then stack it only if it overflows the axes.
        legend = axes.legend(handles[::-1], handle_labels[::-1], ncol=len(bands), **legend_style)
        figure.canvas.draw()
        to_inches = figure.dpi_scale_trans.inverted()
        legend_w = legend.get_window_extent().transformed(to_inches).width
        axes_w = axes.get_window_extent().transformed(to_inches).width
        if legend_w > axes_w:
            legend.remove()
            legend = axes.legend(handles[::-1], handle_labels[::-1], ncol=1, **legend_style)
        legend_height_frac = (
            legend.get_window_extent().transformed(to_inches).height
            / axes.get_window_extent().transformed(to_inches).height
        )

    # From the legend's measured height; skipped when the range is pinned, where a shared scale wins.
    if show_legend and ylim is None:
        clear_fraction = max(0.2, 1.0 - legend_height_frac - 0.04)
        axes.set_ylim(0.0, float(total_ms.max()) / clear_fraction)

    if ylim is not None:
        clipped = int((total_ms > ylim[1]).sum())
        if clipped:
            print(
                f"y axis pinned to {ylim[0]:g}-{ylim[1]:g} ms: {clipped} frame(s) exceed it "
                f"(max {total_ms.max():.1f} ms) and are drawn cut off at the top."
            )

    figure.tight_layout()
    output_path = output_path or os.path.join(directory, output_name)
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
    # Pass show_legend / show_xlabel / show_ylabel as False for a stripped cut to sit beside this one.
    plot_speed_breakdown(show_legend=True, show_xlabel=True, show_ylabel=True)
