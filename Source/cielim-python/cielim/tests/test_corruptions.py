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


@pytest.mark.parametrize(
    "k1, k2, k3, p1, p2",
    [
        (0.5, 0.0, 0.0, 0.0, 0.0),
        (-0.5, 0.0, 0.0, 0.0, 0.0),
        (0.3, 0.1, 0.0, 0.0, 0.0),
        (0.3, 0.2, 0.1, 0.0, 0.0),
        (0.0, -0.3, 0.1, 0.0, 0.0),
        (0.0, 0.3, -0.1, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.3, 0.0),
        (0.0, 0.0, 0.0, 0.0, 0.3),
    ],
)
def test_LensDistortion(cielim_connection, scene_setup, k1, k2, k3, p1, p2):
    """
    Tests that lens distortion is distorting the image as expected.
    """
    connector = cielim_connection

    scene = scene_setup

    # Make spacecraft closer to plane
    scene.spacecraft.position[:] = [0, 0, 3000]

    connector.send_init_request()
    connector.send_frame(scene)
    base_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    # Apply distortions to base image

    h, w = base_image.shape[:2]
    aspect_ratio = w / h

    # Create normalized UV coordinate grids [0, 1]
    u = np.linspace(0, 1, w, dtype=np.float32)
    v = np.linspace(0, 1, h, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # Shift to center [-0.5, 0.5] and apply aspect ratio to X
    cx = (uu - 0.5) * aspect_ratio
    cy = vv - 0.5

    # Radial distances
    r2 = cx * cx + cy * cy
    r4 = r2 * r2
    r6 = r2 * r4

    # Radial distortion factor
    radial = 1.0 + k1 * r2 + k2 * r4 + k3 * r6

    # Tangential distortion offset
    tx = 2.0 * p1 * cx * cy + p2 * (r2 + 2.0 * cx * cx)
    ty = p1 * (r2 + 2.0 * cy * cy) + 2.0 * p2 * cx * cy

    # Edge scale factors (to normalize distortion at image borders)
    x_edge2 = (0.5 * aspect_ratio) ** 2
    x_scale = 1.0 + k1 * x_edge2 + k2 * x_edge2**2 + k3 * x_edge2**3

    y_edge2 = 0.5**2
    y_scale = 1.0 + k1 * y_edge2 + k2 * y_edge2**2 + k3 * y_edge2**3

    # Apply edge scaling before distortion
    cx /= x_scale
    cy /= y_scale

    # Apply radial + tangential distortion
    dx = cx * radial + tx
    dy = cy * radial + ty

    # Undo aspect ratio and shift back to [0, 1] UV space
    dx /= aspect_ratio
    distorted_u = dx + 0.5
    distorted_v = dy + 0.5

    # Convert UVs to pixel coordinates for remap
    map_x = (distorted_u * w).astype(np.float32)
    map_y = (distorted_v * h).astype(np.float32)

    # Remap with black border fill
    distorted_base = cv2.remap(
        base_image, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)
    )

    scene.camera.lensModel.distortionK1 = k1
    scene.camera.lensModel.distortionK2 = k2
    scene.camera.lensModel.distortionK3 = k3
    scene.camera.lensModel.distortionP1 = p1
    scene.camera.lensModel.distortionP2 = p2

    connector.send_init_request()
    connector.send_frame(scene)
    distorted_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    diff = np.abs(distorted_image.astype(np.int32) - distorted_base.astype(np.int32))
    mismatch_fraction = np.mean(diff > 1)

    # Some pixels will be off because cv can smooth edges (0.2% allowance)
    assert mismatch_fraction < 0.002, (
        f"Too many mismatched pixels: {mismatch_fraction:.2%} " f"(max diff: {diff.max()})"
    )


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


@pytest.mark.parametrize(
    "dark_current, sigma",
    [
        (1000, 0),
        (10000, 0),
        (1, 100),
        (1, 1000),
        (10, 100),
        (10, 1000),
        (100, 100),
        (100, 10000),
    ],
)
def test_DarkCurrent(cielim_connection, scene_setup, dark_current, sigma):
    """
    Tests whether dark current is being added to the image.
    """
    connector = cielim_connection

    scene = scene_setup

    del scene.celestialBodies[0]
    scene.camera.sensorModel.exposureTime = 1
    scene.camera.sensorModel.darkCurrent = dark_current
    scene.camera.sensorModel.darkCurrentStdDeviation = sigma

    connector.send_init_request()
    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    np.testing.assert_(image[..., :3].any(), "No noise was applied")


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
    "stuck_rate, dead_rate",
    [
        (0.000005, 0),  # a few pixels
        (0, 0.000005),
        (0.000005, 0.000005),
        (0.000025, 0),  # about a dozen pixels
        (0, 0.000025),
        (0.000025, 0.000025),
    ],
)
def test_PixelDefect(cielim_connection, scene_setup, stuck_rate, dead_rate):
    """
    Tests stuck and dead pixels can be added to image.
    """
    connector = cielim_connection

    scene = scene_setup

    scene.spacecraft.position[:] = [0, 0, 1000]  # Make spacecraft closer to plane to fill screen
    scene.camera.sensorModel.exposureTime = 4e-5  # Reduce exposure time so image is gray
    scene.camera.sensorModel.stuckPixelRate = stuck_rate
    scene.camera.sensorModel.deadPixelRate = dead_rate

    connector.send_init_request()
    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, 1)

    is_white = (image == [255, 255, 255]).all(axis=-1)
    is_black = (image == [0, 0, 0]).all(axis=-1)

    total_pixels = image.shape[0] * image.shape[1]

    white_pixels_rate = np.sum(is_white) / total_pixels
    black_pixels_rate = np.sum(is_black) / total_pixels

    np.testing.assert_allclose(
        white_pixels_rate,
        stuck_rate,
        rtol=0.5,
        err_msg=f"Got white pixel rate of {white_pixels_rate * 100:.5f}%, expected ~{stuck_rate * 100}%",
    )

    np.testing.assert_allclose(
        black_pixels_rate,
        dead_rate,
        rtol=0.5,
        err_msg=f"Got black pixel rate of {black_pixels_rate * 100:.5f}%, expected ~{dead_rate * 100}%",
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
