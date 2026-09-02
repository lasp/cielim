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
        ("Move Closer", [0, 0, 10000]),
        ("Move Away", [0, 0, -10000]),
        ("Move Away & Down", [0, -500, -10000]),
        ("Move Closer & Right", [500, 0, 10000]),
        ("Move Closer, Right & Up", [500, 500, 10000]),
        ("Move Away, Left & Down", [-500, -500, -10000]),
    ],
)
def test_asteroid_size(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, shift):
    """
    Tests the asteroid size in pixels when its distance (Z) and slight position (X, Y) change.
    Parameters: Changing asteroid Z (closer/away) and slight X/Y shift, verifying pixel size.
    """
    connector = cielim_connection

    scene = default_scene

    initial_position = scene.get_scene().celestialBodies[1].position[:3]

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_height, image_width, _ = baseline_image.shape

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(baseline_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest_contour = max(contours, key=cv2.contourArea)

    shifted = [initial_position[i] + shift[i] for i in range(3)]

    scene.set_celestial_body_params(1, position=tuple(shifted))

    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(moved_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest_contour = max(contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)
    asteroid_size_pixels = 2 * moved_radius

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius
    asteroid_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)

    expected_angular_size_rad = 2 * np.arcsin(mean_radius / distance)

    expected_asteroid_size_pixels = (expected_angular_size_rad / camera_fov_horizontal) * image_width

    np.testing.assert_allclose(
        asteroid_size_pixels,
        expected_asteroid_size_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid size in pixels does not match expected value for test: {test_name}",
    )

    cv2.circle(moved_image, (int(moved_x), int(moved_y)), int(moved_radius), (255, 255, 255), 2)
