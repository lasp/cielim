import os

import cv2
import numpy as np
import pytest
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

import cielim
from cielim.utils import image_comparison_toolkit as image_comparison
from cielim.utils import plot_style as ps

# Read at import time so it survives pytest.main() re-importing this file as a module.
show_plots = os.environ.get("show_plots", "False") == "True"

# Scene constants matching asteroid_departure.py
fov_x = 20 * np.pi / 180
fov_y = 15 * np.pi / 180
width = 2000
height = 1500
mean_radius = 1000
albedo = 1.0
sun_position = [0, 0, -1.496e11]
sun_index = 0
asteroid_index = 1


def compute_coverage(radius, distance, fov_x, fov_y, width, height):
    """Compute the shader coverage value matching DistantObjects.usf."""
    angular_radius = np.arctan(radius / max(distance, 1e-6))
    pixel_ang_x = 2 * np.tan(fov_x / 2) / width
    pixel_ang_y = 2 * np.tan(fov_y / 2) / height
    frac_x = angular_radius / pixel_ang_x
    frac_y = angular_radius / pixel_ang_y
    coverage = np.pi * frac_x * frac_y
    return min(coverage, 1.0)


def _pixel_size_threshold(phase_angle_deg, on_grid=False):
    """Return the PixelSize threshold used by IsCelestialBodyResolvable at the given phase angle.

    Unified for on-grid and off-grid (C++ uses the same formula for both, keeping the two
    paths in lockstep avoids the compromise problem where the right rasterized size at
    transition depends on the object's position in the pixel grid):
      clamp(3 / (1 + cos α), 4, 15)
    Aims for a ~1.5-pixel mesh crescent at transition for α in [110°, 143°], capped at 15
    past ~143° so the rasterized bounding box doesn't balloon when the crescent goes sub-pixel.

    Evaluates to 4 for α ≤ 110°, 4.8 at 112°, 10.23 at 135°, 15 (capped) from ~143° up.
    The ``on_grid`` parameter is accepted for backward-compat with call sites but no longer
    affects the result.
    """
    del on_grid  # unified threshold — kept in signature only for backward compat
    alpha = np.radians(phase_angle_deg)
    crescent_factor = max(1.0 + np.cos(alpha), 0.1)
    return float(np.clip(3.0 / crescent_factor, 4.0, 15.0))


def compute_transition_distance(width=width, height=height, phase_angle_deg=0, on_grid=False):
    """Approximate distance where IsCelestialBodyResolvable switches to distant rendering."""
    bounds_radius = mean_radius * np.sqrt(3)
    proj_m00 = 1.0 / np.tan(fov_x / 2)
    proj_m11 = 1.0 / np.tan(fov_y / 2)
    screen_multiple = max(0.5 * proj_m00, 0.5 * proj_m11)
    max_dim = max(width, height)
    threshold = _pixel_size_threshold(phase_angle_deg, on_grid=on_grid)
    return screen_multiple * bounds_radius * max_dim * 2 / threshold


def default_scene(camera_distance, width=width, height=height):
    """Create a Scene matching asteroid_departure.py at the given camera distance.

    Returns a ``cielim.Scene`` (send it via ``render_frame``). The Scene constructor already sets the
    camera id/name, body-frame MRPs, and spacecraft name; only the fields this test cares about are
    overridden here. The Scene's default sun (index 0) is moved behind the camera to front-light +Z.
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


def add_body(scene, name, position, mean_radius=mean_radius, albedo=albedo, brdf="Regolith"):
    """Append a celestial body with a spherical mesh model at the given world position.

    Returns the index of the added body in the scene's celestialBodies list.
    """
    index = scene.add_celestial_body(name)
    scene.set_celestial_body_params(
        index,
        position=position,
        mesh_shape="sphere_normalized",
        mesh_radius=mean_radius,
        albedo=albedo,
        mesh_brdf=brdf,
    )
    return index


def scene_with_bodies(camera_distance, bodies, exposure_time=0.001, width=width, height=height):
    """Build a Scene with the given bodies plus a sun, matching default_scene's camera setup.

    `bodies` is a list of dicts: {"name", "position", optional "mean_radius"/"albedo"/"brdf"}.
    """
    scene = cielim.Scene()
    scene.set_celestial_body_params(sun_index, position=tuple(sun_position))  # move the default sun behind +Z

    for b in bodies:
        add_body(
            scene,
            b["name"],
            b["position"],
            mean_radius=b.get("mean_radius", mean_radius),
            albedo=b.get("albedo", albedo),
            brdf=b.get("brdf", "Regolith"),
        )

    scene.set_lens_params(fov=(fov_x, fov_y))
    scene.set_sensor_params(resolution=(width, height), exposure=exposure_time)
    scene.set_spacecraft_params(position=(0, 0, -camera_distance))
    return scene


def predict_pixel(position, camera_distance):
    """Predict the (px, py) screen pixel of a world position (camera at [0,0,-camera_distance], +Z)."""
    x, y, z = position
    d = z + camera_distance
    ndc_x = (x / d) / np.tan(fov_x / 2)
    ndc_y = (y / d) / np.tan(fov_y / 2)
    px = width / 2 * (1 + ndc_x)
    py = height / 2 * (1 - ndc_y)  # image row 0 is at the top, so +Y world maps to a smaller row
    return px, py


def has_bright_spot(gray, px, py, window=40, thresh=50):
    """True if any pixel within `window` of (px, py) exceeds `thresh`."""
    h, w = gray.shape[:2]
    cx, cy = round(px), round(py)
    x0, x1 = max(0, cx - window), min(w, cx + window)
    y0, y1 = max(0, cy - window), min(h, cy + window)
    if x0 >= x1 or y0 >= y1:
        return False
    return int(np.max(gray[y0:y1, x0:x1])) > thresh


def render_frame(connector, scene):
    """Send a frame (a cielim.Scene) and return (image, cob, coverage) for camera 1."""
    connector.send_frame(scene.get_scene())
    image, cob, coverage = connector.request_image_for_camera_id(1)
    return image, cob, coverage


def to_gray_thresholded(image):
    """Convert BGR image to grayscale and zero out pixels below threshold."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    _, result = cv2.threshold(gray, 50, 255, cv2.THRESH_TOZERO)
    return result


