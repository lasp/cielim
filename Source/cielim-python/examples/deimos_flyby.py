"""
Author: Chun-Wei Kong

Goal:
    Generate images of deimos flyby according to the EMM Hope spacecraft.
    To run this script, one needs to have the spice files.
    By default, the spice files are located in support-data/deimos-spice/ folder.
    In this folder, deimos-spice.txt specify which spice files are used.
    With the "hack" of rotating the camera frame 180 degree,
    the generated images are similar to the .fits images of the EMM.
    However, it is expected to rotate the camera frame 90 degree only (in theory) to the image plane.
    Further investigations are required.
"""

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

# from context import qe_curve_fit

# ---- Paths (portable) ----
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]  # <repo root>
MK = ROOT / "support-data" / "deimos-spice" / "deimos-spice.txt"
FITS_DIR = ROOT / "support-data" / "deimos-spice" / "fits_images"
OUT_DIR = HERE.parent / "images-deimos-spice"


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


def _fits_to_png(filename: str, show_plots=False) -> None:
    data = fits.open(filename)[1].data
    if show_plots:
        print(filename)
        print("Exposure time " + str(fits.open(filename)[0].header.cards["XPOSURE"][1]) + " s")
        plt.imshow(data, cmap="gray")  # 'gray' colormap for grayscale
        plt.colorbar()  # Add a color bar to show value-color mapping
        plt.title("Image")
        plt.show()
    return fits.open(filename)[0].header.cards["XPOSURE"][1]


def _get_exposure_time():
    exposure_time_list = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fits"}:
            exposure_time_list.append(_fits_to_png(p))
    return exposure_time_list


def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "deimos"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in [0, 0, 0]]

    body.model.shapeModel = "bennu_normalized"  # we use bennu shape so far, need to replace it with deimos
    body.model.meanRadius = 6.2 * 1e3  # radius in meter of deimos

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "hope_sat"
    protobuf_message.camera.sensorModel.exposureTime = 1e-3

    # newly set parameters
    protobuf_message.camera.sensorModel.systemGain = 1
    protobuf_message.camera.sensorModel.gamma = 1
    protobuf_message.camera.sensorModel.sensorWidth = 0.022528  # 4096 * 5.5 mu meter
    protobuf_message.camera.sensorModel.sensorHeight = 0.016896  # 3072 * 5.5 mu meter
    protobuf_message.camera.sensorModel.fullWellCapacity = 13500  # dynamic range = 13500 electrons full well
    protobuf_message.camera.lensModel.focalLength = 50.6 / 1000.0
    protobuf_message.camera.lensModel.pointSpreadFunction = 1.0
    protobuf_message.camera.lensModel.apertureRadius = 0.006024  # focal length / f#

    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [25.8 * np.pi / 180, 19.3 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [4096, 3072]]

    protobuf_message.spacecraft.spacecraftName = "hope_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def spice_scenario():
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    # Load SPICE kernels using a meta-kernel with RELATIVE paths.
    # We temporarily chdir to the repo root so 'support-data/…' resolves correctly.
    spice.kclear()
    with cd(ROOT):
        spice.furnsh(str(MK))

    instrument_id = "HOPE_EXI_VIS"

    # Time range of the fits files
    time_range_str = [
        "2023-11-01T03:42:25",
        "2023-11-01T03:43:57",
        "2023-11-01T03:51:54",
        "2023-11-01T03:52:54",
        "2023-11-01T03:53:54",
        "2023-11-01T03:54:54",
        "2023-11-01T03:55:54",
        "2023-11-01T03:56:35",
        "2023-11-01T03:56:40",
        "2023-11-01T03:58:54",
        "2023-11-01T03:59:54",
        "2023-11-01T04:00:54",
        "2023-11-01T04:01:54",
        "2023-11-01T04:06:54",
    ]
    et_range = []
    for _str in time_range_str:
        et_range.append(spice.str2et(_str))
    et_range = np.array(et_range)

    # exposure time (sec) of the fits files
    exposure_time_list = _get_exposure_time()

    # Output dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()

    # camera frame to image plane transformation
    C_img_cam = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]], dtype=float)

    for idx, time in enumerate(et_range):
        # DEIMOS-centered states
        position, _ = spice.spkpos("-62", time, "J2000", "NONE", "DEIMOS")
        sun_pos, _ = spice.spkpos("SUN", time, "J2000", "NONE", "DEIMOS")

        BN = spice.pxform("J2000", instrument_id, time)  # instrument as body frame
        BN = C_img_cam @ C_img_cam @ BN
        # NOTE: we do the transformation "twice" in order to generate images close to the EMM mission
        # However, this should be done "once" in theory. Future work should investigate this.

        message = scene_frame.get_scene()
        message.spacecraft.ClearField("position")
        message.spacecraft.ClearField("attitude")
        [message.spacecraft.position.append(item) for item in position * 1e3]
        [message.spacecraft.attitude.append(item) for item in rbk.dcm_to_mrp(BN)]

        message.celestialBodies[1].ClearField("position")
        [message.celestialBodies[1].position.append(item) for item in sun_pos * 1e3]

        # update exposure time per image
        message.camera.sensorModel.exposureTime = exposure_time_list[idx]
        print(f"exposure time: {message.camera.sensorModel.exposureTime:.4f} sec")

        qe_file_path = Path(__file__).resolve().parent.parent.parent / "support-data/deimos-spice/qe-mod-5.csv"
        solid_angle = np.pi * 0.005**2 / (0.16**2)  # steradians
        pixel_area = (0.022528 * 0.016896) / (4096 * 3072)  # m^2
        f635_window = [625, 645]
        scene_frame.set_qe_curve_fit(str(qe_file_path), exposure_time_list[idx], solid_angle, pixel_area, f635_window)

        scene_frame.set_existing_message(message)
        connector.send_frame(scene_frame.get_scene())
        [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)
        cv2.imwrite(str(OUT_DIR / f"image-{time_range_str[idx]}.png"), image)

    connector.disconnect()
    launcher.terminate()
    spice.kclear()


if __name__ == "__main__":
    spice_scenario()
