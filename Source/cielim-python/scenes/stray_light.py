"""The sun in front of a camera with the stray-light (lens flare) pass enabled.

The stray-light model (``Source/cielim/Shaders/LensFlares.usf``) adds a sun "core" glow, a wide
corona, and a chain of ghost reflections whenever the sun is in front of the camera and the pass is
enabled. A spacecraft/camera at the origin with zero attitude looks toward **+Z**. Placing the sun at
+Z puts it in front of the camera; at -Z it is behind. No target body is needed — the flare is
composited onto the black background.
"""

import cielim
import cv2
import numpy as np

# --- Scene constants -------------------------------------------------------------
fov = 20 * np.pi / 180  # square FoV keeps UV/pixel geometry isotropic
width = 1000
height = 1000
au = 1.496e11  # meters
# The flare multiplies the raw solar spectral radiance (enormous compared to a lit surface), so
# it needs a far shorter exposure than the object tests to avoid painting the whole frame white.
# base_exposure lands the on-axis core mid-range for the simple centered tests; the ghost/sweep
# tests instead auto-calibrate their exposure (see calibrate_exposure) because the right value
# depends on the parameters under test and on the unknown absolute radiance scale.
base_exposure = 1e-9

# Representative (green / center-channel) ghost offsets from LensFlares.usf: each ghost sits at
# offset * SunUV, i.e. offset of the way along the vector from image center to the sun core.
ghost_offsets = {1: 0.325, 2: 0.2, 3: 0.45, 4: 0.85}

# ===========================================================================
# TUNING KNOBS — the single place to dial in the ghost look.
# ===========================================================================
# Every off-center / sweep scene renders with these values (they map 1:1 onto
# set_stray_light_params -> StrayLightModel -> the shader). The wide corona otherwise buries the
# ghosts off-axis, so keep its amplitude low and the ghosts bright enough to read against it.
#
# Two ways to tune (both re-run the sweep with the filmstrip):
#   1. Edit the values below, then:            python tests/test_stray_light.py
#   2. Override on the command line (no edit):  python tests/test_stray_light.py ghost_transmittance=5 corona_intensity=0.05
#      (per-ghost sizes take a comma list:      python tests/test_stray_light.py ghost_relative_sizes=1,2,1,1)
# Ranges in [brackets] are the typical tuning ranges (useful look), not hard limits.
stray_light_tuning = {
    "ghost_transmittance": 3.0,  # overall ghost brightness [0.5, 1.5]
    "ghost_size": 1.25,  # overall ghost size [0.1, 1.25]
    "ghost_relative_sizes": (0.5, 0.5, 0.5, 1.0),  # per-ghost size (1st, 2nd, 3rd, 4th/orb), each [0.25, 1]
    "ghost_brightness_size_exponent": 2.0,  # smaller ghosts get brighter (2 = area-conserving)
    "core_size": 0.5,  # sun core disc size [0.1, 1]
    "corona_intensity": 0.01,  # wide-corona amplitude (lower = fainter wash) [0, 1]
    "corona_falloff_exponent": 1.5,  # corona drop-off (higher = tighter); exposure-independent [0.5, 2]
    "num_rays": 6.0,  # number of symmetric rays (even = mirror-symmetric) [0, 15]
    "ray_sharpness": 24.0,  # ray narrowness (higher = crisper rays) [0, 30]
    "ray_weight": 0.8,  # ray strength relative to the random streaks [0, 1]
}

ghost_half = 45  # half-window (px) around a ghost position for peak measurements
ghost_target = 150  # calibration target peak (below saturation so size/brightness stay measurable)

# ===========================================================================
# Off-boresight sweep: progressively offset the sun off boresight through the shield regimes
# ===========================================================================
#
# A narrow FoV is used so the sun genuinely leaves the frame partway through the sweep, exercising
# all three regimes of the angle-based (baffle-shield) gating in one pass:
#   |angle| <= FoV/2                      -> sun in frame: core visible and tracks the sun
#   FoV/2 < |angle| < FoV/2 + baffle      -> sun off frame but within the shield: ghosts still streak in
#   |angle| > FoV/2 + baffle              -> beyond the shield: no stray light at all
# With FoV = 20 deg (half-angle 10) and baffle = 35 deg the cutoff is 45 deg, so the test's sweep
# angles sit cleanly in each regime: {0, +-4, +-8} in frame, +-20 off-frame-but-flaring, +-55 dark.

sweep_fov = np.radians(20)  # narrow FoV so the sun leaves the frame; half-angle = 10 deg
sweep_baffle = 35.0  # baffle shield (deg); stray-light cutoff = FoV/2 + this = 45 deg
sweep_cal_angle = 8  # exposure-calibration angle (in frame, near the edge, ghosts clear of the core)


