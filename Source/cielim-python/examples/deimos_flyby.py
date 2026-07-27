"""
Author: Chun-Wei Kong, Owen Allison

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

# from context import qe_curve_fit

# ---- Paths (portable) ----
current_file_path = os.path.dirname(__file__)
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]  # <repo root>
MK = ROOT / "support-data" / "deimos-spice" / "deimos-spice.txt"
FITS_DIR = ROOT / "support-data" / "deimos-spice" / "fits_images"
OUT_DIR = HERE.parent / "images-deimos-spice"

# Output dir for the real-vs-generated batch comparison (raw/ and aligned/ subsets).
SHOWCASE_DIR = HERE.parent / "showcase_images" / "deimos"

# The observation time is encoded in each FITS filename, e.g. ...20231101T034225_... -> 03:42:25.
# Only the f635 filter is rendered, so the real frames are restricted to it (the other filters
# would otherwise contaminate the by-time pairing).
_FNAME_TIME = re.compile(r"(\d{8})T(\d{6})")
_RENDER_FILTER = "f635"


def _sorted_fits():
    return [
        p
        for p in sorted(FITS_DIR.iterdir())
        if p.is_file() and p.suffix.lower() == ".fits" and _RENDER_FILTER in p.name
    ]


def _filename_et(path):
    """SPICE ephemeris time parsed from the FITS filename timestamp (requires kernels loaded)."""
    m = _FNAME_TIME.search(path.name)
    if not m:
        return None
    d, t = m.groups()
    iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}"
    return spice.str2et(iso)


def _real_entries():
    """List of (ephemeris_time, fits_path) for the f635 real frames, keyed by filename timestamp."""
    entries = []
    for p in _sorted_fits():
        et = _filename_et(p)
        if et is not None:
            entries.append((et, p))
    return entries


def _exposure_of(path):
    return fits.open(str(path))[0].header.cards["XPOSURE"][1]


def _real_gray_of(path):
    data = np.nan_to_num(fits.open(str(path))[1].data)
    return image_comparison.to_uint8_gray(data)


def _stamp(et):
    """Filesystem-safe compact UTC stamp for a render time, e.g. 20231101T034225 (parsed by
    _filename_et, which the comparison uses for both real and generated filenames)."""
    return spice.et2utc(et, "ISOC", 0).replace("-", "").replace(":", "")


@contextlib.contextmanager
def cd(path: Path):
    prev = Path.cwd()
    os.chdir(str(path))
    try:
        return (yield)
    finally:
        os.chdir(str(prev))


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


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(name="hope_sat", position=(0, 0, -1000000), velocity=(0, 1000, 0))

    scene.set_camera_params(name="hope_sat")

    scene.set_lens_params(
        fov=(25.8 * np.pi / 180, 19.3 * np.pi / 180),
        focal_length=0.0506,
        aperture_radius=0.006024,  # focal length / f#
    )

    scene.set_sensor_params(
        resolution=(4096, 3072),
        exposure=1e-3,
        sensor_dims=(0.022528, 0.016896),  # 4096 * 5.5 mu meter, 3072 * 5.5 mu meter
        well_capacity=13500,  # dynamic range = 13500 electrons full well,
    )

    gain_e_per_dn = 12.333  # e-/DN
    dark_current_e_s = 1.0 * gain_e_per_dn  # e-/s
    scene.set_corruption_params(psf_sigma=1, dc_rate=dark_current_e_s)

    scene.set_celestial_body_params(0, position=(0, 0, -10000))

    index = scene.add_celestial_body("deimos")

    # NOTE: albedo is calculated by taking average albedo (~0.07) and dividing by the average pixel (~0.58) of the albedo map.
    # This is done so that average color of the shape model matches the real world average albedo.

    scene.set_celestial_body_params(
        index, albedo=0.12, mesh_shape="deimos_normalized", mesh_brdf="Regolith", mesh_radius=6.2 * 1e3
    )

    return scene


def spice_scenario():
    scene = scene_setup()

    qe_file_path = (
        Path(__file__).resolve().parent.parent.parent / "cielim-python/support-data/deimos-spice/qe-mod-5.csv"
    )

    solid_angle = np.pi * 0.005**2 / (0.16**2)  # steradians
    pixel_area = (0.022528 * 0.016896) / (4096 * 3072)  # m^2
    f635_window = [625, 645]

    qefit.set_qe_curve_fit(scene.get_scene(), str(qe_file_path), solid_angle, pixel_area, f635_window)

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

    # Real f635 frames keyed by observation time (from their filenames). The exposure for each
    # rendered frame comes from the matched real frame, so the two are directly comparable.
    real_entries = _real_entries()
    real_ets = [e[0] for e in real_entries]

    # Output dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    connector = cielim.Connector()
    launcher = cielim.Launcher()
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

        BN_object = spice.pxform("J2000", "IAU_DEIMOS", time)

        TB = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])  # manual correction to inertial frame
        BN_object = np.dot(TB, BN_object)

        print("get DCM of deimos, det(DCM): ", np.linalg.det(BN_object))

        scene.set_celestial_body_params(0, position=tuple(sun_pos * 1e3))
        scene.set_celestial_body_params(1, attitude=tuple(BN_object.flatten().tolist()))

        scene.set_spacecraft_params(position=tuple(position * 1e3), attitude=tuple(rbk.dcm_to_mrp(BN)))

        # Match this render time to the real f635 frame taken at the same time; use its exposure.
        match = image_comparison.nearest_time_index(time, real_ets, tol_s=2.0)
        if match is not None:
            scene.set_sensor_params(exposure=_exposure_of(real_entries[match][1]))
        print(f"exposure time: {scene.get_scene().camera.sensorModel.exposureTime:.4f} sec")

        connector.send_frame(scene.get_scene())

        print(f"Generating image for time {time_range_str[idx]}")

        [image, _, _] = connector.request_image_for_camera_id(1, True, False)
        image = np.flip(image, 0)  # vertical flip so the render matches the real EMM frame orientation
        # Save the generated frame named with its observation time so the comparison can read it
        # back and pair it with the real f635 image of the same time.
        cv2.imwrite(os.path.join(current_file_path, f"images-deimos-spice/deimos_{_stamp(time)}.png"), image)

    connector.disconnect()
    launcher.terminate()

    # Read the saved generated frames back and compare each to the real f635 image at the same time.
    # raw/ and aligned/ subsets, each with individual histograms + heatmaps and an average histogram.
    n = image_comparison.compare_saved(
        OUT_DIR, _filename_et, real_entries, _real_gray_of, str(SHOWCASE_DIR),
        title_real="real", title_generated="cielim",
    )
    print(f"Saved real-vs-generated batch comparison ({n} pairs) -> {SHOWCASE_DIR}")

    spice.kclear()


if __name__ == "__main__":
    spice_scenario()
