import cv2
import numpy as np
import pytest
from matplotlib import pyplot as plt

import cielim
from cielim.utils import plot_style as ps


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a plane.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    scene.set_lens_params(fov=(10 * np.pi / 180, 10 * np.pi / 180))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="Plane", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "k1, k2, k3, p1, p2",
    [
        (0.5, 0.0, 0.0, 0.0, 0.0),
        (-0.5, 0.0, 0.0, 0.0, 0.0),
        (0.3, 0.1, 0.0, 0.0, 0.0),
        (0.3, 0.2, 0.1, 0.0, 0.0),
        (0.0, -0.3, 0.1, 0.0, 0.0),
        (0.0, 0.3, -0.1, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.3, 0.0),
        (0.0, 0.0, 0.0, 0.0, 0.3),
    ],
)
def test_LensDistortion(cielim_connection: cielim.Connector, default_scene: cielim.Scene, k1, k2, k3, p1, p2):
    """
    Tests that lens distortion is distorting the image as expected.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_spacecraft_params(position=(0, 0, 1000))  # Move closer to make effects more pronounced

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    base_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    # Apply distortions to base image

    h, w = base_image.shape[:2]
    aspect_ratio = w / h

    # Create normalized UV coordinate grids [0, 1]
    u = np.linspace(0, 1, w, dtype=np.float32)
    v = np.linspace(0, 1, h, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # Shift to center [-0.5, 0.5] and apply aspect ratio to X
    cx = (uu - 0.5) * aspect_ratio
    cy = vv - 0.5

    # Radial distances
    r2 = cx * cx + cy * cy
    r4 = r2 * r2
    r6 = r2 * r4

    # Radial distortion factor
    radial = 1.0 + k1 * r2 + k2 * r4 + k3 * r6

    # Tangential distortion offset
    tx = 2.0 * p1 * cx * cy + p2 * (r2 + 2.0 * cx * cx)
    ty = p1 * (r2 + 2.0 * cy * cy) + 2.0 * p2 * cx * cy

    # Edge scale factors (to normalize distortion at image borders)
    x_edge2 = (0.5 * aspect_ratio) ** 2
    x_scale = 1.0 + k1 * x_edge2 + k2 * x_edge2**2 + k3 * x_edge2**3

    y_edge2 = 0.5**2
    y_scale = 1.0 + k1 * y_edge2 + k2 * y_edge2**2 + k3 * y_edge2**3

    # Apply edge scaling before distortion
    cx /= x_scale
    cy /= y_scale

    # Apply radial + tangential distortion
    dx = cx * radial + tx
    dy = cy * radial + ty

    # Undo aspect ratio and shift back to [0, 1] UV space
    dx /= aspect_ratio
    distorted_u = dx + 0.5
    distorted_v = dy + 0.5

    # Convert UVs to pixel coordinates for remap
    map_x = (distorted_u * w).astype(np.float32)
    map_y = (distorted_v * h).astype(np.float32)

    # Remap with black border fill
    distorted_base = cv2.remap(
        base_image, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)
    )

    scene.set_corruption_params(dist_radial=(k1, k2, k3), dist_tangent=(p1, p2))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    distorted_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    diff = np.abs(distorted_image.astype(np.int32) - distorted_base.astype(np.int32))
    mismatch_fraction = np.mean(diff > 1)

    # Some pixels will be off because cv can smooth edges (6% allowance)
    assert mismatch_fraction < 0.06, f"Too many mismatched pixels: {mismatch_fraction:.2%} " f"(max diff: {diff.max()})"


def test_GaussianPSF(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Tests that Gaussian PSF is properly blurring the image using variance of laplacian.
    """
    connector = cielim_connection

    scene = default_scene

    # Change scene to rotated plane to test GaussianPSF on jagged edges
    scene.set_celestial_body_params(1, mesh_attitude=(0, 0, 0.2))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    sharp_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    scene.set_corruption_params(psf_sigma=50)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    blurred_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    sharp_laplace = cv2.Laplacian(sharp_image, cv2.CV_64F)
    sharp_variance = sharp_laplace.var()

    blur_laplace = cv2.Laplacian(blurred_image, cv2.CV_64F)
    blur_variance = blur_laplace.var()

    print(f"Sharp Variance: {sharp_variance}")
    print(f"Blurred Variance: {blur_variance}")

    np.testing.assert_array_less(
        blur_variance,
        sharp_variance,
        err_msg=f"Image was not blurred: expected blurred variance ({blur_variance}) to be less than sharp variance ({sharp_variance})",
    )


