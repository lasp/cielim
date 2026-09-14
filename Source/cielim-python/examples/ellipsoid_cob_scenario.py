"""
Goal:
    Test whether the centre-of-brightness offset is predictable from the target's shape along the
    sun direction.

    Each sample renders the same scene twice: once as a random triaxial ellipsoid, once as a sphere
    whose radius comes from a selectable rule. Everything else — camera, range, pointing, sun — is
    identical between the two, so the difference in CoB is due to shape alone.

    Plotted is the CoB shift along the sunline against how far the ellipsoid surface sits from the
    reference sphere in that same direction. If the CoB simply follows the sub-solar radius, the
    "sub_solar" rule should drive the shift to zero.

    Fixed for a run: camera, exposure, spacecraft position, body-centred pointing. Randomized: the
    sun direction, the three axis scales, and the ellipsoid attitude. Phase angle is not drawn — it
    follows from where the sun lands.
"""

import csv
import json
import os

import cv2
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from scipy.spatial.transform import Rotation

import cielim
from cielim.utils import image_comparison_toolkit as image_comparison
from cielim.utils import plot_style as ps
from cielim.utils import rigid_body_kinematics as rbk

current_file_path = os.path.dirname(__file__)

target_name = "ellipsoid"
central_body_index = 1

base_radius = 25e3  # metres; the axis scales multiply this
axis_log_sigma = 0.2  # lognormal spread on a, b, c
axis_sigma_span = 4.0  # sizing headroom: the largest axis the frame must still hold
frame_fill = 0.6  # that largest ellipsoid spans this fraction of the smaller field of view

astronomical_unit = 1.495978707e11

# Above this many DN a pixel counts as lit. Low on purpose: the geometric centroid wants the whole
# illuminated silhouette down to the terminator, not just the bright sub-solar cap.
lit_threshold = 5

# Which sphere the ellipsoid is compared against. Every sample records all three, so a run can be
# re-plotted under any rule; only the rule named here changes the sphere that is actually rendered.
reference_radius_rules = {
    "arithmetic": lambda axes, r_sub: float(np.mean(axes)),
    "volume": lambda axes, r_sub: float(np.cbrt(np.prod(axes))),
    "sub_solar": lambda axes, r_sub: float(r_sub),
}


def ellipsoid_radius(direction, semi_axes):
    """
    Distance from an ellipsoid's centre to its surface along ``direction``.

    Args:
        direction (ndarray): Direction in the ellipsoid's principal frame; need not be normalized.
        semi_axes (ndarray): The three semi-axis lengths, in the same units as the result.

    Returns:
        float: Distance from centre to surface along that direction.
    """
    unit = np.asarray(direction, float) / np.linalg.norm(direction)
    return float(1.0 / np.linalg.norm(unit / np.asarray(semi_axes, float)))


def centroid(image, threshold=lit_threshold, binary=False, gamma=2.2):
    """
    Sub-pixel centroid of the lit pixels, radiance-weighted or unweighted.

    The photometric branch linearizes first: the frame arrives gamma encoded, and weighting those
    encoded values is not a radiance centroid. Weighting the 8-bit values directly puts the result
    19 px off the engine's own CoB on a 400 px disk, while linearizing agrees to 0.08 px.

    ``binary`` is the geometric case: every lit pixel counts the same, so the Lambertian falloff
    drops out and the result is the centroid of the illuminated projected area. Not
    image_comparison_toolkit.get_cob_and_bbox, which rounds to whole pixels and thresholds at a
    quarter of the peak — this measurement can be a fraction of a pixel.

    Args:
        image (ndarray): Grayscale or BGR frame.
        threshold (int): A pixel counts as lit above this level, in encoded DN.
        binary (bool): Weight every lit pixel equally instead of by radiance.
        gamma (float): Encoding gamma to undo; pass the camera's own sensorModel.gamma.

    Returns:
        tuple[float, float] | None: (x, y) in pixels, or None when nothing is lit.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = gray.astype(float)
    lit = gray > threshold
    if not lit.any():
        return None

    weights = lit.astype(float) if binary else np.where(lit, (gray / 255.0) ** gamma, 0.0)
    total = weights.sum()
    rows, columns = np.indices(gray.shape)
    return float((weights * columns).sum() / total), float((weights * rows).sum() / total)


def lit_extent(image, threshold=lit_threshold):
    """``(width, height, x0, y0)`` in pixels of the lit region's bounding box, or None if unlit."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    rows, columns = np.nonzero(gray > threshold)
    if not len(columns):
        return None
    return (
        int(columns.max() - columns.min() + 1),
        int(rows.max() - rows.min() + 1),
        int(columns.min()),
        int(rows.min()),
    )


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
    """Pixel a world point lands on. project_to_pixel projects the origin, so offset the camera."""
    return image_comparison.project_to_pixel(
        np.asarray(spacecraft_position, float) - np.asarray(world_point, float),
        world_to_camera,
        fov,
        resolution,
    )


