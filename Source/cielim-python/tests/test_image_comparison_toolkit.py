import numpy as np
import pytest

from cielim.utils import image_comparison_toolkit as image_comparison


@pytest.fixture
def circle_image():

    size = 100
    img = np.zeros((size, size), dtype=np.uint8)
    cy, cx = size // 2, size // 2
    y, x = np.ogrid[:size, :size]
    mask = (x - cx) ** 2 + (y - cy) ** 2 <= 10**2
    img[mask] = 255
    return img


def test_histogram_diff_identical(circle_image):

    s1 = image_comparison.compute_disk_stats(circle_image)
    s2 = image_comparison.compute_disk_stats(circle_image)

    np.testing.assert_allclose(s1["mean"], s2["mean"], rtol=0, atol=0, err_msg="Means differ for identical images")
    np.testing.assert_allclose(
        s1["std"], s2["std"], rtol=0, atol=0, err_msg="Standard deviations differ for identical images"
    )

    counts1, _ = np.histogram(s1["pixels"], bins=256, range=(0, 255))
    counts2, _ = np.histogram(s2["pixels"], bins=256, range=(0, 255))
    diff = counts1.astype(int) - counts2.astype(int)

    np.testing.assert_allclose(
        diff, np.zeros_like(diff), rtol=0, atol=0, err_msg="Expected zero histogram difference for identical images"
    )


@pytest.mark.parametrize("correlate_fn", [image_comparison.cross_correlate_fft])
def test_cross_correlation_function(circle_image, correlate_fn):

    shifted = np.roll(np.roll(circle_image, shift=20, axis=1), shift=15, axis=0)
    shift_y, shift_x, _ = correlate_fn(circle_image, shifted)

    np.testing.assert_allclose(
        [-20, -15], [shift_x, shift_y], rtol=0, atol=0, err_msg="Cross-correlation did not recover the correct shift"
    )


def test_pixel_error_identical(circle_image):

    stats = image_comparison.pixel_error_stats(circle_image, circle_image)

    np.testing.assert_allclose(
        [stats["mean_error"], stats["std_error"], stats["mae"], stats["rmse"]],
        [0.0, 0.0, 0.0, 0.0],
        rtol=0,
        atol=0,
        err_msg="Expected zero pixel error between identical images",
    )
    assert stats["pixels"] == circle_image.size


def test_pixel_error_uniform_offset(circle_image):

    offset = 20
    dimmed = circle_image.astype(int)
    dimmed[dimmed > 0] -= offset
    dimmed = dimmed.astype(np.uint8)
    disk_fraction = float((circle_image > 0).sum()) / circle_image.size

    stats = image_comparison.pixel_error_stats(circle_image, dimmed)

    np.testing.assert_allclose(
        [stats["mean_error"], stats["mae"], stats["std_error"]],
        [offset * disk_fraction,
         offset * disk_fraction,
         offset * np.sqrt(disk_fraction * (1 - disk_fraction))],
        rtol=1e-12,
        atol=0,
        err_msg="Pixel error statistics do not match the injected offset",
    )

    fg = circle_image > 0
    masked = image_comparison.pixel_error_stats(circle_image, dimmed, mask=fg)
    np.testing.assert_allclose(
        [masked["mean_error"], masked["std_error"]],
        [offset, 0.0],
        rtol=0,
        atol=1e-12,
        err_msg="Masked pixel error should be the offset applied to the disk",
    )


def test_batch_pixel_error_pools_every_pixel(circle_image):

    real = np.full_like(circle_image, 100)
    pairs = [(real, np.full_like(real, 90)), (real, np.full_like(real, 110))]

    stats = image_comparison.batch_pixel_error(pairs)

    assert stats["frames"] == 2
    assert stats["pixels"] == 2 * real.size
    np.testing.assert_allclose(
        [stats["mean_error"], stats["mae"], stats["rmse"], stats["std_error"]],
        [0.0, 10.0, 10.0, 10.0],
        rtol=0,
        atol=1e-12,
        err_msg="Batch statistics must pool every pixel of every frame",
    )
    np.testing.assert_allclose(
        stats["frame_mean_std"],
        np.std([-10.0, 10.0], ddof=1),
        rtol=1e-12,
        atol=0,
        err_msg="Frame-to-frame scatter should report the per-frame means disagreeing",
    )
