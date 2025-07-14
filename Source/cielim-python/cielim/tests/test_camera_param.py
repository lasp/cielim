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
        ("Standard FOV", 20 * np.pi / 180, 15 * np.pi / 180),
        ("Medium FOV", 10 * np.pi / 180, 8 * np.pi / 180),
        ("Narrow FOV", 5 * np.pi / 180, 4 * np.pi / 180),
        ("Wide FOV", 20 * np.pi / 180, 5 * np.pi / 180),
        ("Tall FOV", 5 * np.pi / 180, 20 * np.pi / 180),
    ],
)
def test_camera_fov(cielim_connection, scene_setup, test_name, fov_x_deg, fov_y_deg):
    """
    Tests that the object in the scene is the correct apparent size given the x and y fov values.
    Does not account for perspective distortion.
    """
    connector = cielim_connection

    scene = scene_setup
    del scene.camera.fieldOfView[:]
    [scene.camera.fieldOfView.append(val) for val in [fov_x_deg, fov_y_deg]]

    connector.send_init_request()
    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w, h = cv2.boundingRect(largest_contour)

    connector.send_init_request()  # Make sure scene is cleared

    mean_radius = scene.celestialBodies[0].model.meanRadius
    spacecraft_position = np.array(scene.spacecraft.position)
    asteroid_position = np.array(scene.celestialBodies[0].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)

    expected_angular_size_rad = 2 * np.arcsin(mean_radius / distance)

    image_width = 4000  # Given in default_scene
    image_height = 3000

    expected_asteroid_w_pixels = (expected_angular_size_rad / fov_x_deg) * image_width
    expected_asteroid_h_pixels = (expected_angular_size_rad / fov_y_deg) * image_height

    np.testing.assert_allclose(
        w,
        expected_asteroid_w_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid width in pixels does not match expected value for test: {test_name}",
    )

    np.testing.assert_allclose(
        h,
        expected_asteroid_h_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid height in pixels does not match expected value for test: {test_name}",
    )


def get_baseline_bounds(connector):
    scene = default_scene()

    connector.send_init_request()
    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w, h = cv2.boundingRect(largest_contour)

    return (w, h)


@pytest.mark.parametrize(
    "test_name, resolution_w, resolution_h",
    [
        ("Medium resolution", 2000, 1000),
        ("Low resolution", 700, 700),
    ],
)
def test_camera_resolution(cielim_connection, scene_setup, test_name, resolution_w, resolution_h):
    """
    Tests that the relative apparent image size is constant across different resolutions by comparing
    the side lengths of the bounding box surrounding the object in the scene to a baseline at 4k x 3k.
    """
    connector = cielim_connection

    scene = scene_setup
    del scene.camera.resolution[:]
    [scene.camera.resolution.append(val) for val in [resolution_w, resolution_h]]

    connector.send_init_request()
    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = max(contours, key=cv2.contourArea)
    _, _, w, h = cv2.boundingRect(largest_contour)

    w_ratio_to_res = w / resolution_w
    h_ratio_to_res = h / resolution_h

    image_width = 4000  # Given in default_scene
    image_height = 3000

    baseline_w, baseline_h = get_baseline_bounds(cielim_connection)
    w_ratio_to_res_baseline = baseline_w / image_width
    h_ratio_to_res_baseline = baseline_h / image_height

    connector.send_init_request()  # Make sure scene is cleared

    np.testing.assert_allclose(
        w_ratio_to_res,
        w_ratio_to_res_baseline,
        rtol=0.1,
        err_msg=f"Mismatch between horizontal apparent size with baseline: {test_name}",
    )

    np.testing.assert_allclose(
        h_ratio_to_res,
        h_ratio_to_res_baseline,
        rtol=0.1,
        err_msg=f"Mismatch between vertical apparent size with baseline: {test_name}",
    )
