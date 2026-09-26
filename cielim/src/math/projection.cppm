// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Defines constructor for infinite-far-plane reverse-Z perspective projection matrix. This matrix form
 * assumes camera (view) space has a right-handed Z-up coordinate system, and projects to Vulkan NDC with Y-down. */

module;

export module cielim.math:projection;

import :tensors;

export namespace cielim::math
{

/**
 * @brief Constructs a right-handed, infinite-far-plane, reverse-Z perspective projection matrix.
 * @details The near plane maps to a depth of 1.0 and infinity maps to a depth of 0.0.
 * @param fov_x Horizontal field of view in radians.
 * @param fov_y Vertical field of view in radians.
 * @param z_near Distance from the camera to the near clipping plane in meters (must be positive).
 * @return A 4x4 perspective projection matrix.
 */
[[nodiscard]] auto perspective_infinite_reverse_z(const float fov_x, const float fov_y, const float z_near) -> Mat4
{
    float effective_z_near = 0.0f;

    // Make sure they didn't put in faulty value
    if (z_near > 0.0f)
        effective_z_near = z_near;

    const float focal_length_x = 1.0f / tan(fov_x * 0.5f);
    const float focal_length_y = 1.0f / tan(fov_y * 0.5f);

    Mat4 perspective_matrix(0.0f);
    perspective_matrix[0][0] = focal_length_x;
    perspective_matrix[2][1] = focal_length_y;
    perspective_matrix[3][2] = effective_z_near;
    perspective_matrix[1][3] = 1.0f;

    return perspective_matrix;
}

/**
 * @brief Constructs a right-handed, infinite-far-plane, reverse-Z perspective projection matrix.
 * @details The near plane maps to a depth of 1.0 and infinity maps to a depth of 0.0.
 * @param aspect Aspect ratio (width to height).
 * @param fov_y Vertical field of view in radians.
 * @param z_near Distance from the camera to the near clipping plane in meters (must be positive).
 * @return A 4x4 perspective projection matrix.
 */
[[nodiscard]] auto perspective_infinite_reverse_z_aspect(const float aspect, const float fov_y, const float z_near)
    -> Mat4
{
    float effective_z_near = 0.0f;

    // Make sure they didn't put in faulty value
    if (z_near > 0.0f)
        effective_z_near = z_near;

    const float focal_length_y = 1.0f / tan(fov_y * 0.5f);
    const float focal_length_x = focal_length_y / aspect;

    Mat4 perspective_matrix(0.0f);
    perspective_matrix[0][0] = focal_length_x;
    perspective_matrix[2][1] = focal_length_y;
    perspective_matrix[3][2] = effective_z_near;
    perspective_matrix[1][3] = 1.0f;

    return perspective_matrix;
}

} // namespace cielim::math
