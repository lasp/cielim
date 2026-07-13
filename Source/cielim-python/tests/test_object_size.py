import cv2
import numpy as np
import pytest

import cielim


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
        ("No movement", [0, 0, 0]),
        ("Move Closer", [0, 0, 10000]),
        ("Move Away", [0, 0, -10000]),
        ("Move Away & Down", [0, -500, -10000]),
        ("Move Closer & Right", [500, 0, 10000]),
        ("Move Closer, Right & Up", [500, 500, 10000]),
        ("Move Away, Left & Down", [-500, -500, -10000]),
    ],
)
def test_asteroid_size(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name, shift):
    """
    Tests the asteroid size in pixels when its distance (Z) and slight position (X, Y) change.
    Parameters: Changing asteroid Z (closer/away) and slight X/Y shift, verifying pixel size.
    """
    connector = cielim_connection

    scene = default_scene

    initial_position = scene.get_scene().celestialBodies[1].position[:3]

    camera_fov_horizontal = scene.get_scene().camera.lensModel.fieldOfView[0]
    camera_fov_vertical = scene.get_scene().camera.lensModel.fieldOfView[1]
    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(baseline_image.shape) == 3:
        baseline_image = cv2.cvtColor(baseline_image, cv2.COLOR_BGR2GRAY)

    _, baseline_thresh = cv2.threshold(baseline_image, 127, 255, cv2.THRESH_BINARY)
    baseline_contours, _ = cv2.findContours(baseline_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert baseline_contours, f"No contours found in baseline rendered image for test: {test_name}"

    _, baseline_radius = cv2.minEnclosingCircle(max(baseline_contours, key=cv2.contourArea))
    baseline_size_pixels = 2 * baseline_radius

    baseline_distance = np.linalg.norm(spacecraft_position - np.array(initial_position))
    baseline_expected_angular_size_rad = 2 * np.arcsin(mean_radius / baseline_distance)
    baseline_expected_size_pixels = (baseline_expected_angular_size_rad / camera_fov_horizontal) * image_width

    np.testing.assert_allclose(
        baseline_size_pixels,
        baseline_expected_size_pixels,
        rtol=0.01,
        atol=1,
        err_msg=f"Baseline asteroid size in pixels does not match expected value for test: {test_name}",
    )

    shifted = [initial_position[i] + shift[i] for i in range(3)]

    scene.set_celestial_body_params(1, position=tuple(shifted))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    moved_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(moved_image.shape) == 3:
        moved_image = cv2.cvtColor(moved_image, cv2.COLOR_BGR2GRAY)

    _, moved_thresh = cv2.threshold(moved_image, 127, 255, cv2.THRESH_BINARY)
    moved_contours, _ = cv2.findContours(moved_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert moved_contours, f"No contours found in moved rendered image for test: {test_name}"

    _, moved_radius = cv2.minEnclosingCircle(max(moved_contours, key=cv2.contourArea))
    asteroid_size_pixels = 2 * moved_radius

    asteroid_position = np.array(scene.get_scene().celestialBodies[1].position)
    distance = np.linalg.norm(spacecraft_position - asteroid_position)

    expected_angular_size_rad = 2 * np.arcsin(mean_radius / distance)

    # Checked against both width/horizontal-FOV and height/vertical-FOV — a sphere rendered with
    # the wrong aspect ratio would still pass a width-only check as long as its horizontal extent
    # happened to be right.
    expected_size_from_width = (expected_angular_size_rad / camera_fov_horizontal) * image_width
    expected_size_from_height = (expected_angular_size_rad / camera_fov_vertical) * image_height

    np.testing.assert_allclose(
        asteroid_size_pixels,
        expected_size_from_width,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid size (vs. width/horizontal FOV) does not match expected value for test: {test_name}",
    )

    np.testing.assert_allclose(
        asteroid_size_pixels,
        expected_size_from_height,
        rtol=0.01,
        atol=1,
        err_msg=f"Asteroid size (vs. height/vertical FOV) does not match expected value for test: {test_name}",
    )


def _measure_asteroid_diameter_pixels(connector: cielim.Connector, scene: cielim.Scene, test_name: str) -> float:
    """Render the current scene and return the asteroid's apparent diameter in pixels."""
    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert contours, f"No contours found in rendered image for test: {test_name}"

    _, radius = cv2.minEnclosingCircle(max(contours, key=cv2.contourArea))
    return 2 * radius


def test_asteroid_size_distance_scaling(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Verifies apparent size scales as 1/distance (perspective projection) by rendering at four
    distances, each double the last, and checking that apparent size halves each time — a direct
    scaling-law check, independent of (and complementary to) test_asteroid_size's absolute
    angular-size formula.
    """
    connector = cielim_connection

    scene = default_scene

    # default_scene's FOV is only 5 deg (half-FOV 2.5 deg); the sphere's angular radius must stay
    # under that or minEnclosingCircle measures a clipped silhouette, not the true unclipped size.
    # arcsin(mean_radius/distance) < half-FOV requires distance > ~22926 for mean_radius=1000 —
    # 10000/20000 (used in an earlier version of this test) are both clipped; 40000 is the first
    # safely-unclipped point (angular radius ~1.43 deg, vs. 2.5 deg half-FOV).
    distances = [40000, 80000, 160000, 320000]
    sizes_pixels = []

    for distance in distances:
        scene.set_celestial_body_params(1, position=(0, 0, 0))
        scene.set_spacecraft_params(position=(0, 0, distance))
        sizes_pixels.append(_measure_asteroid_diameter_pixels(connector, scene, f"distance={distance}"))

    for i in range(len(distances) - 1):
        np.testing.assert_allclose(
            sizes_pixels[i],
            2 * sizes_pixels[i + 1],
            rtol=0.02,
            err_msg=(
                f"Apparent size did not halve going from distance={distances[i]} "
                f"(size={sizes_pixels[i]:.2f}px) to distance={distances[i + 1]} (size={sizes_pixels[i + 1]:.2f}px)"
            ),
        )


def test_asteroid_size_overflow(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Edge case: the asteroid moved close enough to fill (and exceed) the frame. Verifies the
    renderer clips gracefully — a bounding box within image bounds and touching an edge — rather
    than crashing or measuring past the frame; the angular-size formula used elsewhere in this
    file doesn't apply once the object is clipped, so this needs its own assertion.
    """
    connector = cielim_connection

    scene = default_scene

    mean_radius = scene.get_scene().celestialBodies[1].model.meanRadius

    # Close enough that the sphere's angular radius alone exceeds the 2.5 deg half-FOV.
    scene.set_celestial_body_params(1, position=(0, 0, 0))
    scene.set_spacecraft_params(position=(0, 0, mean_radius * 5))

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    assert contours, "No contours found in rendered image for the frame-filling overflow case."

    x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))

    image_width, image_height = scene.get_scene().camera.sensorModel.resolution

    assert w <= image_width and h <= image_height, "Bounding box exceeds image dimensions; overflow was not clipped."

    assert (
        x <= 0 or y <= 0 or x + w >= image_width or y + h >= image_height
    ), "Asteroid did not touch any frame edge; this scenario is not actually testing overflow."
