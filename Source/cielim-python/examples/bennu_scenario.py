import contextlib
import os
import re
from pathlib import Path

import cv2
import numpy as np
import spiceypy as spice
from astropy.io import fits
from matplotlib import pyplot as plt

import cielim
from cielim.utils import image_comparison_toolkit as image_comparison
from cielim.utils import qe_curve_fit as qefit
from cielim.utils import rigid_body_kinematics as rbk

# ---- Paths (portable) ----
current_file_path = os.path.dirname(__file__)
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]  # <repo root>
MK = ROOT / "support-data" / "bennu-spice" / "bennu-spice.txt"
FITS_DIR = ROOT / "support-data" / "bennu-spice" / "images"
OUT_DIR = HERE.parent / "images-bennu"

# Output dir for the real-vs-generated batch comparison (raw/ and aligned/ subsets).
SHOWCASE_DIR = HERE.parent / "showcase_images" / "bennu"

# The observation time is encoded in each FITS filename, e.g. 20181013T092310S088 -> 09:23:10.088.
_FNAME_TIME = re.compile(r"(\d{8})T(\d{6})S(\d{3})")


def _sorted_fits():
    return [p for p in sorted(FITS_DIR.iterdir()) if p.is_file() and p.suffix.lower() == ".fits"]


def _filename_et(path):
    """SPICE ephemeris time parsed from the FITS filename timestamp (requires kernels loaded)."""
    m = _FNAME_TIME.search(path.name)
    if not m:
        return None
    d, t, ms = m.groups()
    iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}.{ms}"
    return spice.str2et(iso)


def _real_entries():
    """List of (ephemeris_time, fits_path) for the real frames, keyed by their filename timestamp."""
    entries = []
    for p in _sorted_fits():
        et = _filename_et(p)
        if et is not None:
            entries.append((et, p))
    return entries


def _real_gray_of(path):
    """Grayscale uint8 of a real Bennu FITS frame (data in HDU[0])."""
    data = np.nan_to_num(fits.open(str(path))[0].data)
    return image_comparison.to_uint8_gray(data)


def _stamp(et):
    """Filesystem-safe compact UTC stamp for a render time, e.g. 20181013T092310."""
    return spice.et2utc(et, "ISOC", 0).replace("-", "").replace(":", "")


def _gen_time(path):
    """Ephemeris time parsed from a saved generated filename's compact stamp (..._YYYYMMDDThhmmss)."""
    m = re.search(r"(\d{8})T(\d{6})", path.name)
    if not m:
        return None
    d, t = m.groups()
    return spice.str2et(f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}")


@contextlib.contextmanager
def cd(path: Path):
    prev = Path.cwd()
    os.chdir(str(path))
    try:
        return (yield)
    finally:
        os.chdir(str(prev))


def _fits_to_png(filename: str) -> None:
    image_data = fits.open(filename)[0]
    image_data = np.nan_to_num(image_data)
    plt.figure()
    plt.imshow(image_data.data, cmap="gray")
    plt.savefig(str(filename).split(".")[0] + ".png")  # save as png
    return fits.open(filename)[0].header.cards["EXPOSEC"][1]


def _fits_time(filename: str):
    return fits.open(filename)[0].header.cards["MIDOBS"][1]


def _fits_sun_vec():
    sun_vec_list = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fits"}:
            sun_x = fits.open(p)[0].header.cards["SUNSCUVX"][1]
            sun_y = fits.open(p)[0].header.cards["SUNSCUVY"][1]
            sun_z = fits.open(p)[0].header.cards["SUNSCUVZ"][1]
            sun_range = fits.open(p)[0].header.cards["SUNSCRNG"][1]
            sun_vec_list.append(sun_range * np.array([sun_x, sun_y, sun_z]))
    return sun_vec_list


def _get_instrument_attitudes():
    attitudes = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fits"}:
            q0 = fits.open(p)[0].header.cards["INST_QA"][1]
            q1 = fits.open(p)[0].header.cards["INST_QX"][1]
            q2 = fits.open(p)[0].header.cards["INST_QY"][1]
            q3 = fits.open(p)[0].header.cards["INST_QZ"][1]
            attitudes.append(rbk.quaternion_to_dcm([q0, q1, q2, q3]))
    return attitudes


def _get_bennu_centers():
    bennu_xy_list = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fits"}:
            bennu_x = fits.open(p)[0].header.cards["CRPIX1"][1] + fits.open(p)[0].header.cards["BENNUNX1"][1]
            bennu_y = fits.open(p)[0].header.cards["CRPIX2"][1] + fits.open(p)[0].header.cards["BENNUNX2"][1]
            bennu_xy_list.append([bennu_x, bennu_y])
    return bennu_xy_list


def _get_exposure_time():
    exposure_time_list = []
    time_list = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fits"}:
            exposure_time_list.append(_fits_to_png(str(p)))
            time_list.append(_fits_time(str(p)))
    return exposure_time_list, time_list


