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
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [-0.5 * 1.496e11, 0.5 * 1.496e11, -0.5 * 1.496e11]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, -1]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -100000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


@pytest.fixture
def scene_setup():
    return default_scene()


def sphere_baseline_cob(connector):

    scene = default_scene()
    scene.celestialBodies[0].model.shapeModel = "sphere_normalized"

    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)
    assert moments["m00"] != 0, "No brightness detected in baseline sphere image."

    cob_x = int(moments["m10"] / moments["m00"])
    cob_y = int(moments["m01"] / moments["m00"])

    return (cob_x, cob_y)


@pytest.mark.parametrize(
    "test_name, shape_model, shift",
    [
        ("bennu", "bennu_normalized", [0, 0, 0]),
        ("itokawa", "itokawa_normalized", [0, 0, 0]),
        ("67p", "67p_normalized", [0, 0, 0]),
    ],
)
def test_center_of_brightness_shift(cielim_connection, scene_setup, test_name, shape_model, shift):
    """
    This test loads different shape models and checks the movement.
    """

    connector = cielim_connection
    connector.send_init_request()

    scene = scene_setup
    scene.celestialBodies[0].model.shapeModel = shape_model

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

    sphere_cob = sphere_baseline_cob(connector)
    diff = np.linalg.norm(np.array(cob) - np.array(sphere_cob))

    np.testing.assert_(
        diff > 2, msg=f"{test_name}: CoB too close to sphere (= {diff:.2f}px) — shape model may be too similar."
    )