@pytest.mark.parametrize(
    "dark_current, sigma",
    [
        (1000, 0),
        (10000, 0),
        (1, 100),
        (1, 1000),
        (10, 100),
        (10, 1000),
        (100, 100),
        (100, 10000),
    ],
)
def test_DarkCurrent(cielim_connection: cielim.Connector, default_scene: cielim.Scene, dark_current, sigma):
    """
    Tests whether dark current is being added to the image.
    See RandomFuncs.ush for RNG implementation.
    """
    connector = cielim_connection

    scene = default_scene

    scene.delete_celestial_body(1)

    scene.set_sensor_params(exposure=1)
    scene.set_corruption_params(dc_rate=dark_current, dc_sigma=sigma)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)
    cv2.imshow("image", image)
    cv2.waitKey(0)
    np.testing.assert_(image[..., :3].any(), "No noise was applied")


def test_CosmicRays(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Tests that comsic rays are being generated in the image.
    """
    connector = cielim_connection

    scene = default_scene

    scene.delete_celestial_body(1)

    scene.set_corruption_params(cosmic_rays=100)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    np.testing.assert_(np.any(np.all(image[:, :, :3] == 255, axis=-1)), "No cosmic rays found in otherwise blank image")


@pytest.mark.parametrize(
    "read_noise",
    [50, 500, 5000, 20000],
)
def test_ReadNoise(cielim_connection: cielim.Connector, default_scene: cielim.Scene, read_noise):
    """
    Tests read noise is being generated with the expected standard deviation.
    See RandomFuncs.ush for RNG implementation.
    """
    connector = cielim_connection

    scene = default_scene

    scene.delete_celestial_body(1)

    scene.set_corruption_params(read_noise=read_noise)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    image_normalized = image.astype(np.float32) / 255.0

    measured_std = np.std(image_normalized**2.2)

    np.testing.assert_array_less(0.0, measured_std, err_msg="Image was blank and no noise was applied")

    np.testing.assert_allclose(
        measured_std,
        read_noise / 50000,
        rtol=0.65,
        err_msg=f"Measured standard deviation ({measured_std}) was too far from expected of ({read_noise})",
    )


@pytest.mark.parametrize(
    "stuck_rate, dead_rate",
    [
        (0.000005, 0),  # a few pixels
        (0, 0.000005),
        (0.000005, 0.000005),
        (0.000025, 0),  # about a dozen pixels
        (0, 0.000025),
        (0.000025, 0.000025),
    ],
)
def test_PixelDefect(cielim_connection: cielim.Connector, default_scene: cielim.Scene, stuck_rate, dead_rate):
    """
    Tests stuck and dead pixels can be added to image.
    See RandomFuncs.ush for RNG implementation.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_spacecraft_params(position=(0, 0, 100))  # Make spacecraft closer to plane to fill screen
    scene.set_sensor_params(exposure=2e-5)  # Reduce exposure time so image is gray
    scene.set_corruption_params(stuck_px_rate=stuck_rate, dead_px_rate=dead_rate)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    is_white = (image == [255, 255, 255]).all(axis=-1)
    is_black = (image == [0, 0, 0]).all(axis=-1)

    total_pixels = image.shape[0] * image.shape[1]

    white_pixels_rate = np.sum(is_white) / total_pixels
    black_pixels_rate = np.sum(is_black) / total_pixels

    np.testing.assert_allclose(
        white_pixels_rate,
        stuck_rate,
        atol=0.0005,
        err_msg=f"Got white pixel rate of {white_pixels_rate * 100:.5f}%, expected ~{stuck_rate * 100}%",
    )

    np.testing.assert_allclose(
        black_pixels_rate,
        dead_rate,
        atol=0.0005,
        err_msg=f"Got black pixel rate of {black_pixels_rate * 100:.5f}%, expected ~{dead_rate * 100}%",
    )


@pytest.mark.parametrize(
    "signal_gain",
    [0.8, 0.75, 0.5, 0.25],
)
def test_SignalGain(cielim_connection: cielim.Connector, default_scene: cielim.Scene, signal_gain):
    """
    Tests whether gain is being properly applied to image.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    base_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    image_normalized = base_image.astype(np.float32) / 255.0
    img_linear = image_normalized**2.2
    img_scaled_linear = img_linear * signal_gain
    comparison_image = (np.clip(img_scaled_linear ** (1 / 2.2), 0.0, 1.0) * 255).astype(np.uint8)

    scene.set_sensor_params(gain=signal_gain)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    gain_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    np.testing.assert_allclose(
        gain_image, comparison_image, rtol=0.1, err_msg="Received image does not match comparison with specified gain"
    )


# ===========================================================================
# Showcase: page-ready sensor- and lens-model demo images (opt-in via showcase_dir)
# ===========================================================================


def _render(connector, scene):
    """Send a scene and return the rendered image (BGR).

    The first image requested after an init can come back blank (the same reason Connector.connect
    renders and discards a dummy scene), which silently turns a showcase panel black. Request twice
    and keep the second.
    """
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    connector.request_image_for_camera_id(1, True, False)
    image, _, _ = connector.request_image_for_camera_id(1, True, False)
    return image


def _show_scene(ax, image_bgr, title, title_width_in=ps.PAGE_W):
    """Display a rendered scene image (native color, not inferno) on ``ax``.

    The title is wrapped to ``title_width_in`` so it stays 10 pt instead of setting the figure's
    width (figures are built at the page's text width and saved at that size).
    """
    ax.imshow(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB), interpolation="nearest")
    ax.set_title(ps.wrap_to_width(title, title_width_in, ps.BODY_PT, family="sans"))
    ax.axis("off")


@pytest.mark.showcase
def test_showcase_sensor_effects(cielim_connection, default_scene):
    """One frame combining the sensor-model corruptions: read noise, dark current, stuck/dead
    pixels, and cosmic rays over a simple lit target."""
    ps.apply_showcase_style()
    connector = cielim_connection
    scene = default_scene

    scene.set_spacecraft_params(position=(0, 0, 100))  # fill the frame with the lit plane
    scene.set_sensor_params(exposure=2e-5)  # low exposure -> mid-gray field so the effects read
    scene.set_corruption_params(
        read_noise=3000,
        dc_rate=50,
        dc_sigma=800,
        stuck_px_rate=0.0005,
        dead_px_rate=0.0005,
        cosmic_rays=100,
    )

    image = _render(connector, scene)

    # Half text width — one square render, printed at the size of a single side-by-side panel rather
    # than blown up to a full page (see plot_style: figures are placed at scale 1.0). The title stays
    # 10 pt and wraps, so the figure carries the height for its extra lines.
    title = "Sensor model — read noise, dark current, dead/stuck pixels, cosmic rays"
    lines = ps.wrap_to_width(title, ps.HALF_W, ps.BODY_PT, family="sans").count("\n") + 1
    fig, ax = plt.subplots(figsize=ps.figsize_half(title_lines=lines))
    _show_scene(ax, image, title, title_width_in=ps.HALF_W)
    fig.tight_layout()
    ps.save_showcase(fig, "sensor_effects")
    plt.close(fig)


@pytest.mark.showcase
def test_showcase_lens_effects(cielim_connection, default_scene):
    """Lens models side-by-side: a clean render, radial distortion, and a PSF-blurred render."""
    ps.apply_showcase_style()
    connector = cielim_connection
    scene = default_scene
    scene.set_spacecraft_params(position=(0, 0, 1000))  # closer -> distortion/blur are pronounced

    clean = _render(connector, scene)

    scene.set_corruption_params(dist_radial=(0.5, 0.0, 0.0), dist_tangent=(0.0, 0.0))
    distorted = _render(connector, scene)

    scene.set_corruption_params(dist_radial=(0.0, 0.0, 0.0), dist_tangent=(0.0, 0.0), psf_sigma=50)
    blurred = _render(connector, scene)

    # Full text width exactly; each panel title wraps within its own third of the strip.
    panel_w = ps.PAGE_W / 3
    fig, axes = plt.subplots(1, 3, figsize=ps.figsize_strip(3))
    _show_scene(axes[0], clean, "Clean", title_width_in=panel_w)
    _show_scene(axes[1], distorted, "Radial distortion (k1=0.5)", title_width_in=panel_w)
    _show_scene(axes[2], blurred, "Gaussian PSF (σ=50)", title_width_in=panel_w)
    fig.suptitle("Lens models")
    fig.tight_layout()
    ps.save_showcase(fig, "lens_effects")
    plt.close(fig)
