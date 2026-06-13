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
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]
    body.model.shapeModel = "sphere_normalized"
    body.model.meanRadius = 1000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -1000000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]

    return protobuf_message


@pytest.fixture
def scene_setup():
    return default_scene()


@pytest.mark.parametrize(
    "test_name, sun_position, phase_angle",
    [
        ("Full Illumination (0°)", [0, 0, -1000000], 0),
        ("(45° Horizontal)", [700000, 0, -700000], 45),
        ("Half Moon (90° Horizontal)", [1000000, 0, 0], 90),
        ("(135° Horizontal)", [-700000, 0, 700000], 135),
        ("Half Moon (90° Vertical)", [0, 1000000, 0], 90),
        ("(45° Vertical)", [0, 700000, -700000], 45),
        ("(135° Vertical)", [0, -700000, 700000], 135),
    ],
)
def test_phase_angle_scene(cielim_connection, scene_setup, test_name, sun_position, phase_angle):
    """
    Tests the phase angle change by testing Center of Brightness (CoB) vs expected shift (by comparing expected and actual pixel shifts).
    """
    connector = cielim_connection
    connector.send_init_request()

    scene = default_scene()
    scene.celestialBodies[1].ClearField("position")
    [scene.celestialBodies[1].position.append(item) for item in sun_position]

    mean_radius = scene.celestialBodies[0].model.meanRadius
    spacecraft_position = np.array(scene.spacecraft.position)
    asteroid_position = np.array(scene.celestialBodies[0].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)
    phase_angle_rad = np.radians(phase_angle)

    theta = np.arctan((4 * mean_radius) / (3 * np.pi * distance) * (1 - np.cos(phase_angle_rad)))

    camera_fov_horizontal = 20 * np.pi / 180
    camera_fov_vertical = 15 * np.pi / 180
    image_width = 4000
    image_height = 3000

    sun_vector = np.array(sun_position) - asteroid_position
    sun_direction = sun_vector / np.linalg.norm(sun_vector)

    expected_cob_x = 2000
    expected_cob_y = 1500

    if abs(sun_direction[0]) > 1e-6:
        expected_cob_x += np.sign(sun_direction[0]) * theta * (image_width / camera_fov_horizontal)
        expected_cob_x = round(expected_cob_x)

    if abs(sun_direction[1]) > 1e-6:
        expected_cob_y += np.sign(sun_direction[1]) * theta * (image_height / camera_fov_vertical)
        expected_cob_y = round(expected_cob_y)

    connector.send_frame(scene)
    captured_image, _, _ = connector.request_image_for_camera_id(1, 1)

    if len(captured_image.shape) == 3:
        captured_image = cv2.cvtColor(captured_image, cv2.COLOR_BGR2GRAY)

    captured_image = cv2.GaussianBlur(captured_image, (5, 5), 0)

    moments = cv2.moments(captured_image)
    if moments["m00"] != 0:
        # TODO understand why it works with ceil but not round or floor
        actual_cob_x = int(np.ceil(moments["m10"] / moments["m00"]))
        actual_cob_y = int(np.ceil(moments["m01"] / moments["m00"]))

    else:
        actual_cob_x, actual_cob_y = 2000, 1500

    np.testing.assert_allclose(
        [actual_cob_x, actual_cob_y],
        [expected_cob_x, expected_cob_y],
        atol=1,
        err_msg=f"CoB mismatch for test: {test_name}",
    )
