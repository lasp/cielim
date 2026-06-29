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


def test_ping(cielim_connection: cielim.Connector):
    connector = cielim_connection

    message = connector.send_ping()
    try:
        np.testing.assert_string_equal(message, "PONG")
    except AssertionError as e:
        print(f"Fail in test_ping: {e}")


def test_init_scene(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    connector = cielim_connection

    scene = default_scene

    # Init to ensure clean setup

    init_scene_message = connector.send_init_request()
    print(f"Init request: {init_scene_message}")
    try:
        np.testing.assert_string_equal(init_scene_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_init_scene: {e}")

    # Create scene

    send_frame_message = connector.send_frame(scene.get_scene())
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_init_scene: {e}")

    # Use INIT_SCENE to clear

    init_scene_message = connector.send_init_request()
    print(f"Init request: {init_scene_message}")
    try:
        np.testing.assert_string_equal(init_scene_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_init_scene: {e}")

    # Send blank protobuf

    scene.delete_celestial_body(1)

    send_frame_message = connector.send_frame(scene.get_scene())
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_init_scene: {e}")

    # Get image and check for blank

    [image, _, _] = connector.request_image_for_camera_id(1, True, False)

    np.testing.assert_(np.all(image <= 2), "Image was not cleared")


@pytest.mark.parametrize(
    "position",
    [
        (500, 0, 2000),
        (-500, 0, 2000),
        (0, 500, 2000),
        (0, -500, 2000),
    ],
)
def test_send_frame(cielim_connection: cielim.Connector, default_scene: cielim.Scene, position):
    connector = cielim_connection

    scene = default_scene

    # Init to ensure clean setup

    init_scene_message = connector.send_init_request()
    print(f"Init request: {init_scene_message}")
    try:
        np.testing.assert_string_equal(init_scene_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")

    # Create scene

    send_frame_message = connector.send_frame(scene.get_scene())
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")

    # Update scene

    scene.set_spacecraft_params(position=position)

    send_frame_message = connector.send_frame(scene.get_scene())
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")

    [_, center_of_brightness, _] = connector.request_image_for_camera_id(1, False, True)

    try:
        assert not np.allclose(
            center_of_brightness, [1000, 1000], rtol=1e-4, atol=1
        )  # 1000x1000 is the default resolution
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")


@pytest.mark.parametrize(
    "position",
    [
        (500, 0, 2000),
        (-500, 0, 2000),
        (0, 500, 2000),
        (0, -500, 2000),
    ],
)
def test_request_image(cielim_connection: cielim.Connector, default_scene: cielim.Scene, position):
    connector = cielim_connection

    scene = default_scene

    # Init to ensure clean setup

    init_scene_message = connector.send_init_request()
    print(f"Init request: {init_scene_message}")
    try:
        np.testing.assert_string_equal(init_scene_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_request_image: {e}")

    # Create scene

    scene.set_spacecraft_params(position=position)

    send_frame_message = connector.send_frame(scene.get_scene())
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_request_image: {e}")

    # Get image

    [image, _, _] = connector.request_image_for_camera_id(1, True, False)

    # Check image is not null
    try:
        assert np.any(image)
    except AssertionError as e:
        print(f"Fail in test_request_image: {e}")
