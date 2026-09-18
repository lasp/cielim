// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The camera navigates the scene and has view and projection. Camera (view) space coordinate system is
 * right-handed Z-up. */

module;

#include <utility>

export module cielim.camera;

import cielim.math;

constexpr float DEFAULT_FOV = cielim::math::radians(90.0f);

export namespace cielim::camera
{

class Camera
{
public:
    /**
     * @brief Sets the absolute position relative to the global inertial frame.
     * @param new_position The new position vector.
     */
    auto set_position(const math::DVec3& new_position) -> void { this->world_position_ = new_position; }

    /**
     * @brief Offsets the position in the global inertial frame.
     * @param delta_position The change in position by which to move.
     */
    auto move(const math::DVec3& delta_position) -> void { this->world_position_ += delta_position; }

    /**
     * @brief Sets the absolute orientation relative to the global inertial frame.
     * @param new_orientation The new orientation as a quaternion.
     */
    auto set_orientation(const math::Quat& new_orientation) -> void
    {
        this->orientation_ = math::normalize(new_orientation);

        // Apply the new absolute orientation to the default look_at and up vectors

        this->looking_at_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 1.0f, 0.0f));
        this->up_vec_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 0.0f, 1.0f));
    }

    /**
     * @brief Sets the absolute orientation relative to the global inertial frame.
     * @param new_yaw The new yaw in radians.
     * @param new_pitch The new pitch in radians.
     * @param new_roll The new roll in radians.
     */
    auto set_orientation(const float new_yaw, const float new_pitch, const float new_roll) -> void
    {
        // Convert euler angles to quaternions and combine

        const math::Quat new_yaw_q = math::angleAxis(new_yaw, math::Vec3(0, 0, 1));
        const math::Quat new_pitch_q = math::angleAxis(new_pitch, math::Vec3(1, 0, 0));
        const math::Quat new_roll_q = math::angleAxis(new_roll, math::Vec3(0, 1, 0));

        const math::Quat new_orientation = new_yaw_q * new_pitch_q * new_roll_q;

        this->orientation_ = math::normalize(new_orientation);

        // Apply the new absolute orientation to the default look_at and up vectors

        this->looking_at_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 1.0f, 0.0f));
        this->up_vec_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 0.0f, 1.0f));
    }

    /**
     * @brief Sets the orientation relative to the camera's local frame.
     * @param delta_orientation The change in orientation by which to rotate.
     */
    auto rotate(const math::Quat& delta_orientation) -> void
    {
        // Delta gets multiplied on the right side for it to be a relative rotation
        this->orientation_ = math::normalize(this->orientation_ * math::normalize(delta_orientation));

        // Apply the new absolute orientation to the default look_at and up vectors

        this->looking_at_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 1.0f, 0.0f));
        this->up_vec_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 0.0f, 1.0f));
    }

    /**
     * @brief Sets the orientation relative to the camera's local frame.
     * @param delta_yaw The change in yaw in radians by which to rotate.
     * @param delta_pitch The change in pitch in radians by which to rotate.
     * @param delta_roll The change in roll in radians by which to rotate.
     */
    auto rotate(const float delta_yaw, const float delta_pitch, const float delta_roll) -> void
    {
        // Convert euler angles to quaternions and combine

        const math::Quat delta_yaw_q = math::angleAxis(delta_yaw, math::Vec3(0, 0, 1));
        const math::Quat delta_pitch_q = math::angleAxis(delta_pitch, math::Vec3(1, 0, 0));
        const math::Quat delta_roll_q = math::angleAxis(delta_roll, math::Vec3(0, 1, 0));

        const math::Quat delta_orientation = delta_yaw_q * delta_pitch_q * delta_roll_q;

        // Delta gets multiplied on the right side for it to be a relative rotation
        this->orientation_ = math::normalize(this->orientation_ * math::normalize(delta_orientation));

        // Apply the new absolute orientation to the default look_at and up vectors

        this->looking_at_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 1.0f, 0.0f));
        this->up_vec_ = math::normalize(this->orientation_ * math::Vec3(0.0f, 0.0f, 1.0f));
    }

    /**
     * @brief Sets the field of view of the camera.
     * @param fov_x The horizontal fov.
     * @param fov_y The vertical fov.
     */
    auto set_fov(const float fov_x, const float fov_y) -> void
    {
        this->fov_x_ = fov_x;
        this->fov_y_ = fov_y;
    }

    /**
     * @brief Sets the field of view of the camera.
     * @param fov The field of view.
     * @param aspect The aspect ratio (width to height).
     */
    auto set_fov_aspect(const float fov, const float aspect) -> void
    {
        this->fov_x_ = aspect * fov;
        this->fov_y_ = fov;
    }

    /**
     * @brief Sets the distance of the near clipping plane from the camera.
     * @param distance The near plane distance in meters.
     */
    auto set_near_plane(const float distance) -> void { this->near_plane_distance_ = distance; }

    [[nodiscard]] auto get_view_matrix() const -> math::Mat4
    {
        const auto inverse_position_32 = static_cast<math::Vec3>(-this->world_position_);
        const math::Mat4 translation_matrix = math::translate(math::Mat4(1.0f), inverse_position_32);

        const math::Quat inverse_orientation = math::conjugate(this->orientation_);
        const math::Mat4 rotation_matrix = math::mat4_cast(inverse_orientation);

        return rotation_matrix * translation_matrix;
    }
    [[nodiscard]] auto get_projection_matrix() const -> math::Mat4
    { return math::perspective_infinite_reverse_z(this->fov_x_, this->fov_y_, this->near_plane_distance_); }
    [[nodiscard]] auto get_view_projection_matrix() const -> math::Mat4
    { return this->get_projection_matrix() * this->get_view_matrix(); }
    [[nodiscard]] auto get_position() const -> math::DVec3 { return this->world_position_; }
    [[nodiscard]] auto get_orientation() const -> math::Quat { return this->orientation_; }
    [[nodiscard]] auto get_look_at() const -> math::Vec3 { return this->looking_at_; }
    [[nodiscard]] auto get_up() const -> math::Vec3 { return this->up_vec_; }
    [[nodiscard]] auto get_fov() const -> std::pair<float, float> { return std::make_pair(this->fov_x_, this->fov_y_); }

private:
    // Double precision world coordinates in meters
    math::DVec3 world_position_ = math::DVec3(0.0, 0.0, 0.0);

    // Normalized orientation quaternion
    math::Quat orientation_ = math::Quat(1.0f, 0.0f, 0.0f, 0.0f);

    // Normalized direction vector for where the camera is looking at
    math::Vec3 looking_at_ = math::Vec3(0.0f, 1.0f, 0.0f);

    // Normalized direction vector for which direction is up
    math::Vec3 up_vec_ = math::Vec3(0.0f, 0.0f, 1.0f);

    float fov_x_ = DEFAULT_FOV;
    float fov_y_ = DEFAULT_FOV;
    float near_plane_distance_ = 0.0f;
};

} // namespace cielim::camera
