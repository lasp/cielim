"""
Goal:
    Render a controlled, repeatable sweep of apparent object size around a closed Keplerian orbit.

    The orbit is parameterized by the *apparent angular radius of the central body at apoapse*
    rather than by a distance in meters, which pins the geometry in the units that actually drive
    the cielim render cost (angular size relative to the field of view). The ratio of the radius of
    periapse to the radius of apoapse then sets how far into "the body overflows the frame"
    territory the orbit dives.

    Images are captured evenly spaced in time along one full orbit, starting at apoapse, and the
    per-frame render time is reported so cost can be plotted against apparent size.

    Pointing is nadir (boresight on the body center), automatically switching to horizon pointing
    (boresight offset onto the lit limb) once the body grows larger than the field of view.

    The central body, its gravitational parameter and radius, and the camera are all read off the
    scene: scene_setup() builds the skeleton and everything physical is edited in __main__.
"""

import csv
import os
import time

import cv2
import imageio
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.ticker import MaxNLocator

import cielim
from cielim.utils import orbital_motion
from cielim.utils import plot_style
from cielim.utils import rigid_body_kinematics as rbk
from cielim.utils import scene_dynamics
from cielim.utils.qe_curve_fit import CONST_AU

current_file_path = os.path.dirname(__file__)

# Index of the central body in the scene. Index 0 is the sun, auto-created by Scene.__init__.
CENTRAL_BODY_INDEX = 1


def _true_anomaly_from_mean(mean_anomaly: float, eccentricity: float) -> float:
    """
    Solve Kepler's equation M = E - e sin(E) for the true anomaly.

    Newton iteration on the eccentric anomaly. Used instead of orbital_motion.propagate_cartesian
    because that propagator is RK4 with fixed one-second steps: a single inter-frame gap on a small
    body orbit is ~1e5 pure-python steps, which would both be slow and pollute the render timing
    this scenario exists to measure.

    Args:
        mean_anomaly (float): Mean anomaly in radians.
        eccentricity (float): Orbit eccentricity (dimensionless, < 1).

    Returns:
        float: The true anomaly in radians.
    """
    eccentric_anomaly = mean_anomaly + eccentricity * np.sin(mean_anomaly)

    for _ in range(50):
        residual = eccentric_anomaly - eccentricity * np.sin(eccentric_anomaly) - mean_anomaly
        derivative = 1.0 - eccentricity * np.cos(eccentric_anomaly)
        step = residual / derivative
        eccentric_anomaly -= step
        if abs(step) < 1e-12:
            break

    return 2.0 * np.arctan2(
        np.sqrt(1.0 + eccentricity) * np.sin(eccentric_anomaly / 2.0),
        np.sqrt(1.0 - eccentricity) * np.cos(eccentric_anomaly / 2.0),
    )


def _point_at_body(scene: cielim.Scene, offset_angle: float) -> None:
    """
    Point the camera at the central body, optionally offset onto the illuminated limb.

    The offset is applied by rotating the primary heading before handing it to
    rigid_body_kinematics.body_to_inertial_for_pointing, which is the same machinery
    scene_dynamics.look_at_target uses. With a zero offset this is identical to look_at_target on a
    body sitting at the inertial origin.

    Args:
        scene (Scene): The Scene object to update.
        offset_angle (float): Angle in radians to tilt the boresight off nadir, toward the lit limb.
    """
    message = scene.get_scene()

    spacecraft_position = np.array(message.spacecraft.position)
    spacecraft_velocity = np.array(message.spacecraft.velocity)
    camera_position = np.array(message.camera.cameraPositionInBody)
    camera_orientation = np.array(message.camera.bodyFrameToCameraMrp)
    sun_position = np.array(message.celestialBodies[0].position)

    # Nadir: the central body sits at the inertial origin, so the body-relative camera position
    # points away from it.
    nadir = -(spacecraft_position - camera_position)
    nadir /= np.linalg.norm(nadir)

    # The relative velocity is the secondary heading, matching look_at_target.
    secondary = -spacecraft_velocity

    primary = nadir
    if offset_angle > 0.0:
        to_sun = sun_position - spacecraft_position
        to_sun /= np.linalg.norm(to_sun)

        # Component of the sun direction perpendicular to nadir: the in-frame direction of the lit
        # limb. Degenerate at a phase angle of 0 or 180 degrees, where any limb direction is as good
        # as another, so fall back to the velocity-perpendicular direction.
        limb_direction = to_sun - np.dot(to_sun, nadir) * nadir
        if np.linalg.norm(limb_direction) < 1e-8:
            limb_direction = secondary - np.dot(secondary, nadir) * nadir
        limb_direction /= np.linalg.norm(limb_direction)

        primary = np.cos(offset_angle) * nadir + np.sin(offset_angle) * limb_direction

    BN = rbk.body_to_inertial_for_pointing(primary, secondary, rbk.mrp_to_dcm(camera_orientation))

    scene.set_spacecraft_params(attitude=tuple(rbk.dcm_to_mrp(BN)))


