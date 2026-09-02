import cv2
import numpy as np
import pytest

import cielim


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
    Tests that reducing exposure time, transmission factor, and QE reduces image brightness.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    base_mean = np.mean(image_gray)

    scene.set_sensor_params(exposure=1e-4)  # Reduce exposure time

    # connector.send_init_request()
    connector.send_frame(scene.get_scene())
    low_exposure_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    low_exposure_image_gray = cv2.cvtColor(low_exposure_image, cv2.COLOR_BGR2GRAY)
    low_exposure_mean = np.mean(low_exposure_image_gray)

    np.testing.assert_array_less(
        low_exposure_mean, base_mean, err_msg="Brightness did not decrease with lower exposure."
    )

    scene.set_lens_params(transmission=(0.25, 0.25, 0.25))  # Reduce transmission factor

    connector.send_frame(scene.get_scene())
    low_transmission_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    low_transmission_image_gray = cv2.cvtColor(low_transmission_image, cv2.COLOR_BGR2GRAY)
    low_transmission_mean = np.mean(low_transmission_image_gray)

    np.testing.assert_array_less(
        low_transmission_mean, low_exposure_mean, err_msg="Brightness did not decrease with lower transmission."
    )

    scene.set_sensor_params(
        qe_chan1=(0.25, 0.25, 0.25), qe_chan2=(0.25, 0.25, 0.25), qe_chan3=(0.25, 0.25, 0.25)
    )  # Reduce QE

    # connector.send_init_request()
    connector.send_frame(scene.get_scene())
    low_qe_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    low_qe_image_gray = cv2.cvtColor(low_qe_image, cv2.COLOR_BGR2GRAY)
    low_qe_mean = np.mean(low_qe_image_gray)

    np.testing.assert_array_less(
        low_qe_mean, low_transmission_mean, err_msg="Brightness did not decrease with lower QE."
    )


@pytest.mark.parametrize(
    "test_name, fov_x_deg, fov_y_deg",
    [
        ("Standard FOV", 20 * np.pi / 180, 15 * np.pi / 180),
        ("Medium FOV", 10 * np.pi / 180, 8 * np.pi / 180),
        ("Narrow FOV", 5 * np.pi / 180, 4 * np.pi / 180),
        ("Wide FOV", 20 * np.pi / 180, 5 * np.pi / 180),
        ("Tall FOV", 5 * np.pi / 180, 20 * np.pi / 180),
    ],
)
def test_camera_fov(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, fov_x_deg, fov_y_deg):
    """
    Tests that the object in the scene is the correct apparent size given the x and y fov values.
    Does not account for perspective distortion.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_lens_params(fov=(fov_x_deg, fov_y_deg))

    scene.set_spacecraft_params(position=(0, 0, 100000))  # Move spacecraft back to avoid overflow

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w, h = cv2.boundingRect(largest_contour)

    connector.send_init_request()  # Make sure scene is cleared

    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius
    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    asteroid_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)

    expected_angular_size_rad = 2 * np.arcsin(mean_radius / distance)

    image_height, image_width = image.shape

    expected_asteroid_w_pixels = (expected_angular_size_rad / fov_x_deg) * image_width
    expected_asteroid_h_pixels = (expected_angular_size_rad / fov_y_deg) * image_height

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


@pytest.mark.parametrize(
    "test_name, resolution_w, resolution_h",
    [
        ("Medium resolution", 2000, 1000),
        ("Low resolution", 700, 700),
    ],
)
def test_camera_resolution(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, resolution_w, resolution_h
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

    contours, _ = cv2.findContours(base_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w_base, h_base = cv2.boundingRect(largest_contour)

    image_height, image_width = base_image.shape

    w_ratio_to_res_baseline = w_base / image_width
    h_ratio_to_res_baseline = h_base / image_height

    scene.set_sensor_params(resolution=(resolution_w, resolution_h))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w, h = cv2.boundingRect(largest_contour)

    w_ratio_to_res = w / resolution_w
    h_ratio_to_res = h / resolution_h

    connector.send_init_request()  # Make sure scene is cleared

    np.testing.assert_allclose(
        w_ratio_to_res,
        w_ratio_to_res_baseline,
        rtol=0.1,
        err_msg=f"Mismatch between horizontal apparent size with baseline: {test_name}",
    )

    np.testing.assert_allclose(
        h_ratio_to_res,
        h_ratio_to_res_baseline,
        rtol=0.1,
        err_msg=f"Mismatch between vertical apparent size with baseline: {test_name}",
    )
