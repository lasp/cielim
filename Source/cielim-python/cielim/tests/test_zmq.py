import context
from driver import *
from launcher import *
from context import cielimMessage_pb2
import numpy as np
import pytest

def scene_setup(spacecraft_position):
    protobuf_message = cielimMessage_pb2.CielimMessage()
    
    sc_pos_x, sc_pos_y, sc_pos_z = spacecraft_position

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in [0, 0, 0]]

    body.model.shapeModel = "sphere_normalized"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun_planet_data"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [sc_pos_x, sc_pos_y, sc_pos_z]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message

def test_ping():
    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())

    message = connector._send_ping()
    try:
        np.testing.assert_string_equal(message, "PONG")
    except AssertionError as e:
        print(f"Fail in test_ping: {e}")

    connector.disconnect()
    launcher.terminate()

def test_init_scene():
    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())

    # Init to ensure clean setup

    init_scene_message = connector.send_init_request()
    print(f"Init request: {init_scene_message}")
    try:
        np.testing.assert_string_equal(init_scene_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_init_scene: {e}")

    # Create scene

    send_frame_message = connector.send_frame(scene_setup((0, 0, -1000000)))
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

    send_frame_message = connector.send_frame(scene_setup((0, 0, 1000000)))
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_init_scene: {e}")

    # Get image and check for blank

    [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)
    
    np.testing.assert_equal(image, np.zeros_like(image), "Image was not cleared")

    connector.disconnect()
    launcher.terminate()

@pytest.mark.parametrize("position", [((100000, 0, -1000000)), ((10000, 0, -1000000)), ((1000, 10000, -1000000))])
def test_send_frame(position):
    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())

    # Init to ensure clean setup

    init_scene_message = connector.send_init_request()
    print(f"Init request: {init_scene_message}")
    try:
        np.testing.assert_string_equal(init_scene_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")

    # Create scene

    send_frame_message = connector.send_frame(scene_setup((0, 0, -1000000)))
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")

    # Update scene

    send_frame_message = connector.send_frame(scene_setup(position))
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")

    [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)

    # Check the object definitively moved on the screen

    try:
        assert not np.allclose(center_of_brightness, [1500, 2000], rtol=1e-4, atol=1)
    except AssertionError as e:
        print(f"Fail in test_send_frame: {e}")

    connector.disconnect()
    launcher.terminate()

@pytest.mark.parametrize("position", [((100000, 0, -1000000)), ((10000, 0, -1000000)), ((1000, 10000, -1000000))])
def test_request_image(position):
    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())

    # Init to ensure clean setup

    init_scene_message = connector.send_init_request()
    print(f"Init request: {init_scene_message}")
    try:
        np.testing.assert_string_equal(init_scene_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_request_image: {e}")

    # Create scene

    send_frame_message = connector.send_frame(scene_setup(position))
    print(f"Send frame: {send_frame_message}")
    try:
        np.testing.assert_string_equal(send_frame_message, "OK")
    except AssertionError as e:
        print(f"Fail in test_request_image: {e}")

    # Get image

    [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)

    # Check image is not null
    try:
        assert np.any(image)
    except AssertionError as e:
        print(f"Fail in test_request_image: {e}")

    connector.disconnect()
    launcher.terminate()
