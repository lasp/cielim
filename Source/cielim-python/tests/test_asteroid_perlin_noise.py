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
    scene.set_celestial_body_params(index, mesh_shape="Sphere", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


def test_PerlinNoise(cielim_connection: cielim.Connector, default_scene: cielim.Scene):
    """
    Tests whether perlin noise is applied by comparing a base image to one with mesh deformation.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    base_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    # Apply a lot of noise so that the circle becomes spikey

    scene.get_scene().celestialBodies[1].model.perlinNoise.octaveCount = 3
    scene.get_scene().celestialBodies[1].model.perlinNoise.baseFrequency = 0.1
    scene.get_scene().celestialBodies[1].model.perlinNoise.baseAmplitude = 400.0
    scene.get_scene().celestialBodies[1].model.perlinNoise.persistence = 0.5

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    noise_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    # Compare image shapes

    base_grayscale = cv2.cvtColor(base_image, cv2.COLOR_BGR2GRAY)
    noise_grayscale = cv2.cvtColor(noise_image, cv2.COLOR_BGR2GRAY)

    _, base_thresh = cv2.threshold(base_grayscale, 127, 255, cv2.THRESH_BINARY)
    _, noise_thresh = cv2.threshold(noise_grayscale, 127, 255, cv2.THRESH_BINARY)

    base_contours, _ = cv2.findContours(base_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    noise_contours, _ = cv2.findContours(noise_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    base_contour_largest = max(base_contours, key=cv2.contourArea)
    noise_contour_largest = max(noise_contours, key=cv2.contourArea)

    score = cv2.matchShapes(base_contour_largest, noise_contour_largest, cv2.CONTOURS_MATCH_I1, 0.0)

    np.testing.assert_(score > 0.001, f"Shape contours are too similar between base and noisy (score={score})")
