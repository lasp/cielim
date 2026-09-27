// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A surface is a platform-independent bridge between Vulkan and a presentation window. A surface is required
 * to create a swapchain that presents to the window. */

module;

#include <string>

#include <volk/volk.h>

export module cielim.render.vk:surface;

import cielim.error;
import cielim.gpu.vk;
import cielim.handle;
import cielim.platform;
import cielim.result;

export namespace cielim::render::vk
{

class Surface
{
public:
    // Delete copy constructors

    Surface(const Surface&) = delete;
    auto operator=(const Surface&) -> Surface& = delete;

    // Use default move constructor, delete move assignment

    Surface(Surface&&) = default;
    auto operator=(Surface&&) -> Surface& = delete;

    ~Surface()
    {
        if (this->surface_)
            vkDestroySurfaceKHR(this->vk_instance_handle_, this->surface_.get(), nullptr);
    }

    /**
     * @brief Creates the Vulkan surface for the given window.
     * @param context The Vulkan context, must have been initialized for window presentation.
     * @param window The window for which to create the surface.
     * @return The surface on success, error code on failure.
     */
    static auto create(const gpu::vk::Context& context, const platform::Window& window) -> Result<Surface>
    {
        Surface surface;

        surface.vk_instance_handle_ = context.get_instance(); // This is specifically a non-owning (borrow) handle

        if (const auto result = window.vk_create_surface(surface.vk_instance_handle_, surface.surface_.put());
            !result.has_value())
            return result.propagate();

        return surface;
    }

    [[nodiscard]] auto get_handle() const -> VkSurfaceKHR { return this->surface_.get(); }

private:
    Surface() = default;

    // Non-owning handle for the Vulkan instance
    VkInstance vk_instance_handle_ = nullptr;

    // Vulkan surface, corresponds to the window this was created for
    UniqueHandle<VkSurfaceKHR> surface_;
};

} // namespace cielim::render::vk
