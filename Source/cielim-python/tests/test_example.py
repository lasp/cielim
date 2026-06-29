import numpy as np

import cielim


def test_example(cielim_connection):
    """
    Example test function to demonstrate how to use the Cielim Python library.
    """
    connector = cielim_connection  # See conftest.py for the fixture that provides this connection

    scene = cielim.Scene()

    scene.set_sensor_params(resolution=(1250, 1000))

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(
        index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000
    )  # Position, attitude, and velocity default to 0.

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    [image, _, _] = connector.request_image_for_camera_id(1, True, False)

    height, width, _ = image.shape

    np.testing.assert_allclose(
        [width, height], [1250, 1000], rtol=0, atol=0, err_msg="Image does not have correct dimensions."
    )
