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
    Set up the scene with the spacecraft looking directly at a sphere with zoomed-in fov.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 50000), attitude=(0, 1, 0))

    scene.set_lens_params(fov=(5 * np.pi / 180, 5 * np.pi / 180))  # Zoom in to make image close to orthogonal

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


@pytest.mark.parametrize(
    "test_name, shift",
    [
        ("Move Right", [1000, 0, 0]),
        ("Move Left", [-1000, 0, 0]),
        ("Move Up", [0, -1000, 0]),
        ("Move Down", [0, 1000, 0]),
        ("Move Diagonal", [1000, 1000, 0]),
    ],
)
def test_camera_position(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool, test_name, shift
):
    """
    Tests the effect of moving the camera on the asteroid's apparent position in the image.
    """
    connector = cielim_connection

    scene = default_scene

    initial_x, initial_y, initial_z = scene.get_scene().spacecraft.position[:3]
    initial_spacecraft_position = np.array([initial_x, initial_y, initial_z])
    object_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(initial_spacecraft_position - object_position)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    _, baseline_thresh = cv2.threshold(baseline_image, 127, 255, cv2.THRESH_BINARY)
    baseline_contours, _ = cv2.findContours(baseline_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert baseline_contours, f"No contours found in baseline rendered image for test: {test_name}"

    largest_contour = max(baseline_contours, key=cv2.contourArea)
    (baseline_x, baseline_y), baseline_radius = cv2.minEnclosingCircle(largest_contour)

    if show_plots:
        show_render(baseline_image, f"{test_name} (baseline)")

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    shifted = [initial_x + shift[0], initial_y + shift[1], initial_z]

    scene.set_spacecraft_params(position=tuple(shifted))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    _, moved_thresh = cv2.threshold(moved_image, 127, 255, cv2.THRESH_BINARY)
    moved_contours, _ = cv2.findContours(moved_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert moved_contours, f"No contours found in moved rendered image for test: {test_name}"

    largest_contour = max(moved_contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)

    if show_plots:
        show_render(moved_image, test_name)

    # X shift is not inverted because +x points left (Unreal uses left handed coordinates)
    expected_pixel_shift_x = round(np.arctan(shift[0] / distance) * (image_width / camera_fov_horizontal))
    expected_pixel_shift_y = -round(np.arctan(shift[1] / distance) * (image_height / camera_fov_vertical))

    actual_pixel_shift_x = moved_x - baseline_x
    actual_pixel_shift_y = moved_y - baseline_y

    np.testing.assert_allclose(
        [actual_pixel_shift_x, actual_pixel_shift_y],
        [expected_pixel_shift_x, expected_pixel_shift_y],
        atol=5,
        err_msg=f"Pixel shift mismatch for test: {test_name}",
    )


@pytest.mark.parametrize(
    "test_name, z_shift",
    [
        ("Move Closer", -10000),
        ("Move Farther", 10000),
    ],
)
def test_camera_distance(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool, test_name, z_shift
):
    """
    Tests the effect of moving the camera along its boresight (Z) axis: the sphere's apparent
    center should stay put (a depth-only move causes no lateral pixel shift) while its apparent
    size changes (larger when closer, smaller when farther)
    """
    connector = cielim_connection

    scene = default_scene

    initial_x, initial_y, initial_z = scene.get_scene().spacecraft.position[:3]

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    _, baseline_thresh = cv2.threshold(baseline_image, 127, 255, cv2.THRESH_BINARY)
    baseline_contours, _ = cv2.findContours(baseline_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert baseline_contours, f"No contours found in baseline rendered image for test: {test_name}"

    largest_contour = max(baseline_contours, key=cv2.contourArea)
    (baseline_x, baseline_y), baseline_radius = cv2.minEnclosingCircle(largest_contour)

    if show_plots:
        show_render(baseline_image, f"{test_name} (baseline)")

    scene.set_spacecraft_params(position=(initial_x, initial_y, initial_z + z_shift))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    _, moved_thresh = cv2.threshold(moved_image, 127, 255, cv2.THRESH_BINARY)
    moved_contours, _ = cv2.findContours(moved_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert moved_contours, f"No contours found in moved rendered image for test: {test_name}"

    largest_contour = max(moved_contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)

    if show_plots:
        show_render(moved_image, test_name)

    print(f"Test: {test_name}")
    print(f"Baseline (center, radius): (({baseline_x}, {baseline_y}), {baseline_radius})")
    print(f"Moved (center, radius): (({moved_x}, {moved_y}), {moved_radius})")

    np.testing.assert_allclose(
        [moved_x, moved_y],
        [baseline_x, baseline_y],
        atol=5,
        err_msg=f"Center shifted for a depth-only (Z-axis) move: {test_name}",
    )

    if z_shift < 0:
        assert moved_radius > baseline_radius, f"Apparent size did not increase when moving closer: {test_name}"
    else:
        assert moved_radius < baseline_radius, f"Apparent size did not decrease when moving farther: {test_name}"


@pytest.mark.parametrize(
    "test_name, mrp_rotation",
    [
        ("Rotate X-axis", [0.001, 0, 0]),
        ("Rotate Y-axis", [0, -0.001, 0]),
        ("Rotate X-axis (large)", [0.003, 0, 0]),
        ("Roll (Z-axis)", [0, 0, 0.01]),
    ],
)
def test_camera_orientation(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool, test_name, mrp_rotation
):
    """
    Tests the effect of modifying the camera's orientation using MRPs on the asteroid's apparent position in the image.
    The expected pixel shifts are computed based on the new orientation.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    _, baseline_thresh = cv2.threshold(baseline_image, 127, 255, cv2.THRESH_BINARY)
    baseline_contours, _ = cv2.findContours(baseline_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert baseline_contours, f"No contours found in baseline rendered image for test: {test_name}"

    largest_contour = max(baseline_contours, key=cv2.contourArea)
    (baseline_x, baseline_y), baseline_radius = cv2.minEnclosingCircle(largest_contour)

    if show_plots:
        show_render(baseline_image, f"{test_name} (baseline)")

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    sigma = np.array(mrp_rotation)
    sigma_norm = np.linalg.norm(sigma)
    theta = 4 * np.arctan(sigma_norm)

    rotation_axis = sigma / sigma_norm if sigma_norm > 0 else np.array([0, 0, 0])

    scene.set_camera_params(attitude=tuple(mrp_rotation))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    _, moved_thresh = cv2.threshold(moved_image, 127, 255, cv2.THRESH_BINARY)
    moved_contours, _ = cv2.findContours(moved_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert moved_contours, f"No contours found in moved rendered image for test: {test_name}"

    largest_contour = max(moved_contours, key=cv2.contourArea)
    (moved_x, moved_y), moved_radius = cv2.minEnclosingCircle(largest_contour)

    if show_plots:
        show_render(moved_image, test_name)

    expected_pixel_shift_x = -rotation_axis[1] * theta * (image_width / camera_fov_horizontal)
    expected_pixel_shift_y = rotation_axis[0] * theta * (image_height / camera_fov_vertical)

    actual_pixel_shift_x = moved_x - baseline_x
    actual_pixel_shift_y = moved_y - baseline_y

    np.testing.assert_allclose(
        [actual_pixel_shift_x, actual_pixel_shift_y],
        [expected_pixel_shift_x, expected_pixel_shift_y],
        atol=5,
        err_msg=f"Pixel shift mismatch for test: {test_name}",
    )
    if abs(expected_pixel_shift_x) < abs(expected_pixel_shift_y):
        assert (
            abs(actual_pixel_shift_x) < 5
        ), f"Rotation about the other axis leaked into X (shift={actual_pixel_shift_x:.2f}px): {test_name}"
    elif abs(expected_pixel_shift_y) < abs(expected_pixel_shift_x):
        assert (
            abs(actual_pixel_shift_y) < 5
        ), f"Rotation about the other axis leaked into Y (shift={actual_pixel_shift_y:.2f}px): {test_name}"
