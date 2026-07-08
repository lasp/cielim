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

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


def test_request_image_and_center_of_brightness(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    [image, center_of_brightness, _] = connector.request_image_for_camera_id(1)

    height, width, _ = image.shape
    np.testing.assert_allclose([1000, 1000], [width, height], rtol=0, atol=0, err_msg="Returned image not correct")

    true_center_of_brightness = [500, 500]
    np.testing.assert_allclose(
        center_of_brightness,
        true_center_of_brightness,
        atol=1,
        err_msg="Center of brightness not close enough to expected",
    )


def test_request_only_center_of_brightness(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    connector = cielim_connection

    scene = default_scene

    connector.send_frame(scene.get_scene())
    [image, center_of_brightness, _] = connector.request_image_for_camera_id(1, False, True)

    assert image is None

    true_center_of_brightness = [500, 500]
    np.testing.assert_allclose(
        center_of_brightness,
        true_center_of_brightness,
        rtol=0,
        atol=1,
        err_msg="Center of brightness not close enough to expected",
    )


@pytest.mark.parametrize(
    "center_x, center_y, width, height",
    [
        (2000, 1500, 4000, 3000),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 2000, 1500),
        (2000, 1500, 1000, 750),
        (2000, 1500, 500, 375),
        (2000, 1500, 250, 250),
    ],
)
def test_coverage(cielim_connection: cielim.Connector, default_scene: cielim.Scene, center_x, center_y, width, height):
    connector = cielim_connection

    scene = default_scene

    scene.get_scene().camera.areaOfInterest.centerX = center_x
    scene.get_scene().camera.areaOfInterest.centerY = center_y
    scene.get_scene().camera.areaOfInterest.width = width
    scene.get_scene().camera.areaOfInterest.height = height

    threshold = 0.01

    scene.get_scene().camera.areaOfInterest.threshold = threshold

    connector.send_frame(scene.get_scene())
    [image, _, coverage] = connector.request_image_for_camera_id(1)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Compute bounds
    x1 = max(center_x - width // 2, 0)
    y1 = max(center_y - height // 2, 0)
    x2 = min(center_x + width // 2, 4000)
    y2 = min(center_y + height // 2, 3000)

    bounds = gray[y1 : y2 + 1, x1 : x2 + 1]

    mask_total = gray > threshold * 255
    mask_covered = bounds > threshold * 255

    # Ratio of bright pixels
    pct = np.sum(mask_covered) / np.sum(mask_total)

    np.testing.assert_allclose(
        coverage,
        pct,
        rtol=0.02,
        err_msg="Coverage not close enough to expected",
    )
