// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The scene view views an active scene and is used to render its view to a render target every frame. */

module;

#include <cstdint>
#include <string>

#include <volk/volk.h>

export module cielim.render.vk:scene_view;

import cielim.gpu.vk;
import cielim.math;
import cielim.result;
import cielim.snapshot;

export namespace cielim::render::vk
{

struct SceneInfo
{
    math::Mat4 view_projection{};
    math::Vec3 sun_position{};
};

class SceneView
{
public:
    SceneView() = default;

    // Delete copy constructors

    SceneView(const SceneView&) = delete;
    auto operator=(const SceneView&) -> SceneView& = delete;

    // Use default move constructors

    SceneView(SceneView&&) = default;
    auto operator=(SceneView&&) -> SceneView& = default;

    ~SceneView() = default;

    /**
     * @brief Creates the scene view.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param frames_in_flight The number of frames in flight.
     * @return Void on success, error code on failure.
     */
    auto create(const gpu::vk::Context& context, const gpu::vk::Allocator& allocator, const uint32_t frames_in_flight)
        -> Result<void>
    {
        // These flags are needed so that we can fetch buffer contents from shaders with device addresses
        constexpr VkBufferUsageFlags FLAGS
            = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT;

        if (const auto result = this->scene_info_.create(context, allocator, frames_in_flight, 1, FLAGS);
            !result.has_value())
            return Err(result.error().with_trace("failed to create scene view"));

        return {};
    }

    /**
     * @brief Updates the view's camera info in its buffers from a camera.
     * @param camera The camera from which to update.
     * @param sun_pos The position of the sun in the scene inertial frame.
     * @param frame_index The current frame index.
     */
    auto update(const snapshot::Camera& camera, const math::Vec3& sun_pos, const uint32_t frame_index) -> Result<void>
    {
        const math::Mat4 view_projection = camera.get_view_projection_matrix();

        const SceneInfo scene_info = {
            .view_projection = view_projection,
            .sun_position = sun_pos,
        };

        if (const auto result = this->scene_info_.write(frame_index, 0, scene_info); !result.has_value())
            return Err(result.error().with_trace("failed to update scene view"));

        return {};
    }

    auto get_scene_info_address(const uint32_t frame_index) const -> Result<VkDeviceAddress>
    { return this->scene_info_.get_address(frame_index); }

private:
    // The list of scene info buffers for each frame in flight
    gpu::vk::BufferRing<SceneInfo> scene_info_;
};

} // namespace cielim::render::vk
