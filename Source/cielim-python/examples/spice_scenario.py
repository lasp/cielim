from context import driver, launcher
from context import cielimMessage_pb2
from context import scene
from context import rigid_body_kinematics as rbk
import numpy as np
import spiceypy as spice
import urllib.request
import json
import os
import cv2

current_file_path = os.path.dirname(__file__)


def get_spice_data(filename):
    with open(filename, "r") as file:
        data = json.load(file)

    directory = filename.rsplit(".", 1)[0]
    absolute_path = os.path.dirname(directory)
    local_path = directory.split("/")[-1]
    meta_kernel = filename.rsplit("/")[-1].rsplit(".")[0]
    if not os.path.exists(directory):
        print("Retrieving spice data")
        os.makedirs(directory)
        with open(directory + "/" + meta_kernel + ".txt", "w") as file:
            file.write("\\begindata\nPATH_VALUES = ( '" + absolute_path + "' )\n")
            file.write("PATH_SYMBOLS = ( 'KERNELS' )\n")
            file.write("KERNELS_TO_LOAD=( \n\n")
            for key, value in data.items():
                urllib.request.urlretrieve(value, absolute_path + "/" + local_path + "/" + key)
                file.write("'$KERNELS/" + local_path + "/" + key + "', \n")
            file.write(") \n\n\\begintext \n")

    return directory + "/" + meta_kernel + ".txt"


def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "bennu_normalized"
    body.model.meanRadius = 58232 * 1e3

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    protobuf_message.camera.sensorModel.exposureTime = 1
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [5 * np.pi / 180, 3.75 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [2000, 1500]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def spice_scenario():
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    meta_data = get_spice_data(os.path.dirname(current_file_path) + "/support-data/cassini-spice.json")
    spice.furnsh(meta_data)
    instrument_id = "CASSINI_UVIS_FUV"
    # Define time range
    start_et = spice.str2et("2004-05-15T00:00:00")
    end_et = spice.str2et("2004-05-15T10:00:00")
    time_step = 300  # 5min
    et_range = np.arange(start_et, end_et, time_step)

    # prep file for saving
    directory_path = current_file_path + "/images-cassini-spice"
    os.makedirs(directory_path, exist_ok=True)

    connector = driver.Connector()
    launch = launcher.Launcher()
    connector.connect(launch.launch())
    connector.send_init_request()

    for time in et_range:
        position, light_time = spice.spkpos("CASSINI", time, "J2000", "NONE", "SATURN BARYCENTER")
        BN = spice.pxform("J2000", instrument_id, time)
        message = scene_frame.get_scene()
        message.spacecraft.ClearField("position")
        message.spacecraft.ClearField("attitude")
        [message.spacecraft.position.append(item) for item in position * 1e3]
        [message.spacecraft.attitude.append(item) for item in rbk.dcm_to_mrp(BN)]
        scene_frame.set_existing_message(message)
        connector.send_frame(scene_frame.get_scene())
        [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)
        cv2.imwrite(directory_path + "/cassini-" + str(time) + ".png", image)

    connector.disconnect()
    launch.terminate()


if __name__ == "__main__":
    spice_scenario()
