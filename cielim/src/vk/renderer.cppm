// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* The renderer renders a frame using Vulkan objects. */

module;

#include <array>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.vk:renderer;

import cielim.handle;
import cielim.result;
import cielim.utils;
import :context;
import :frame_resources;
import :pipeline;
import :swapchain;

export namespace cielim::vk::renderer
{

class Renderer
{
public:
    Renderer() = default;

    // Delete copy constructors

    Renderer(const Renderer&) = delete;
    auto operator=(const Renderer&) -> Renderer& = delete;

    // Use default move constructors

    Renderer(Renderer&&) = default;
    auto operator=(Renderer&&) -> Renderer& = default;

    ~Renderer()
    {
        if (timeline_semaphore_)
            vkDestroySemaphore(this->vk_device_handle_, this->timeline_semaphore_.get(), nullptr);
    }

    /**
     * @brief Initializes the renderer.
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

        if (const auto result
            = vkCreateSemaphore(this->vk_device_handle_, &timeline_semaphore_info, nullptr, timeline_semaphore_.put());
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
     * @brief Draws a frame.
     * @param context The Vulkan context.
     * @param frame_resources The frame resources to use for drawing.
     * @param render_pipeline The pipeline to be used for rendering.
     * @param swapchain The swapchain to which the frame should be presented.
     * @return Void on success, error code on failure.
     */
    auto draw_frame(
        const context::Context& context,
        const frame_resources::FrameResources& frame_resources,
        const pipeline::Pipeline& render_pipeline,
        const swapchain::Swapchain& swapchain
    ) -> Result<void>
    {
        // Don't do anything if renderer is not initialized
        if (this->vk_device_handle_ == nullptr)
            return {};

        const uint32_t frames_in_flight = frame_resources.get_frames_in_flight();

        // We use the first queue in the queue family
        VkQueue graphics_queue;
        vkGetDeviceQueue(this->vk_device_handle_, context.get_queue_family(), 0, &graphics_queue);

        // The image in the frame buffer to render to; [0,1] for double-buffering, [0,1,2] for triple-buffering
        const uint32_t frame_index = this->frame_counter_ % frames_in_flight;

        // Don't wait if it's the first frames to be rendered as there's nothing to wait on
        if (this->frame_counter_ >= frames_in_flight)
        {
            VkSemaphore timeline_semaphore_handle = this->timeline_semaphore_.get();

            // Wait for the timeline value signaled by the previous rendered frame in this frame index
            uint64_t wait_value = (this->frame_counter_ - frames_in_flight) + 1;

            const VkSemaphoreWaitInfo wait_info = {
                .sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
                .semaphoreCount = 1,
                .pSemaphores = &timeline_semaphore_handle,
                .pValues = &wait_value,
            };

            if (const auto result = vkWaitSemaphores(this->vk_device_handle_, &wait_info, UINT64_MAX);
                result != VK_SUCCESS)
            {
                error::DetailedError error = {
                    .errc = make_error_code(error::VkResourcesError::SemaphoreWaitError),
                    .detail = string_VkResult(result),
                };

                return Err(error);
            }
        }

        // This semaphore is signaled when the image has been acquired and can be rendered to
        VkSemaphore image_acquire_semaphore = frame_resources.get_semaphore(frame_index);

        // The image in the list of swapchain images this frame should be presented to
        uint32_t image_index;

        const auto image_acquire_result = vkAcquireNextImageKHR(
            this->vk_device_handle_, swapchain.get_handle(), UINT64_MAX, image_acquire_semaphore, nullptr, &image_index
        );

        // If the swapchain is out of date, skip frame and try again
        if (image_acquire_result == VK_ERROR_OUT_OF_DATE_KHR)
        {
            utils::log::warn("Swapchain is out of date on acquire, skipping frame");
            return {};
        }
        // Only warn with suboptimal, keep rendering afterwards
        if (image_acquire_result == VK_SUBOPTIMAL_KHR)
        {
            utils::log::warn("Swapchain is suboptimal on acquire");
        }
        else if (image_acquire_result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkSwapchainError::AcquireImageError),
                .detail = string_VkResult(image_acquire_result),
            };

