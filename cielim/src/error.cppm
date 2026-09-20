// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Creates and defines custom containers and types for error handling. A struct with an error code and detail
 * string is created as the main error wrapper to be propagated. Generic and specific error types are derived from
 * std::error_category and std::error_type to allow custom errors to be interchanged with standard errors. */

module;

#include <cctype>
#include <format>
#include <ranges>
#include <string>
#include <string_view>
#include <system_error>

export module cielim.error;

export namespace cielim::error
{

// Trims trailing periods and lowercases a leading capital
[[nodiscard]] inline auto sanitize_fragment(std::string text) -> std::string
{
    // Remove the last character until the last character is no longer a period
    while (!text.empty() && text.back() == '.') text.pop_back();

    // Lowercase the first letter
    if (!text.empty() && !text.starts_with("VK_"))
        text.front() = static_cast<char>(std::tolower(static_cast<unsigned char>(text.front())));

    return text;
}

// Error type that contains standard error and optional detail string
struct DetailedError
{
    std::error_code errc;
    std::string detail;
    std::string trace;

    /**
     * @brief Returns a copy of this error with an added trace.
     * @details This should be used when returning the same error further up the call stack.
     * @param trace A description of the operation that was being attempted when this error occurred.
     * @return A copy of this error with an added trace.
     */
    [[nodiscard]] auto with_trace(std::string trace) const -> DetailedError
    {
        DetailedError copy = *this;
        copy.trace = this->trace.empty() ? std::move(trace) : trace + ": " + this->trace;
        return copy;
    }

    // Returns the error message formatted as "[trace]: [error]: [detail]".
    [[nodiscard]] auto message() const -> std::string
    {
        const std::string sanitized_error = sanitize_fragment(this->errc.message());
        const std::string sanitized_detail = sanitize_fragment(this->detail);
        const std::string sanitized_trace = sanitize_fragment(this->trace);

        std::string message = sanitized_error;

        if (!sanitized_detail.empty())
            message = std::format("{:s}: {:s}", message, sanitized_detail);

        if (!sanitized_trace.empty())
            message = std::format("{:s}: {:s}", sanitized_trace, message);

        // Uppercase the first letter in the combined string
        if (!message.empty())
            message.front() = static_cast<char>(std::toupper(static_cast<unsigned char>(message.front())));

        return message;
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
        case WindowCreateError: return "failed to create window";
        case ExtensionEnumerateError: return "failed to enumerate required Vulkan instance extensions";
        case SurfaceCreateError: return "failed to create window surface";
        case PresentationUnsupported: return "no queue family supports presentation";
        case GetSizeError: return "failed to get window size";
        }

        return "unknown window error";
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
        case EnumerateVersionError: return "failed to enumerate Vulkan instance version";
        case VersionUnsupported: return "Vulkan instance does not support version 1.4";
        case EnumerateInstanceLayersError: return "failed to enumerate supported Vulkan instance layers";
        case MissingInstanceLayer: return "missing required Vulkan instance layer";
        case EnumerateInstanceExtsError: return "failed to enumerated supported Vulkan instance extensions";
        case MissingInstanceExt: return "missing required Vulkan instance extension";
        case InstanceCreateError: return "failed to create Vulkan instance";
        case DebugMessengerCreateError: return "failed to create Vulkan debug messenger";
        case EnumeratePhysicalDevicesError: return "failed to enumerate Vulkan physical devices";
        case NoSupportedDevice: return "failed to find supported Vulkan physical device";
        case EnumerateDeviceExtsError: return "failed to enumerate Vulkan device extensions";
        case MissingDeviceExt: return "missing required Vulkan device extensions";
        case DeviceCreateError: return "failed to create Vulkan device";
        }

