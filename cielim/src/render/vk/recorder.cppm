// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* The recorder records and submits a frame's rendering commands using Vulkan objects. */

module;

#include <array>
#include <cstdint>
#include <optional>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.render.vk:recorder;

import cielim.error;
import cielim.gpu.vk;
import cielim.handle;
import cielim.result;
import cielim.utils;
import :frame_counter;
import :frame_resources;
import :mesh_registry;
import :pipeline;
import :push_constants;
import :swapchain;

export namespace cielim::render::vk
{

class Recorder
{
public:
    Recorder() = default;

    // Delete copy constructors

    Recorder(const Recorder&) = delete;
    auto operator=(const Recorder&) -> Recorder& = delete;

    // Use default move constructors

    Recorder(Recorder&&) = default;
    auto operator=(Recorder&&) -> Recorder& = default;

    /**
     * @brief Draws a frame.
     * @param context The Vulkan context.
     * @param swapchain The swapchain to which the frame should be presented.
     * @param frame_resources The frame resources to use for drawing.
     * @param frame_counter The frame counter used to pace this stream's frames and reuse of its frame resources.
     * @param render_pipeline The pipeline to be used for rendering.
     * @param scene_data_addresses Push constant struct containing scene data device addresses.
     * @param mesh_registry The mesh registry from which the meshes to be rendered are pulled.
     * @return Void on success, error code on failure.
     */
    static auto draw_frame(
        const gpu::vk::Context& context,
        const Swapchain& swapchain,
        const FrameResources& frame_resources,
        FrameCounter& frame_counter,
        const Pipeline& render_pipeline,
        const SceneDataAddresses& scene_data_addresses,
        const MeshRegistry& mesh_registry
    ) -> Result<void>
    {
        const VkDevice vk_device_handle = context.get_device();

        const uint32_t frames_in_flight = frame_resources.get_frames_in_flight();

        // We use the first queue in the queue family
        VkQueue graphics_queue;
        vkGetDeviceQueue(vk_device_handle, context.get_queue_family(), 0, &graphics_queue);

        // The image in the frame buffer to render to; [0,1] for double-buffering, [0,1,2] for triple-buffering
        const uint32_t frame_index = frame_counter.get_current_index(frames_in_flight);

        // Wait until the frame that last used this slot has finished on the GPU (no-op for the first frames)
        if (const auto result = frame_counter.wait_for_slot(frames_in_flight); !result.has_value())
            return result.propagate();

        // This semaphore is signaled when the image has been acquired and can be rendered to
        const auto image_acquire_semaphore_result = frame_resources.get_semaphore(frame_index);

        if (!image_acquire_semaphore_result.has_value())
            return image_acquire_semaphore_result.propagate();

        VkSemaphore image_acquire_semaphore = image_acquire_semaphore_result.value();

        // The image in the list of swapchain images this frame should be presented to
        uint32_t image_index;

        const auto image_acquire_result = vkAcquireNextImageKHR(
            vk_device_handle, swapchain.get_handle(), UINT64_MAX, image_acquire_semaphore, nullptr, &image_index
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
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkSwapchainError::AcquireImageError),
                    .detail = string_VkResult(image_acquire_result),
                }
            );
        }

        // This semaphore is signaled when the GPU is done rendering the frame
        const auto render_finished_semaphore_result = swapchain.get_semaphore(image_index);

        if (!render_finished_semaphore_result.has_value())
            return render_finished_semaphore_result.propagate();

        VkSemaphore render_finished_semaphore = render_finished_semaphore_result.value();

        // The image (and its view) in the swapchain this frame should render to and present

        const auto swapchain_image_result = swapchain.get_image(image_index);

        if (!swapchain_image_result.has_value())
            return swapchain_image_result.propagate();

        VkImage swapchain_image = swapchain_image_result.value();

        const auto swapchain_view_result = swapchain.get_view(image_index);

        if (!swapchain_view_result.has_value())
            return swapchain_view_result.propagate();

        VkImageView swapchain_view = swapchain_view_result.value();

        // Get GPU command resources for the frame in the frame buffer we're rendering to

        const auto command_pool_result = frame_resources.get_command_pool(frame_index);

        if (!command_pool_result.has_value())
            return command_pool_result.propagate();

        VkCommandPool command_pool = command_pool_result.value();

        const auto command_buffer_result = frame_resources.get_command_buffer(frame_index);

        if (!command_buffer_result.has_value())
            return command_buffer_result.propagate();

        VkCommandBuffer command_buffer = command_buffer_result.value();

        // Flush all commands from previous rendering
        if (const auto result = vkResetCommandPool(vk_device_handle, command_pool, 0); result != VK_SUCCESS)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkResourcesError::CommandPoolResetError),
                    .detail = string_VkResult(result),
                }
            );
        }

        constexpr VkCommandBufferBeginInfo BEGIN_INFO = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        };

        // Start recording commands to the command buffer
        if (const auto result = vkBeginCommandBuffer(command_buffer, &BEGIN_INFO); result != VK_SUCCESS)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkResourcesError::CommandBufferBeginError),
                    .detail = string_VkResult(result),
                }
            );
        }

        // Transition image to color write
        transition_image_layout(
            command_buffer,
            swapchain_image,
            VK_IMAGE_LAYOUT_UNDEFINED,
            VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            {},
            VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT
        );

        // Setup basic rendering information

        VkClearValue clear_color = {{0.0f, 0.0f, 0.0f, 1.0f}};

        VkRenderingAttachmentInfo rendering_attachment_info = {
            .sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO,
            .imageView = swapchain_view,
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

        /* We flip the viewport upside down here to account for the fact that Vulkan expects the +Y direction to
         * point downwards in NDC, but GLM implicitly assumes OpenGL's convention of +Y pointing up in NDC. */
        VkViewport viewport = {
            .x = 0.0f,
            .y = static_cast<float>(req_extent.height),
            .width = static_cast<float>(req_extent.width),
            .height = -static_cast<float>(req_extent.height),
            .minDepth = 0.0f,
            .maxDepth = 1.0f,
        };

        vkCmdSetViewport(command_buffer, 0, 1, &viewport);

        VkRect2D scissor = {
            .offset = {.x = 0, .y = 0},
            .extent = req_extent,
        };

        vkCmdSetScissor(command_buffer, 0, 1, &scissor);

        // Inject the push constants
        vkCmdPushConstants(
            command_buffer,
            render_pipeline.get_layout(),
            render_pipeline.get_push_stages(),
            0,
            sizeof(scene_data_addresses),
            &scene_data_addresses
        );

        vkCmdBindIndexBuffer(command_buffer, mesh_registry.get_index_handle(), 0, VK_INDEX_TYPE_UINT32);

        // Draw just the first (and only for now) object in the registry

        auto first_mesh = mesh_registry.get_mesh({.index = 0});

        if (first_mesh.has_value())
        {
            const auto [vertex_offset, index_offset, index_count] = first_mesh.value();
            vkCmdDrawIndexed(command_buffer, index_count, 1, index_offset, vertex_offset, 0);
        }

        vkCmdEndRendering(command_buffer);

        // Transition image to presentation
        transition_image_layout(
            command_buffer,
            swapchain_image,
            VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,
            VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
            VK_PIPELINE_STAGE_2_BOTTOM_OF_PIPE_BIT,
            {}
        );

        if (const auto result = vkEndCommandBuffer(command_buffer); result != VK_SUCCESS)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkResourcesError::CommandBufferEndError),
                    .detail = string_VkResult(result),
                }
            );
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

        // Signal the frame counter when all commands have been executed and the pool can be reused
        VkSemaphoreSubmitInfo signal_timeline_info
            = frame_counter.get_signal_info(VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT);

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
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkRenderError::QueueSubmitError),
                    .detail = string_VkResult(result),
                }
            );
        }

        // The frame's commands have been submitted, so its slot in the frame counter is now spoken for
        frame_counter.increment();

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

        // If the swapchain is out of date, give a warning and continue
        if (present_result == VK_ERROR_OUT_OF_DATE_KHR || present_result == VK_SUBOPTIMAL_KHR)
        {
            utils::log::warn("Swapchain is out of date or suboptimal on present");
        }
        else if (present_result != VK_SUCCESS)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkRenderError::QueuePresentError),
                    .detail = string_VkResult(present_result),
                }
            );
        }

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
};

} // namespace cielim::render::vk
