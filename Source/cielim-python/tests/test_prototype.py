import os
import sys

sys.path.insert(0, os.path.dirname(__file__) + "/../python-driver/")
import pytest
import cielimMessage_pb2
from driver import *
from proto_interface import ProtoInterface
import numpy as np


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
    sun.bodyName = "sun_planet_data"
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


def test_prototype(scene_setup):
    connector = Connector()
    connector.connect(connector.launch())

    proto_interface = ProtoInterface()
    proto_interface.set_existing_message(scene_setup)

    times = [0, 1, 2]
    for time in times:
        proto_interface.propagate_and_stare(time)
        connector.send_frame(proto_interface.return_message())
        [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)
        height, width, _ = image.shape
        np.testing.assert_allclose([4000, 3000], [width, height], rtol=0, atol=0, err_msg="Returned image not correct")

    connector.disconnect()
