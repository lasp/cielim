// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A frame counter tracks GPU frame-completion pacing for one output stream via a timeline semaphore. It should
 * be used to find out when it is safe to reuse a GPU resource. */

module;

#include <cstdint>
#include <string>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.vk:frame_counter;

import cielim.error;
import cielim.handle;
import cielim.result;
import :context;

export namespace cielim::vk::frame_counter
{

class FrameCounter
{
public:
    FrameCounter() = default;

    // Delete copy constructors

    FrameCounter(const FrameCounter&) = delete;
    auto operator=(const FrameCounter&) -> FrameCounter& = delete;

    // Use default move constructors

    FrameCounter(FrameCounter&&) = default;
    auto operator=(FrameCounter&&) -> FrameCounter& = default;

    ~FrameCounter()
    {
        if (this->timeline_semaphore_)
            vkDestroySemaphore(this->vk_device_handle_, this->timeline_semaphore_.get(), nullptr);
    }

    /**
     * @brief Initializes the frame counter.
     * @param context The Vulkan context.
     * @return Void on success, error code on failure.
     */
    auto init(const context::Context& context) -> Result<void>
    {
        this->vk_device_handle_ = context.get_device(); // This is specifically a non-owning (borrow) handle

        VkSemaphoreTypeCreateInfo timeline_semaphore_type_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,
            .semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE,
            .initialValue = 0,
        };

        const VkSemaphoreCreateInfo timeline_semaphore_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
            .pNext = &timeline_semaphore_type_info,
        };

        if (const auto result = vkCreateSemaphore(
                this->vk_device_handle_, &timeline_semaphore_info, nullptr, this->timeline_semaphore_.put()
            );
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkResourcesError::SemaphoreCreateError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        return {};
    }

    /**
     * @brief Waits for the value signaled by the frame `pool_size` slots back.
     * @details Does nothing if fewer than `pool_size` frames have been submitted.
     * @param pool_size The number of slots in the resource pool asking to reuse a slot.
     * @return Void on success, error code on failure.
     */
    [[nodiscard]] auto wait_for_slot(const uint32_t pool_size) const -> Result<void>
    {
        if (this->frame_counter_ < pool_size)
            return {}; // Nothing has used this slot yet

        VkSemaphore timeline_semaphore_handle = this->timeline_semaphore_.get();
        uint64_t wait_value = (this->frame_counter_ - pool_size) + 1;

        const VkSemaphoreWaitInfo wait_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
            .semaphoreCount = 1,
            .pSemaphores = &timeline_semaphore_handle,
            .pValues = &wait_value,
        };

        if (const auto result = vkWaitSemaphores(this->vk_device_handle_, &wait_info, UINT64_MAX); result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkResourcesError::SemaphoreWaitError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        return {};
    }

    /**
     * @brief Returns the slot index into a resource pool with `pool_size` slots for the current frame.
     * @details Calculated as counter % pool_size.
     */
    [[nodiscard]] auto get_current_index(const uint32_t pool_size) const -> uint32_t
    { return static_cast<uint32_t>(this->frame_counter_ % pool_size); }

    // Returns submit info that signals the timeline semaphore.
    [[nodiscard]] auto get_signal_info(const VkPipelineStageFlagBits2 stage_mask) const -> VkSemaphoreSubmitInfo
    {
        return VkSemaphoreSubmitInfo{
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = this->timeline_semaphore_.get(),
            .value = this->frame_counter_ + 1,
            .stageMask = stage_mask,
        };
    }

    // Increments the counter; should only be called after the frame's commands have been submitted.
    auto increment() -> void { this->frame_counter_++; }

private:
    // Non-owning handle for the Vulkan logical device
    VkDevice vk_device_handle_ = nullptr;

    // Monotonically increasing counter
    uint64_t frame_counter_ = 0;

    // Timeline semaphore corresponding to the counter to be signaled once per frame after command submission
    UniqueHandle<VkSemaphore> timeline_semaphore_;
};

} // namespace cielim::vk::frame_counter
