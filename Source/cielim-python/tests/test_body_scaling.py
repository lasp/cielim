import cv2
import matplotlib.pyplot as plt
import numpy as np
import pytest

import cielim

# Minimum pixel shift that counts as real movement, not render/quantization noise.
SHIFT_DETECTION_FLOOR_PX = 0.5
# Multiplier on the geometry-derived shift bound, giving headroom above the largest observed ratio.
SHIFT_BOUND_MARGIN = 1.2
# Multiplier on baseline brightness required before a change counts as a real increase/decrease.
BRIGHTNESS_CHANGE_MARGIN = 1.01


def measure_cob(image, test_name: str = "", show_plots: bool = False):
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    moments = cv2.moments(image)
    assert moments["m00"] != 0, "No brightness detected."

    cob_x, cob_y = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]

    if show_plots:
        plt.figure()
        plt.imshow(image, cmap="gray")
        plt.scatter(cob_x, cob_y, c="red", marker="x", label="center of brightness")
        plt.title(test_name)
        plt.legend()
        plt.tight_layout()
        plt.show()

    return cob_x, cob_y, moments["m00"]


def expected_shift_bound_px(scene: cielim.Scene, axis_index: int, distortion_factor: float) -> float:
    """
    Upper bound (px) on CoB movement from scaling one axis, derived from the body's angular size.
    """
    body = scene.get_celestial_body(1)
    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    distance = np.linalg.norm(spacecraft_position - np.array(body.position))

    fov = scene.get_scene().camera.lensModel.fieldOfView[axis_index]
    resolution = scene.get_scene().camera.sensorModel.resolution[axis_index]

    pixel_radius = np.arctan(body.model.meanRadius / distance) * (resolution / fov)

    return pixel_radius * abs(distortion_factor - 1)


@pytest.fixture
def default_scene() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere with the sun lighting left half.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))
    scene.set_celestial_body_params(0, position=(1.496e11, 0, 0))
    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)
    return scene


@pytest.mark.parametrize(
    "test_name, distortion",
    [
        ("Distort X", [1.5, 1, 1]),
        ("Shrink X", [0.5, 1, 1]),
        ("Distort Y", [1, 1.5, 1]),
        ("Uniform Scale", [1.5, 1.5, 1.5]),
    ],
)
def test_body_scaling(
    cielim_connection: cielim.Connector, default_scene: cielim.Scene, show_plots: bool, test_name, distortion
):
    """
    Checks distorting the body shifts the CoB only along x, within geometric bounds, and that
    pixel coverage tracks the projected size change.
    """
    connector = cielim_connection

    scene = default_scene

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    base_image, _, _ = connector.request_image_for_camera_id(1, True, False)

    base_cob_x, base_cob_y, base_brightness_sum = measure_cob(
        base_image, f"{test_name} (baseline)", show_plots=show_plots
    )

    scene.set_celestial_body_params(1, mesh_distortions=distortion)

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    cob_x, cob_y, brightness_sum = measure_cob(image, test_name, show_plots=show_plots)

    diff_x = abs(cob_x - base_cob_x)
    diff_y = abs(cob_y - base_cob_y)

    max_shift_x = max(SHIFT_DETECTION_FLOOR_PX, expected_shift_bound_px(scene, 0, distortion[0]) * SHIFT_BOUND_MARGIN)
    max_shift_y = max(SHIFT_DETECTION_FLOOR_PX, expected_shift_bound_px(scene, 1, distortion[1]) * SHIFT_BOUND_MARGIN)

    if distortion[0] != 1:
        np.testing.assert_(
            SHIFT_DETECTION_FLOOR_PX <= diff_x <= max_shift_x,
            msg=(
                f"{test_name}: X shift ({diff_x:.2f}px) outside expected range "
                f"({SHIFT_DETECTION_FLOOR_PX}-{max_shift_x:.2f}px)."
            ),
        )
    else:
        np.testing.assert_(
            diff_x <= SHIFT_DETECTION_FLOOR_PX,
            msg=f"{test_name}: X shift ({diff_x:.2f}px) expected near zero (<= {SHIFT_DETECTION_FLOOR_PX}px).",
        )

    np.testing.assert_(
        diff_y <= max_shift_y,
        msg=f"{test_name}: Y shift ({diff_y:.2f}px) outside expected range (<= {max_shift_y:.2f}px).",
    )

    projected_area_factor = distortion[0] * distortion[1]
    if projected_area_factor > 1:
        assert brightness_sum > base_brightness_sum * BRIGHTNESS_CHANGE_MARGIN, (
            f"{test_name}: projected area grew (x{projected_area_factor:.2f}) but total brightness did not increase "
            f"(base={base_brightness_sum:.0f}, actual={brightness_sum:.0f})."
        )
    elif projected_area_factor < 1:
        assert brightness_sum < base_brightness_sum / BRIGHTNESS_CHANGE_MARGIN, (
            f"{test_name}: projected area shrank (x{projected_area_factor:.2f}) but total brightness did not decrease "
            f"(base={base_brightness_sum:.0f}, actual={brightness_sum:.0f})."
        )
