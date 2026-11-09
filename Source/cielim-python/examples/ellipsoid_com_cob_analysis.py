"""
Goal:
    Test an analytical centre-of-brightness (CoB) offset for a triaxial ellipsoid.

    Each sample draws a phase angle, renders a sphere, then renders the same scene with the sphere
    deformed into the ellipsoid x^T A x = 1, A = D^T diag(1/a^2, 1/b^2, 1/c^2) D. The CoB is predicted
    from the true centre of mass (CoM) three ways:

        1. sphere,    sphere model:    gamma(alpha) * rho along the projected sunline
        2. ellipsoid, sphere model:    same, with rho the mean of the three semi-axes, the radius a
                                       distant observer would have (the volume is not known)
        3. ellipsoid, ellipsoid model: with R = r^T A r, S = s^T A s, C = s^T A r,
                                       cos(alpha_bar) = C / sqrt(SR),
                                       delta = gamma(alpha_bar) sqrt(R) / sqrt(SR - C^2) (s - cos(alpha) r)

    gamma is the binary model, 4 / (3 pi) (1 - cos). Mapping y = A^(1/2) x turns the ellipsoid into a
    unit sphere seen at phase alpha_bar, and an affine map keeps area centroids, so case 3 should be
    exact for a binary CoB up to perspective and pixelization. The measured CoB is therefore the
    unweighted centroid of the thresholded lit silhouette, not the engine's radiance-weighted CoB.

    Fixed for a run: camera, exposure, spacecraft position, body-centred pointing. Randomized: the
    phase angle and its azimuth about the boresight, the three semi-axes and the ellipsoid attitude.
"""

import importlib.util
import json
import os

import cielim
import cv2
import matplotlib
import numpy as np
from cielim.utils import rigid_body_kinematics as rbk
from matplotlib import pyplot as plt
from scipy import stats
from scipy.spatial.transform import Rotation

matplotlib.rcParams.update({"font.size": 6})
colorsInt = len(matplotlib.colormaps["inferno"].colors) / (10.0)
colorList = []
for i in range(10):
    colorList.append(matplotlib.colormaps["inferno"].colors[int(i * colorsInt)])

current_file_path = os.path.dirname(__file__)


