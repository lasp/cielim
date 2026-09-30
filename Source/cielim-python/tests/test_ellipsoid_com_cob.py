import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

examples_dir = Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, str(examples_dir / f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ec():
    return _load("ellipsoid_com_cob_analysis")


def _geometry(ec, phase_deg, azimuth=0.7):
    r_hat = np.array([0.0, 0.0, -1.0])
    return r_hat, ec.sun_heading_for_phase(r_hat, np.radians(phase_deg), azimuth)


def _random_ellipsoid(ec, seed):
    rng = np.random.default_rng(seed)
    semi_axes = np.exp(rng.normal(0.0, 0.3, size=3))
    attitude = ec.rbk.dcm_to_mrp(Rotation.random(random_state=seed).as_matrix())
    return ec.ellipsoid_matrix(semi_axes, attitude)


def test_sun_heading_has_requested_phase(ec):
    r_hat, s_hat = _geometry(ec, 73.0)
    np.testing.assert_allclose(np.linalg.norm(s_hat), 1.0, rtol=1e-12)
    np.testing.assert_allclose(np.degrees(np.arccos(s_hat @ r_hat)), 73.0, rtol=1e-12)


@pytest.mark.parametrize("phase_deg", [10.0, 60.0, 120.0, 160.0])
def test_sphere_limit_matches_sphere_model(ec, phase_deg):
    r_hat, s_hat = _geometry(ec, phase_deg)
    radius = 3.5
    np.testing.assert_allclose(
        ec.ellipsoid_offset(r_hat, s_hat, np.eye(3) / radius**2),
        ec.sphere_offset(r_hat, s_hat, radius),
        atol=1e-12,
        err_msg="With A = I / rho^2 the ellipsoid offset must reduce to gamma(alpha) rho",
    )


def test_offset_is_perpendicular_to_view_and_in_sun_plane(ec):
    r_hat, s_hat = _geometry(ec, 85.0)
    delta = ec.ellipsoid_offset(r_hat, s_hat, _random_ellipsoid(ec, 3))
    assert abs(delta @ r_hat) < 1e-12
    assert abs(delta @ np.cross(r_hat, s_hat)) < 1e-12


def test_zero_phase_returns_zero(ec):
    r_hat = np.array([0.0, 0.0, -1.0])
    a = np.diag([1.0, 0.25, 4.0])  # principal axes aligned with r_hat, so alpha_bar = 0 too
    delta = ec.ellipsoid_offset(r_hat, r_hat, a)
    assert np.all(np.isfinite(delta))
    np.testing.assert_allclose(delta, 0.0, atol=1e-12)


@pytest.mark.parametrize("seed, phase_deg", [(1, 40.0), (2, 90.0), (5, 135.0)])
def test_offset_matches_lit_silhouette_centroid(ec, seed, phase_deg):
    """
    Orthographic ray cast, independent of the renderer: sample uniformly over the image plane, keep
    the rays that hit the ellipsoid on a sunlit facet, and take their centroid. Uniform sampling in the
    image plane is the projected-area weighting the binary model assumes.
    """
    r_hat, s_hat = _geometry(ec, phase_deg)
    a = _random_ellipsoid(ec, seed)
    e1 = np.cross(r_hat, [1.0, 0.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(r_hat, e1)

    extent = 1.0 / np.sqrt(np.linalg.eigvalsh(a).min())
    rng = np.random.default_rng(seed)
    uv = rng.uniform(-extent, extent, size=(1_000_000, 2))
    p = uv[:, :1] * e1 + uv[:, 1:] * e2

    # (p + t r)^T A (p + t r) = 1; the camera-facing hit is the larger root, since r points to the camera.
    big_r = r_hat @ a @ r_hat
    half_b = p @ a @ r_hat
    c = np.einsum("ij,jk,ik->i", p, a, p) - 1.0
    discriminant = half_b**2 - big_r * c
    hit = discriminant > 0
    t = (-half_b[hit] + np.sqrt(discriminant[hit])) / big_r
    surface = p[hit] + t[:, None] * r_hat
    lit = (surface @ a) @ s_hat > 0

    centroid = p[hit][lit].mean(axis=0)
    size = 1.0 / np.sqrt(big_r)
    np.testing.assert_allclose(
        centroid,
        ec.ellipsoid_offset(r_hat, s_hat, a),
        atol=5e-3 * size,
        err_msg="Analytical ellipsoid offset must match the lit silhouette centroid",
    )


def test_binary_centroid_uses_project_coordinates(ec):
    # A lit block centred on the boresight must land exactly where project() puts the boresight.
    width, height = 40, 30
    fov = (0.3, 0.2)
    gray = np.zeros((height, width), dtype=np.uint8)
    gray[height // 2 - 3 : height // 2 + 3, width // 2 - 4 : width // 2 + 4] = 255
    spacecraft = np.array([0.0, 0.0, -10.0])
    boresight = ec.project(np.zeros(3), spacecraft, np.eye(3), fov, (width, height))
    np.testing.assert_allclose(ec.binary_centroid(gray), boresight, atol=1e-12)
    np.testing.assert_allclose(ec.photometric_centroid(gray), boresight, atol=1e-12)


def test_range_radii_keeps_the_disk_size_in_pixels(ec):
    sizes = []
    for radii in (ec.base_range_m / ec.base_radius, 10.0, 100.0):
        scene = ec.scene_setup(radii)
        world_to_camera, fov, resolution = ec.camera_frame(scene)
        spacecraft = np.array(scene.get_scene().spacecraft.position)
        np.testing.assert_allclose(np.linalg.norm(spacecraft), radii * ec.base_radius, rtol=1e-12)
        # Angular radius over the half field of view, which is what fixes the disk's size in pixels
        sizes.append(np.tan(np.arcsin(ec.base_radius / np.linalg.norm(spacecraft))) / np.tan(fov[0] / 2))
    np.testing.assert_allclose(sizes[1:], sizes[0], rtol=1e-2)


def test_range_inside_the_body_is_rejected(ec):
    with pytest.raises(ValueError):
        ec.scene_setup(1.5)
