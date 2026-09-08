import cv2
import matplotlib.pyplot as plt
import numpy as np
import pytest

import cielim


def show_render(image_gray: np.ndarray, title: str) -> None:
    plt.figure()
    plt.imshow(image_gray, cmap="gray", vmin=0, vmax=255)
    plt.title(title)
    plt.tight_layout()
    plt.show()


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere.
    """
    scene = cielim.Scene()

    # Rotate so +x is right, +y is up, and +z is out of the page
    scene.set_spacecraft_params(position=(0, 0, 4000), attitude=(1, 0, 0))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Regolith", mesh_radius=1000)

    return scene


def photocenter_offset_angle(mean_radius: float, distance: float, phase_angle_rad: float) -> float:
    """
    Calculates how far the illuminated region's brightness-center shifts away from a Lambertian sphere's
    true center as phase angle increases, converted to an angle
    """
    return np.arctan((4 * mean_radius) / (3 * np.pi * distance) * (1 - np.cos(phase_angle_rad)))


def test_photocenter_offset_formula():
    """
     This test checks that the offset formula behaves correctly at its edges (zero when fully lit, grows
    with phase angle, and matches a hand-computed value at 180°).
    """
    mean_radius = 1000.0
    distance = 50000.0

    # Full illumination (phase=0): no illuminated-region asymmetry, so no offset.
    assert photocenter_offset_angle(mean_radius, distance, 0.0) == 0.0

    # Monotonically increasing over the visible phase range.
    phase_angles_rad = np.radians(np.linspace(0, 180, 19))
    thetas = [photocenter_offset_angle(mean_radius, distance, p) for p in phase_angles_rad]
    assert np.all(np.diff(thetas) > 0), "Photocenter offset is not monotonically increasing with phase angle"

    # At 180 deg (new moon geometry), the offset is at its formula-implied maximum.
    expected_max_theta = np.arctan(8 * mean_radius / (3 * np.pi * distance))
    np.testing.assert_allclose(thetas[-1], expected_max_theta, rtol=1e-9)


def test_phase_angle_new_moon(cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool):
    """
    At 180 deg phase (sun directly behind the target from the camera's viewpoint), the camera
    should see only the unlit far hemisphere — the image should be near-black.
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_celestial_body_params(0, position=(0, 0, -1.496e11))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    mean_brightness = np.mean(image)

    if show_plots:
        show_render(image, f"180 deg phase (mean={mean_brightness:.2f})")

    assert mean_brightness < 5, f"Image was not near-black at 180 deg phase (mean pixel value={mean_brightness:.2f})"


def test_phase_angle_brightness_scaling(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool
):
    """
    Total reflected brightness (sum of pixel values, i.e. image moment m00) should decrease
    monotonically as phase angle increases.
    """
    connector = cielim_connection

    scene = default_scene

    phase_angles_deg = [0, 45, 90, 135]
    sun_positions = [
        (0, 0, 1.496e11),
        (1.496e11, 0, 1.496e11),
        (1.496e11, 0, 0),
        (1.496e11, 0, -1.496e11),
    ]

    brightnesses = []
    for phase_angle_deg, sun_position in zip(phase_angles_deg, sun_positions):
        scene.set_celestial_body_params(0, position=sun_position)

        connector.send_init_request()
        connector.send_frame(scene.get_scene())
        image, _, _ = connector.request_image_for_camera_id(1, True, False)

        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        m00 = cv2.moments(image)["m00"]
        assert m00 > 0, f"Image was blank at phase angle {phase_angle_deg} deg."
        brightnesses.append(m00)

        if show_plots:
            show_render(image, f"phase={phase_angle_deg} deg (m00={m00:.0f})")

    for i in range(1, len(brightnesses)):
        max_prior = max(brightnesses[:i])
        assert brightnesses[i] < max_prior, (
            f"Brightness at {phase_angles_deg[i]} deg ({brightnesses[i]:.1f}) exceeds the peak of "
            f"earlier phase angles ({max_prior:.1f})"
        )


@pytest.mark.parametrize(
    "test_name, sun_position, phase_angle",
    [
        ("Full Illumination (0°)", (0, 0, 1.496e11), 0),
        ("(45° Horizontal)", (1.496e11, 0, 1.496e11), 45),
        ("Half Moon (90° Horizontal)", (1.496e11, 0, 0), 90),
        ("(135° Horizontal)", (1.496e11, 0, -1.496e11), 135),
        ("(45° Vertical)", (0, -1.496e11, 1.496e11), 45),
        ("Half Moon (90° Vertical)", (0, -1.496e11, 0), 90),
        ("(135° Vertical)", (0, -1.496e11, -1.496e11), 135),
    ],
)
def test_phase_angle_scene(
    cielim_connection: cielim.Connector,
    default_scene: cielim.Scene,
    show_plots: bool,
    test_name,
    sun_position,
    phase_angle,
):
    """
    Tests the phase angle change by testing Center of Brightness (CoB) vs expected shift (by comparing expected and actual pixel shifts).
    """
    connector = cielim_connection

    scene = default_scene

    scene.set_celestial_body_params(0, position=sun_position)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius
    asteroid_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)
    phase_angle_rad = np.radians(phase_angle)

    theta = photocenter_offset_angle(mean_radius, distance, phase_angle_rad)

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_height, image_width, _ = image.shape

    sun_vector = np.array(sun_position) - asteroid_position
    sun_direction = sun_vector / np.linalg.norm(sun_vector)

    expected_cob_x = image_width / 2
    expected_cob_y = image_height / 2

    if abs(sun_direction[0]) > 1e-6:
        expected_cob_x += np.sign(sun_direction[0]) * theta * (image_width / camera_fov_horizontal)
        expected_cob_x = round(expected_cob_x)

    if abs(sun_direction[1]) > 1e-6:
        expected_cob_y += np.sign(sun_direction[1]) * theta * (image_height / camera_fov_vertical)
        expected_cob_y = round(expected_cob_y)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)

    assert moments["m00"] != 0, f"Image was blank — no illuminated body detected for test: {test_name}"
    actual_cob_x = round(moments["m10"] / moments["m00"])
    actual_cob_y = image_height - round(moments["m01"] / moments["m00"])

    if show_plots:
        show_render(
            image,
            f"{test_name} (actual CoB=({actual_cob_x}, {actual_cob_y}), "
            f"expected=({expected_cob_x}, {expected_cob_y}))",
        )

    np.testing.assert_allclose(
        [actual_cob_x, actual_cob_y],
        [expected_cob_x, expected_cob_y],
        rtol=0.1,
        err_msg=f"CoB mismatch for test: {test_name}",
    )