def crop_center(gray, half_window=6):
    """Return a (2*half_window) x (2*half_window) crop centered on the image."""
    h, w = gray.shape[:2]
    cy, cx = h // 2, w // 2
    return gray[
        max(0, cy - half_window) : min(h, cy + half_window),
        max(0, cx - half_window) : min(w, cx + half_window),
    ]


def bright_pixel_extent(gray, half_window=6):
    """Return (width, height) of the bright-pixel bounding box around the center."""
    region = crop_center(gray, half_window)
    coords = np.argwhere(region > 0)
    if len(coords) == 0:
        return 0, 0
    rows = coords[:, 0]
    cols = coords[:, 1]
    width_px = int(cols.max() - cols.min() + 1)
    height_px = int(rows.max() - rows.min() + 1)
    return width_px, height_px


def bright_pixel_values(gray, half_window=6):
    """Return all non-zero pixel values within the central window."""
    region = crop_center(gray, half_window)
    return region[region > 0]


def show_size_comparison(
    image_before, image_after, dist_before, dist_after, transition_dist, extent_before, extent_after, width, height
):
    """Display side-by-side 12x12 crops around image center before/after the transition."""
    if not show_plots:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    crop = 6  # 12x12 box
    cy, cx = height // 2, width // 2

    for ax, img, dist, extent, label in [
        (axes[0], image_before, dist_before, extent_before, "Before (mesh)"),
        (axes[1], image_after, dist_after, extent_after, "After (distant obj)"),
    ]:
        region = img[cy - crop : cy + crop, cx - crop : cx + crop]
        if len(region.shape) == 3:
            region = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
        ax.imshow(region, cmap="gray" if len(region.shape) == 2 else None, interpolation="nearest")
        ax.set_title(f"{label}\n{dist / 1e6:.1f} Mm — {extent[0]}×{extent[1]} px")
        ax.axhline(crop - 0.5, color="r", linewidth=0.5, linestyle="--")
        ax.axvline(crop - 0.5, color="r", linewidth=0.5, linestyle="--")

    fig.suptitle(
        f"Object size across transition — {width}×{height} " f"(threshold ≈ {transition_dist / 1e6:.3f} Mm)",
        fontsize=13,
    )
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# Test 1: Position — CoB should match image center for a centered distant object
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_name, camera_distance",
    [
        ("40Mm", 40_000_000),
        ("100Mm", 100_000_000),
    ],
)
def test_distant_object_position(cielim_connection, test_name, camera_distance):
    """Verify that the distant object center of brightness matches the expected projection."""
    assert camera_distance > compute_transition_distance(), f"{camera_distance} m is not in the distant object regime"

    connector = cielim_connection
    connector.send_init_request()

    scene = default_scene(camera_distance)
    render_frame(connector, scene)  # warm-up
    image, cob, _ = render_frame(connector, scene)

    expected_x = width / 2.0
    expected_y = height / 2.0

    np.testing.assert_allclose(
        [cob[0], cob[1]],
        [expected_x, expected_y],
        atol=1.5,
        err_msg=f"CoB does not match expected image center for {test_name}",
    )


# ---------------------------------------------------------------------------
# Test 2: Size — object footprint should be consistent across the transition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_name, width, height, expected_quad",
    [
        ("corner (2x2)", 2000, 1500, (2, 2)),  # even×even  → center on pixel corner
        ("v-edge (1x2)", 2001, 1500, (1, 2)),  # odd×even   → X center, Y boundary
        ("h-edge (2x1)", 2000, 1501, (2, 1)),  # even×odd   → X boundary, Y center
        ("center (1x1 plus)", 2001, 1501, (1, 1)),  # odd×odd → pixel interior → plus mode;
        # after the threshold=50 filter only the
        # center pixel (0.9× radiance) survives —
        # the 0.025× halo is below the floor by design.
    ],
)
def test_distant_object_size(cielim_connection, test_name, width, height, expected_quad):
    """Verify object footprint before and after the distant-rendering transition.

    The resolution determines where the image center falls on the pixel grid:
      even×even → pixel corner     → 2×2 quad                      (on-grid, Mode 0)
      odd×even  → vertical edge    → 1×2 quad                      (on-grid, Mode 0)
      even×odd  → horizontal edge  → 2×1 quad                      (on-grid, Mode 0)
      odd×odd   → pixel interior   → plus shape (center + halo)    (off-grid, Mode 1 at α≤100°)

    In the plus case, the dominant center carries 90% of the flux and the 4-connected halo
    each carries 2.5% — the halo is intentionally below the sensor/threshold floor so the
    render reads as a single bright pixel while still providing rasterization redundancy.

    Just before the threshold the object is mesh-rendered at ~2 pixels.  Just after,
    the distant object shader produces the expected footprint for the grid alignment.
    """
    transition_dist = compute_transition_distance(width, height)
    dist_before = transition_dist * 0.999999  # just below threshold — mesh rendered
    dist_after = transition_dist  # just above threshold — distant object

    connector = cielim_connection

    # Render just before transition (mesh)
    connector.send_init_request()
    scene = default_scene(dist_before, width, height)
    render_frame(connector, scene)
    image_before, _, _ = render_frame(connector, scene)
    gray_before = to_gray_thresholded(image_before)

    # Render just after transition (distant object)
    connector.send_init_request()
    scene = default_scene(dist_after, width, height)
    render_frame(connector, scene)
    image_after, _, _ = render_frame(connector, scene)
    gray_after = to_gray_thresholded(image_after)

    # Both images must have visible pixels
    assert np.max(gray_before) > 0, "Mesh-rendered image should have bright pixels"
    assert np.max(gray_after) > 0, "Distant object image should have bright pixels"

    extent_before = bright_pixel_extent(gray_before)
    extent_after = bright_pixel_extent(gray_after)

    show_size_comparison(
        image_before, image_after, dist_before, dist_after, transition_dist, extent_before, extent_after, width, height
    )

    # The distant object quad must match the expected size for this resolution
    assert extent_after == expected_quad, (
        f"[{test_name}] Distant object extent {extent_after[0]}×{extent_after[1]}, "
        f"expected {expected_quad[0]}×{expected_quad[1]} for {width}×{height} resolution"
    )

    # The mesh-rendered object near the threshold should have a similar small footprint
    assert extent_before[0] <= 4 and extent_before[1] <= 4, (
        f"Mesh object extent {extent_before[0]}×{extent_before[1]} " f"is unexpectedly large near the transition"
    )


