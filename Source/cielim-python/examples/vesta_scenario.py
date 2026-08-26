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
MK = ROOT / "support-data" / "vesta-spice" / "vesta-spice.txt"
FITS_DIR = ROOT / "support-data" / "vesta-spice" / "images"
OUT_DIR = HERE.parent / "images-vesta"

# Output dir for the real-vs-generated batch comparison (raw/ and aligned/ subsets).
SHOWCASE_DIR = HERE.parent / "showcase_images" / "vesta"

# The comparison is split into two groups plus a dropped pair. Keys are the observation-time stamp of
# each frame (as in the saved render filename); the indices quoted below are the positions the frames
# had in the earlier single 00-19 comparison.
#
# 00-11: the distant approach frames (2011-05-03 .. 2011-07-04, ~8-9 ms). Vesta covers only a small
# part of the frame here, so their statistics don't belong in the same batch as the close-in frames —
# they get their own comparison group in DISTANT_DIR.
DISTANT_DIR = HERE.parent / "showcase_images" / "vesta_distant"
DISTANT_STAMPS = frozenset(
    {
        "20110503T133601",
        "20110510T070317",
        "20110517T125701",
        "20110524T085201",
        "20110601T063701",
        "20110608T152416",
        "20110614T133816",
        "20110617T123816",
        "20110620T133816",
        "20110624T040816",
        "20110704T004002",
        "20110704T023402",
    }
)

# 14-15: the 2011-07-18 pair, the only 31 ms exposures kept by EXPOSURE_MAX_MS. Excluded from the
# comparison altogether (they are still rendered and saved to OUT_DIR).
EXCLUDED_STAMPS = frozenset({"20110718T204002", "20110718T223402"})

# Frames come in near-simultaneous pairs: a 1500 ms long exposure and a short (8-31 ms) exposure.
# The long exposures saturate (the disk clips to full well), so both the real and cielim sides render
# as a flat overexposed blob — not an informative comparison. Skip anything above this threshold and
# keep only the well-exposed short twins. Set EXPOSURE_MAX_MS = None to add the long exposures back.
EXPOSURE_MAX_MS = 100


def _sorted_fits():
    return [p for p in sorted(FITS_DIR.iterdir()) if p.is_file() and p.suffix.lower() == ".fit"]


def _real_entries():
    """List of (ephemeris_time, fit_path) for the real frames, keyed by each frame's START_TIME
    header. Matching on time (rather than list position) keeps the real/generated pairing correct
    even if the file ordering changes. Requires SPICE kernels loaded (for str2et)."""
    entries = []
    for p in _sorted_fits():
        try:
            exp, time, *_ = get_header(str(p))
            if EXPOSURE_MAX_MS is not None and exp > EXPOSURE_MAX_MS:
                continue  # overexposed long exposure — re-added when EXPOSURE_MAX_MS is None
            entries.append((spice.str2et(time), p))
        except Exception:
            continue
    return entries


def _real_gray_of(path):
    """Grayscale uint8 of a real Vesta FITS frame (HDU[0]).

    Min/max stretch computed in-memory (to_uint8_gray with 0/100 percentiles) — the same look the
    saved PNG previews had, without saving/reading a PNG. Preserves the resolved disk's gradient; a
    1-99 percentile stretch would clip the disk (it's <1% of the frame) to a flat white blob.
    """
    data = np.nan_to_num(fits.open(str(path))[0].data)
    return image_comparison.to_uint8_gray(data, lo_pct=0, hi_pct=100)


def _predicted_pixel(path):
    """SPICE-projected Vesta pixel for a real frame — where cielim places Vesta given the ephemeris.

    Validated against cielim's rendered COB to sub-pixel. Vesta is at the scene origin, so this
    projects the origin from the Dawn position through the same pose cielim is pointed with (DAWN_FC2
    via DAWN_SPACECRAFT), plus the render's vertical flip (np.flip(image, 0)). Kernels must be loaded;
    the render time is the frame's START_TIME (as in the render loop). Keep FOV/resolution in sync
    with scene_setup.
    """
    _, tstr, *_ = get_header(str(path))
    time = spice.str2et(tstr)
    position, _ = spice.spkpos("DAWN", time, "J2000", "NONE", "2000004")
    BN = spice.pxform("DAWN_SPACECRAFT", "DAWN_FC2", time) @ spice.pxform("J2000", "DAWN_SPACECRAFT", time)
    return image_comparison.project_to_pixel(
        position, BN, (5.5 * np.pi / 180, 5.5 * np.pi / 180), (1024, 1024), flip_y=True
    )


