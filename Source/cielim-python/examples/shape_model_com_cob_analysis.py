"""
Goal:
    Predict an irregular body's centre of mass (CoM) from its measured centre of brightness (CoB) with a
    triaxial ellipsoid built from its published dimensions, and compare it with the mean-radius sphere
    method across lighting. Bodies: Eros (default) and Itokawa.

    The ellipsoid's semi-axes are a least-squares radial fit to the surface (the mean-radius
    ellipsoid), or with --ellipsoid dimensions half the published overall dimensions (Eros
    34.4 x 11.2 x 11.2 km, Itokawa 535 x 294 x 209 m). Its centre and orientation come from the shape model: the uniform-density
    volume centroid and the principal axes of the second moments about it, longest axis along the
    largest moment. Each sample draws a phase angle, its azimuth about the boresight and a body
    attitude, renders the body (<body>_normalized) and predicts the CoM as the measured CoB minus the
    projected offset, scored against the true CoM:

        sphere model:      gamma(alpha) rho with rho the mean of the three semi-axes
        ellipsoid model:   the ellipsoid offset of ellipsoid_com_cob_analysis

    ellipsoid_com_cob_analysis shows the ellipsoid model is sub-pixel on a rendered ellipsoid, so the
    errors here are the body-ellipsoid shape mismatch.

    How the engine meshes were scaled, pivoted and axis-flipped on import is not recorded, so each OBJ is
    registered to the engine by rendering: silhouettes near zero phase at known attitudes are matched to
    the rasterized OBJ over the 48 signed axis permutations, solving the scale and pivot (see
    register_mesh). The result is cached in support-data/<body>/registration.json.
"""

import importlib.util
import itertools
import json
import os

import cv2
import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from scipy import stats
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

import cielim
from cielim.utils import rigid_body_kinematics as rbk

current_file_path = os.path.dirname(__file__)