            return Err(error);
        }

        // This semaphore is signaled when the GPU is done rendering the frame
        VkSemaphore render_finished_semaphore = swapchain.get_semaphore(image_index);

        // Get GPU command resources for the frame in the frame buffer we're rendering to

        VkCommandPool command_pool = frame_resources.get_command_pool(frame_index);
        VkCommandBuffer command_buffer = frame_resources.get_command_buffer(frame_index);

        // Flush all commands from previous rendering
        if (const auto result = vkResetCommandPool(this->vk_device_handle_, command_pool, 0); result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkResourcesError::CommandPoolResetError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        constexpr VkCommandBufferBeginInfo BEGIN_INFO = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        };

        // Start recording commands to the command buffer
        if (const auto result = vkBeginCommandBuffer(command_buffer, &BEGIN_INFO); result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkResourcesError::CommandBufferBeginError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        // Transition image to color write
        transition_image_layout(
            command_buffer,
            swapchain.get_image(image_index),
            VK_IMAGE_LAYOUT_UNDEFINED,
            VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            {},
            VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT
        );

        // Setup basic rendering information

        constexpr float GRAY_COLOR = 0.12f;

        VkClearValue clear_color = {{GRAY_COLOR, GRAY_COLOR, GRAY_COLOR, GRAY_COLOR}};

        VkRenderingAttachmentInfo rendering_attachment_info = {
            .sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO,
            .imageView = swapchain.get_view(image_index),
            .imageLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR,
            .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
            .clearValue = clear_color,
        };

        VkExtent2D req_extent = swapchain.get_extent();

        VkRenderingInfo rendering_info = {
            .sType = VK_STRUCTURE_TYPE_RENDERING_INFO,
            .renderArea = {.offset = {.x = 0, .y = 0}, .extent = req_extent},
            .layerCount = 1,
            .colorAttachmentCount = 1,
            .pColorAttachments = &rendering_attachment_info,
        };

        vkCmdBeginRendering(command_buffer, &rendering_info);

        vkCmdBindPipeline(command_buffer, VK_PIPELINE_BIND_POINT_GRAPHICS, render_pipeline.get_handle());

        VkViewport viewport = {
            .x = 0.0f,
            .y = 0.0f,
            .width = static_cast<float>(req_extent.width),
            .height = static_cast<float>(req_extent.height),
            .minDepth = 0.0f,
            .maxDepth = 0.0f,
        };

        vkCmdSetViewport(command_buffer, 0, 1, &viewport);

        VkRect2D scissor = {
            .offset = {.x = 0, .y = 0},
            .extent = req_extent,
        };

        vkCmdSetScissor(command_buffer, 0, 1, &scissor);

        // Draw a single triangle
        vkCmdDraw(command_buffer, 3, 1, 0, 0);

        vkCmdEndRendering(command_buffer);

        // Transition image to presentation
        transition_image_layout(
            command_buffer,
            swapchain.get_image(image_index),
            VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,
            VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
            VK_PIPELINE_STAGE_2_BOTTOM_OF_PIPE_BIT,
            {}
        );

        if (const auto result = vkEndCommandBuffer(command_buffer); result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkResourcesError::CommandBufferEndError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        // Submit commands to the graphics queue

        // Don't begin rendering until image acquisition is completed
        VkSemaphoreSubmitInfo wait_acquire_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = image_acquire_semaphore,
            .stageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
        };

        // Signal when the presentation layout transition has completed
        VkSemaphoreSubmitInfo signal_render_finished_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = render_finished_semaphore,
            .stageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT,
        };

