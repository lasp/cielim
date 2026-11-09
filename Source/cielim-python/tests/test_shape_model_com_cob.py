import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

examples_dir = Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, str(examples_dir / f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sm():
    return _load("shape_model_com_cob_analysis")


@pytest.fixture(scope="module", params=["eros", "itokawa"])
def body(sm, request):
    obj_path = Path(sm.support_directory(request.param)) / sm.bodies[request.param]["obj"]
    if not obj_path.exists():
        pytest.skip(f"{request.param} shape model not found at {obj_path}")
    vertices, faces, km_per_unit = sm.load_body_mesh(request.param)
    fit = sm.body_ellipsoid(request.param, vertices, faces, km_per_unit, "dimensions")
    return request.param, vertices, faces, km_per_unit, fit


def _closed_hull(points):
    """Triangulated convex hull with every face wound outward."""
    hull = ConvexHull(points)
    faces = hull.simplices.copy()
    centre = points.mean(axis=0)
    a, b, c = (points[faces[:, i]] for i in range(3))
    inward = np.einsum("ij,ij->i", np.cross(b - a, c - a), a - centre) < 0
    faces[inward] = faces[inward][:, ::-1]
    return faces


def _ellipsoid_mesh(semi_axes, rotation, centre, count=20000, seed=0):
    rng = np.random.default_rng(seed)
    unit = rng.normal(size=(count, 3))
    unit /= np.linalg.norm(unit, axis=1, keepdims=True)
    points = (unit * semi_axes) @ rotation.T + centre
    return points, _closed_hull(points)


def test_principal_frame_recovers_an_ellipsoid(sm):
    semi_axes = np.array([3.0, 1.7, 1.1])
    rotation = Rotation.from_euler("zyx", (20, -35, 60), degrees=True).as_matrix()
    centre = np.array([0.4, -1.2, 2.5])
    vertices, faces = _ellipsoid_mesh(semi_axes, rotation, centre)

    volume, centroid, principal_axes = sm.principal_frame(vertices, faces)
    np.testing.assert_allclose(centroid, centre, atol=2e-3)
    np.testing.assert_allclose(volume, 4 / 3 * np.pi * np.prod(semi_axes), rtol=5e-3)
    np.testing.assert_allclose(np.abs(principal_axes.T @ rotation), np.eye(3), atol=1e-2)
    np.testing.assert_allclose(np.linalg.det(principal_axes), 1.0)

    fit = sm.fit_ellipsoid(vertices, faces, semi_axes)
    axis = principal_axes[:, 0] * semi_axes[0]
    np.testing.assert_allclose(axis @ fit["shape_matrix"] @ axis, 1.0)


def test_inward_winding_is_flipped(sm, tmp_path, monkeypatch):
    vertices, faces = _ellipsoid_mesh(np.ones(3), np.eye(3), np.zeros(3), count=200)
    path = tmp_path / "inward.obj"
    path.write_text(
        "".join(f"v {x} {y} {z}\n" for x, y, z in vertices)
        + "".join(f"f {a + 1} {c + 1} {b + 1}\n" for a, b, c in faces)
    )
    monkeypatch.setitem(sm.bodies, "test", {"obj": path.name, "km_per_unit": 1.0, "dimensions_km": (2, 2, 2)})
    monkeypatch.setattr(sm, "support_directory", lambda body: str(tmp_path))
    _, flipped, _ = sm.load_body_mesh("test")
    assert sm.mesh_moments(vertices, flipped)[0] > 0


def test_body_mesh_and_ellipsoid_are_plausible(sm, body):
    name, vertices, faces, km_per_unit, fit = body
    assert sm.mesh_is_closed(faces)
    np.testing.assert_allclose(fit["semi_axes"] * km_per_unit * 2, sm.bodies[name]["dimensions_km"])
    # The published dimensions and the shape model's extents along its principal axes agree to ~30%.
    local = (vertices - fit["centroid"]) @ fit["principal_axes"] * km_per_unit
    extents = local.max(axis=0) - local.min(axis=0)
    np.testing.assert_allclose(extents, sm.bodies[name]["dimensions_km"], rtol=0.35)
    assert 0.8 < fit["volume_ratio"] < 1.1
    # Published volumes: Eros 2503 km^3 (Thomas et al. 2002), Itokawa 0.0178 km^3 (Gaskell).
    expected = {"eros": 2503.0, "itokawa": 0.0178}[name]
    np.testing.assert_allclose(fit["volume"] * km_per_unit**3, expected, rtol=0.02)


def test_signed_permutations(sm):
    matrices = sm.signed_permutations()
    assert len(matrices) == 48
    assert len({m.tobytes() for m in matrices}) == 48
    for m in matrices:
        np.testing.assert_allclose(m @ m.T, np.eye(3))


@pytest.mark.parametrize("improper", [False, True])
def test_world_shape_matrix(sm, body, improper):
    _, _, _, _, fit = body
    permutation = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, -1.0 if improper else 1.0, 0.0]])
    assert np.linalg.det(permutation) == (-1.0 if improper else 1.0)
    scale, pivot = 1.5e5, np.array([0.002, -0.001, 0.003])
    attitude = sm.rbk.dcm_to_mrp(Rotation.from_euler("xyz", (10, 70, -40), degrees=True).as_matrix())

    # Surface points of the ellipsoid, mapped to world, lie on x^T A_world x = 1 about the centre.
    rng = np.random.default_rng(4)
    unit = rng.normal(size=(500, 3))
    unit /= np.linalg.norm(unit, axis=1, keepdims=True)
    surface = fit["centroid"] + (unit * fit["semi_axes"]) @ fit["principal_axes"].T
    world = sm.to_world(surface, attitude, permutation, scale, pivot)
    centre = sm.to_world(fit["centroid"], attitude, permutation, scale, pivot)
    shape_matrix = sm.world_shape_matrix(fit, permutation, scale, attitude)
    np.testing.assert_allclose(np.einsum("ij,jk,ik->i", world - centre, shape_matrix, world - centre), 1.0, rtol=1e-9)


