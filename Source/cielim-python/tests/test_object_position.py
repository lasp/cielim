import sys
from pathlib import Path

import cielim
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scenes.common import default_scene


def moments_centroid(image_gray: np.ndarray, test_name: str) -> tuple[float, float]:
    """
    Sub-pixel center via image moments.
    """
    moments = cv2.moments(image_gray)
    assert moments["m00"] > 0, f"No illuminated body detected in rendered image for test: {test_name}"
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


@pytest.mark.parametrize(
    "test_name, shift",
    [
        ("Move Right", [1000, 0, 0]),
        ("Move Left", [-1000, 0, 0]),
        ("Move Up", [0, 1000, 0]),
        ("Move Down", [0, -1000, 0]),
        ("Move Diagonal", [1000, 1000, 0]),
    ],
)
def test_object_position(cielim_connection: cielim.Connector, test_name, shift):
    """
    Tests that moving an object shifts its position in the image as expected.
    """
    connector = cielim_connection

    scene = default_scene()

    initial_x, initial_y, initial_z = scene.get_scene().celestialBodies[1].position[:3]

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_x, baseline_y = moments_centroid(baseline_image, test_name)

    np.testing.assert_allclose(
        [baseline_x, baseline_y],
        [image_width / 2, image_height / 2],
        atol=5,
        err_msg=f"Baseline (pre-shift) object position was not centered for test: {test_name}",
    )

    shifted = [initial_x + shift[0], initial_y + shift[1], initial_z + shift[2]]

    scene.set_celestial_body_params(1, position=tuple(shifted))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    moved_x, moved_y = moments_centroid(moved_image, test_name)

    object_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - object_position)

    expected_pixel_shift_x = np.arctan(shift[0] / distance) * (image_width / camera_fov_horizontal)
    # We multiply by -1 here to account for +y being down for image data
    expected_pixel_shift_y = -np.arctan(shift[1] / distance) * (image_height / camera_fov_vertical)

    actual_pixel_shift_x = moved_x - baseline_x
    actual_pixel_shift_y = moved_y - baseline_y

    np.testing.assert_allclose(
        [actual_pixel_shift_x, actual_pixel_shift_y],
        [expected_pixel_shift_x, expected_pixel_shift_y],
        atol=2,
        err_msg=f"Pixel shift mismatch for test: {test_name}",
    )


@pytest.mark.parametrize(
    "test_name, z_shift",
    [
        ("Move Closer", 10000),
        ("Move Farther", -10000),
    ],
)
def test_object_distance(cielim_connection: cielim.Connector, test_name, z_shift):
    """
    Tests moving the object along the boresight (Z) axis: its apparent size should match the
    sphere's angular size at the new distance, and its apparent center should stay put (a depth-only
    move causes no lateral pixel shift).
    """
    connector = cielim_connection

    scene = default_scene()

    initial_x, initial_y, initial_z = scene.get_scene().celestialBodies[1].position[:3]
    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius
    camera_fov_horizontal, camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView
    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_x, baseline_y = moments_centroid(baseline_image, test_name)

    _, baseline_thresh = cv2.threshold(baseline_image, 127, 255, cv2.THRESH_BINARY)
    baseline_contours, _ = cv2.findContours(baseline_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert baseline_contours, f"No contours found in baseline rendered image for test: {test_name}"

    _, baseline_radius = cv2.minEnclosingCircle(max(baseline_contours, key=cv2.contourArea))
    baseline_size_pixels = 2 * baseline_radius

    baseline_distance = np.linalg.norm(spacecraft_position - np.array([initial_x, initial_y, initial_z]))
    baseline_expected_angular_size_rad = 2 * np.arcsin(mean_radius / baseline_distance)

    np.testing.assert_allclose(
        baseline_size_pixels,
        (baseline_expected_angular_size_rad / camera_fov_horizontal) * image_width,
        rtol=0.01,
        atol=1,
        err_msg=f"Baseline object size in pixels does not match expected value for test: {test_name}",
    )

    # Z increases toward the spacecraft (which sits at z=50000, with the object starting near
    # the origin), so a positive z_shift moves the object closer.
    moved_position = np.array([initial_x, initial_y, initial_z + z_shift])
    scene.set_celestial_body_params(1, position=tuple(moved_position))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    moved_x, moved_y = moments_centroid(moved_image, test_name)

    _, moved_thresh = cv2.threshold(moved_image, 127, 255, cv2.THRESH_BINARY)
    moved_contours, _ = cv2.findContours(moved_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert moved_contours, f"No contours found in moved rendered image for test: {test_name}"

    _, moved_radius = cv2.minEnclosingCircle(max(moved_contours, key=cv2.contourArea))
    moved_size_pixels = 2 * moved_radius

    moved_distance = np.linalg.norm(spacecraft_position - moved_position)
    expected_angular_size_rad = 2 * np.arcsin(mean_radius / moved_distance)

    # Checked against both width/horizontal-FOV and height/vertical-FOV — a sphere rendered with
    # the wrong aspect ratio would still pass a width-only check as long as its horizontal extent
    # happened to be right.
    np.testing.assert_allclose(
        moved_size_pixels,
        (expected_angular_size_rad / camera_fov_horizontal) * image_width,
        rtol=0.01,
        atol=1,
        err_msg=f"Object size (vs. width/horizontal FOV) does not match expected value for test: {test_name}",
    )

    np.testing.assert_allclose(
        moved_size_pixels,
        (expected_angular_size_rad / camera_fov_vertical) * image_height,
        rtol=0.01,
        atol=1,
        err_msg=f"Object size (vs. height/vertical FOV) does not match expected value for test: {test_name}",
    )

    np.testing.assert_allclose(
        [moved_x, moved_y],
        [baseline_x, baseline_y],
        atol=5,
        err_msg=f"Center shifted for a depth-only (Z-axis) move: {test_name}",
    )
