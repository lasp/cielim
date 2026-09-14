// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A buffer represents memory allocated through VMA. It may optionally be mapped for direct CPU access and/or
 * given a GPU device virtual address so it can be read without descriptor sets. */

module;

#include <cstddef>
#include <cstring>
#include <format>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

#include <vma/vk_mem_alloc.h>

export module cielim.vk:buffer;

import cielim.handle;
import cielim.result;
import :allocator;
import :context;

export namespace cielim::vk::buffer
{

class Buffer
{
public:
    Buffer() = default;

    // Delete copy constructors

    Buffer(const Buffer&) = delete;
    auto operator=(const Buffer&) -> Buffer& = delete;

    // Use default move constructors

    Buffer(Buffer&&) = default;
    auto operator=(Buffer&&) -> Buffer& = default;

    ~Buffer()
    {
        if (this->buffer_)
            vmaDestroyBuffer(this->vma_allocator_handle_, this->buffer_.get(), this->allocation_.get());
    }

    /**
     * @brief Creates the buffer and allocates its memory.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param size The size of the buffer in bytes.
     * @param usage_flags (Optional) Intended usage flags for the buffer.
     * @param alloc_flags (Optional) Memory allocation flags.
     * @param memory_usage (Optional) Intended memory usage for the buffer; determines memory type.
     * @return Void on success, error code on failure.
     */
    auto create(
        const context::Context& context,
        const allocator::Allocator& allocator,
        const VkDeviceSize size,
        const VkBufferUsageFlags usage_flags = {},
        const VmaAllocationCreateFlags alloc_flags = {},
        const VmaMemoryUsage memory_usage = VMA_MEMORY_USAGE_AUTO
    ) -> Result<void>
    {
        this->vma_allocator_handle_ = allocator.get_handle(); // This is specifically a non-owning (borrow) handle

        const VkBufferCreateInfo buffer_info = {
            .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
            .size = size,
            .usage = usage_flags,
        };

        const VmaAllocationCreateInfo allocation_create_info = {
            .flags = alloc_flags,
            .usage = memory_usage,
        };

        VmaAllocationInfo allocation_info = {};

        if (const auto result = vmaCreateBuffer(
                this->vma_allocator_handle_,
                &buffer_info,
                &allocation_create_info,
                this->buffer_.put(),
                this->allocation_.put(),
                &allocation_info
            );
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkBufferError::BufferCreateError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        this->size_ = allocation_info.size;

        // Null pointer unless mapped memory was requested in alloc_flags
        this->mapped_data_ = static_cast<std::byte*>(allocation_info.pMappedData);

        // Get buffer device address if one was requested
        if ((usage_flags & VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT) != 0)
        {
            const VkBufferDeviceAddressInfo address_info = {
                .sType = VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO,
                .buffer = this->buffer_.get(),
            };

            this->address_ = vkGetBufferDeviceAddress(context.get_device(), &address_info);
        }

        return {};
    }

    /**
     * @brief Directly writes data into the buffer's mapped host-visible memory.
     * @details Only valid if the buffer was created with persistent CPU mapping (VMA_ALLOCATION_CREATE_MAPPED_BIT) and
     * the buffer's memory is host-visible. This bypasses the use of a staging buffer.
     * @param offset Byte offset into the buffer at which to begin writing.
     * @param data Pointer to the source data to copy.
     * @param size Number of bytes to copy.
     * @return Void on success, error code on failure.
     */
    auto direct_write(const VkDeviceSize offset, const void* data, const VkDeviceSize size) const -> Result<void>
    {
        if (this->mapped_data_ == nullptr)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkBufferError::NullMappedMemory),
                .detail = "",
            };

            return Err(error);
        }

        if (offset > this->size_)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkBufferError::BufferOverflow),
                .detail = std::format("offset {} exceeds buffer size {}", offset, this->size_),
            };
            return Err(error);
        }

        if (const auto available_bytes = this->size_ - offset; size > available_bytes)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkBufferError::BufferOverflow),
                .detail = std::format("need {} bytes, only {} available", size, available_bytes),
            };

            return Err(error);
        }

        std::memcpy(this->mapped_data_ + offset, data, size);

        // Make the write immediately visible for non-coherent memory
        vmaFlushAllocation(this->vma_allocator_handle_, this->allocation_.get(), offset, size);

        return {};
    }

    [[nodiscard]] auto get_handle() const -> VkBuffer { return this->buffer_.get(); }
    // Gets the size of the buffer's underlying allocation in bytes
    [[nodiscard]] auto get_size() const -> VkDeviceSize { return this->size_; }
    // Gets pointer to persistently-mapped host-visible memory, or nullptr if none was created.
    [[nodiscard]] auto get_mapped_data() const -> std::byte* { return this->mapped_data_; }
    // Gets GPU device address, or 0 if none was created.
    [[nodiscard]] auto get_device_address() const -> VkDeviceAddress { return this->address_; }

private:
    // Non-owning handle for the VMA allocator
    VmaAllocator vma_allocator_handle_ = nullptr;

    // The buffer object
    UniqueHandle<VkBuffer> buffer_;

    // The memory allocation for the buffer object
    UniqueHandle<VmaAllocation> allocation_;

    // The size of the buffer in bytes
    VkDeviceSize size_ = 0;

    // Pointer to mapped memory, only valid if the buffer was created with VMA_ALLOCATION_CREATE_MAPPED_BIT
    std::byte* mapped_data_ = nullptr;

    // GPU device address, only valid if the buffer was created with VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT
    VkDeviceAddress address_ = 0;
};

} // namespace cielim::vk::buffer