        return "unknown Vulkan instance error";
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
    AcquireImageError,
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
        case SurfaceCapabilitiesError: return "failed to get surface capabilities";
        case SurfaceFormatsError: return "failed to get surface formats";
        case MissingSurfaceFormats: return "required surface formats are not supported";
        case NullExtent: return "swapchain extent is invalid (0x0)";
        case SwapchainCreateError: return "failed to create swapchain";
        case GetImageError: return "failed to get swapchain images";
        case ViewCreateError: return "failed to create image view for swapchain image";
        case AcquireImageError: return "failed to acquire swapchain image";
        }

        return "unknown Vulkan swapchain error";
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
        case FileOpenError: return "failed to open shader file";
        case ModuleCreateError: return "failed to create shader module";
        }

        return "unknown Vulkan shader module error";
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
        case LayoutCreateError: return "failed to create pipeline layout";
        case PipelineCreateError: return "failed to create render pipeline";
        }

        return "unknown Vulkan pipeline error";
    }
};

enum class VkResourcesError : std::uint8_t
{
    CommandPoolCreateError,
    CommandPoolResetError,
    CommandBufferCreateError,
    CommandBufferBeginError,
    CommandBufferEndError,
    SemaphoreCreateError,
    SemaphoreWaitError,
};

template <>
struct ErrorType<VkResourcesError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkResourcesError";

    static auto message(const VkResourcesError error) -> std::string_view
    {
        using enum VkResourcesError;

        switch (error)
        {
        case CommandPoolCreateError: return "failed to create command pool";
        case CommandPoolResetError: return "failed to reset command pool";
        case CommandBufferCreateError: return "failed to create command buffer";
        case CommandBufferBeginError: return "failed to begin command buffer";
        case CommandBufferEndError: return "failed to end command buffer";
        case SemaphoreCreateError: return "failed to create semaphore";
        case SemaphoreWaitError: return "failed to wait on semaphore";
        }

        return "unknown Vulkan resource error";
    }
};

enum class VkAllocatorError : std::uint8_t
{
    ImportFunctionsError,
    AllocatorCreateError,
};

template <>
struct ErrorType<VkAllocatorError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkAllocatorError";

    static auto message(const VkAllocatorError error) -> std::string_view
    {
        using enum VkAllocatorError;

        switch (error)
        {
        case ImportFunctionsError: return "failed to import Vulkan functions";
        case AllocatorCreateError: return "failed to create VMA allocator";
        }

        return "unknown VMA allocator error";
    }
};

enum class VkBufferError : std::uint8_t
{
    InvalidBufferCount,
    BufferCreateError,
    NullMappedMemory,
    BufferOverflow,
};

template <>
struct ErrorType<VkBufferError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkBufferError";

    static auto message(const VkBufferError error) -> std::string_view
    {
        using enum VkBufferError;

        switch (error)
        {
        case InvalidBufferCount: return "invalid buffer count";
        case BufferCreateError: return "failed to allocate buffer memory";
        case NullMappedMemory: return "mapped memory is not allocated or could not be found";
        case BufferOverflow: return "buffer overflow";
        }

        return "unknown buffer error";
    }
};

enum class VkRenderError : std::uint8_t
{
    QueueSubmitError,
    QueuePresentError,
};

template <>
struct ErrorType<VkRenderError>
{
    static constexpr bool IS_ERROR = true;
    static constexpr std::string_view CATEGORY_NAME = "VkRenderError";

    static auto message(const VkRenderError error) -> std::string_view
    {
        using enum VkRenderError;

        switch (error)
        {
        case QueueSubmitError: return "failed to submit commands to queue";
        case QueuePresentError: return "failed to present to swapchain";
        }

        return "unknown Vulkan render error";
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
template <>
struct std::is_error_code_enum<cielim::error::VkResourcesError> : std::true_type
{
};
template <>
struct std::is_error_code_enum<cielim::error::VkAllocatorError> : std::true_type
{
};
template <>
struct std::is_error_code_enum<cielim::error::VkBufferError> : std::true_type
{
};
template <>
struct std::is_error_code_enum<cielim::error::VkRenderError> : std::true_type
{
};
