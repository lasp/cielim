"""RPC tests for the stray-light / lens-flare post-process pass.

The stray-light model (``Source/cielim/Shaders/LensFlares.usf``) adds a sun "core" glow, a
wide corona, and a chain of ghost reflections whenever the sun is in front of the camera and
the pass is enabled. Its parameters come from the protobuf ``StrayLightModel`` message (wired
through ``FStrayLightParams`` → the ``FLensFlares`` shader), plus two quantities read from
existing scene state: ``ExposureTime`` and ``IsGrayscale`` (the image grayscale setting).

This module builds a scenario that puts the sun in the field of view and then varies each
stray-light parameter **individually**, asserting that each one has its expected, isolated
effect on the image:

  * enable gating (opt-in; default OFF)                      -> flare present only when enabled
  * SunClipPosition (sun screen position)                    -> core position / gating by geometry
  * SunRadiusUV (sun angular size, via distance)             -> core size
  * coreSize                                                  -> core disc size
  * ghostSize                                                -> ghost band grows (total ghost signal up)
  * ghostBrightnessSizeExponent                              -> smaller ghosts get brighter
  * ghost{1..4}RelativeSize                                  -> changing one ghost measurably shifts the band
  * ghostTransmittance                                       -> ghost brightness
  * coronaIntensity / coronaFalloffExponent                  -> corona amplitude / tightness, exposure-independent (test_corona_response)
  * numRays / raySharpness / rayWeight                       -> count / narrowness / strength of the symmetric rays (test_ray_parameters)
  * baffleShieldAngle                                        -> off-frame reach: stray light persists out to FoV/2 + this, then cuts off (test_ghost_sweep_across_boresight)
  * exposure time                                            -> overall flare intensity; 0.1 s saturates the sun (test_flare_brightness_scales_with_exposure)
  * isGrayscale (image setting)                              -> achromatic vs chromatic flare

Scene convention (matches the distant-object tests): a spacecraft/camera at the origin with
zero attitude looks toward **+Z**. Placing the sun at +Z puts it in front of the camera; at
-Z it is behind. No target body is needed — the flare is composited onto the black background.

Run standalone with plots:  ``python test_stray_light.py``
"""

import os

import cv2
import numpy as np
import pytest
from matplotlib import pyplot as plt

import cielim

# Read at import time so it survives pytest.main() re-importing this file as a module.
show_plots = os.environ.get("show_plots", "False") == "True"

# The stray-light tunables are wired from the protobuf StrayLightModel through to the shader, so
# the parameter-variation tests are active. (Set this True to skip them, e.g. while temporarily
# hard-coding the shader tunables again.)
PARAMS_HARDCODED = False
requires_params = pytest.mark.skipif(
    PARAMS_HARDCODED,
    reason="stray-light shader tunables are hard-coded; re-wire params then set PARAMS_HARDCODED=False",
)

# --- Scene constants -------------------------------------------------------------
FOV = 20 * np.pi / 180  # square FoV keeps UV/pixel geometry isotropic
WIDTH = 1000
HEIGHT = 1000
AU = 1.496e11  # meters
# The flare multiplies the raw solar spectral radiance (enormous compared to a lit surface), so
# it needs a far shorter exposure than the object tests to avoid painting the whole frame white.
# BASE_EXPOSURE lands the on-axis core mid-range for the simple centered tests; the ghost/sweep
# tests instead auto-calibrate their exposure (see calibrate_exposure) because the right value
# depends on the parameters under test and on the unknown absolute radiance scale.
BASE_EXPOSURE = 1e-9

# Lateral sun offset that lands the core ~1/3 of the way toward the right edge, leaving room
# for the ghosts (which sit between image center and the core) and a corona annulus.
SUN_OFFSET_X = 1.8e10

