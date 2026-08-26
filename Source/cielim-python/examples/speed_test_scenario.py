"""
Goal:
    Render a controlled, repeatable sweep of apparent object size around a closed Keplerian orbit.

    The orbit is parameterized by the *apparent angular radius of the central body at apoapse*
    rather than by a distance in meters, which pins the geometry in the units that actually drive
    the cielim render cost (angular size relative to the field of view). The ratio of the radius of
    periapse to the radius of apoapse then sets how far into "the body overflows the frame"
    territory the orbit dives.

    Images are captured evenly spaced in time along one full orbit, starting at apoapse. The
    per-frame round-trip time is written to a CSV for examples/speed_test_analysis.py, which
    plots it against the engine-side timings; this module only generates data.

    Pointing is nadir (boresight on the body center), automatically switching to horizon pointing
    (boresight offset onto the lit limb) once the body grows larger than the field of view.

    The central body, its gravitational parameter and radius, and the camera are all read off the
    scene: scene_setup() builds the skeleton and everything physical is edited in __main__.
"""

import csv
import os
import time

import cv2
import numpy as np

import cielim
from cielim.utils import orbital_motion
from cielim.utils import rigid_body_kinematics as rbk
from cielim.utils import scene_dynamics
from cielim.utils.qe_curve_fit import CONST_AU

current_file_path = os.path.dirname(__file__)

# Index of the central body in the scene. Index 0 is the sun, auto-created by Scene.__init__.
CENTRAL_BODY_INDEX = 1

# Per-frame round-trip timings are written here for examples/speed_test_analysis.py. Milliseconds,
# to match the engine-side instrumentation CSVs exactly, so all three inputs share one format.
TIMING_CSV_NAME = "cielim_roundtrip.csv"


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
    number_of_images: int = 100,
    radius_ratio: float = 0.5,
    apoapse_angular_radius: float = 5.0,
    phase_angle: float = 30.0,
    pointing_mode: str = "auto",
    horizon_trigger_fov_fraction: float = 1.0,
    save_images: bool = True,
    output_directory: str | None = None,
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
        output_directory (str, optional): Where the frames and the timing CSV go. Defaults to
            examples/images-speed-test/. Point it elsewhere to keep a run out of the repo tree.

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

    directory_path = output_directory or os.path.join(current_file_path, "images-speed-test")
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

        print(
            f"[{idx:03d}] t {sample_time:9.1f} s  range {orbit_radius * 1e-3:8.3f} km  "
            f"rho {angular_radius * 180 / np.pi:7.3f} deg  fill {fov_fill:6.3f}  "
            f"{'horizon' if is_horizon else 'nadir  '}  phase {frame_phase_angle * 180 / np.pi:6.2f} deg  "
            #f"coverage {coverage:6.4f}  render {render_time:6.3f} s"
        )

    connector.disconnect()
    #launcher.terminate()

    render_times = np.array(render_times)

    # Written unconditionally, not gated on save_images: the point of save_images=False is to time
    # the path without PNG encoding, and those numbers are exactly what this file is for.
    timing_csv = os.path.join(directory_path, TIMING_CSV_NAME)
    with open(timing_csv, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame_time_ms"])
        writer.writerows([[f"{value * 1e3:.3f}"] for value in render_times])
    print(f"Wrote per-frame round-trip timings -> {timing_csv}")

    summary = {
        "timing_csv": timing_csv,
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

    speed_test_scenario(
        scene,
        number_of_images=201,
        radius_ratio=0.05,
        apoapse_angular_radius=0.57,
        phase_angle=130.0,
    )

    # Plotting lives in examples/speed_test_analysis.py, which reads this run's timing CSV together
    # with the engine-side ones. Run it after this to get the frame-time breakdown.