def _stamp(et):
    """Filesystem-safe compact UTC stamp for a render time, e.g. 20110503T133516."""
    return spice.et2utc(et, "ISOC", 0).replace("-", "").replace(":", "")


def _gen_time(path):
    """Ephemeris time parsed from a saved generated filename's compact stamp (..._YYYYMMDDThhmmss)."""
    m = re.search(r"(\d{8})T(\d{6})", path.name)
    if not m:
        return None
    d, t = m.groups()
    return spice.str2et(f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}")


def _stamp_of(path):
    """Compact observation stamp of a saved generated frame (..._YYYYMMDDThhmmss), or None."""
    m = re.search(r"(\d{8})T(\d{6})", path.name)
    return f"{m.group(1)}T{m.group(2)}" if m else None


def _gen_time_if(keep):
    """``gen_time`` for compare_saved restricted to the frames whose stamp satisfies ``keep``.

    Returning None for every other frame leaves it unpaired, which is how compare_saved drops it: the
    group's figures are numbered over the kept frames only.
    """

    def _timer(path):
        stamp = _stamp_of(path)
        return _gen_time(path) if stamp is not None and keep(stamp) else None

    return _timer


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


def get_header_data():
    exposure_time_list = []
    time_list = []
    position_list = []
    attitude_list = []
    sun_list = []
    for p in sorted(FITS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fit"}:
            exp, time, pos, sun_pos, mrp = get_header(str(p))
            if EXPOSURE_MAX_MS is not None and exp > EXPOSURE_MAX_MS:
                continue  # overexposed long exposure — re-added when EXPOSURE_MAX_MS is None
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

    scene.set_camera_params(name="dawn", grayscale=True)

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

    scene.set_corruption_params(psf_sigma=0.7 , read_noise=18, dc_rate=dark_current_rate_e_s(vesta_ccd_temp_k), dc_sigma=10, shot_noise=True)

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
        # Save the generated frame named with its observation time so the comparison can read it
        # back and pair it with the real image of the same time (using the exact saved orientation).
        cv2.imwrite(os.path.join(current_file_path, f"images-vesta/vesta_{_stamp(time)}.png"), image)

    connector.disconnect()
    launcher.terminate()

    # Read the saved generated frames back and compare each to the real image at the same time.
    # raw/ and aligned/ subsets, each with individual histograms + heatmaps and an average histogram.
    real_entries = _real_entries()

    # Main group: the close-in frames only (old indices 12-13 and 16-19, renumbered 00-05 here). The
    # distant approach frames go to their own group below and the 31 ms pair is dropped outright.
    n = image_comparison.compare_saved(
        OUT_DIR, _gen_time_if(lambda s: s not in DISTANT_STAMPS and s not in EXCLUDED_STAMPS),
        real_entries, _real_gray_of, str(SHOWCASE_DIR),
        title_real="real", title_generated="cielim",
        # Overall average plus one sub-batch average per observation date (15 ms vs 14 ms exposures).
        average_batches=[("20110717", range(0, 2)), ("20110723", range(2, 6))],
    )
    print(f"Saved real-vs-generated batch comparison ({n} pairs) -> {SHOWCASE_DIR}")

    # Distant-approach group: the same comparison over DISTANT_STAMPS only (old indices 00-11), so its
    # average histogram isn't mixed with the close-in frames.
    m = image_comparison.compare_saved(
        OUT_DIR, _gen_time_if(lambda s: s in DISTANT_STAMPS),
        real_entries, _real_gray_of, str(DISTANT_DIR),
        title_real="real", title_generated="cielim",
    )
    print(f"Saved distant-approach batch comparison ({m} pairs) -> {DISTANT_DIR}")

    spice.kclear()


if __name__ == "__main__":
    vesta_scenario()