def sunline_pixel_direction(sun_heading, spacecraft_position, world_to_camera, fov, resolution):
    """
    Unit vector in pixel space pointing from the body centre toward the sun.

    Derived by projecting two world points rather than by rotating a vector, so the pixel axis signs
    come from the same projection the render uses and none of them have to be assumed here.
    """
    step = 0.05 * np.linalg.norm(spacecraft_position)
    centre = np.array(project((0, 0, 0), spacecraft_position, world_to_camera, fov, resolution))
    toward = np.array(
        project(step * np.asarray(sun_heading, float), spacecraft_position, world_to_camera, fov, resolution)
    )
    direction = toward - centre
    return direction / np.linalg.norm(direction)


def scene_setup() -> cielim.Scene:
    """
    Camera and one body slot. Nothing randomized is set here; the sampler edits the returned scene.

    The range is fixed so that even the largest ellipsoid the axis distribution is likely to produce
    still fits inside frame_fill of the smaller field of view — a full, well-resolved disk is what
    gives the CoB shift the resolution to be measured at all.
    """
    scene = cielim.Scene()

    fov = (20 * np.pi / 180, 15 * np.pi / 180)
    scene.set_lens_params(fov=fov)
    scene.set_sensor_params(resolution=(2000, 1500), exposure=5e-4)
    scene.set_camera_params(grayscale=True)

    largest_semi_axis = base_radius * np.exp(axis_sigma_span * axis_log_sigma)
    camera_range = largest_semi_axis / np.tan(frame_fill * min(fov) / 2)

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
    blank, the same quirk tests/test_corruptions.py guards against. Every sample re-inits to pick up
    the new shape, so without this any sample can silently lose a frame — it cost one intermittently.
    """
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    connector.request_image_for_camera_id(1)
    image, engine_cob, coverage = connector.request_image_for_camera_id(1)
    return image, engine_cob, coverage


def validate_scaling_frame(connector, scene, output_directory=None):
    """
    Establish which frame the principal-axis distortion is applied in, before trusting any analysis.

    mesh_distortions becomes SetActorScale3D on the actor while mesh_attitude becomes a relative
    rotation on the child mesh component, so whether the ellipsoid's long axis follows the mesh
    attitude is a property of how Unreal composes the two, not something to assume. Renders a 2:1:1
    ellipsoid at identity and again rolled 90 degrees about the boresight, and reports the lit
    region's width:height both times. If the mesh attitude orients the scaling, the ratio inverts.

    Returns:
        dict: Measured extents and the ratios, for the caller to assert on or print.
    """
    scene.set_celestial_body_params(central_body_index, position=(0.0, 0.0, 0.0))
    scene.set_celestial_body_params(0, position=(0.0, 0.0, -astronomical_unit))  # sun behind camera

    results = {}
    for label, mrp in (("identity", (0.0, 0.0, 0.0)), ("roll_90", tuple(rbk.dcm_to_mrp(_roll_z(np.pi / 2))))):
        scene.set_celestial_body_params(
            central_body_index, mesh_distortions=(2.0, 1.0, 1.0), mesh_attitude=mrp, mesh_radius=base_radius
        )
        image, _, _ = _render(connector, scene)
        extent = lit_extent(image)
        results[label] = {
            "width": extent[0] if extent else 0,
            "height": extent[1] if extent else 0,
            "ratio": (extent[0] / extent[1]) if extent and extent[1] else 0.0,
        }
        if output_directory:
            cv2.imwrite(os.path.join(output_directory, f"validate_{label}.png"), image)

    results["mesh_attitude_orients_scaling"] = bool(
        results["identity"]["ratio"] > 1.3 and results["roll_90"]["ratio"] < 0.8
    )
    return results


def _roll_z(angle):
    """Rotation by ``angle`` about z, as a DCM."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])


