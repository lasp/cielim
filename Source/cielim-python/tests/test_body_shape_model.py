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

    scene.set_sensor_params(exposure=1e-5)

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "test_name, shape_model",
    [
        ("bennu", "bennu_normalized"),
        ("itokawa", "itokawa_normalized"),
        ("67p", "67p_normalized"),
    ],
)
def test_center_of_brightness_shift(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, shape_model
):
    """
    This test loads different shape models and checks the movement.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    base_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(base_image.shape) == 3:
        base_image = cv2.cvtColor(base_image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(base_image)
    assert moments["m00"] != 0, "No brightness detected in baseline sphere image."

    base_cob_x = int(moments["m10"] / moments["m00"])
    base_cob_y = int(moments["m01"] / moments["m00"])

    scene.set_celestial_body_params(1, mesh_shape=shape_model)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)

    assert moments["m00"] != 0, f"No brightness detected in test: {test_name}"

    cob_x = int(moments["m10"] / moments["m00"])
    cob_y = int(moments["m01"] / moments["m00"])

    diff = np.linalg.norm(np.array((cob_x, cob_y)) - np.array((base_cob_x, base_cob_y)))

    np.testing.assert_(
        diff > 2, msg=f"{test_name}: CoB too close to sphere (= {diff:.2f}px) — shape model may be too similar."
    )
