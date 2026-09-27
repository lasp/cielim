// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* The window holds a window object and exposes functions to get system windowing properties. */

module;

#include <cstdint>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <volk/volk.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_vulkan.h>

export module cielim.platform;

import cielim.error;
import cielim.handle;
import cielim.result;
import cielim.utils;

export namespace cielim::platform
{

class Window
{
public:
    // Delete copy constructors

    Window(const Window&) = delete;
    auto operator=(const Window&) -> Window& = delete;

    // Use default move constructor, delete move assignment

    Window(Window&&) = default;
    auto operator=(Window&&) -> Window& = delete;

    ~Window()
    {
        if (this->window_)
            SDL_DestroyWindow(this->window_.get());
    }

    /**
     * @brief Creates a window with SDL3.
     * @param name The name to be displayed at the top of the window.
     * @param width The width for the window to be in pixels.
     * @param height The height for the window to be in pixels.
     * @param flags Bit string containing window flags.
     * @return The window on success, error code on failure.
     */
    static auto create(const std::string_view name, const uint16_t width, const uint16_t height, const uint64_t flags)
        -> Result<Window>
    {
        Window window;

        *window.window_.put() = SDL_CreateWindow(std::string(name).c_str(), width, height, flags);

        if (!window.window_)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::WindowError::WindowCreateError),
                    .detail = SDL_GetError(),
                }
            );
        }

        utils::log::info("Created window ({}x{})", width, height);

        return window;
    }

    /**
     * @brief Displays an error message popup window.
     * @details This should only ever be used for fatal errors as the popup window will stall the thread.
     * @param message The error message to display.
     */
    auto error_popup(const std::string& message) const -> void
    {
        // Ignore any errors that may occur displaying this popup because the program is ending anyways
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Cielim - Fatal Error", message.c_str(), this->window_.get());
    }

    // ----- Vulkan interop functions -----

    /**
     * @brief Gets a list of c strings for required Vulkan instance extensions.
     * @return The list of required instance extensions in success, error code on failure.
     */
    static auto vk_get_extensions() -> Result<std::vector<const char*>>
    {
        uint32_t sdl_extension_count = 0;
        const char* const* sdl_extensions = SDL_Vulkan_GetInstanceExtensions(&sdl_extension_count);

        if (sdl_extensions == nullptr)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::WindowError::ExtensionEnumerateError),
                    .detail = SDL_GetError(),
                }
            );
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
    static auto vk_get_presentation_support(
        const VkInstance instance, const VkPhysicalDevice physical_device, const uint32_t queue_family_index
    ) -> Result<void>
    {
        const bool supported = SDL_Vulkan_GetPresentationSupport(instance, physical_device, queue_family_index);

        if (!supported)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::WindowError::PresentationUnsupported),
                    .detail = "",
                }
            );
        }

        return {};
    }

    /**
     * @bief Creates a Vulkan surface object.
     * @param instance The current Vulkan instance.
     * @param surface Pointer to the Vulkan surface object to be created.
     * @return Void on success, error code on failure.
     */
    auto vk_create_surface(const VkInstance instance, VkSurfaceKHR* surface) const -> Result<void>
    {
        const bool created = SDL_Vulkan_CreateSurface(this->window_.get(), instance, nullptr, surface);

        if (!created)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::WindowError::SurfaceCreateError),
                    .detail = SDL_GetError(),
                }
            );
        }

        return {};
    }

    // Returns the window handle
    [[nodiscard]] auto get_handle() const -> SDL_Window* { return this->window_.get(); }

    // Returns window size on success, error code on failure
    auto get_size() const -> Result<std::pair<int, int>>
    {
        int width = 0;
        int height = 0;

        const bool got_size = SDL_GetWindowSizeInPixels(this->window_.get(), &width, &height);

        if (!got_size)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::WindowError::GetSizeError),
                    .detail = SDL_GetError(),
                }
            );
        }

        return std::make_pair(width, height);
    }

private:
    Window() = default;

    UniqueHandle<SDL_Window*> window_;
    uint8_t id_ = 0; // Not used right now, will be if we have more than one window
};

} // namespace cielim::platform
