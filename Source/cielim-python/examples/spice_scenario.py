import json
import os
import urllib.request

import cv2
import numpy as np
import spiceypy as spice

import cielim
from cielim import rigid_body_kinematics as rbk

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


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, -1000000), velocity=(0, 1000, 0))

    scene.set_lens_params(
        fov=(5 * np.pi / 180, 3.75 * np.pi / 180),
        focal_length=150e-3,
        aperture_radius=150e-3 / 7.5 / 2,  # focal length / f# / 2
    )

    scene.set_sensor_params(resolution=(2000, 1500), exposure=1)

    scene.set_celestial_body_params(0, position=(0, 0, -10000))

    index = scene.add_celestial_body("2000269")

    scene.set_celestial_body_params(
        index, mesh_shape="bennu_normalized", mesh_brdf="Lambertian", mesh_radius=58232 * 1e3
    )

    return scene


def spice_scenario():
    scene = scene_setup()

    meta_data = get_spice_data(os.path.dirname(current_file_path) + "/support-data/cassini-spice.json")
    spice.furnsh(meta_data)
    instrument_id = "CASSINI_UVIS_FUV"
    # Define time range
    start_et = float(spice.str2et("2004-05-15T00:00:00"))
    end_et = float(spice.str2et("2004-05-15T10:00:00"))
    time_step = 300  # 5min
    et_range = np.arange(start_et, end_et, time_step)

    # prep file for saving
    directory_path = current_file_path + "/images-cassini-spice"
    os.makedirs(directory_path, exist_ok=True)

    connector = cielim.Connector()
    launch = cielim.Launcher()
    connector.connect(launch.launch())
    connector.send_init_request()

    for time in et_range:
        position, light_time = spice.spkpos("CASSINI", time, "J2000", "NONE", "SATURN BARYCENTER")
        BN = spice.pxform("J2000", instrument_id, time)

        scene.set_spacecraft_params(position=tuple(position * 1e3), attitude=tuple(rbk.dcm_to_mrp(BN)))

        connector.send_frame(scene.get_scene())
        [image, _, _] = connector.request_image_for_camera_id(1, True, False)
        cv2.imwrite(directory_path + "/cassini-" + str(time) + ".png", image)

    connector.disconnect()
    launch.terminate()


if __name__ == "__main__":
    spice_scenario()