def _load_sibling(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(current_file_path, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ec = _load_sibling("ellipsoid_com_cob_analysis")
colorList = ec.colorList
matplotlib.rcParams.update({"font.size": 6})

support_root = os.path.join(current_file_path, "..", "support-data")

# obj: shape model under support-data/<body>/, in km_per_unit km. dimensions_km: published overall
# dimensions, longest first.
bodies = {
    "eros": {
        "display_name": "Eros",
        "shape_model": "eros_normalized",
        "obj": "ErosICQ128.obj",  # Gaskell 512ICQ (the source of eros_normalized) decimated, km
        "km_per_unit": 1.0,
        "dimensions_km": (34.4, 11.2, 11.2),
    },
    "itokawa": {
        "display_name": "Itokawa",
        "shape_model": "itokawa_normalized",
        "obj": "ItokawaHayabusa.obj",  # Gaskell Hayabusa model, km
        "km_per_unit": 1.0,
        "dimensions_km": (0.535, 0.294, 0.209),  # Fujiwara et al. 2006
    },
}
default_body = "eros"

target_name = "asteroid"
central_body_index = 1
mesh_radius = 25e3  # metres; engine mean radius, the scene's length scale

frame_fill = 0.75  # the body's bounding sphere spans this fraction of the smaller field of view
default_range_radii = 300.0  # spacecraft range in mean semi-axes of the ellipsoid
phase_range_deg = ec.phase_range_deg
lit_threshold = ec.lit_threshold

# Registration renders near zero phase, where the whole silhouette is lit; the Lambertian limb is dim,
# so it thresholds just above the black level. It is accepted only if every view matches this well.
registration_threshold = 1
registration_min_iou = 0.98
registration_attitudes = [
    (0.0, 0.0, 0.0),
    tuple(rbk.dcm_to_mrp(Rotation.from_euler("x", 90, degrees=True).as_matrix())),
    tuple(rbk.dcm_to_mrp(Rotation.from_euler("y", 90, degrees=True).as_matrix())),
    tuple(rbk.dcm_to_mrp(Rotation.from_euler("zyx", (30, 40, 50), degrees=True).as_matrix())),
]

cases = ("body_sphere_model", "body_ellipsoid_model")
body_of = {name: name.split("_")[0] for name in cases}
phase_bins_deg = ((5.0, 60.0), (60.0, 120.0), (120.0, 170.0))


def case_descriptions(display_name):
    return {
        "body_sphere_model": f"{display_name}, sphere model (mean radius)",
        "body_ellipsoid_model": f"{display_name}, ellipsoid model",
    }


def support_directory(body):
    return os.path.join(support_root, body)


def registration_path(body):
    return os.path.join(support_directory(body), "registration.json")


def output_directory_for(body, ellipsoid="radial"):
    suffix = "" if ellipsoid == "radial" else f"-{ellipsoid}"
    return os.path.join(current_file_path, f"images-{body}-com-cob{suffix}")


def load_obj(path):
    """Vertices and triangle indices of an OBJ; polygons are fan-triangulated, texture/normal refs dropped."""
    vertices, faces = [], []
    with open(path) as handle:
        for line in handle:
            if line.startswith("v "):
                vertices.append(line.split()[1:4])
            elif line.startswith("f "):
                polygon = [int(token.split("/")[0]) - 1 for token in line.split()[1:]]
                faces.extend([polygon[0], polygon[i], polygon[i + 1]] for i in range(1, len(polygon) - 1))
    return np.array(vertices, float), np.array(faces, int)


def mesh_is_closed(faces):
    """True if every edge is shared by exactly two triangles, which the volume integrals need."""
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return bool(np.all(counts == 2))


def mesh_moments(vertices, faces):
    """
    Volume, centroid and central second-moment tensor J = int (x - c)(x - c)^T dV of a closed mesh.

    Sums signed tetrahedra (0, a, b, c): volume det / 6, first moment det / 24 (a + b + c), second
    moment det / 120 (aa^T + bb^T + cc^T + ss^T) with s = a + b + c. Outward faces give V > 0.
    """
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    det = np.einsum("ij,ij->i", a, np.cross(b, c))
    volume = det.sum() / 6
    s = a + b + c
    centroid = (det[:, None] * s).sum(axis=0) / (24 * volume)
    second = sum(np.einsum("i,ij,ik->jk", det, p, p) for p in (a, b, c, s)) / 120
    return volume, centroid, second - volume * np.outer(centroid, centroid)


def load_body_mesh(body):
    """
    The body's closed shape model, faces wound outward, and its length unit in km.

    Returns:
        tuple: vertices (OBJ units), faces, km per OBJ unit.
    """
    config = bodies[body]
    vertices, faces = load_obj(os.path.join(support_directory(body), config["obj"]))
    if not mesh_is_closed(faces):
        raise ValueError(f"{config['obj']} is not closed: the volume integrals need every edge on two triangles")
    volume, _, _ = mesh_moments(vertices, faces)
    if volume < 0:
        faces = faces[:, ::-1].copy()
    return vertices, faces, float(config["km_per_unit"])


def principal_frame(vertices, faces):
    """
    Volume, uniform-density centroid and principal axes E (columns, largest second moment first, det +1).
    """
    volume, centroid, second = mesh_moments(vertices, faces)
    if volume <= 0:
        raise ValueError(f"mesh volume is {volume}; the faces must wind outward")
    eigenvalues, principal_axes = np.linalg.eigh(second)
    order = eigenvalues.argsort()[::-1]
    principal_axes = principal_axes[:, order]
    if np.linalg.det(principal_axes) < 0:
        principal_axes[:, 2] *= -1
    return volume, centroid, principal_axes


def fit_ellipsoid(vertices, faces, semi_axes):
    """
    The ellipsoid with ``semi_axes`` (OBJ units, longest first) on the mesh centroid and principal axes.

    Returns:
        dict: centroid, semi_axes, principal_axes E, shape_matrix A = E diag(1/a^2) E^T about the
            centroid, mesh volume and the ratio of the ellipsoid's volume to the mesh's.
    """
    volume, centroid, principal_axes = principal_frame(vertices, faces)
    semi_axes = np.asarray(semi_axes, float)
    return {
        "centroid": centroid,
        "semi_axes": semi_axes,
        "principal_axes": principal_axes,
        "shape_matrix": principal_axes @ np.diag(1.0 / semi_axes**2) @ principal_axes.T,
        "volume": float(volume),
        "volume_ratio": float(4 / 3 * np.pi * np.prod(semi_axes) / volume),
    }


def vertex_areas(vertices, faces):
    """A third of the area of the triangles around each vertex, so vertex sums approximate surface means."""
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    areas = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    return np.bincount(faces.ravel(), weights=np.repeat(areas / 3, 3), minlength=len(vertices))


def radial_semi_axes(vertices, faces):
    """
    Semi-axes, on the mesh centroid and principal axes, of the ellipsoid closest to the surface radially.

    Along each vertex direction u from the centroid, the ellipsoid's radius is (sum u_i^2 / a_i^2)^(-1/2);
    the semi-axes minimize the area-weighted mean square of the vertex radius minus that. Starts from
    half the extents along the principal axes.
    """
    _, centroid, principal_axes = principal_frame(vertices, faces)
    local = (vertices - centroid) @ principal_axes
    radius = np.linalg.norm(local, axis=1)
    directions = local / radius[:, None]
    weights = np.sqrt(vertex_areas(vertices, faces))

    def residuals(semi_axes):
        return weights * (radius - (directions**2 @ (1.0 / semi_axes**2)) ** -0.5)

    start = (local.max(axis=0) - local.min(axis=0)) / 2
    return least_squares(residuals, start, bounds=(1e-3 * start, 10 * start)).x


ellipsoid_choices = ("radial", "dimensions")


def body_ellipsoid(body, vertices, faces, km_per_unit, ellipsoid="radial"):
    """
    The ellipsoid of ``body`` in OBJ units, on the mesh centroid and principal axes:

        dimensions:  half the published overall dimensions
        radial:      the least-squares radial fit to the surface, see radial_semi_axes
    """
    if ellipsoid == "dimensions":
        return fit_ellipsoid(vertices, faces, np.array(bodies[body]["dimensions_km"]) / 2 / km_per_unit)
    if ellipsoid == "radial":
        return fit_ellipsoid(vertices, faces, radial_semi_axes(vertices, faces))
    raise ValueError(f"ellipsoid must be one of {ellipsoid_choices}, not {ellipsoid!r}")


def signed_permutations():
    """The 48 signed axis permutations P (P[i, perm[i]] = sign[i]), proper and improper."""
    matrices = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1.0, -1.0), repeat=3):
            p = np.zeros((3, 3))
            p[range(3), perm] = signs
            matrices.append(p)
    return matrices


def to_world(points, mesh_attitude, permutation, scale, pivot):
    """
    OBJ points (OBJ units) to world (m) for a body at the origin: x = D^T k P (v - o).

    P, k and o come from the registration; D = mrp_to_dcm(mesh_attitude) rotates world into the mesh
    frame, the convention ellipsoid_com_cob_analysis.ellipsoid_matrix validated.
    """
    dcm = rbk.mrp_to_dcm(np.asarray(mesh_attitude, float))
    return (scale * (np.asarray(points, float) - pivot) @ np.asarray(permutation).T) @ dcm


def world_shape_matrix(fit, permutation, scale, mesh_attitude):
    """A in world axes and metres: D^T P A_obj P^T D / k^2, about the fitted centre."""
    dcm = rbk.mrp_to_dcm(np.asarray(mesh_attitude, float))
    rotation = np.asarray(permutation).T @ dcm
    return rotation.T @ fit["shape_matrix"] @ rotation / scale**2


def project_many(points, spacecraft_position, world_to_camera, fov, resolution):
    """Vectorized ec.project: pixel coordinates (N, 2) of world points (N, 3)."""
    d = (np.asarray(points, float) - spacecraft_position) @ np.asarray(world_to_camera, float).T
    width, height = resolution
    return np.column_stack(
        [
            (1 + d[:, 0] / d[:, 2] / np.tan(fov[0] / 2)) / 2 * width,
            (1 + d[:, 1] / d[:, 2] / np.tan(fov[1] / 2)) / 2 * height,
        ]
    )


