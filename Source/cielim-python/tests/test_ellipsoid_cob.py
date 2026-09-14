import importlib.util
from pathlib import Path

import numpy as np
import pytest

examples_dir = Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, str(examples_dir / f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ec():
    return _load("ellipsoid_cob_scenario")


def test_ellipsoid_radius_on_principal_axes(ec):
    semi_axes = [2.0, 3.0, 5.0]

    np.testing.assert_allclose(
        [ec.ellipsoid_radius(d, semi_axes) for d in np.eye(3)],
        semi_axes,
        rtol=1e-12,
        err_msg="Radius along a principal axis must be that semi-axis",
    )


def test_ellipsoid_radius_of_a_sphere_is_its_radius(ec):
    # Direction-independent for a=b=c, whatever the direction and however it is scaled.
    for direction in ([1, 1, 1], [0.3, -2.0, 0.1], [-1, 0, 4]):
        np.testing.assert_allclose(ec.ellipsoid_radius(direction, [4.0, 4.0, 4.0]), 4.0, rtol=1e-12)


def test_reference_radius_rules(ec):
    axes = np.array([1.0, 2.0, 4.0])
    r_sub = 1.7

    np.testing.assert_allclose(ec.reference_radius_rules["arithmetic"](axes, r_sub), 7.0 / 3.0, rtol=1e-12)
    np.testing.assert_allclose(ec.reference_radius_rules["volume"](axes, r_sub), 8.0 ** (1 / 3), rtol=1e-12)
    np.testing.assert_allclose(ec.reference_radius_rules["sub_solar"](axes, r_sub), r_sub, rtol=1e-12)


def test_sub_solar_radius_follows_the_mesh_attitude(ec):
    # A 2:1:1 body with the sun on +x sees the long axis; rotating the body 90 degrees about z puts
    # the short axis there instead. Validated against the engine, see validate_scaling_frame.
    semi_axes = [2.0, 1.0, 1.0]
    roll = ec.rbk.dcm_to_mrp(ec._roll_z(np.pi / 2))

    np.testing.assert_allclose(ec.sub_solar_radius([1, 0, 0], [0, 0, 0], semi_axes), 2.0, rtol=1e-9)
    np.testing.assert_allclose(ec.sub_solar_radius([0, 1, 0], [0, 0, 0], semi_axes), 1.0, rtol=1e-9)
    np.testing.assert_allclose(ec.sub_solar_radius([0, 1, 0], roll, semi_axes), 2.0, rtol=1e-9)


def _disk(size=101, radius=30, ramp=False):
    """A lit disk, optionally with a left-to-right intensity ramp across it."""
    rows, columns = np.indices((size, size))
    centre = size // 2
    inside = (columns - centre) ** 2 + (rows - centre) ** 2 <= radius**2
    if not ramp:
        return (inside * 200).astype(np.uint8)
    level = 40 + 200 * (columns - (centre - radius)) / (2 * radius)
    return (inside * np.clip(level, 0, 255)).astype(np.uint8)


def test_centroids_agree_on_a_uniform_disk(ec):
    image = _disk()

    photometric = ec.centroid(image)
    geometric = ec.centroid(image, binary=True)

    np.testing.assert_allclose(photometric, geometric, atol=1e-9)
    np.testing.assert_allclose(photometric, (50.0, 50.0), atol=1e-9)


def test_only_the_photometric_centroid_follows_an_intensity_ramp(ec):
    image = _disk(ramp=True)

    photometric = ec.centroid(image)
    geometric = ec.centroid(image, binary=True)

    # The mask is unchanged by the ramp, so the geometric centroid stays on the disk centre while
    # the intensity-weighted one is pulled toward the bright side. That difference is the whole
    # point of the geometric toggle.
    np.testing.assert_allclose(geometric, (50.0, 50.0), atol=1e-9)
    np.testing.assert_(photometric[0] > geometric[0] + 1.0, msg="Ramp did not pull the photometric centroid")
    np.testing.assert_allclose(photometric[1], 50.0, atol=1e-9)


def test_photometric_centroid_linearizes_first(ec):
    # The frame is gamma encoded, so weighting the raw values is not a radiance centroid. Undoing a
    # larger gamma weights the bright side harder and pulls the centroid further along the ramp.
    image = _disk(ramp=True)

    encoded = ec.centroid(image, gamma=1.0)
    linearized = ec.centroid(image, gamma=2.2)

    np.testing.assert_(
        linearized[0] > encoded[0] + 0.5, msg="Linearizing should pull the centroid toward the bright side"
    )


def test_centroid_returns_none_when_nothing_is_lit(ec):
    np.testing.assert_(ec.centroid(np.zeros((20, 20), np.uint8)) is None, msg="Unlit frame should give no centroid")


def test_sunline_pixel_direction_is_a_unit_vector(ec):
    position = np.array([0.0, 0.0, -1.0e6])
    world_to_camera = np.eye(3)

    for heading in ([1, 0, 0], [0, 1, 0], [0.6, -0.8, 0.0]):
        direction = ec.sunline_pixel_direction(heading, position, world_to_camera, (0.35, 0.26), (2000, 1500))
        np.testing.assert_allclose(np.linalg.norm(direction), 1.0, rtol=1e-9)
