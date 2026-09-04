// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* The Vulkan context is a singleton that contains global context for Vulkan. This class contains and manages the
 * Vulkan instance, the windowing surface, and the logical device. */

module;

#include <cstring>
#include <expected>
#include <limits>
#include <string>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.vk:context;

import cielim.error;
import cielim.utils;
import cielim.window;

#ifndef NDEBUG
namespace
{
// Debug callback function for Vulkan context, only visible in context module
VKAPI_ATTR auto VKAPI_CALL debug_callback(
    VkDebugUtilsMessageSeverityFlagBitsEXT message_severity,
    VkDebugUtilsMessageTypeFlagsEXT message_type,
    const VkDebugUtilsMessengerCallbackDataEXT* p_callback_data,
    void* p_user_data
) -> VkBool32
{
    (void)p_user_data; // We don't do anything with this for now

    // Drop message if logger can't be found
    if (const auto logger = cielim::utils::log::get("log-vulkan"))
    {
        std::string message_type_str;

        if (message_type == VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT)
        {
            message_type_str = "General";
        }
        else if (message_type == VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT)
        {
            message_type_str = "Performance";
        }
        else if (message_type == VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT)
        {
            message_type_str = "Validation";
        }

        if (message_severity == VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT)
        {
            logger->info("Vulkan-{} -- {}", message_type_str, p_callback_data->pMessage);
        }
        else if (message_severity == VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT)
        {
            logger->warn("Vulkan-{} -- {}", message_type_str, p_callback_data->pMessage);
        }
        else if (message_severity == VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT)
        {
            logger->error("Vulkan-{} -- {}", message_type_str, p_callback_data->pMessage);
        }
        else
        {
            logger->trace("Vulkan-{} -- {}", message_type_str, p_callback_data->pMessage);
        }
    }

    return VK_FALSE; // Always return VK_FALSE
}
} // namespace
#endif

export namespace cielim::vk::context
{

class Context
{
public:
    // Delete copy and move constructors to prevent duplication

    Context(const Context&) = delete;
    auto operator=(const Context&) -> Context& = delete;
    Context(Context&&) = delete;
    auto operator=(Context&&) -> Context& = delete;

    /**
     * @brief Gets a reference to the global Vulkan context object.
     * @return Reference to the global Vulkan context object.
     */
    [[nodiscard]] static auto get_context() noexcept -> Context&
    {
        // Guaranteed instantiated on first use
        static Context context;
        return context;
    }

    [[nodiscard]] auto get_instance() const -> VkInstance { return this->vk_instance_; }
    [[nodiscard]] auto get_surface() const -> VkSurfaceKHR { return this->vk_surface_; }
    [[nodiscard]] auto get_physical_device() const -> VkPhysicalDevice { return this->vk_physical_device_; }
    [[nodiscard]] auto get_queue() const -> uint32_t { return this->queue_index_; }
    [[nodiscard]] auto get_device() const -> VkDevice { return this->vk_device_; }

    /**
     * @brief Initializes the Vulkan context.
     * @param window Window to link the Vulkan context to.
     * @return Void on success, error code on failure.
     */
    [[nodiscard]] auto init(const cielim::window::Window& window) -> std::expected<void, cielim::error::DetailedError>
    {
        if (this->is_initialized_)
            return {}; // Don't initialize more than once

        // Init the Vulkan instance
        if (const auto result = this->init_instance(window); !result.has_value())
            return std::unexpected(result.error());

        // Init the window surface
        if (const auto result = window.vk_create_surface(this->vk_instance_, &this->vk_surface_); !result.has_value())
            return std::unexpected(result.error());

        // Find physical devices
        if (const auto result = this->find_physical_device(window); !result.has_value())
            return std::unexpected(result.error());

        // Init the logical device
        if (const auto result = this->init_device(); !result.has_value())
            return std::unexpected(result.error());

        this->is_initialized_ = true;

        return {};
    }

private:
    Context() = default;

    ~Context()
    {
#ifndef NDEBUG
        if (this->debug_messenger_ != nullptr)
            vkDestroyDebugUtilsMessengerEXT(this->vk_instance_, this->debug_messenger_, nullptr);
#endif
        if (this->vk_device_ != nullptr)
            vkDestroyDevice(this->vk_device_, nullptr);

        if (this->vk_surface_ != nullptr)
            vkDestroySurfaceKHR(this->vk_instance_, this->vk_surface_, nullptr);

        if (this->vk_instance_ != nullptr)
            vkDestroyInstance(this->vk_instance_, nullptr);
    }

