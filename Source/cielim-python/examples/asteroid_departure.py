from numpy import ndarray

import context
from driver import *
from launcher import *
from context import cielimMessage_pb2
from context import scene
from context import rigid_body_kinematics as rbk
import numpy as np
from orbital_motion import ClassicOrbitalElements
import os
import cv2

current_file_path = os.path.dirname(__file__)


def append_protobuf_to_file(filename, message):
    """Appends a serialized protobuf message to a file"""
    serialized_data = message.SerializeToString()

    with open(filename, "ab") as f:
        f.write(serialized_data)


def scene_setup() -> cielimMessage_pb2:
    """
    Setup basic scene: populate default values in protobuffer
    """
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "bennu_normalized"
    body.model.brdfModel = "Regolith"
    body.model.meanRadius = 58232 * 1e3

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -1e10]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    protobuf_message.camera.exposureTime = 1
    [protobuf_message.camera.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.resolution.append(item) for item in [2000, 1500]]
    protobuf_message.camera.focalLength = 0.025

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -4e8]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def departure_scene(number_of_images: int):
    """
    Generate a scenario in which the camera starts close to the asteroid and is progressively moved farther and farther
    This can test the rendering methods and accuracy at all distances
    """
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    # prep file for saving
    directory_path = current_file_path + "/images-departure"
    protobuff_file = directory_path + "/departure.bin"
    os.makedirs(directory_path, exist_ok=True)

    position_shift = np.array([0, 0, -1e9])

    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    message = scene_frame.get_scene()
    initial_position = np.array(message.spacecraft.position)

    for idx in range(number_of_images):

        message = scene_frame.get_scene()

        new_position = initial_position + position_shift * idx
        message.spacecraft.ClearField("position")
        [message.spacecraft.position.append(item) for item in new_position]
        scene_frame.set_existing_message(message)

        # Generate image
        image_name = "image-" + str(idx)
        connector.send_init_request()  # re-initialize shape model
        connector.send_frame(scene_frame.get_scene())
        [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)
        cv2.imwrite(directory_path + "/" + image_name + ".png", image)
        append_protobuf_to_file(protobuff_file, message)

    connector.disconnect()
    launcher.terminate()


if __name__ == "__main__":
    number_of_images = 600
    departure_scene(number_of_images)