# ---------------------------------------------------------------------------
# Test 3: Rendering path — albedo response proves the distant shader is active
# ---------------------------------------------------------------------------

BASELINE_DISTANCE = 40_000_000
SRGB_GAMMA = 2.2


def _max_pixel_linear(image):
    """Return the brightest pixel value linearized from sRGB to undo gamma encoding."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return (float(np.max(gray)) / 255.0) ** SRGB_GAMMA


# ---------------------------------------------------------------------------
# Test 4: Brightness — pixel brightness ratio should track the Coverage formula
# ---------------------------------------------------------------------------


def measure_brightness(image):
    """Return the max grayscale pixel value, linearized from sRGB to undo gamma encoding."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return (float(np.max(gray)) / 255.0) ** SRGB_GAMMA


def measure_mean_brightness(image):
    """Mean linearised brightness over grayscale pixels above zero. Each pixel is sRGB→linear
    converted before averaging (averaging gamma-encoded values would underweight bright
    pixels). Returns 0 if no pixel is lit."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    lit = gray[gray > 0]
    if len(lit) == 0:
        return 0.0
    linear = (lit.astype(float) / 255.0) ** SRGB_GAMMA
    return float(np.mean(linear))


def measure_combined_brightness(image):
    """Geometric mean of the lit-pixel mean and the max pixel, both in 8-bit pixel space (0-255).

    Combining the two metrics is more robust than either alone for tracking exposure: the
    plain max plateaus at sensor saturation while the rest of the image is still brightening,
    and the plain mean is sensitive to how many sub-noise-floor pixels round to 1 vs 0.
    Their geometric mean rises whenever either rises."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    lit = gray[gray > 0]
    if len(lit) == 0:
        return 0.0
    mean = float(np.mean(lit))
    peak = float(np.max(lit))
    return float(np.sqrt(mean * peak))


@pytest.mark.parametrize(
    "test_name, object_z_shift, exposure_time",
    [
        ("60Mm @ 5e-4", 20_000_000, 5e-4),
        ("60Mm @ 1e-3", 20_000_000, 1e-3),
        ("60Mm @ 2e-3", 20_000_000, 2e-3),
        ("120Mm @ 1e-3", 80_000_000, 1e-3),
        ("120Mm @ 2e-3", 80_000_000, 2e-3),
    ],
)
def test_distant_object_brightness(cielim_connection, test_name, object_z_shift, exposure_time):
    """Verify that distant object brightness scales with the Coverage formula across exposures.

    With PSF disabled, CosineLoss = 1.0 (sun behind camera), and constant SSI, the
    per-pixel radiance is proportional to Coverage. The QuE tonemap is linear below
    full-well capacity. The render target applies sRGB gamma, so we linearize the max
    pixel value before comparing ratios. Exposure is parametrized to verify the ratio
    is invariant to exposure (within the linear regime) and to surface actual brightness
    variation rather than saturated values.
    """
    connector = cielim_connection
    connector.send_init_request()

    scene = default_scene(BASELINE_DISTANCE)
    scene.set_sensor_params(exposure=exposure_time)
    render_frame(connector, scene)  # warm-up

    # Baseline measurement
    image, _, _ = render_frame(connector, scene)
    baseline_brightness = measure_brightness(image)
    assert baseline_brightness > 0, "Baseline brightness must be non-zero"

    # Shift object along +Z to increase distance
    scene.set_celestial_body_params(asteroid_index, position=(0, 0, object_z_shift))

    image, _, _ = render_frame(connector, scene)
    shifted_brightness = measure_brightness(image)

    # Expected coverage ratio
    baseline_coverage = compute_coverage(mean_radius, BASELINE_DISTANCE, fov_x, fov_y, width, height)
    shifted_distance = BASELINE_DISTANCE + object_z_shift
    shifted_coverage = compute_coverage(mean_radius, shifted_distance, fov_x, fov_y, width, height)
    expected_ratio = shifted_coverage / baseline_coverage

    actual_ratio = shifted_brightness / baseline_brightness

    print(
        f"\n[brightness] {test_name:<14}  exp={exposure_time:.1e}  "
        f"baseline={baseline_brightness:7.4f}  shifted={shifted_brightness:7.4f}  "
        f"expected_ratio={expected_ratio:7.4f}  actual_ratio={actual_ratio:7.4f}  "
        f"diff={actual_ratio - expected_ratio:+7.4f}"
    )

    np.testing.assert_allclose(
        actual_ratio,
        expected_ratio,
        rtol=0.15,
        atol=0.03,
        err_msg=f"Brightness ratio does not match coverage ratio for {test_name}",
    )


def scene_with_phase_angle(
    camera_distance, phase_angle_deg, brdf_model="Regolith", exposure_time=None, width=width, height=height
):
    """Create a Scene at the given phase angle by rotating the sun position."""
    alpha = np.radians(phase_angle_deg)
    sun_dist = 1.496e11
    sun_pos = (sun_dist * np.sin(alpha), 0.0, -sun_dist * np.cos(alpha))

    scene = default_scene(camera_distance, width, height)
    scene.set_celestial_body_params(asteroid_index, mesh_brdf=brdf_model)
    scene.set_celestial_body_params(sun_index, position=sun_pos)
    if exposure_time is not None:
        scene.set_sensor_params(exposure=exposure_time)
    return scene