def rasterize(pixels, faces, resolution):
    """
    Silhouette mask of a closed mesh from its projected vertices.

    Only one winding is filled: every line of sight through a closed surface crosses at least one
    triangle of each, so either set covers the silhouette, at half the cost. cv2.fillPoly is not used
    because it XORs overlapping polygons.
    """
    width, height = resolution
    triangles = pixels[faces]
    edge_1, edge_2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    triangles = triangles[edge_1[:, 0] * edge_2[:, 1] - edge_1[:, 1] * edge_2[:, 0] > 0]
    # cv2 puts pixel centres on integers; shift=4 keeps 1/16 px of the sub-pixel vertex positions.
    fixed = np.round((triangles - ec.pixel_centre) * 16).astype(np.int32)
    mask = np.zeros((height, width), np.uint8)
    for triangle in fixed:
        cv2.fillConvexPoly(mask, triangle, 1, lineType=cv2.LINE_8, shift=4)
    return mask


def mask_moments(mask):
    """Area in pixels and centroid in project() coordinates of a binary mask."""
    rows, columns = np.nonzero(mask)
    return len(rows), np.array([columns.mean(), rows.mean()]) + ec.pixel_centre


def iou(first, second):
    first, second = first.astype(bool), second.astype(bool)
    return float((first & second).sum() / max((first | second).sum(), 1))


def projection_jacobian(geometry, step=1.0):
    """d pixel / d world at the origin, in px per metre (2, 3), by central differences."""
    spacecraft_position, world_to_camera, fov, resolution = geometry
    columns = []
    for axis in np.eye(3):
        high = ec.project(step * axis, spacecraft_position, world_to_camera, fov, resolution)
        low = ec.project(-step * axis, spacecraft_position, world_to_camera, fov, resolution)
        columns.append((high - low) / (2 * step))
    return np.column_stack(columns)


def _predict_masks(vertices, faces, attitudes, permutation, scale, pivot, geometry):
    return [
        rasterize(project_many(to_world(vertices, attitude, permutation, scale, pivot), *geometry), faces, geometry[3])
        for attitude in attitudes
    ]


def _refine(measured, vertices, faces, attitudes, permutation, scale, pivot, geometry):
    """
    One Gauss-Newton step on (k, o) for a fixed P, from silhouette areas and centroids.

    Near-orthographic, area goes as k^2 and the centroid scales about the pivot's pixel with k, and a
    pivot shift delta moves the silhouette by -k J D^T P delta: a linear solve across the views.
    """
    jacobian = projection_jacobian(geometry)
    pivot_px = ec.project(np.zeros(3), *geometry)
    masks = _predict_masks(vertices, faces, attitudes, permutation, scale, pivot, geometry)
    predicted = [mask_moments(mask) for mask in masks]
    new_scale = scale * np.sqrt(sum(a for a, _ in measured) / max(sum(a for a, _ in predicted), 1))
    ratio = new_scale / scale
    lhs, rhs = [], []
    for (_, measured_centroid), (_, predicted_centroid), attitude in zip(measured, predicted, attitudes):
        dcm = rbk.mrp_to_dcm(np.asarray(attitude, float))
        lhs.append(-new_scale * jacobian @ dcm.T @ permutation)
        rhs.append(measured_centroid - pivot_px - ratio * (predicted_centroid - pivot_px))
    delta = np.linalg.lstsq(np.vstack(lhs), np.concatenate(rhs), rcond=None)[0]
    return new_scale, pivot + delta


def solve_registration(masks, attitudes, vertices, faces, geometry, initial_scale, iterations=3, finalists=3):
    """
    Signed permutation P, scale k (m per OBJ unit) and pivot o (OBJ units and frame) that best reproduce ``masks``.

    Every P gets one (k, o) step and an IoU; the best ``finalists`` are refined further. The score is
    the worst view's IoU.

    Returns:
        dict: permutation, scale, pivot, per-view iou, and the runner-up's score for the ambiguity.
    """
    measured = [mask_moments(mask) for mask in masks]
    candidates = []
    for permutation in signed_permutations():
        scale, pivot = _refine(measured, vertices, faces, attitudes, permutation, initial_scale, np.zeros(3), geometry)
        predicted = _predict_masks(vertices, faces, attitudes, permutation, scale, pivot, geometry)
        scores = [iou(mask, prediction) for mask, prediction in zip(masks, predicted)]
        candidates.append((min(scores), permutation, scale, pivot))
    candidates.sort(key=lambda candidate: -candidate[0])

    refined = []
    for _, permutation, scale, pivot in candidates[:finalists]:
        for _ in range(iterations - 1):
            scale, pivot = _refine(measured, vertices, faces, attitudes, permutation, scale, pivot, geometry)
        predicted = _predict_masks(vertices, faces, attitudes, permutation, scale, pivot, geometry)
        scores = [iou(mask, prediction) for mask, prediction in zip(masks, predicted)]
        refined.append((min(scores), permutation, scale, pivot, scores))
    refined.sort(key=lambda candidate: -candidate[0])

    score, permutation, scale, pivot, scores = refined[0]
    return {
        "permutation": permutation,
        "scale": float(scale),
        "pivot": pivot,
        "iou": scores,
        "runner_up_iou": float(refined[1][0]) if len(refined) > 1 else None,
    }


def scene_setup(extent_m, camera_range, shape_model):
    """
    Camera and one body slot, framing a bounding sphere of ``extent_m`` about the body origin.

    As in ec.scene_setup, the field of view follows the range so the body keeps its size in pixels.
    """
    if camera_range <= 1.05 * extent_m:
        raise ValueError(f"camera range {camera_range:.0f} m is inside the body's bounding sphere ({extent_m:.0f} m)")
    base_range = extent_m / np.tan(frame_fill * min(ec.base_fov) / 2)
    fov = tuple(2 * np.arctan(np.tan(angle / 2) * base_range / camera_range) for angle in ec.base_fov)

    scene = cielim.Scene()
    scene.set_lens_params(fov=fov)
    scene.set_sensor_params(resolution=(2000, 1500), exposure=5e-4)
    scene.set_camera_params(grayscale=True)

    scene.add_celestial_body(target_name)  # index central_body_index; index 0 is the sun
    scene.set_celestial_body_params(
        central_body_index,
        position=(0.0, 0.0, 0.0),
        mesh_shape=shape_model,
        mesh_brdf="Lambertian",
        mesh_radius=mesh_radius,
        albedo=0.2,
    )
    scene.set_spacecraft_params(position=(0.0, 0.0, -camera_range), velocity=(0.0, 1000.0, 0.0))
    return scene


