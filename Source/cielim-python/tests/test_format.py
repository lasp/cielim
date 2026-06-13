import numpy as np
import pytest

import context
from cielim import cielimMessage_pb2
from cielim.driver import *
from cielim.launcher import *


def default_scene():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]
    body.model.shapeModel = "sphere_normalized"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -0.5 * 1.496e11]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [20 * np.pi / 180, 20 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [2000, 2000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -100000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]

    return protobuf_message


@pytest.fixture
def scene_setup():
    return default_scene()


@pytest.mark.parametrize(
    "test_name",
    [
        ("RAW 8-bit"),
        ("RAW 12-bit"),
        ("RAW 12-bit packed"),
        ("RAW 16-bit"),
    ],
)
def test_Format(cielim_connection, scene_setup, test_name):
    """
    Tests raw image data is properly formatted.
    """
    connector = cielim_connection

    scene = scene_setup

    connector.send_init_request()
    connector.send_frame(scene)
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True)

    # Refer to CameraModel.cpp for raw format generation algorithms

    if test_name == "RAW 8-bit":
        scene.camera.imageFormat.format = cielimMessage_pb2.ImageFormat.RAW_8

        connector.send_frame(scene)
        data, _, _ = connector.request_image_for_camera_id(1, True, format_raw=True)

        test_image = np.frombuffer(data, dtype=np.uint8).reshape((2000, 2000, 3))

        max_value = 255

    elif test_name == "RAW 12-bit":
        scene.camera.imageFormat.format = cielimMessage_pb2.ImageFormat.RAW_12

        connector.send_frame(scene)
        data, _, _ = connector.request_image_for_camera_id(1, True, format_raw=True)

        test_image = (np.frombuffer(data, dtype=np.uint16) >> 4 & 0x0FFF).reshape((2000, 2000, 3))

        max_value = 4095

    elif test_name == "RAW 12-bit packed":
        scene.camera.imageFormat.format = cielimMessage_pb2.ImageFormat.RAW_12_PACKED

        connector.send_frame(scene)
        data, _, _ = connector.request_image_for_camera_id(1, True, format_raw=True)

        num_channels = 2000 * 2000 * 3
        num_pairs = (num_channels + 1) // 2
        raw = np.frombuffer(data, dtype=np.uint8).reshape((num_pairs, 3))
        b0 = raw[:, 0].astype(np.uint16)
        b1 = raw[:, 1].astype(np.uint16)
        b2 = raw[:, 2].astype(np.uint16)
        sample_a = (b0 | ((b1 & 0x0F) << 8)) & 0xFFF
        sample_b = ((b1 >> 4) | (b2 << 4)) & 0xFFF
        samples = np.empty(num_pairs * 2, dtype=np.uint16)
        samples[0::2] = sample_a
        samples[1::2] = sample_b
        test_image = (samples[:num_channels]).astype(np.uint16).reshape((2000, 2000, 3))

        max_value = 4095

    else:
        scene.camera.imageFormat.format = cielimMessage_pb2.ImageFormat.RAW_16

        connector.send_frame(scene)
        data, _, _ = connector.request_image_for_camera_id(1, True, format_raw=True)

        test_image = np.frombuffer(data, dtype=np.uint16).reshape((2000, 2000, 3))

        max_value = 65535

    assert test_image is not None, "No image data returned"
    assert (
        test_image.shape == baseline_image.shape
    ), f"Image shape mismatch: {test_image.shape} vs {baseline_image.shape}"

    assert test_image.min() != test_image.max(), "Image is uniform, likely a zeroed buffer"
    assert (
        test_image.min() >= 0 and test_image.max() <= max_value
    ), f"Values out of range: {test_image.min()}-{test_image.max()}"

    # Check the corners are black (dont' include alpha channel)

    corners = [test_image[0, 0], test_image[0, -1], test_image[-1, 0], test_image[-1, -1]]

    for corner in corners:
        assert np.all(corner[:3] == 0), f"Corner not black: {corner}"

    # Check the center pixel is max value for bit depth

    mid_y, mid_x = test_image.shape[0] // 2, test_image.shape[1] // 2
    assert np.all(test_image[mid_y, mid_x] == max_value), f"Middle pixel not max: {test_image[mid_y, mid_x]}"
