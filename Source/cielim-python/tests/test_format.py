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


@pytest.mark.parametrize(
    "test_name",
    [
        ("RAW 8-bit"),
        ("RAW 12-bit"),
        ("RAW 12-bit packed"),
        ("RAW 16-bit"),
    ],
)
def test_Format(cielim_connection: cielim.Connector, default_scene: cielim.Scene, test_name):
    """
    Tests raw image data is properly formatted.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    baseline_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    height, width, _ = baseline_image.shape

    # Refer to CameraModel.cpp for raw format generation algorithms

    if test_name == "RAW 8-bit":
        scene.set_camera_params(image_format=cielim.cielimProto.ImageFormat.RAW_8)

        connector.send_frame(scene.get_scene())
        data, _, _ = connector.request_image_for_camera_id(1, True, False, format_raw=True)

        test_image = np.frombuffer(data, dtype=np.uint8).reshape((width, height, 3))

        max_value = 255

    elif test_name == "RAW 12-bit":
        scene.set_camera_params(image_format=cielim.cielimProto.ImageFormat.RAW_12)

        connector.send_frame(scene.get_scene())
        data, _, _ = connector.request_image_for_camera_id(1, True, False, format_raw=True)

        test_image = (np.frombuffer(data, dtype=np.uint16) >> 4 & 0x0FFF).reshape((width, height, 3))

        max_value = 4095

    elif test_name == "RAW 12-bit packed":
        scene.set_camera_params(image_format=cielim.cielimProto.ImageFormat.RAW_12_PACKED)

        connector.send_frame(scene.get_scene())
        data, _, _ = connector.request_image_for_camera_id(1, True, False, format_raw=True)

        num_channels = width * height * 3
        num_pairs = (num_channels + 1) // 2
        raw = np.frombuffer(data, dtype=np.uint8).reshape((num_pairs, 3))
        b0 = raw[:, 0].astype(np.uint16)
        b1 = raw[:, 1].astype(np.uint16)
        b2 = raw[:, 2].astype(np.uint16)
        sample_a = (b0 | ((b1 & 0x0F) << 8)) & 0xFFF
        sample_b = ((b1 >> 4) | (b2 << 4)) & 0xFFF
        samples = np.empty(num_pairs * 2, dtype=np.uint16)
        samples[0::2] = sample_a
        samples[1::2] = sample_b
        test_image = (samples[:num_channels]).astype(np.uint16).reshape((width, height, 3))

        max_value = 4095

    else:
        scene.set_camera_params(image_format=cielim.cielimProto.ImageFormat.RAW_16)

        connector.send_frame(scene.get_scene())
        data, _, _ = connector.request_image_for_camera_id(1, True, False, format_raw=True)

        test_image = np.frombuffer(data, dtype=np.uint16).reshape((width, height, 3))

        max_value = 65535

    assert test_image is not None, "No image data returned"
    assert (
        test_image.shape == baseline_image.shape
    ), f"Image shape mismatch: {test_image.shape} vs {baseline_image.shape}"

    assert test_image.min() != test_image.max(), "Image is uniform, likely a zeroed buffer"
    assert (
        test_image.min() >= 0 and test_image.max() <= max_value
    ), f"Values out of range: {test_image.min()}-{test_image.max()}"

    # Check the corners are black (dont' include alpha channel)

    corners = [test_image[0, 0], test_image[0, -1], test_image[-1, 0], test_image[-1, -1]]

    for corner in corners:
        assert np.all(corner[:3] == 0), f"Corner not black: {corner}"

    # Check the center pixel is max value for bit depth

    mid_y, mid_x = test_image.shape[0] // 2, test_image.shape[1] // 2
    assert np.all(test_image[mid_y, mid_x] == max_value), f"Middle pixel not max: {test_image[mid_y, mid_x]}"