def dark_signal_rate_dn_s(temp_c: float) -> float:
    """
    PolyCam CCD dark signal generation rate (DN/s) as a function of CCD temperature (deg C).
    Fit: R_dark = a*exp(b*T) + c*exp(d*T). Valid over the documented CCD range (-25 to 13 degC).
    """
    a, b, c, d = 2.47, 0.0148, 0.295, 0.101
    return a * np.exp(b * temp_c) + c * np.exp(d * temp_c)


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(name="osiris_rex", position=(0, 0, -1000000), velocity=(0, 1000, 0))

    scene.set_camera_params(name="PolyCam")

    # Camera params from here: (https://link.springer.com/article/10.1007/s11214-011-9745-4)

    scene.set_lens_params(fov=(0.0138, 0.0138), focal_length=610 / 1000, aperture_radius=0.175 / 2)

    scene.set_sensor_params(
        resolution=(1024, 1024),
        exposure=1e-3,
        sensor_dims=(6.5 * 1024 * 10 ** (-6), 8.5 * 1024 * 10 ** (-6)),  # 8.5 um pixel pitch
        well_capacity=int(14500 / 4.5),  # Using sensor linearity
    )

    ccd_temp_c = -10.0
    dark_current_e_s = dark_signal_rate_dn_s(ccd_temp_c) / 4.5  # DN/s -> e-/s, same 4.5 DN/e- gain as well_capacity

    scene.set_corruption_params(read_noise=3, dc_rate=dark_current_e_s)

    scene.set_celestial_body_params(0, position=(0, 0, -10000))  # Sets the position of the sun

    index = scene.add_celestial_body("bennu")
    scene.set_celestial_body_params(
        index, albedo=0.044, mesh_shape="bennu_normalized", mesh_brdf="Regolith", mesh_radius=246
    )

    return scene


def bennu_scenario(number_of_images: int | None = None):
    scene = scene_setup()

    qe_file_path = (
        Path(__file__).resolve().parent.parent.parent / "cielim-python/support-data/bennu-spice/ocam_qe_curve.csv"
    )

    solid_angle = np.pi
    pixel_area = 2.2 * 2.2 * 10 ** (-12)  # m^2

    qefit.set_qe_curve_fit(scene.get_scene(), str(qe_file_path), solid_angle, pixel_area)

    instrument_id = "-64360"

    # Load SPICE kernels using a meta-kernel with RELATIVE paths.
    # We temporarily chdir to the repo root so 'support-data/…' resolves correctly.
    spice.kclear()
    with cd(ROOT):
        spice.furnsh(str(MK))

    if os.path.exists(FITS_DIR):
        exposure_time_list, time_list = _get_exposure_time()
        bennu_pixel_center = _get_bennu_centers()
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
        bennu_pixel_center = [
            [507.13748977968123, 505.05846626368765],
            [516.6736671503357, 474.6122219513481],
            [580.6872789385088, 306.354102901876],
            [462.61883895157223, 500.8249160231412],
            [462.1288443838623, 501.2590208836935],
            [471.3981807802967, 503.55086533318956],
            [434.4903610978049, 545.4937059694048],
            [514.9087687287606, 511.2892659899703],
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

    # camera frame to image plane transformation
    C_img_cam = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)

    for idx, time in enumerate(et_range):
        position, _ = spice.spkpos("ORX_SPACECRAFT", time, "J2000", "NONE", "2101955")
        sun_pos, _ = spice.spkpos("SUN", time, "J2000", "NONE", "2101955")
        phase_angle = (
            np.arccos(np.dot(position / np.linalg.norm(position), sun_pos / np.linalg.norm(sun_pos))) * 180 / np.pi
        )
        BN = spice.pxform("J2000", "ORX_SPACECRAFT", time)
        CB = np.array(
            [
                [0.999992877299969, 0.00376869788833074, 0.000205585885614917],
                [-0.003768435874442, 0.999992105221604, -0.00126031167762166],
                [-0.000210333996518, 0.001259527963573, 0.999999184674127],
            ]
        )  # instrument in body frame

        # sun_pos = np.dot(np.dot(CB, BN).T, sun_vec_list[idx])
        BN = C_img_cam @ np.dot(CB, BN)
        BN_object = spice.pxform("J2000", "IAU_BENNU", time)

        scene.set_celestial_body_params(0, position=tuple(sun_pos * 1e3))  # Move sun
        scene.set_celestial_body_params(1, attitude=tuple(BN_object.flatten().tolist()))  # Rotate bennu

        scene.set_spacecraft_params(position=tuple(position * 1e3), attitude=tuple(rbk.dcm_to_mrp(BN)))

        # update exposure time per image
        scene.set_sensor_params(exposure=exposure_time_list[idx])
        print(f"exposure time: {scene.get_scene().camera.sensorModel.exposureTime:.4f} sec")

        connector.send_frame(scene.get_scene())

        print(f"Generating image for time {time_list[idx]}")
        print(f"Phase angle {phase_angle}")

        image, _, _ = connector.request_image_for_camera_id(1, True, False)
        image = np.flip(image, 1)
        # Save the generated frame named with its observation time so the comparison can read it
        # back and pair it with the real image of the same time (using the exact saved orientation).
        cv2.imwrite(os.path.join(current_file_path, f"images-bennu/bennu_{_stamp(time)}.png"), image)

        captured_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        moments = cv2.moments(captured_image)
        if moments["m00"] != 0:
            cob_x = np.ceil(moments["m10"] / moments["m00"])
            cob_y = np.ceil(moments["m01"] / moments["m00"])
            truth = bennu_pixel_center[idx]
            print("px x diff", cob_x - truth[0])
            print("px y diff", cob_y - truth[1])

    connector.disconnect()
    launcher.terminate()

    # Read the saved generated frames back and compare each to the real image at the same time.
    # raw/ and aligned/ subsets, each with individual histograms + heatmaps and an average histogram.
    n = image_comparison.compare_saved(
        OUT_DIR, _gen_time, _real_entries(), _real_gray_of, str(SHOWCASE_DIR),
        title_real="real", title_generated="cielim",
    )
    print(f"Saved real-vs-generated batch comparison ({n} pairs) -> {SHOWCASE_DIR}")

    spice.kclear()


if __name__ == "__main__":
    bennu_scenario()
