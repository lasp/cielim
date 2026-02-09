import os, contextlib
from pathlib import Path
import numpy as np
import spiceypy as spice
import cv2
import context
from driver import *
from launcher import *
from context import cielimMessage_pb2
from context import scene
from context import rigid_body_kinematics as rbk

# ---- Paths (portable) ----
current_file_path = os.path.dirname(__file__)
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]  # <repo root>
MK = ROOT / "support-data" / "vesta-spice" / "vesta-spice.txt"
FITS_DIR = ROOT / "support-data" / "vesta-spice" / "images"
OUT_DIR = HERE.parent / "images-vesta"


@contextlib.contextmanager
def cd(path: Path):
    prev = Path.cwd()
    os.chdir(str(path))
    try:
        return (yield)
    finally:
        os.chdir(str(prev))


import astropy
from astropy.io import fits
import matplotlib.pyplot as plt


def get_header(filename: str) -> dict:
    with open(filename.with_suffix(".txt"), "r") as file:
        content = file.read()
        quat_start_idx = content.find("QUATERNION")
        sun_start_idx = content.find("SC_SUN_POSITION_VECTOR")
        pos_start_idx = content.find("SC_TARGET_POSITION_VECTOR")
        exp_start_idx = content.find("EXPOSURE_DURATION")
        time_start_idx = content.find("START_TIME")

        quat_str = content[quat_start_idx : quat_start_idx + 109].split("=")[1][3:-3].split(",")
        quat = np.array(
            [float(quat_str[0][:-1]), float(quat_str[1][:-1]), float(quat_str[2][:-1]), float(quat_str[3][:-1])]
        )
        mrp = -rbk.quaternion_to_mrp(quat)
        sun_str = content[sun_start_idx : sun_start_idx + 128].split("=")[1][3:-3].split(",")
        sun_pos = np.array(
            [float(sun_str[0].split("<")[0]), float(sun_str[1].split("<")[0]), float(sun_str[2].split("<")[0])]
        )

        pos_str = content[pos_start_idx : pos_start_idx + 123].split("=")[1][3:-3].split(",")
        pos = np.array(
            [float(pos_str[0].split("<")[0]), float(pos_str[1].split("<")[0]), float(pos_str[2].split("<")[0])]
        )

        exp = float(content[exp_start_idx : exp_start_idx + 60].split("=")[1].split("<")[0])
        time = content[time_start_idx : time_start_idx + 60].split("=")[1][:22]

    return exp, time, pos, sun_pos, mrp


def _fits_to_png(filename: str) -> None:
    image_data = fits.open(filename)[0]
    image_data = np.nan_to_num(image_data)
    plt.figure()
    plt.xticks([])
    plt.yticks([])
    plt.tight_layout(pad=0)  # Remove padding around the image
    plt.imshow(image_data.data, cmap="gray")
    plt.imsave(str(filename).split(".")[0] + ".png", image_data.data, cmap="gray")


def get_header_data():
    exposure_time_list = []
    time_list = []
    position_list = []
    attitude_list = []
    sun_list = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fit"}:
            _fits_to_png(p)
            exp, time, pos, sun_pos, mrp = get_header(p)
            exposure_time_list.append(exp * 1e-3)
            time_list.append(time)
            position_list.append(-pos)
            attitude_list.append(mrp)
            sun_list.append(sun_pos)
    return exposure_time_list, time_list, position_list, attitude_list, sun_list


