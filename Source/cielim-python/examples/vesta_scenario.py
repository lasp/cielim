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
here = Path(__file__).resolve()
root = here.parents[1]  # <repo root>
mk = root / "support-data" / "vesta-spice" / "vesta-spice.txt"
fits_dir = root / "support-data" / "vesta-spice" / "images"
out_dir = here.parent / "images-vesta"

showcase_dir = here.parent / "images-compared" / "vesta"

# Two comparison groups plus a dropped pair, keyed by observation-time stamp. These are the distant
# approach frames, where Vesta covers little of the frame, so they get their own group in distant_dir.
distant_dir = here.parent / "images-compared" / "vesta_distant"
distant_stamps = frozenset(
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

excluded_stamps = frozenset({"20110718T204002", "20110718T223402"})

# Frames come in pairs, a 1500 ms long exposure and a short one; the long exposures saturate to a
# flat blob on both sides. Set exposure_max_ms = None to add them back.
exposure_max_ms = 100

albedo = 0.423  # published geometric albedo, both modes

# One run renders and compares one mode. The close frames resolve a disk and take a Regolith BRDF;
# the distant approach frames are a few pixels across and take a Lambertian one. `keep` decides both
# which frames the run renders and which ones it compares, so the two can never disagree.
render_modes = {
    "close": {
        "brdf": "Regolith",
        "out": showcase_dir,
        "keep": lambda s: s not in distant_stamps and s not in excluded_stamps,
        "batches": [("20110717", range(0, 2)), ("20110723", range(2, 6))],
    },
    "distant": {
        "brdf": "Lambertian",
        "out": distant_dir,
        "keep": lambda s: s in distant_stamps,
        "batches": None,
    },
}


def _sorted_fits():
    return [p for p in sorted(fits_dir.iterdir()) if p.is_file() and p.suffix.lower() == ".fit"]


def _real_entries():
    """List of (ephemeris_time, fit_path) for the real frames, keyed by each frame's START_TIME
    header. Matching on time (rather than list position) keeps the real/generated pairing correct
    even if the file ordering changes. Requires SPICE kernels loaded (for str2et)."""
    entries = []
    for p in _sorted_fits():
        try:
            exp, time, *_ = get_header(str(p))
            if exposure_max_ms is not None and exp > exposure_max_ms:
                continue  # overexposed long exposure — re-added when exposure_max_ms is None
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
    for p in sorted(fits_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in {".fit"}:
            exp, time, pos, sun_pos, mrp = get_header(str(p))
            if exposure_max_ms is not None and exp > exposure_max_ms:
                continue  # overexposed long exposure — re-added when exposure_max_ms is None
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


def scene_setup(mode: str = "close") -> cielim.Scene:
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
        index,
        albedo=albedo,
        mesh_shape="vesta_normalized",
        mesh_brdf=render_modes[mode]["brdf"],
        mesh_radius=262.7 * 1e3,
    )

    return scene


def vesta_scenario(number_of_images: int | None = None, mode: str = "close"):
    """Render and compare one mode's frames. See render_modes for what each renders.

    ``number_of_images`` is applied after the mode's frame selection, so a truncated run still
    renders frames belonging to ``mode``.
    """
    if mode not in render_modes:
        raise ValueError(f"unknown mode {mode!r}; expected one of {', '.join(render_modes)}")

    scene = scene_setup(mode)

    qe_file_path = (
        Path(__file__).resolve().parent.parent.parent / "cielim-python/support-data/vesta-spice/f2_qe_curve.csv"
    )

    solid_angle = np.pi
    pixel_area = 2.2 * 2.2 * 10 ** (-12)  # m^2

    qefit.set_qe_curve_fit(
        scene.get_scene(), str(qe_file_path), solid_angle, pixel_area, figure_name="qe_fit_vesta_fc2"
    )

    # Load SPICE kernels using a meta-kernel with RELATIVE paths.
    # We temporarily chdir to the repo root so 'support-data/…' resolves correctly.
    spice.kclear()
    with cd(root):
        spice.furnsh(str(mk))

    if os.path.exists(fits_dir):
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

    et_range = []
    for _str in time_list:
        et_range.append(spice.str2et(_str))
    et_range = np.array(et_range)

    # Keep only the frames this mode owns, then truncate, so a short run is still this mode's frames.
    keep = render_modes[mode]["keep"]
    selected = [i for i, et in enumerate(et_range) if keep(_stamp(et))]
    if number_of_images is not None:
        selected = selected[:number_of_images]
    print(f"[{mode}] rendering {len(selected)} of {len(et_range)} frames with {render_modes[mode]['brdf']} BRDF")

    # Output dir
    out_dir.mkdir(parents=True, exist_ok=True)

    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()

    for idx in selected:
        time = et_range[idx]
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
        cv2.imwrite(os.path.join(current_file_path, f"images-vesta/vesta_{_stamp(time)}.png"), image)

    connector.disconnect()
    launcher.terminate()

    real_entries = _real_entries()

    comparison_dir = render_modes[mode]["out"]
    n, stats = image_comparison.compare_saved(
        out_dir, _gen_time_if(keep),
        real_entries, _real_gray_of, str(comparison_dir),
        title_real="real", title_generated="cielim",
        average_batches=render_modes[mode]["batches"],
    )
    print(f"Saved {mode} real-vs-generated batch comparison ({n} pairs) -> {comparison_dir}")
    print(image_comparison.format_error_stats(stats))

    spice.kclear()


if __name__ == "__main__":
    import sys

    vesta_scenario(mode=sys.argv[1] if len(sys.argv) > 1 else "close")