# Representative (green / center-channel) ghost offsets from LensFlares.usf: each ghost sits at
# offset * SunUV, i.e. offset of the way along the vector from image center to the sun core.
GHOST_OFFSETS = {1: 0.325, 2: 0.2, 3: 0.45, 4: 0.85}

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
STRAY_LIGHT_TUNING = {
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


def _apply_tuning_overrides(spec):
    """Apply whitespace-separated ``key=value`` overrides onto STRAY_LIGHT_TUNING.

    Called at import time from the ``stray_light_tuning`` env var so command-line overrides set by
    the __main__ entrypoint survive pytest re-importing this file as a module.
    """
    for item in spec.split():
        key, _, val = item.partition("=")
        key = key.strip()
        if key not in STRAY_LIGHT_TUNING:
            print(f"[tuning] unknown knob '{key}' (valid: {', '.join(STRAY_LIGHT_TUNING)})")
            continue
        if key == "ghost_relative_sizes":
            STRAY_LIGHT_TUNING[key] = tuple(float(v) for v in val.split(","))
        else:
            STRAY_LIGHT_TUNING[key] = float(val)
        print(f"[tuning] {key} = {STRAY_LIGHT_TUNING[key]}")


_tuning_overrides = os.environ.get("stray_light_tuning", "")
if _tuning_overrides:
    _apply_tuning_overrides(_tuning_overrides)


def _ghost_params(overrides=None):
    """STRAY_LIGHT_TUNING knobs with per-test overrides merged on top."""
    params = dict(STRAY_LIGHT_TUNING)
    if overrides:
        params.update(overrides)
    return params


def stray_light_scene(
    sun_offset=(0.0, 0.0),
    sun_distance=AU,
    sun_position=None,
    exposure=BASE_EXPOSURE,
    width=WIDTH,
    height=HEIGHT,
    fov=FOV,
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


def sun_at_angle(angle_deg, distance=AU):
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
        raise AssertionError("No image returned from renderer")
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


def bright_pixel_count(gray, frac=0.6):
    """Count pixels brighter than ``frac`` of the image max."""
    peak = float(np.max(gray))
    if peak <= 0:
        return 0
    return int(np.count_nonzero(gray >= frac * peak))


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
# below saturation. Results are cached per scene key so parametrized tests don't re-calibrate.
_EXPOSURE_CACHE = {}


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


def cached_exposure(connector, key, build_scene, target=160, measure=None):
    """calibrate_exposure with a per-key cache (one calibration per distinct scene shape)."""
    if key not in _EXPOSURE_CACHE:
        _EXPOSURE_CACHE[key] = calibrate_exposure(connector, build_scene, target=target, measure=measure)
    return _EXPOSURE_CACHE[key]


def ghost_positions(core_pix, img_center):
    """Map each ghost index to its expected pixel position: center + offset*(core - center)."""
    mx, my = img_center
    cx, cy = core_pix
    return {idx: (mx + off * (cx - mx), my + off * (cy - my)) for idx, off in GHOST_OFFSETS.items()}


def _show(gray, title):
    if not show_plots:
        return
    plt.figure(figsize=(5, 5))
    plt.imshow(gray, cmap="gray", vmin=0, vmax=255)
    plt.title(title)
    plt.tight_layout()
    plt.show()


# ===========================================================================
# Gating: geometry + enable flag
# ===========================================================================


@pytest.mark.parametrize(
    "test_name, sun_z, expect_flare",
    [
        ("sun in front (+Z)", AU, True),
        ("sun behind (-Z)", -AU, False),
    ],
)
def test_flare_gated_by_sun_in_front(cielim_connection, test_name, sun_z, expect_flare):
    """The pass fires only when the sun projects in front of the camera (SunClipPosition.w > 0)."""
    scene = stray_light_scene(sun_distance=abs(sun_z))
    scene.set_celestial_body_params(0, position=(0, 0, sun_z))

    gray = render_gray(cielim_connection, scene)
    peak = float(np.max(gray))
    _show(gray, f"{test_name}  (max={peak:.0f})")

    if expect_flare:
        assert peak > 50, f"[{test_name}] expected a visible flare, got max pixel {peak:.0f}"
    else:
        assert peak < 5, f"[{test_name}] expected no flare (sun behind camera), got max {peak:.0f}"


def test_flare_enable_toggle(cielim_connection):
    """With the sun in front, the flare appears only when strayLightModel.enabled is true."""
    scene_off = stray_light_scene(stray_light={"enabled": False})
    off = float(np.max(render_gray(cielim_connection, scene_off)))

    scene_on = stray_light_scene(stray_light={"enabled": True})
    on = float(np.max(render_gray(cielim_connection, scene_on)))

    assert off < 5, f"Stray light disabled should give a black frame, got max {off:.0f}"
    assert on > 50, f"Stray light enabled should give a visible flare, got max {on:.0f}"


# ===========================================================================
# Core: position and size (SunClipPosition, SunRadiusUV, coreSize)
# ===========================================================================


def test_flare_core_centered_on_axis(cielim_connection):
    """With the sun on the optical axis, the flare core is centered in the image."""
    gray = render_gray(cielim_connection, stray_light_scene(sun_offset=(0.0, 0.0)))
    centroid = bright_centroid(gray)
    assert centroid is not None, "No flare core found for on-axis sun"
    _show(gray, f"On-axis sun — core at {centroid[0]:.0f},{centroid[1]:.0f}")
    np.testing.assert_allclose(centroid, [WIDTH / 2.0, HEIGHT / 2.0], atol=8, err_msg="On-axis core not centered")


@pytest.mark.parametrize(
    "test_name, axis, offsets",
    [
        ("horizontal", "x", [-8e9, -4e9, 0.0, 4e9, 8e9]),
        ("vertical", "y", [-8e9, -4e9, 0.0, 4e9, 8e9]),
    ],
)
def test_flare_core_tracks_sun(cielim_connection, test_name, axis, offsets):
    """The flare core centroid moves monotonically and symmetrically as the sun sweeps the FoV."""
    coords = []
    for off in offsets:
        sun_offset = (off, 0.0) if axis == "x" else (0.0, off)
        c = bright_centroid(render_gray(cielim_connection, stray_light_scene(sun_offset=sun_offset)))
        assert c is not None, f"[{test_name}] no flare core at offset {off:g}"
        coords.append(c[0] if axis == "x" else c[1])
    coords = np.array(coords)
    center = WIDTH / 2.0 if axis == "x" else HEIGHT / 2.0

    np.testing.assert_allclose(
        coords[len(offsets) // 2], center, atol=8, err_msg=f"[{test_name}] on-axis core not centered"
    )
    diffs = np.diff(coords)
    assert np.all(diffs > 1.0) or np.all(
        diffs < -1.0
    ), f"[{test_name}] core does not track the sun monotonically: {coords.tolist()}"
    np.testing.assert_allclose(
        abs(coords[0] - center),
        abs(coords[-1] - center),
        rtol=0.25,
        err_msg=f"[{test_name}] core displacement asymmetric: {coords.tolist()}",
    )


def test_core_size_grows_with_proximity(cielim_connection):
    """The core grows as the sun gets closer (larger SunRadiusUV)."""
    distances = [1.0 * AU, 0.3 * AU, 0.1 * AU]
    counts = [
        bright_pixel_count(render_gray(cielim_connection, stray_light_scene(sun_distance=d)), 0.6) for d in distances
    ]
    assert all(n > 0 for n in counts), f"Flare core missing at some distance: {counts}"
    for i in range(1, len(counts)):
        assert counts[i] > counts[i - 1], (
            f"Core did not grow as sun approached: distances={[d / AU for d in distances]} AU, " f"counts={counts}"
        )


@requires_params
def test_core_size_parameter(cielim_connection):
    """Increasing coreSize widens the crisp core disc (more high-brightness pixels)."""
    sizes = [0.5, 1.0, 2.0]
    counts = []
    for cs in sizes:
        gray = render_gray(cielim_connection, stray_light_scene(stray_light={"core_size": cs}))
        counts.append(bright_pixel_count(gray, frac=0.9))
        _show(gray, f"coreSize={cs} — {counts[-1]} bright px")
    assert all(n > 0 for n in counts), f"Core missing for some coreSize: {counts}"
    for i in range(1, len(counts)):
        assert counts[i] > counts[i - 1], f"coreSize did not grow the core: sizes={sizes}, counts={counts}"


def test_flare_brightness_scales_with_exposure(cielim_connection):
    """The flare's overall intensity scales with exposure time, and a realistic exposure (0.1 s)
    clearly saturates the sun at 1 AU — no artificial overdrive needed.

    The flare is added as radiance and the QuE tonemap multiplies by ExposureTime before clipping,
    so the core-region brightness rises with exposure (then plateaus at the full-well ceiling).
    """
    center = (WIDTH / 2.0, HEIGHT / 2.0)

    exposures = [1e-11, 1e-10, 1e-9, 1e-8]
    peaks = []
    for e in exposures:
        gray = render_gray(cielim_connection, stray_light_scene(sun_offset=(0.0, 0.0), exposure=e))
        peaks.append(region_peak(gray, center, half=5))
    # Non-decreasing (rises then plateaus at saturation), allowing 1 LSB of quantisation slack.
    for i in range(1, len(peaks)):
        assert (
            peaks[i] >= peaks[i - 1] - 1
        ), f"Flare should brighten (or plateau) with exposure: exposures={exposures}, peaks={peaks}"

    # A realistic 0.1 s exposure of the sun at 1 AU blows the core out to white.
    gray = render_gray(cielim_connection, stray_light_scene(sun_offset=(0.0, 0.0), exposure=0.1))
    peak = region_peak(gray, center, half=5)
    assert peak >= 254, f"Sun core should saturate at a 0.1 s exposure, got peak={peak:.0f}"


# ===========================================================================
# Ghosts: size, brightness/size coupling, per-ghost relative size, transmittance
# ===========================================================================


GHOST_HALF = 45  # half-window (px) around a ghost position for peak measurements
GHOST_TARGET = 150  # calibration target peak (below saturation so size/brightness stay measurable)


def ghost_residual_map(gray, core, sigma=15, core_mask_r=110):
    """High-pass residual isolating the ghost "bumps" in the strip between center and core.

    Per-ghost windows are unreliable here: the ghosts overlap, sit on the smooth corona, and the
    shader's UV-mix (``lerp(PixelUV, UVDistorted, -0.5)``) renders them at ~0.667*offset*SunUV, not
    at the offset*SunUV the position model assumes. So we work on the whole band: high-pass the
    frame (image minus a large Gaussian blur) to strip the smooth corona, keeping the sharp ghost
    bumps; mask out the bright core and everything sunward of it. Robust to exact ghost positions
    and to the corona pedestal.
    """
    f = gray.astype(np.float32)
    hp = np.clip(f - cv2.GaussianBlur(f, (0, 0), sigmaX=sigma), 0.0, None)
    h, w = gray.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    hp[np.sqrt((xx - core[0]) ** 2 + (yy - core[1]) ** 2) < core_mask_r] = 0.0
    if core[0] >= WIDTH / 2.0:  # keep only the center->core side (where the ghosts live)
        hp[:, int(round(core[0])) :] = 0.0
    else:
        hp[:, : int(round(core[0]))] = 0.0
    return hp


def ghost_band_signal(gray, core, **kw):
    """Total ghost-band signal — rises with ghostSize / ghostTransmittance."""
    return float(ghost_residual_map(gray, core, **kw).sum())


def ghost_window_peak(gray, ghost_idx=3, half=GHOST_HALF):
    """Peak pixel in the given ghost's window — a calibration measure that ignores the bright core,
    which clips to 255 at the ghost-visible exposures and would otherwise pin the global max."""
    core = bright_centroid(gray, frac=0.9)
    if core is None:
        return 0.0
    g = ghost_positions(core, (WIDTH / 2.0, HEIGHT / 2.0))[ghost_idx]
    return region_peak(gray, g, half)


def _ghost_scene(exposure, stray_light=None):
    """Off-center base scene with the GHOST_VISIBLE preset (faint corona, brighter ghosts)."""
    return stray_light_scene(sun_offset=(SUN_OFFSET_X, 0.0), exposure=exposure, stray_light=_ghost_params(stray_light))


def _core_and_ghosts(connector, exposure, stray_light=None):
    """Render the off-center base scene and return (gray, core_pix, ghost_pix_dict)."""
    gray = render_gray(connector, _ghost_scene(exposure, stray_light))
    core = bright_centroid(gray, frac=0.9)
    assert core is not None, "No flare core found in off-center base scene"
    return gray, core, ghost_positions(core, (WIDTH / 2.0, HEIGHT / 2.0))


@requires_params
def test_ghost_size_grows_and_dims(cielim_connection):
    """Increasing ghostSize spreads the ghosts, raising the total ghost-band signal.

    Measured on the whole ghost band (corona removed, core masked) rather than a single ghost
    window, because the ghosts overlap and the shader's UV-mix shifts their exact positions.
    """
    sizes = [0.6, 1.0, 1.6]
    # Calibrate the exposure on the ghost region (not the bright core) at the smallest size.
    exp = calibrate_exposure(
        cielim_connection,
        lambda e: _ghost_scene(e, {"ghost_size": sizes[0]}),
        target=GHOST_TARGET,
        measure=ghost_window_peak,
    )
    signals = []
    for gs in sizes:
        gray, core, _ = _core_and_ghosts(cielim_connection, exp, {"ghost_size": gs})
        signals.append(ghost_band_signal(gray, core))
        _show(gray, f"ghostSize={gs} — band={signals[-1]:.2e}")
    assert all(s > 0 for s in signals), f"No ghost-band signal at some ghostSize: {signals}"
    assert (
        signals[-1] > signals[0]
    ), f"Larger ghostSize should raise the ghost-band signal: sizes={sizes}, signals={signals}"


@requires_params
def test_ghost_brightness_size_coupling(cielim_connection):
    """At a fixed (small) ghostSize, a larger brightness/size exponent makes ghosts brighter."""
    exponents = [1.0, 2.0, 3.0]
    base = {"ghost_size": 0.5}
    # Calibrate at the largest exponent (brightest for size < 1) so it lands below saturation.
    exp = calibrate_exposure(
        cielim_connection,
        lambda e: _ghost_scene(e, {**base, "ghost_brightness_size_exponent": exponents[-1]}),
        target=GHOST_TARGET,
        measure=ghost_window_peak,
    )
    peaks = []
    for ex in exponents:
        gray, _, ghosts = _core_and_ghosts(cielim_connection, exp, {**base, "ghost_brightness_size_exponent": ex})
        peaks.append(region_peak(gray, ghosts[3], half=GHOST_HALF))
    assert all(p > 0 for p in peaks), f"Ghost 3 not found at some exponent: peaks={peaks}"
    assert peaks[-1] > peaks[0], (
        f"Smaller ghosts (size 0.5) should brighten as the exponent rises: " f"exponents={exponents}, peaks={peaks}"
    )


@requires_params
@pytest.mark.parametrize("ghost_idx", [1, 2, 3])
def test_ghost_relative_size(cielim_connection, ghost_idx):
    """Changing one ghost's relative size measurably changes the ghost band.

    Per-ghost isolation isn't reliable (ghosts overlap, sit on the corona, and the shader's UV-mix
    shifts their positions), and the energy-conserving size/brightness coupling means a bigger ghost
    is also dimmer — so the band signal's *direction* isn't a clean monotonic. We assert the
    parameter is wired and affects the image: bumping ghost N's relative size shifts the band signal
    by a clear margin.
    """

    def sizes_with(idx, value):
        s = [1.0, 1.0, 1.0, 1.0]
        s[idx - 1] = value
        return tuple(s)

    exp = cached_exposure(
        cielim_connection, "ghost_base", lambda e: _ghost_scene(e), target=GHOST_TARGET, measure=ghost_window_peak
    )

    gray_base, core_base, _ = _core_and_ghosts(cielim_connection, exp)
    gray_big, core_big, _ = _core_and_ghosts(
        cielim_connection, exp, {"ghost_relative_sizes": sizes_with(ghost_idx, 3.0)}
    )

    # Per-pixel difference of the residual maps (same core position, so they're aligned). This is
    # far more sensitive than the net total: it captures the ghost's local change without the
    # grow-vs-dim cancellation that shrinks a single ghost's effect on the whole-band sum.
    res_base = ghost_residual_map(gray_base, core_base)
    res_big = ghost_residual_map(gray_big, core_big)
    base_total = float(res_base.sum())
    assert base_total > 0, "No ghost-band signal in the base scene"
    change = float(np.abs(res_big - res_base).sum()) / base_total
    assert change > 0.05, (
        f"Ghost {ghost_idx} relative size had no measurable effect on the ghost band: "
        f"change={change:.1%} (base_total={base_total:.2e})"
    )


@requires_params
def test_ghost_transmittance(cielim_connection):
    """Increasing ghostTransmittance brightens the ghosts without moving them."""
    transmittances = [0.5, 1.0, 2.0]
    # Calibrate at the highest transmittance (brightest) so it lands below saturation.
    exp = calibrate_exposure(
        cielim_connection,
        lambda e: _ghost_scene(e, {"ghost_transmittance": transmittances[-1]}),
        target=GHOST_TARGET,
        measure=ghost_window_peak,
    )
    peaks = []
    for t in transmittances:
        gray, _, ghosts = _core_and_ghosts(cielim_connection, exp, {"ghost_transmittance": t})
        peaks.append(region_peak(gray, ghosts[3], half=GHOST_HALF))
    assert all(p > 0 for p in peaks), f"Ghost 3 not found at some transmittance: peaks={peaks}"
    assert peaks[-1] > peaks[0], f"Higher transmittance should brighten ghosts: peaks={peaks}"


# ===========================================================================
# Targeted corona tuning: centered sun + radial brightness profile
# ===========================================================================
# The off-boresight sweep is a poor instrument for the corona: it is faint, off-axis, and the
# auto-exposure normalizes the core, so radial changes are invisible in a whole-frame filmstrip.
# This test centers the sun (ghosts collapse onto the core, so the outer profile is pure corona)
# and plots the radial brightness profile — mean brightness vs distance from the core — at a
# single fixed exposure, which makes each corona knob's effect obvious.
#
# Tune the corona with:  python tests/test_stray_light.py   (after switching the __main__
# entrypoint to test_corona_response — see the bottom of this file), or:
#   pytest tests/test_stray_light.py -k corona_response -s

CORONA_R_MAX = 400  # radial profile extent (px)
CORONA_BAND = (80, 300)  # radius band (px) sampled as the "corona shoulder" for assertions


def _radial_profile(gray, center, r_max=CORONA_R_MAX, n_bins=80):
    """Return (radii, mean_brightness) in concentric annuli from the center out to r_max."""
    h, w = gray.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2)
    edges = np.linspace(0, r_max, n_bins + 1)
    radii = 0.5 * (edges[:-1] + edges[1:])
    means = np.zeros(n_bins)
    for i in range(n_bins):
        mask = (r >= edges[i]) & (r < edges[i + 1])
        if np.any(mask):
            means[i] = float(gray[mask].mean())
    return radii, means


def _corona_shoulder(profile, band=CORONA_BAND):
    """Mean profile brightness across the corona-shoulder radius band."""
    r, m = profile
    sel = (r >= band[0]) & (r <= band[1])
    return float(m[sel].mean()) if np.any(sel) else 0.0


def corona_shoulder_of(gray):
    """Corona-shoulder brightness of a centered-sun frame — a calibration measure that ignores
    the bright core (which clips to 255 inside the CORONA_BAND inner radius)."""
    return _corona_shoulder(_radial_profile(gray, (WIDTH / 2.0, HEIGHT / 2.0)))


@requires_params
def test_corona_response(cielim_connection):
    """Centered sun: verify and visualize the corona knobs via the radial brightness profile.

      corona_intensity        -> raises the whole corona shoulder
      corona_falloff_exponent -> steepens it (shoulder drops, tighter glow)

    The corona is a fixed, exposure-independent power-law aureole (its size does not change with
    exposure). Both variants share ONE fixed exposure (calibrated on the corona shoulder) so the
    amplitude/shape changes are directly comparable.
    """
    center = (WIDTH / 2.0, HEIGHT / 2.0)

    # One fixed exposure for every variant, calibrated on the corona SHOULDER at the brightest
    # corona (the core always clips to white, so we drive the shoulder, not the global max).
    exp = calibrate_exposure(
        cielim_connection,
        lambda e: stray_light_scene(
            sun_offset=(0.0, 0.0), exposure=e, stray_light=_ghost_params({"corona_intensity": 0.4})
        ),
        target=120,
        measure=corona_shoulder_of,
    )

    def profile(overrides):
        gray = render_gray(
            cielim_connection,
            stray_light_scene(sun_offset=(0.0, 0.0), exposure=exp, stray_light=_ghost_params(overrides)),
        )
        return _radial_profile(gray, center)

    # With the crisp exponential core, the corona owns the wide glow, so these span a visible range.
    intensities = [0.05, 0.15, 0.4]
    falloffs = [1.2, 2.5, 5.0]

    prof_i = [profile({"corona_intensity": v}) for v in intensities]
    prof_f = [profile({"corona_intensity": 0.3, "corona_falloff_exponent": v}) for v in falloffs]

    if show_plots:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
        for (r, m), v in zip(prof_i, intensities):
            axes[0].plot(r, m, label=f"{v}")
        for (r, m), v in zip(prof_f, falloffs):
            axes[1].plot(r, m, label=f"{v}")
        for ax, title in zip(axes, ["corona_intensity", "corona_falloff_exponent"]):
            ax.axvspan(CORONA_BAND[0], CORONA_BAND[1], color="gray", alpha=0.1)
            ax.set_xlabel("radius from core (px)")
            ax.set_title(title)
            ax.legend()
        axes[0].set_ylabel("mean brightness (0-255)")
        fig.suptitle(f"Corona radial profile — centered sun, fixed exposure {exp:.1e}")
        plt.tight_layout()
        plt.show()

    si = [_corona_shoulder(p) for p in prof_i]
    sf = [_corona_shoulder(p) for p in prof_f]
    print(f"\n[corona] exposure={exp:.2e}")
    print(f"[corona] intensity {intensities} -> shoulder {[round(x, 2) for x in si]}")
    print(f"[corona] falloff   {falloffs} -> shoulder {[round(x, 2) for x in sf]}")

    assert si[-1] > si[0], f"Higher corona_intensity should raise the corona shoulder: {intensities} -> {si}"
    assert sf[-1] < sf[0], f"Higher corona_falloff_exponent should lower the shoulder: {falloffs} -> {sf}"


# ===========================================================================
# Rays: number, sharpness, weight of the symmetric rays
# ===========================================================================
# The rays are the azimuthal structure of the flare, so they are measured on an annulus around a
# centered sun: sample mean brightness vs azimuth at a fixed radius. The core/corona are radially
# symmetric (a constant offset around the ring), so all the azimuthal variation is the rays.

RAY_RADIUS = 200  # px from the core at which to sample the ray annulus
RAY_ANNULUS_DR = 10  # half-thickness of the annulus (px)


def _azimuthal_profile(gray, center, radius=RAY_RADIUS, dr=RAY_ANNULUS_DR, n_bins=180):
    """Mean brightness in a thin annulus at ``radius``, binned by azimuth angle (n_bins)."""
    h, w = gray.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dx, dy = xx - center[0], yy - center[1]
    r = np.sqrt(dx * dx + dy * dy)
    ring = (r >= radius - dr) & (r <= radius + dr)
    ang = np.arctan2(dy[ring], dx[ring]) % (2 * np.pi)
    bins = np.clip((ang / (2 * np.pi) * n_bins).astype(int), 0, n_bins - 1)
    vals = gray[ring].astype(float)
    sums = np.bincount(bins, weights=vals, minlength=n_bins)
    counts = np.bincount(bins, minlength=n_bins)
    return np.divide(sums, counts, out=np.zeros(n_bins), where=counts > 0)


@requires_params
def test_ray_parameters(cielim_connection):
    """The three ray knobs each do their one thing on the azimuthal (ray) structure:

      numRays      -> more rays: higher dominant azimuthal frequency (more peaks around the ring)
      rayWeight    -> stronger rays: higher azimuthal contrast (peak-to-trough)
      raySharpness -> crisper rays: each ray covers a smaller fraction of the ring

    Measured on a centered sun (rays form a full star) with the ray weight boosted so the symmetric
    rays dominate the random streaks. One shared exposure, calibrated on the ray peak below clipping.
    """
    center = (WIDTH / 2.0, HEIGHT / 2.0)
    base = {"ray_weight": 3.0}  # boost so the symmetric rays dominate the random streaks

    def build(e, extra):
        return stray_light_scene(sun_offset=(0.0, 0.0), exposure=e, stray_light=_ghost_params({**base, **extra}))

    def ray_peak(gray):
        return float(_azimuthal_profile(gray, center).max())

    exp = calibrate_exposure(cielim_connection, lambda e: build(e, {"num_rays": 6.0}), target=120, measure=ray_peak)

    def profile(extra):
        gray = render_gray(cielim_connection, build(exp, extra))
        return _azimuthal_profile(gray, center)

    # (1) numRays -> dominant azimuthal frequency (peak count) rises
    def dominant_freq(prof):
        spec = np.abs(np.fft.rfft(prof - prof.mean()))
        spec[0] = 0.0  # ignore the DC term
        return int(np.argmax(spec))

    f_few = dominant_freq(profile({"num_rays": 4.0}))
    f_many = dominant_freq(profile({"num_rays": 12.0}))
    assert f_many > f_few, f"More rays should raise the azimuthal frequency: numRays 4->12 gave freq {f_few}->{f_many}"

    # (2) rayWeight -> azimuthal contrast (peak - trough) rises
    def contrast(prof):
        return float(prof.max() - prof.min())

    c_weak = contrast(profile({"num_rays": 6.0, "ray_weight": 1.0}))
    c_strong = contrast(profile({"num_rays": 6.0, "ray_weight": 3.0}))
    assert c_strong > c_weak, f"Higher rayWeight should raise the ray contrast: {c_weak:.1f} -> {c_strong:.1f}"

    # (3) raySharpness -> each ray narrows, so a smaller fraction of the ring is above the midline
    def frac_lit(prof):
        mid = 0.5 * (prof.max() + prof.min())
        return float(np.mean(prof > mid))

    a_soft = frac_lit(profile({"num_rays": 6.0, "ray_sharpness": 8.0}))
    a_sharp = frac_lit(profile({"num_rays": 6.0, "ray_sharpness": 48.0}))
    assert a_sharp < a_soft, f"Higher raySharpness should narrow the rays: lit fraction {a_soft:.2f} -> {a_sharp:.2f}"


# ===========================================================================
# Grayscale (driven from the image settings, not a stray-light field)
# ===========================================================================


# Diagonal QE: each output channel responds to a single wavelength (R<-650nm, G<-550nm, B<-450nm).
# The scene default QE is identity (all 1.0), which makes every output channel integrate the SAME
# wavelength sum -> the flare is achromatic regardless of input. Diagonal QE lets the flare's
# chromatic ghost R/B offsets (IsGrayscale=0) produce real channel differences.
DIAGONAL_QE = dict(qe_chan1=(1.0, 0.0, 0.0), qe_chan2=(0.0, 1.0, 0.0), qe_chan3=(0.0, 0.0, 1.0))


def channel_spread_in_ghosts(color_img, half=GHOST_HALF):
    """Max |B - R| within the ghost windows (where the chromatic R/B offset lives).

    Measured in the ghosts, not whole-frame: the bright core clips to white (B==R) and the
    background is black, so a whole-frame max would miss the small chromatic signal in the ghosts.
    """
    gray = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
    core = bright_centroid(gray, frac=0.9)
    if core is None:
        return 0
    diff = np.abs(color_img[..., 0].astype(int) - color_img[..., 2].astype(int))
    ghosts = ghost_positions(core, (WIDTH / 2.0, HEIGHT / 2.0))
    spread = 0
    for g in ghosts.values():
        win = region(diff, g, half)
        if win.size:
            spread = max(spread, int(np.max(win)))
    return spread


@requires_params
def test_grayscale_from_image_settings(cielim_connection):
    """Color image → chromatic flare (channel separation in the ghosts); grayscale image → achromatic.

    Root cause of the old failure: default QE is identity, so all output channels are equal. This
    test sets DIAGONAL QE on both scenes so the flare's chromatic ghost offsets can register; the
    only difference between the two renders is then the image grayscale flag. Measured in the ghost
    windows, below saturation (calibrated on the ghost peak so the ghosts aren't clipped).
    """

    def build_color(e):
        s = stray_light_scene(sun_offset=(SUN_OFFSET_X, 0.0), exposure=e, grayscale=False, stray_light=_ghost_params())
        s.set_sensor_params(**DIAGONAL_QE)
        return s

    exp = calibrate_exposure(cielim_connection, build_color, target=GHOST_TARGET, measure=ghost_window_peak)

    color = render_color(cielim_connection, build_color(exp))
    gray_scene = stray_light_scene(
        sun_offset=(SUN_OFFSET_X, 0.0), exposure=exp, grayscale=True, stray_light=_ghost_params()
    )
    gray_scene.set_sensor_params(**DIAGONAL_QE)
    gray = render_color(cielim_connection, gray_scene)

    assert color.ndim == 3 and gray.ndim == 3, "Expected 3-channel images from the renderer"

    color_spread = channel_spread_in_ghosts(color)
    gray_spread = channel_spread_in_ghosts(gray)

    assert gray_spread <= 2, f"Grayscale image should have equal channels, got max |B-R|={gray_spread}"
    assert color_spread > 5, f"Color flare should show chromatic ghost separation, got max |B-R|={color_spread}"


# ===========================================================================
# Off-boresight sweep: progressively offset the sun off boresight through the shield regimes
# ===========================================================================
#
# A narrow FoV is used so the sun genuinely leaves the frame partway through the sweep, exercising
# all three regimes of the angle-based (baffle-shield) gating in one pass:
#   |angle| <= FoV/2                      -> sun in frame: core visible and tracks the sun
#   FoV/2 < |angle| < FoV/2 + baffle      -> sun off frame but within the shield: ghosts still streak in
#   |angle| > FoV/2 + baffle              -> beyond the shield: no stray light at all
# With FoV = 20 deg (half-angle 10) and baffle = 35 deg the cutoff is 45 deg, so the sweep angles
# below sit cleanly in each regime: {0, +-4, +-8} in frame, +-20 off-frame-but-flaring, +-55 dark.

SWEEP_FOV = np.radians(20)  # narrow FoV so the sun leaves the frame; half-angle = 10 deg
SWEEP_BAFFLE = 35.0  # baffle shield (deg); stray-light cutoff = FoV/2 + this = 45 deg
SWEEP_CAL_ANGLE = 8  # exposure-calibration angle (in frame, near the edge, ghosts clear of the core)
SWEEP_ANGLES = [-55, -30, -16, -8, 0, 8, 16, 30, 55]


def _sweep_scene(angle_deg, exposure, extra=None):
    """A sweep/off-axis scene: sun at ``angle_deg`` off boresight, narrow FoV, baffle shield set."""
    sl = {"baffle_shield_angle": SWEEP_BAFFLE}
    if extra:
        sl.update(extra)
    return stray_light_scene(
        sun_position=sun_at_angle(angle_deg), fov=SWEEP_FOV, exposure=exposure, stray_light=_ghost_params(sl)
    )


def _sweep_filmstrip(grays, angles, title):
    if not show_plots:
        return
    fig, axes = plt.subplots(1, len(angles), figsize=(2.0 * len(angles), 2.4))
    for ax, gray, ang in zip(axes, grays, angles):
        ax.imshow(gray, cmap="gray", vmin=0, vmax=255)
        ax.axvline(WIDTH / 2, color="r", lw=0.4, ls="--")
        ax.set_title(f"{ang:+d}°", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(title)
    plt.tight_layout()
    plt.show()


def test_ghost_sweep_across_boresight(cielim_connection):
    """Sweep the sun off boresight through all three regimes of the baffle-shield gating.

    With FoV/2 = 10 deg and baffle = 35 deg (cutoff 45 deg), asserts robustly to coordinate
    handedness: (1) the flare is present both in frame AND off frame within the shield (|angle| <= 20);
    (2) it is gated fully OFF beyond the shield (|angle| = 55); (3) it is centered at 0 deg; (4) the
    core tracks the sun outward while in frame; (5) off-frame-within-shield the flare sits off-center
    toward the sun; and (6) +theta and -theta produce mirror-image flares.
    """
    # Calibrate on the ghosts at an in-frame edge angle (core in frame and clear of the ghosts) and
    # reuse across the sweep. Calibrating at 0 deg would measure the core (ghosts collapse onto it),
    # and the global max is pinned at 255 by the bright core.
    exp = cached_exposure(
        cielim_connection,
        "sweep",
        lambda e: _sweep_scene(SWEEP_CAL_ANGLE, e),
        target=GHOST_TARGET,
        measure=ghost_window_peak,
    )

    fov_half = np.degrees(SWEEP_FOV) / 2.0  # 10 deg
    cutoff = fov_half + SWEEP_BAFFLE  # 45 deg

    grays, centroids, maxes = [], [], []
    for ang in SWEEP_ANGLES:
        gray = render_gray(cielim_connection, _sweep_scene(ang, exp))
        grays.append(gray)
        maxes.append(float(np.max(gray)))
        centroids.append(bright_centroid(gray, frac=0.5))

    _sweep_filmstrip(
        grays, SWEEP_ANGLES, f"Off-boresight sun sweep ({np.degrees(SWEEP_FOV):.0f}° FoV, {SWEEP_BAFFLE:.0f}° baffle)"
    )

    center = WIDTH / 2.0
    cx = {ang: (c[0] if c else None) for ang, c in zip(SWEEP_ANGLES, centroids)}
    mx = dict(zip(SWEEP_ANGLES, maxes))

    # Regime boundaries derived from the geometry, so the checks track whatever SWEEP_ANGLES are set.
    # "visible" is comfortably inside full visibility: the shader holds intensity until 75% of the way
    # through the baffle region and only then fades, so half-way is safely bright.
    visible_bound = fov_half + 0.5 * SWEEP_BAFFLE

    def dist_at(mag):
        """|centroid - center| for the angle of magnitude ``mag`` whose centroid was found (+ or -)."""
        for a in (mag, -mag):
            if cx.get(a) is not None:
                return abs(cx[a] - center)
        return None

    # (1) present in frame AND off frame while comfortably within the shield
    for ang in SWEEP_ANGLES:
        if abs(ang) <= visible_bound:
            assert mx[ang] > 30, f"No flare at {ang:+g} deg (within the shield); max pixel {mx[ang]:.0f}"

    # (2) gated fully off beyond the shield cutoff
    for ang in SWEEP_ANGLES:
        if abs(ang) > cutoff:
            assert (
                mx[ang] < 5
            ), f"Flare should be gated off beyond the {cutoff:.0f} deg shield at {ang:+g} deg (max {mx[ang]:.0f})"

    # (3) centered on boresight at 0 deg (allow a little slack for the random streaks)
    if 0 in cx:
        assert cx[0] is not None and abs(cx[0] - center) < 15, f"0 deg flare not centered (x={cx[0]})"

    # (4) monotonic outward motion while the core is still in frame (|angle| <= fov_half). The centroid
    # jumps inward once the core leaves the frame (it then tracks the ghosts), so this is in-frame only.
    in_frame_mags = sorted({abs(a) for a in SWEEP_ANGLES if abs(a) <= fov_half})
    dists = [d for d in (dist_at(m) for m in in_frame_mags) if d is not None]
    if len(dists) >= 2:
        assert all(
            b > a for a, b in zip(dists, dists[1:])
        ), f"Core did not track the sun outward while in frame: {dists}"

    # (5) off frame but within the shield: the flare sits off-center toward the sun
    for ang in SWEEP_ANGLES:
        if fov_half < abs(ang) <= visible_bound and cx.get(ang) is not None:
            assert abs(cx[ang] - center) > 50, f"Off-frame flare at {ang:+g} deg should be off-center (x={cx[ang]:.0f})"

    # (6) mirror symmetry: +theta and -theta land on opposite sides, ~equidistant from center. The
    # random component of the streaks is not a pixel-perfect mirror, so this is a "roughly symmetric"
    # check (rtol) rather than exact — the sign check already catches handedness bugs.
    for mag in sorted({abs(a) for a in SWEEP_ANGLES if 0 < abs(a) <= visible_bound}):
        cp, cn = cx.get(mag), cx.get(-mag)
        if cp is None or cn is None:
            continue  # need both signs present to compare
        assert np.sign(cp - center) == -np.sign(
            cn - center
        ), f"+/-{mag:g} deg flares are not on opposite sides of boresight ({cp:.0f} vs {cn:.0f})"
        np.testing.assert_allclose(
            abs(cp - center),
            abs(cn - center),
            rtol=0.15,
            atol=25,
            err_msg=f"+/-{mag:g} deg flares are not roughly symmetric ({cp:.0f} vs {cn:.0f})",
        )


def test_ghosts_visible_with_sun_out_of_frame(cielim_connection):
    """Off frame but within the shield: at 25 deg off boresight (20 deg FoV -> 10 deg half-angle,
    35 deg baffle -> 45 deg cutoff) the sun core projects outside the frame, yet the inner ghosts
    stay visible and off-center toward the sun. This is the middle regime of the baffle gating."""
    ang = 25

    # Reuse the sweep's ghost-calibrated exposure (calibrated in frame near the FoV edge). Calibrating
    # here is unreliable: at 25 deg the core is off-screen so there's no on-screen core for
    # ghost_window_peak to anchor to, and the global max would collapse the exposure.
    exp = cached_exposure(
        cielim_connection,
        "sweep",
        lambda e: _sweep_scene(SWEEP_CAL_ANGLE, e),
        target=GHOST_TARGET,
        measure=ghost_window_peak,
    )
    gray = render_gray(cielim_connection, _sweep_scene(ang, exp))
    _show(gray, f"Sun {ang} deg off boresight (core out of frame, within shield)")

    assert float(np.max(gray)) > 30, "Expected ghosts to remain visible with the sun off frame but within the shield"
    c = bright_centroid(gray, frac=0.5)
    assert (
        c is not None and abs(c[0] - WIDTH / 2.0) > 50
    ), f"Ghost streak should sit off-center toward the sun (x={c[0] if c else None})"


@requires_params
def test_ghost_parameters_respond_off_axis(cielim_connection):
    """Off axis but in frame (near the FoV edge), the ghost parameters still behave as expected:
    higher transmittance brightens the ghosts, larger ghost size enlarges them. Measured in frame
    (core locatable) so the ghost windows anchor correctly."""
    ang = SWEEP_CAL_ANGLE  # off axis, still in frame so the core anchors the ghost windows

    def build(e, sl):
        return _sweep_scene(ang, e, sl)

    def measure(exp, sl):
        gray = render_gray(cielim_connection, build(exp, sl))
        core = bright_centroid(gray, frac=0.9)
        assert core is not None, "No flare core found in off-axis scene"
        return gray, ghost_positions(core, (WIDTH / 2.0, HEIGHT / 2.0))

    # Transmittance up -> ghost 3 brighter (calibrate at the brightest transmittance)
    transmittances = [0.5, 1.0, 2.0]
    exp_t = calibrate_exposure(
        cielim_connection,
        lambda e: build(e, {"ghost_transmittance": transmittances[-1]}),
        target=GHOST_TARGET,
        measure=ghost_window_peak,
    )
    peaks = []
    for t in transmittances:
        gray, ghosts = measure(exp_t, {"ghost_transmittance": t})
        peaks.append(region_peak(gray, ghosts[3], half=GHOST_HALF))
    assert all(p > 0 for p in peaks), f"Ghost 3 not found off-axis at some transmittance: {peaks}"
    assert peaks[-1] > peaks[0], f"Higher transmittance should brighten off-axis ghosts: {peaks}"

    # Size up -> larger ghost band (calibrate at the smallest/brightest size)
    sizes = [0.6, 1.6]
    exp_s = calibrate_exposure(
        cielim_connection,
        lambda e: build(e, {"ghost_size": sizes[0]}),
        target=GHOST_TARGET,
        measure=ghost_window_peak,
    )
    signals = []
    for gs in sizes:
        gray = render_gray(cielim_connection, build(exp_s, {"ghost_size": gs}))
        core = bright_centroid(gray, frac=0.9)
        assert core is not None, "No flare core found in off-axis scene"
        signals.append(ghost_band_signal(gray, core))
    assert signals[-1] > signals[0], f"Larger ghostSize should raise the off-axis ghost band: {signals}"


if __name__ == "__main__":
    import sys

    # Tuning entrypoint. Watch the sun move across the FoV and dial in the STRAY_LIGHT_TUNING knobs.
    # Any "key=value" args override those knobs for this run (see the STRAY_LIGHT_TUNING comment).
    os.environ["show_plots"] = "True"
    os.environ["stray_light_tuning"] = " ".join(a for a in sys.argv[1:] if "=" in a)

    # --- Run the FULL parameter-validation suite — comment above, uncomment this ---
    pytest.main([__file__, "-v", "-s"])