def scene_geometry(scene):
    """(spacecraft position, world to camera, fov, resolution): the arguments of ec.project after the point."""
    world_to_camera, fov, resolution = ec.camera_frame(scene)
    return np.array(scene.get_scene().spacecraft.position), world_to_camera, fov, resolution


def _set_body(scene, mesh_attitude, shape, distortions=(1.0, 1.0, 1.0)):
    scene.set_celestial_body_params(
        central_body_index,
        mesh_shape=shape,
        mesh_radius=mesh_radius,
        mesh_distortions=tuple(distortions),
        mesh_attitude=tuple(mesh_attitude),
    )


def _launch():
    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    return connector, launcher


def register_mesh(connector, body, vertices, faces, km_per_unit, output_directory):
    """
    Render <body>_normalized near zero phase at registration_attitudes and fit the OBJ to it.

    The first guess for k takes the engine's meshes to be normalized to mean radius mesh_radius
    ("~1000 units radius"), read as the volume-equivalent radius. The scene frames 1.5x that guess
    of the bounding sphere so a wrong guess still fits. Writes registration.png (rendered masks with
    the registered OBJ outline) and, if every view reaches registration_min_iou, registration.json.

    Returns:
        dict: the registration, JSON-ready.
    """
    shape_model = bodies[body]["shape_model"]
    os.makedirs(output_directory, exist_ok=True)
    volume, _, _ = mesh_moments(vertices, faces)
    initial_scale = mesh_radius / (3 * volume / (4 * np.pi)) ** (1 / 3)
    extent_guess = 1.5 * initial_scale * np.linalg.norm(vertices, axis=1).max()
    scene = scene_setup(extent_guess, default_range_radii * mesh_radius, shape_model)
    geometry = scene_geometry(scene)
    r_hat = geometry[0] / np.linalg.norm(geometry[0])
    scene.set_celestial_body_params(0, position=tuple(ec.astronomical_unit * r_hat))  # sun behind the camera

    masks = []
    for attitude in registration_attitudes:
        _set_body(scene, attitude, shape_model)
        image, _ = ec._render(connector, scene)
        gray = ec.to_gray(image)
        extent = ec.lit_extent(gray, registration_threshold)
        if extent is None or ec._touches_edge([extent], geometry[3]):
            raise RuntimeError(f"registration view at attitude {attitude} is empty or touches the frame edge")
        masks.append((gray > registration_threshold).astype(np.uint8))

    solution = solve_registration(masks, registration_attitudes, vertices, faces, geometry, initial_scale)
    predicted = _predict_masks(
        vertices, faces, registration_attitudes, solution["permutation"], solution["scale"], solution["pivot"], geometry
    )
    _plot_registration(masks, predicted, solution, os.path.join(output_directory, "registration.png"))

    registration = {
        "shape_model": shape_model,
        "obj": bodies[body]["obj"],
        "km_per_obj_unit": km_per_unit,
        "mesh_radius_m": mesh_radius,
        "permutation": solution["permutation"].tolist(),
        "scale_m_per_obj_unit": solution["scale"],
        "scale_per_mesh_radius": solution["scale"] / mesh_radius,
        "pivot_obj": solution["pivot"].tolist(),
        "iou": solution["iou"],
        "runner_up_iou": solution["runner_up_iou"],
        "attitudes_mrp": [list(a) for a in registration_attitudes],
        "threshold": registration_threshold,
    }
    pivot_m = solution["pivot"] * km_per_unit * 1e3
    print(
        f"Registration: P = {registration['permutation']}  pivot = {np.round(pivot_m, 2).tolist()} m  "
        f"IoU = {np.round(solution['iou'], 4).tolist()}  (runner-up {solution['runner_up_iou']:.4f})"
    )
    if min(solution["iou"]) < registration_min_iou:
        raise RuntimeError(
            f"registration IoU {min(solution['iou']):.4f} is below {registration_min_iou}; the OBJ may not be the "
            f"source of {shape_model}. See {output_directory}/registration.png"
        )
    with open(registration_path(body), "w") as handle:
        json.dump(registration, handle, indent=2)
    return registration


def _plot_registration(masks, predicted, solution, output_path):
    figure, axes = plt.subplots(1, len(masks), figsize=(2.2 * len(masks), 2.4), dpi=200)
    for ax, mask, prediction, score in zip(axes, masks, predicted, solution["iou"]):
        rows, columns = np.nonzero(mask | prediction)
        pad = 10
        y1, y2, x1, x2 = rows.min() - pad, rows.max() + pad, columns.min() - pad, columns.max() + pad
        overlay = np.zeros((y2 - y1, x2 - x1, 3))
        overlay[..., 0] = mask[y1:y2, x1:x2]
        overlay[..., 1] = prediction[y1:y2, x1:x2]
        overlay[..., 2] = mask[y1:y2, x1:x2]
        ax.imshow(overlay, interpolation="nearest")
        ax.set_title(f"IoU {score:.4f}")
        ax.axis("off")
    figure.suptitle("Rendered (magenta) against registered OBJ (green); white is both")
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def load_registration(body):
    with open(registration_path(body)) as handle:
        registration = json.load(handle)
    if registration["shape_model"] != bodies[body]["shape_model"]:
        raise ValueError(f"{registration_path(body)} registers {registration['shape_model']}")
    return registration


def body_model(fit, registration, vertices):
    """P, k at mesh_radius, o, and the lengths the scene is sized from, in world metres."""
    permutation = np.array(registration["permutation"], float)
    scale = registration["scale_per_mesh_radius"] * mesh_radius
    pivot = np.array(registration["pivot_obj"], float)
    return {
        "permutation": permutation,
        "scale": scale,
        "pivot": pivot,
        "extent_m": float(scale * np.linalg.norm(vertices - pivot, axis=1).max()),
        "mean_radius_m": float(scale * np.mean(fit["semi_axes"])),
        "semi_axes_m": scale * fit["semi_axes"],
    }


