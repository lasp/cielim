// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Provides a thin wrapper over std::expected explicitly marked as [[nodiscard]] and with added convenience.
 * Pointer operators are forbidden to avoid accidental misuse. */

module;

#include <concepts>
#include <expected>
#include <system_error>
#include <type_traits>
#include <utility>

export module cielim.result;

import cielim.error;

// We export this in the project-level namespace for convenience, otherwise we'd need result::Result everywhere
export namespace cielim
{

// Namespace alis for std::unexpected
template <typename E>
using Err = std::unexpected<E>;

template <typename T, typename E = error::DetailedError> // DetailedError is the default error type
class [[nodiscard]] Result
{
public:
    using value_type = T;
    using error_type = E;
    using std_expected = std::expected<T, E>;

    // Forward construction to the constructor of std::expected<T, E> only if it's constructible
    template <typename... Args>
        requires std::constructible_from<std_expected, Args...>
    constexpr Result(Args&&... args) : expected_obj_(std::forward<Args>(args)...)
    {
    }

    // Use default copy/move behavior

    Result(const Result&) = default;
    Result(Result&&) = default;
    auto operator=(const Result&) -> Result& = default;
    auto operator=(Result&&) -> Result& = default;

    // Return true if result is normal value, false if result is an error
    [[nodiscard]] constexpr auto has_value() const noexcept -> bool { return expected_obj_.has_value(); }

    // Return whatever std::expected<T, E>::value() returns, i.e., the normal value object
    template <typename Self>
    [[nodiscard]] constexpr auto value(this Self&& self) -> decltype(auto)
    { return std::forward<Self>(self).expected_obj_.value(); }

    // Return whatever std::expected<T, E>::error() returns, i.e., the error object
    template <typename Self>
    [[nodiscard]] constexpr auto error(this Self&& self) -> decltype(auto)
    { return std::forward<Self>(self).expected_obj_.error(); }

    // Propagate current error, returns Err(E)
    template <typename Self>
    [[nodiscard]] constexpr auto propagate(this Self&& self) -> Err<E>
    { return Err(std::forward<Self>(self).expected_obj_.error()); }

private:
    // The std::expected<T, E> object being wrapped
    std_expected expected_obj_;
};

} // namespace cielim
