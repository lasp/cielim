// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Serves as the program entry point. */

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_vulkan.h>

#include <SDL3/SDL_main.h> // This has to be the last SDL include

import cielim.error;
import cielim.result;
import cielim.utils;
import cielim.vk;
import cielim.window;

static cielim::vk::Context& vk_context = cielim::vk::Context::get_context();
static VkSemaphore timeline_semaphore = VK_NULL_HANDLE;

// Clean up Vulkan resources
static auto clean() -> void
{
    if (timeline_semaphore != VK_NULL_HANDLE)
        vkDestroySemaphore(vk_context.get_device(), timeline_semaphore, nullptr);
}

static auto fatal_error(const cielim::window::Window* window, const std::string& message) -> void
{
    cielim::utils::log::critical("{}", message);

    if (window != nullptr)
        window->error_popup(message);
}

auto main(int argc, char* argv[]) -> int
{
    // Create vulkan specific log for validation layers
    cielim::utils::log::init_log("log-vulkan");

    // Create default main log
    cielim::utils::log::init_log("log-cielim");

    // Set global log format
    cielim::utils::log::set_pattern("[%Y-%m-%d %H:%M:%S.%e] %n - %^%l%$: %v");

    // Set lowest rendered level to trace i.e., everything is logged
    cielim::utils::log::set_level(cielim::utils::log::level::trace);

    // Flush warnings and above immediately instead of buffering
    cielim::utils::log::flush_on(cielim::utils::log::level::warn);

    const char* base_path_raw = SDL_GetBasePath();

    if (base_path_raw == nullptr)
    {
        fatal_error(nullptr, fmt::format("Executable location could not be found: {}", SDL_GetError()));
        return EXIT_FAILURE;
    }

    std::filesystem::path base_path(base_path_raw);

    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS))
    {
        fatal_error(nullptr, fmt::format("SDL failed to initialize: {}", SDL_GetError()));
        return EXIT_FAILURE;
    }

    if (volkInitialize() != VK_SUCCESS)
    {
        fatal_error(nullptr, "Volk failed to initialize!");
        return EXIT_FAILURE;
    }

    constexpr int WINDOW_WIDTH = 1280;
    constexpr int WINDOW_HEIGHT = 720;

    auto window = cielim::window::Window();

    auto win_result
        = window.create_window("cielim", WINDOW_WIDTH, WINDOW_HEIGHT, SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE);

    if (!win_result.has_value())
    {
        fatal_error(nullptr, win_result.error().message());
        return EXIT_FAILURE;
    }

    if (auto const result = vk_context.init(window); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        clean();
        return EXIT_FAILURE;
    }

    VkResult vk_result;

    cielim::vk::Swapchain swapchain;

    if (const auto result = swapchain.init(vk_context, window);
        !result.has_value() && result.error().errc != cielim::error::VkSwapchainError::NullExtent)
    {
        fatal_error(&window, result.error().message());
        clean();
        return EXIT_FAILURE;
    }

    std::filesystem::path triangle_shader_path = base_path / "content" / "shaders" / "triangle.spv";

    cielim::vk::Shader triangle_shader;

    if (const auto result = triangle_shader.create(vk_context, triangle_shader_path); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        clean();
        return EXIT_FAILURE;
    }

    cielim::vk::Pipeline render_pipeline;

    std::vector<cielim::vk::ShaderStage> stages = {
        {.stage_flag = VK_SHADER_STAGE_VERTEX_BIT, .shader_module = triangle_shader, .entry_point = "VertMain"},
        {.stage_flag = VK_SHADER_STAGE_FRAGMENT_BIT, .shader_module = triangle_shader, .entry_point = "FragMain"},
    };

    if (const auto result = render_pipeline.create(vk_context, swapchain, stages); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        clean();
        return EXIT_FAILURE;
    }

    cielim::vk::FrameResources frame_resources;

    if (const auto result = frame_resources.init(vk_context, false); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        clean();
        return EXIT_FAILURE;
    }

    uint32_t frames_in_flight = frame_resources.get_frames_in_flight();

    VkSemaphoreTypeCreateInfo timeline_semaphore_type_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,
        .semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE,
        .initialValue = 0,
    };

    VkSemaphoreCreateInfo timeline_semaphore_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
        .pNext = &timeline_semaphore_type_info,
    };

    vk_result = vkCreateSemaphore(vk_context.get_device(), &timeline_semaphore_info, nullptr, &timeline_semaphore);

    if (vk_result != VK_SUCCESS)
    {
        fatal_error(&window, fmt::format("Failed to create timeline semaphore: {}", string_VkResult(vk_result)));
        clean();
        return EXIT_FAILURE;
    }

    VkQueue graphics_queue;
    vkGetDeviceQueue(vk_context.get_device(), vk_context.get_queue_family(), 0, &graphics_queue);

    uint64_t frame_counter = 0;

    bool is_running = true;

    while (is_running)
    {
        SDL_Event event;
        while (SDL_PollEvent(&event))
        {
            switch (event.type)
            {
            case SDL_EVENT_QUIT: is_running = false; break;

            case SDL_EVENT_WINDOW_RESIZED:
                if (const auto result = swapchain.recreate(vk_context, window);
                    !result.has_value() && result.error().errc != cielim::error::VkSwapchainError::NullExtent)
                {
                    fatal_error(&window, result.error().message());
                    clean();
                    return EXIT_FAILURE;
                }
                break;

            default: break;
            }
        }

        SDL_WindowFlags window_flags = SDL_GetWindowFlags(window.get_handle());

        if ((window_flags & SDL_WINDOW_MINIMIZED) != 0 || swapchain.get_handle() == nullptr)
        {
            SDL_Delay(8); // Wait a bit to reduce CPU usage when not rendering
            continue;
        }

        frame_counter++;

        const uint32_t frame_index = (frame_counter - 1) % frames_in_flight;

        if (frame_counter > frames_in_flight)
        {
            uint64_t wait_value = frame_counter - frames_in_flight;

            VkSemaphoreWaitInfo wait_info = {
                .sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
                .semaphoreCount = 1,
                .pSemaphores = &timeline_semaphore,
                .pValues = &wait_value,
            };

            vk_result = vkWaitSemaphores(vk_context.get_device(), &wait_info, UINT64_MAX);

            if (vk_result != VK_SUCCESS)
            {
                fatal_error(
                    &window, fmt::format("Failed waiting on timeline semaphore: {}", string_VkResult(vk_result))
                );
                clean();
                return EXIT_FAILURE;
            }
        }

        uint32_t image_index;

        auto image_acquire_semaphore = frame_resources.get_semaphore(frame_index);

        vk_result = vkAcquireNextImageKHR(
            vk_context.get_device(), swapchain.get_handle(), UINT64_MAX, image_acquire_semaphore, nullptr, &image_index
        );

        if (vk_result == VK_ERROR_OUT_OF_DATE_KHR)
        {
            cielim::utils::log::warn("Swapchain out of date on acquire, skipping frame");
            frame_counter--;
            continue;
        }

        if (vk_result != VK_SUCCESS && vk_result != VK_SUBOPTIMAL_KHR)
        {
            fatal_error(&window, fmt::format("Failed to acquire swapchain image: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        auto render_finished_semaphore = swapchain.get_semaphore(image_index);

        auto command_pool = frame_resources.get_command_pool(frame_index);
        auto command_buffer = frame_resources.get_command_buffer(frame_index);

        vk_result = vkResetCommandPool(vk_context.get_device(), command_pool, 0);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Failed to reset command pool: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferBeginInfo begin_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        };

        vk_result = vkBeginCommandBuffer(command_buffer, &begin_info);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Failed to begin command buffer: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        // This can be reused after each command recording
        VkImageMemoryBarrier2 barrier = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
            .srcStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            .srcAccessMask = {},
            .dstStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            .dstAccessMask = VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
            .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = swapchain.get_image(image_index),
            .subresourceRange = {
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };

        // Same for this
        VkDependencyInfo dependency_info = {
            .sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
            .dependencyFlags = {},
            .imageMemoryBarrierCount = 1,
            .pImageMemoryBarriers = &barrier,
        };

        vkCmdPipelineBarrier2(command_buffer, &dependency_info);

        VkClearValue clear_color = {{0.12f, 0.12f, 0.12f, 1.0f}};

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

        VkRect2D scissor = {
            .offset = {.x = 0, .y = 0},
            .extent = req_extent,
        };

        vkCmdSetViewport(command_buffer, 0, 1, &viewport);
        vkCmdSetScissor(command_buffer, 0, 1, &scissor);

        vkCmdDraw(command_buffer, 3, 1, 0, 0);

        vkCmdEndRendering(command_buffer);

        barrier = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
            .srcStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            .srcAccessMask = VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
            .dstStageMask = VK_PIPELINE_STAGE_2_BOTTOM_OF_PIPE_BIT,
            .dstAccessMask = {},
            .oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .newLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = swapchain.get_image(image_index),
            .subresourceRange = {
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };

        dependency_info = {
            .sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
            .dependencyFlags = {},
            .imageMemoryBarrierCount = 1,
            .pImageMemoryBarriers = &barrier,
        };

        vkCmdPipelineBarrier2(command_buffer, &dependency_info);

        vk_result = vkEndCommandBuffer(command_buffer);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Failed to end command buffer: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferSubmitInfo buffer_submit_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
            .commandBuffer = command_buffer,
        };

        VkSemaphoreSubmitInfo wait_binary_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = image_acquire_semaphore,
            .stageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
        };

        VkSemaphoreSubmitInfo signal_binary_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = render_finished_semaphore,
            .stageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
        };

        VkSemaphoreSubmitInfo signal_timeline_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = timeline_semaphore,
            .value = frame_counter,
            .stageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT,
        };

        VkSemaphoreSubmitInfo wait_semaphores[] = {wait_binary_info};
        VkSemaphoreSubmitInfo signal_semaphores[] = {signal_binary_info, signal_timeline_info};

        VkSubmitInfo2 submit_info = {
            .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO_2,
            .waitSemaphoreInfoCount = 1,
            .pWaitSemaphoreInfos = wait_semaphores,
            .commandBufferInfoCount = 1,
            .pCommandBufferInfos = &buffer_submit_info,
            .signalSemaphoreInfoCount = 2,
            .pSignalSemaphoreInfos = signal_semaphores,
        };

        vk_result = vkQueueSubmit2(graphics_queue, 1, &submit_info, nullptr);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Failed to submit command buffer: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        VkSwapchainKHR swapchain_handle = swapchain.get_handle();

        VkPresentInfoKHR present_info = {
            .sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,
            .waitSemaphoreCount = 1,
            .pWaitSemaphores = &render_finished_semaphore,
            .swapchainCount = 1,
            .pSwapchains = &swapchain_handle,
            .pImageIndices = &image_index,
        };

        vk_result = vkQueuePresentKHR(graphics_queue, &present_info);

        if (vk_result == VK_ERROR_OUT_OF_DATE_KHR || vk_result == VK_SUBOPTIMAL_KHR)
        {
            cielim::utils::log::warn("Swapchain out of date or suboptimal for presentation");
        }
        else if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Failed to present swapchain image: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }
    }

    vkDeviceWaitIdle(vk_context.get_device());

    clean();

    SDL_Quit();

    return EXIT_SUCCESS;
}
