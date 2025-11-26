from driver import *
from launcher import *
from context import cielimMessage_pb2
import numpy as np
import pytest


def default_scene():

    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "Plane"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]
    [body.model.inertialToBodyMrp.append(item) for item in [0, 0, 0]]
    body.model.shapeModel = "Plane"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, 0.5 * 1.496e11]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [30 * np.pi / 180, 25 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0.0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [3000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, 10000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 1, 0]]

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

    # Change scene to rotated plane to test GaussianPSF on jagged edges
    scene.celestialBodies[0].model.inertialToBodyMrp[:] = [0, 0, 0.2]

    connector.send_init_request()
    connector.send_frame(scene)
    sharp_image, _, _ = connector.request_image_for_camera_id(1, 1)

    scene.camera.lensModel.pointSpreadFunction = 50

    connector.send_init_request()
    connector.send_frame(scene)
    blurred_image, _, _ = connector.request_image_for_camera_id(1, 1)

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
    scene.renderParameters.cosmicRayStdDeviation = 100

    connector.send_init_request()
    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, 1)

    np.testing.assert_(np.any(np.all(image[:, :, :3] == 255, axis=-1)), "No cosmic rays found in otherwise blank image")


@pytest.mark.parametrize(
    "read_noise",
    [50, 500, 5000, 20000],
)
def test_ReadNoise(cielim_connection, scene_setup, read_noise):
    """
    Tests read noise is being generated with the expected standard deviation.
    """
    connector = cielim_connection

    scene = scene_setup

    del scene.celestialBodies[0]
    scene.camera.sensorModel.readNoise = read_noise

    connector.send_init_request()
    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, 1)

    image_normalized = image.astype(np.float32) / 255.0

    measured_std = np.std(image_normalized**2.2)

    np.testing.assert_array_less(0.0, measured_std, err_msg=f"Image was blank and no noise was applied")

    np.testing.assert_allclose(
        measured_std,
        read_noise / 50000,
        rtol=0.65,
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
    base_image, _, _ = connector.request_image_for_camera_id(1, 1)

    image_normalized = base_image.astype(np.float32) / 255.0
    img_linear = image_normalized**2.2
    img_scaled_linear = img_linear * signal_gain
    comparison_image = (np.clip(img_scaled_linear ** (1 / 2.2), 0.0, 1.0) * 255).astype(np.uint8)

    scene.camera.sensorModel.systemGain = signal_gain

    connector.send_init_request()
    connector.send_frame(scene)
    gain_image, _, _ = connector.request_image_for_camera_id(1, 1)

    np.testing.assert_allclose(
        gain_image, comparison_image, rtol=0.1, err_msg="Received image does not match comparison with specified gain"
    )