# Confirmed by validate_scaling_frame: a 2:1:1 body renders 802x404 at identity and 402x806 rolled
# 90 degrees about the boresight, so mesh_attitude does orient the scaling axes and the sub-solar
# direction has to be rotated into the principal frame by that same attitude.
def sub_solar_radius(sun_heading, mesh_attitude_mrp, semi_axes):
    """Distance from centre to surface at the sub-solar point, for a body at the world origin."""
    principal = rbk.mrp_to_dcm(np.asarray(mesh_attitude_mrp, float)) @ np.asarray(sun_heading, float)
    return ellipsoid_radius(principal, semi_axes)


def ellipsoid_cob_scenario(
    number_of_samples: int = 200,
    reference_rule: str = "arithmetic",
    axis_sigma: float = axis_log_sigma,
    seed: int | None = None,
    save_first: int = 5,
    cob_mode: str = "geometric",
    output_directory: str | None = None,
) -> dict:
    """
    Render matched ellipsoid/sphere pairs and record how far the CoB moves along the sunline.

    Args:
        number_of_samples (int): Number of ellipsoid/sphere pairs to render.
        reference_rule (str): Which sphere to compare against, see reference_radius_rules. All three
            candidate radii are recorded regardless, so a run can be re-plotted under any of them.
        axis_sigma (float): Lognormal spread on the axis scales. Zero makes every body a sphere,
            which is the degenerate self-check: the shift must come out at ~0.
        seed (int, optional): Seed for the draws, so a run can be repeated under another rule.
        save_first (int): Write the pair figure, renders and lit masks for this many samples.
        cob_mode (str): Which CoB the pair figure marks and the scatter defaults to. Both modes are
            recorded either way, so the other one needs no re-render.
        output_directory (str, optional): Defaults to examples/images-ellipsoid-cob/.

    Returns:
        dict: The per-sample rows plus the run's settings.
    """
    if reference_rule not in reference_radius_rules:
        raise ValueError(f"unknown rule {reference_rule!r}; expected one of {', '.join(reference_radius_rules)}")

    directory_path = output_directory or os.path.join(current_file_path, "images-ellipsoid-cob")
    os.makedirs(directory_path, exist_ok=True)

    rng = np.random.default_rng(seed)
    scene = scene_setup()
    world_to_camera, fov, resolution = camera_frame(scene)
    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    gamma = scene.get_scene().camera.sensorModel.gamma or 2.2
    camera_range = float(np.linalg.norm(spacecraft_position))

    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())

    rows, skipped = [], 0
    for idx in range(number_of_samples):
        axes = np.exp(rng.normal(0.0, axis_sigma, size=3)) if axis_sigma > 0 else np.ones(3)
        attitude = rbk.dcm_to_mrp(Rotation.random(random_state=rng.integers(2**31)).as_matrix())

        sun_heading = rng.normal(size=3)
        sun_heading /= np.linalg.norm(sun_heading)
        scene.set_celestial_body_params(0, position=tuple(astronomical_unit * sun_heading))

        semi_axes = base_radius * axes
        r_sub = sub_solar_radius(sun_heading, attitude, semi_axes)
        candidate_radii = {
            name: base_radius * rule(axes, r_sub / base_radius) for name, rule in reference_radius_rules.items()
        }
        r_reference = candidate_radii[reference_rule]

        scene.set_celestial_body_params(
            central_body_index, mesh_radius=base_radius, mesh_distortions=tuple(axes), mesh_attitude=tuple(attitude)
        )
        ellipsoid_image, engine_cob_ellipsoid, _ = _render(connector, scene)

        scene.set_celestial_body_params(
            central_body_index, mesh_radius=r_reference, mesh_distortions=(1.0, 1.0, 1.0), mesh_attitude=(0.0, 0.0, 0.0)
        )
        sphere_image, engine_cob_sphere, _ = _render(connector, scene)

        extents = [lit_extent(ellipsoid_image), lit_extent(sphere_image)]
        if any(e is None for e in extents) or _touches_edge(extents, resolution):
            skipped += 1
            continue

        sunline = sunline_pixel_direction(sun_heading, spacecraft_position, world_to_camera, fov, resolution)
        shifts = {}
        for mode, binary in (("photometric", False), ("geometric", True)):
            cob_ellipsoid = centroid(ellipsoid_image, binary=binary, gamma=gamma)
            cob_sphere = centroid(sphere_image, binary=binary, gamma=gamma)
            if cob_ellipsoid is None or cob_sphere is None:
                break
            shifts[mode] = {
                "ellipsoid": list(cob_ellipsoid),
                "sphere": list(cob_sphere),
                "along_sunline_px": float(np.dot(np.array(cob_ellipsoid) - np.array(cob_sphere), sunline)),
            }
        if len(shifts) != 2:
            skipped += 1
            continue

        # Exact rather than small-angle: project a point one reference radius off the boresight.
        perpendicular = world_to_camera.T @ np.array([r_reference, 0.0, 0.0])
        centre_px = np.array(project((0, 0, 0), spacecraft_position, world_to_camera, fov, resolution))
        apparent_radius_px = float(
            np.linalg.norm(
                np.array(project(perpendicular, spacecraft_position, world_to_camera, fov, resolution)) - centre_px
            )
        )

        rows.append(
            {
                "sample": idx,
                "axes": axes.tolist(),
                "mesh_attitude_mrp": np.asarray(attitude).tolist(),
                "sun_heading_N": sun_heading.tolist(),
                "phase_angle_deg": float(
                    np.degrees(np.arccos(np.clip(np.dot(sun_heading, spacecraft_position / camera_range), -1.0, 1.0)))
                ),
                "r_sub_solar_m": r_sub,
                "reference_rule": reference_rule,
                "r_reference_m": r_reference,
                "candidate_radii_m": candidate_radii,
                "apparent_radius_px": apparent_radius_px,
                "sunline_px": sunline.tolist(),
                "centre_of_mass_px": centre_px.tolist(),
                "engine_cob_ellipsoid": list(engine_cob_ellipsoid),
                "engine_cob_sphere": list(engine_cob_sphere),
                "scale_factor": r_sub / r_reference,
                **{f"shift_{mode}": data for mode, data in shifts.items()},
            }
        )

        if idx < save_first:
            plot_sample_pair(
                ellipsoid_image,
                sphere_image,
                rows[-1],
                os.path.join(directory_path, f"sample{idx:03d}_pair.png"),
                cob_mode=cob_mode,
            )
            for label, frame in (("ellipsoid", ellipsoid_image), ("sphere", sphere_image)):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
                cv2.imwrite(os.path.join(directory_path, f"sample{idx:03d}_{label}.png"), frame)
                cv2.imwrite(
                    os.path.join(directory_path, f"sample{idx:03d}_{label}_mask.png"),
                    ((gray > lit_threshold) * 255).astype(np.uint8),
                )

        print(
            f"[{idx:03d}] axes {axes[0]:.2f},{axes[1]:.2f},{axes[2]:.2f}  "
            f"phase {rows[-1]['phase_angle_deg']:6.2f} deg  scale {rows[-1]['scale_factor']:.3f}  "
            f"shift photo {shifts['photometric']['along_sunline_px']:+7.3f} px  "
            f"geom {shifts['geometric']['along_sunline_px']:+7.3f} px"
        )

    connector.disconnect()
    launcher.terminate()

    summary = {
        "reference_rule": reference_rule,
        "number_of_samples": number_of_samples,
        "kept": len(rows),
        "skipped": skipped,
        "axis_sigma": axis_sigma,
        "seed": seed,
        "base_radius_m": base_radius,
        "camera_range_m": camera_range,
        "lit_threshold": lit_threshold,
        "gamma": gamma,
        "cob_mode": cob_mode,
        "rows": rows,
    }
    _write_run(summary, directory_path)
    print(f"Kept {len(rows)} of {number_of_samples} samples ({skipped} skipped) -> {directory_path}")
    return summary


