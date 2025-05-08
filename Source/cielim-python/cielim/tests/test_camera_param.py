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
    [protobuf_message.camera.fieldOfView.append(item) for item in [30 * np.pi / 180, 25 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]

    return protobuf_message


@pytest.fixture
def scene_setup():
    return default_scene()


@pytest.mark.parametrize(
    "test_name, fov_x_deg, fov_y_deg",
    [
        ("FOV", 20 * np.pi / 180, 15 * np.pi / 180),
        ("Medium FOV", 10 * np.pi / 180, 8 * np.pi / 180),
        ("Narrow FOV", 5 * np.pi / 180, 4 * np.pi / 180),
    ],
)
def test_camera_fov(cielim_connection, scene_setup, test_name, fov_x_deg, fov_y_deg):
    """
    This remote procedure call test changes the field of view and checks for appropriate apparent size.
    """
    connector = cielim_connection
    connector.send_init_request()

    scene = scene_setup
    del scene.camera.fieldOfView[:]
    [scene.camera.fieldOfView.append(val) for val in [fov_x_deg, fov_y_deg]]

    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    (_, _), radius = cv2.minEnclosingCircle(largest_contour)
    asteroid_size_pixels = 2 * int(radius)

    connector.send_init_request()

    mean_radius = scene.celestialBodies[0].model.meanRadius
    spacecraft_position = np.array(scene.spacecraft.position)
    asteroid_position = np.array(scene.celestialBodies[0].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)

    expected_angular_size_rad = 2 * np.arcsin(mean_radius / distance)
    camera_fov_horizontal = fov_x_deg
    image_width = 4000

    expected_asteroid_size_pixels = (expected_angular_size_rad / camera_fov_horizontal) * image_width

    np.testing.assert_allclose(
        asteroid_size_pixels,
        expected_asteroid_size_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid size in pixels does not match expected value for test: {test_name}",
    )


def get_baseline_resolution(connector):
    scene = default_scene()

    del scene.camera.resolution[:]
    [scene.camera.resolution.append(val) for val in [4000, 3000]]

    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    (_, _), radius = cv2.minEnclosingCircle(largest_contour)
    baseline_size_pixels = 2 * int(radius)

    connector.send_init_request()

    return baseline_size_pixels


@pytest.mark.parametrize(
    "test_name, resolution_w, resolution_h",
    [
        ("Medium resolution", 2000, 1000),
        ("Low resolution", 700, 700),
    ],
)
def test_camera_resolution(cielim_connection, scene_setup, test_name, resolution_w, resolution_h):
    """
    This remote procedure call test changes the resolution and checks for appropriate apparent size along with ratio of the image and the apparent diameter.
    """
    connector = cielim_connection
    connector.send_init_request()

    scene = scene_setup
    del scene.camera.resolution[:]
    [scene.camera.resolution.append(val) for val in [resolution_w, resolution_h]]
    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    (_, _), radius = cv2.minEnclosingCircle(largest_contour)
    asteroid_size_pixels = 2 * int(radius)

    connector.send_init_request()

    baseline_size_pixels = get_baseline_resolution(cielim_connection)
    asteroid_size_pixels_ratio = asteroid_size_pixels / resolution_w
    baseline_size_pixels_ration = baseline_size_pixels / 4000

    resolution_deg = resolution_w * (30 * np.pi / 180 / resolution_w)
    baseline_resolution_deg = 4000 * (30 * np.pi / 180 / 4000)

    np.testing.assert_allclose(
        asteroid_size_pixels_ratio,
        baseline_size_pixels_ration,
        rtol=0.1,
        err_msg=f"Ratio of the image and the apparent diameter does not match: {test_name}",
    )

    np.testing.assert_allclose(
        resolution_deg,
        baseline_resolution_deg,
        rtol=0.1,
        err_msg=f"Resolution in degrees does not match: {test_name}",
    )
