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
    scene.set_spacecraft_params(position=(0, 0, 4000), attitude=(1, 0, 0))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Regolith", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "test_name, sun_position, phase_angle",
    [
        ("Full Illumination (0°)", [0, 0, 1.496e11], 0),
        ("(45° Horizontal)", [1.496e11, 0, 1.496e11], 45),
        ("Half Moon (90° Horizontal)", [1.496e11, 0, 0], 90),
        ("(135° Horizontal)", [1.496e11, 0, -1.496e11], 135),
        ("(45° Vertical)", [0, -1.496e11, 1.496e11], 45),
        ("Half Moon (90° Vertical)", [0, -1.496e11, 0], 90),
        ("(135° Vertical)", [0, -1.496e11, -1.496e11], 135),
    ],
)
def test_phase_angle_scene(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, sun_position, phase_angle
):
    """
    Tests the phase angle change by testing Center of Brightness (CoB) vs expected shift (by comparing expected and actual pixel shifts).
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_celestial_body_params(0, position=sun_position)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius
    asteroid_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)
    phase_angle_rad = np.radians(phase_angle)

    theta = np.arctan((4 * mean_radius) / (3 * np.pi * distance) * (1 - np.cos(phase_angle_rad)))

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_height, image_width, _ = image.shape

    sun_vector = np.array(sun_position) - asteroid_position
    sun_direction = sun_vector / np.linalg.norm(sun_vector)

    expected_cob_x = image_width / 2
    expected_cob_y = image_height / 2

    if abs(sun_direction[0]) > 1e-6:
        expected_cob_x += np.sign(sun_direction[0]) * theta * (image_width / camera_fov_horizontal)
        expected_cob_x = round(expected_cob_x)

    if abs(sun_direction[1]) > 1e-6:
        expected_cob_y += np.sign(sun_direction[1]) * theta * (image_height / camera_fov_vertical)
        expected_cob_y = round(expected_cob_y)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)
    if moments["m00"] != 0:
        # TODO understand why it works with ceil but not round or floor
        actual_cob_x = int(np.ceil(moments["m10"] / moments["m00"]))
        # We subtract here to flip +y=down for image data to +y=up
        actual_cob_y = image_height - int(np.ceil(moments["m01"] / moments["m00"]))

    else:
        actual_cob_x, actual_cob_y = image_width / 2, image_height / 2

    np.testing.assert_allclose(
        [actual_cob_x, actual_cob_y],
        [expected_cob_x, expected_cob_y],
        rtol=0.1,
        err_msg=f"CoB mismatch for test: {test_name}",
    )
