// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Creates and defines custom containers and types for error handling. A struct with an error code and detail
 * string is created as the main error wrapper to be propagated. Generic and specific error types are derived from
 * std::error_category and std::error_type to allow custom errors to be interchanged with standard errors. */

module;

#include <format>
#include <ranges>
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

    // Return error message with optional details
    [[nodiscard]] auto message() const -> std::string
    {
        if (detail.empty())
            return errc.message();

        return std::format("{:s}: {:s}", errc.message(), detail);
    }
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
    GetSizeError,
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
        case GetSizeError: return "Failed to get window size";
        }

        return "Unknown window error";
    }
};

enum class VkContextError : std::uint8_t
{
    EnumerateVersionError,
    VersionUnsupported,
    EnumerateInstanceLayersError,
    MissingInstanceLayer,
    EnumerateInstanceExtsError,
    MissingInstanceExt,
    InstanceCreateError,
    DebugMessengerCreateError,
    EnumeratePhysicalDevicesError,
    NoSupportedDevice,
    EnumerateDeviceExtsError,
    MissingDeviceExt,
    DeviceCreateError,
};

template <>
struct ErrorType<VkContextError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkContextError";

    static auto message(const VkContextError error) -> std::string_view
    {
        using enum VkContextError;

        switch (error)
        {
        case EnumerateVersionError: return "Failed to enumerate Vulkan instance version";
        case VersionUnsupported: return "Vulkan instance does not support version 1.4";
        case EnumerateInstanceLayersError: return "Failed to enumerate supported Vulkan instance layers";
        case MissingInstanceLayer: return "Missing required Vulkan instance layer";
        case EnumerateInstanceExtsError: return "Failed to enumerated supported Vulkan instance extensions";
        case MissingInstanceExt: return "Missing required Vulkan instance extension";
        case InstanceCreateError: return "Failed to create Vulkan instance";
        case DebugMessengerCreateError: return "Failed to create Vulkan debug messenger";
        case EnumeratePhysicalDevicesError: return "Failed to enumerate Vulkan physical devices";
        case NoSupportedDevice: return "Failed to find supported Vulkan physical device";
        case EnumerateDeviceExtsError: return "Failed to enumerate Vulkan device extensions";
        case MissingDeviceExt: return "Missing required Vulkan device extensions";
        case DeviceCreateError: return "Failed to create Vulkan device";
        }

        return "Unknown Vulkan instance error";
    }
};

enum class VkSwapchainError : std::uint8_t
{
    SurfaceCapabilitiesError,
    SurfaceFormatsError,
    MissingSurfaceFormats,
    NullExtent,
    SwapchainCreateError,
    GetImageError,
    ViewCreateError,
};

template <>
struct ErrorType<VkSwapchainError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkSwapchainError";

    static auto message(const VkSwapchainError error) -> std::string_view
    {
        using enum VkSwapchainError;

        switch (error)
        {
        case SurfaceCapabilitiesError: return "Failed to get surface capabilities";
        case SurfaceFormatsError: return "Failed to get surface formats";
        case MissingSurfaceFormats: return "Required surface formats are not supported";
        case NullExtent: return "Swapchain extent is invalid (0x0)";
        case SwapchainCreateError: return "Failed to create swapchain";
        case GetImageError: return "Failed to get swapchain images";
        case ViewCreateError: return "Failed to create image view for swapchain image";
        }

        return "Unknown Vulkan swapchain error";
    }
};

enum class VkShaderModuleError : std::uint8_t
{
    FileOpenError,
    ModuleCreateError,
};

template <>
struct ErrorType<VkShaderModuleError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkShaderModuleError";

    static auto message(const VkShaderModuleError error) -> std::string_view
    {
        using enum VkShaderModuleError;

        switch (error)
        {
        case FileOpenError: return "Failed to open shader file";
        case ModuleCreateError: return "Failed to create shader module";
        }

        return "Unknown Vulkan shader module error";
    }
};

enum class VkPipelineError : std::uint8_t
{
    LayoutCreateError,
    PipelineCreateError,
};

template <>
struct ErrorType<VkPipelineError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkPipelineError";

    static auto message(const VkPipelineError error) -> std::string_view
    {
        using enum VkPipelineError;

        switch (error)
        {
        case LayoutCreateError: return "Failed to create pipeline layout";
        case PipelineCreateError: return "Failed to create render pipeline";
        }

        return "Unknown Vulkan pipeline error";
    }
};

} // namespace cielim::error

// Register custom error types with standard library

template <>
struct std::is_error_code_enum<cielim::error::WindowError> : std::true_type
{
};
template <>
struct std::is_error_code_enum<cielim::error::VkContextError> : std::true_type
{
};
template <>
struct std::is_error_code_enum<cielim::error::VkSwapchainError> : std::true_type
{
};
template <>
struct std::is_error_code_enum<cielim::error::VkShaderModuleError> : std::true_type
{
};
template <>
struct std::is_error_code_enum<cielim::error::VkPipelineError> : std::true_type
{
};