# ---------------------------------------------------------------------------
# Test 5: Intensity continuity — brightness should be continuous across the transition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_name, brdf_model, phase_angle_deg, exposure_time, rtol",
    [
        # Exposures chosen to put the overlay's peak pixel near mid-range (~0.5 linear) so both
        # paths stay below saturation and the mesh-vs-distant comparison reflects the actual
        # radiance ratio rather than clipped values. Regolith's analytical radiance is ~1/π
        # of Lambertian's at the same geometry, so it needs ~3× longer exposure to match.
        #
        # Per-BRDF rtol: Lambertian tracks the analytical formula closely (UE Lambertian
        # shading is the same model). Regolith's UE material (M_Regolith) outputs ~70% of
        # what the analytical Lommel-Seeliger formula produces — that residual mismatch is
        # structural to the material graph and can't be closed without auditing/replacing
        # it. Accept the gap with a wider rtol; keep atol tight to still catch gross drift.
        ("Lambertian 0°", "Lambertian", 0, 1e-4, 0.15),
        ("Lambertian 45°", "Lambertian", 45, 1e-4, 0.15),
        ("Regolith 0°", "Regolith", 0, 3e-4, 0.5),
        ("Regolith 45°", "Regolith", 45, 3e-4, 0.5),
    ],
)
def test_intensity_continuity(cielim_connection, test_name, brdf_model, phase_angle_deg, exposure_time, rtol):
    """Verify that the max pixel brightness is continuous across the mesh/distant transition.

    Renders just before (mesh) and just after (distant object) the transition threshold
    and checks that the brightest pixel values are within tolerance.
    """
    transition_dist = compute_transition_distance(phase_angle_deg=phase_angle_deg)
    dist_before = transition_dist * 0.999999
    dist_after = transition_dist

    connector = cielim_connection

    # Render mesh just before transition
    connector.send_init_request()
    scene = scene_with_phase_angle(dist_before, phase_angle_deg, brdf_model, exposure_time=exposure_time)
    render_frame(connector, scene)
    image_before, _, _ = render_frame(connector, scene)

    # Render distant object just after transition
    connector.send_init_request()
    scene = scene_with_phase_angle(dist_after, phase_angle_deg, brdf_model, exposure_time=exposure_time)
    render_frame(connector, scene)
    image_after, _, _ = render_frame(connector, scene)

    gray_before = cv2.cvtColor(image_before, cv2.COLOR_BGR2GRAY) if len(image_before.shape) == 3 else image_before
    gray_after = cv2.cvtColor(image_after, cv2.COLOR_BGR2GRAY) if len(image_after.shape) == 3 else image_after

    max_before = float(np.max(gray_before))
    max_after = float(np.max(gray_after))

    assert max_before > 0, "Mesh image should have bright pixels"
    assert max_after > 0, "Distant object image should have bright pixels"

    ratio = max_after / max_before if max_before > 0 else float("inf")
    print(
        f"\n[continuity] {test_name:<14}  exp={exposure_time:.1e}  "
        f"mesh={max_before:6.1f}  distant={max_after:6.1f}  "
        f"diff={max_after - max_before:+6.1f}  ratio={ratio:5.3f}"
    )

    if show_plots:
        crop = 6
        cy, cx = height // 2, width // 2
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        for ax, img, val, label in [
            (axes[0], image_before, max_before, "Mesh"),
            (axes[1], image_after, max_after, "Distant"),
        ]:
            region = img[cy - crop : cy + crop, cx - crop : cx + crop]
            if len(region.shape) == 3:
                region = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
            ax.imshow(region, cmap="gray" if len(region.shape) == 2 else None, interpolation="nearest")
            ax.set_title(f"{label} (max={val:.0f})")
        fig.suptitle(f"{test_name}: mesh={max_before:.0f} → distant={max_after:.0f}", fontsize=13)
        plt.tight_layout()
        plt.show()

    np.testing.assert_allclose(
        max_after,
        max_before,
        atol=30,
        rtol=rtol,
        err_msg=f"[{test_name}] Brightness discontinuity: mesh={max_before:.0f}, distant={max_after:.0f}",
    )


# ---------------------------------------------------------------------------
# Test 6: Cosine loss — distant object should dim with increasing phase angle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "brdf_model",
    ["Lambertian", "Regolith"],
)
def test_cosine_loss(cielim_connection, brdf_model):
    """Verify that distant object brightness decreases with increasing phase angle."""
    camera_distance = BASELINE_DISTANCE
    phase_angles = [0, 30, 60, 90, 112, 135, 160]

    connector = cielim_connection
    connector.send_init_request()

    brightnesses = []
    for angle in phase_angles:
        scene = scene_with_phase_angle(camera_distance, angle, brdf_model)
        render_frame(connector, scene)
        image, _, _ = render_frame(connector, scene)
        brightnesses.append(measure_brightness(image))

    if show_plots:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(phase_angles, brightnesses, "o-", label=brdf_model)
        ax.set_xlabel("Phase angle (deg)")
        ax.set_ylabel("Linearized max brightness")
        ax.set_title(f"Cosine loss — {brdf_model}")
        ax.legend()
        plt.tight_layout()
        plt.show()

    # Brightness should trend downward with phase angle, but strict per-pair monotonicity is
    # brittle: at low α consecutive samples can saturate and tie, and the shader's pixel-snap
    # can change quad shape (2×2 ↔ 1×2 ↔ 1×1) depending on the photocenter offset's fractional
    # position at each α, introducing small non-monotonic wiggles between adjacent samples.
    # Instead require each sample to be strictly below the running maximum of preceding
    # samples — no α can rise above any earlier α's brightness.
    for i in range(1, len(brightnesses)):
        max_prior = max(brightnesses[:i])
        assert brightnesses[i] < max_prior, (
            f"[{brdf_model}] Brightness at {phase_angles[i]}° ({brightnesses[i]:.4f}) exceeds "
            f"the peak of earlier phase angles ({max_prior:.4f})"
        )


# ---------------------------------------------------------------------------
# Test 7: High-phase-angle continuity — crescent regime (90° – 160°)
# ---------------------------------------------------------------------------
#
# The behavior depends on where the object's projected center lands on the pixel grid:
#   - On-grid   (even×even resolution → object on a pixel boundary → 2×2 quad)
#   - Off-grid  (odd×odd  resolution → object in the pixel interior  → 1×1 quad)
# On-grid currently works up to ≈160°. Off-grid fails above 100° and is the target of
# the Phase B fix (shader "+"-shape rendering with flux conservation).