def shape_model_com_cob_analysis(
    body: str = default_body,
    number_of_samples: int = 200,
    seed: int | None = None,
    save_first: int = 100,
    range_radii: float = default_range_radii,
    register: bool = False,
    ellipsoid: str = "radial",
    output_directory: str | None = None,
) -> dict:
    """
    Render body/ellipsoid pairs at random lighting and score the three CoM predictions.

    Args:
        body (str): A key of ``bodies``.
        number_of_samples (int): Pairs to render. Zero only registers (if needed) and returns.
        seed (int, optional): Seed for the draws.
        save_first (int): Write the pair figure and frames for this many samples.
        range_radii (float): Spacecraft range in mean semi-axes of the ellipsoid.
        register (bool): Re-run the registration even if registration.json exists.
        ellipsoid (str): "radial" (least-squares fit) or "dimensions" (published), see body_ellipsoid.
        output_directory (str, optional): Defaults to examples/images-<body>-com-cob/, with a
            -dimensions suffix for the published dimensions.

    Returns:
        dict: The per-sample rows plus the run's settings.
    """
    directory_path = output_directory or output_directory_for(body, ellipsoid)
    os.makedirs(directory_path, exist_ok=True)

    vertices, faces, km_per_unit = load_body_mesh(body)
    fit = body_ellipsoid(body, vertices, faces, km_per_unit, ellipsoid)
    connector, launcher = _launch()
    try:
        if register or not os.path.exists(registration_path(body)):
            registration = register_mesh(connector, body, vertices, faces, km_per_unit, directory_path)
        else:
            registration = load_registration(body)
        model = body_model(fit, registration, vertices)
        print(
            f"{bodies[body]['display_name']} {ellipsoid} ellipsoid: semi-axes "
            f"{np.round(fit['semi_axes'] * km_per_unit, 4).tolist()} km, centroid "
            f"{np.round(fit['centroid'] * km_per_unit * 1e3, 1).tolist()} m from the OBJ origin, "
            f"ellipsoid/mesh volume {fit['volume_ratio']:.3f}"
        )

        rows, skipped = [], 0
        if number_of_samples:
            rows, skipped = _run_samples(
                connector, body, fit, model, number_of_samples, seed, save_first, range_radii, directory_path
            )
    finally:
        connector.disconnect()
        launcher.terminate()

    summary = {
        "body": body,
        "display_name": bodies[body]["display_name"],
        "number_of_samples": number_of_samples,
        "kept": len(rows),
        "skipped": skipped,
        "seed": seed,
        "mesh_radius_m": mesh_radius,
        "range_radii": range_radii,
        "lit_threshold": lit_threshold,
        "ellipsoid": {
            "kind": ellipsoid,
            "semi_axes_km": (fit["semi_axes"] * km_per_unit).tolist(),
            "dimensions_km": list(bodies[body]["dimensions_km"]),
            "km_per_obj_unit": km_per_unit,
            "centroid_obj": fit["centroid"].tolist(),
            "principal_axes": fit["principal_axes"].tolist(),
            "mesh_volume_km3": fit["volume"] * km_per_unit**3,
            "volume_ratio": fit["volume_ratio"],
        },
        "registration": registration,
        "mean_radius_m": model["mean_radius_m"],
        "rows": rows,
    }
    if number_of_samples:
        with open(os.path.join(directory_path, "run.json"), "w") as handle:
            json.dump(summary, handle, indent=2)
        print(f"Kept {len(rows)} of {number_of_samples} samples ({skipped} skipped) -> {directory_path}")
    return summary


def _run_samples(connector, body, fit, model, number_of_samples, seed, save_first, range_radii, directory_path):
    shape_model = bodies[body]["shape_model"]
    permutation, scale, pivot = model["permutation"], model["scale"], model["pivot"]
    camera_range = range_radii * model["mean_radius_m"]
    scene = scene_setup(model["extent_m"], camera_range, shape_model)
    geometry = scene_geometry(scene)
    spacecraft_position, world_to_camera, fov, resolution = geometry
    ifov = fov[0] / resolution[0]
    rho = model["mean_radius_m"]
    encoding_gamma = scene.get_scene().camera.sensorModel.gamma or 2.2
    radius_px = rho / np.linalg.norm(spacecraft_position) / ifov

    def to_pixel(point):
        return ec.project(point, *geometry)

    pivot_px = to_pixel(np.zeros(3))
    r_hat = spacecraft_position / np.linalg.norm(spacecraft_position)
    rng = np.random.default_rng(seed)
    rows, skipped = [], 0
    for idx in range(number_of_samples):
        phase_angle = np.radians(rng.uniform(*phase_range_deg))
        azimuth = rng.uniform(0.0, 2 * np.pi)
        attitude = rbk.dcm_to_mrp(Rotation.random(random_state=rng.integers(2**31)).as_matrix())

        # The phase is set from the body origin; the offsets below are taken from each body's own centre.
        sun_heading = ec.sun_heading_for_phase(r_hat, phase_angle, azimuth)
        sun_position = ec.astronomical_unit * sun_heading
        scene.set_celestial_body_params(0, position=tuple(sun_position))

        _set_body(scene, attitude, shape_model)
        body_image, engine_cob_body = ec._render(connector, scene)

        frames = {"body": ec.to_gray(body_image)}
        extents = [ec.lit_extent(frame) for frame in frames.values()]
        if any(e is None for e in extents) or ec._touches_edge(extents, resolution):
            skipped += 1
            continue

        # The body's CoM is the registered centroid, not the pivot.
        centres = {"body": to_world(fit["centroid"], attitude, permutation, scale, pivot)}
        shape_matrix = world_shape_matrix(fit, permutation, scale, attitude)
        views = {
            label: (spacecraft_position - c) / np.linalg.norm(spacecraft_position - c) for label, c in centres.items()
        }
        suns = {label: (sun_position - c) / np.linalg.norm(sun_position - c) for label, c in centres.items()}
        offsets = {
            "body_sphere_model": ec.sphere_offset(views["body"], suns["body"], rho),
            "body_ellipsoid_model": ec.ellipsoid_offset(views["body"], suns["body"], shape_matrix),
        }
        measured = {label: ec.binary_centroid(frame) for label, frame in frames.items()}
        true_com = {label: to_pixel(centre) for label, centre in centres.items()}
        sunline_px = to_pixel(centres["body"] + offsets["body_sphere_model"]) - true_com["body"]
        sunline_px = sunline_px / np.linalg.norm(sunline_px) if np.linalg.norm(sunline_px) > 1e-9 else np.zeros(2)

        results = {}
        for name in cases:
            label = body_of[name]
            predicted_cob = to_pixel(centres[label] + offsets[name])
            predicted_com = measured[label] - (predicted_cob - true_com[label])
            error = predicted_com - true_com[label]  # equals measured minus predicted CoB
            results[name] = {
                "predicted_cob_px": predicted_cob.tolist(),
                "predicted_com_px": predicted_com.tolist(),
                "residual_px": error.tolist(),
                "error_px": float(np.linalg.norm(error)),
                "error_arcsec": float(np.degrees(np.linalg.norm(error) * ifov) * 3600),
                "error_fraction_of_radius": float(np.linalg.norm(error) / radius_px),
                "along_sunline_px": float(np.dot(error, sunline_px)),
            }

        row = {
            "sample": idx,
            "phase_angle_deg": float(np.degrees(phase_angle)),
            "equivalent_phase_angle_deg": float(
                np.degrees(ec.equivalent_phase_angle(views["body"], suns["body"], shape_matrix))
            ),
            "azimuth_deg": float(np.degrees(azimuth)),
            "body_attitude_mrp": np.asarray(attitude).tolist(),
            "sun_heading_N": sun_heading.tolist(),
            "mean_radius_m": rho,
            "apparent_radius_px": float(radius_px),
            "camera_ifov": ifov,
            "pivot_px": pivot_px.tolist(),
            "sunline_px": sunline_px.tolist(),
            "true_com_px": {label: point.tolist() for label, point in true_com.items()},
            "measured_cob_px": {label: point.tolist() for label, point in measured.items()},
            "photometric_cob_px": {
                label: ec.photometric_centroid(frame, gamma=encoding_gamma).tolist() for label, frame in frames.items()
            },
            "engine_cob_px": {"body": list(engine_cob_body)},
            **results,
        }
        rows.append(row)

        if idx < save_first:
            pair_path = os.path.join(directory_path, f"sample{idx:03d}_pair.png")
            plot_sample_pair(frames, row, bodies[body]["display_name"], pair_path)
            for label, frame in frames.items():
                cv2.imwrite(os.path.join(directory_path, f"sample{idx:03d}_{label}.png"), frame)

        print(
            f"[{idx:03d}] phase {row['phase_angle_deg']:6.1f} (bar {row['equivalent_phase_angle_deg']:6.1f}) deg  "
            "error px: " + "  ".join(f"{name} {results[name]['error_px']:6.2f}" for name in cases)
        )
    return rows, skipped


