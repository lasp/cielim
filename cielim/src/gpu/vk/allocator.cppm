// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Owns the Vulkan Memory Allocator (VMA) allocator handle. Only one should exist at a time. */

module;

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

#include <vma/vk_mem_alloc.h>

export module cielim.gpu.vk:allocator;

import cielim.error;
import cielim.handle;
import cielim.result;
import cielim.utils;
import :context;

export namespace cielim::gpu::vk
{

class Allocator
{
public:
    Allocator() = default;

    // Delete copy constructors

    Allocator(const Allocator&) = delete;
    auto operator=(const Allocator&) -> Allocator& = delete;

    // Use default move constructors

    Allocator(Allocator&&) = default;
    auto operator=(Allocator&&) -> Allocator& = default;

    ~Allocator()
    {
        if (this->allocator_)
            vmaDestroyAllocator(this->allocator_.get());
    }

    /**
     * @brief Initializes the VMA allocator.
     * @param context The Vulkan context.
     * @return Void on success, error code on failure.
     */
    auto init(const Context& context) -> Result<void>
    {
        VmaAllocatorCreateInfo allocator_create_info = {
            .flags = VMA_ALLOCATOR_CREATE_EXT_MEMORY_BUDGET_BIT      // Uses memory budget feature
                   | VMA_ALLOCATOR_CREATE_BUFFER_DEVICE_ADDRESS_BIT, // Required for buffer device address features
            .physicalDevice = context.get_physical_device(),
            .device = context.get_device(),
            .instance = context.get_instance(),
            .vulkanApiVersion = VK_API_VERSION_1_4,
        };

        VmaVulkanFunctions vulkan_functions = {};

        if (const auto result = vmaImportVulkanFunctionsFromVolk(&allocator_create_info, &vulkan_functions);
            result != VK_SUCCESS)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkAllocatorError::ImportFunctionsError),
                    .detail = string_VkResult(result),
                }
            );
        }

        allocator_create_info.pVulkanFunctions = &vulkan_functions;

        if (const auto result = vmaCreateAllocator(&allocator_create_info, this->allocator_.put());
            result != VK_SUCCESS)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkAllocatorError::AllocatorCreateError),
                    .detail = string_VkResult(result),
                }
            );
        }

        utils::log::info("Initialized VMA allocator");

        return {};
    }

    [[nodiscard]] auto get_handle() const -> VmaAllocator { return allocator_.get(); }

private:
    // The VMA allocator object
    UniqueHandle<VmaAllocator> allocator_;
};

} // namespace cielim::gpu::vk
