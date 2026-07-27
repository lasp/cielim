import contextlib
import os
from pathlib import Path

import cv2
import numpy as np
import spiceypy as spice
from astropy.io import fits
from matplotlib import pyplot as plt

import cielim
from cielim.utils import qe_curve_fit as qefit
from cielim.utils import rigid_body_kinematics as rbk

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


def get_header(filename: str) -> tuple:
    with open(Path(filename).with_suffix(".txt"), "r") as file:
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
            _fits_to_png(str(p))
            exp, time, pos, sun_pos, mrp = get_header(str(p))
            exposure_time_list.append(exp * 1e-3)
            time_list.append(time)
            position_list.append(-pos)
            attitude_list.append(mrp)
            sun_list.append(sun_pos)
    return exposure_time_list, time_list, position_list, attitude_list, sun_list


vesta_gain_e_per_dn = 17.7
vesta_b_j = 1.018e-19  # activation-energy-like constant, J
vesta_t_ref_k = 219.0
vesta_ccd_temp_k = 220.0
boltzmann_j_per_k = 1.38065e-23
vesta_a_dn_s = 2.46e13

# PLACEHOLDER M(T_ref): the mission paper builds this from the median of real 300s dark
# exposures at T_ref, corrected to temperature -- that measured value isn't available here.
# Approximated via B(T_ref) itself; replace with the real measured value once available.
vesta_m_tref_dn_s = vesta_a_dn_s * np.exp(-vesta_b_j / (boltzmann_j_per_k * vesta_t_ref_k))


def dark_current_ratio(temp_k: float, t_ref_k: float) -> float:
    """B(T)/B(T_ref) from B(T) = a*exp(-b/(k_B*T)); the pre-exponential constant a cancels out."""
    return np.exp(-vesta_b_j / boltzmann_j_per_k * (1 / temp_k - 1 / t_ref_k))


def dark_current_rate_e_s(temp_k: float) -> float:
    """
    Vesta CCD dark current rate (e-/s): D(T_CCD) = [B(T_CCD)/B(T_ref)] * M(T_ref), converted
    from DN/s to e-/s via gain.
    """
    dn_rate = vesta_m_tref_dn_s * dark_current_ratio(temp_k, vesta_t_ref_k)
    return dn_rate * vesta_gain_e_per_dn


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(name="dawn", position=(0, 0, -1000000), velocity=(0, 1000, 0))

    scene.set_camera_params(name="dawn")

    # (https://link.springer.com/article/10.1007/s11214-011-9745-4)
    # (https://www.teledynespaceimaging.com/en-us/Products_/Documents/ccd-datasheets/CCD47-20%20FSI%20NIMO%20Datasheet%20(v9).pdf)

    scene.set_lens_params(
        fov=(5.5 * np.pi / 180, 5.5 * np.pi / 180),
        focal_length=0.150,
        aperture_radius=0.150 / 7.5 / 2,  # focal length / f# / 2
    )

    scene.set_sensor_params(
        resolution=(1024, 1024),
        exposure=1e-3,
        sensor_dims=(13.3 * 10 ** (-3), 13.3 * 10 ** (-3)),  # 2592 * 2.2 um, 1944 * 2.2 um
        well_capacity=120_000,
    )

    scene.set_corruption_params(psf_sigma=1, read_noise=18, dc_rate=dark_current_rate_e_s(vesta_ccd_temp_k))

    scene.set_celestial_body_params(0, position=(0, 0, -10000))

    index = scene.add_celestial_body("vesta")

    scene.set_celestial_body_params(
        index, albedo=0.423, mesh_shape="vesta_normalized", mesh_brdf="Regolith", mesh_radius=262.7 * 1e3
    )

    return scene


def vesta_scenario(number_of_images: int | None = None):
    scene = scene_setup()

    qe_file_path = (
        Path(__file__).resolve().parent.parent.parent / "cielim-python/support-data/vesta-spice/f2_qe_curve.csv"
    )

    solid_angle = np.pi
    pixel_area = 2.2 * 2.2 * 10 ** (-12)  # m^2

    qefit.set_qe_curve_fit(scene.get_scene(), str(qe_file_path), solid_angle, pixel_area)

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

    connector = cielim.Connector()
    launcher = cielim.Launcher()
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

        scene.set_celestial_body_params(0, position=tuple(sun_pos * 1e3))
        scene.set_celestial_body_params(1, attitude=tuple(BN_object.flatten().tolist()))

        print(f"Sun position: {sun_pos * 1e3}")

        scene.set_spacecraft_params(position=tuple(position * 1e3), attitude=tuple(rbk.dcm_to_mrp(BN)))

        print(f"Spacecraft position: {position * 1e3}")

        # update exposure time per image
        scene.set_sensor_params(exposure=exposure_time_list[idx])
        print(f"exposure time: {scene.get_scene().camera.sensorModel.exposureTime:.4f} sec")

        connector.send_frame(scene.get_scene())

        print(f"Generating image for time {time_list[idx]}")
        print(f"Phase angle {phase_angle}")

        image, _, _ = connector.request_image_for_camera_id(1, True, False)
        image = np.flip(image, 0)
        cv2.imwrite(os.path.join(current_file_path, f"images-vesta/vesta_image_{idx}.png"), image)

    connector.disconnect()
    launcher.terminate()
    spice.kclear()


if __name__ == "__main__":
    vesta_scenario()
