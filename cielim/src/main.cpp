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
static VkShaderModule shader_module = VK_NULL_HANDLE; // Single shader for now
static VkPipelineLayout pipeline_layout = VK_NULL_HANDLE;
static VkPipeline graphics_pipeline = VK_NULL_HANDLE;
static std::vector<VkCommandPool> command_pools;
static std::vector<VkCommandBuffer> command_buffers;
static VkSemaphore timeline_semaphore = VK_NULL_HANDLE;
static std::vector<VkSemaphore> acquire_semaphores;
static std::vector<VkSemaphore> render_finished_semaphores;

// Clean up Vulkan resources
static auto clean() -> void
{
    for (const auto& semaphore : render_finished_semaphores)
    {
        if (semaphore != VK_NULL_HANDLE)
            vkDestroySemaphore(vk_context.get_device(), semaphore, nullptr);
    }

    for (const auto& semaphore : acquire_semaphores)
    {
        if (semaphore != VK_NULL_HANDLE)
            vkDestroySemaphore(vk_context.get_device(), semaphore, nullptr);
    }

    if (timeline_semaphore != VK_NULL_HANDLE)
        vkDestroySemaphore(vk_context.get_device(), timeline_semaphore, nullptr);

    for (const auto& pool : command_pools)
    {
        if (pool != VK_NULL_HANDLE)
            vkDestroyCommandPool(vk_context.get_device(), pool, nullptr);
    }

    if (graphics_pipeline != VK_NULL_HANDLE)
        vkDestroyPipeline(vk_context.get_device(), graphics_pipeline, nullptr);

    if (pipeline_layout != VK_NULL_HANDLE)
        vkDestroyPipelineLayout(vk_context.get_device(), pipeline_layout, nullptr);

    if (shader_module != VK_NULL_HANDLE)
        vkDestroyShaderModule(vk_context.get_device(), shader_module, nullptr);
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

    auto triangle_shader = cielim::utils::file::read_file32(triangle_shader_path);

    if (!triangle_shader.has_value())
    {
        fatal_error(
            &window,
            fmt::format(
                "Shader {} could not be opened: {}", triangle_shader_path.string(), triangle_shader.error().message()
            )
        );
        clean();
        return EXIT_FAILURE;
    }

    VkShaderModuleCreateInfo shader_module_create_info = {
        .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = triangle_shader.value().size() * sizeof(uint32_t),
        .pCode = triangle_shader.value().data(),
    };

    vk_result = vkCreateShaderModule(vk_context.get_device(), &shader_module_create_info, nullptr, &shader_module);

    if (vk_result != VK_SUCCESS)
    {
        fatal_error(&window, fmt::format("Shader module could not be created: {}", string_VkResult(vk_result)));
        clean();
        return EXIT_FAILURE;
    }

    VkPipelineShaderStageCreateInfo vertex_stage_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_VERTEX_BIT,
        .module = shader_module,
        .pName = "VertMain",
    };

    VkPipelineShaderStageCreateInfo frag_stage_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_FRAGMENT_BIT,
        .module = shader_module,
        .pName = "FragMain",
    };

    VkPipelineShaderStageCreateInfo shader_stages[] = {vertex_stage_info, frag_stage_info};

    // Empty for now because of shader hard-coding vertex buffer
    VkPipelineVertexInputStateCreateInfo vertex_input_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
    };

    VkPipelineInputAssemblyStateCreateInfo input_assembly_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
        .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP,
    };

    VkPipelineViewportStateCreateInfo viewport_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
        .viewportCount = 1,
        .scissorCount = 1,
    };

    VkPipelineRasterizationStateCreateInfo rasterization_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
        .depthClampEnable = VK_FALSE,
        .rasterizerDiscardEnable = VK_FALSE,
        .polygonMode = VK_POLYGON_MODE_FILL,
        .cullMode = VK_CULL_MODE_BACK_BIT,
        .frontFace = VK_FRONT_FACE_CLOCKWISE,
        .depthBiasEnable = VK_FALSE,
        .lineWidth = 1.0f,
    };

    VkPipelineMultisampleStateCreateInfo multisample_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
        .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT,
        .sampleShadingEnable = VK_FALSE,
    };

    VkPipelineColorBlendAttachmentState color_blend_attachment_state = {
        .blendEnable = VK_TRUE,
        .srcColorBlendFactor = VK_BLEND_FACTOR_SRC_ALPHA,
        .dstColorBlendFactor = VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA,
        .colorBlendOp = VK_BLEND_OP_ADD,
        .srcAlphaBlendFactor = VK_BLEND_FACTOR_ONE,
        .dstAlphaBlendFactor = VK_BLEND_FACTOR_ZERO,
        .alphaBlendOp = VK_BLEND_OP_ADD,
        .colorWriteMask
        = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT | VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT,
    };

    VkPipelineColorBlendStateCreateInfo color_blend_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
        .logicOpEnable = VK_FALSE,
        .logicOp = VK_LOGIC_OP_COPY,
        .attachmentCount = 1,
        .pAttachments = &color_blend_attachment_state,
    };

    // This is empty because no uniforms are used yet
    VkPipelineLayoutCreateInfo layout_create_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 0,
        .pushConstantRangeCount = 0,
    };

    vk_result = vkCreatePipelineLayout(vk_context.get_device(), &layout_create_info, nullptr, &pipeline_layout);

    if (vk_result != VK_SUCCESS)
    {
        fatal_error(&window, fmt::format("Pipeline layout could not be created: {}", string_VkResult(vk_result)));
        clean();
        return EXIT_FAILURE;
    }

    std::vector<VkDynamicState> dynamic_states = {VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR};

    VkPipelineDynamicStateCreateInfo dynamic_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
        .dynamicStateCount = static_cast<uint32_t>(dynamic_states.size()),
        .pDynamicStates = dynamic_states.data(),
    };

    VkFormat req_format = swapchain.get_format();

    VkPipelineRenderingCreateInfo pipeline_rendering_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO,
        .colorAttachmentCount = 1,
        .pColorAttachmentFormats = &req_format,
    };

    VkGraphicsPipelineCreateInfo pipeline_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .pNext = &pipeline_rendering_state,
        .stageCount = 2,
        .pStages = shader_stages,
        .pVertexInputState = &vertex_input_state,
        .pInputAssemblyState = &input_assembly_state,
        .pViewportState = &viewport_state,
        .pRasterizationState = &rasterization_state,
        .pMultisampleState = &multisample_state,
        .pColorBlendState = &color_blend_state,
        .pDynamicState = &dynamic_state,
        .layout = pipeline_layout,
        .renderPass = nullptr,
    };

    vk_result
        = vkCreateGraphicsPipelines(vk_context.get_device(), nullptr, 1, &pipeline_info, nullptr, &graphics_pipeline);

    if (vk_result != VK_SUCCESS)
    {
        fatal_error(&window, fmt::format("Graphics pipeline could not be created: {}", string_VkResult(vk_result)));
        clean();
        return EXIT_FAILURE;
    }

    constexpr uint32_t MAX_FRAMES_IN_FLIGHT = 2;

    command_pools.resize(MAX_FRAMES_IN_FLIGHT);
    command_buffers.resize(MAX_FRAMES_IN_FLIGHT);

    for (uint32_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++)
    {
        VkCommandPoolCreateInfo command_pool_create_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
            .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
            .queueFamilyIndex = vk_context.get_queue(),
        };

        vk_result = vkCreateCommandPool(vk_context.get_device(), &command_pool_create_info, nullptr, &command_pools[i]);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Command pool could not be created: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferAllocateInfo command_buffer_allocate_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
            .commandPool = command_pools[i],
            .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
            .commandBufferCount = 1,
        };

        vk_result
            = vkAllocateCommandBuffers(vk_context.get_device(), &command_buffer_allocate_info, &command_buffers[i]);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Command buffer could not be allocated: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }
    }

    VkSemaphoreTypeCreateInfo timeline_semaphore_type_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,
        .semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE,
        .initialValue = 0,
    };

    VkSemaphoreCreateInfo timeline_semaphore_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
        .pNext = &timeline_semaphore_type_info,
    };

    vkCreateSemaphore(vk_context.get_device(), &timeline_semaphore_info, nullptr, &timeline_semaphore);

    VkSemaphoreCreateInfo binary_semaphore_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
    };

    acquire_semaphores.resize(MAX_FRAMES_IN_FLIGHT);

    for (auto& semaphore : acquire_semaphores)
    {
        vk_result = vkCreateSemaphore(
            vk_context.get_device(), &binary_semaphore_info, nullptr, &semaphore
        ); // One per frame-in-flight

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Binary semaphore failed to be created: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }
    }

    render_finished_semaphores.resize(swapchain.get_num_images());

    for (auto& semaphore : render_finished_semaphores)
    {
        vk_result = vkCreateSemaphore(
            vk_context.get_device(), &binary_semaphore_info, nullptr, &semaphore
        ); // One per swapchain image

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Binary semaphore failed to be created: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }
    }

    VkQueue graphics_queue;
    vkGetDeviceQueue(vk_context.get_device(), vk_context.get_queue(), 0, &graphics_queue);

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

                // Per-image semaphores need to be recreated as the number of swapchain images may have changed

                for (const auto& semaphore : render_finished_semaphores)
                {
                    if (semaphore != nullptr)
                        vkDestroySemaphore(vk_context.get_device(), semaphore, nullptr);
                }

                render_finished_semaphores.assign(swapchain.get_num_images(), nullptr);

                for (auto& semaphore : render_finished_semaphores)
                {
                    vk_result = vkCreateSemaphore(vk_context.get_device(), &binary_semaphore_info, nullptr, &semaphore);

                    if (vk_result != VK_SUCCESS)
                    {
                        fatal_error(
                            &window, fmt::format("Failed to create binary semaphore: {}", string_VkResult(vk_result))
                        );
                        clean();
                        return EXIT_FAILURE;
                    }
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

        const uint32_t frame_index = (frame_counter - 1) % MAX_FRAMES_IN_FLIGHT;

        if (frame_counter > MAX_FRAMES_IN_FLIGHT)
        {
            uint64_t wait_value = frame_counter - MAX_FRAMES_IN_FLIGHT;

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

        vk_result = vkAcquireNextImageKHR(
            vk_context.get_device(),
            swapchain.get_handle(),
            UINT64_MAX,
            acquire_semaphores[frame_index],
            nullptr,
            &image_index
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

        vk_result = vkResetCommandPool(vk_context.get_device(), command_pools[frame_index], 0);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Failed to reset command pool: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferBeginInfo begin_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        };

        vk_result = vkBeginCommandBuffer(command_buffers[frame_index], &begin_info);

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

        vkCmdPipelineBarrier2(command_buffers[frame_index], &dependency_info);

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

        vkCmdBeginRendering(command_buffers[frame_index], &rendering_info);

        vkCmdBindPipeline(command_buffers[frame_index], VK_PIPELINE_BIND_POINT_GRAPHICS, graphics_pipeline);

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

        vkCmdSetViewport(command_buffers[frame_index], 0, 1, &viewport);
        vkCmdSetScissor(command_buffers[frame_index], 0, 1, &scissor);

        vkCmdDraw(command_buffers[frame_index], 3, 1, 0, 0);

        vkCmdEndRendering(command_buffers[frame_index]);

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

        vkCmdPipelineBarrier2(command_buffers[frame_index], &dependency_info);

        vk_result = vkEndCommandBuffer(command_buffers[frame_index]);

        if (vk_result != VK_SUCCESS)
        {
            fatal_error(&window, fmt::format("Failed to end command buffer: {}", string_VkResult(vk_result)));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferSubmitInfo buffer_submit_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
            .commandBuffer = command_buffers[frame_index],
        };

        VkSemaphoreSubmitInfo wait_binary_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = acquire_semaphores[frame_index],
            .stageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
        };

        VkSemaphoreSubmitInfo signal_binary_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = render_finished_semaphores[image_index],
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
            .pWaitSemaphores = &render_finished_semaphores[image_index],
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
