// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A device buffer is specifically a device-local buffer allocated in GPU VRAM. This buffer type may or may not
 * be host-visible depending on whether the buffer goes beyond the BAR limit of 256 MiB and/or the physical device is
 * integrated or has ReBAR enabled. */

module;

#include <cstdint>
#include <span>
#include <utility>

#include <volk/volk.h>

#include <vma/vk_mem_alloc.h>

export module cielim.gpu.vk:device_buffer;

import cielim.result;
import :allocator;
import :buffer;
import :context;

export namespace cielim::gpu::vk
{

template <typename T>
class DeviceBuffer
{
public:
    // Delete copy constructors

    DeviceBuffer(const DeviceBuffer&) = delete;
    auto operator=(const DeviceBuffer&) -> DeviceBuffer& = delete;

    // Use default move constructor, delete move assignment

    DeviceBuffer(DeviceBuffer&&) = default;
    auto operator=(DeviceBuffer&&) -> DeviceBuffer& = delete;

    ~DeviceBuffer() = default;

    /**
     * @brief Creates the device buffer.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param element_capacity The initial number of elements the buffers should hold.
     * @param usage_flags (Optional) Intended usage flags for the buffers.
     * @return The device buffer on success, error code on failure.
     */
    static auto create(
        const Context& context,
        const Allocator& allocator,
        const uint32_t element_capacity,
        const VkBufferUsageFlags usage_flags = {}
    ) -> Result<DeviceBuffer>
    {
        auto buffer_result = Buffer::create(
            context,
            allocator,
            element_capacity * sizeof(T),
            usage_flags,
            VMA_ALLOCATION_CREATE_MAPPED_BIT | VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT
                | VMA_ALLOCATION_CREATE_HOST_ACCESS_ALLOW_TRANSFER_INSTEAD_BIT
        );

        if (!buffer_result.has_value())
            return buffer_result.propagate();

        return DeviceBuffer(std::move(buffer_result).value());
    }

    /**
     * @brief Writes an item into the device buffer.
     * @param slot The slot in the buffer to write to.
     * @param value The element to write into the buffer.
     * @return Void on success, error code on failure.
     */
    auto write(const uint32_t slot, const T& value) const -> Result<void>
    {
        const auto offset = slot * sizeof(T);
        const auto size = sizeof(T);

        // In the future, this should ideally resize buffer on overflow
        if (const auto result = this->gpu_buffer_.direct_write(offset, &value, size); !result.has_value())
            return result.propagate();

        return {};
    }

    /**
     * @brief Writes a list of items into the device buffer.
     * @param slot_offset The slot in the buffer at which the write should start.
     * @param values The elements to write into the buffer.
     * @return Void on success, error code on failure.
     */
    auto write_many(const uint32_t slot_offset, const std::span<const T> values) const -> Result<void>
    {
        const auto offset = slot_offset * sizeof(T);
        const auto size = values.size_bytes();

        // In the future, this should ideally resize buffer on overflow
        if (const auto result = this->gpu_buffer_.direct_write(offset, values.data(), size); !result.has_value())
            return result.propagate();

        return {};
    }

    [[nodiscard]] auto get_handle() const -> VkBuffer { return this->gpu_buffer_.get_handle(); }
    [[nodiscard]] auto get_address() const -> VkDeviceAddress { return this->gpu_buffer_.get_device_address(); }

private:
    explicit DeviceBuffer(Buffer&& gpu_buffer) : gpu_buffer_(std::move(gpu_buffer)) {}

    // The GPU buffer object
    Buffer gpu_buffer_;
};

} // namespace cielim::gpu::vk
