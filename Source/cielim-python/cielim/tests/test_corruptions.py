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
    [body.attitude.append(item) for item in [0, 0, 0]]
    body.model.shapeModel = "sphere_normalized"
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


def test_GaussianPSF(cielim_connection, scene_setup):
    """
    Tests that Gaussian PSF is properly blurring the image using variance of laplacian.
    """
    connector = cielim_connection

    scene = scene_setup

    connector.send_init_request()
    connector.send_frame(scene)
    sharp_image, _ = connector.request_image_for_camera_id(1, 1)

    scene.camera.pointSpreadFunction = 50

    connector.send_init_request()
    connector.send_frame(scene)
    blurred_image, _ = connector.request_image_for_camera_id(1, 1)

    sharp_laplace = cv2.Laplacian(sharp_image, cv2.CV_64F)
    sharp_variance = sharp_laplace.var()

    blur_laplace = cv2.Laplacian(blurred_image, cv2.CV_64F)
    blur_variance = blur_laplace.var()

    print(f"Sharp Variance: {sharp_variance}")
    print(f"Blurred Variance: {blur_variance}")

    np.testing.assert_array_less(
        blur_variance,
        sharp_variance,
        err_msg=f"Image was not blurred: expected blurred variance ({blur_variance}) to be less than sharp variance ({sharp_variance})",
    )


def test_CosmicRays(cielim_connection, scene_setup):
    """
    Tests that comsic rays are being generated in the image.
    """
    connector = cielim_connection

    scene = scene_setup

    del scene.celestialBodies[0]
    scene.camera.renderParameters.cosmicRayStdDeviation = 100

    connector.send_init_request()
    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    np.testing.assert_(np.any(np.all(image[:, :, :3] == 255, axis=-1)), "No cosmic rays found in otherwise blank image")


@pytest.mark.parametrize(
    "read_noise",
    [1, 3, 5, 10, 20],
)
def test_ReadNoise(cielim_connection, scene_setup, read_noise):
    """
    Tests read noise is being generated with the expected standard deviation.
    """
    connector = cielim_connection

    scene = scene_setup

    del scene.celestialBodies[0]
    scene.camera.readNoise = read_noise

    connector.send_init_request()
    connector.send_frame(scene)
    image, _ = connector.request_image_for_camera_id(1, 1)

    measured_std = np.std(image)

    np.testing.assert_array_less(0.0, measured_std, err_msg=f"Image was blank and no noise was applied")

    np.testing.assert_allclose(
        measured_std,
        read_noise,
        rtol=0.5,
        err_msg=f"Measured standard deviation ({measured_std}) was too far from expected of ({read_noise})",
    )


@pytest.mark.parametrize(
    "signal_gain",
    [0.8, 0.75, 0.5, 0.25],
)
def test_SignalGain(cielim_connection, scene_setup, signal_gain):
    """
    Tests whether gain is being properly applied to image.
    """
    connector = cielim_connection

    scene = scene_setup

    connector.send_init_request()
    connector.send_frame(scene)
    base_image, _ = connector.request_image_for_camera_id(1, 1)

    comparison_image = base_image * signal_gain

    scene.camera.systemGain = signal_gain

    connector.send_init_request()
    connector.send_frame(scene)
    gain_image, _ = connector.request_image_for_camera_id(1, 1)

    np.testing.assert_allclose(
        gain_image, comparison_image, rtol=1e-2, err_msg="Received image does not match comparison with specified gain"
    )
