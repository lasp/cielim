import numpy as np
import pytest

import context
from cielim.image_comparison_toolkit import compute_disk_stats, cross_correlate_fft


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

    s1 = compute_disk_stats(circle_image)
    s2 = compute_disk_stats(circle_image)

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


@pytest.mark.parametrize("correlate_fn", [cross_correlate_fft])
def test_cross_correlation_function(circle_image, correlate_fn):

    shifted = np.roll(np.roll(circle_image, shift=20, axis=1), shift=15, axis=0)
    shift_y, shift_x, _ = correlate_fn(circle_image, shifted)

    np.testing.assert_allclose(
        [-20, -15], [shift_x, shift_y], rtol=0, atol=0, err_msg="Cross-correlation did not recover the correct shift"
    )
