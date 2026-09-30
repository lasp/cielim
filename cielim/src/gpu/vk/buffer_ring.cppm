// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A ring of device-local GPU buffers. */

module;

#include <cstdint>
#include <span>
#include <utility>
#include <vector>

#include <volk/volk.h>

export module cielim.gpu.vk:buffer_ring;

import cielim.error;
import cielim.helpers;
import cielim.result;
import :allocator;
import :context;
import :device_buffer;

export namespace cielim::gpu::vk
{

template <typename T>
class BufferRing
{
public:
    // Delete copy constructors

    BufferRing(const BufferRing&) = delete;
    auto operator=(const BufferRing&) -> BufferRing& = delete;

    // Use default move constructor, delete move assignment

    BufferRing(BufferRing&&) = default;
    auto operator=(BufferRing&&) -> BufferRing& = delete;

    ~BufferRing() = default;

    /**
     * @brief Creates the buffer ring.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param num_buffers The number of buffers the ring should hold.
     * @param element_capacity The initial number of elements the buffers should hold.
     * @param usage_flags (Optional) Intended usage flags for the buffers.
     * @return The buffer ring on success, error code on failure.
     */
    static auto create(
        const Context& context,
        const Allocator& allocator,
        const uint32_t num_buffers,
        const uint32_t element_capacity,
        const VkBufferUsageFlags usage_flags = {}
    ) -> Result<BufferRing>
    {
        BufferRing ring;

        if (num_buffers == 0)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkBufferError::InvalidBufferCount),
                    .detail = "a ring must have one or more buffers",
                }
            );
        }

        ring.num_buffers_ = num_buffers;

        ring.gpu_buffers_.reserve(ring.num_buffers_);

        for (uint32_t i = 0; i < ring.num_buffers_; i++)
        {
            auto buffer_result = DeviceBuffer<T>::create(context, allocator, element_capacity, usage_flags);

            if (!buffer_result.has_value())
                return buffer_result.propagate();

            ring.gpu_buffers_.emplace_back(std::move(buffer_result).value());
        }

        return ring;
    }

    /**
     * @brief Writes an item into one of the buffers in the ring.
     * @param index The index by which the ring of buffers should be accessed.
     * @param slot The slot in the buffer to write to.
     * @param value The element to write into the buffer.
     * @return Void on success, error code on failure.
     */
    auto write(const uint32_t index, const uint32_t slot, const T& value) const -> Result<void>
    {
        const auto gpu_buffer_result = try_at_ref(this->gpu_buffers_, index);

        if (!gpu_buffer_result.has_value())
            return gpu_buffer_result.propagate();

        return gpu_buffer_result.value().get().write(slot, value);
    }

    /**
     * @brief Writes a list of items into one of the buffers in the ring.
     * @param index The index by which the ring of buffers should be accessed.
     * @param slot_offset The slot in the buffer at which the write should start.
     * @param values The elements to write into the buffer.
     * @return Void on success, error code on failure.
     */
    auto write_many(const uint32_t index, const uint32_t slot_offset, const std::span<const T> values) const
        -> Result<void>
    {
        const auto gpu_buffer_result = try_at_ref(this->gpu_buffers_, index);

        if (!gpu_buffer_result.has_value())
            return gpu_buffer_result.propagate();

        return gpu_buffer_result.value().get().write_many(slot_offset, values);
    }

    auto get_handle(const uint32_t index) const -> Result<VkBuffer>
    {
        const auto gpu_buffer_result = try_at_ref(this->gpu_buffers_, index);

        if (!gpu_buffer_result.has_value())
            return gpu_buffer_result.propagate();

        return gpu_buffer_result.value().get().get_handle();
    }

    auto get_address(const uint32_t index) const -> Result<VkDeviceAddress>
    {
        const auto gpu_buffer_result = try_at_ref(this->gpu_buffers_, index);

        if (!gpu_buffer_result.has_value())
            return gpu_buffer_result.propagate();

        return gpu_buffer_result.value().get().get_address();
    }

private:
    BufferRing() = default;

    // The number of GPU buffers to hold
    uint32_t num_buffers_ = 0;

    // The list of GPU buffers sized by the number of frames in flight
    std::vector<DeviceBuffer<T>> gpu_buffers_;
};

} // namespace cielim::gpu::vk
