import context
from driver import *
from launcher import *
from context import cielimMessage_pb2
import numpy as np
import pytest
import cv2


def default_scene():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in [0, 0, 0]]

    body.model.shapeModel = "sphere_normalized"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -2000000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.resolution.append(item) for item in [4000, 3000]]

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
        ("Move Closer", [0, 0, -80000]),
        ("Move Away", [0, 0, 80000]),
        ("Move Away & Down", [0, 10000, 500000]),
        ("Move Closer & Right", [10000, 0, -500000]),
        ("Move Closer, Right & Up", [10000, -10000, -500000]),
        ("Move Away, Left & Down", [-10000, 10000, 500000]),
    ],
)
def test_asteroid_size(cielim_connection, scene_setup, test_name, shift):
    """
    This Remote Procedure call tests the asteroid size in pixels when its distance (Z) and slight position (X, Y) change.
    Parameters: Changing asteroid Z (closer/away) and slight X/Y shift, verifying pixel size.
    """
    connector = cielim_connection
    scene = scene_setup
    initial_position = scene.celestialBodies[0].position[:3]

    connector.send_frame(scene)
    asteroid_image, _ = connector.request_image_for_camera_id(1, 1)

    if len(asteroid_image.shape) == 3:
        asteroid_image = cv2.cvtColor(asteroid_image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(asteroid_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest_contour = max(contours, key=cv2.contourArea)
    (x, y), radius = cv2.minEnclosingCircle(largest_contour)

    shifted = [initial_position[i] + shift[i] for i in range(3)]
    scene.celestialBodies[0].ClearField("position")
    [scene.celestialBodies[0].position.append(item) for item in shifted]

    connector.send_frame(scene)
    moved_image, _ = connector.request_image_for_camera_id(1, 1)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(moved_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest_contour = max(contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)
    asteroid_size_pixels = 2 * int(moved_radius)

    mean_radius = scene.celestialBodies[0].model.meanRadius
    spacecraft_position = np.array(scene.spacecraft.position)
    asteroid_position = np.array(scene.celestialBodies[0].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)

    expected_angular_size_rad = 2 * np.arcsin(mean_radius / distance)
    camera_fov_horizontal = 20 * np.pi / 180
    image_width = 4000

    expected_asteroid_size_pixels = (expected_angular_size_rad / camera_fov_horizontal) * image_width

    np.testing.assert_allclose(
        asteroid_size_pixels,
        expected_asteroid_size_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid size in pixels does not match expected value for test: {test_name}",
    )

    cv2.circle(moved_image, (int(moved_x), int(moved_y)), int(moved_radius), (255, 255, 255), 2)