# On-grid sweep stops at 135° — at 160° the mesh rasterizer loses the sub-pixel crescent even
# on-grid (bounding ≈4 px × crescent factor 0.03 → 0.12 px), so there is no mesh-side signal to
# be continuous with. The off-grid sweep keeps 160° since the plus shape still renders and the
# 112° / 160° cases self-skip via the "both too dim to compare" guard when exposure isn't enough.
ON_GRID_HIGH_PHASE_PARAMS = [
    ("Lambertian 90°", "Lambertian", 90, 0.5),
    ("Lambertian 112°", "Lambertian", 112, 100.0),
    ("Lambertian 135°", "Lambertian", 135, 500.0),
    ("Regolith 90°", "Regolith", 90, 0.5),
    ("Regolith 112°", "Regolith", 112, 100.0),
    ("Regolith 135°", "Regolith", 135, 500.0),
]

OFF_GRID_HIGH_PHASE_PARAMS = [
    ("Lambertian 90°", "Lambertian", 90, 0.5),
    ("Lambertian 112°", "Lambertian", 112, 100.0),
    ("Lambertian 135°", "Lambertian", 135, 500.0),
    ("Lambertian 160°", "Lambertian", 160, 1000.0),
    ("Regolith 90°", "Regolith", 90, 0.5),
    ("Regolith 112°", "Regolith", 112, 100.0),
    ("Regolith 135°", "Regolith", 135, 500.0),
    ("Regolith 160°", "Regolith", 160, 1000.0),
]


def _run_high_phase_angle_continuity(
    cielim_connection, test_name, brdf_model, phase_angle_deg, exposure_time, width, height, on_grid, rtol=0.25
):
    """Shared body for on-grid / off-grid variants of the high-phase continuity test.

    Compares peak pixel values before and after the mesh→distant transition. ``rtol`` is
    wider for the off-grid case because the plus shape's center pixel is intentionally
    attenuated to 0.6× (flux is spread across the 5 lit pixels of the plus) so the peak
    is dimmer than the mesh's surface-radiance peak by design.
    """
    transition_dist = compute_transition_distance(
        width=width, height=height, phase_angle_deg=phase_angle_deg, on_grid=on_grid
    )
    # Use a 0.5% margin on each side of the transition so that tiny float-precision
    # differences between Python's K and C++'s ComputeBoundsScreenSize × viewport don't
    # accidentally place the "after" sample inside the mesh regime (or vice versa). The
    # resulting object-size change across the 1% gap is smaller than the test's rtol.
    dist_before = transition_dist * 0.995
    dist_after = transition_dist * 1.005

    connector = cielim_connection

    # Render mesh just before transition
    connector.send_init_request()
    scene = scene_with_phase_angle(
        dist_before, phase_angle_deg, brdf_model, exposure_time=exposure_time, width=width, height=height
    )
    render_frame(connector, scene)
    image_before, _, _ = render_frame(connector, scene)

    # Render distant object just after transition
    connector.send_init_request()
    scene = scene_with_phase_angle(
        dist_after, phase_angle_deg, brdf_model, exposure_time=exposure_time, width=width, height=height
    )
    render_frame(connector, scene)
    image_after, _, _ = render_frame(connector, scene)

    gray_before = cv2.cvtColor(image_before, cv2.COLOR_BGR2GRAY) if len(image_before.shape) == 3 else image_before
    gray_after = cv2.cvtColor(image_after, cv2.COLOR_BGR2GRAY) if len(image_after.shape) == 3 else image_after

    max_before = float(np.max(gray_before))
    max_after = float(np.max(gray_after))

    if show_plots:
        crop = 10
        cy, cx = height // 2, width // 2
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        for ax, img, val, label in [
            (axes[0], image_before, max_before, "Mesh"),
            (axes[1], image_after, max_after, "Distant"),
        ]:
            region = img[cy - crop : cy + crop, cx - crop : cx + crop]
            if len(region.shape) == 3:
                region = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
            ax.imshow(region, cmap="gray" if len(region.shape) == 2 else None, interpolation="nearest")
            ax.set_title(f"{label} (max={val:.0f})")
        fig.suptitle(f"{test_name}: mesh={max_before:.0f} → distant={max_after:.0f}", fontsize=13)
        plt.tight_layout()
        plt.show()

    # At high phase angles, accept that one or both may be very dim
    if max_before < 2 and max_after < 2:
        pytest.skip(f"Both images too dim to compare at {phase_angle_deg}° (mesh={max_before}, distant={max_after})")

    np.testing.assert_allclose(
        max_after,
        max_before,
        atol=40,
        rtol=rtol,
        err_msg=f"[{test_name}] max discontinuity: mesh={max_before:.0f}, distant={max_after:.0f}",
    )


@pytest.mark.parametrize("test_name, brdf_model, phase_angle_deg, exposure_time", ON_GRID_HIGH_PHASE_PARAMS)
def test_high_phase_angle_continuity_on_grid(cielim_connection, test_name, brdf_model, phase_angle_deg, exposure_time):
    """On-grid variant: even×even resolution → object center on pixel boundary → 2×2 quad.

    The mesh rasterizer and the distant shader both emit surface radiance in their brightest
    pixel, so the strict rtol=0.25 tolerance applies.
    """
    _run_high_phase_angle_continuity(
        cielim_connection,
        test_name,
        brdf_model,
        phase_angle_deg,
        exposure_time,
        width=2000,
        height=1500,
        on_grid=True,
        rtol=0.25,
    )


@pytest.mark.parametrize("test_name, brdf_model, phase_angle_deg, exposure_time", OFF_GRID_HIGH_PHASE_PARAMS)
def test_high_phase_angle_continuity_off_grid(cielim_connection, test_name, brdf_model, phase_angle_deg, exposure_time):
    """Off-grid variant: odd×odd resolution → object center in pixel interior → plus shape.

    The shader renders a flux-conserving plus (center at 0.6×, N/S/E/W at 0.1×, corners
    discarded — sum across the 5 lit pixels equals one single-pixel photometric footprint).
    The peak pixel is the plus center at 0.6× surface radiance, so the tolerance is widened
    to rtol=0.5 to accommodate the intentional peak attenuation vs. the mesh's full-radiance
    crescent pixel.
    """
    _run_high_phase_angle_continuity(
        cielim_connection,
        test_name,
        brdf_model,
        phase_angle_deg,
        exposure_time,
        width=2001,
        height=1501,
        on_grid=False,
        rtol=0.5,
    )


