// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Wraps raw pointer handles to add default move behavior and restrict copying. This should only be used when
 * one needs to claim ownership over the handle and manage its lifetime. */

module;

#include <cassert>
#include <utility>

export module cielim.handle;

// Export to project-level namespace because this is generic enough
export namespace cielim
{

template <typename T, T Null = nullptr>
class UniqueHandle
{
public:
    UniqueHandle() = default;
    explicit UniqueHandle(T handle) : handle_ptr_(handle) {}

    // Delete copy constructors, two different objects shouldn't have ownership over a raw pointer

    UniqueHandle(const UniqueHandle&) = delete;
    auto operator=(const UniqueHandle&) -> UniqueHandle& = delete;

    // Null pointer on move to avoid double free, move assignment is deleted so a live handle can't be overwritten

    UniqueHandle(UniqueHandle&& other) noexcept : handle_ptr_(std::exchange(other.handle_ptr_, Null)) {}
    auto operator=(UniqueHandle&&) -> UniqueHandle& = delete;

    ~UniqueHandle() = default; // Deconstruction should be handled by owning class

    [[nodiscard]] explicit operator bool() const { return handle_ptr_ != Null; }
    [[nodiscard]] auto get() const -> T { return handle_ptr_; }

    /**
     * @brief Gets a pointer to the handle so it can be written by a creation function.
     * @details The handle must be null so it doesn't override a live handle and leak it.
     */
    [[nodiscard]] auto put() -> T*
    {
        assert(handle_ptr_ == Null && "UniqueHandle::put() called on a live handle");
        return &handle_ptr_;
    }

    auto reset() -> void { handle_ptr_ = Null; }

private:
    T handle_ptr_ = Null;
};

} // namespace cielim
