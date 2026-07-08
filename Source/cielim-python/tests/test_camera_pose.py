import cv2
import numpy as np
import pytest

import cielim


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere with zoomed-in fov.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 50000), attitude=(0, 1, 0))

    scene.set_lens_params(fov=(5 * np.pi / 180, 5 * np.pi / 180))  # Zoom in to make image close to orthogonal

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "test_name, shift",
    [
        ("No movement", [0, 0, 0]),
        ("Move Right", [1000, 0, 0]),
        ("Move Left", [-1000, 0, 0]),
        ("Move Up", [0, -1000, 0]),
        ("Move Down", [0, 1000, 0]),
    ],
)
def test_camera_position(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, shift):
    """
    Tests the effect of moving the camera on the asteroid's apparent position in the image.
    """
    connector = cielim_connection

    scene = default_scene

    initial_x, initial_y, initial_z = scene.get_scene().spacecraft.position[:3]

    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_contours, _ = cv2.findContours(baseline_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(baseline_contours, key=cv2.contourArea)
    (baseline_x, baseline_y), baseline_radius = cv2.minEnclosingCircle(largest_contour)

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_height, image_width = baseline_image.shape

    shifted = [initial_x + shift[0], initial_y + shift[1], initial_z]

    scene.set_spacecraft_params(position=tuple(shifted))

    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    moved_contours, _ = cv2.findContours(moved_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(moved_contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    object_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - object_position)

    # X shift is not inverted because +x points left (Unreal uses left handed coordinates)
    expected_pixel_shift_x = round(np.arctan(shift[0] / distance) * (image_width / camera_fov_horizontal))
    expected_pixel_shift_y = -round(np.arctan(shift[1] / distance) * (image_height / camera_fov_vertical))

    actual_pixel_shift_x = moved_x - baseline_x
    actual_pixel_shift_y = moved_y - baseline_y

    print(f"Test: {test_name}")
    print(f"Expected Pixel Shift (X, Y): ({expected_pixel_shift_x}, {expected_pixel_shift_y})")
    print(f"Actual Pixel Shift (X, Y): ({actual_pixel_shift_x}, {actual_pixel_shift_y})")

    np.testing.assert_allclose(
        [actual_pixel_shift_x, actual_pixel_shift_y],
        [expected_pixel_shift_x, expected_pixel_shift_y],
        atol=5,
        err_msg=f"Pixel shift mismatch for test: {test_name}",
    )


@pytest.mark.parametrize(
    "test_name, mrp_rotation",
    [
        ("No rotation", [0, 0, 0]),
        ("Rotate X-axis", [0.001, 0, 0]),
        ("Rotate Y-axis", [0, -0.001, 0]),
    ],
)
def test_camera_orientation(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, mrp_rotation):
    """
    Tests the effect of modifying the camera's orientation using MRPs on the asteroid's apparent position in the image.
    The expected pixel shifts are computed based on the new orientation.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_contours, _ = cv2.findContours(baseline_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(baseline_contours, key=cv2.contourArea)
    (baseline_x, baseline_y), baseline_radius = cv2.minEnclosingCircle(largest_contour)

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_height, image_width = baseline_image.shape

    sigma = np.array(mrp_rotation)
    sigma_norm = np.linalg.norm(sigma)
    theta = 4 * np.arctan(sigma_norm)

    rotation_axis = sigma / sigma_norm if sigma_norm > 0 else np.array([0, 0, 0])

    scene.set_camera_params(attitude=tuple(mrp_rotation))

    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    moved_contours, _ = cv2.findContours(moved_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(moved_contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)

    expected_pixel_shift_x = np.abs(rotation_axis[1]) * (theta) * (image_width / camera_fov_horizontal)
    expected_pixel_shift_y = np.abs(rotation_axis[0]) * (theta) * (image_height / camera_fov_vertical)

    actual_pixel_shift_x = moved_x - baseline_x
    actual_pixel_shift_y = moved_y - baseline_y

    print(f"Test: {test_name}")
    print(f"MRP: {mrp_rotation}")
    print(f"Expected Pixel Shift (X, Y): ({expected_pixel_shift_x}, {expected_pixel_shift_y})")
    print(f"Actual Pixel Shift (X, Y): ({actual_pixel_shift_x}, {actual_pixel_shift_y})")

    np.testing.assert_allclose(
        [actual_pixel_shift_x, actual_pixel_shift_y],
        [expected_pixel_shift_x, expected_pixel_shift_y],
        atol=5,
        err_msg=f"Pixel shift mismatch for test: {test_name}",
    )
