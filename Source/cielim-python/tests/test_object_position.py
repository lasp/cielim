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


def moments_centroid(image_gray: np.ndarray, test_name: str) -> tuple[float, float]:
    """
    Sub-pixel center via image moments.
    """
    moments = cv2.moments(image_gray)
    assert moments["m00"] > 0, f"No illuminated body detected in rendered image for test: {test_name}"
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere.
    """
    scene = cielim.Scene()

    # Rotate so +x is right, +y is up, and +z is out of the page
    scene.set_spacecraft_params(position=(0, 0, 50000), attitude=(1, 0, 0))

    scene.set_lens_params(fov=(5 * np.pi / 180, 5 * np.pi / 180))  # Zoom in to make image close to orthogonal

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Regolith", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "test_name, shift",
    [
        ("Move Right", [1000, 0, 0]),
        ("Move Left", [-1000, 0, 0]),
        ("Move Up", [0, 1000, 0]),
        ("Move Down", [0, -1000, 0]),
        ("Move Diagonal", [1000, 1000, 0]),
    ],
)
def test_object_position(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool, test_name, shift
):
    """
    Tests the asteroid movement in image space when shifted in 3D (X, Y).
    Parameters: Changing asteroid position in meters and verifying pixel shift.
    """
    connector = cielim_connection

    scene = default_scene

    initial_x, initial_y, initial_z = scene.get_scene().celestialBodies[1].position[:3]

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_x, baseline_y = moments_centroid(baseline_image, test_name)

    if show_plots:
        show_render(baseline_image, f"{test_name} (baseline)")

    np.testing.assert_allclose(
        [baseline_x, baseline_y],
        [image_width / 2, image_height / 2],
        atol=5,
        err_msg=f"Baseline (pre-shift) object position was not centered for test: {test_name}",
    )

    shifted = [initial_x + shift[0], initial_y + shift[1], initial_z + shift[2]]

    scene.set_celestial_body_params(1, position=tuple(shifted))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    moved_x, moved_y = moments_centroid(moved_image, test_name)

    if show_plots:
        show_render(moved_image, test_name)

    object_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - object_position)

    expected_pixel_shift_x = np.arctan(shift[0] / distance) * (image_width / camera_fov_horizontal)
    # We multiply by -1 here to account for +y being down for image data
    expected_pixel_shift_y = -np.arctan(shift[1] / distance) * (image_height / camera_fov_vertical)

    actual_pixel_shift_x = moved_x - baseline_x
    actual_pixel_shift_y = moved_y - baseline_y

    np.testing.assert_allclose(
        [actual_pixel_shift_x, actual_pixel_shift_y],
        [expected_pixel_shift_x, expected_pixel_shift_y],
        atol=2,
        err_msg=f"Pixel shift mismatch for test: {test_name}",
    )


@pytest.mark.parametrize(
    "test_name, axis_shift",
    [
        ("X-axis", [1000, 0, 0]),
        ("Y-axis", [0, 1000, 0]),
    ],
)
def test_object_position_symmetry(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool, test_name, axis_shift
):
    """
    Opposite shifts along the same axis should produce opposite, canceling pixel shifts a
    self-consistency check that catches sign errors.
    """
    connector = cielim_connection

    scene = default_scene

    initial_x, initial_y, initial_z = scene.get_scene().celestialBodies[1].position[:3]

    def render_and_get_center(position, label):
        scene.set_celestial_body_params(1, position=position)
        connector.send_init_request()
        connector.send_frame(scene.get_scene())
        image, _, _ = connector.request_image_for_camera_id(1, True, False)
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if show_plots:
            show_render(image, f"{test_name} ({label})")
        return moments_centroid(image, test_name)

    baseline_x, baseline_y = render_and_get_center((initial_x, initial_y, initial_z), "baseline")
    positive_x, positive_y = render_and_get_center(
        (initial_x + axis_shift[0], initial_y + axis_shift[1], initial_z), "positive"
    )
    negative_x, negative_y = render_and_get_center(
        (initial_x - axis_shift[0], initial_y - axis_shift[1], initial_z), "negative"
    )

    positive_shift = np.array([positive_x - baseline_x, positive_y - baseline_y])
    negative_shift = np.array([negative_x - baseline_x, negative_y - baseline_y])

    np.testing.assert_allclose(
        positive_shift + negative_shift,
        [0, 0],
        atol=2,
        err_msg=(
            f"Opposite shifts along {test_name} did not cancel "
            f"(positive shift={positive_shift}, negative shift={negative_shift})"
        ),
    )


@pytest.mark.parametrize(
    "test_name, z_shift",
    [
        ("Move Closer", 10000),
        ("Move Farther", -10000),
    ],
)
def test_object_distance(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool, test_name, z_shift
):
    """
    Tests the effect of moving the asteroid along the boresight (Z) axis: its apparent center
    should stay put (a depth-only move causes no lateral pixel shift) while its apparent size
    changes (larger when closer, smaller when farther).
    """
    connector = cielim_connection

    scene = default_scene

    initial_x, initial_y, initial_z = scene.get_scene().celestialBodies[1].position[:3]

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    baseline_x, baseline_y = moments_centroid(baseline_image, test_name)

    if show_plots:
        show_render(baseline_image, f"{test_name} (baseline)")

    _, baseline_thresh = cv2.threshold(baseline_image, 127, 255, cv2.THRESH_BINARY)
    baseline_contours, _ = cv2.findContours(baseline_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert baseline_contours, f"No contours found in baseline rendered image for test: {test_name}"

    _, baseline_radius = cv2.minEnclosingCircle(max(baseline_contours, key=cv2.contourArea))

    # Z increases toward the spacecraft (which sits at z=50000, with the asteroid starting near
    # the origin), so a positive z_shift moves the asteroid closer.
    scene.set_celestial_body_params(1, position=(initial_x, initial_y, initial_z + z_shift))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    moved_x, moved_y = moments_centroid(moved_image, test_name)

    if show_plots:
        show_render(moved_image, test_name)

    _, moved_thresh = cv2.threshold(moved_image, 127, 255, cv2.THRESH_BINARY)
    moved_contours, _ = cv2.findContours(moved_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert moved_contours, f"No contours found in moved rendered image for test: {test_name}"

    _, moved_radius = cv2.minEnclosingCircle(max(moved_contours, key=cv2.contourArea))

    np.testing.assert_allclose(
        [moved_x, moved_y],
        [baseline_x, baseline_y],
        atol=5,
        err_msg=f"Center shifted for a depth-only (Z-axis) move: {test_name}",
    )

    if z_shift > 0:
        assert moved_radius > baseline_radius, f"Apparent size did not increase when moving closer: {test_name}"
    else:
        assert moved_radius < baseline_radius, f"Apparent size did not decrease when moving farther: {test_name}"
