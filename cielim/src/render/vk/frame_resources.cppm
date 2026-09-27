// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Groups several coupled frame resources into a single class. */

module;

#include <cstdint>
#include <string>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.render.vk:frame_resources;

import cielim.error;
import cielim.gpu.vk;
import cielim.helpers;
import cielim.result;

export namespace cielim::render::vk
{

class FrameResources
{
public:
    // Delete copy constructors

    FrameResources(const FrameResources&) = delete;
    auto operator=(const FrameResources&) -> FrameResources& = delete;

    // Use default move constructor, delete move assignment

    FrameResources(FrameResources&&) = default;
    auto operator=(FrameResources&&) -> FrameResources& = delete;

    ~FrameResources()
    {
        // Destroying command pool destroys associated command buffers as well
        for (const auto& pool : this->command_pools_)
        {
            if (pool != nullptr)
                vkDestroyCommandPool(this->vk_device_handle_, pool, nullptr);
        }

        for (const auto& semaphore : this->image_acquire_semaphores_)
        {
            if (semaphore != nullptr)
                vkDestroySemaphore(this->vk_device_handle_, semaphore, nullptr);
        }
    }

    /**
     * @brief Creates various frame resources for rendering.
     * @param context The Vulkan context.
     * @param triple_buffer Whether rendering should be triple buffered. If not, it will be double buffered.
     * @return The frame resources on success, error code on failure.
     */
    static auto create(const gpu::vk::Context& context, const bool triple_buffer) -> Result<FrameResources>
    {
        FrameResources frame_resources;

        frame_resources.vk_device_handle_ = context.get_device(); // This is specifically a non-owning (borrow) handle

        // Default to double-buffering
        frame_resources.frames_in_flight_ = 2;

        if (triple_buffer)
            frame_resources.frames_in_flight_ = 3;

        // Create command pools and command buffers

        frame_resources.command_pools_.resize(frame_resources.frames_in_flight_);
        frame_resources.command_buffers_.resize(frame_resources.frames_in_flight_);

        for (uint32_t i = 0; i < frame_resources.frames_in_flight_; i++)
        {
            VkCommandPoolCreateInfo command_pool_create_info = {
                .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
                .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
                .queueFamilyIndex = context.get_queue_family(),
            };

            if (const auto result = vkCreateCommandPool(
                    frame_resources.vk_device_handle_,
                    &command_pool_create_info,
                    nullptr,
                    &frame_resources.command_pools_[i]
                );
                result != VK_SUCCESS)
            {
                return Err(
                    error::DetailedError{
                        .errc = make_error_code(error::VkResourcesError::CommandPoolCreateError),
                        .detail = string_VkResult(result),
                    }
                );
            }

            VkCommandBufferAllocateInfo command_buffer_allocate_info = {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
                .commandPool = frame_resources.command_pools_[i],
                .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                .commandBufferCount = 1,
            };

            if (const auto result = vkAllocateCommandBuffers(
                    frame_resources.vk_device_handle_,
                    &command_buffer_allocate_info,
                    &frame_resources.command_buffers_[i]
                );
                result != VK_SUCCESS)
            {
                return Err(
                    error::DetailedError{
                        .errc = make_error_code(error::VkResourcesError::CommandBufferCreateError),
                        .detail = string_VkResult(result),
                    }
                );
            }
        }

        // Create image acquire semaphores

        constexpr VkSemaphoreCreateInfo BINARY_SEMAPHORE_INFO = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
        };

        frame_resources.image_acquire_semaphores_.resize(frame_resources.frames_in_flight_);

        for (auto& semaphore : frame_resources.image_acquire_semaphores_)
        {
            if (const auto result
                = vkCreateSemaphore(frame_resources.vk_device_handle_, &BINARY_SEMAPHORE_INFO, nullptr, &semaphore);
                result != VK_SUCCESS)
            {
                return Err(
                    error::DetailedError{
                        .errc = make_error_code(error::VkResourcesError::SemaphoreCreateError),
                        .detail = std::string("image acquire semaphore: ") + string_VkResult(result),
                    }
                );
            }
        }

        return frame_resources;
    }

    [[nodiscard]] auto get_frames_in_flight() const -> uint32_t { return this->frames_in_flight_; }
    auto get_command_pool(const uint32_t index) const -> Result<VkCommandPool>
    { return try_at(this->command_pools_, index); }
    auto get_command_buffer(const uint32_t index) const -> Result<VkCommandBuffer>
    { return try_at(this->command_buffers_, index); }
    auto get_semaphore(const uint32_t index) const -> Result<VkSemaphore>
    { return try_at(this->image_acquire_semaphores_, index); }

private:
    FrameResources() = default;

    // Non-owning handle for the Vulkan logical device
    VkDevice vk_device_handle_ = nullptr;

    // The number of frames to render and present at one time; 2 = double-buffering, 3 = triple-buffering
    uint32_t frames_in_flight_ = 0;

    // List of GPU command pools to allocate, count should equal (frames in flight x recording threads)
    std::vector<VkCommandPool> command_pools_;

    // List of GPU command buffers, one-to-one with command pools for now
    std::vector<VkCommandBuffer> command_buffers_;

    // List of semaphores used to signal when a swapchain image can be acquired, count should equal frames in flight
    std::vector<VkSemaphore> image_acquire_semaphores_;
};

} // namespace cielim::render::vk
