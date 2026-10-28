"""Showcase: the sensor-model corruptions and the lens models, rendered over a lit plane.

Writes two page-ready figures, each with a JSON record of the settings it was rendered with:

  * ``sensor_effects.png``: one frame combining read noise, dark current, stuck/dead pixels and
    cosmic rays.
  * ``lens_effects.png``: a clean render, radial distortion, and a Gaussian PSF side by side.

Run:  python examples/showcases/sensor_and_lens_effects.py [--out DIR]
"""

import argparse
from pathlib import Path

import cielim
import cv2
import matplotlib.pyplot as plt
import numpy as np
from cielim.utils import plot_style as ps

default_out_dir = Path(__file__).resolve().parents[1] / "images-showcase"


def scene_setup() -> cielim.Scene:
    """The spacecraft looking straight down at a Lambertian plane through a narrow 10 deg FoV."""
    scene = cielim.Scene()
    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))
    scene.set_lens_params(fov=(10 * np.pi / 180, 10 * np.pi / 180))
    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="Plane", mesh_brdf="Lambertian", mesh_radius=1000)
    return scene


def render(connector: cielim.Connector, scene: cielim.Scene) -> np.ndarray:
    """Send a scene and return the rendered image (BGR).

    The first image requested after an init can come back blank (the same reason Connector.connect
    renders and discards a dummy scene), which would silently turn a panel black. Request twice and
    keep the second.
    """
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    connector.request_image_for_camera_id(1, True, False)
    image, _, _ = connector.request_image_for_camera_id(1, True, False)
    return image


def show_scene(ax, image_bgr, title, title_width_in=ps.page_w):
    """Display a rendered scene image (native color, not inferno) on ``ax``.

    The title is wrapped to ``title_width_in`` so it stays 10 pt instead of setting the figure's
    width (figures are built at the page's text width and saved at that size).
    """
    ax.imshow(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB), interpolation="nearest")
    ax.set_title(ps.wrap_to_width(title, title_width_in, ps.body_pt, family="sans"))
    ax.axis("off")


def sensor_effects(connector: cielim.Connector, out_dir: Path):
    """One frame combining the sensor-model corruptions over the lit plane."""
    scene = scene_setup()

    position, exposure = (0, 0, 100), 2e-5
    corruptions = {
        "read_noise": 3000,
        "dc_rate": 50,
        "dc_sigma": 800,
        "stuck_px_rate": 0.0005,
        "dead_px_rate": 0.0005,
        "cosmic_rays": 100,
    }

    scene.set_spacecraft_params(position=position)  # fill the frame with the lit plane
    scene.set_sensor_params(exposure=exposure)  # low exposure -> mid-gray field so the effects read
    scene.set_corruption_params(**corruptions)

    image = render(connector, scene)

    # Half text width rather than a full page; the title stays 10 pt and wraps.
    title = "Sensor model — read noise, dark current, dead/stuck pixels, cosmic rays"
    lines = ps.wrap_to_width(title, ps.half_w, ps.body_pt, family="sans").count("\n") + 1
    fig, ax = plt.subplots(figsize=ps.figsize_half(title_lines=lines))
    show_scene(ax, image, title, title_width_in=ps.half_w)
    fig.tight_layout()
    ps.save_figure(fig, out_dir / "sensor_effects.png")
    ps.save_context(
        "sensor_effects",
        {"target": "lit plane", "position_m": list(position), "exposure_s": exposure, **corruptions},
        files=["sensor_effects.png"],
        directory=out_dir,
    )
    plt.close(fig)


def lens_effects(connector: cielim.Connector, out_dir: Path):
    """Lens models side by side: a clean render, radial distortion, and a PSF-blurred render."""
    scene = scene_setup()

    position, dist_radial, psf_sigma = (0, 0, 1000), (0.5, 0.0, 0.0), 50
    scene.set_spacecraft_params(position=position)  # closer -> distortion/blur are pronounced

    clean = render(connector, scene)

    scene.set_corruption_params(dist_radial=dist_radial, dist_tangent=(0.0, 0.0))
    distorted = render(connector, scene)

    scene.set_corruption_params(dist_radial=(0.0, 0.0, 0.0), dist_tangent=(0.0, 0.0), psf_sigma=psf_sigma)
    blurred = render(connector, scene)

    panel_w = ps.page_w / 3
    fig, axes = plt.subplots(1, 3, figsize=ps.figsize_strip(3))
    show_scene(axes[0], clean, "Clean", title_width_in=panel_w)
    show_scene(axes[1], distorted, f"Radial distortion (k1={dist_radial[0]:g})", title_width_in=panel_w)
    show_scene(axes[2], blurred, f"Gaussian PSF (σ={psf_sigma:g})", title_width_in=panel_w)
    fig.suptitle("Lens models")
    fig.tight_layout()
    ps.save_figure(fig, out_dir / "lens_effects.png")
    ps.save_context(
        "lens_effects",
        {
            "target": "lit plane",
            "position_m": list(position),
            "panels": ["clean", "radial distortion", "gaussian psf"],
            "dist_radial_k": list(dist_radial),
            "dist_tangent_p": [0.0, 0.0],
            "psf_sigma": psf_sigma,
        },
        files=["lens_effects.png"],
        directory=out_dir,
    )
    plt.close(fig)


def main(out_dir: Path = default_out_dir):
    ps.apply_showcase_style()

    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    try:
        sensor_effects(connector, out_dir)
        lens_effects(connector, out_dir)
    finally:
        connector.disconnect()
        launcher.terminate()

    print(f"Saved sensor and lens showcase figures -> {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=default_out_dir, help="directory to write the figures into")
    main(parser.parse_args().out)
