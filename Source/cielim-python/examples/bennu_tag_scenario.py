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
MK = ROOT / "support-data" / "bennu-tag-spice" / "bennu-tag-spice.txt"
FITS_DIR = ROOT / "support-data" / "bennu-tag-spice" / "images"
OUT_DIR = HERE.parent / "images-bennu-tag"


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


def _fits_to_png(filename: str) -> None:
    image_data = fits.open(filename)[0]
    image_data = np.nan_to_num(image_data)
    plt.figure()
    plt.imshow(image_data.data, cmap="gray")
    plt.savefig(str(filename).split(".")[0] + ".png")  # save as png
    return fits.open(filename)[0].header.cards["EXPTIME"][1]


def _get_exposure_time():
    exposure_time_list = []
    time_list = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fits"}:
            exposure_time_list.append(_fits_to_png(p))
            year = str(p).split("/")[-1][0:4]
            month = str(p).split("/")[-1][4:6]
            day = str(p).split("/")[-1][6:8]
            hour = str(p).split("/")[-1][9:11]
            minutes = str(p).split("/")[-1][11:13]
            seconds = str(p).split("/")[-1][13:15] + "." + str(p).split("/")[-1][16:19]
            time_list.append(year + "-" + month + "-" + day + "T" + hour + ":" + minutes + ":" + seconds)
    return exposure_time_list, time_list


