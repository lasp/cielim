import cv2
import numpy as np
import pytest

import cielim

baseline_exposure = 0.001  # seconds, matches Scene.__init__ default
baseline_qe = (1.0, 1.0, 1.0)
baseline_transmission = (1.0, 1.0, 1.0)
halved_exposure = baseline_exposure / 2  # used to check linear proportionality, not just direction
baseline_well_capacity = 2_000_000  # electrons avoids saturation without going too dim to measure.
# exposureTime=0.0 can't be sent through SIM_UPDATE
near_zero_exposure = 1e-15  # seconds


def lit_pixel_mean(image_gray: np.ndarray) -> float:
    """
    Mean of lit pixels only avoids the black background skewing brightness comparisons
    """
    lit = image_gray[image_gray > 0]
    return float(np.mean(lit)) if lit.size else 0.0


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


def test_image_brightness(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Tests that reducing exposure time, transmission factor, and QE reduces image brightness,
    and that brightness scales proportionally (not just directionally) with exposure time.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_sensor_params(
        exposure=baseline_exposure,
        gamma=1.0,
        well_capacity=baseline_well_capacity,
        qe_chan1=baseline_qe,
        qe_chan2=baseline_qe,
        qe_chan3=baseline_qe,
    )

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    base_mean = lit_pixel_mean(image_gray)

    assert np.max(image_gray) < 255, (
        "Baseline render is fully saturated (max pixel = 255) — the exposure-halving check below "
        "can't detect a brightness difference against a clipped signal. Lower baseline_exposure or "
        "raise baseline_well_capacity further."
    )

    scene.set_sensor_params(exposure=halved_exposure)  # Halve exposure time

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    low_exposure_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    low_exposure_image_gray = cv2.cvtColor(low_exposure_image, cv2.COLOR_BGR2GRAY)
    low_exposure_mean = lit_pixel_mean(low_exposure_image_gray)

    np.testing.assert_array_less(
        low_exposure_mean, base_mean, err_msg="Brightness did not decrease with lower exposure."
    )

    np.testing.assert_allclose(
        low_exposure_mean,
        base_mean / 2,
        rtol=0.15,
        err_msg="Brightness did not scale proportionally (halve) when exposure time was halved.",
    )

    scene.set_sensor_params(exposure=baseline_exposure)  # Restore baseline so the transmission test is isolated

    scene.set_lens_params(transmission=(0.25, 0.25, 0.25))  # Reduce transmission factor

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    low_transmission_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    low_transmission_image_gray = cv2.cvtColor(low_transmission_image, cv2.COLOR_BGR2GRAY)
    low_transmission_mean = lit_pixel_mean(low_transmission_image_gray)

    np.testing.assert_array_less(
        low_transmission_mean, base_mean, err_msg="Brightness did not decrease with lower transmission."
    )

    scene.set_lens_params(transmission=baseline_transmission)  # Restore baseline so the QE test is isolated

    scene.set_sensor_params(
        qe_chan1=(0.25, 0.25, 0.25), qe_chan2=(0.25, 0.25, 0.25), qe_chan3=(0.25, 0.25, 0.25)
    )  # Reduce QE

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    low_qe_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    low_qe_image_gray = cv2.cvtColor(low_qe_image, cv2.COLOR_BGR2GRAY)
    low_qe_mean = lit_pixel_mean(low_qe_image_gray)

    np.testing.assert_array_less(low_qe_mean, base_mean, err_msg="Brightness did not decrease with lower QE.")


def test_near_zero_exposure_produces_black_image(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Tests that a vanishingly short exposure time (effectively no shutter time to collect photons)
    produces a fully black image.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_sensor_params(exposure=near_zero_exposure)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    assert np.all(image_gray == 0), "Image was not fully black with a near-zero exposure time."


@pytest.mark.parametrize(
    "test_name, fov_x_rad, fov_y_rad",
    [
        ("Standard FOV", 20 * np.pi / 180, 15 * np.pi / 180),
        ("Medium FOV", 10 * np.pi / 180, 8 * np.pi / 180),
        ("Narrow FOV", 5 * np.pi / 180, 4 * np.pi / 180),
        ("Wide FOV", 20 * np.pi / 180, 5 * np.pi / 180),
        ("Tall FOV", 5 * np.pi / 180, 20 * np.pi / 180),
    ],
)
def test_camera_fov(
    cielim_connection: cielim.Connector,
    default_scene: cielim.Scene,
    test_name,
    fov_x_rad,
    fov_y_rad,
):
    """
    Tests that the object in the scene is the correct apparent size given the x and y fov values.
    Does not account for perspective distortion.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_lens_params(fov=(fov_x_rad, fov_y_rad))

    scene.set_spacecraft_params(position=(0, 0, 100000))  # Move spacecraft back to avoid overflow

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert contours, f"No contours found in rendered image for test: {test_name}"

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w, h = cv2.boundingRect(largest_contour)

    connector.send_init_request()  # Make sure scene is cleared

    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius
    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    asteroid_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)

    expected_angular_size_rad = 2 * np.arcsin(mean_radius / distance)

    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    expected_asteroid_w_pixels = (expected_angular_size_rad / fov_x_rad) * image_width
    expected_asteroid_h_pixels = (expected_angular_size_rad / fov_y_rad) * image_height

    np.testing.assert_allclose(
        w,
        expected_asteroid_w_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid width in pixels does not match expected value for test: {test_name}",
    )

    np.testing.assert_allclose(
        h,
        expected_asteroid_h_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid height in pixels does not match expected value for test: {test_name}",
    )


def test_camera_fov_overflow(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Tests that an object much larger than the frame is clipped to the
    image bounds instead of crashing the render or producing an out-of-frame measurement.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_lens_params(fov=(5 * np.pi / 180, 5 * np.pi / 180))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert contours, "No contours found in rendered image for FOV overflow test."

    largest_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest_contour)

    connector.send_init_request()

    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    assert w <= image_width and h <= image_height, "Bounding box exceeds image dimensions; overflow was not clipped."

    assert (
        x <= 0 or y <= 0 or x + w >= image_width or y + h >= image_height
    ), "Object did not touch any frame edge; this scenario is not actually testing overflow/clipping."


@pytest.mark.parametrize(
    "test_name, resolution_w, resolution_h",
    [
        ("Medium resolution", 2000, 1000),
        ("Low resolution", 700, 700),
        ("High resolution", 2000, 2000),  # upscale in both dimensions vs. default_scene's 1000x1000 baseline
    ],
)
def test_camera_resolution(
    cielim_connection: cielim.Connector,
    default_scene: cielim.Scene,
    test_name,
    resolution_w,
    resolution_h,
):
    """
    Tests that the relative apparent image size is constant across different resolutions by comparing
    the side lengths of the bounding box surrounding the object in the scene.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    base_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(base_image.shape) == 3:
        base_image = cv2.cvtColor(base_image, cv2.COLOR_BGR2GRAY)

    _, base_thresh = cv2.threshold(base_image, 127, 255, cv2.THRESH_BINARY)

    base_contours, _ = cv2.findContours(base_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert base_contours, f"No contours found in baseline rendered image for test: {test_name}"

    largest_base_contour = max(base_contours, key=cv2.contourArea)
    _, _, w_base, h_base = cv2.boundingRect(largest_base_contour)

    image_width_base, image_height_base = scene.get_scene().camera.sensorModel.resolution

    w_ratio_to_res_baseline = w_base / image_width_base
    h_ratio_to_res_baseline = h_base / image_height_base

    scene.set_sensor_params(resolution=(resolution_w, resolution_h))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert contours, f"No contours found in rendered image for test: {test_name}"

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w, h = cv2.boundingRect(largest_contour)

    w_ratio_to_res = w / resolution_w
    h_ratio_to_res = h / resolution_h

    connector.send_init_request()  # Make sure scene is cleared

    np.testing.assert_allclose(
        w_ratio_to_res,
        w_ratio_to_res_baseline,
        rtol=0.02,
        err_msg=f"Mismatch between horizontal apparent size with baseline: {test_name}",
    )

    np.testing.assert_allclose(
        h_ratio_to_res,
        h_ratio_to_res_baseline,
        rtol=0.02,
        err_msg=f"Mismatch between vertical apparent size with baseline: {test_name}",
    )
