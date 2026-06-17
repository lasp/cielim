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
from cielim import rigid_body_kinematics as rbk
from cielim import scene


HERE = Path(__file__).resolve()
CIELIM_ROOT = HERE.parents[1]

sys.path.insert(0, str(CIELIM_ROOT / "cielim"))
sys.path.insert(0, str(HERE.parent))

MK = CIELIM_ROOT / "support-data" / "vesta-spice" / "vesta-spice.txt"
FIT_DIR = CIELIM_ROOT / "support-data" / "vesta-spice" / "opnav"
OUT_DIR = HERE.parent / "images-cielim-giant"
QE_FILE = CIELIM_ROOT / "support-data" / "vesta-spice" / "f2_qe_curve.csv"
GIANT_GIF = CIELIM_ROOT / "support-data" / "vesta-spice" / "templatesummary.gif"
OUT_GIF = OUT_DIR / "comparison.gif"


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
        glob.glob(str(FIT_DIR / "2011123_OPNAV_001/*.FIT"))
        + glob.glob(str(FIT_DIR / "2011165_OPNAV_007/*.FIT"))
        + glob.glob(str(FIT_DIR / "2011198_OPNAV_017/*.FIT"))
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


def scene_setup() -> cielim.CielimMessage:
    protobuf_message = cielim.CielimMessage()

    vesta = protobuf_message.celestialBodies.add()
    vesta.bodyName = "vesta"
    [vesta.position.append(v) for v in [0, 0, 0]]
    [vesta.velocity.append(v) for v in [0, 0, 0]]
    [vesta.attitude.append(v) for v in np.eye(3).flatten().tolist()]
    vesta.model.shapeModel = "vesta_normalized"
    vesta.model.geometricAlbedo = 0.423
    vesta.model.refModel.brdfModel = "Regolith"
    vesta.model.meanRadius = 262.7 * 1e3

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(v) for v in [0, 0, -10000]]
    [sun.attitude.append(v) for v in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "dawn"

    protobuf_message.camera.sensorModel.exposureTime = 1e-3
    protobuf_message.camera.sensorModel.systemGain = 1
    protobuf_message.camera.sensorModel.readNoise = 18
    protobuf_message.camera.sensorModel.sensorWidth = 13.3e-3
    protobuf_message.camera.sensorModel.sensorHeight = 13.3e-3
    protobuf_message.camera.sensorModel.fullWellCapacity = 120_000

    protobuf_message.camera.lensModel.focalLength = 150e-3
    protobuf_message.camera.lensModel.pointSpreadFunction = 0.0
    protobuf_message.camera.lensModel.apertureRadius = (150e-3) / 7.5 / 2

    [protobuf_message.camera.lensModel.fieldOfView.append(v) for v in [5.5 * np.pi / 180, 5.5 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(v) for v in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(v) for v in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(v) for v in [1024, 1024]]

    protobuf_message.spacecraft.spacecraftName = "dawn"
    [protobuf_message.spacecraft.position.append(v) for v in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(v) for v in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(v) for v in [0, 0, 0]]

    return protobuf_message


def create_comparison_gif() -> None:
    """Create side-by-side comparison GIF of GIANT template summary and CIELIM."""
    giant_gif = Image.open(GIANT_GIF)
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
        glob.glob(str(FIT_DIR / "2011123_OPNAV_001/*.LBL"))
        + glob.glob(str(FIT_DIR / "2011165_OPNAV_007/*.LBL"))
        + glob.glob(str(FIT_DIR / "2011198_OPNAV_017/*.LBL"))
    )
    short_lbls = []
    for lbl in lbl_files:
        with open(lbl) as f:
            content = f.read()
        m = re.search(r"EXPOSURE_DURATION\s*=\s*([\d\.]+)", content)
        if m and float(m.group(1)) < 1000:
            short_lbls.append(lbl)

    cielim_paths = sorted(glob.glob(str(OUT_DIR / "giant-cielim-vesta_*.png")))
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

    frames[0].save(OUT_GIF, save_all=True, append_images=frames[1:], duration=500, loop=0)
    print(f"\nComparison GIF saved to {OUT_GIF}")


def cielim_giant(number_of_images: int = None):
    pairs = collect_image_lbl_pairs()
    if not pairs:
        raise FileNotFoundError(f"No .FIT/.LBL pairs found under {FIT_DIR}")

    if number_of_images is not None:
        pairs = pairs[:number_of_images]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    if QE_FILE.exists():
        message = scene_frame.get_scene()
        solid_angle = np.pi
        pixel_area = 14e-6 * 14e-6
        scene_frame.set_qe_curve_fit(str(QE_FILE), solid_angle, pixel_area)
        scene_frame.set_existing_message(message)
        print(f"QE curve loaded: {QE_FILE.name}")
    else:
        print(f"WARNING: QE file not found at {QE_FILE}")

    spice.kclear()
    with cd(CIELIM_ROOT):
        spice.furnsh(str(MK))

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

        message = scene_frame.get_scene()

        message.celestialBodies[0].ClearField("attitude")
        [message.celestialBodies[0].attitude.append(v) for v in BN_vesta.flatten().tolist()]

        message.spacecraft.ClearField("position")
        message.spacecraft.ClearField("attitude")
        [message.spacecraft.position.append(v) for v in (sc_pos_km * 1e3).tolist()]
        [message.spacecraft.attitude.append(v) for v in rbk.dcm_to_mrp(BN)]

        message.celestialBodies[1].ClearField("position")
        [message.celestialBodies[1].position.append(v) for v in (sun_pos_km * 1e3).tolist()]

        message.camera.sensorModel.exposureTime = exposure_s

        scene_frame.set_existing_message(message)
        connector.send_frame(scene_frame.get_scene())

        image, _, _ = connector.request_image_for_camera_id(1, True, False)
        image = np.flip(image, 0)
        cv2.imwrite(str(OUT_DIR / f"giant-cielim-vesta_{idx:03d}.png"), image)

    connector.disconnect()
    launcher.terminate()
    spice.kclear()

    print("\nCreating comparison GIF...")
    create_comparison_gif()


if __name__ == "__main__":
    cielim_giant()