def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "vesta"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "vesta_normalized"
    body.model.geometricAlbedo = 0.423  # effective albedo of vesta
    body.model.refModel.brdfModel = "Regolith"  # vesta has better results with Lambertian
    body.model.meanRadius = 262.7 * 1e3  # radius in meter of vesta

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "dawn"
    protobuf_message.camera.sensorModel.exposureTime = 1e-3

    # newly set parameters
    protobuf_message.camera.sensorModel.systemGain = 1
    protobuf_message.camera.sensorModel.readNoise = 18
    protobuf_message.camera.sensorModel.sensorWidth = 13.3 * 10 ** (-3)  # 2592 * 2.2 um
    protobuf_message.camera.sensorModel.sensorHeight = 13.3 * 10 ** (-3)  # 1944 * 2.2 um
    protobuf_message.camera.sensorModel.fullWellCapacity = 60000
    protobuf_message.camera.lensModel.focalLength = 150 / 1000
    protobuf_message.camera.lensModel.pointSpreadFunction = 1.0
    protobuf_message.camera.lensModel.apertureRadius = (
        protobuf_message.camera.lensModel.focalLength / 7.5 / 2
    )  # focal length / f# / 2

    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [5.5 * np.pi / 180, 5.5 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [1024, 1024]]

    protobuf_message.spacecraft.spacecraftName = "dawn"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def vesta_scenario(number_of_images: int = None):
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    message = scene_frame.get_scene()
    qe_file_path = (
        Path(__file__).resolve().parent.parent.parent / "cielim-python/support-data/vesta-spice/f2_qe_curve.csv"
    )
    solid_angle = np.pi
    pixel_area = 2.2 * 2.2 * 10 ** (-12)  # m^2
    scene_frame.set_qe_curve_fit(str(qe_file_path), solid_angle, pixel_area)
    scene_frame.set_existing_message(message)

    # Load SPICE kernels using a meta-kernel with RELATIVE paths.
    # We temporarily chdir to the repo root so 'support-data/…' resolves correctly.
    spice.kclear()
    with cd(ROOT):
        spice.furnsh(str(MK))

    if os.path.exists(FITS_DIR):
        exposure_time_list, time_list, position_list, attitude_list, sun_list = get_header_data()
    else:
        time_list = [
            "2018-10-13T09:23:10.088",
            "2018-10-14T09:23:18.953",
            "2018-10-15T09:23:04.822",
            "2018-11-08T06:09:26.456",
            "2018-11-08T07:56:56.453",
            "2018-11-09T07:56:56.852",
            "2018-11-11T10:22:17.655",
            "2018-11-12T04:28:23.821",
        ]
        exposure_time_list = [
            4.000285275,
            4.000285275,
            4.000285275,
            0.003224675,
            0.003224675,
            0.003224675,
            0.002554475,
            0.002554475,
        ]

    if number_of_images is not None:
        if number_of_images > len(exposure_time_list):
            number_of_images = len(exposure_time_list)
        time_list = time_list[:number_of_images]
        exposure_time_list = exposure_time_list[:number_of_images]

    et_range = []
    for _str in time_list:
        et_range.append(spice.str2et(_str))
    et_range = np.array(et_range)

    # Output dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()

    for idx, time in enumerate(et_range):
        position, _ = spice.spkpos("DAWN", time, "J2000", "NONE", "2000004")
        sun_pos, _ = spice.spkpos("SUN", time, "J2000", "NONE", "2000004")
        phase_angle = (
            np.arccos(np.dot(position / np.linalg.norm(position), sun_pos / np.linalg.norm(sun_pos))) * 180 / np.pi
        )
        BN = spice.pxform("J2000", "DAWN_SPACECRAFT", time)
        CB = spice.pxform("DAWN_SPACECRAFT", "DAWN_FC2", time)
        BN = np.dot(CB, BN)
        BN_object = spice.pxform("J2000", "IAU_VESTA", time)

        message = scene_frame.get_scene()
        message.celestialBodies[0].ClearField("attitude")
        [message.celestialBodies[0].attitude.append(item) for item in BN_object.flatten().tolist()]

        message.spacecraft.ClearField("position")
        message.spacecraft.ClearField("attitude")
        [message.spacecraft.position.append(item) for item in position * 1e3]
        [message.spacecraft.attitude.append(item) for item in rbk.dcm_to_mrp(BN)]

        print(f"Spacecraft position: {position * 1e3}")

        message.celestialBodies[1].ClearField("position")
        [message.celestialBodies[1].position.append(item) for item in sun_pos * 1e3]

        print(f"Sun position: {sun_pos * 1e3}")

        # update exposure time per image
        message.camera.sensorModel.exposureTime = exposure_time_list[idx]
        print(f"exposure time: {message.camera.sensorModel.exposureTime:.4f} sec")

        scene_frame.set_existing_message(message)
        connector.send_frame(scene_frame.get_scene())

        print(f"Generating image for time {time_list[idx]}")
        print(f"Phase angle {phase_angle}")

        image, _, _ = connector.request_image_for_camera_id(1, 1)
        image = np.flip(image, 0)
        cv2.imwrite(os.path.join(current_file_path, f"images-vesta/vesta_image_{idx}.png"), image)

    connector.disconnect()
    launcher.terminate()
    spice.kclear()


if __name__ == "__main__":
    vesta_scenario()