def _load_sibling(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(current_file_path, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gm = _load_sibling("geometric_cob_model")

target_name = "ellipsoid"
central_body_index = 1

base_radius = 25e3  # metres; the axis scales multiply this
axis_log_sigma = 0.5  # lognormal spread on a, b, c
axis_sigma_span = 3.0  # sizing headroom: the largest axis the frame must still hold
frame_fill = 0.75  # that largest ellipsoid spans this fraction of the smaller field of view
phase_range_deg = (5.0, 170.0)

# Spacecraft range in units of base_radius. The models assume a distant camera; up close it sees less
# than a hemisphere and perspective dominates the residual (about 1.5 px median at 28 radii, 0.3 px at
# 113). The field of view is set from the range so the disk keeps the same size in pixels at any range.
default_range_radii = 300.0
base_fov = (20 * np.pi / 180, 15 * np.pi / 180)  # the field of view that frames the body at base_range_m

# Pixel i covers [i, i + 1) in the projection's continuous coordinates, so its centre is at i + 0.5.
# Centroids are reported in those coordinates, the same ones project() returns.
pixel_centre = 0.5

astronomical_unit = 1.495978707e11

# Above this many DN a pixel counts as lit. Low on purpose: the binary model is the centroid of the
# whole illuminated silhouette down to the terminator, where the Lambertian falloff is dim.
lit_threshold = 12
sweep_thresholds = (1, 2, 3, 5, 8, 12, 16, 20, 25, 30, 40)

cases = {
    "sphere_sphere_model": "sphere, sphere model",
    "ellipsoid_sphere_model": "ellipsoid, sphere model",
    "ellipsoid_ellipsoid_model": "ellipsoid, ellipsoid model",
    "sphere_full_model": "sphere, full model (finite range)",
    "ellipsoid_full_model": "ellipsoid, full model (finite range)",
}
# The binary-model cases the threshold sweep and the clipped debug plot follow.
swept_cases = ("sphere_sphere_model", "ellipsoid_ellipsoid_model", "sphere_full_model", "ellipsoid_full_model")


def cob_offset_binary(phase_angle: float) -> float:
    """
    Computes COB correction due to solar phase angle assuming brightness is either 0 (shaded) or 1 (sunlit)
    Returns a normalized correction factor
    """
    return 4 / (3 * np.pi) * (1 - np.cos(phase_angle))


def ellipsoid_matrix(semi_axes, mesh_attitude_mrp):
    """
    Shape matrix A of the ellipsoid x^T A x = 1 in world axes.

    mesh_attitude rotates world into the principal frame (validated by the earlier ellipsoid
    scenario: a 2:1:1 body rolled 90 degrees about the boresight swaps its extents), so
    A = D^T diag(1/a^2, 1/b^2, 1/c^2) D with D = mrp_to_dcm(mesh_attitude).
    """
    dcm = rbk.mrp_to_dcm(np.asarray(mesh_attitude_mrp, float))
    return dcm.T @ np.diag(1.0 / np.asarray(semi_axes, float) ** 2) @ dcm


def sphere_offset(r_hat, s_hat, radius):
    """
    3D CoB offset of a sphere: gamma(alpha) * radius along the sunline component perpendicular to r_hat.

    Args:
        r_hat (ndarray): Unit vector from the body centre to the spacecraft.
        s_hat (ndarray): Unit vector from the body centre to the sun.
        radius (float): Sphere radius.

    Returns:
        ndarray: Offset from the CoM to the CoB, in the same units as radius.
    """
    r_hat, s_hat = np.asarray(r_hat, float), np.asarray(s_hat, float)
    cos_alpha = np.dot(s_hat, r_hat)
    perpendicular = s_hat - cos_alpha * r_hat
    norm = np.linalg.norm(perpendicular)
    if norm < 1e-12:
        return np.zeros(3)
    return cob_offset_binary(np.arccos(np.clip(cos_alpha, -1.0, 1.0))) * radius * perpendicular / norm


def ellipsoid_offset(r_hat, s_hat, shape_matrix):
    """
    3D CoB offset of the ellipsoid x^T A x = 1.

    delta = gamma(alpha_bar) sqrt(R) / sqrt(SR - C^2) (s_hat - cos(alpha) r_hat), with R = r^T A r,
    S = s^T A s, C = s^T A r and cos(alpha_bar) = C / sqrt(SR).

    Args:
        r_hat (ndarray): Unit vector from the body centre to the spacecraft.
        s_hat (ndarray): Unit vector from the body centre to the sun.
        shape_matrix (ndarray): A, in the same axes as r_hat and s_hat.

    Returns:
        ndarray: Offset from the CoM to the CoB, in the units of A^(-1/2).
    """
    r_hat, s_hat = np.asarray(r_hat, float), np.asarray(s_hat, float)
    a = np.asarray(shape_matrix, float)
    big_r = r_hat @ a @ r_hat
    big_s = s_hat @ a @ s_hat
    big_c = s_hat @ a @ r_hat
    determinant = big_s * big_r - big_c**2
    if determinant <= 1e-12 * big_s * big_r:
        return np.zeros(3)
    alpha_bar = np.arccos(np.clip(big_c / np.sqrt(big_s * big_r), -1.0, 1.0))
    gamma = cob_offset_binary(alpha_bar)
    return gamma * np.sqrt(big_r) / np.sqrt(determinant) * (s_hat - np.dot(s_hat, r_hat) * r_hat)


def equivalent_phase_angle(r_hat, s_hat, shape_matrix):
    """alpha_bar: the phase angle of the unit sphere the ellipsoid maps to."""
    a = np.asarray(shape_matrix, float)
    big_r, big_s, big_c = r_hat @ a @ r_hat, s_hat @ a @ s_hat, s_hat @ a @ r_hat
    return float(np.arccos(np.clip(big_c / np.sqrt(big_s * big_r), -1.0, 1.0)))


def sun_heading_for_phase(r_hat, phase_angle, azimuth):
    """Unit sun vector at ``phase_angle`` from r_hat, rotated ``azimuth`` about it."""
    r_hat = np.asarray(r_hat, float)
    helper = np.array([1.0, 0.0, 0.0]) if abs(r_hat[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(r_hat, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(r_hat, e1)
    return np.cos(phase_angle) * r_hat + np.sin(phase_angle) * (np.cos(azimuth) * e1 + np.sin(azimuth) * e2)


def to_gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def binary_centroid(gray, threshold=lit_threshold):
    """
    Sub-pixel centroid of the thresholded lit silhouette, every lit pixel weighted equally.

    This is what the binary model predicts. Not the engine CoB (radiance weighted, whole pixels) and
    not image_comparison_toolkit.get_cob_and_bbox (thresholds at a quarter of the peak, which drops
    the dim terminator pixels and biases the centroid sunward).

    Returns:
        ndarray | None: (x, y) in the continuous pixel coordinates project() uses, or None when
            nothing is lit.
    """
    lit = gray > threshold
    count = lit.sum()
    if not count:
        return None
    rows, columns = np.nonzero(lit)
    return np.array([columns.mean(), rows.mean()]) + pixel_centre


def photometric_centroid(gray, threshold=lit_threshold, gamma=2.2):
    """Radiance-weighted centroid, linearizing the gamma-encoded frame first. Recorded for reference."""
    gray = gray.astype(float)
    weights = np.where(gray > threshold, (gray / 255.0) ** gamma, 0.0)
    total = weights.sum()
    if total <= 0:
        return None
    rows, columns = np.indices(gray.shape)
    return np.array([(weights * columns).sum() / total, (weights * rows).sum() / total]) + pixel_centre


def lit_extent(gray, threshold=lit_threshold):
    """``(width, height, x0, y0)`` in pixels of the lit region's bounding box, or None if unlit."""
    rows, columns = np.nonzero(gray > threshold)
    if not len(columns):
        return None
    return (
        int(columns.max() - columns.min() + 1),
        int(rows.max() - rows.min() + 1),
        int(columns.min()),
        int(rows.min()),
    )


def _touches_edge(extents, resolution, margin=8):
    """True if any lit region comes within ``margin`` pixels of the frame edge."""
    width, height = resolution
    for w, h, x0, y0 in extents:
        if x0 < margin or y0 < margin or x0 + w > width - margin or y0 + h > height - margin:
            return True
    return False


def camera_frame(scene):
    """World→camera rotation, the camera's field of view and its resolution, read off the scene."""
    message = scene.get_scene()
    dcm_bn = rbk.mrp_to_dcm(np.array(message.spacecraft.attitude))
    dcm_cb = rbk.mrp_to_dcm(np.array(message.camera.bodyFrameToCameraMrp))
    return (
        dcm_cb @ dcm_bn,
        tuple(message.camera.lensModel.fieldOfView),
        tuple(message.camera.sensorModel.resolution),
    )


def project(world_point, spacecraft_position, world_to_camera, fov, resolution):
    """
    Pixel a world point lands on, reproducing cielim's projection: NDC = (cot(fovx/2) x/z,
    cot(fovy/2) y/z), pixel = ((1 + NDCx)/2 W, (1 + NDCy)/2 H), camera +z along the boresight.
    """
    d = np.asarray(world_to_camera, float) @ (np.asarray(world_point, float) - np.asarray(spacecraft_position, float))
    d = d / np.linalg.norm(d)
    width, height = resolution
    return np.array(
        [
            (1 + (d[0] / d[2]) / np.tan(fov[0] / 2)) / 2 * width,
            (1 + (d[1] / d[2]) / np.tan(fov[1] / 2)) / 2 * height,
        ]
    )


base_range_m = base_radius * np.exp(axis_sigma_span * axis_log_sigma) / np.tan(frame_fill * min(base_fov) / 2)


def scene_setup(range_radii: float = default_range_radii) -> cielim.Scene:
    """
    Camera and one body slot. Nothing randomized is set here; the sampler edits the returned scene.

    base_range_m frames the largest ellipsoid the axis distribution is likely to produce inside
    frame_fill of base_fov. At any other range, tan(fov / 2) scales by base_range_m / range, so that
    body keeps the same size in pixels and only the perspective changes.

    Args:
        range_radii (float): Spacecraft distance from the body centre, in units of base_radius. Must
            clear the largest likely semi-axis.
    """
    largest_semi_axis = base_radius * np.exp(axis_sigma_span * axis_log_sigma)
    camera_range = range_radii * base_radius
    if camera_range <= largest_semi_axis:
        raise ValueError(
            f"range of {range_radii} radii is inside the largest likely semi-axis "
            f"({largest_semi_axis / base_radius:.2f} radii)"
        )
    fov = tuple(2 * np.arctan(np.tan(angle / 2) * base_range_m / camera_range) for angle in base_fov)

    scene = cielim.Scene()
    scene.set_lens_params(fov=fov)
    scene.set_sensor_params(resolution=(2000, 1500), exposure=5e-4)
    scene.set_camera_params(grayscale=True)

    scene.add_celestial_body(target_name)  # index central_body_index; index 0 is the sun
    scene.set_celestial_body_params(
        central_body_index,
        position=(0.0, 0.0, 0.0),
        mesh_shape="sphere_normalized",
        mesh_brdf="Lambertian",
        mesh_radius=base_radius,
        albedo=0.2,
    )

    scene.set_spacecraft_params(position=(0.0, 0.0, -camera_range), velocity=(0.0, 1000.0, 0.0))

    return scene


def _render(connector, scene):
    """
    Re-init (the shape model is only re-read then), send, and return the frame plus engine CoB.

    The image is requested twice and the second kept: the first request after an init can come back
    blank, the same quirk tests/test_corruptions.py guards against.
    """
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    connector.request_image_for_camera_id(1)
    image, engine_cob, _ = connector.request_image_for_camera_id(1)
    return image, engine_cob


def ellipsoid_com_cob_analysis(
    number_of_samples: int = 200,
    axis_sigma: float = axis_log_sigma,
    seed: int | None = None,
    save_first: int = 100,
    threshold_sweep: bool = False,
    range_radii: float = default_range_radii,
    output_directory: str | None = None,
) -> dict:
    """
    Render sphere/ellipsoid pairs at random phase angles and score the three CoB predictions.

    Args:
        number_of_samples (int): Number of sphere/ellipsoid pairs to render.
        axis_sigma (float): Lognormal spread on the axis scales. Zero makes the ellipsoid a sphere,
            which is the degenerate self-check: cases 2 and 3 must then match case 1.
        seed (int, optional): Seed for the draws.
        save_first (int): Write the pair figure and lit masks for this many samples.
        threshold_sweep (bool): Also record the case 1 and case 3 residuals over sweep_thresholds.
        range_radii (float): Spacecraft range in body radii, see scene_setup.
        output_directory (str, optional): Defaults to examples/images-ellipsoid-com-cob/.

    Returns:
        dict: The per-sample rows plus the run's settings.
    """
    directory_path = output_directory or os.path.join(current_file_path, "images-ellipsoid-com-cob")
    os.makedirs(directory_path, exist_ok=True)

    rng = np.random.default_rng(seed)
    scene = scene_setup(range_radii)
    world_to_camera, fov, resolution = camera_frame(scene)
    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    camera_range = float(np.linalg.norm(spacecraft_position))
    r_hat = spacecraft_position / camera_range
    encoding_gamma = scene.get_scene().camera.sensorModel.gamma or 2.2
    ifov = fov[0] / resolution[0]

    def to_pixel(point):
        return project(point, spacecraft_position, world_to_camera, fov, resolution)

    com_px = to_pixel(np.zeros(3))

    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())

    rows, skipped = [], 0
    for idx in range(number_of_samples):
        phase_angle = np.radians(rng.uniform(*phase_range_deg))
        azimuth = rng.uniform(0.0, 2 * np.pi)
        sun_heading = sun_heading_for_phase(r_hat, phase_angle, azimuth)
        scene.set_celestial_body_params(0, position=tuple(astronomical_unit * sun_heading))

        axes = np.exp(rng.normal(0.0, axis_sigma, size=3)) if axis_sigma > 0 else np.ones(3)
        attitude = rbk.dcm_to_mrp(Rotation.random(random_state=rng.integers(2**31)).as_matrix())
        semi_axes = base_radius * axes
        shape_matrix = ellipsoid_matrix(semi_axes, attitude)
        mean_radius = float(np.mean(semi_axes))

        scene.set_celestial_body_params(
            central_body_index, mesh_radius=base_radius, mesh_distortions=(1.0, 1.0, 1.0), mesh_attitude=(0.0, 0.0, 0.0)
        )
        sphere_image, engine_cob_sphere = _render(connector, scene)

        scene.set_celestial_body_params(
            central_body_index, mesh_radius=base_radius, mesh_distortions=tuple(axes), mesh_attitude=tuple(attitude)
        )
        ellipsoid_image, engine_cob_ellipsoid = _render(connector, scene)

        frames = {"sphere": to_gray(sphere_image), "ellipsoid": to_gray(ellipsoid_image)}
        extents = [lit_extent(frame) for frame in frames.values()]
        if any(e is None for e in extents) or _touches_edge(extents, resolution):
            skipped += 1
            continue

        measured = {label: binary_centroid(frame) for label, frame in frames.items()}
        predicted = {
            "sphere_sphere_model": to_pixel(sphere_offset(r_hat, sun_heading, base_radius)),
            "ellipsoid_sphere_model": to_pixel(sphere_offset(r_hat, sun_heading, mean_radius)),
            "ellipsoid_ellipsoid_model": to_pixel(ellipsoid_offset(r_hat, sun_heading, shape_matrix)),
            # Case D plus the projective and limb-centre terms at the camera's range (geometric_cob_model).
            "sphere_full_model": to_pixel(gm.full_offset(np.eye(3) / base_radius**2, sun_heading, r_hat, camera_range)),
            "ellipsoid_full_model": to_pixel(gm.full_offset(shape_matrix, sun_heading, r_hat, camera_range)),
        }
        body_of = {name: name.split("_")[0] for name in cases}
        sunline_px = predicted["sphere_sphere_model"] - com_px
        sunline_px = sunline_px / np.linalg.norm(sunline_px) if np.linalg.norm(sunline_px) > 1e-9 else np.zeros(2)

        residuals = {}
        for name in cases:
            residual = measured[body_of[name]] - predicted[name]
            residuals[name] = {
                "predicted_cob_px": predicted[name].tolist(),
                "residual_px": residual.tolist(),
                "error_px": float(np.linalg.norm(residual)),
                "error_arcsec": float(np.degrees(np.linalg.norm(residual) * ifov) * 3600),
                "along_sunline_px": float(np.dot(residual, sunline_px)),
            }

        row = {
            "sample": idx,
            "phase_angle_deg": float(np.degrees(phase_angle)),
            "equivalent_phase_angle_deg": float(np.degrees(equivalent_phase_angle(r_hat, sun_heading, shape_matrix))),
            "azimuth_deg": float(np.degrees(azimuth)),
            "axes": axes.tolist(),
            "mesh_attitude_mrp": np.asarray(attitude).tolist(),
            "sun_heading_N": sun_heading.tolist(),
            "mean_radius_m": mean_radius,
            "apparent_radius_px": float(base_radius / camera_range / np.tan(fov[0] / 2) * resolution[0] / 2),
            "center_of_mass_px": com_px.tolist(),
            "measured_cob_px": {label: point.tolist() for label, point in measured.items()},
            "photometric_cob_px": {
                label: photometric_centroid(frame, gamma=encoding_gamma).tolist() for label, frame in frames.items()
            },
            "engine_cob_px": {"sphere": list(engine_cob_sphere), "ellipsoid": list(engine_cob_ellipsoid)},
            **residuals,
        }

        if threshold_sweep:
            row["threshold_sweep"] = {}
            for name in swept_cases:
                errors = []
                for threshold in sweep_thresholds:
                    point = binary_centroid(frames[body_of[name]], threshold)
                    errors.append(float(np.linalg.norm(point - predicted[name])) if point is not None else np.nan)
                row["threshold_sweep"][name] = errors

        rows.append(row)

        if idx < save_first:
            plot_sample_pair(frames, row, os.path.join(directory_path, f"sample{idx:03d}_pair.png"))
            for label, frame in frames.items():
                cv2.imwrite(os.path.join(directory_path, f"sample{idx:03d}_{label}.png"), frame)
                cv2.imwrite(
                    os.path.join(directory_path, f"sample{idx:03d}_{label}_mask.png"),
                    ((frame > lit_threshold) * 255).astype(np.uint8),
                )

        print(
            f"[{idx:03d}] phase {row['phase_angle_deg']:6.1f} (bar {row['equivalent_phase_angle_deg']:6.1f}) deg  "
            f"axes {axes[0]:.2f},{axes[1]:.2f},{axes[2]:.2f}  error px: "
            + "  ".join(f"{name} {residuals[name]['error_px']:6.2f}" for name in cases)
        )

    connector.disconnect()
    launcher.terminate()

    summary = {
        "number_of_samples": number_of_samples,
        "kept": len(rows),
        "skipped": skipped,
        "axis_sigma": axis_sigma,
        "seed": seed,
        "base_radius_m": base_radius,
        "camera_range_m": camera_range,
        "range_radii": range_radii,
        "camera_ifov": ifov,
        "lit_threshold": lit_threshold,
        "sweep_thresholds": list(sweep_thresholds) if threshold_sweep else None,
        "rows": rows,
    }
    with open(os.path.join(directory_path, "run.json"), "w") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Kept {len(rows)} of {number_of_samples} samples ({skipped} skipped) -> {directory_path}")
    return summary


def _show(ax, frame, x1, x2, y1, y2):
    """Crop of ``frame`` drawn in continuous pixel coordinates (pixel i spans [i, i + 1)), like the markers."""
    height, width = frame.shape
    x1, y1 = max(int(np.floor(x1)), 0), max(int(np.floor(y1)), 0)
    x2, y2 = min(int(np.ceil(x2)), width), min(int(np.ceil(y2)), height)
    ax.imshow(
        frame[y1:y2, x1:x2],
        cmap="gray",
        extent=[x1, x2, y2, y1],
        interpolation="nearest",
        vmin=0,
        vmax=255,
    )


def _mark(ax, row, label, predictions, com, zoomed=False):
    """True CoM, measured CoB and each predicted CoB; zoomed panels also join prediction to measurement."""
    measured = np.array(row["measured_cob_px"][label])
    scale = 1.6 if zoomed else 1.0
    ax.plot(*com, "o", mfc="none", mec="#40ff40", markersize=6 * scale, markeredgewidth=1.0, label="true CoM")
    ax.plot(*measured, "+", color=colorList[8], markersize=9 * scale, markeredgewidth=1.2, label="measured CoB")
    for name, description, color in predictions[label]:
        predicted = np.array(row[name]["predicted_cob_px"])
        if zoomed:
            ax.plot(*np.column_stack([predicted, measured]), "--", color=color, linewidth=0.8)
        ax.plot(
            *predicted,
            "x",
            color=color,
            markersize=7 * scale,
            markeredgewidth=1.2,
            label=f"predicted CoB, {description}",
        )


def plot_sample_pair(frames, row, output_path):
    """
    Sphere and ellipsoid side by side, each with its measured and predicted CoB and the true CoM.

    Top row: the whole body, both panels sharing one crop window. Bottom row: a zoom on the CoM/CoB
    markers, the same size for both bodies so the shifts compare by eye, with a dashed line from each
    prediction to the measured CoB — its length is the error in the panel title. The ellipsoid panels
    show both predictions: the sphere model it would get today and the ellipsoid model under test.
    """
    boxes = [lit_extent(frame) for frame in frames.values()]
    pad = 25
    x1 = min(b[2] for b in boxes) - pad
    y1 = min(b[3] for b in boxes) - pad
    x2 = max(b[2] + b[0] for b in boxes) + pad
    y2 = max(b[3] + b[1] for b in boxes) + pad

    com = np.array(row["center_of_mass_px"])
    predictions = {
        "sphere": [
            ("sphere_sphere_model", "sphere model", colorList[5]),
            ("sphere_full_model", "full model", colorList[3]),
        ],
        "ellipsoid": [
            ("ellipsoid_sphere_model", "sphere model", colorList[5]),
            ("ellipsoid_ellipsoid_model", "ellipsoid model", "#00d0ff"),
            ("ellipsoid_full_model", "full model", colorList[3]),
        ],
    }

    # One zoom half-width for both bodies: enough to hold every marker of either, with margin.
    centres, spans = {}, []
    for label in frames:
        points = np.array(
            [com, row["measured_cob_px"][label]] + [row[name]["predicted_cob_px"] for name, _, _ in predictions[label]]
        )
        centres[label] = 0.5 * (points.min(axis=0) + points.max(axis=0))
        spans.append(np.abs(points - centres[label]).max())
    half = max(1.4 * max(spans) + 3.0, 8.0)

    figure, axes = plt.subplots(2, 2, figsize=(7, 6.8), dpi=200)
    for column, label in enumerate(("sphere", "ellipsoid")):
        top, bottom = axes[0, column], axes[1, column]
        _show(top, frames[label], x1, x2, y1, y2)
        _mark(top, row, label, predictions, com)
        top.add_patch(
            plt.Rectangle(
                centres[label] - half, 2 * half, 2 * half, fill=False, edgecolor="#40ff40", linewidth=0.6, linestyle=":"
            )
        )
        errors = ", ".join(f"{d}: {row[n]['error_px']:.2f} px" for n, d, _ in predictions[label])
        top.set_title(f"{label}\n{errors}")
        top.legend(loc="lower left", fontsize=5, framealpha=0.6)

        cx, cy = centres[label]
        _show(bottom, frames[label], cx - half - 1, cx + half + 1, cy - half - 1, cy + half + 1)
        _mark(bottom, row, label, predictions, com, zoomed=True)
        bottom.set_xlim(cx - half, cx + half)
        bottom.set_ylim(cy + half, cy - half)
        bottom.set_title(f"{label}, zoom ({2 * half:.0f} px window)")
        for ax in (top, bottom):
            ax.set_xlabel("x (px)")
    for ax in axes[:, 0]:
        ax.set_ylabel("y (px)")
    a, b, c = row["axes"]
    figure.suptitle(
        f"sample {row['sample']}  phase {row['phase_angle_deg']:.1f} deg  "
        f"(equivalent {row['equivalent_phase_angle_deg']:.1f} deg)  axes {a:.2f}, {b:.2f}, {c:.2f}"
    )
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)
    return output_path


def replot_pairs(output_directory=None):
    """Rebuild the pair figures from a finished run's saved frames and run.json, without re-rendering."""
    directory_path = output_directory or os.path.join(current_file_path, "images-ellipsoid-com-cob")
    with open(os.path.join(directory_path, "run.json")) as handle:
        summary = json.load(handle)
    written = []
    for row in summary["rows"]:
        stem = os.path.join(directory_path, f"sample{row['sample']:03d}")
        paths = {label: f"{stem}_{label}.png" for label in ("sphere", "ellipsoid")}
        if not all(os.path.exists(path) for path in paths.values()):
            continue
        frames = {label: cv2.imread(path, cv2.IMREAD_GRAYSCALE) for label, path in paths.items()}
        written.append(plot_sample_pair(frames, row, f"{stem}_pair.png"))
    return written


def sunline_split(row, name):
    """
    Measured minus predicted CoB for one case, split along and across the projected sunline, in px.

    The sunline is taken from the sphere-model offset, which is gamma(alpha) rho along the projected
    sun direction by construction. Positive along is sunward of the prediction; positive across is
    90 degrees counter-clockwise from sunward in the image (x right, y down). Returns (nan, nan) when
    the sunline is undefined, at zero phase.
    """
    sunline = np.array(row["sphere_sphere_model"]["predicted_cob_px"]) - np.array(row["center_of_mass_px"])
    norm = np.linalg.norm(sunline)
    if norm < 1e-9:
        return np.nan, np.nan
    along = sunline / norm
    across = np.array([along[1], -along[0]])
    residual = np.array(row[name]["residual_px"])
    return float(residual @ along), float(residual @ across)


def plot_sunline_split(summary, output_directory=None):
    """
    Debug plot: each case's residual along and across the sunline, against phase angle.

    Both models put the CoB offset exactly on the projected sunline, and so does the true centroid for
    a parallel view, so any across-sunline residual comes from what the models leave out (perspective)
    or from the render, not from the formula.
    """
    rows = summary["rows"]
    directory_path = output_directory or os.path.join(current_file_path, "images-ellipsoid-com-cob")
    phases = np.array([row["phase_angle_deg"] for row in rows])
    case_colors = dict(zip(cases, (colorList[1], colorList[5], colorList[7], colorList[3], "#00d0ff")))

    figure, axes = plt.subplots(2, 1, figsize=(5, 5), dpi=200, sharex=True)
    print(f"{'':28s} {'along median':>13s} {'along std':>10s} {'across median':>14s} {'across std':>11s}")
    for name, description in cases.items():
        split = np.array([sunline_split(row, name) for row in rows])
        for ax, values in zip(axes, split.T):
            ax.scatter(phases, values, marker=".", s=10, color=case_colors[name], label=description)
        print(
            f"{description:28s} {np.nanmedian(split[:, 0]):13.3f} {np.nanstd(split[:, 0]):10.3f} "
            f"{np.nanmedian(split[:, 1]):14.3f} {np.nanstd(split[:, 1]):11.3f}"
        )
    for ax, label in zip(axes, ("along sunline (px, + sunward)", "across sunline (px)")):
        ax.axhline(0.0, color="0.6", linewidth=0.6)
        ax.set_ylabel(label)
    # The sphere model on the ellipsoid can be tens of pixels off; clip to where the other two live.
    others = np.array([sunline_split(row, name) for row in rows for name in swept_cases])
    limit = 1.5 * np.nanpercentile(np.abs(others), 99)
    for ax in axes:
        ax.set_ylim(-limit, limit)
    axes[0].set_title("Measured minus predicted CoB, split along and across the sunline")
    axes[0].legend(fontsize=5)
    axes[1].set_xlabel("Phase angle (deg)")
    figure.tight_layout()
    path = os.path.join(directory_path, "error-along-across-sunline.png")
    figure.savefig(path)
    plt.close(figure)
    return path


def gaussianity(values):
    """
    Mean, standard deviation and how Gaussian ``values`` are.

    Skewness and excess kurtosis are both 0 for a Gaussian (heavy tails give positive kurtosis).
    """
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    return {
        "mean": float(values.mean()),
        "std": float(values.std()),
        "skewness": float(stats.skew(values)),
        "excess_kurtosis": float(stats.kurtosis(values)),
    }


def error_histogram(errors, colors, title, xlabel, output_path, bins=50):
    """
    Outline histograms of each case's errors, with its mean (dotted) and a Gaussian of the same mean and
    sigma (dashed). The range holds the 0.5-99.5th percentiles of the narrowest-spread half of the
    cases, so a broad case does not flatten the precise ones; how many samples fall outside is in the
    legend. Also prints the statistics.
    """
    names = list(errors)
    spreads = sorted(names, key=lambda name: np.nanstd(errors[name]))
    core = np.concatenate([errors[name][np.isfinite(errors[name])] for name in spreads[: max(1, len(names) // 2 + 1)]])
    low, high = np.percentile(core, (0.5, 99.5))
    pad = 0.15 * (high - low)
    edges = np.linspace(low - pad, high + pad, bins + 1)
    curve = np.linspace(edges[0], edges[-1], 400)

    plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
    for name in names:
        values = errors[name][np.isfinite(errors[name])]
        moments = gaussianity(values)
        outside = int(((values < edges[0]) | (values > edges[-1])).sum())
        description = cases.get(name, name)
        plt.hist(
            values,
            bins=edges,
            histtype="step",
            color=colors[name],
            label=f"{description}: $\\mu$ = {moments['mean']:.2f}, $\\sigma$ = {moments['std']:.2f} px, "
            f"skew {moments['skewness']:.2f}, ex. kurt. {moments['excess_kurtosis']:.1f}"
            + (f" ({outside} off-scale)" if outside else ""),
        )
        density = stats.norm.pdf(curve, moments["mean"], moments["std"]) * len(values) * (edges[1] - edges[0])
        plt.plot(curve, density, "--", color=colors[name], linewidth=0.6)
        plt.axvline(moments["mean"], color=colors[name], linewidth=0.7, linestyle=":")
        print(
            f"{description:38s}{moments['mean']:8.3f}{moments['std']:8.3f}{moments['skewness']:8.2f}"
            f"{moments['excess_kurtosis']:8.2f}"
        )
    plt.axvline(0.0, color="0.6", linewidth=0.6)
    plt.xlim(edges[0], edges[-1])
    plt.title(f"{title} (dashed: Gaussian, same $\\mu$ and $\\sigma$)")
    plt.xlabel(xlabel)
    plt.ylabel("Number of runs")
    plt.legend(fontsize=4, loc="upper left")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_results(summary, output_directory=None, show_plots=False):
    """Error against phase angle and error histograms for the three cases, plus the threshold sweep."""
    rows = summary["rows"]
    if not rows:
        raise ValueError("no samples to plot")
    directory_path = output_directory or os.path.join(current_file_path, "images-ellipsoid-com-cob")
    ifov_arcsec = np.degrees(summary["camera_ifov"]) * 3600

    phases = np.array([row["phase_angle_deg"] for row in rows])
    order = phases.argsort()
    case_colors = dict(zip(cases, (colorList[1], colorList[5], colorList[7], colorList[3], "#00d0ff")))

    plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
    for name, description in cases.items():
        errors = np.array([row[name]["error_arcsec"] for row in rows])
        plt.scatter(phases[order], errors[order], marker=".", s=10, color=case_colors[name], label=description)
    plt.axhline(ifov_arcsec, linewidth=1, linestyle=":", color=colorList[9], label="pixel ifov")
    plt.yscale("log")
    plt.title("CoB prediction error as a function of phase angle")
    plt.xlabel("Phase angle (deg)")
    plt.ylabel("Prediction error (arcsec)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(directory_path, "error-by-phase.png"))

    split = {name: np.array([sunline_split(row, name) for row in rows]) for name in cases}
    for column, label, filename in (
        (0, "along the sunline (px, + sunward)", "correction-errors-hist.png"),
        (1, "across the sunline (px)", "correction-errors-hist-across.png"),
    ):
        print(f"{label:38s}{'mean':>8s}{'sigma':>8s}{'skew':>8s}{'ex.kurt':>8s}")
        error_histogram(
            {name: values[:, column] for name, values in split.items()},
            case_colors,
            f"Measured minus predicted CoB, {label.split(' (')[0]}",
            f"Error {label.split(' ', 3)[-1]}",
            os.path.join(directory_path, filename),
        )

    if summary.get("sweep_thresholds"):
        thresholds = summary["sweep_thresholds"]
        plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
        for name in swept_cases:
            if name not in rows[0]["threshold_sweep"]:
                continue  # runs from before the full model
            errors = np.array([row["threshold_sweep"][name] for row in rows])
            plt.plot(
                thresholds,
                np.nanmedian(errors, axis=0),
                marker=".",
                color=case_colors[name],
                label=f"{cases[name]}, median",
            )
            plt.plot(
                thresholds,
                np.nanpercentile(errors, 95, axis=0),
                linestyle="--",
                color=case_colors[name],
                label=f"{cases[name]}, 95th percentile",
            )
        plt.axvline(summary["lit_threshold"], color="0.6", linewidth=0.8)
        plt.title("Binary CoB prediction error against lit threshold")
        plt.xlabel("Lit threshold (DN)")
        plt.ylabel("Prediction error (px)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(directory_path, "error-by-threshold.png"))

    for name, description in cases.items():
        errors = np.array([row[name]["error_px"] for row in rows])
        print(f"{description:28s} median {np.median(errors):6.3f} px  95% {np.percentile(errors, 95):6.3f} px")

    plot_sunline_split(summary, directory_path)

    if show_plots:
        plt.show()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ellipsoid analytical CoB offset against rendered sphere/ellipsoid")
    parser.add_argument("--samples", type=int, default=200, help="sphere/ellipsoid pairs to render")
    parser.add_argument("--figures", type=int, default=100, help="samples to save a pair figure for")
    parser.add_argument("--axis-sigma", type=float, default=axis_log_sigma, help="lognormal spread on a, b, c")
    parser.add_argument("--threshold-sweep", action="store_true", help="also score the lit threshold")
    parser.add_argument(
        "--range-radii",
        type=float,
        default=default_range_radii,
        help="spacecraft range in body radii; the fov follows so the disk keeps its size in pixels",
    )
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--show", action="store_true", help="show the plots")
    parser.add_argument("--replot", action="store_true", help="only rebuild the figures from the last run")
    args = parser.parse_args()

    if args.replot:
        for path in replot_pairs():
            print(f"Wrote {path}")
        with open(os.path.join(current_file_path, "images-ellipsoid-com-cob", "run.json")) as handle:
            plot_results(json.load(handle), show_plots=args.show)
        raise SystemExit

    run = ellipsoid_com_cob_analysis(
        number_of_samples=args.samples,
        axis_sigma=args.axis_sigma,
        seed=args.seed,
        save_first=args.figures,
        threshold_sweep=args.threshold_sweep,
        range_radii=args.range_radii,
    )
    plot_results(run, show_plots=args.show)
