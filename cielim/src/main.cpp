// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The program entry point. */

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <utility>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

#include <vma/vk_mem_alloc.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_vulkan.h>

#include <SDL3/SDL_main.h> // This has to be the last SDL include

import cielim.error;
import cielim.gpu.vk;
import cielim.math;
import cielim.mesh;
import cielim.platform;
import cielim.render.vk;
import cielim.result;
import cielim.snapshot;
import cielim.utils;

static auto fatal_error(const cielim::platform::Window* window, const std::string& message) -> void
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

    auto window = cielim::platform::Window();

    auto win_result
        = window.create_window("cielim", WINDOW_WIDTH, WINDOW_HEIGHT, SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE);

    if (!win_result.has_value())
    {
        fatal_error(nullptr, win_result.error().message());
        return EXIT_FAILURE;
    }

    cielim::gpu::vk::Context vk_context;

    if (auto const result = vk_context.init(); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::gpu::vk::Allocator vk_allocator;

    if (const auto result = vk_allocator.init(vk_context); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::render::vk::Surface vk_surface;

    if (const auto result = vk_surface.init(vk_context, window); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::render::vk::Swapchain vk_swapchain;

    if (const auto result = vk_swapchain.init(vk_context, vk_surface, window);
        !result.has_value() && result.error().errc != cielim::error::VkSwapchainError::NullExtent)
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::render::vk::FrameResources vk_frame_resources;

    if (const auto result = vk_frame_resources.init(vk_context, false); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    const uint32_t frames_in_flight = vk_frame_resources.get_frames_in_flight();

    std::filesystem::path cube_shader_path = base_path / "content" / "shaders" / "cube.spv";

    cielim::render::vk::Shader cube_shader;

    if (const auto result = cube_shader.create(vk_context, cube_shader_path); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    std::vector<cielim::render::vk::ShaderStage> shader_stages = {
        {.stage_flag = VK_SHADER_STAGE_VERTEX_BIT, .shader_module = cube_shader, .entry_point = "VertMain"},
        {.stage_flag = VK_SHADER_STAGE_FRAGMENT_BIT, .shader_module = cube_shader, .entry_point = "FragMain"},
    };

    cielim::render::vk::Pipeline vk_render_pipeline;

    if (const auto result = vk_render_pipeline.create(
            vk_context,
            vk_swapchain,
            shader_stages,
            VK_SHADER_STAGE_VERTEX_BIT,
            sizeof(cielim::render::vk::SceneDataAddresses)
        );
        !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::render::vk::FrameCounter vk_frame_counter;

    if (const auto result = vk_frame_counter.init(vk_context); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::render::vk::MeshRegistry mesh_registry;

    constexpr uint32_t MESH_REGISTRY_BUFFER_SIZE = 20971520;

    if (const auto result = mesh_registry.create(vk_context, vk_allocator, MESH_REGISTRY_BUFFER_SIZE);
        !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    std::filesystem::path shape_path = base_path / "content" / "meshes" / "vesta.glb";

    auto shape_result = cielim::mesh::Loader::load_mesh(shape_path);

    if (!shape_result.has_value())
    {
        fatal_error(&window, shape_result.error().message());
        return EXIT_FAILURE;
    }

    auto [vertices, indices] = std::move(shape_result).value();

    if (const auto result = mesh_registry.upload(vertices, indices); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    cielim::snapshot::Camera camera;

    float camera_yaw = 0.0f;
    float camera_pitch = 0.0f;

    camera.set_position({0.0f, -3.0f, 0.0f});
    camera.set_orientation(camera_yaw, camera_pitch, 0.0f);

    auto view_width = static_cast<float>(vk_swapchain.get_extent().width);
    auto view_height = static_cast<float>(vk_swapchain.get_extent().height);

    camera.set_fov_aspect(cielim::math::radians(60.0f), view_width / view_height);

    cielim::render::vk::SceneView view;

    if (const auto result = view.create(vk_context, vk_allocator, frames_in_flight); !result.has_value())
    {
        fatal_error(&window, result.error().message());
        return EXIT_FAILURE;
    }

    bool mouse_capture = true;

    // Capture the mouse in the window
    SDL_SetWindowRelativeMouseMode(window.get_handle(), mouse_capture);

    uint64_t previous_time_ms = SDL_GetTicks();
    float delta_time = 0.0f;

    bool is_running = true;

    while (is_running)
    {
        bool skip_frame = false;

        // Check for window events

        float mouse_x = 0.0f;
        float mouse_y = 0.0f;

        SDL_Event event;
        while (SDL_PollEvent(&event))
        {
            switch (event.type)
            {
            case SDL_EVENT_QUIT: is_running = false; break;

            case SDL_EVENT_WINDOW_MINIMIZED: skip_frame = true; break;

            case SDL_EVENT_WINDOW_RESIZED:
                if (const auto result = vk_swapchain.recreate(vk_context, vk_surface, window);
                    !result.has_value() && result.error().errc != cielim::error::VkSwapchainError::NullExtent)
                {
                    fatal_error(&window, result.error().message());
                    return EXIT_FAILURE;
                }

                view_width = static_cast<float>(vk_swapchain.get_extent().width);
                view_height = static_cast<float>(vk_swapchain.get_extent().height);

                camera.set_fov_aspect(cielim::math::radians(60.0f), view_width / view_height);
                break;

            case SDL_EVENT_KEY_DOWN:
                if (event.key.scancode == SDL_SCANCODE_ESCAPE)
                {
                    mouse_capture = !mouse_capture;
                    SDL_SetWindowRelativeMouseMode(window.get_handle(), mouse_capture);
                }
                break;

            case SDL_EVENT_MOUSE_MOTION:
                if (mouse_capture)
                {
                    mouse_x = event.motion.xrel;
                    mouse_y = event.motion.yrel;
                }
                break;

            default: break;
            }
        }

        if (skip_frame || vk_swapchain.get_handle() == nullptr)
        {
            constexpr uint32_t STALL_DELAY = 8;
            SDL_Delay(STALL_DELAY); // Wait a bit to reduce CPU usage when not rendering
            continue;
        }

        // Check for user keyboard input

        cielim::math::Vec3 move_direction(0.0f, 0.0f, 0.0f);

        int keys;
        const bool* key_state = SDL_GetKeyboardState(&keys);

        if (key_state[SDL_SCANCODE_W])
        {
            move_direction += camera.get_look_at();
        }
        if (key_state[SDL_SCANCODE_S])
        {
            move_direction -= camera.get_look_at();
        }
        if (key_state[SDL_SCANCODE_D])
        {
            move_direction += cielim::math::cross(camera.get_look_at(), camera.get_up());
        }
        if (key_state[SDL_SCANCODE_A])
        {
            move_direction -= cielim::math::cross(camera.get_look_at(), camera.get_up());
        }
        if (key_state[SDL_SCANCODE_LSHIFT])
        {
            move_direction += camera.get_up();
        }
        if (key_state[SDL_SCANCODE_LCTRL])
        {
            move_direction -= camera.get_up();
        }

        // Update camera

        uint64_t current_time_ms = SDL_GetTicks();
        constexpr float SECOND_IN_MS = 1000.0f;
        delta_time = static_cast<float>(current_time_ms - previous_time_ms) / SECOND_IN_MS;
        previous_time_ms = current_time_ms;

        constexpr float CAMERA_SPEED = 100.0f;

        move_direction *= delta_time * CAMERA_SPEED;

        camera.move(move_direction);

        constexpr float MOUSE_SENSITIVITY = 0.005f;
        constexpr float PITCH_LIMIT = cielim::math::radians(90.0f);

        camera_yaw += -mouse_x * MOUSE_SENSITIVITY;
        camera_pitch = std::clamp(camera_pitch + (-mouse_y * MOUSE_SENSITIVITY), -PITCH_LIMIT, PITCH_LIMIT);

        camera.set_orientation(camera_yaw, camera_pitch, 0.0f);

        // Render the scene view

        const uint32_t frame_index = vk_frame_counter.get_current_index(frames_in_flight);

        if (const auto result = view.update(camera, frame_index); !result.has_value())
        {
            fatal_error(&window, result.error().message());
            return EXIT_FAILURE;
        }

        const auto camera_info_address_result = view.get_camera_info_address(frame_index);

        if (!camera_info_address_result.has_value())
        {
            fatal_error(&window, camera_info_address_result.error().message());
            return EXIT_FAILURE;
        }

        const cielim::render::vk::SceneDataAddresses push_constants = {
            .vertex_info_address = mesh_registry.get_vertex_address(),
            .frame_data_address = camera_info_address_result.value(),
        };

        if (const auto result = cielim::render::vk::Recorder::draw_frame(
                vk_context,
                vk_swapchain,
                vk_frame_resources,
                vk_frame_counter,
                vk_render_pipeline,
                push_constants,
                mesh_registry
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
