// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A ring of device-local GPU buffers. */

module;

#include <cstdint>
#include <vector>

#include <volk/volk.h>

#include <vma/vk_mem_alloc.h>

export module cielim.gpu.vk:buffer_ring;

import cielim.error;
import cielim.helpers;
import cielim.result;
import :allocator;
import :buffer;
import :context;

export namespace cielim::gpu::vk
{

template <typename T>
class BufferRing
{
public:
    BufferRing() = default;

    // Delete copy constructors

    BufferRing(const BufferRing&) = delete;
    auto operator=(const BufferRing&) -> BufferRing& = delete;

    // Use default move constructors

    BufferRing(BufferRing&&) = default;
    auto operator=(BufferRing&&) -> BufferRing& = default;

    ~BufferRing() = default;

    /**
     * @brief Creates the buffer ring.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param num_buffers The number of buffers the ring should hold.
     * @param element_capacity The initial number of elements the buffers should hold.
     * @param usage_flags (Optional) Intended usage flags for the buffers.
     * @return Void on success, error code on failure.
     */
    auto create(
        const Context& context,
        const Allocator& allocator,
        const uint32_t num_buffers,
        const uint32_t element_capacity,
        const VkBufferUsageFlags usage_flags = {}
    ) -> Result<void>
    {
        if (num_buffers == 0)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkBufferError::InvalidBufferCount),
                    .detail = "a ring must have 1 or more buffers",
                }
            );
        }

        this->num_buffers_ = num_buffers;

        // Create N buffers with default constructed buffers
        this->gpu_buffers_.resize(this->num_buffers_);

        /* Allocate each buffer as device-local memory. If available, it will be host-visible and can be written to
         * directly from the CPU. In the case that device-local memory that is host-visible is not available, a staging
         * buffer must be used to write into the buffer (not implemented rn). */
        for (auto& buffer : this->gpu_buffers_)
        {
            if (const auto result = buffer.create(
                    context,
                    allocator,
                    element_capacity * sizeof(T),
                    usage_flags,
                    VMA_ALLOCATION_CREATE_MAPPED_BIT | VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT
                        | VMA_ALLOCATION_CREATE_HOST_ACCESS_ALLOW_TRANSFER_INSTEAD_BIT
                );
                !result.has_value())
                return result.propagate();
        }

        return {};
    }

    /**
     * @brief Writes an item into one of the buffers in the ring.
     * @param index The index by which the ring of buffers should be accessed.
     * @param slot The slot in the buffer to write to.
     * @param value The element to write into the buffer.
     * @return Void on success, error code on failure.
     */
    auto write(const uint32_t index, const uint32_t slot, const T& value) -> Result<void>
    {
        const auto gpu_buffer_result = try_at_ref(this->gpu_buffers_, index);

        if (!gpu_buffer_result.has_value())
            return gpu_buffer_result.propagate();

        const Buffer& gpu_buffer = gpu_buffer_result.value().get();

        // In the future, this should ideally resize buffer on overflow
        if (const auto result = gpu_buffer.direct_write(slot * sizeof(T), &value, sizeof(T)); !result.has_value())
            return result.propagate();

        return {};
    }

    auto get_address(const uint32_t index) const -> Result<VkDeviceAddress>
    {
        const auto gpu_buffer_result = try_at_ref(this->gpu_buffers_, index);

        if (!gpu_buffer_result.has_value())
            return gpu_buffer_result.propagate();

        return gpu_buffer_result.value().get().get_device_address();
    }

private:
    // The number of GPU buffers to hold
    uint32_t num_buffers_ = 0;

    // The list of GPU buffers sized by the number of frames in flight
    std::vector<Buffer> gpu_buffers_;
};

} // namespace cielim::gpu::vk
