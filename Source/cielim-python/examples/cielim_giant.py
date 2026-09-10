import contextlib
import glob
import io
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for matplotlib
import numpy as np
import spiceypy as spice
from matplotlib import pyplot as plt
from PIL import Image

import cielim
from cielim.utils import qe_curve_fit as qefit
from cielim.utils import rigid_body_kinematics as rbk


here = Path(__file__).resolve()
cielim_root = here.parents[1]

sys.path.insert(0, str(cielim_root / "cielim"))
sys.path.insert(0, str(here.parent))

mk = cielim_root / "support-data" / "vesta-spice" / "vesta-spice.txt"
fit_dir = cielim_root / "support-data" / "vesta-spice" / "opnav"
out_dir = here.parent / "images-cielim-giant"
qe_file = cielim_root / "support-data" / "vesta-spice" / "f2_qe_curve.csv"
giant_gif_path = cielim_root / "support-data" / "vesta-spice" / "templatesummary.gif"
out_gif = out_dir / "comparison.gif"


@contextlib.contextmanager
def cd(path: Path):
    prev = Path.cwd()
    os.chdir(str(path))
    try:
        return (yield)
    finally:
        os.chdir(str(prev))


def parse_lbl(lbl_path: str) -> dict:
    """Parse key fields from a PDS3 .LBL file."""
    result = {}
    with open(lbl_path, "r") as f:
        content = f.read()

    single_keys = {
        "START_TIME": r"START_TIME\s*=\s*([\w\-\:\.]+)",
        "EXPOSURE_DURATION": r"EXPOSURE_DURATION\s*=\s*([\d\.]+)",
    }
    for key, pattern in single_keys.items():
        m = re.search(pattern, content)
        if m:
            result[key] = m.group(1)

    return result


def collect_image_lbl_pairs() -> list:
    """Return sorted list of (fit_path, lbl_path) tuples — short exposure only."""
    fits_files = sorted(
        glob.glob(str(fit_dir / "2011123_OPNAV_001/*.FIT"))
        + glob.glob(str(fit_dir / "2011165_OPNAV_007/*.FIT"))
        + glob.glob(str(fit_dir / "2011198_OPNAV_017/*.FIT"))
    )
    pairs = []
    for fit in fits_files:
        lbl = fit.replace(".FIT", ".LBL")
        if not os.path.exists(lbl):
            print(f"WARNING: no .LBL found for {fit}")
            continue
        with open(lbl, "r") as f:
            content = f.read()
        m = re.search(r"EXPOSURE_DURATION\s*=\s*([\d\.]+)", content)
        if m:
            exp_ms = float(m.group(1))
            if exp_ms < 1000:
                pairs.append((fit, lbl))
    print(f"\nTotal short exposure images: {len(pairs)}")
    return pairs


def convert_timestamp(doy_str: str) -> str:
    """Convert 2011-123T13:36:01.154 to 2011-05-03T13:36:01.154000"""
    date_part, time_part = doy_str.strip().split("T")
    parts = date_part.split("-")
    year, doy = parts[0], parts[1]
    dt = datetime.strptime(f"{year}-{doy}", "%Y-%j")
    return dt.strftime(f"%Y-%m-%dT{time_part}") + "00"


def get_timestamp(lbl_path: str) -> str:
    """Read START_TIME from a PDS3 .LBL file and return it as a string."""
    with open(lbl_path) as f:
        content = f.read()
    m = re.search(r"START_TIME\s*=\s*([\w\-\:\.]+)", content)
    return m.group(1) if m else ""


def make_cielim_frame(img: np.ndarray, timestamp: str, x1: int, x2: int, y1: int, y2: int) -> Image.Image:
    """Render CIELIM frame on a canvas that matches the GIANT GIF frame size."""

    fig = plt.figure(figsize=(3.2, 4.8), dpi=100)

    fig.suptitle(f"{timestamp} Vesta", fontsize=10, y=0.98)

    ax = fig.add_axes([0.15, 0.08, 0.80, 0.78])

    ax.imshow(img, cmap="gray", origin="upper")
    ax.set_xlim(x1, x2)
    ax.set_ylim(y2, y1)  # inverted y like GIANT
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("CIELIM", fontsize=10)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).copy().convert("RGB")


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(name="dawn", position=(0, 0, -1000000), velocity=(0, 1000, 0))

    scene.set_camera_params(name="dawn")

    scene.set_lens_params(
        fov=(5.5 * np.pi / 180, 5.5 * np.pi / 180),
        focal_length=150e-3,
        aperture_radius=150e-3 / 7.5 / 2,  # focal length / f# / 2
    )

    scene.set_sensor_params(
        resolution=(1024, 1024),
        exposure=1e-3,
        sensor_dims=(13.3e-3, 13.3e-3),
        well_capacity=120_000,
    )

    scene.set_corruption_params(read_noise=18)

    scene.set_celestial_body_params(0, position=(0, 0, -10000))

    index = scene.add_celestial_body("vesta")

    scene.set_celestial_body_params(
        index, albedo=0.423, mesh_shape="vesta_normalized", mesh_brdf="Regolith", mesh_radius=262.7 * 1e3
    )

    return scene


