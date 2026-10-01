// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The scene view views an active scene and is used to render its view to a render target every frame. */

module;

#include <cstdint>
#include <string>
#include <utility>

#include <volk/volk.h>

export module cielim.render.vk:scene_view;

import cielim.gpu.vk;
import cielim.math;
import cielim.result;
import cielim.snapshot;
import :elements;

export namespace cielim::render::vk
{

class SceneView
{
public:
    // Delete copy constructors

    SceneView(const SceneView&) = delete;
    auto operator=(const SceneView&) -> SceneView& = delete;

    // Use default move constructor, delete move assignment

    SceneView(SceneView&&) = default;
    auto operator=(SceneView&&) -> SceneView& = delete;

    ~SceneView() = default;

    /**
     * @brief Creates the scene view.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param frames_in_flight The number of frames in flight.
     * @return The scene view on success, error code on failure.
     */
    static auto
    create(const gpu::vk::Context& context, const gpu::vk::Allocator& allocator, const uint32_t frames_in_flight)
        -> Result<SceneView>
    {
        // These flags are needed so that we can fetch buffer contents from shaders with device addresses
        constexpr VkBufferUsageFlags FLAGS
            = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT;

        auto scene_info_result = gpu::vk::BufferRing<SceneInfo>::create(context, allocator, frames_in_flight, 1, FLAGS);

        if (!scene_info_result.has_value())
            return Err(scene_info_result.error().with_trace("failed to create scene view"));

        return SceneView(std::move(scene_info_result).value());
    }

    /**
     * @brief Updates the view's camera info in its buffers from a camera.
     * @details This should only be called after waiting on the frame index's frame counter slot.
     * @param camera The camera from which to update.
     * @param sun_pos The position of the sun in the scene inertial frame.
     * @param frame_index The current frame index.
     * @return Void on success, error code on failure.
     */
    auto update(const snapshot::Camera& camera, const math::Vec3& sun_pos, const uint32_t frame_index) const
        -> Result<void>
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
    explicit SceneView(gpu::vk::BufferRing<SceneInfo>&& scene_info) : scene_info_(std::move(scene_info)) {}

    // The list of scene info buffers for each frame in flight
    gpu::vk::BufferRing<SceneInfo> scene_info_;
};

} // namespace cielim::render::vk
