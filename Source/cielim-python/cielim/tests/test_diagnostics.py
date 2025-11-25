import context
from driver import *
from launcher import *
from context import cielimMessage_pb2
import numpy as np
import pytest


@pytest.fixture
def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "sphere_normalized"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def test_request_image_and_center_of_brightness(cielim_connection, scene_setup):
    connector = cielim_connection
    connector.send_init_request()
    connector.send_frame(scene_setup)

    [image, center_of_brightness, _] = connector.request_image_for_camera_id(1, 1)
    height, width, channels = image.shape
    np.testing.assert_allclose([4000, 3000], [width, height], rtol=0, atol=0, err_msg="Returned image not correct")

    true_center_of_brightness = [1999.5, 1499.5]
    np.testing.assert_allclose(
        center_of_brightness,
        true_center_of_brightness,
        rtol=0,
        atol=1e-1,
        err_msg="Center of brightness not close enough to expected",
    )


def test_request_only_center_of_brightness(cielim_connection, scene_setup):
    connector = cielim_connection
    connector.send_frame(scene_setup)

    [image, center_of_brightness, _] = connector.request_image_for_camera_id(1, 0)

    assert image == None

    true_center_of_brightness = [1999.5, 1499.5]
    np.testing.assert_allclose(
        center_of_brightness,
        true_center_of_brightness,
        rtol=0,
        atol=1e-1,
        err_msg="Center of brightness not close enough to expected",
    )


@pytest.mark.parametrize(
    "center_x, center_y, width, height",
    [
        (2000, 1500, 4000, 3000),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 1000, 750),
        (2000, 1500, 500, 375),
        (2000, 1500, 250, 250),
    ],
)
def test_coverage(cielim_connection, scene_setup, center_x, center_y, width, height):
    connector = cielim_connection

    scene_setup.camera.areaOfInterest.centerX = center_x
    scene_setup.camera.areaOfInterest.centerY = center_y
    scene_setup.camera.areaOfInterest.width = width
    scene_setup.camera.areaOfInterest.height = height

    threshold = 0.01

    scene_setup.camera.areaOfInterest.threshold = threshold

    del scene_setup.spacecraft.position[:]
    [scene_setup.spacecraft.position.append(item) for item in [0, 0, -1 * 75000]]  # Make circle fill most of the screen

    connector.send_frame(scene_setup)

    [image, _, coverage] = connector.request_image_for_camera_id(1)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Compute bounds
    x1 = max(center_x - width // 2, 0)
    y1 = max(center_y - height // 2, 0)
    x2 = min(center_x + width // 2, 4000)
    y2 = min(center_y + height // 2, 3000)

    bounds = gray[y1 : y2 + 1, x1 : x2 + 1]

    mask_total = gray > threshold * 255
    mask_covered = bounds > threshold * 255

    # Ratio of bright pixels
    pct = np.sum(mask_covered) / np.sum(mask_total)

    np.testing.assert_allclose(
        coverage,
        pct,
        rtol=0.02,
        err_msg=f"Coverage not close enough to expected",
    )
