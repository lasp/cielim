// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The swapchain is used to present rendered images to the window via its corresponding Vulkan surface object.
 */

module;

#include <algorithm>
#include <expected>
#include <string>
#include <utility>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.vk:swapchain;

import cielim.error;
import cielim.utils;
import cielim.window;
import :context;

export namespace cielim::vk::swapchain
{

class Swapchain
{
public:
    Swapchain() = default;

    ~Swapchain()
    {
        for (const auto& view : this->swapchain_views_)
        {
            if (view != nullptr)
                vkDestroyImageView(vk_device_handle_, view, nullptr);
        }

        if (this->vk_swapchain_ != nullptr)
            vkDestroySwapchainKHR(vk_device_handle_, this->vk_swapchain_, nullptr);
    }

    /**
     * @brief Initializes the swapchain for the Vulkan context and window.
     * @param context The Vulkan context.
     * @param window The window to which the swapchain is connected.
     * @return Void on success, error code on failure.
     */
    [[nodiscard]] auto init(const context::Context& context, window::Window& window)
        -> std::expected<void, error::DetailedError>
    {
        this->vk_device_handle_ = context.get_device(); // This is specifically a non-owning (borrow) handle

        // Get surface capabilities

        VkSurfaceCapabilitiesKHR surface_capabilities;

        if (const auto result = vkGetPhysicalDeviceSurfaceCapabilitiesKHR(
                context.get_physical_device(), context.get_surface(), &surface_capabilities
            );
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkSwapchainError::SurfaceCapabilitiesError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        // Get surface formats

        uint32_t surface_format_count = 0;
        vkGetPhysicalDeviceSurfaceFormatsKHR(
            context.get_physical_device(), context.get_surface(), &surface_format_count, nullptr
        );

        std::vector<VkSurfaceFormatKHR> surface_formats(surface_format_count);

        if (const auto result = vkGetPhysicalDeviceSurfaceFormatsKHR(
                context.get_physical_device(), context.get_surface(), &surface_format_count, surface_formats.data()
            );
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkSwapchainError::SurfaceFormatsError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        // Check that the required formats are supported (standard sRGB)

        this->format_ = VK_FORMAT_B8G8R8A8_SRGB;
        this->color_space_ = VK_COLOR_SPACE_SRGB_NONLINEAR_KHR; // The color space corresponds to the format

        bool found_format = false;
        for (const auto& [format, color_space] : surface_formats)
        {
            if (format == this->format_ && color_space == this->color_space_)
                found_format = true;
        }

        if (!found_format)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkSwapchainError::MissingSurfaceFormats),
                .detail = "",
            };

            return std::unexpected(error);
        }

        // We'll skip querying present modes and use VK_PRESENT_MODE_FIFO_KHR which is always present
        VkPresentModeKHR req_present_mode = VK_PRESENT_MODE_FIFO_KHR;

        // Set the size of the swapchain images

        // Max value indicate the window manager wants us to choose swapchain image extent explicitly
        if (surface_capabilities.currentExtent.width == std::numeric_limits<uint32_t>::max())
        {
            auto window_size = window.get_size();

            if (!window_size.has_value())
                return std::unexpected(window_size.error());

            this->extent_.width = window_size.value().first;
            this->extent_.height = window_size.value().second;

            this->extent_.width = std::clamp<uint32_t>(
                this->extent_.width,
                surface_capabilities.minImageExtent.width,
                surface_capabilities.maxImageExtent.width
            );

            this->extent_.height = std::clamp<uint32_t>(
                this->extent_.height,
                surface_capabilities.minImageExtent.height,
                surface_capabilities.maxImageExtent.height
            );
        }
        else
        {
            this->extent_ = surface_capabilities.currentExtent;
        }

