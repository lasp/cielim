// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Creates and defines custom containers and types for error handling. A struct with an error code and detail
 * string is created as the main error wrapper to be propagated. Generic and specific error types are derived from
 * std::error_category and std::error_type to allow custom errors to be interchanged with standard errors. */

module;

#include <format>
#include <string>
#include <string_view>
#include <system_error>

export module cielim.error;

export namespace cielim::error
{

// Error type that contains standard error and optional detail string
struct DetailedError
{
    std::error_code errc;
    std::string detail;

    // Return error message with details
    [[nodiscard]] auto message() const -> std::string
    { return detail.empty() ? errc.message() : std::format("{}: {}", errc.message(), detail); }
};

// ----- Generic error type definitions -----

// Default error type struct
template <typename Enum>
struct ErrorType
{
    static constexpr bool IS_ERROR = false;
};

template <typename Enum>
concept ErrorEnum = ErrorType<Enum>::IS_ERROR; // Error struct must be explicitly marked as such

// Generic custom error category
template <ErrorEnum Enum>
class ErrorCategory final : public std::error_category
{
public:
    // Returns the name of the error category
    [[nodiscard]] auto name() const noexcept -> const char* override { return ErrorType<Enum>::CATEGORY_NAME.data(); }

    // Returns the message associated with the specific error
    [[nodiscard]] auto message(int value) const -> std::string override
    { return std::string(ErrorType<Enum>::message(static_cast<Enum>(value))); }

    // Returns a reference to the error type singleton
    [[nodiscard]] static auto instance() noexcept -> const ErrorCategory&
    {
        static const ErrorCategory instance;
        return instance;
    }
};

// Generic implementation of make_error_code for custom error types
template <ErrorEnum Enum>
auto make_error_code(Enum e) noexcept -> std::error_code
{ return std::error_code(static_cast<int>(e), ErrorCategory<Enum>::instance()); }

// ----- Specific error type implementations -----

enum class WindowError : std::uint8_t
{
    WindowCreateError,
    ExtensionEnumerateError,
    SurfaceCreateError,
    PresentationUnsupported,
};

template <>
struct ErrorType<WindowError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "WindowError";

    static auto message(const WindowError error) -> std::string_view
    {
        using enum WindowError;

        switch (error)
        {
        case WindowCreateError: return "Failed to create window";
        case ExtensionEnumerateError: return "Failed to enumerate required Vulkan instance extensions";
        case SurfaceCreateError: return "Failed to create window surface";
        case PresentationUnsupported: return "No queue family supports presentation";
        }

        return "Unknown window error";
    }
};

} // namespace cielim::error

// Register custom error types with standard library

template <>
struct std::is_error_code_enum<cielim::error::WindowError> : std::true_type
{
};
