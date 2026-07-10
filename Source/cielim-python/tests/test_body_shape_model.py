import cv2
import numpy as np
import pytest

import cielim

MIN_ILLUMINATED_PX = 50


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    scene.set_sensor_params(exposure=1e-5)

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


def _render_and_measure_cob(connector: cielim.Connector, scene: cielim.Scene, test_name: str):
    """
    Renders the scene and returns its center of brightness, validating resolution and illumination.
    """
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    requested_width, requested_height = scene.get_scene().camera.sensorModel.resolution
    assert image.shape[:2] == (requested_height, requested_width), (
        f"{test_name}: rendered resolution {image.shape[1::-1]} does not match "
        f"requested ({requested_width}, {requested_height})."
    )

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    illuminated_px = cv2.countNonZero(image)
    assert (
        illuminated_px >= MIN_ILLUMINATED_PX
    ), f"{test_name}: only {illuminated_px} illuminated px (< {MIN_ILLUMINATED_PX}) — no body rendered."

    moments = cv2.moments(image)
    assert moments["m00"] != 0, f"{test_name}: no brightness detected."

    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


# NOTE: expected_cob values are placeholders (baseline sphere's center) pending calibration against
# a known-good reference render for each shape model — swap in real measured values when available.
@pytest.mark.parametrize(
    "test_name, shape_model, body_shift, expected_cob, cob_tolerance_px, min_shift_px, max_shift_px",
    [
        ("bennu", "bennu_normalized", (0, 0, 0), (500.0, 500.0), 60, 2, 50),
        ("itokawa", "itokawa_normalized", (0, 0, 0), (500.0, 500.0), 60, 2, 50),
        ("67p", "67p_normalized", (0, 0, 0), (500.0, 500.0), 60, 2, 50),
        ("vesta", "vesta_normalized", (0, 0, 0), (500.0, 500.0), 60, 2, 50),
        ("deimos", "deimos_normalized", (0, 0, 0), (500.0, 500.0), 60, 2, 50),
        ("bennu shifted", "bennu_normalized", (100, 50, 0), None, None, 20, 100),
    ],
)
def test_center_of_brightness_shift(
    cielim_connection: cielim.Connector,
    default_scene: cielim.Scene,
    test_name,
    shape_model,
    body_shift,
    expected_cob,
    cob_tolerance_px,
    min_shift_px,
    max_shift_px,
):
    """
    Checks the CoB shift, position, and shift direction for a shape model against the baseline sphere.
    """
    connector = cielim_connection
    scene = default_scene

    base_cob_x, base_cob_y = _render_and_measure_cob(connector, scene, f"{test_name} (baseline)")

    body = scene.get_celestial_body(1)
    initial_position = tuple(body.position)
    shifted_position = tuple(p + s for p, s in zip(initial_position, body_shift))
    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    distance = np.linalg.norm(spacecraft_position - np.array(initial_position))
    camera_fov_horizontal, camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView
    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    scene.set_celestial_body_params(1, mesh_shape=shape_model, position=shifted_position)

    cob_x, cob_y = _render_and_measure_cob(connector, scene, test_name)

    diff = np.linalg.norm(np.array((cob_x, cob_y)) - np.array((base_cob_x, base_cob_y)))
    np.testing.assert_(
        min_shift_px < diff < max_shift_px,
        msg=(
            f"{test_name}: CoB shift ({diff:.2f}px) outside expected range "
            f"({min_shift_px}-{max_shift_px}px) — shape model may not have rendered correctly."
        ),
    )

    if expected_cob is not None:
        np.testing.assert_allclose(
            [cob_x, cob_y],
            expected_cob,
            atol=cob_tolerance_px,
            err_msg=f"{test_name}: CoB {(cob_x, cob_y)} not within {cob_tolerance_px}px of expected {expected_cob}.",
        )

    if any(body_shift):
        # Both axes are negated for this scene's attitude=(0, 1, 0): a +x/+y body displacement maps
        # to -x/-y in image space
        expected_shift_x = -np.arctan(body_shift[0] / distance) * (image_width / camera_fov_horizontal)
        expected_shift_y = np.arctan(body_shift[1] / distance) * (image_height / camera_fov_vertical)

        actual_shift_x = cob_x - base_cob_x
        actual_shift_y = cob_y - base_cob_y

        if expected_shift_x:
            assert np.sign(actual_shift_x) == np.sign(expected_shift_x), (
                f"{test_name}: CoB X moved {actual_shift_x:.2f}px, expected same sign as "
                f"analytic shift {expected_shift_x:.2f}px."
            )
        if expected_shift_y:
            assert np.sign(actual_shift_y) == np.sign(expected_shift_y), (
                f"{test_name}: CoB Y moved {actual_shift_y:.2f}px, expected same sign as "
                f"analytic shift {expected_shift_y:.2f}px."
            )


def test_center_of_brightness_shift_invalid_shape_model(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene
):
    """
    An unknown shape model name silently falls back to the engine's default sphere mesh rather
    than failing, so it should render like the baseline sphere, centered in frame.
    """
    connector = cielim_connection
    scene = default_scene

    scene.set_celestial_body_params(1, mesh_shape="not_a_real_shape_model")

    cob_x, cob_y = _render_and_measure_cob(connector, scene, "invalid shape model", show_plots=show_plots)

    image_width, image_height = scene.get_scene().camera.sensorModel.resolution
    np.testing.assert_allclose(
        [cob_x, cob_y],
        [image_width / 2, image_height / 2],
        atol=60,
        err_msg=(
            f"invalid shape model: CoB {(cob_x, cob_y)} not centered — expected fallback-to-sphere render."
        ),
    )
