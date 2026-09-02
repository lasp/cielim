import cv2
import numpy as np
import pytest

import cielim


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere with the sun lighting left half.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    scene.set_celestial_body_params(0, position=(1.496e11, 0, 0))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "test_name, distortion",
    [
        ("Distort X", [1.5, 1, 1]),
        ("Distort Y", [1, 1.5, 1]),
    ],
)
def test_body_scaling(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, distortion):
    """
    Tests that the center of brightness (CoB) shifts appropriately when the principal axes of the asteroid are distorted.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    base_image, _, _ = cielim_connection.request_image_for_camera_id(1, True, False)

    if len(base_image.shape) == 3:
        base_image = cv2.cvtColor(base_image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(base_image)
    assert moments["m00"] != 0, "No brightness detected in baseline scene."

    base_cob_x = int(moments["m10"] / moments["m00"])
    base_cob_y = int(moments["m01"] / moments["m00"])

    scene.set_celestial_body_params(1, mesh_distortions=distortion)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)
    assert moments["m00"] != 0, f"No brightness detected in test: {test_name}"

    cob_x = int(moments["m10"] / moments["m00"])
    cob_y = int(moments["m01"] / moments["m00"])

    diff = np.array((cob_x, cob_y)) - np.array((base_cob_x, base_cob_y))
    diff_x = abs(diff[0])
    diff_y = abs(diff[1])

    if test_name == "Distort X":
        np.testing.assert_(diff_x >= 5, msg=f"{test_name}: X shift too small (= {diff_x:.2f}px).")
    elif test_name == "Distort Y":
        np.testing.assert_(diff_y <= 1, msg=f"{test_name}: Y shift too large (= {diff_y:.2f}px), expected is 0.")