def _read_timing_csv(path: str) -> tuple[np.ndarray, dict]:
    """
    Read a per-image timing column, and any context columns, out of a CSV.

    Deliberately liberal about the layout, so a timing log from another renderer can be dropped in
    without reshaping it. Accepts a file with or without a header row. With a header, the column
    whose name mentions time / duration / render / elapsed / second is the timing; without one, a
    single column is the timings and a wider file is assumed to be (index, timing).

    Timing values are seconds per image, unless the column name mentions hz / fps / rate, in which
    case they are read as a rate and inverted.

    A headed file may also carry a phase angle column, picked up by name so that a CSV can be plotted
    on its own with the same overlay the scenario produces: a column mentioning "phase" is read as
    the phase angle in degrees.

    Args:
        path (str): Path to the CSV file.

    Returns:
        tuple[ndarray, dict]: Per-image render times in seconds, and a context dict that may hold a
        "phase_angle" array in degrees.
    """
    with open(path, newline="") as handle:
        rows = [row for row in csv.reader(handle) if row and any(field.strip() for field in row)]

    if not rows:
        raise ValueError(f"No data found in timing CSV {path}.")

    def is_numeric(row):
        try:
            [float(field) for field in row]
            return True
        except ValueError:
            return False

    header = None if is_numeric(rows[0]) else [field.strip().lower() for field in rows[0]]
    data_rows = rows if header is None else rows[1:]

    def column_values(index):
        return np.array([float(row[index]) for row in data_rows])

    if header is None:
        timing_column = 0 if len(rows[0]) == 1 else len(rows[0]) - 1
        name = ""
    else:
        keywords = ("time", "duration", "render", "elapsed", "second", "hz", "fps", "rate")
        matches = [i for i, field in enumerate(header) if any(key in field for key in keywords)]
        timing_column = matches[0] if matches else (0 if len(header) == 1 else len(header) - 1)
        name = header[timing_column]

    values = column_values(timing_column)
    if any(key in name for key in ("hz", "fps", "rate")):
        values = 1.0 / values

    context = {}
    if header is not None:
        found = [i for i, field in enumerate(header) if i != timing_column and "phase" in field]
        if found:
            context["phase_angle"] = column_values(found[0])

    return values, context


# The phase angle overlay is deliberately recessive: a thin muted line drawn behind the rate curves
# at low alpha, so it gives the timing something to be read against without competing with it. Its
# axis and label carry the same color, so the pairing needs no legend entry.
PHASE_ALPHA = 0.55
PHASE_COLOR = "#5b7f95"


def _overlay_phase_angle(axes, phase_angle=None) -> None:
    """
    Overlay the phase angle on a render timing plot, as faint background context.

    It takes the right-hand axis, tinted to match its curve, and sits behind the rate data.

    Args:
        axes (Axes): The rate axes to overlay onto.
        phase_angle (ndarray, optional): Phase angle per image, in degrees.
    """
    if phase_angle is None or not len(phase_angle):
        return

    values = np.asarray(phase_angle, dtype=float)

    # The rate axes must be transparent and on top for the overlay to sit behind it.
    axes.set_zorder(3)
    axes.patch.set_visible(False)

    phase_axes = axes.twinx()
    phase_axes.set_zorder(1)
    phase_axes.patch.set_visible(False)

    phase_axes.plot(
        np.arange(len(values)),
        values,
        color=PHASE_COLOR,
        alpha=PHASE_ALPHA,
        linewidth=1.2,
        zorder=1,
    )

    phase_axes.set_ylabel("Phase angle [deg]", color=PHASE_COLOR, alpha=0.85)
    phase_axes.tick_params(axis="y", colors=PHASE_COLOR)
    for tick_label in phase_axes.get_yticklabels():
        tick_label.set_alpha(0.85)
    phase_axes.set_ylim(bottom=0)
    phase_axes.spines["top"].set_visible(False)
    phase_axes.spines["right"].set_linewidth(0.6)
    phase_axes.spines["right"].set_color(PHASE_COLOR)
    phase_axes.spines["right"].set_alpha(PHASE_ALPHA)


