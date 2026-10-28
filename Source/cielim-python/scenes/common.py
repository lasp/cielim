"""The default scene: the spacecraft on the +Z axis looking down at a single body at the origin centered in the frame.

By default the central body is a 1 km sphere seen from 50 km through a 5 deg FoV. The narrow FoV keeps the projection
close to orthographic, so pixel shifts and sizes follow simple angle-per-pixel geometry, and the sphere spans a bit
under half the image width.
"""

import cielim
import numpy as np


def default_scene(
    distance=50_000,
    fov_deg=5.0,
    brdf="Lambertian",
    attitude=(1, 0, 0),
    shape="sphere_normalized",
) -> cielim.Scene:
    """Return a scene with the spacecraft ``distance`` meters up the +Z axis looking at a body at the origin.

    Args:
        distance: spacecraft distance from the body, in meters.
        fov_deg: (square) field of view, in degrees.
        brdf: the body's surface model, e.g. "Lambertian" or "Regolith".
        attitude: spacecraft attitude as an MRP. The default orients the image so +x is right, +y is
            up, and +z is out of the page.
        shape: the body's mesh, e.g. "sphere_normalized" or "Plane".
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, distance), attitude=attitude)

    fov = np.radians(fov_deg)
    scene.set_lens_params(fov=(fov, fov))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape=shape, mesh_brdf=brdf, mesh_radius=1000)

    return scene
