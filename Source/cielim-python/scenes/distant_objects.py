"""An asteroid seen at long range, where Cielim hands it over from mesh rendering to a distant object.

The camera sits on the -Z axis looking toward +Z at an asteroid at the origin, with a field of view
and resolution matching asteroid_departure.py. :func:`compute_transition_distance` mirrors the
engine's IsCelestialBodyResolvable, so a scene can be placed just either side of the handover.
"""

import cielim
import numpy as np

fov_x = 20 * np.pi / 180
fov_y = 15 * np.pi / 180
width = 2000
height = 1500
mean_radius = 1000
albedo = 1.0
sun_distance = 1.496e11
sun_position = [0, 0, -sun_distance]  # behind the camera, so the asteroid is front-lit
sun_index = 0
asteroid_index = 1


def pixel_size_threshold(phase_angle_deg):
    """Return the PixelSize threshold used by IsCelestialBodyResolvable at the given phase angle.

    Unified for on-grid and off-grid (C++ uses the same formula for both, keeping the two
    paths in lockstep avoids the compromise problem where the right rasterized size at
    transition depends on the object's position in the pixel grid):
      clamp(3 / (1 + cos α), 4, 15)
    Aims for a ~1.5-pixel mesh crescent at transition for α in [110°, 143°], capped at 15
    past ~143° so the rasterized bounding box doesn't balloon when the crescent goes sub-pixel.

    Evaluates to 4 for α ≤ 110°, 4.8 at 112°, 10.23 at 135°, 15 (capped) from ~143° up.
    """
    alpha = np.radians(phase_angle_deg)
    crescent_factor = max(1.0 + np.cos(alpha), 0.1)
    return float(np.clip(3.0 / crescent_factor, 4.0, 15.0))


def compute_transition_distance(width=width, height=height, phase_angle_deg=0):
    """Approximate distance where IsCelestialBodyResolvable switches to distant rendering."""
    bounds_radius = mean_radius * np.sqrt(3)
    proj_m00 = 1.0 / np.tan(fov_x / 2)
    proj_m11 = 1.0 / np.tan(fov_y / 2)
    screen_multiple = max(0.5 * proj_m00, 0.5 * proj_m11)
    max_dim = max(width, height)
    return screen_multiple * bounds_radius * max_dim * 2 / pixel_size_threshold(phase_angle_deg)


def scene_at_distance(camera_distance, width=width, height=height):
    """Create a Scene matching asteroid_departure.py at the given camera distance.

    The Scene constructor already sets the camera id/name, body-frame MRPs, and spacecraft name; only
    the fields this setup cares about are overridden here. The Scene's default sun (index 0) is moved
    behind the camera to front-light +Z.
    """
    scene = cielim.Scene()
    scene.set_celestial_body_params(sun_index, position=tuple(sun_position))

    # Asteroid (index 1): a normalized sphere mesh.
    scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(
        asteroid_index,
        mesh_shape="sphere_normalized",
        mesh_radius=mean_radius,
        albedo=albedo,
        mesh_brdf="Regolith",
    )

    scene.set_lens_params(fov=(fov_x, fov_y))
    scene.set_sensor_params(resolution=(width, height), exposure=0.001)
    scene.set_spacecraft_params(position=(0, 0, -camera_distance))
    return scene


def scene_with_phase_angle(
    camera_distance, phase_angle_deg, brdf_model="Regolith", exposure_time=None, width=width, height=height
):
    """Create a Scene at the given phase angle by rotating the sun position."""
    alpha = np.radians(phase_angle_deg)
    sun_pos = (sun_distance * np.sin(alpha), 0.0, -sun_distance * np.cos(alpha))

    scene = scene_at_distance(camera_distance, width, height)
    scene.set_celestial_body_params(asteroid_index, mesh_brdf=brdf_model)
    scene.set_celestial_body_params(sun_index, position=sun_pos)
    if exposure_time is not None:
        scene.set_sensor_params(exposure=exposure_time)
    return scene
