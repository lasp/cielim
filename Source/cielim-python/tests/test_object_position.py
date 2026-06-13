import cv2
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
    [sun.position.append(item) for item in [0, 0, -2000000]]
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


@pytest.fixture
def scene_setup():
    return default_scene()


@pytest.mark.parametrize(
    "test_name, shift",
    [
        ("No movement", [0, 0, 0]),
        ("Move Right", [10000, 0, 0]),
        ("Move Left", [-10000, 0, 0]),
        ("Move Up", [0, -10000, 0]),
        ("Move Down", [0, 10000, 0]),
    ],
)
def test_object_position(cielim_connection, scene_setup, test_name, shift):
    """
    This Remote Procedure call tests the asteroid movement in image space when shifted in 3D (X, Y).
    Parameters: Changing asteroid position in meters and verifying pixel shift.
    """
    connector = cielim_connection
    connector.send_init_request()
    scene = scene_setup
    initial_x, initial_y, initial_z = scene.celestialBodies[0].position[:3]

    connector.send_frame(scene)
    baseline_image, _, _ = connector.request_image_for_camera_id(1, 1)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_contours, _ = cv2.findContours(baseline_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(baseline_contours, key=cv2.contourArea)
    (baseline_x, baseline_y), baseline_radius = cv2.minEnclosingCircle(largest_contour)

    camera_fov_horizontal = 20 * np.pi / 180
    camera_fov_vertical = 15 * np.pi / 180
    image_width = 4000
    image_height = 3000

    shifted = [initial_x + shift[0], initial_y + shift[1], initial_z + shift[2]]
    scene.celestialBodies[0].ClearField("position")
    [scene.celestialBodies[0].position.append(item) for item in shifted]

    connector.send_frame(scene)
    moved_image, _, _ = connector.request_image_for_camera_id(1, 1)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    moved_contours, _ = cv2.findContours(moved_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(moved_contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)

    spacecraft_position = np.array(scene.spacecraft.position)
    object_position = np.array(scene.celestialBodies[0].position)
    distance = np.linalg.norm(spacecraft_position - object_position)

    expected_pixel_shift_x = np.arctan(shift[0] / distance) * (image_width / camera_fov_horizontal)
    expected_pixel_shift_y = np.arctan(shift[1] / distance) * (image_height / camera_fov_vertical)

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