    [[nodiscard]] auto init_instance(const cielim::window::Window& window)
        -> std::expected<void, cielim::error::DetailedError>
    {
        uint32_t vk_api_version = 0;
        if (const auto result = vkEnumerateInstanceVersion(&vk_api_version); result != VK_SUCCESS)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::EnumerateVersionError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        cielim::utils::log::info(
            "Detected Vulkan loader API version: {}.{}.{}",
            VK_API_VERSION_MAJOR(vk_api_version),
            VK_API_VERSION_MINOR(vk_api_version),
            VK_API_VERSION_PATCH(vk_api_version)
        );

        if (vk_api_version < VK_API_VERSION_1_4)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::VersionUnsupported),
                .detail = "",
            };

            return std::unexpected(error);
        }

        // Setup application info
        constexpr VkApplicationInfo APP_INFO = {
            .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
            .pApplicationName = "Cielim",
            .applicationVersion = VK_MAKE_VERSION(0, 1, 0),
            .pEngineName = "CielimEngine",
            .engineVersion = VK_MAKE_VERSION(0, 1, 0),
            .apiVersion = VK_API_VERSION_1_4,
        };

        // Check if any required Vulkan instance layers are missing

        std::vector<const char*> req_inst_layers;

#ifndef NDEBUG
        req_inst_layers.push_back("VK_LAYER_KHRONOS_validation"); // Add validation layers in debug builds
#endif

        uint32_t inst_layer_count = 0;
        vkEnumerateInstanceLayerProperties(&inst_layer_count, nullptr);

        std::vector<VkLayerProperties> inst_layers(inst_layer_count);

        if (const auto result = vkEnumerateInstanceLayerProperties(&inst_layer_count, inst_layers.data());
            result != VK_SUCCESS)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::EnumerateInstanceLayersError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        std::vector<const char*> missing_inst_layers;

        for (const char* req_layer : req_inst_layers)
        {
            bool found = false;

            for (const auto& layer : inst_layers)
            {
                if (std::strcmp(req_layer, layer.layerName) == 0)
                {
                    found = true;
                    break;
                }
            }

            if (!found)
                missing_inst_layers.push_back(req_layer);
        }

        if (!missing_inst_layers.empty())
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::MissingInstanceLayer),
                .detail = fmt::format("{}", fmt::join(missing_inst_layers, ", ")),
            };

            return std::unexpected(error);
        }

        // Check if any required Vulkan instance extensions are missing

        auto ext_result = cielim::window::Window::vk_get_extensions();

        if (!ext_result.has_value())
            return std::unexpected(ext_result.error());

        std::vector<const char*> req_inst_extensions = ext_result.value(); // Initial list comes from the window

#ifndef NDEBUG
        req_inst_extensions.push_back("VK_EXT_debug_utils"); // Add debug extension in debug builds
#endif
#ifdef __APPLE__
        req_inst_extensions.push_back("VK_KHR_portability_enumeration"); // Add portability extension for Apple
#endif

        uint32_t inst_ext_count = 0;
        vkEnumerateInstanceExtensionProperties(nullptr, &inst_ext_count, nullptr);

        std::vector<VkExtensionProperties> inst_extensions(inst_ext_count);

        if (const auto result
            = vkEnumerateInstanceExtensionProperties(nullptr, &inst_ext_count, inst_extensions.data());
            result != VK_SUCCESS)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::EnumerateInstanceExtsError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        std::vector<const char*> missing_inst_extensions;

        for (const char* req_extension : req_inst_extensions)
        {
            bool found = false;

            for (const auto& [extension_name, spec_version] : inst_extensions)
            {
                if (std::strcmp(req_extension, extension_name) == 0)
                {
                    found = true;
                    break;
                }
            }

            if (!found)
                missing_inst_extensions.push_back(req_extension);
        }

        if (!missing_inst_extensions.empty())
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::MissingInstanceExt),
                .detail = fmt::format("{}", fmt::join(missing_inst_extensions, ", ")),
            };

            return std::unexpected(error);
        }

#ifndef NDEBUG
        VkDebugUtilsMessengerCreateInfoEXT debug_messenger_create_info = {
            .sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
            .messageSeverity
            = VK_DEBUG_UTILS_MESSAGE_SEVERITY_VERBOSE_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT
            | VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT,
            .messageType
            = VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT,
            .pfnUserCallback = debug_callback,
        };
