"""Showcase: the mesh -> distant-object handover, at low and high phase angle.

An asteroid is rendered at several multiples of the transition distance d_t, the range at which
Cielim stops rasterizing its mesh and draws it as a distant object instead. Each render is written
as its own bare crop, e.g. ``distant_a135_0pnt45dt.png`` (phase angle 135 deg, 0.45 d_t), plus a
``distant_objects.json`` record of the settings.

Every panel shows the same fixed-size crop, so the target visibly shrinks with range. The point of
the two rows is why the threshold has to grow with phase angle: at high alpha only a thin crescent
is lit, so the body's *bounding box* is still several pixels across when its visible signal has
already gone sub-pixel.

Brightness is normalised per phase-angle row, so panels from the two rows are NOT photometrically
comparable with each other — within a row they are.

Run:  python examples/showcases/distant_objects.py [--out DIR]
"""

import argparse
import sys
from pathlib import Path

import cielim
import cv2
import numpy as np
from cielim.utils import plot_style as ps

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scenes.distant_objects import (
    albedo,
    compute_transition_distance,
    fov_x,
    fov_y,
    height,
    mean_radius,
    pixel_size_threshold,
    scene_with_phase_angle,
    width,
)

default_out_dir = Path(__file__).resolve().parents[1] / "images-showcase"

exposure = 1e-4
brdf = "Lambertian"

# Ranges to render, as multiples of d_t. The far column sits well past it: coverage saturates just
# after the transition.
factors = [0.2, 0.45, 0.9, 1.05, 3.0]
phase_angles = [0, 135]

# Sized so one row of panels spans the text width at scale 1.0, with a gutter between them.
gutter_in = 0.06
panel_h = (ps.page_w - (len(factors) - 1) * gutter_in) / len(factors)

# Every panel shows the same 2*crop_half square, so the target visibly shrinks inside a fixed window.
# 13 fits the widest target (the alpha=135 crescent at 0.2*d_t, 8x22 px) with ~2 px to spare.
crop_half = 13


def render_gray(connector: cielim.Connector, scene: cielim.Scene) -> np.ndarray:
    """Send a scene and return the rendered image in grayscale."""
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    connector.request_image_for_camera_id(1)  # warm-up; the first frame after an init can be blank
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def lit_bbox(gray, near, reach):
    """``(x0, x1, y0, y1)`` of the lit pixels within ±``reach`` of ``near``, or None if none are.

    Windowed on purpose. Measuring the lit box over the whole frame is what the recorded
    ``footprint`` does, and that is right for a number that describes the render — but for choosing
    a crop center it is a trap: one stray nonzero pixel anywhere in the frame stretches the box
    across the image and drags the center to the middle of nowhere, silently. Restricting to a
    generous window around the peak keeps a hot pixel from moving the target off-panel.
    """
    cx, cy = int(near[0]), int(near[1])
    h, w = gray.shape
    x0, x1 = max(cx - reach, 0), min(cx + reach + 1, w)
    y0, y1 = max(cy - reach, 0), min(cy + reach + 1, h)
    ys, xs = np.nonzero(gray[y0:y1, x0:x1])
    if not len(xs):
        return None
    return x0 + int(xs.min()), x0 + int(xs.max()), y0 + int(ys.min()), y0 + int(ys.max())


def crop_target(gray, phase_angle_deg, factor):
    """Return the fixed-size crop centered on the lit target, and the target's whole-frame footprint."""
    peak_y, peak_x = np.unravel_index(np.argmax(gray), gray.shape)

    # Centered on the lit bounding box, not the brightest pixel: at high phase that would cut a horn off.
    box = lit_bbox(gray, near=(peak_x, peak_y), reach=4 * crop_half)
    if box is None:
        box = (int(peak_x), int(peak_x), int(peak_y), int(peak_y))
    bx0, bx1, by0, by1 = box
    if bx1 - bx0 >= 2 * crop_half or by1 - by0 >= 2 * crop_half:
        raise ValueError(
            f"alpha={phase_angle_deg}, {factor:g}*d_t: lit target is {bx1 - bx0 + 1}x{by1 - by0 + 1} px and "
            f"does not fit the {2 * crop_half}x{2 * crop_half} crop — it would be clipped. Raise crop_half."
        )
    x = int(np.clip((bx0 + bx1 + 1) // 2, crop_half, gray.shape[1] - crop_half))
    y = int(np.clip((by0 + by1 + 1) // 2, crop_half, gray.shape[0] - crop_half))

    # Measured over the whole frame: disagreeing with the windowed box means signal outside it.
    lit_y, lit_x = np.nonzero(gray)
    footprint = f"{lit_x.max() - lit_x.min() + 1}x{lit_y.max() - lit_y.min() + 1}" if len(lit_x) else "-"
    return gray[y - crop_half : y + crop_half, x - crop_half : x + crop_half], footprint


def distant_objects(connector: cielim.Connector, out_dir: Path):
    footprints, row_maxes, panel_files = {}, {}, []

    for phase_angle_deg in phase_angles:
        d_t = compute_transition_distance(phase_angle_deg=phase_angle_deg)
        crops = []
        for factor in factors:
            scene = scene_with_phase_angle(d_t * factor, phase_angle_deg, brdf, exposure_time=exposure)
            crops.append(crop_target(render_gray(connector, scene), phase_angle_deg, factor))

        # One display range per row, or the dim high-phase crescent is not visible at all.
        row_max = max(int(crop.max()) for crop, _ in crops) or 255
        row_maxes[phase_angle_deg] = row_max
        footprints[phase_angle_deg] = ",".join(footprint for _, footprint in crops)

        # Baked into the pixels: bare rasters have no imshow to apply the range at draw time.
        for factor, (crop, _) in zip(factors, crops):
            panel = np.clip(np.rint(crop.astype(np.float64) * (255.0 / row_max)), 0, 255).astype(np.uint8)
            tag = f"{factor:.2f}".replace(".", "pnt")
            name = f"distant_a{phase_angle_deg:03d}_{tag}dt.png"
            ps.save_raster_panel(panel, out_dir / name, panel_h)
            panel_files.append(name)

    # Written beside the panels, not drawn on them; several values are derived and move with the model.
    ps.save_context(
        "distant_objects",
        {
            "fov_deg": f"{np.degrees(fov_x):g}x{np.degrees(fov_y):g}",
            "resolution": f"{width}x{height}",
            "mean_radius_m": mean_radius,
            "geometric_albedo": albedo,
            "brdf": brdf,
            "exposure_s": exposure,
            "crop_px": f"{2 * crop_half}x{2 * crop_half}",
            "crop_center": "lit bounding box",
            "factors_of_d_t": factors,
            "d_t_alpha0_m": float(f"{compute_transition_distance(phase_angle_deg=0):.3g}"),
            "d_t_alpha135_m": float(f"{compute_transition_distance(phase_angle_deg=135):.3g}"),
            "threshold_px": f"{pixel_size_threshold(0):g}/{pixel_size_threshold(135):.1f}",
            "footprints_a000": footprints.get(0, "-"),
            "footprints_a135": footprints.get(135, "-"),
            "display": "per-row normalised",
            "row_max_a000": row_maxes.get(0, "-"),
            "row_max_a135": row_maxes.get(135, "-"),
        },
        files=panel_files,
        directory=out_dir,
    )


def main(out_dir: Path = default_out_dir):
    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    try:
        distant_objects(connector, out_dir)
    finally:
        connector.disconnect()
        launcher.terminate()

    print(f"Saved distant-object showcase panels -> {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=default_out_dir, help="directory to write the panels into")
    main(parser.parse_args().out)