def _touches_edge(extents, resolution, margin=8):
    """True if either lit region comes within ``margin`` pixels of the frame edge."""
    width, height = resolution
    for extent in extents:
        w, h, x0, y0 = extent
        if x0 < margin or y0 < margin or x0 + w > width - margin or y0 + h > height - margin:
            return True
    return False


def _write_run(summary, directory_path):
    """Write the run as JSON (everything) and CSV (the columns the plot needs)."""
    stem = f"cob_shift_{summary['reference_rule']}"
    with open(os.path.join(directory_path, f"{stem}.json"), "w") as handle:
        json.dump(summary, handle, indent=2)

    columns = ["sample", "phase_angle_deg", "scale_factor", "apparent_radius_px", "photometric_px", "geometric_px"]
    with open(os.path.join(directory_path, f"{stem}.csv"), "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in summary["rows"]:
            writer.writerow(
                [
                    row["sample"],
                    f"{row['phase_angle_deg']:.4f}",
                    f"{row['scale_factor']:.6f}",
                    f"{row['apparent_radius_px']:.4f}",
                    f"{row['shift_photometric']['along_sunline_px']:.6f}",
                    f"{row['shift_geometric']['along_sunline_px']:.6f}",
                ]
            )


def zoom_half_width(shift_px, minimum=15.0):
    """Half-width of the CoB zoom window: enough to hold the shift with context around it."""
    return float(max(3.0 * abs(shift_px), minimum))


def plot_sample_pair(ellipsoid_image, sphere_image, row, output_path, cob_mode="geometric"):
    """
    Ellipsoid and sphere side by side, plus a zoom on the CoB pair, for one sample.

    The two wide panels share one crop window so they are comparable pixel for pixel, and the axes
    stay in original pixel coordinates (the ``extent`` idiom from
    image_comparison_toolkit.plot_point_source_pair) so every marker plots at its true position.

    The zoom panel is the point of the figure: the shift vector and the projected sunline are drawn
    from the same origin at the same length, so they overlap exactly when the CoB slides along the
    sun direction and the alignment is read off rather than computed.

    Args:
        ellipsoid_image (ndarray): The ellipsoid render.
        sphere_image (ndarray): The matched sphere render.
        row (dict): One entry of the run's ``rows``.
        output_path (str): Where to write the figure.
        cob_mode (str): Which recorded CoB to mark, "geometric" or "photometric".

    Returns:
        str: The path written.
    """
    ps.apply_showcase_style()
    frames = {}
    for label, image in (("ellipsoid", ellipsoid_image), ("sphere", sphere_image)):
        frames[label] = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    shift = row[f"shift_{cob_mode}"]
    cob = {label: np.array(shift[label], float) for label in frames}
    centre_of_mass = np.array(row["centre_of_mass_px"], float)
    sunline = np.array(row["sunline_px"], float)
    displacement = cob["ellipsoid"] - cob["sphere"]

    height, width = frames["ellipsoid"].shape
    boxes = [lit_extent(frame) for frame in frames.values()]
    pad = 25
    x1 = max(min(b[2] for b in boxes) - pad, 0)
    y1 = max(min(b[3] for b in boxes) - pad, 0)
    x2 = min(max(b[2] + b[0] for b in boxes) + pad, width)
    y2 = min(max(b[3] + b[1] for b in boxes) + pad, height)

    # Extra height for the legend band below the panels; in-axes it sits on top of the body.
    strip_width, strip_height = ps.figsize_strip(3)
    figure, axes = plt.subplots(1, 3, figsize=(strip_width, strip_height + 0.4))
    for ax, label in zip(axes[:2], ("ellipsoid", "sphere")):
        ax.imshow(
            frames[label][y1:y2, x1:x2],
            cmap=ps.scene_cmap,
            extent=[x1 - 0.5, x2 - 0.5, y2 - 0.5, y1 - 0.5],
            interpolation="nearest",
            vmin=0,
            vmax=255,
        )
        _mark(ax, cob, centre_of_mass)
        _arrow(ax, centre_of_mass, 0.35 * (x2 - x1) * sunline, "#00d0ff")
        ax.set_title(label)

    half = zoom_half_width(np.linalg.norm(displacement))
    midpoint = 0.5 * (cob["ellipsoid"] + cob["sphere"])
    zoom = axes[2]
    zx1, zx2 = midpoint[0] - half, midpoint[0] + half
    zy1, zy2 = midpoint[1] - half, midpoint[1] + half
    zoom.imshow(
        frames["sphere"][max(int(zy1), 0) : int(zy2), max(int(zx1), 0) : int(zx2)],
        cmap=ps.scene_cmap,
        extent=[max(int(zx1), 0) - 0.5, int(zx2) - 0.5, int(zy2) - 0.5, max(int(zy1), 0) - 0.5],
        interpolation="nearest",
        vmin=0,
        vmax=255,
    )
    # Both arrows leave the sphere CoB at the same length: they coincide when the slide is along the
    # sunline, so the figure answers the alignment question by eye.
    _arrow(zoom, cob["sphere"], displacement, ps.series_colors[1])
    _arrow(zoom, cob["sphere"], np.linalg.norm(displacement) * sunline, "#00d0ff")
    _mark(zoom, cob, centre_of_mass)
    zoom.set_xlim(zx1, zx2)
    zoom.set_ylim(zy2, zy1)
    zoom.set_title(f"zoom: shift {np.linalg.norm(displacement):.1f} px")

    for ax in axes:
        ax.set_xlabel("x (px)")
    axes[0].set_ylabel("y (px)")
    figure.suptitle(
        f"sample {row['sample']}  {cob_mode} CoB  phase {row['phase_angle_deg']:.1f} deg  "
        f"scale {row['scale_factor']:.3f}  along sunline {shift['along_sunline_px']:+.2f} px"
    )
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(Line2D([], [], color="#00d0ff", linewidth=1.4))
    labels.append("sunline")
    handles.append(Line2D([], [], color=ps.series_colors[1], linewidth=1.4))
    labels.append("shift (zoom)")
    figure.legend(handles, labels, loc="lower center", ncol=5, frameon=False)
    figure.tight_layout(rect=(0, 0.09, 1, 1))
    ps.save_figure(figure, output_path)
    plt.close(figure)
    return output_path


def _mark(ax, cob, centre_of_mass):
    """Centre of mass and the two centres of brightness, same styling on every panel."""
    ax.plot(*centre_of_mass, "o", mfc="none", mec="#00d0ff", markersize=9, markeredgewidth=1.2, label="CoM")
    ax.plot(*cob["sphere"], "+", color=ps.series_colors[0], markersize=11, markeredgewidth=1.6, label="sphere CoB")
    ax.plot(*cob["ellipsoid"], "x", color=ps.series_colors[1], markersize=9, markeredgewidth=1.6, label="ellipsoid CoB")


def _arrow(ax, origin, vector, color):
    """Arrow from ``origin`` along ``vector``, in pixel coordinates."""
    ax.annotate(
        "",
        xy=(origin[0] + vector[0], origin[1] + vector[1]),
        xytext=(origin[0], origin[1]),
        arrowprops=dict(arrowstyle="->", color=color, linewidth=1.4, shrinkA=0, shrinkB=0),
    )


def plot_cob_shift(summary, cob_mode="geometric", output_path=None):
    """
    Scatter the normalized CoB shift against the sub-solar scale factor, coloured by phase angle.

    Both axes are dimensionless: x is how far the sub-solar surface sits from the reference sphere,
    y is the shift in units of the sphere's apparent radius, so the slope means the same thing at
    any range.
    """
    rows = summary["rows"]
    if not rows:
        raise ValueError("no samples to plot")

    x = np.array([row["scale_factor"] for row in rows])
    y = np.array([row[f"shift_{cob_mode}"]["along_sunline_px"] / row["apparent_radius_px"] for row in rows])
    phase = np.array([row["phase_angle_deg"] for row in rows])

    ps.apply_showcase_style()
    figure, axes = plt.subplots(figsize=ps.figsize_half(title_lines=1))
    points = axes.scatter(x, y, c=phase, cmap="inferno", s=14, edgecolor="none")
    figure.colorbar(points, ax=axes, label="phase angle (deg)")

    axes.axhline(0.0, color="0.6", linewidth=0.6)
    axes.axvline(1.0, color="0.6", linewidth=0.6)
    axes.set_xlabel(f"sub-solar radius / {summary['reference_rule']} sphere radius")
    axes.set_ylabel("CoB shift along sunline / apparent radius")
    axes.set_title(f"{cob_mode} CoB, {summary['reference_rule']} sphere")
    figure.tight_layout()

    output_path = output_path or os.path.join(
        current_file_path, "images-ellipsoid-cob", f"cob_shift_{summary['reference_rule']}_{cob_mode}.pdf"
    )
    ps.save_figure(figure, output_path)
    plt.close(figure)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ellipsoid vs sphere centre-of-brightness sensitivity")
    parser.add_argument("--rule", default="arithmetic", choices=sorted(reference_radius_rules), help="reference sphere")
    parser.add_argument("--samples", type=int, default=200, help="ellipsoid/sphere pairs to render")
    parser.add_argument("--figures", type=int, default=5, help="samples to save a pair figure for")
    parser.add_argument("--cob-mode", default="geometric", choices=("geometric", "photometric"), help="CoB to mark")
    parser.add_argument("--seed", type=int, default=20260914)
    args = parser.parse_args()

    run = ellipsoid_cob_scenario(
        number_of_samples=args.samples,
        reference_rule=args.rule,
        seed=args.seed,
        save_first=args.figures,
        cob_mode=args.cob_mode,
    )
    for mode in ("geometric", "photometric"):
        print(f"Wrote {plot_cob_shift(run, mode)}")