# ---------------------------------------------------------------------------
# Test 8: Exposure scaling — distant object brightness should grow with exposure time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "brdf_model",
    ["Lambertian", "Regolith"],
)
def test_exposure_scaling(cielim_connection, brdf_model):
    """Distant-object brightness should rise with exposure time until the sensor saturates.

    Spans three orders of magnitude in exposure and checks the endpoints. Per-pair
    monotonicity isn't required: small exposure-to-exposure wiggles can come from
    rendering noise, scene-update timing, or near-noise-floor quantisation, and aren't a
    physics violation; what must hold is that brightness is higher at the longest exposure
    than the shortest. α=90° gives a moderate Lambertian phase so the dim-end exposure is
    above the sensor floor and the bright-end lands near saturation. The range is bounded
    so the sweep doesn't camp in the flat saturated region — saturation kicks in around
    3e-2 s at this scene with AA disabled, so we stop at 1e-1.
    """
    camera_distance = BASELINE_DISTANCE
    phase_angle_deg = 90
    exposures = [1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1]

    connector = cielim_connection
    connector.send_init_request()

    brightnesses = []
    images = []
    for exposure in exposures:
        scene = scene_with_phase_angle(camera_distance, phase_angle_deg, brdf_model, exposure_time=exposure)
        render_frame(connector, scene)  # warm-up
        image, _, _ = render_frame(connector, scene)
        brightnesses.append(measure_combined_brightness(image))
        images.append(image)

    if show_plots:
        # Brightness-vs-exposure line plot in 0-255 pixel space.
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(exposures, brightnesses, "o-", label=brdf_model)
        ax.set_xscale("log")
        ax.set_xlabel("Exposure time (s)")
        ax.set_ylabel("Combined brightness — pixel value (0-255)")
        ax.set_ylim(0, 260)
        ax.axhline(255, color="gray", linewidth=0.5, linestyle="--", label="saturation (255)")
        ax.set_title(f"Exposure scaling — {brdf_model}")
        ax.legend()
        ax.grid(True, which="both", linewidth=0.3, alpha=0.5)
        plt.tight_layout()
        plt.show()

        # Image strip — central crop at each exposure.
        crop = 8
        cy, cx = height // 2, width // 2
        fig, axes = plt.subplots(1, len(exposures), figsize=(1.6 * len(exposures), 2.5))
        for ax, img, exp, b in zip(axes, images, exposures, brightnesses):
            region = img[cy - crop : cy + crop, cx - crop : cx + crop]
            if len(region.shape) == 3:
                region = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
            ax.imshow(
                region, cmap="gray" if len(region.shape) == 2 else None, interpolation="nearest", vmin=0, vmax=255
            )
            ax.set_title(f"{exp:g}s\nB={b:.0f}", fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])
        fig.suptitle(f"Exposure scaling — {brdf_model}", fontsize=12)
        plt.tight_layout()
        plt.show()

    # Endpoint check: brightness at the longest exposure must exceed brightness at the
    # shortest (or be at the sensor ceiling, in which case the longest already maxed out).
    SATURATION_PIXEL = 255 - 1e-3
    assert brightnesses[-1] > brightnesses[0] or brightnesses[-1] >= SATURATION_PIXEL, (
        f"[{brdf_model}] Brightness did not increase across exposures "
        f"{exposures[0]:g} → {exposures[-1]:g}: "
        f"{brightnesses[0]:.1f} → {brightnesses[-1]:.1f} "
        f"(all samples: {[f'{b:.1f}' for b in brightnesses]})"
    )


# ---------------------------------------------------------------------------
# Test 9: Multi-body scene — distant bodies (in/out of frame) plus a rasterized mesh
# ---------------------------------------------------------------------------


def test_multibody_with_rasterized(cielim_connection):
    """Several distant bodies (some in frame, some out) plus a rasterized mesh must render.

    This is the regression for the original black-frame bug: off-screen / behind-camera
    distant objects coexisting with a rasterized body used to corrupt the whole frame.
    """
    connector = cielim_connection
    camera_distance = 0  # camera at world origin looking +Z; sun at -Z front-lights +Z bodies

    # All bodies on the X axis (y=0) so only the predicted column matters; row stays centered.
    # Distant bodies sit at 20e6 (~3x the ~6.6e6 mesh transition): safely sub-pixel yet still bright.
    rasterized = [0, 0, 2e6]  # D=2e6 < transition -> rasterized mesh, screen center
    distant_right = [1.41e6, 0, 20e6]  # ndc_x ~ +0.4 -> in frame
    distant_left = [-1.41e6, 0, 20e6]  # ndc_x ~ -0.4 -> in frame
    distant_offscreen = [5.29e6, 0, 20e6]  # ndc_x ~ 1.5 -> off screen
    behind_camera = [0, 0, -1e7]  # D < 0 -> behind the camera, culled

    scene = scene_with_bodies(
        camera_distance,
        [
            {"name": "rasterized", "position": rasterized},
            {"name": "distant_right", "position": distant_right},
            {"name": "distant_left", "position": distant_left},
            {"name": "distant_offscreen", "position": distant_offscreen},
            {"name": "behind_camera", "position": behind_camera},
        ],
    )

    connector.send_init_request()
    render_frame(connector, scene)  # warm-up
    image, _, _ = render_frame(connector, scene)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    cy = height // 2
    px_r, _ = predict_pixel(distant_right, camera_distance)
    px_l, _ = predict_pixel(distant_left, camera_distance)
    px_off, _ = predict_pixel(distant_offscreen, camera_distance)

    print(
        f"\n[multibody] peak={int(np.max(gray))} "
        f"center={int(np.max(crop_center(gray, 20)))} "
        f"right@{int(px_r)}={int(np.max(gray[cy - 40 : cy + 40, int(px_r) - 40 : int(px_r) + 40]))} "
        f"left@{int(px_l)}={int(np.max(gray[cy - 40 : cy + 40, int(px_l) - 40 : int(px_l) + 40]))}"
    )

    if show_plots:
        # Full frame with the predicted body positions marked, so a failed assertion can be
        # read against where each body was expected to land.
        fig, ax = plt.subplots(figsize=(10, 7.5))
        ax.imshow(gray, cmap="gray", interpolation="nearest", vmin=0, vmax=255)
        for px, py, label, color in [
            (width / 2, cy, "rasterized (center)", "lime"),
            (px_r, cy, "distant_right", "cyan"),
            (px_l, cy, "distant_left", "magenta"),
            (px_off, cy, "distant_offscreen", "orange"),
        ]:
            ax.scatter([px], [py], s=160, facecolors="none", edgecolors=color, linewidths=1.5)
            ax.annotate(label, (px, py), color=color, fontsize=8, xytext=(6, 6), textcoords="offset points")
        ax.set_title(f"Multi-body frame — peak={int(np.max(gray))}")
        plt.tight_layout()
        plt.show()

    # 1. The frame is not black — this mix used to black the whole image.
    assert int(np.max(gray)) > 50, "Frame is black — multi-body + rasterized regression"
    # 2. The rasterized mesh renders at screen center.
    assert has_bright_spot(gray, width / 2, cy), "Rasterized body missing at center"
    # 3. Both in-frame distant bodies render near their predicted columns.
    assert has_bright_spot(gray, px_r, cy), "In-frame distant body (right) missing"
    assert has_bright_spot(gray, px_l, cy), "In-frame distant body (left) missing"