#endif

        const VkInstanceCreateInfo instance_create_info = {
            .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
#ifndef NDEBUG
            .pNext = &debug_messenger_create_info,
#endif
#ifdef __APPLE__
            .flags = VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR,
#endif
            .pApplicationInfo = &APP_INFO,
            .enabledLayerCount = static_cast<uint32_t>(req_inst_layers.size()),
            .ppEnabledLayerNames = req_inst_layers.data(),
            .enabledExtensionCount = static_cast<uint32_t>(req_inst_extensions.size()),
            .ppEnabledExtensionNames = req_inst_extensions.data(),
        };

        if (const auto result = vkCreateInstance(&instance_create_info, nullptr, &this->vk_instance_);
            result != VK_SUCCESS)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::InstanceCreateError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        volkLoadInstance(this->vk_instance_); // Initialize Vulkan instance

#ifndef NDEBUG
        if (const auto result = vkCreateDebugUtilsMessengerEXT(
                this->vk_instance_, &debug_messenger_create_info, nullptr, &this->debug_messenger_
            );
            result != VK_SUCCESS)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::DebugMessengerCreateError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }
#endif

        return {};
    }

    [[nodiscard]] auto find_physical_device(const cielim::window::Window& window)
        -> std::expected<void, cielim::error::DetailedError>
    {
        VkPhysicalDevice physical_device = nullptr;
        uint32_t graphics_queue_family = std::numeric_limits<uint32_t>::max();

        // Get physical devices

        uint32_t num_devices = 0;
        vkEnumeratePhysicalDevices(this->vk_instance_, &num_devices, nullptr);

        std::vector<VkPhysicalDevice> physical_devices(num_devices);

        if (const auto result = vkEnumeratePhysicalDevices(this->vk_instance_, &num_devices, physical_devices.data());
            result != VK_SUCCESS || physical_devices.empty())
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::EnumeratePhysicalDevicesError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        // Loop through all physical devices to find the most suitable one
        // TODO: Make this more robust instead of choosing first suitable device

        bool found_device = false;

        for (const auto& device : physical_devices)
        {
            VkPhysicalDeviceProperties device_properties;
            vkGetPhysicalDeviceProperties(device, &device_properties);

            // Reject devices that can't support Vulkan 1.4+
            if (device_properties.apiVersion < VK_API_VERSION_1_4)
                continue;

            uint32_t num_queue_families = 0;
            vkGetPhysicalDeviceQueueFamilyProperties(device, &num_queue_families, nullptr);

            std::vector<VkQueueFamilyProperties> queue_families(num_queue_families);

            vkGetPhysicalDeviceQueueFamilyProperties(device, &num_queue_families, queue_families.data());

            for (uint32_t index = 0; const auto& queue_family : queue_families)
            {
                // Check that the GPU supports graphics computations and presentation
                if ((queue_family.queueFlags & VK_QUEUE_GRAPHICS_BIT) != 0
                    && cielim::window::Window::vk_get_presentation_support(this->vk_instance_, device, index)
                           .has_value())
                {
                    physical_device = device;
                    graphics_queue_family = index;
                    found_device = true;
                    break;
                }
                index++;
            }

            if (found_device)
                break;
        }

        // The physical device should've been found and the queue index should never reach max 32 bit value
        if (physical_device == nullptr || graphics_queue_family == std::numeric_limits<uint32_t>::max())
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::NoSupportedDevice),
                .detail = "",
            };

            return std::unexpected(error);
        }

        VkPhysicalDeviceProperties device_properties;
        vkGetPhysicalDeviceProperties(physical_device, &device_properties);

        cielim::utils::log::info(
            "Found device {} (graphics queue family {})", device_properties.deviceName, graphics_queue_family
        );

        VkPhysicalDeviceMemoryProperties memory_properties;
        vkGetPhysicalDeviceMemoryProperties(physical_device, &memory_properties);

        // Total heap size in bytes for device
        VkDeviceSize dev_local_bytes = 0;
        for (uint32_t i = 0; i < memory_properties.memoryHeapCount; i++)
        {
            if ((memory_properties.memoryHeaps[i].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) != 0)
                dev_local_bytes += memory_properties.memoryHeaps[i].size;
        }

        constexpr float BYTES_IN_GB = 1073741824.0f;

        cielim::utils::log::info("Device heap total: {:.2f} GB", static_cast<float>(dev_local_bytes) / BYTES_IN_GB);

        this->vk_physical_device_ = physical_device;
        this->queue_index_ = graphics_queue_family;

        return {};
    }

    [[nodiscard]] auto init_device() -> std::expected<void, cielim::error::DetailedError>
    {
        // List required Vulkan features

        /* TODO: Add checking for support for each feature, assuming support for basic features for now. */

        VkPhysicalDeviceVulkan11Features req_dev_vulkan11_features = {
            .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES,
            .shaderDrawParameters = VK_TRUE,
        };

        VkPhysicalDeviceVulkan12Features req_dev_vulkan12_features = {
            .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES,
            .pNext = &req_dev_vulkan11_features,
            .scalarBlockLayout = VK_TRUE,
            .timelineSemaphore = VK_TRUE,
            .bufferDeviceAddress = VK_TRUE,
        };

        VkPhysicalDeviceVulkan13Features req_dev_vulkan13_features = {
            .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES,
            .pNext = &req_dev_vulkan12_features,
            .synchronization2 = VK_TRUE,
            .dynamicRendering = VK_TRUE,
            .maintenance4 = VK_TRUE,
        };

        VkPhysicalDeviceVulkan14Features req_dev_vulkan14_features = {
            .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_4_FEATURES,
            .pNext = &req_dev_vulkan13_features,
        };

        VkPhysicalDeviceFeatures2 req_dev_features = {
            .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
            .pNext = &req_dev_vulkan14_features,
            .features = {
                .samplerAnisotropy = VK_TRUE,
            },
        };

        // Check if any required device extensions are missing

        std::vector<const char*> req_dev_extensions;

        req_dev_extensions.push_back("VK_KHR_swapchain"); // Required for image presentation to window
#ifdef __APPLE__
        req_dev_extensions.push_back("VK_KHR_portability_subset");
#endif

        uint32_t dev_ext_count = 0;
        vkEnumerateDeviceExtensionProperties(this->vk_physical_device_, nullptr, &dev_ext_count, nullptr);

        std::vector<VkExtensionProperties> dev_extensions(dev_ext_count);

        if (const auto result = vkEnumerateDeviceExtensionProperties(
                this->vk_physical_device_, nullptr, &dev_ext_count, dev_extensions.data()
            );
            result != VK_SUCCESS)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::EnumerateDeviceExtsError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        std::vector<const char*> missing_dev_extensions;

        for (const char* req_extension : req_dev_extensions)
        {
            bool found = false;

            for (const auto& [extension_name, spec_version] : dev_extensions)
            {
                if (std::strcmp(req_extension, extension_name) == 0)
                {
                    found = true;
                    break;
                }
            }

            if (!found)
                missing_dev_extensions.push_back(req_extension);
        }

        if (!missing_dev_extensions.empty())
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::MissingDeviceExt),
                .detail = fmt::format("{}", fmt::join(missing_dev_extensions, ", ")),
            };

            return std::unexpected(error);
        }

        float queue_priority = 1.0f;
        const VkDeviceQueueCreateInfo queue_info = {
            .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
            .queueFamilyIndex = this->queue_index_,
            .queueCount = 1,
            .pQueuePriorities = &queue_priority,
        };

        const VkDeviceCreateInfo device_info = {
            .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
            .pNext = &req_dev_features,
            .queueCreateInfoCount = 1,
            .pQueueCreateInfos = &queue_info,
            .enabledExtensionCount = static_cast<uint32_t>(req_dev_extensions.size()),
            .ppEnabledExtensionNames = req_dev_extensions.data(),
        };

        if (const auto result = vkCreateDevice(this->vk_physical_device_, &device_info, nullptr, &this->vk_device_);
            result != VK_SUCCESS)
        {
            cielim::error::DetailedError error = {
                .errc = make_error_code(cielim::error::VkContextError::DeviceCreateError),
                .detail = string_VkResult(result),
            };

            return std::unexpected(error);
        }

        volkLoadDevice(this->vk_device_);

        return {};
    }

    bool is_initialized_ = false;

#ifndef NDEBUG
    VkDebugUtilsMessengerEXT debug_messenger_ = nullptr; // Only included in debug builds
#endif
    VkInstance vk_instance_ = nullptr;
    VkSurfaceKHR vk_surface_ = nullptr;
    VkPhysicalDevice vk_physical_device_ = nullptr;
    uint32_t queue_index_ = 0;
    VkDevice vk_device_ = nullptr;
};

} // namespace cielim::vk::context
