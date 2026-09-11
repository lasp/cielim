// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Groups several coupled frame resources into a single class. */

module;

#include <string>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.vk:frame_resources;

import cielim.result;
import :context;

export namespace cielim::vk::frame_resources
{

class FrameResources
{
public:
    FrameResources() = default;

    // Delete copy constructors

    FrameResources(const FrameResources&) = delete;
    auto operator=(const FrameResources&) -> FrameResources& = delete;

    // Use default move constructors

    FrameResources(FrameResources&&) = default;
    auto operator=(FrameResources&&) -> FrameResources& = default;

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
     * @brief Initializes various frame resources for rendering.
     * @param context The Vulkan context.
     * @param triple_buffer Whether rendering should be triple buffered. If not, it will be double buffered.
     * @return Void on success, error code on failure.
     */
    auto init(const context::Context& context, const bool triple_buffer) -> Result<void>
    {
        this->vk_device_handle_ = context.get_device(); // This is specifically a non-owning (borrow) handle

        // Default to double-buffering
        this->frames_in_flight_ = 2;

        if (triple_buffer)
            this->frames_in_flight_ = 3;

        // Create command pools and command buffers

        this->command_pools_.resize(this->frames_in_flight_);
        this->command_buffers_.resize(this->frames_in_flight_);

        for (uint32_t i = 0; i < this->frames_in_flight_; i++)
        {
            VkCommandPoolCreateInfo command_pool_create_info = {
                .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
                .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
                .queueFamilyIndex = context.get_queue_family(),
            };

            if (const auto result = vkCreateCommandPool(
                    this->vk_device_handle_, &command_pool_create_info, nullptr, &this->command_pools_[i]
                );
                result != VK_SUCCESS)
            {
                error::DetailedError error = {
                    .errc = make_error_code(error::VkResourcesError::CommandPoolCreateError),
                    .detail = string_VkResult(result),
                };

                return Err(error);
            }

            VkCommandBufferAllocateInfo command_buffer_allocate_info = {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
                .commandPool = this->command_pools_[i],
                .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                .commandBufferCount = 1,
            };

            if (const auto result = vkAllocateCommandBuffers(
                    this->vk_device_handle_, &command_buffer_allocate_info, &this->command_buffers_[i]
                );
                result != VK_SUCCESS)
            {
                error::DetailedError error = {
                    .errc = make_error_code(error::VkResourcesError::CommandBufferCreateError),
                    .detail = string_VkResult(result),
                };

                return Err(error);
            }
        }

        // Create image acquire semaphores

        constexpr VkSemaphoreCreateInfo BINARY_SEMAPHORE_INFO = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
        };

        this->image_acquire_semaphores_.resize(this->frames_in_flight_);

        for (auto& semaphore : this->image_acquire_semaphores_)
        {
            if (const auto result
                = vkCreateSemaphore(this->vk_device_handle_, &BINARY_SEMAPHORE_INFO, nullptr, &semaphore);
                result != VK_SUCCESS)
            {
                error::DetailedError error = {
                    .errc = make_error_code(error::VkResourcesError::SemaphoreCreateError),
                    .detail = std::string("image acquire semaphore: ") + string_VkResult(result),
                };

                return Err(error);
            }
        }

        return {};
    }

    [[nodiscard]] auto get_frames_in_flight() const -> uint32_t { return this->frames_in_flight_; }
    [[nodiscard]] auto get_command_pool(const uint32_t index) const -> VkCommandPool
    { return this->command_pools_.at(index); }
    [[nodiscard]] auto get_command_buffer(const uint32_t index) const -> VkCommandBuffer
    { return this->command_buffers_.at(index); }
    [[nodiscard]] auto get_semaphore(const uint32_t index) const -> VkSemaphore
    { return this->image_acquire_semaphores_.at(index); }

private:
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

} // namespace cielim::vk::frame_resources