def test_registration_recovers_a_known_mapping(sm):
    """Rasterized "renders" of an asymmetric mesh under a known P, k and o must be matched back."""
    rng = np.random.default_rng(11)
    points = rng.normal(size=(150, 3)) * (1.0, 0.6, 0.4)
    points[:40, 0] += 0.8  # a lobe, so no mirror or permutation reproduces all views
    vertices = points - points.mean(axis=0)
    faces = _closed_hull(vertices)

    extent = 1.3 * np.linalg.norm(vertices, axis=1).max() * 1e4
    scene = sm.scene_setup(extent_m=extent, camera_range=3e6, shape_model="sphere_normalized")
    scene.set_sensor_params(resolution=(400, 300))
    geometry = sm.scene_geometry(scene)

    permutation = np.array([[0.0, -1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]])
    scale, pivot = 1.07e4, np.array([0.05, -0.03, 0.02])
    masks = sm._predict_masks(vertices, faces, sm.registration_attitudes, permutation, scale, pivot, geometry)

    solution = sm.solve_registration(masks, sm.registration_attitudes, vertices, faces, geometry, initial_scale=0.9e4)
    np.testing.assert_array_equal(solution["permutation"], permutation)
    np.testing.assert_allclose(solution["scale"], scale, rtol=5e-3)
    np.testing.assert_allclose(solution["pivot"], pivot, atol=5e-3)
    assert min(solution["iou"]) > 0.98
    assert solution["runner_up_iou"] < min(solution["iou"])


def test_project_many_matches_project(sm):
    scene = sm.scene_setup(extent_m=1e4, camera_range=1e6, shape_model="sphere_normalized")
    geometry = sm.scene_geometry(scene)
    points = np.random.default_rng(2).normal(size=(5, 3)) * 5e3
    expected = np.array([sm.ec.project(p, *geometry) for p in points])
    np.testing.assert_allclose(sm.project_many(points, *geometry), expected, atol=1e-9)


def test_radial_fit_recovers_an_ellipsoid(sm):
    semi_axes = np.array([3.0, 1.7, 1.1])
    rotation = Rotation.from_euler("zyx", (20, -35, 60), degrees=True).as_matrix()
    vertices, faces = _ellipsoid_mesh(semi_axes, rotation, np.array([0.4, -1.2, 2.5]))
    # The vertices lie on the ellipsoid, so the radial residuals vanish at the true semi-axes.
    np.testing.assert_allclose(sm.radial_semi_axes(vertices, faces), semi_axes, rtol=2e-3)
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    total_area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum()
    np.testing.assert_allclose(sm.vertex_areas(vertices, faces).sum(), total_area)


def test_gaussianity(sm):
    rng = np.random.default_rng(5)
    normal = sm.gaussianity(rng.normal(3.0, 2.0, size=2000))
    np.testing.assert_allclose([normal["mean"], normal["std"]], [3.0, 2.0], atol=0.15)
    assert abs(normal["skewness"]) < 0.2 and abs(normal["excess_kurtosis"]) < 0.3
    heavy = sm.gaussianity(rng.standard_t(3, size=2000))
    assert heavy["excess_kurtosis"] > 1.0