        // Signal the counter when all commands have been executed and the pool can be cleared
        VkSemaphoreSubmitInfo signal_timeline_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = this->timeline_semaphore_.get(),
            .value = this->frame_counter_ + 1,
            .stageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT,
        };

        std::array wait_semaphores = {wait_acquire_info};
        std::array signal_semaphores = {signal_render_finished_info, signal_timeline_info};

        VkCommandBufferSubmitInfo buffer_submit_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
            .commandBuffer = command_buffer,
        };

        VkSubmitInfo2 submit_info = {
            .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO_2,
            .waitSemaphoreInfoCount = wait_semaphores.size(),
            .pWaitSemaphoreInfos = wait_semaphores.data(),
            .commandBufferInfoCount = 1,
            .pCommandBufferInfos = &buffer_submit_info,
            .signalSemaphoreInfoCount = signal_semaphores.size(),
            .pSignalSemaphoreInfos = signal_semaphores.data(),
        };

        if (const auto result = vkQueueSubmit2(graphics_queue, 1, &submit_info, nullptr); result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkRenderError::QueueSubmitError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        // Submit render output presentation command to the swapchain

        VkSwapchainKHR swapchain_handle = swapchain.get_handle();

        VkPresentInfoKHR present_info = {
            .sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,
            .waitSemaphoreCount = 1,
            .pWaitSemaphores = &render_finished_semaphore, // Presentation should wait until rendering is done
            .swapchainCount = 1,
            .pSwapchains = &swapchain_handle,
            .pImageIndices = &image_index,
        };

        const auto present_result = vkQueuePresentKHR(graphics_queue, &present_info);

        // If the swapchain is out of date, t
        if (present_result == VK_ERROR_OUT_OF_DATE_KHR || present_result == VK_SUBOPTIMAL_KHR)
        {
            utils::log::warn("Swapchain is out of date or suboptimal on present");
        }
        else if (present_result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkRenderError::QueuePresentError),
                .detail = string_VkResult(present_result),
            };

            return Err(error);
        }

        this->frame_counter_++;

        return {};
    }

private:
    /**
     * @brief Transitions an image from one layout to another.
     * @param command_buffer The command buffer into which this transition should be recorded.
     * @param image The image whose layout is to be transitioned.
     * @param old_layout The current (old) layout of the image before the transition.
     * @param new_layout The desired (new) layout of the image after the transition.
     * @param src_stage_mask The pipeline stage(s) that must complete before the transition can begin.
     * @param src_access_mask The access types that must complete before the transition occurs.
     * @param dst_stage_mask The pipeline stage(s) that must wait for the transition to complete before proceeding.
     * @param dst_access_mask The access types that must wait for the transition to complete.
     */
    static auto transition_image_layout(
        const VkCommandBuffer command_buffer,
        const VkImage image,
        const VkImageLayout old_layout,
        const VkImageLayout new_layout,
        const VkPipelineStageFlagBits2 src_stage_mask,
        const VkAccessFlags2 src_access_mask,
        const VkPipelineStageFlagBits2 dst_stage_mask,
        const VkAccessFlags2 dst_access_mask

    ) -> void
    {
        VkImageMemoryBarrier2 barrier = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
            .srcStageMask = src_stage_mask,
            .srcAccessMask = src_access_mask,
            .dstStageMask = dst_stage_mask,
            .dstAccessMask = dst_access_mask,
            .oldLayout = old_layout,
            .newLayout = new_layout,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = image,
            .subresourceRange = {
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };

        const VkDependencyInfo dependency_info = {
            .sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
            .dependencyFlags = {},
            .imageMemoryBarrierCount = 1,
            .pImageMemoryBarriers = &barrier,
        };

        vkCmdPipelineBarrier2(command_buffer, &dependency_info);
    }

    // Non-owning handle for the Vulkan logical device
    VkDevice vk_device_handle_ = nullptr;

    // Monotonically increasing counter
    uint64_t frame_counter_ = 0;

    // Semaphore corresponding to the monotonic counter
    UniqueHandle<VkSemaphore> timeline_semaphore_;
};

} // namespace cielim::vk::renderer
