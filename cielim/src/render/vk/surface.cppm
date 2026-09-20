// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A surface is a platform-independent bridge between Vulkan and a presentation window. A surface is required
 * to create a swapchain that presents to the window. */

module;

#include <volk/volk.h>

export module cielim.render.vk:surface;

import cielim.gpu.vk;
import cielim.handle;
import cielim.platform;
import cielim.result;

export namespace cielim::render::vk
{

class Surface
{
public:
    Surface() = default;

    // Delete copy constructors

    Surface(const Surface&) = delete;
    auto operator=(const Surface&) -> Surface& = delete;

    // Use default move constructors

    Surface(Surface&&) = default;
    auto operator=(Surface&&) -> Surface& = default;

    ~Surface()
    {
        if (this->surface_)
            vkDestroySurfaceKHR(this->vk_instance_handle_, this->surface_.get(), nullptr);
    }

    /**
     * @brief Creates the Vulkan surface for the given window.
     * @param context The Vulkan context, must have been initialized for window presentation.
     * @param window The window for which to create the surface.
     * @return Void on success, error code on failure.
     */
    auto init(const gpu::vk::Context& context, const platform::Window& window) -> Result<void>
    {
        this->vk_instance_handle_ = context.get_instance(); // This is specifically a non-owning (borrow) handle

        if (const auto result = window.vk_create_surface(this->vk_instance_handle_, this->surface_.put());
            !result.has_value())
            return result.propagate();

        return {};
    }

    [[nodiscard]] auto get_handle() const -> VkSurfaceKHR { return this->surface_.get(); }

private:
    // Non-owning handle for the Vulkan instance
    VkInstance vk_instance_handle_ = nullptr;

    // Vulkan surface, corresponds to the window this was created for
    UniqueHandle<VkSurfaceKHR> surface_;
};

} // namespace cielim::render::vk