def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "bennu"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    if os.path.exists(str(ROOT) + "/../../Content/AsteroidMeshes/bennu_medfi_normalized.uasset"):
        body.model.shapeModel = "bennu_medfi_normalized"
        body.model.geometricAlbedo = 0.044 / 0.234745  # effective albedo of bennu
        # NOTE: this is calculated by taking average albedo (~0.044) and dividing by the average pixel (in linear RGB) 0.234745 of the albedo map
        # This is done so that average color of the shape model matches the real world average albedo
    else:
        body.model.shapeModel = "bennu_normalized"
        body.model.geometricAlbedo = 0.044  # effective albedo of bennu

    body.model.refModel.brdfModel = "Regolith"
    body.model.meanRadius = 246  # radius in meter of bennu

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "osiris_rex"
    protobuf_message.camera.sensorModel.exposureTime = 1e-3

    # newly set parameters
    protobuf_message.camera.sensorModel.systemGain = 1
    protobuf_message.camera.sensorModel.readNoise = 6.7
    protobuf_message.camera.sensorModel.sensorWidth = 2592 * 2.2 * 10 ** (-6)
    protobuf_message.camera.sensorModel.sensorHeight = 1944 * 2.2 * 10 ** (-6)
    protobuf_message.camera.sensorModel.fullWellCapacity = 7000
    protobuf_message.camera.lensModel.focalLength = 7.6 / 1000
    protobuf_message.camera.lensModel.pointSpreadFunction = 1.0
    protobuf_message.camera.lensModel.apertureRadius = (
        protobuf_message.camera.lensModel.focalLength / 3.5 / 2
    )  # focal length / f# / 2

    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [44 * np.pi / 180, 32 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [2592, 1944]]

    protobuf_message.spacecraft.spacecraftName = "osiris_rex"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def tag_scenario(number_of_images: int = None):
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    message = scene_frame.get_scene()
    qe_file_path = (
        Path(__file__).resolve().parent.parent.parent / "cielim-python/support-data/bennu-tag-spice/navcam_qe_curve.csv"
    )
    solid_angle = np.pi
    pixel_area = 2.2 * 2.2 * 10 ** (-12)  # m^2
    scene_frame.set_qe_curve_fit(str(qe_file_path), solid_angle, pixel_area)
    scene_frame.set_existing_message(message)
    instrument_id = "ORX_NAVCAM2"

    # Load SPICE kernels using a meta-kernel with RELATIVE paths.
    # We temporarily chdir to the repo root so 'support-data/…' resolves correctly.
    spice.kclear()
    with cd(ROOT):
        spice.furnsh(str(MK))

    if os.path.exists(FITS_DIR):
        exposure_time_list, time_list = _get_exposure_time()
    else:
        time_list = [
            "2020-10-20T18:58:51.722",
            "2020-10-20T19:03:51.304",
            "2020-10-20T19:08:52.835",
            "2020-10-20T19:13:51.218",
            "2020-10-20T19:18:52.886",
            "2020-10-20T19:23:51.234",
            "2020-10-20T19:28:52.555",
            "2020-10-20T19:33:51.590",
            "2020-10-20T19:38:52.797",
            "2020-10-20T19:43:51.270",
            "2020-10-20T19:48:52.524",
            "2020-10-20T19:53:51.407",
            "2020-10-20T19:58:52.962",
            "2020-10-20T20:03:51.610",
            "2020-10-20T20:06:12.946",
            "2020-10-20T20:11:12.810",
            "2020-10-20T20:16:14.193",
            "2020-10-20T20:21:13.072",
            "2020-10-20T20:26:14.380",
            "2020-10-20T20:31:13.158",
            "2020-10-20T20:36:14.373",
            "2020-10-20T20:41:12.873",
            "2020-10-20T20:46:14.131",
            "2020-10-20T20:51:12.920",
            "2020-10-20T20:56:14.201",
            "2020-10-20T21:01:12.799",
            "2020-10-20T21:06:14.737",
            "2020-10-20T21:11:14.428",
            "2020-10-20T21:18:04.339",
            "2020-10-20T21:20:23.331",
            "2020-10-20T21:22:43.296",
            "2020-10-20T21:25:02.960",
            "2020-10-20T21:29:33.144",
            "2020-10-20T21:30:32.878",
            "2020-10-20T21:31:33.210",
            "2020-10-20T21:32:33.113",
            "2020-10-20T21:33:32.956",
            "2020-10-20T21:34:59.765",
            "2020-10-20T21:35:59.609",
            "2020-10-20T21:36:59.878",
            "2020-10-20T21:38:26.261",
            "2020-10-20T21:39:40.867",
            "2020-10-20T21:40:40.773",
            "2020-10-20T21:41:41.168",
            "2020-10-20T21:42:41.004",
            "2020-10-20T21:43:40.929",
            "2020-10-20T21:44:40.816",
            "2020-10-20T21:45:40.676",
            "2020-10-20T21:46:41.117",
            "2020-10-20T21:47:40.922",
            "2020-10-20T21:48:40.812",
            "2020-10-20T21:49:05.683",
            "2020-10-20T21:49:06.680",
            "2020-10-20T21:49:07.680",
        ]
        exposure_time_list = [
            0.0065924,
            0.0065924,
            0.0062432,
            0.0062432,
            0.005894,
            0.0055448,
            0.0055448,
            0.0051956,
            0.0048464,
            0.0048464,
            0.0044972,
            0.004148,
            0.0037988,
            0.0037988,
            0.0034496,
            0.0034496,
            0.0031004,
            0.0027512,
            0.002402,
            0.0020528,
            0.0020528,
            0.0017036,
            0.0013544,
            0.0013544,
            0.0017036,
            0.0020528,
            0.002402,
            0.0027512,
            0.0037988,
            0.0037988,
            0.004148,
            0.0044972,
            0.0051956,
            0.0051956,
            0.0051956,
            0.0051956,
            0.0051956,
            0.0055448,
            0.0055448,
            0.0055448,
            0.0055448,
            0.005894,
            0.005894,
            0.005894,
            0.005894,
            0.005894,
            0.005894,
            0.005894,
            0.005894,
            0.005894,
            0.005894,
            0.0062432,
            0.0062432,
            0.0062432,
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

    # camera frame to image plane transformation
    C_img_cam = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=float)

    for idx, time in enumerate(et_range):
        # Bennu-centered states
        position, _ = spice.spkpos("-64082", time, "J2000", "NONE", "2101955")
        sun_pos, _ = spice.spkpos("SUN", time, "J2000", "NONE", "2101955")
        BN = spice.pxform("J2000", instrument_id, time)  # instrument as body frame
        BN = C_img_cam @ BN

        message = scene_frame.get_scene()

        BN_object = spice.pxform("J2000", "IAU_BENNU", time)
        TB = rbk.euler321_to_dcm([np.pi / 2, 0, 0])  # manual correction to inertial frame
        BN_object = np.dot(TB, BN_object)

        message.celestialBodies[0].ClearField("attitude")
        [message.celestialBodies[0].attitude.append(item) for item in BN_object.flatten().tolist()]

        message.spacecraft.ClearField("position")
        message.spacecraft.ClearField("attitude")
        [message.spacecraft.position.append(item) for item in position * 1e3]
        [message.spacecraft.attitude.append(item) for item in rbk.dcm_to_mrp(BN)]

        message.celestialBodies[1].ClearField("position")
        [message.celestialBodies[1].position.append(item) for item in sun_pos * 1e3]

        # update exposure time per image
        message.camera.sensorModel.exposureTime = exposure_time_list[idx]
        print(f"exposure time: {message.camera.sensorModel.exposureTime:.4f} sec")

        scene_frame.set_existing_message(message)
        connector.send_frame(scene_frame.get_scene())

        print(f"Generating image for time {time_list[idx]}")

        image, _, _ = connector.request_image_for_camera_id(1, 1)
        cv2.imwrite(os.path.join(current_file_path, f"images-bennu-tag/bennu_image_{idx}.png"), np.flip(image, 1))

    connector.disconnect()
    launcher.terminate()
    spice.kclear()


if __name__ == "__main__":
    tag_scenario()
