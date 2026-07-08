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

    # Rotate so +x is right, +y is up, and +z is out of the page
    scene.set_spacecraft_params(position=(0, 0, 50000), attitude=(1, 0, 0))

    scene.set_lens_params(fov=(5 * np.pi / 180, 5 * np.pi / 180))  # Zoom in to make image close to orthogonal

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Regolith", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "test_name, shift",
    [
        ("No movement", [0, 0, 0]),
        ("Move Right", [1000, 0, 0]),
        ("Move Left", [-1000, 0, 0]),
        ("Move Up", [0, 1000, 0]),
        ("Move Down", [0, -1000, 0]),
    ],
)
def test_object_position(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, shift):
    """
    Tests the asteroid movement in image space when shifted in 3D (X, Y).
    Parameters: Changing asteroid position in meters and verifying pixel shift.
    """
    connector = cielim_connection

    scene = default_scene

    initial_x, initial_y, initial_z = scene.get_scene().celestialBodies[1].position[:3]

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_height, image_width, _ = baseline_image.shape

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_contours, _ = cv2.findContours(baseline_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(baseline_contours, key=cv2.contourArea)
    (baseline_x, baseline_y), baseline_radius = cv2.minEnclosingCircle(largest_contour)

    shifted = [initial_x + shift[0], initial_y + shift[1], initial_z + shift[2]]

    scene.set_celestial_body_params(1, position=tuple(shifted))

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

    expected_pixel_shift_x = np.arctan(shift[0] / distance) * (image_width / camera_fov_horizontal)
    # We multiply by -1 here to account for +y being down for image data
    expected_pixel_shift_y = -np.arctan(shift[1] / distance) * (image_height / camera_fov_vertical)

    actual_pixel_shift_x = moved_x - baseline_x
    actual_pixel_shift_y = moved_y - baseline_y

    print(f"Test: {test_name}")
    print(f"Expected Pixel Shift (X, Y): ({expected_pixel_shift_x}, {expected_pixel_shift_y})")
    print(f"Actual Pixel Shift (X, Y): ({actual_pixel_shift_x}, {actual_pixel_shift_y})")

    np.testing.assert_allclose(
        [actual_pixel_shift_x, actual_pixel_shift_y],
        [expected_pixel_shift_x, expected_pixel_shift_y],
        atol=2,
        err_msg=f"Pixel shift mismatch for test: {test_name}",
    )