_predictions = {
    "body": [
        ("body_sphere_model", "sphere model", colorList[5]),
        ("body_ellipsoid_model", "ellipsoid model", "#00d0ff"),
    ],
}


def _mark(ax, row, label, zoomed=False):
    """True CoM, measured CoB and each predicted CoM; zoomed panels join each prediction to the truth."""
    com = np.array(row["true_com_px"][label])
    scale = 1.6 if zoomed else 1.0
    ax.plot(*com, "o", mfc="none", mec="#40ff40", markersize=6 * scale, markeredgewidth=1.0, label="true CoM")
    ax.plot(
        *row["measured_cob_px"][label],
        "+",
        color=colorList[8],
        markersize=9 * scale,
        markeredgewidth=1.2,
        label="measured CoB",
    )
    for name, description, color in _predictions[label]:
        predicted = np.array(row[name]["predicted_com_px"])
        if zoomed:
            ax.plot(*np.column_stack([predicted, com]), "--", color=color, linewidth=0.8)
        ax.plot(
            *predicted,
            "x",
            color=color,
            markersize=7 * scale,
            markeredgewidth=1.2,
            label=f"predicted CoM, {description}",
        )


def plot_sample_pair(frames, row, display_name, output_path):
    """
    The body with both predictions: the whole body on the left, and on the right a zoom on the markers
    with a dashed line from each predicted CoM to the true CoM, whose length is the error in the title.
    """
    label = "body"
    frame = frames[label]
    width, height, x0, y0 = ec.lit_extent(frame)
    pad = 25
    x1, y1, x2, y2 = x0 - pad, y0 - pad, x0 + width + pad, y0 + height + pad

    points = np.array(
        [row["true_com_px"][label], row["measured_cob_px"][label]]
        + [row[name]["predicted_com_px"] for name, _, _ in _predictions[label]]
    )
    centre = 0.5 * (points.min(axis=0) + points.max(axis=0))
    half = max(1.4 * np.abs(points - centre).max() + 3.0, 8.0)

    figure, (whole, zoom) = plt.subplots(1, 2, figsize=(7, 3.6), dpi=200)
    ec._show(whole, frame, x1, x2, y1, y2)
    _mark(whole, row, label)
    whole.add_patch(
        plt.Rectangle(centre - half, 2 * half, 2 * half, fill=False, edgecolor="#40ff40", linewidth=0.6, linestyle=":")
    )
    errors = ", ".join(f"{d}: {row[n]['error_px']:.2f} px" for n, d, _ in _predictions[label])
    whole.set_title(f"{display_name}\n{errors}")
    whole.legend(loc="lower left", fontsize=5, framealpha=0.6)

    cx, cy = centre
    ec._show(zoom, frame, cx - half - 1, cx + half + 1, cy - half - 1, cy + half + 1)
    _mark(zoom, row, label, zoomed=True)
    zoom.set_xlim(cx - half, cx + half)
    zoom.set_ylim(cy + half, cy - half)
    zoom.set_title(f"zoom ({2 * half:.0f} px window)")
    for ax in (whole, zoom):
        ax.set_xlabel("x (px)")
    whole.set_ylabel("y (px)")
    figure.suptitle(
        f"sample {row['sample']}  phase {row['phase_angle_deg']:.1f} deg  "
        f"(equivalent {row['equivalent_phase_angle_deg']:.1f} deg)  azimuth {row['azimuth_deg']:.0f} deg"
    )
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)
    return output_path


