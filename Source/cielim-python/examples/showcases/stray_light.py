"""Showcase: the stray-light (lens flare) model.

Writes two figure sets, each with a JSON record of the stray-light settings it was rendered with:

  * ``stray_light_flare.png``: one well-composed flare, with the sun just inside the frame edge.
  * ``sweep_00deg.png`` ... ``sweep_32deg.png``: the sun walking off boresight, past the frame edge
    (10 deg) but inside the baffle shield, so the ghosts persist after the sun has left the frame.

The flare multiplies the raw solar radiance, so the exposures are tiny compared to a lit surface.
The sweep's exposure is calibrated against a render rather than fixed, because the right value
depends on the tuning and on the absolute radiance scale.

Run:  python examples/showcases/stray_light.py [--out DIR]
"""

import argparse
import sys
from pathlib import Path

import cielim
import matplotlib.pyplot as plt
import numpy as np
from cielim.utils import plot_style as ps

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scenes.stray_light import (
    au,
    calibrate_exposure,
    fov,
    ghost_target,
    ghost_window_peak,
    render_gray,
    stray_light_scene,
    stray_light_tuning,
    sun_at_angle,
    sweep_baffle,
    sweep_cal_angle,
    sweep_fov,
)

default_out_dir = Path(__file__).resolve().parents[1] / "images-showcase"

# --- The flare -------------------------------------------------------------------
# Tuned to illustrate the model: graded ghost sizes for a legible chain, and the sun at 0.88 of the
# frame half-width to give it room to spread.
flare_sun_offset_x = 0.88 * np.tan(fov / 2) * au
flare_exposure = 4.0e-10

# Ghost sizing is counter-intuitive: support radius is 0.01^(1/(e_k*sigma_k)), so a larger sigma
# gives a larger, softer blob. Ghosts 1 and 3 are shrunk below a pixel; the count is fixed at four.
flare_tuning = {
    "core_size": 0.9,  # large, soft core (1/e radius = core_size/8 in UV; the frame spans 0.5)
    "corona_intensity": 0.004,  # faint, so the corona does not flood the frame into a grey wash
    "corona_falloff_exponent": 1.4,
    "num_rays": 6.0,  # even keeps the star mirror-symmetric
    "ray_sharpness": 4.0,  # broad, soft lobes (24 baseline is crisp)
    "ray_weight": 0.5,
    "ghost_size": 1.0,
    "ghost_relative_sizes": (0.25, 1.0, 0.25, 0.9),  # 1 and 3 collapsed away; 2 and 4 grown large
    "ghost_transmittance": 5.0,
    "ghost_brightness_size_exponent": 0.3,
}

# --- The off-boresight sweep -----------------------------------------------------
sweep_angles = [0, 8, 16, 32]  # walking out from boresight, past the frame edge at 10 deg
sweep_tuning = {**stray_light_tuning, "baffle_shield_angle": sweep_baffle}

# Sized so the panels placed in one row span the text width at scale 1.0, with a gutter.
sweep_gutter_in = 0.06
sweep_panel_h = (ps.page_w - (len(sweep_angles) - 1) * sweep_gutter_in) / len(sweep_angles)

# The order settings are recorded in, so the JSON records of both figure sets read the same way.
setting_order = (
    "core_size",
    "corona_intensity",
    "corona_falloff_exponent",
    "num_rays",
    "ray_sharpness",
    "ray_weight",
    "ghost_size",
    "ghost_relative_sizes",
    "ghost_transmittance",
    "ghost_brightness_size_exponent",
    "baffle_shield_angle",
)


def stray_light_facts(tuning, **extra):
    """The JSON record for a figure set: its stray-light settings, then ``extra`` scene facts."""
    facts = {}
    for key in setting_order:
        if key in tuning:
            value = tuning[key]
            facts[key] = list(value) if isinstance(value, tuple) else value
    facts.update(extra)
    return facts


def flare(connector: cielim.Connector, out_dir: Path):
    """One well-composed flare, shown in grayscale at half the text width."""
    scene = stray_light_scene(sun_offset=(flare_sun_offset_x, 0.0), exposure=flare_exposure, stray_light=flare_tuning)
    gray = render_gray(connector, scene)

    # Bare: what it was rendered with goes in the sidecar JSON, so nothing in the image can go stale.
    fig, ax = plt.subplots(figsize=ps.figsize_half())
    ax.imshow(gray, cmap=ps.scene_cmap, vmin=0, vmax=255)
    ax.axis("off")
    fig.tight_layout()
    ps.save_figure(fig, out_dir / "stray_light_flare.png")
    ps.save_context(
        "stray_light_flare",
        stray_light_facts(
            flare_tuning,
            exposure_s=f"{flare_exposure:.3g}",
            fov_deg=f"{np.degrees(fov):g}",
            sun_off_axis=f"{flare_sun_offset_x / (np.tan(fov / 2) * au):.2f}x_half_frame",
        ),
        files=["stray_light_flare.png"],
        directory=out_dir,
    )
    plt.close(fig)


def sweep(connector: cielim.Connector, out_dir: Path):
    """The sun walking off boresight, one bare raster per angle so the document lays out the row."""

    def sweep_scene(angle_deg, exposure):
        return stray_light_scene(
            sun_position=sun_at_angle(angle_deg), fov=sweep_fov, exposure=exposure, stray_light=sweep_tuning
        )

    exposure = calibrate_exposure(
        connector, lambda e: sweep_scene(sweep_cal_angle, e), target=ghost_target, measure=ghost_window_peak
    )

    files = []
    for angle in sweep_angles:
        name = f"sweep_{angle:02d}deg.png"
        ps.save_raster_panel(render_gray(connector, sweep_scene(angle, exposure)), out_dir / name, sweep_panel_h)
        files.append(name)

    ps.save_context(
        "stray_light_sweep",
        stray_light_facts(
            sweep_tuning,
            exposure_s=f"{exposure:.3g}",
            fov_deg=f"{np.degrees(sweep_fov):g}",
            cutoff_deg=f"{np.degrees(sweep_fov) / 2 + sweep_baffle:g}",
            angles_deg=sweep_angles,
        ),
        files=files,
        directory=out_dir,
    )


def main(out_dir: Path = default_out_dir):
    ps.apply_showcase_style()

    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    try:
        flare(connector, out_dir)
        sweep(connector, out_dir)
    finally:
        connector.disconnect()
        launcher.terminate()

    print(f"Saved stray-light showcase figures -> {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=default_out_dir, help="directory to write the figures into")
    main(parser.parse_args().out)