def create_comparison_gif() -> None:
    """Create side-by-side comparison GIF of GIANT template summary and CIELIM."""
    giant_gif = Image.open(giant_gif_path)
    giant_frames = []
    try:
        while True:
            frame = giant_gif.copy().convert("RGB")

            frame_np = np.array(frame)

            if frame_np.mean() < 5:
                print("  skipping GIANT dark frame")
            else:
                giant_frames.append(frame)
            giant_gif.seek(giant_gif.tell() + 1)
    except EOFError:
        pass
    GIANT_W, GIANT_H = giant_frames[0].size

    lbl_files = sorted(
        glob.glob(str(fit_dir / "2011123_OPNAV_001/*.LBL"))
        + glob.glob(str(fit_dir / "2011165_OPNAV_007/*.LBL"))
        + glob.glob(str(fit_dir / "2011198_OPNAV_017/*.LBL"))
    )
    short_lbls = []
    for lbl in lbl_files:
        with open(lbl) as f:
            content = f.read()
        m = re.search(r"EXPOSURE_DURATION\s*=\s*([\d\.]+)", content)
        if m and float(m.group(1)) < 1000:
            short_lbls.append(lbl)

    cielim_paths = sorted(glob.glob(str(out_dir / "giant-cielim-vesta_*.png")))
    cielim_frames = []

    for path in cielim_paths:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

        if img.max() == 255 and img.mean() < 1.0:

            continue

        lbl_idx = len(cielim_frames)
        timestamp = convert_timestamp(get_timestamp(short_lbls[lbl_idx])) if lbl_idx < len(short_lbls) else ""
        if img.mean() > 5.0:
            # session 3
            thresh_val = int(np.percentile(img, 99))
            _, thresh = cv2.threshold(img, thresh_val, 255, cv2.THRESH_BINARY)
            moments = cv2.moments(thresh)
            if moments["m00"] > 0:
                bright_cx = int(moments["m10"] / moments["m00"])
                bright_cy = int(moments["m01"] / moments["m00"])
                cx = bright_cx - 150
                cy = bright_cy
            else:
                cx, cy = 558, 501
            x1 = cx - 330
            x2 = cx + 330
            y1 = cy - 330
            y2 = cy + 330

        else:

            _, thresh = cv2.threshold(img, img.max() // 4, 255, cv2.THRESH_BINARY)
            moments = cv2.moments(thresh)
            if moments["m00"] > 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
            else:
                cx, cy = img.shape[1] // 2, img.shape[0] // 2
            if lbl_idx < 20:
                # session 1 — far away, tiny Vesta ~5px
                x1, x2 = cx - 6, cx + 6
                y1, y2 = cy - 5, cy + 5
            elif lbl_idx < 40:
                # session 2 — middle distance, Vesta ~11px
                x1, x2 = cx - 21, cx + 21
                y1, y2 = cy - 21, cy + 21

        frame = make_cielim_frame(img, timestamp, x1, x2, y1, y2)
        cielim_frames.append(frame)

    n_frames = min(len(giant_frames), len(cielim_frames))
    GAP = 4
    TOTAL_W = GIANT_W + GAP + 320
    TOTAL_H = GIANT_H

    frames = []
    for idx in range(n_frames):
        canvas = Image.new("RGB", (TOTAL_W, TOTAL_H), (255, 255, 255))

        # GIANT panel (left)
        canvas.paste(giant_frames[idx], (0, 0))

        cielim_resized = cielim_frames[idx].resize((320, 480), Image.LANCZOS)
        canvas.paste(cielim_resized, (GIANT_W + GAP, 0))

        frames.append(canvas)

    frames[0].save(out_gif, save_all=True, append_images=frames[1:], duration=500, loop=0)
    print(f"\nComparison GIF saved to {out_gif}")


def cielim_giant(number_of_images: int = None):
    pairs = collect_image_lbl_pairs()
    if not pairs:
        raise FileNotFoundError(f"No .FIT/.LBL pairs found under {fit_dir}")

    if number_of_images is not None:
        pairs = pairs[:number_of_images]

    out_dir.mkdir(parents=True, exist_ok=True)

    scene = scene_setup()

    if qe_file.exists():
        solid_angle = np.pi
        pixel_area = 14e-6 * 14e-6
        qefit.set_qe_curve_fit(
            scene.get_scene(), str(qe_file), solid_angle, pixel_area, figure_name="qe_fit_giant_fc2"
        )
        print(f"QE curve loaded: {qe_file.name}")
    else:
        print(f"WARNING: QE file not found at {qe_file}")

    spice.kclear()
    with cd(cielim_root):
        spice.furnsh(str(mk))

    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()

    for idx, (fit_path, lbl_path) in enumerate(pairs):

        lbl = parse_lbl(lbl_path)
        et = spice.str2et(lbl["START_TIME"])
        exposure_s = float(lbl["EXPOSURE_DURATION"]) / 1000.0

        sc_pos_km, _ = spice.spkpos("DAWN", et, "J2000", "NONE", "2000004")
        sun_pos_km, _ = spice.spkpos("SUN", et, "J2000", "NONE", "2000004")

        BN = spice.pxform("J2000", "DAWN_SPACECRAFT", et)
        CB = spice.pxform("DAWN_SPACECRAFT", "DAWN_FC2", et)
        BN = np.dot(CB, BN)

        BN_vesta = spice.pxform("J2000", "IAU_VESTA", et)

        scene.set_celestial_body_params(0, position=tuple((sun_pos_km * 1e3).tolist()))
        scene.set_celestial_body_params(1, attitude=tuple(BN_vesta.flatten().tolist()))

        scene.set_spacecraft_params(position=tuple((sc_pos_km * 1e3).tolist()), attitude=tuple(rbk.dcm_to_mrp(BN)))

        scene.set_sensor_params(exposure=exposure_s)

        connector.send_frame(scene.get_scene())

        image, _, _ = connector.request_image_for_camera_id(1, True, False)
        image = np.flip(image, 0)
        cv2.imwrite(str(out_dir / f"giant-cielim-vesta_{idx:03d}.png"), image)

    connector.disconnect()
    launcher.terminate()
    spice.kclear()

    print("\nCreating comparison GIF...")
    create_comparison_gif()


if __name__ == "__main__":
    cielim_giant()