def plot_render_timing(
    render_times: np.ndarray | None = None,
    csv_path: str | None = None,
    csv_label: str | None = None,
    label: str = "cielim",
    phase_angle: np.ndarray | None = None,
    output_path: str | None = None,
    show: bool = False,
) -> str:
    """
    Plot the render rate for each image in Hertz, with the phase angle overlaid on the right axis.

    The phase angle is context, not a second measurement to compare against: it is drawn faint and
    behind the rate curves so it gives the timing something to be read against without competing
    with it.

    At least one of render_times and csv_path must be given; passing only csv_path plots the CSV on
    its own, without running or referring to a scenario.

    Args:
        render_times (ndarray, optional): Per-image render times in seconds, as returned in the
            scenario summary under "render_times". Omit to plot a CSV on its own.
        csv_path (str, optional): CSV holding a per-image timing, plotted alongside render_times or
            on its own. See _read_timing_csv for the accepted layouts.
        csv_label (str, optional): Legend label for the CSV series. Defaults to the file stem.
        label (str): Legend label for the rendered timings.
        phase_angle (ndarray, optional): Per-image phase angle in degrees, from the scenario summary
            under "phase_angles". Falls back to a matching CSV column.
        output_path (str, optional): Where to write the PNG. Defaults to
            examples/images-speed-test/render_timing.png.
        show (bool): Whether to show the figure interactively.

    Returns:
        str: The path the figure was written to.
    """
    if render_times is None and csv_path is None:
        raise ValueError("Nothing to plot: pass render_times, csv_path, or both.")

    plot_style.apply_showcase_style()

    series = []
    if render_times is not None:
        series.append((label, np.asarray(render_times, dtype=float)))

    if csv_path is not None:
        csv_times, csv_context = _read_timing_csv(csv_path)
        series.append((csv_label or os.path.splitext(os.path.basename(csv_path))[0], csv_times))
        # An explicit argument wins; the CSV only fills in context that was not supplied.
        if phase_angle is None:
            phase_angle = csv_context.get("phase_angle")

    figure, axes = plt.subplots(figsize=plot_style.figsize_single())
    means = []

    for (series_label, times), color in zip(series, plot_style.SERIES_COLORS):
        rate = 1.0 / times
        indices = np.arange(len(rate))
        mean_rate = rate.mean()

        legend_label = f"{series_label} (mean {mean_rate:.2f} Hz)" if len(series) > 1 else series_label
        # Per-point markers turn into a solid blob on a long run, so drop them past a readable count.
        marker = "o" if len(rate) <= 60 else None
        axes.plot(
            indices,
            rate,
            color=color,
            linewidth=1.8,
            marker=marker,
            markersize=4,
            label=legend_label,
            zorder=3,
        )

        # A reference level, not a gridline, so it is drawn dashed on purpose. It carries no inline
        # label: the mean rides in the legend for two series and in the title for one, which keeps
        # it off a curve that hugs its own mean on a long run.
        axes.axhline(mean_rate, color=color, linewidth=1.0, linestyle="--", alpha=0.7, zorder=2)
        means.append(mean_rate)

    axes.set_xlabel("Image index")
    axes.set_ylabel("Render rate [Hz]")
    axes.set_xlim(-0.5, max(len(times) for _, times in series) - 0.5)
    axes.margins(x=0.02)

    # Padded around the data rather than resting on a zero baseline: the rates sit in a narrow band
    # and a zero baseline would flatten the run-to-run structure this plot exists to show.
    all_rates = np.concatenate([1.0 / np.asarray(times, dtype=float) for _, times in series])
    axes.set_ylim(0.92 * all_rates.min(), 1.06 * all_rates.max())

    _overlay_phase_angle(axes, phase_angle)

    axes.xaxis.set_major_locator(MaxNLocator(integer=True))
    axes.grid(True, linewidth=0.5, color="0.85", alpha=0.8)
    axes.set_axisbelow(True)
    axes.spines["top"].set_visible(False)
    for side in ("left", "bottom", "right"):
        axes.spines[side].set_linewidth(0.6)
        axes.spines[side].set_color("0.6")

    if len(series) > 1:
        # The phase overlay lives on a twin axes, which matplotlib's "best" placement cannot see, so
        # the legend is backed with the surface color instead of relying on landing somewhere clear.
        axes.legend(loc="best", frameon=True, facecolor="white", edgecolor="none", framealpha=0.85)
    else:
        axes.set_title(f"{series[0][0]} render rate per image (mean {means[0]:.2f} Hz)")

    if output_path is None:
        output_path = os.path.join(current_file_path, "images-speed-test", "render_timing.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    figure.savefig(output_path, dpi=plot_style.SAVE_DPI, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(figure)

    print(f"Saved render timing plot -> {output_path}")

    return output_path


def scene_setup() -> cielim.Scene:
    """
    Build the scene skeleton: a grayscale camera and one central body slot at the inertial origin.

    Nothing physical is set here. The central body (name, shape model, radius, albedo), its
    gravitational parameter, and the camera (field of view, resolution, exposure) are all edited on
    the returned scene by the caller, see __main__.
    """
    scene = cielim.Scene()

    scene.set_camera_params(grayscale=True)

    scene.add_celestial_body("central_body")  # index CENTRAL_BODY_INDEX; index 0 is the sun

    return scene


def speed_test_scenario(
    scene: cielim.Scene,
    number_of_images: int = 20,
    radius_ratio: float = 0.5,
    apoapse_angular_radius: float = 5.0,
    phase_angle: float = 30.0,
    pointing_mode: str = "auto",
    horizon_trigger_fov_fraction: float = 1.0,
    save_images: bool = True,
) -> dict:
    """
    Render one full orbit of the scene's central body, evenly spaced in time, starting at apoapse.

    The radius of apoapse is locked in by the body radius and the requested apparent angular radius
    at apoapse: r_a = R / sin(theta_a). The radius of periapse follows from radius_ratio.

    Read off the scene rather than passed in: the central body name, mean radius, shape model and
    albedo (celestial body at CENTRAL_BODY_INDEX), the gravitational parameter
    (scene.gravitational_parameter), and the camera field of view, resolution and exposure.

    The orbit is placed in the inertial x-y plane with apoapse on -x. The sun is then placed
    relative to that plane, so the orbit's inertial orientation has no observable effect and is not
    exposed as a knob.

    Args:
        scene (Scene): The scene to render, fully configured (see scene_setup and __main__).
        number_of_images (int): Number of images to capture, evenly spaced in time over one orbit.
        radius_ratio (float): Ratio of the radius of periapse to the radius of apoapse, in (0, 1].
        apoapse_angular_radius (float): Apparent angular radius of the body at apoapse, in degrees.
        phase_angle (float): Phase angle at apoapse in degrees, setting where the sun is placed.
        pointing_mode (str): "auto" to switch to horizon pointing when the body overflows the field
            of view, or "nadir" to always point at the body center.
        horizon_trigger_fov_fraction (float): Fraction of the (smaller) field of view that the
            angular diameter must exceed before horizon pointing engages. 1.0 means "once the body
            is larger than the field of view".
        save_images (bool): Whether to write the rendered frames to disk.

    Returns:
        dict: Orbit geometry and render timing summary.
    """
    if number_of_images < 1:
        raise ValueError(f"number_of_images must be at least 1, got {number_of_images}.")
    if not 0.0 < radius_ratio <= 1.0:
        raise ValueError(f"radius_ratio (r_p / r_a) must be in (0, 1], got {radius_ratio}.")
    if not 0.0 < apoapse_angular_radius < 90.0:
        raise ValueError(f"apoapse_angular_radius must be in (0, 90) degrees, got {apoapse_angular_radius}.")
    if pointing_mode not in ("auto", "nadir"):
        raise ValueError(f'pointing_mode must be "auto" or "nadir", got "{pointing_mode}".')

    # Central body and camera come from the scene, not from arguments.
    body = scene.get_celestial_body(CENTRAL_BODY_INDEX)
    body_name = body.bodyName
    body_radius = body.model.meanRadius
    gravitational_parameter = scene.gravitational_parameter
    fov = tuple(scene.get_scene().camera.lensModel.fieldOfView)

    if body_radius <= 0.0:
        raise ValueError(
            f'Central body "{body_name}" has no mean radius. Set it on the scene with '
            f"set_celestial_body_params({CENTRAL_BODY_INDEX}, mesh_radius=...) in meters."
        )
    if gravitational_parameter <= 0.0:
        raise ValueError(
            "Central body gravitational parameter is not set. Set scene.gravitational_parameter "
            "on the scene, in m^3/s^2."
        )

    # Orbit geometry: the requested apparent angular radius at apoapse locks in the radius of
    # apoapse, and the ratio locks in the radius of periapse.
    apoapse_angular_radius_rad = apoapse_angular_radius * np.pi / 180
    radius_apoapse = body_radius / np.sin(apoapse_angular_radius_rad)
    radius_periapse = radius_ratio * radius_apoapse

    if radius_periapse <= body_radius:
        max_ratio = body_radius / radius_apoapse
        raise ValueError(
            f"radius_ratio {radius_ratio} puts periapse at {radius_periapse:.1f} m, inside the body "
            f"radius of {body_radius:.1f} m. Use a radius_ratio above {max_ratio:.4f}, or a smaller "
            f"apoapse_angular_radius."
        )

    semi_major_axis = 0.5 * (radius_apoapse + radius_periapse)
    eccentricity = (1.0 - radius_ratio) / (1.0 + radius_ratio)
    period = 2 * np.pi * np.sqrt(semi_major_axis**3 / gravitational_parameter)

    elements = orbital_motion.ClassicOrbitalElements()
    elements.semi_major_axis = semi_major_axis
    elements.eccentricity = eccentricity
    elements.inclination = 0.0
    elements.ascending_node = 0.0
    elements.argument_periapsis = 0.0

    # Place the sun at 1 AU, in the orbit plane, at the requested phase angle from the apoapse
    # position. The sun is then held fixed, so the phase angle varies naturally around the orbit.
    elements.true_anomaly = np.pi
    apoapse_position, apoapse_velocity = orbital_motion.orbital_elements_to_cartesian(
        gravitational_parameter, elements
    )
    orbit_normal = np.cross(apoapse_position, apoapse_velocity)
    orbit_normal /= np.linalg.norm(orbit_normal)
    radial = apoapse_position / np.linalg.norm(apoapse_position)
    in_plane = np.cross(orbit_normal, radial)

    phase_angle_rad = phase_angle * np.pi / 180
    sun_heading = np.cos(phase_angle_rad) * radial + np.sin(phase_angle_rad) * in_plane
    scene.set_celestial_body_params(0, position=tuple(CONST_AU * sun_heading))

    directory_path = os.path.join(current_file_path, "images-speed-test")
    if save_images:
        os.makedirs(directory_path, exist_ok=True)

    min_fov = min(fov)
    horizon_threshold = horizon_trigger_fov_fraction * min_fov

    print(f"Orbit around {body_name}: r_a {radius_apoapse * 1e-3:.3f} km, r_p {radius_periapse * 1e-3:.3f} km")
    print(f"  a {semi_major_axis * 1e-3:.3f} km, e {eccentricity:.4f}, period {period:.1f} s")
    print(f"  {number_of_images} images evenly spaced in time, starting at apoapse")

    connector = cielim.Connector()
    #launcher = cielim.Launcher()
    #connector.connect(launcher.launch())
    connector.connect()
    connector.send_init_request()

    render_times = []
    angular_radii = []
    phase_angles = []
    horizon_frames = 0

    frames = []

    for idx in range(number_of_images):
        sample_time = idx * period / number_of_images

        # Apoapse is a mean anomaly of pi, and evenly spaced in time is evenly spaced in mean anomaly.
        mean_anomaly = np.pi + 2 * np.pi * idx / number_of_images
        elements.true_anomaly = _true_anomaly_from_mean(mean_anomaly, eccentricity)

        scene_dynamics.set_orbital_elements(scene, elements, gravitational_parameter)

        spacecraft_position = np.array(scene.get_scene().spacecraft.position)
        orbit_radius = np.linalg.norm(spacecraft_position)
        angular_radius = np.arcsin(min(body_radius / orbit_radius, 1.0))
        fov_fill = 2 * angular_radius / min_fov

        is_horizon = pointing_mode == "auto" and 2 * angular_radius > horizon_threshold
        horizon_frames += int(is_horizon)

        _point_at_body(scene, angular_radius if is_horizon else 0.0)

        sun_position = np.array(scene.get_scene().celestialBodies[0].position)
        frame_phase_angle = np.arccos(
            np.dot(spacecraft_position / orbit_radius, sun_position / np.linalg.norm(sun_position))
        )

        angular_radii.append(angular_radius * 180 / np.pi)
        phase_angles.append(frame_phase_angle * 180 / np.pi)

        start = time.perf_counter()
        connector.send_frame(scene.get_scene())
        image, _, _ = connector.request_image_for_camera_id(1, save_images, True)
        render_time = time.perf_counter() - start
        render_times.append(render_time)

        # Written outside the timed block so disk IO does not contaminate the render measurement.
        if save_images and image is not None:
            cv2.imwrite(os.path.join(directory_path, f"speed_test_{idx:03d}.png"), image)
            frames.append(image)

        print(
            f"[{idx:03d}] t {sample_time:9.1f} s  range {orbit_radius * 1e-3:8.3f} km  "
            f"rho {angular_radius * 180 / np.pi:7.3f} deg  fill {fov_fill:6.3f}  "
            f"{'horizon' if is_horizon else 'nadir  '}  phase {frame_phase_angle * 180 / np.pi:6.2f} deg  "
            #f"coverage {coverage:6.4f}  render {render_time:6.3f} s"
        )

    connector.disconnect()
    #launcher.terminate()

    imageio.mimsave(os.path.join(directory_path, "output.gif"), frames, fps=60, loop=0)

    render_times = np.array(render_times)
    summary = {
        "number_of_images": number_of_images,
        "render_times": render_times.tolist(),
        "angular_radii": angular_radii,
        "phase_angles": phase_angles,
        "radius_apoapse": radius_apoapse,
        "radius_periapse": radius_periapse,
        "semi_major_axis": semi_major_axis,
        "eccentricity": eccentricity,
        "period": period,
        "horizon_frames": horizon_frames,
        "total_render_time": float(render_times.sum()),
        "mean_render_time": float(render_times.mean()),
        "min_render_time": float(render_times.min()),
        "max_render_time": float(render_times.max()),
        "images_per_second": float(number_of_images / render_times.sum()),
    }

    print(
        f"Rendered {number_of_images} images in {summary['total_render_time']:.3f} s "
        f"({summary['images_per_second']:.2f} images/s)"
    )
    print(
        f"  per frame: mean {summary['mean_render_time']:.3f} s, "
        f"min {summary['min_render_time']:.3f} s, max {summary['max_render_time']:.3f} s"
    )
    print(f"  {horizon_frames} of {number_of_images} frames used horizon pointing")

    return summary


if __name__ == "__main__":
    scene = scene_setup()

    # Central body: shape model, mean radius (meters), albedo, and gravitational parameter (m^3/s^2).
    # Swap in bennu_normalized / eros_normalized / sphere_normalized and their constants as needed.
    scene.set_celestial_body_params(
        CENTRAL_BODY_INDEX,
        name="vesta",
        mesh_shape="vesta_normalized",
        mesh_brdf="Regolith",
        mesh_radius=262.7 * 1e3,
        albedo=0.432,
    )
    scene.gravitational_parameter = 1.728 * 10 ** 10
    scene.target_name = "vesta"

    # Camera: field of view (x, y) in radians, sensor resolution in pixels, exposure in seconds.
    scene.set_lens_params(fov=(5 * np.pi / 180, 5 * np.pi / 180))
    scene.set_sensor_params(resolution=(1024, 1024), exposure=5e-4)

    summary = speed_test_scenario(
        scene,
        number_of_images=400,
        radius_ratio=0.05,
        apoapse_angular_radius=0.57,
        phase_angle=130.0,
    )

    # Pass csv_path=... to overlay a per-image timing log from another renderer or an earlier run,
    # or call plot_render_timing(csv_path=...) on its own to plot a saved log without a scenario.
    plot_render_timing(summary["render_times"], phase_angle=summary["phase_angles"])
