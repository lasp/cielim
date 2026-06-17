import cv2
import numpy as np
import pytest

import cielim


def default_scene():
    protobuf_message = cielim.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "sphere_normalized"
    body.model.meanRadius = 500
    [body.model.principalAxisDistortion.append(item) for item in [1, 1, 1]]

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [-2000000, 100000, -1000000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [15 * np.pi / 180, 10 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, -1]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1e5]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


@pytest.fixture
def scene_setup():
    return default_scene()


def get_baseline_cob(connector):
    scene = default_scene()

    del scene.celestialBodies[0].model.principalAxisDistortion[:]
    [scene.celestialBodies[0].model.principalAxisDistortion.append(val) for val in [1, 1, 1]]

    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)
    assert moments["m00"] != 0, "No brightness detected in baseline scene."

    cob_x = int(moments["m10"] / moments["m00"])
    cob_y = int(moments["m01"] / moments["m00"])
    return (cob_x, cob_y)


@pytest.mark.parametrize(
    "test_name, distortion",
    [
        ("Distort X", [1.5, 1, 1]),
        ("Distort Y", [1, 1.5, 1]),
    ],
)
def test_body_scaling(cielim_connection, scene_setup, test_name, distortion):
    """
    This remote procedure call test distorts the asteroid's principal axes and checks for appropriate movement of CoB.
    """
    connector = cielim_connection
    connector.send_init_request()

    scene = scene_setup
    del scene.celestialBodies[0].model.principalAxisDistortion[:]
    [scene.celestialBodies[0].model.principalAxisDistortion.append(val) for val in distortion]

    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)
    assert moments["m00"] != 0, f"No brightness detected in test: {test_name}"

    cob_x = int(moments["m10"] / moments["m00"])
    cob_y = int(moments["m01"] / moments["m00"])
    cob = (cob_x, cob_y)

    connector.send_init_request()
    sphere_cob = get_baseline_cob(cielim_connection)

    diff = np.array(cob) - np.array(sphere_cob)
    diff_total = np.linalg.norm(diff)
    diff_x = abs(diff[0])
    diff_y = abs(diff[1])

    if test_name == "Distort X":
        np.testing.assert_(diff_x >= 5, msg=f"{test_name}: X shift too small (= {diff_x:.2f}px).")
    elif test_name == "Distort Y":
        np.testing.assert_(diff_y <= 1, msg=f"{test_name}: Y shift too large (= {diff_y:.2f}px), expected is 0")
