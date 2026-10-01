// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A ring of device-local GPU buffers synced with a CPU mirror. This should be used for buffers whose data is
 * updated between frames in flight and whose data must be accessed from the CPU. Using this type avoids having to do
 * slow GPU buffer readbacks to the CPU. */

module;

#include <cstdint>
#include <format>
#include <functional>
#include <span>
#include <system_error>
#include <utility>
#include <vector>

#include <volk/volk.h>

export module cielim.gpu.vk:synced_ring;

import cielim.error;
import cielim.helpers;
import cielim.result;
import :allocator;
import :context;
import :buffer_ring;

export namespace cielim::gpu::vk
{

template <typename T>
class SyncedRing
{
public:
    // Delete copy constructors

    SyncedRing(const SyncedRing&) = delete;
    auto operator=(const SyncedRing&) -> SyncedRing& = delete;

    // Use default move constructor, delete move assignment

    SyncedRing(SyncedRing&&) = default;
    auto operator=(SyncedRing&&) -> SyncedRing& = delete;

    ~SyncedRing() = default;

    /**
     * @brief Creates the synced ring with an empty CPU mirror.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param num_buffers The number of GPU buffers the ring should hold.
     * @param element_capacity The number of elements each GPU buffer can hold.
     * @param usage_flags (Optional) Intended usage flags for the GPU buffers.
     * @return The synced ring on success, error code on failure.
     */
    static auto create(
        const Context& context,
        const Allocator& allocator,
        const uint32_t num_buffers,
        const uint32_t element_capacity,
        const VkBufferUsageFlags usage_flags = {}
    ) -> Result<SyncedRing>
    {
        auto ring_result = BufferRing<T>::create(context, allocator, num_buffers, element_capacity, usage_flags);

        if (!ring_result.has_value())
            return ring_result.propagate();

        return SyncedRing(element_capacity, std::move(ring_result).value());
    }

    /**
     * @brief Appends an element to the CPU mirror.
     * @details Changes to the CPU mirror do not affect the GPU buffers until after flush.
     * @param value The element to append.
     * @return The index of the new element on success, error code on failure.
     */
    auto push_back(const T& value) -> Result<uint32_t>
    {
        // In the future, this should ideally resize the GPU buffers instead
        if (this->cpu_mirror_.size() >= this->capacity_)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::VkBufferError::BufferOverflow),
                    .detail = std::format("synced ring is full ({} elements)", this->capacity_),
                }
            );
        }

        const auto index = static_cast<uint32_t>(this->cpu_mirror_.size());

        this->cpu_mirror_.push_back(value);

        return index;
    }

    /**
     * @brief Overwrites an existing element in the CPU mirror.
     * @details Changes to the CPU mirror do not affect the GPU buffers until after flush.
     * @param index The index of the element to overwrite.
     * @param value The new value of the element.
     * @return Void on success, error code on failure.
     */
    auto set(const uint32_t index, const T& value) -> Result<void>
    {
        if (index >= this->cpu_mirror_.size())
        {
            return Err(
                error::DetailedError{
                    .errc = std::make_error_code(std::errc::argument_out_of_domain),
                    .detail = std::format("index {} is out of bounds for size {}", index, this->cpu_mirror_.size()),
                }
            );
        }

        this->cpu_mirror_[index] = value;

        return {};
    }

    /**
     * @brief Flushes the contents of the CPU mirror into one of the GPU buffers in the ring.
     * @details This should only be called when the GPU is not reading from the indexed buffer.
     * @param index The index of the GPU buffer into which to flush.
     * @return Void on success, error code on failure.
     */
    auto flush(const uint32_t index) -> Result<void>
    {
        if (index >= this->buffer_num_elements_.size())
        {
            return Err(
                error::DetailedError{
                    .errc = std::make_error_code(std::errc::argument_out_of_domain),
                    .detail
                    = std::format("index {} is out of bounds for size {}", index, this->buffer_num_elements_.size()),
                }
            );
        }

        // Only write to the GPU buffer if the CPU mirror isn't empty
        if (!this->cpu_mirror_.empty())
        {
            // TODO: Replace naive full copy with selective update propagation later
            if (const auto result = this->gpu_buffers_.write_many(index, 0, std::span<const T>(this->cpu_mirror_));
                !result.has_value())
                return result.propagate();
        }

        this->buffer_num_elements_[index] = static_cast<uint32_t>(this->cpu_mirror_.size());

        return {};
    }

    /**
     * @brief Gets an element from the CPU mirror.
     * @param index The index of the element.
     * @return A copy of the element on success, error code on failure.
     */
    auto at(const uint32_t index) const -> Result<T> { return try_at(this->cpu_mirror_, index); }

    // Gets the number of elements currently in the CPU mirror
    [[nodiscard]] auto get_mirror_size() const -> uint32_t { return static_cast<uint32_t>(this->cpu_mirror_.size()); }

    // Gets the maximum number of elements that can be held
    [[nodiscard]] auto get_capacity() const -> uint32_t { return this->capacity_; }

    // Gets the number of elements held within a buffer, or an error code on failure
    auto get_buffer_num_elements(const uint32_t index) const -> Result<uint32_t>
    { return try_at(this->buffer_num_elements_, index); }

    auto get_handle(const uint32_t index) const -> Result<VkBuffer> { return this->gpu_buffers_.get_handle(index); }

    auto get_address(const uint32_t index) const -> Result<VkDeviceAddress>
    { return this->gpu_buffers_.get_address(index); }

private:
    // gpu_buffers_ must be initialized before buffer_num_elements
    SyncedRing(const uint32_t capacity, BufferRing<T>&& gpu_buffers) :
        capacity_(capacity), gpu_buffers_(std::move(gpu_buffers)),
        buffer_num_elements_(gpu_buffers_.get_num_buffers(), 0)
    { this->cpu_mirror_.reserve(capacity); }

    // TODO: This should be replaced with buffer resizing at some point
    // The max number of elements to hold
    uint32_t capacity_ = 0;

    // The CPU mirror and the source of truth for the buffers
    std::vector<T> cpu_mirror_;

    // The GPU buffer ring
    BufferRing<T> gpu_buffers_;

    // The number of elements in each GPU buffer
    std::vector<uint32_t> buffer_num_elements_;
};

} // namespace cielim::gpu::vk