def stray_light_scene(
    sun_offset=(0.0, 0.0),
    sun_distance=au,
    sun_position=None,
    exposure=base_exposure,
    width=width,
    height=height,
    fov=fov,
    grayscale=None,
    stray_light=None,
):
    """Build a scene with the sun in front of the camera and the stray-light pass enabled.

    Args:
        sun_offset: (x, y) lateral offset of the sun, in meters, at ``sun_distance`` along +Z.
        sun_distance: sun distance along the +Z optical axis, in meters.
        sun_position: full (x, y, z) sun position, in meters. Overrides sun_offset/sun_distance
            when given (used by the off-boresight sweep to place the sun at an arbitrary angle).
        exposure: sensor exposure time, in seconds.
        width, height: sensor resolution, in pixels.
        fov: (square) field of view, in radians.
        grayscale: if not None, sets the sensor's grayscale image flag.
        stray_light: dict of overrides passed to ``set_stray_light_params`` (merged on top of
            ``enabled=True``). Pass ``{"enabled": False}`` to keep the pass off.
    """
    scene = cielim.Scene()
    scene.set_spacecraft_params(position=(0, 0, 0), attitude=(0, 0, 0))  # look toward +Z
    scene.set_lens_params(fov=(fov, fov))
    scene.set_sensor_params(resolution=(width, height), exposure=exposure)
    if grayscale is not None:
        scene.set_camera_params(grayscale=grayscale)

    params = {"enabled": True}
    if stray_light:
        params.update(stray_light)
    scene.set_stray_light_params(**params)

    if sun_position is None:
        sx, sy = sun_offset
        sun_position = (sx, sy, sun_distance)
    scene.set_celestial_body_params(0, position=tuple(sun_position))
    return scene


def sun_at_angle(angle_deg, distance=au):
    """Sun position at ``angle_deg`` off the +Z boresight, in the x-z plane."""
    a = np.radians(angle_deg)
    return (distance * np.sin(a), 0.0, distance * np.cos(a))


def render_gray(connector, scene):
    """Send a scene (with a warm-up frame) and return the grayscale image."""
    image = render_color(connector, scene)
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def render_color(connector, scene):
    """Send a scene (with a warm-up frame) and return the raw (BGR) image."""
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    connector.request_image_for_camera_id(1)  # warm-up
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1)
    if image is None:
        raise RuntimeError("No image returned from renderer")
    return image


def bright_centroid(gray, frac=0.6):
    """Return (cx, cy) centroid of pixels brighter than ``frac`` of the image max."""
    peak = float(np.max(gray))
    if peak <= 0:
        return None
    ys, xs = np.nonzero(gray >= frac * peak)
    if len(xs) == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def region(gray, center, half):
    """Return the square window of half-size ``half`` centered on ``center`` (x, y)."""
    cx, cy = int(round(center[0])), int(round(center[1]))
    h, w = gray.shape[:2]
    return gray[max(0, cy - half) : min(h, cy + half), max(0, cx - half) : min(w, cx + half)]


def region_peak(gray, center, half):
    """Peak pixel value in a window around ``center``."""
    win = region(gray, center, half)
    return float(np.max(win)) if win.size else 0.0


# Exposure auto-calibration ------------------------------------------------------
#
# The absolute solar-radiance scale (and therefore the right exposure) is not known a priori;
# a fixed exposure either clips the whole frame to white (losing all ghost/color structure) or
# leaves it black. Below saturation the peak pixel rises monotonically with exposure roughly as
# exposure**(1/gamma), so we probe once and rescale to land the brightest configuration just
# below saturation.


def calibrate_exposure(connector, build_scene, target=160, probe=1e-11, gamma=2.2, max_iters=7, measure=None):
    """Return an exposure whose measured brightness is near ``target`` (and below saturation).

    ``build_scene(exposure)`` must return a Scene. Converges in a few renders: it rescales by
    (target/measured)**gamma when unsaturated and backs off hard when clipped or black.

    ``measure(gray) -> float`` selects the quantity to drive to ``target``; defaults to the global
    max pixel. Pass a region measure (e.g. ``ghost_window_peak``) when the bright core (which clips
    to 255 at the ghost/corona-visible exposures) would otherwise pin the global max and defeat it.
    """
    if measure is None:
        measure = lambda gray: float(np.max(gray))
    exposure = probe
    for _ in range(max_iters):
        m = float(measure(render_gray(connector, build_scene(exposure))))
        if m <= 1.0:  # too dark
            exposure *= 50.0
            continue
        if m >= 253.0:  # clipped — drop hard and re-probe
            exposure *= 0.1
            continue
        if 0.85 * target <= m <= 1.15 * target:
            return exposure
        exposure *= (target / m) ** gamma
    return exposure


def ghost_positions(core_pix, img_center):
    """Map each ghost index to its expected pixel position: center + offset*(core - center)."""
    mx, my = img_center
    cx, cy = core_pix
    return {idx: (mx + off * (cx - mx), my + off * (cy - my)) for idx, off in ghost_offsets.items()}


def ghost_window_peak(gray, ghost_idx=3, half=ghost_half):
    """Peak pixel in the given ghost's window — a calibration measure that ignores the bright core,
    which clips to 255 at the ghost-visible exposures and would otherwise pin the global max."""
    core = bright_centroid(gray, frac=0.9)
    if core is None:
        return 0.0
    g = ghost_positions(core, (width / 2.0, height / 2.0))[ghost_idx]
    return region_peak(gray, g, half)
