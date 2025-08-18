from driver import *
from launcher import *
from context import cielimMessage_pb2
import numpy as np
import pytest


def default_scene():

    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]
    body.model.shapeModel = "Sphere"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -2000000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.fieldOfView.append(item) for item in [30 * np.pi / 180, 25 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.resolution.append(item) for item in [4000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -50000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]

    return protobuf_message


@pytest.fixture
def scene_setup():
    return default_scene()


def test_PerlinNoise(cielim_connection, scene_setup):
    """
    Tests whether perlin noise is applied by comparing a base image to one with mesh deformation.
    """
    connector = cielim_connection

    scene = scene_setup

    connector.send_init_request()
    connector.send_frame(scene)
    base_image, _ = connector.request_image_for_camera_id(1, True)

    # Apply a lot of noise so that the circle becomes spikey

    scene.celestialBodies[0].model.perlinNoise.octaveCount = 3
    scene.celestialBodies[0].model.perlinNoise.baseFrequency = 0.1
    scene.celestialBodies[0].model.perlinNoise.baseAmplitude = 400.0
    scene.celestialBodies[0].model.perlinNoise.persistence = 0.5

    connector.send_init_request()
    connector.send_frame(scene)
    noise_image, _ = connector.request_image_for_camera_id(1, True)

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