def replot_pairs(body=default_body, ellipsoid="radial", output_directory=None):
    """Rebuild the pair figures from a finished run's saved frames and run.json, without re-rendering."""
    directory_path = output_directory or output_directory_for(body, ellipsoid)
    with open(os.path.join(directory_path, "run.json")) as handle:
        summary = json.load(handle)
    written = []
    for row in summary["rows"]:
        stem = os.path.join(directory_path, f"sample{row['sample']:03d}")
        paths = {"body": f"{stem}_body.png"}
        if not all(os.path.exists(path) for path in paths.values()):
            continue
        frames = {label: cv2.imread(path, cv2.IMREAD_GRAYSCALE) for label, path in paths.items()}
        written.append(plot_sample_pair(frames, row, summary["display_name"], f"{stem}_pair.png"))
    return written


sweep_thresholds = (1, 2, 3, 5, 8, 12, 16, 20, 25, 30, 40, 60, 80, 100)


def threshold_sweep(summary, output_directory=None, thresholds=sweep_thresholds):
    """
    Re-threshold a finished run's saved frames and score every case at each lit threshold.

    Only the samples whose frames were saved (save_first) are used; the predictions do not depend on
    the threshold, so nothing is re-rendered. Writes error-by-threshold.png and returns, per case, an
    (samples, thresholds) array of errors in px (nan where nothing is lit).
    """
    kind = summary["ellipsoid"].get("kind", "dimensions")  # runs before the radial fit have no kind
    directory_path = output_directory or output_directory_for(summary["body"], kind)
    frames, rows = {}, []
    for row in summary["rows"]:
        stem = os.path.join(directory_path, f"sample{row['sample']:03d}")
        paths = {"body": f"{stem}_body.png"}
        if all(os.path.exists(path) for path in paths.values()):
            frames[row["sample"]] = {label: cv2.imread(path, cv2.IMREAD_GRAYSCALE) for label, path in paths.items()}
            rows.append(row)
    if not rows:
        raise ValueError(f"no saved frames in {directory_path}")

    errors = {name: np.full((len(rows), len(thresholds)), np.nan) for name in cases}
    for i, row in enumerate(rows):
        for name in cases:
            frame = frames[row["sample"]][body_of[name]]
            predicted = np.array(row[name]["predicted_cob_px"])
            for j, threshold in enumerate(thresholds):
                point = ec.binary_centroid(frame, threshold)
                if point is not None:
                    errors[name][i, j] = np.linalg.norm(point - predicted)

    descriptions = case_descriptions(summary["display_name"])
    case_colors = dict(zip(cases, (colorList[5], "#00a0d0")))
    plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
    for name, description in descriptions.items():
        plt.plot(
            thresholds,
            np.nanmedian(errors[name], axis=0),
            marker=".",
            color=case_colors[name],
            label=f"{description}, median",
        )
        plt.plot(
            thresholds,
            np.nanpercentile(errors[name], 95, axis=0),
            linestyle="--",
            color=case_colors[name],
            label=f"{description}, 95th percentile",
        )
    plt.axvline(summary["lit_threshold"], color="0.6", linewidth=0.8)
    plt.yscale("log")
    plt.title(f"{summary['display_name']}: CoM prediction error against lit threshold ({len(rows)} samples)")
    plt.xlabel("Lit threshold (DN)")
    plt.ylabel("Prediction error (px)")
    plt.legend(fontsize=5)
    plt.tight_layout()
    plt.savefig(os.path.join(directory_path, "error-by-threshold.png"))
    plt.close()

    phases = np.array([row["phase_angle_deg"] for row in rows])
    print(f"threshold sweep over {len(rows)} saved samples: median error (px)")
    print(f"{'threshold (DN)':38s}" + "".join(f"{t:>7d}" for t in thresholds))
    for name, description in descriptions.items():
        print(f"{description:38s}" + "".join(f"{v:7.1f}" for v in np.nanmedian(errors[name], axis=0)))
        for low, high in phase_bins_deg:
            inside = (phases >= low) & (phases < high)
            if inside.any():
                cells = np.nanmedian(errors[name][inside], axis=0)
                label = f"  {low:.0f}-{high:.0f} deg (n={inside.sum()})"
                print(f"{label:38s}" + "".join(f"{v:7.1f}" for v in cells))
    return errors


def sunline_split(row, name):
    """Error of one case along (+ sunward) and across the projected sunline, in px; nan at zero phase."""
    along = np.array(row["sunline_px"])
    if np.linalg.norm(along) < 1e-9:
        return np.nan, np.nan
    across = np.array([along[1], -along[0]])
    residual = np.array(row[name]["residual_px"])
    return float(residual @ along), float(residual @ across)


def _binned(x, y, edges):
    centres, medians, upper = [], [], []
    for low, high in zip(edges[:-1], edges[1:]):
        inside = (x >= low) & (x < high)
        if inside.sum() >= 3:
            centres.append(0.5 * (low + high))
            medians.append(np.median(y[inside]))
            upper.append(np.percentile(y[inside], 95))
    return np.array(centres), np.array(medians), np.array(upper)


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


