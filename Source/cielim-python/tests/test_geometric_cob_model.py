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
def gm():
    return _load("geometric_cob_model")


def _perspective_reference(gm, A, s, r, rho, n=1400):
    """
    Pinhole ray cast from rho r onto the ellipsoid: the lit visible region's image-plane area centroid,
    in gnomonic coordinates times rho (body units, (e1, e2) basis), independent of the model.
    """
    e1, e2 = gm.image_basis(r)
    largest = 1.0 / np.sqrt(np.linalg.eigvalsh(A).min())
    extent = 1.25 * largest / np.sqrt(rho**2 - largest**2)
    u = np.linspace(-extent, extent, n)
    grid_u, grid_v = (g.ravel() for g in np.meshgrid(u, u))
    directions = -r + grid_u[:, None] * e1 + grid_v[:, None] * e2
    origin = rho * r
    qa = np.einsum("ij,jk,ik->i", directions, A, directions)
    qb = directions @ (A @ origin)
    discriminant = qb**2 - qa * (origin @ A @ origin - 1)
    hit = discriminant > 0
    t = (-qb[hit] - np.sqrt(discriminant[hit])) / qa[hit]  # the near intersection is the visible one
    surface = origin + t[:, None] * directions[hit]
    lit = surface @ A @ s > 0
    return rho * np.array([grid_u[hit][lit].mean(), grid_v[hit][lit].mean()]), e1, e2


def _configuration(seed, range_in_largest_axes):
    rng = np.random.default_rng(seed)
    axes = np.exp(rng.normal(0.0, 0.35, 3))
    rotation = Rotation.random(random_state=seed).as_matrix()
    A = rotation @ np.diag(1.0 / axes**2) @ rotation.T
    r = rng.normal(size=3)
    r /= np.linalg.norm(r)
    alpha = np.radians(rng.uniform(30.0, 140.0))
    side = np.cross(r, rng.normal(size=3))
    side /= np.linalg.norm(side)
    s = np.cos(alpha) * r + np.sin(alpha) * side
    return A, s, r, range_in_largest_axes * axes.max()


@pytest.mark.parametrize("seed, range_in_largest_axes", [(1, 5.0), (2, 8.0), (3, 8.0), (4, 20.0)])
def test_full_offset_matches_a_perspective_ray_cast(gm, seed, range_in_largest_axes):
    A, s, r, rho = _configuration(seed, range_in_largest_axes)
    reference, e1, e2 = _perspective_reference(gm, A, s, r, rho)
    to_image = lambda vector: np.array([vector @ e1, vector @ e2])
    h = gm.error_components(A, s, r, rho)["h"]

    full = np.linalg.norm(reference - to_image(gm.full_offset(A, s, r, rho))) / h
    case_a = np.linalg.norm(reference - to_image(gm.delta_caseA(A, s, r))) / h
    assert full < 0.02, f"full model off by {full:.4f} h"
    assert full < case_a, f"full model {full:.4f} h is no better than Case A {case_a:.4f} h"


def test_error_vector_perpendicular_term_follows_e_perp(gm):
    A, s, r, rho = _configuration(2, 8.0)
    e = gm.error_components(A, s, r, rho)
    w = s - (s @ r) * r
    d3 = w / np.linalg.norm(w)
    xc, e1, e2 = gm.limb_centre(A, r, rho)
    xc3 = xc[0] * e1 + xc[1] * e2
    # The error vector's component across the sunline is the limb centre's, x_c being its only source.
    across = np.cross(-r, d3)
    np.testing.assert_allclose(gm.error_vector(A, s, r, rho) @ across, xc3 @ across, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(e["e_perp"] * e["h"], xc3 @ across, rtol=1e-9, atol=1e-12)


def test_full_offset_tends_to_case_a_far_away(gm):
    A, s, r, _ = _configuration(5, 1.0)
    far = 1e6 / np.sqrt(np.linalg.eigvalsh(A).min())
    np.testing.assert_allclose(gm.full_offset(A, s, r, far), gm.delta_caseA(A, s, r), atol=1e-5)