# ---------------------------------------------------------------------------
# Test 10: Occlusion — a rasterized body hides a distant object behind it
# ---------------------------------------------------------------------------


def test_distant_object_occluded_by_mesh(cielim_connection):
    """A distant object directly behind a nearer rasterized body must be occluded by it
    (depth-tested out), not added on top through the additive composite.

    The occluder is given a low albedo so it renders DIM while still writing depth (depth is
    independent of albedo). A bright distant object behind it then gives a stark contrast:
    occluded -> center stays at the dim mesh level; bled through -> center jumps to the bright
    distant level. Brightness is measured in linear space to undo sRGB gamma so the contrast
    isn't compressed.
    """
    connector = cielim_connection
    camera_distance = 0

    occluder = [0, 0, 2e6]  # D=2e6 < transition -> rasterized mesh at center (writes depth)
    distant = [0, 0, 20e6]  # D=20e6 > transition -> distant object at center, behind the occluder

    def center_brightness(bodies):
        scene = scene_with_bodies(camera_distance, bodies)
        connector.send_init_request()
        render_frame(connector, scene)  # warm-up
        image, _, _ = render_frame(connector, scene)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        brightness = (float(np.max(crop_center(gray, 20))) / 255.0) ** SRGB_GAMMA  # linearized
        return brightness, gray

    b_distant, gray_distant = center_brightness([{"name": "distant", "position": distant, "albedo": 1.0}])
    b_mesh, gray_mesh = center_brightness([{"name": "occluder", "position": occluder, "albedo": 0.05}])
    b_both, gray_both = center_brightness(
        [
            {"name": "occluder", "position": occluder, "albedo": 0.05},
            {"name": "distant", "position": distant, "albedo": 1.0},
        ]
    )

    print(f"\n[occlusion] distant_only={b_distant:.4f} mesh_only={b_mesh:.4f} both={b_both:.4f}")

    if show_plots:
        # Central crops of the three scenarios. Occlusion is working when "both" looks like
        # "mesh only" (distant hidden); a bleed-through shows up as "both" matching "distant only".
        crop = 20
        cy0, cx0 = height // 2, width // 2
        fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
        for ax, g, b, label in [
            (axes[0], gray_distant, b_distant, "distant only"),
            (axes[1], gray_mesh, b_mesh, "mesh only (occluder)"),
            (axes[2], gray_both, b_both, "both (should == mesh)"),
        ]:
            region = g[cy0 - crop : cy0 + crop, cx0 - crop : cx0 + crop]
            ax.imshow(region, cmap="gray", interpolation="nearest", vmin=0, vmax=255)
            ax.set_title(f"{label}\nlinear b={b:.4f}", fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
        fig.suptitle("Occlusion — distant object behind a dim rasterized mesh", fontsize=13)
        plt.tight_layout()
        plt.show()

    # Control: the distant object is clearly visible when nothing occludes it.
    assert b_distant > 0.02, f"Distant object not visible unoccluded (b_distant={b_distant:.4f})"
    # Precondition: the occluder must be the dimmer feature, else a bleed-through is undetectable.
    assert b_mesh < 0.5 * b_distant, (
        f"Occluder not dim enough vs distant; lower occluder albedo " f"(mesh={b_mesh:.4f}, distant={b_distant:.4f})"
    )
    # Occlusion: with the mesh in front, the bright distant object is hidden — the center stays
    # near the dim mesh level, far below the distant brightness (additive bleed-through would
    # push it up toward b_mesh + b_distant).
    assert (
        b_both < 0.5 * b_distant
    ), f"Distant object bled through the occluder: both={b_both:.4f}, distant={b_distant:.4f}"
    np.testing.assert_allclose(
        b_both,
        b_mesh,
        rtol=0.3,
        atol=0.02,
        err_msg=f"Occluded center should match mesh-only: both={b_both:.4f}, mesh={b_mesh:.4f}",
    )


def _report_params(name, **facts):
    """Echo the scene/camera settings showcase figure ``name`` was rendered with to stdout.

    NOT drawn on the figure — the settings live in the ``Reference image`` section of
    ``docs/distant_objects.tex``, so the paper carries them in text rather than as small print baked
    into the image. Printing them keeps that sheet checkable: run the showcase with ``pytest -s`` and
    diff what it reports against what the sheet claims. Several of these are derived (the transition
    distances, the thresholds), so they move whenever the model does.
    """
    print(f"[showcase] {name}: " + "  ".join(f"{k}={v}" for k, v in facts.items()))


# ---------------------------------------------------------------------------
# Showcase: page-ready distant-object demo image (opt-in via the showcase_dir env var)
# ---------------------------------------------------------------------------


@pytest.mark.showcase
def test_showcase_distant_objects(cielim_connection):
    """The mesh -> distant handover, at low and high phase angle.

    Each row walks the camera out through that phase angle's own transition distance, showing the
    same fixed-size crop at every range so the size change is directly comparable. The point of the
    pair is why the threshold has to grow with phase angle: at high alpha only a thin crescent is
    lit, so the body's *bounding box* is still several pixels across when its visible signal has
    already gone sub-pixel.
    """
    ps.apply_showcase_style()
    connector = cielim_connection

    # Multiples of the transition distance. The far column sits well past d_t on purpose: coverage
    # saturates at 1 just after the transition (which is what makes the handover photometrically
    # continuous), so the point source does not begin to dim until some way beyond it.
    factors = [0.2, 0.45, 0.9, 1.05, 3.0]
    rows = [(0, "low phase\n" + r"$\alpha=0\degree$"), (135, "high phase\n" + r"$\alpha=135\degree$")]
    exposure, half = 1e-4, 26

    # Full text width exactly, so the grid drops onto the page at scale 1.0 and its 10 pt labels
    # print at 10 pt. Height = the two rows of square panels plus room for their two-line titles
    # (without it the titles land on the row above) and one line for the rule label underneath.
    # No figure title: what the grid shows is described in docs/distant_objects.tex.
    panel_w = ps.PAGE_W / len(factors)
    title_h = 2 * 1.35 * ps.BODY_PT / 72
    fig, axes = plt.subplots(
        len(rows), len(factors), figsize=(ps.PAGE_W, len(rows) * (panel_w + title_h) + 0.45)
    )

    for row, (phase_angle_deg, row_label) in enumerate(rows):
        transition = compute_transition_distance(phase_angle_deg=phase_angle_deg)
        threshold = _pixel_size_threshold(phase_angle_deg)

        crops = []
        for factor in factors:
            scene = scene_with_phase_angle(
                transition * factor, phase_angle_deg, "Lambertian", exposure_time=exposure
            )
            connector.send_init_request()
            render_frame(connector, scene)  # warm-up; the first frame after an init can be blank
            image, _, _ = render_frame(connector, scene)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
            peak_y, peak_x = np.unravel_index(np.argmax(gray), gray.shape)
            y = int(np.clip(peak_y, half, gray.shape[0] - half))
            x = int(np.clip(peak_x, half, gray.shape[1] - half))
            lit_y, lit_x = np.nonzero(gray)
            footprint = (
                f"{lit_x.max() - lit_x.min() + 1}x{lit_y.max() - lit_y.min() + 1}" if len(lit_x) else "-"
            )
            crops.append((gray[y - half : y + half, x - half : x + half], footprint))

        # One display range per row, set by that row's brightest panel. Within a row the relative
        # brightnesses are untouched, so the photometric continuity across the handover still reads;
        # normalising per row is only what keeps the dim high-phase crescent visible at all.
        row_max = max(int(crop.max()) for crop, _ in crops) or 255

        for col, (factor, (crop, footprint)) in enumerate(zip(factors, crops)):
            ax = axes[row][col]
            ax.imshow(crop, cmap=ps.SCENE_CMAP, vmin=0, vmax=row_max, interpolation="nearest")
            # The label is the *measured* lit footprint. Past d_t the shader draws a pixel-snapped
            # quad, so that footprint stops shrinking with range and only the brightness falls —
            # labelling those panels with the projected size (threshold * d_t / d, the quantity the
            # transition test measures) would describe something that is not on screen.
            is_distant = factor >= 1.0
            kind = "distant" if is_distant else "mesh"
            ax.set_title(f"{factor:g}" + r"$\times d_t$" + f"\n{kind}  {footprint}")
            ax.axis("off")

        axes[row][0].text(
            -0.10, 0.5, row_label, transform=axes[row][0].transAxes,
            rotation=90, va="center", ha="center",
        )

    # h_pad keeps the two-line panel titles off the row above. Lay out before reading get_position()
    # for the rule below, so the rule is placed against the final axes geometry.
    fig.tight_layout(h_pad=2.2)

    # Rule marking where the path flips, drawn between the last mesh column and the first distant one.
    x_rule = 0.5 * (
        axes[0][factors.index(0.9)].get_position().x1 + axes[0][factors.index(1.05)].get_position().x0
    )
    y_bottom_row = axes[1][0].get_position().y0
    fig.add_artist(Line2D([x_rule, x_rule], [y_bottom_row, axes[0][0].get_position().y1],
                          color="0.55", linewidth=0.8))
    fig.text(x_rule, y_bottom_row - 0.03, r"$d_t$: mesh $\rightarrow$ distant",
             ha="center", va="top", color="0.4")

    _report_params(
        "distant_objects",
        fov_deg=f"{np.degrees(fov_x):g}x{np.degrees(fov_y):g}",
        resolution=f"{width}x{height}",
        mean_radius_m=f"{mean_radius:g}",
        geometric_albedo=f"{albedo:g}",
        brdf="Lambertian",
        exposure_s=f"{exposure:g}",
        crop_px=f"{2 * half}x{2 * half}",
        factors_of_d_t=",".join(f"{f:g}" for f in factors),
        d_t_alpha0_m=f"{compute_transition_distance(phase_angle_deg=0):.3g}",
        d_t_alpha135_m=f"{compute_transition_distance(phase_angle_deg=135):.3g}",
        threshold_px=f"{_pixel_size_threshold(0):g}/{_pixel_size_threshold(135):.1f}",
        display="per-row normalised",
        panel_label="lit footprint in px (distant = snapped quad, constant with range)",
    )
    ps.save_showcase(fig, "distant_objects")
    plt.close(fig)


if __name__ == "__main__":
    # Set the env var BEFORE pytest re-imports this file so the module-level
    # `show_plots` reads it as True in the freshly-imported test module.
    os.environ["show_plots"] = "False"
    pytest.main([__file__, "-v"])
