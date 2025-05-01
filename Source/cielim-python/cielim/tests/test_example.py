import context
from driver import *
from launcher import *
from context import cielimMessage_pb2
from context import scene
import numpy as np
import pytest


@pytest.fixture
def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in [0, 0, 0]]

    body.model.shapeModel = "bennu_normalized"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def test_example(cielim_connection, scene_setup):

    connector = cielim_connection
    connector.send_init_request()
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup)

    times = [0, 1, 2]
    for time in times:
        scene_frame.propagate_and_stare(time)
        connector.send_frame(scene_frame.get_scene())
        [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)
        height, width, _ = image.shape
        np.testing.assert_allclose([4000, 3000], [width, height], rtol=0, atol=0, err_msg="Returned image not correct")
