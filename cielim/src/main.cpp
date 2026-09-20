// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The program entry point. */

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

#include <vma/vk_mem_alloc.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_vulkan.h>

#include <SDL3/SDL_main.h> // This has to be the last SDL include

import cielim.camera;
import cielim.default_shape;
import cielim.error;
import cielim.math;
import cielim.mesh_elements;
import cielim.result;
import cielim.utils;
import cielim.vk;
import cielim.window;

static auto fatal_error(const cielim::window::Window* window, const std::string& message) -> void
{
    cielim::utils::log::critical("{}", message);

    if (window != nullptr)
        window->error_popup(message);
}

static auto run(const std::filesystem::path& base_path) -> int;

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

    if (volkInitialize() != VK_SUCCESS)
    {
        fatal_error(nullptr, "Volk failed to initialize!");
        return EXIT_FAILURE;
    }

    const char* base_path_raw = SDL_GetBasePath();

    if (base_path_raw == nullptr)
    {
        fatal_error(nullptr, fmt::format("Failed to find executable location: {}", SDL_GetError()));
        return EXIT_FAILURE;
    }

    // Path to the executable
    const std::filesystem::path base_path(base_path_raw);

    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS))
    {
        fatal_error(nullptr, fmt::format("Failed to initialize SDL3: {}", SDL_GetError()));
        return EXIT_FAILURE;
    }

    const int return_val = run(base_path);

    SDL_Quit();

    return return_val;
}

auto run(const std::filesystem::path& base_path) -> int
{
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

    cielim::vk::Context vk_context;

    if (auto const result = vk_context.init(); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::vk::Surface vk_surface;

    if (const auto result = vk_surface.init(vk_context, window); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::vk::Allocator vk_allocator;

    if (const auto result = vk_allocator.init(vk_context); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::vk::Swapchain vk_swapchain;

    if (const auto result = vk_swapchain.init(vk_context, vk_surface, window);
        !result.has_value() && result.error().errc != cielim::error::VkSwapchainError::NullExtent)
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::vk::FrameResources vk_frame_resources;

    if (const auto result = vk_frame_resources.init(vk_context, false); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    std::filesystem::path cube_shader_path = base_path / "content" / "shaders" / "cube.spv";

    cielim::vk::Shader cube_shader;

    if (const auto result = cube_shader.create(vk_context, cube_shader_path); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    std::vector<cielim::vk::ShaderStage> shader_stages = {
        {.stage_flag = VK_SHADER_STAGE_VERTEX_BIT, .shader_module = cube_shader, .entry_point = "VertMain"},
        {.stage_flag = VK_SHADER_STAGE_FRAGMENT_BIT, .shader_module = cube_shader, .entry_point = "FragMain"},
    };

    cielim::vk::Pipeline vk_render_pipeline;

    if (const auto result = vk_render_pipeline.create(
            vk_context, vk_swapchain, shader_stages, VK_SHADER_STAGE_VERTEX_BIT, sizeof(cielim::vk::SceneDataAddresses)
        );
        !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::vk::Renderer vk_renderer;

    if (const auto result = vk_renderer.init(vk_context); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::vk::MeshRegistry mesh_registry;

    constexpr uint32_t MESH_REGISTRY_BUFFER_SIZE = 65536;

    if (const auto result = mesh_registry.create(vk_context, vk_allocator, MESH_REGISTRY_BUFFER_SIZE);
        !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    if (const auto result = mesh_registry.upload(cielim::default_shape::vertices, cielim::default_shape::indices);
        !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::camera::Camera camera;

    camera.set_position({0.0f, 0.0f, 3.0f});
    camera.set_orientation({0.7071f, -0.7071f, 0.0f, 0.0f}); // Look directly down
    camera.set_fov_aspect(cielim::math::radians(60.0f), 1);

    cielim::math::Mat4 view_projection_matrix = camera.get_view_projection_matrix();

    cielim::vk::Buffer camera_info_buffer;

    if (const auto result = camera_info_buffer.create(
            vk_context,
            vk_allocator,
            sizeof(view_projection_matrix),
            VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
            VMA_ALLOCATION_CREATE_MAPPED_BIT | VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT
        );
        !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    if (const auto result = camera_info_buffer.direct_write(
            0, cielim::math::value_ptr(view_projection_matrix), sizeof(view_projection_matrix)
        );
        !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

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
                if (const auto result = vk_swapchain.recreate(vk_context, vk_surface, window);
                    !result.has_value() && result.error().errc != cielim::error::VkSwapchainError::NullExtent)
                {
                    fatal_error(&window, result.error().message());
                    return EXIT_FAILURE;
                }
                break;

            default: break;
            }
        }

        SDL_WindowFlags window_flags = SDL_GetWindowFlags(window.get_handle());

        if ((window_flags & SDL_WINDOW_MINIMIZED) != 0 || vk_swapchain.get_handle() == nullptr)
        {
            constexpr uint32_t STALL_DELAY = 8;
            SDL_Delay(STALL_DELAY); // Wait a bit to reduce CPU usage when not rendering
            continue;
        }

        const cielim::vk::SceneDataAddresses push_constants = {
            .vertex_info_address = mesh_registry.get_vertex_address(),
            .frame_data_address = camera_info_buffer.get_device_address(),
        };

        if (const auto result = vk_renderer.draw_frame(
                vk_context, vk_swapchain, vk_frame_resources, vk_render_pipeline, push_constants, mesh_registry
            );
            !result.has_value())
        {
            fatal_error(&window, result.error().message());
            return EXIT_FAILURE;
        }
    }

    vkDeviceWaitIdle(vk_context.get_device()); // Wait for device to finish whatever it's doing before quitting

    return EXIT_SUCCESS;
}