def plot_results(summary, output_directory=None, show_plots=False):
    """Error against phase, equivalent phase and azimuth, the along/across sunline split and histograms."""
    rows = summary["rows"]
    if not rows:
        raise ValueError("no samples to plot")
    kind = summary["ellipsoid"].get("kind", "dimensions")  # runs before the radial fit have no kind
    directory_path = output_directory or output_directory_for(summary["body"], kind)
    descriptions = case_descriptions(summary["display_name"])
    case_colors = dict(zip(cases, (colorList[5], "#00a0d0")))
    errors = {name: np.array([row[name]["error_px"] for row in rows]) for name in cases}

    for key, label, filename, edges in (
        ("phase_angle_deg", "Phase angle (deg)", "error-by-phase.png", np.arange(0, 181, 15)),
        (
            "equivalent_phase_angle_deg",
            "Equivalent phase angle (deg)",
            "error-by-equivalent-phase.png",
            np.arange(0, 181, 15),
        ),
        ("azimuth_deg", "Sun azimuth about the boresight (deg)", "error-by-azimuth.png", np.arange(0, 361, 30)),
    ):
        x = np.array([row[key] for row in rows])
        plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
        for name, description in descriptions.items():
            plt.scatter(x, errors[name], marker=".", s=8, alpha=0.6, color=case_colors[name], label=description)
            centres, medians, upper = _binned(x, errors[name], edges)
            plt.plot(centres, medians, "-", color=case_colors[name], linewidth=1.2)
            plt.plot(centres, upper, ":", color=case_colors[name], linewidth=0.8)
        plt.axhline(1.0, linewidth=0.8, linestyle="--", color="0.5", label="1 px")
        plt.yscale("log")
        plt.title(f"{summary['display_name']}: CoM prediction error (lines: binned median, dotted 95th percentile)")
        plt.xlabel(label)
        plt.ylabel("Prediction error (px)")
        plt.legend(fontsize=5)
        plt.tight_layout()
        plt.savefig(os.path.join(directory_path, filename))
        plt.close()

    phases = np.array([row["phase_angle_deg"] for row in rows])
    figure, axes = plt.subplots(2, 1, figsize=(5, 5), dpi=200, sharex=True)
    for name, description in descriptions.items():
        split = np.array([sunline_split(row, name) for row in rows])
        for ax, values in zip(axes, split.T):
            ax.scatter(phases, values, marker=".", s=10, color=case_colors[name], label=description)
    for ax, label in zip(axes, ("along sunline (px, + sunward)", "across sunline (px)")):
        ax.axhline(0.0, color="0.6", linewidth=0.6)
        ax.set_ylabel(label)
    axes[0].set_title("Measured minus predicted CoB, split along and across the sunline")
    axes[0].legend(fontsize=5)
    axes[1].set_xlabel("Phase angle (deg)")
    figure.tight_layout()
    figure.savefig(os.path.join(directory_path, "error-along-across-sunline.png"))
    plt.close(figure)

    plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
    along = {name: np.array([row[name]["along_sunline_px"] for row in rows]) for name in cases}
    bins = np.linspace(*np.percentile(np.concatenate(list(along.values())), (0.5, 99.5)), 40)
    curve = np.linspace(bins[0], bins[-1], 400)
    print(f"{'along-sunline error (px)':38s}{'mean':>8s}{'sigma':>8s}{'skew':>8s}{'ex.kurt':>8s}")
    for name, description in descriptions.items():
        moments = gaussianity(along[name])
        plt.hist(
            along[name],
            bins=bins,
            histtype="step",
            color=case_colors[name],
            label=f"{description}: $\\mu$ = {moments['mean']:.1f}, $\\sigma$ = {moments['std']:.1f} px, "
            f"skew {moments['skewness']:.2f}, ex. kurt. {moments['excess_kurtosis']:.2f}",
        )
        # The Gaussian with the same mean and sigma, scaled to counts per bin.
        density = stats.norm.pdf(curve, moments["mean"], moments["std"]) * len(along[name]) * (bins[1] - bins[0])
        plt.plot(curve, density, "--", color=case_colors[name], linewidth=0.7)
        plt.axvline(moments["mean"], color=case_colors[name], linewidth=0.8, linestyle=":")
        print(
            f"{description:38s}{moments['mean']:8.2f}{moments['std']:8.2f}{moments['skewness']:8.2f}"
            f"{moments['excess_kurtosis']:8.2f}"
        )
    plt.axvline(0.0, color="0.6", linewidth=0.6)
    plt.title("Measured minus predicted CoB along the sunline (dashed: Gaussian, same $\\mu$ and $\\sigma$)")
    plt.xlabel("Error (px, + sunward)")
    plt.ylabel("Number of runs")
    plt.legend(fontsize=4.5, loc="upper left")
    plt.tight_layout()
    plt.savefig(os.path.join(directory_path, "correction-errors-hist.png"))
    plt.close()

    print(f"apparent mean radius {rows[0]['apparent_radius_px']:.0f} px")
    header = "".join(f"{f'{low:.0f}-{high:.0f} deg':>20s}" for low, high in phase_bins_deg)
    print(f"{'median / 95% error (px)':38s}{'all':>20s}{header}")
    for name, description in descriptions.items():
        cells = []
        for low, high in ((0.0, 180.0), *phase_bins_deg):
            inside = (phases >= low) & (phases < high)
            values = errors[name][inside]
            cells.append(
                f"{np.median(values):7.2f} / {np.percentile(values, 95):6.2f} (n={inside.sum():3d})"
                if len(values)
                else "-"
            )
        print(f"{description:38s}" + "".join(f"{cell:>20s}" for cell in cells))

    if show_plots:
        plt.show()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CoM from CoB on a shape model: dimensions ellipsoid vs mean radius")
    parser.add_argument("--body", choices=sorted(bodies), default=default_body)
    parser.add_argument(
        "--ellipsoid", choices=ellipsoid_choices, default="radial", help="radial fit or published dimensions"
    )
    parser.add_argument("--samples", type=int, default=200, help="body/ellipsoid pairs to render")
    parser.add_argument("--figures", type=int, default=100, help="samples to save a pair figure for")
    parser.add_argument(
        "--range-radii", type=float, default=default_range_radii, help="range in mean semi-axes of the ellipsoid"
    )
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--register", action="store_true", help="re-run the OBJ-to-engine registration")
    parser.add_argument("--show", action="store_true", help="show the plots")
    parser.add_argument("--replot", action="store_true", help="only rebuild the figures from the last run")
    parser.add_argument(
        "--threshold-sweep", action="store_true", help="only re-score the last run's saved frames over lit thresholds"
    )
    args = parser.parse_args()

    if args.threshold_sweep:
        with open(os.path.join(output_directory_for(args.body, args.ellipsoid), "run.json")) as handle:
            threshold_sweep(json.load(handle))
        raise SystemExit

    if args.replot:
        for path in replot_pairs(args.body, args.ellipsoid):
            print(f"Wrote {path}")
        with open(os.path.join(output_directory_for(args.body, args.ellipsoid), "run.json")) as handle:
            plot_results(json.load(handle), show_plots=args.show)
        raise SystemExit

    run = shape_model_com_cob_analysis(
        body=args.body,
        ellipsoid=args.ellipsoid,
        number_of_samples=args.samples,
        seed=args.seed,
        save_first=args.figures,
        range_radii=args.range_radii,
        register=args.register,
    )
    if run["rows"]:
        plot_results(run, show_plots=args.show)
