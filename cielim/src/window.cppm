// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* The window holds a window object and exposes functions to get system windowing properties. */

module;

#include <expected>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include <volk/volk.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_vulkan.h>

export module cielim.window;

import cielim.error;

export namespace cielim::window
{

class Window
{
public:
    Window() = default;

    ~Window()
    {
        if (this->window_ != nullptr)
            SDL_DestroyWindow(this->window_);
    }

    /**
     * @brief Creates a window with SDL3.
     * @param name The name to be displayed at the top of the window.
     * @param width The width for the window to be in pixels.
     * @param height The height for the window to be in pixels.
     * @param flags Bit string containing window flags.
     * @return Void on success, error code on failure.
     */
    [[nodiscard]] auto
    create_window(const std::string_view name, const uint16_t width, const uint16_t height, const uint64_t flags)
        -> std::expected<void, cielim::error::DetailedError>
    {
        this->window_ = SDL_CreateWindow(std::string(name).c_str(), width, height, flags);

        if (this->window_ == nullptr)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::WindowError::WindowCreateError),
                .detail = SDL_GetError(),
            };

            return std::unexpected(error);
        }

        return {};
    }

    // ----- Vulkan interop functions -----

    /**
     * @brief Gets a list of c strings for required Vulkan instance extensions.
     * @return The list of required instance extensions in success, error code on failure.
     */
    [[nodiscard]] static auto vk_get_extensions()
        -> std::expected<std::vector<const char*>, cielim::error::DetailedError>
    {
        uint32_t sdl_extension_count = 0;
        const char* const* sdl_extensions = SDL_Vulkan_GetInstanceExtensions(&sdl_extension_count);

        if (sdl_extensions == nullptr)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::WindowError::ExtensionEnumerateError),
                .detail = SDL_GetError(),
            };

            return std::unexpected(error);
        }

        if (sdl_extension_count == 0)
            return {};

        return std::vector<const char*>(sdl_extensions, sdl_extensions + sdl_extension_count);
    }

    /**
     * @brief Gets whether presentation is supported for the queue family index in the physical device.
     * @param instance The current Vulkan instance.
     * @param physical_device The physical device being queried.
     * @param queue_family_index The index for the queue family in the physical device being queried.
     * @return Void if supported, error code otherwise.
     */
    [[nodiscard]] static auto vk_get_presentation_support(
        const VkInstance instance, const VkPhysicalDevice physical_device, const uint32_t queue_family_index
    ) -> std::expected<void, cielim::error::DetailedError>
    {
        const bool supported = SDL_Vulkan_GetPresentationSupport(instance, physical_device, queue_family_index);

        if (!supported)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::WindowError::PresentationUnsupported),
                .detail = "",
            };

            return std::unexpected(error);
        }

        return {};
    }

    /**
     * @bief Creates a Vulkan surface object.
     * @param instance The current Vulkan instance.
     * @param surface Pointer to the surface object to be created.
     * @return Void on success, error code on failure.
     */
    [[nodiscard]] auto vk_create_surface(const VkInstance instance, VkSurfaceKHR* surface) const
        -> std::expected<void, cielim::error::DetailedError>
    {
        const bool created = SDL_Vulkan_CreateSurface(this->window_, instance, nullptr, surface);

        if (!created)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::WindowError::SurfaceCreateError),
                .detail = SDL_GetError(),
            };

            return std::unexpected(error);
        }

        return {};
    }

private:
    SDL_Window* window_ = nullptr;
    int width_ = 0;
    int height_ = 0;
};

} // namespace cielim::window