        // Null extent is not a valid swapchain size, this is non-fatal though and should be handled
        if (this->extent_.width == 0 || this->extent_.height == 0)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkSwapchainError::NullExtent),
                .detail = "",
            };

            return std::unexpected(error);
        }

        // Minimum number of images the swapchain should contain, dictated by the window manager
        uint32_t min_image_count = surface_capabilities.minImageCount;

        // Don't know how this would happen but might as well check
        if (surface_capabilities.maxImageCount > 0 && min_image_count > surface_capabilities.maxImageCount)
            min_image_count = surface_capabilities.maxImageCount;

        // Create the swapchain

        VkSwapchainCreateInfoKHR swapchain_create_info = {
            .sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,
            .surface = context.get_surface(),
            .minImageCount = min_image_count,
            .imageFormat = this->format_,
            .imageColorSpace = this->color_space_,
            .imageExtent = this->extent_,
            .imageArrayLayers = 1,
            .imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
            .preTransform = VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,
            .compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
            .presentMode = req_present_mode,
        };

        if (const auto result
            = vkCreateSwapchainKHR(context.get_device(), &swapchain_create_info, nullptr, &this->vk_swapchain_);
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkSwapchainError::SwapchainCreateError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        // Get all of the images from the swapchain and map to our list of VkImages

        uint32_t image_count = 0;
        vkGetSwapchainImagesKHR(context.get_device(), this->vk_swapchain_, &image_count, nullptr);

        if (image_count > 0)
        {
            this->swapchain_images_.resize(image_count);
            this->swapchain_views_.resize(image_count);
        }

        if (const auto result = vkGetSwapchainImagesKHR(
                context.get_device(), this->vk_swapchain_, &image_count, this->swapchain_images_.data()
            );
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkSwapchainError::GetImageError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        // Create image view for each image in the swapchain

        VkImageViewCreateInfo view_create_info = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
            .viewType = VK_IMAGE_VIEW_TYPE_2D,
            .format = this->format_,
            .subresourceRange = {.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT, .levelCount = 1, .layerCount = 1},
        };

        for (int i = 0; auto& image : this->swapchain_images_)
        {
            view_create_info.image = image;

            if (const auto result
                = vkCreateImageView(context.get_device(), &view_create_info, nullptr, &this->swapchain_views_[i]);
                result != VK_SUCCESS)
            {
                error::DetailedError error = {
                    .errc = make_error_code(error::VkSwapchainError::ViewCreateError),
                    .detail = string_VkResult(result),
                };

                return std::unexpected(error);
            }

            i++;
        }

        return {};
    }

    [[nodiscard]] auto get_handle() const -> VkSwapchainKHR { return this->vk_swapchain_; }
    [[nodiscard]] auto get_extent() const -> VkExtent2D { return this->extent_; }
    [[nodiscard]] auto get_num_images() const -> uint32_t { return this->swapchain_images_.size(); }
    [[nodiscard]] auto get_image(const uint32_t index) const -> VkImage { return this->swapchain_images_[index]; }
    [[nodiscard]] auto get_view(const uint32_t index) const -> VkImageView { return this->swapchain_views_[index]; }
    [[nodiscard]] auto get_format() const -> VkFormat { return this->format_; }
    [[nodiscard]] auto get_color_space() const -> VkColorSpaceKHR { return this->color_space_; }

private:
    // Non-owning handle for the Vulkan logical device
    VkDevice vk_device_handle_ = nullptr;

    // Vulkan swapchain
    VkSwapchainKHR vk_swapchain_ = nullptr;

    // Size of the swapchain
    VkExtent2D extent_{};

    // List of available images in the swapchain
    std::vector<VkImage> swapchain_images_;

    // List of views corresponding one-to-one to available images in the swapchain
    std::vector<VkImageView> swapchain_views_;

    VkFormat format_ = VK_FORMAT_MAX_ENUM;
    VkColorSpaceKHR color_space_ = VK_COLOR_SPACE_MAX_ENUM_KHR;
};

} // namespace cielim::vk::swapchain
