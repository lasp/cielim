// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Serves as the program entry point. */

#include <cstdlib>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_vulkan.h>

#include <SDL3/SDL_main.h> // This has to be the last SDL include

import cielim.utils.log;

#ifndef NDEBUG
static VKAPI_ATTR auto VKAPI_CALL DebugCallback(
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
#endif

auto main(int argc, char* argv[]) -> int
{
    // Create vulkan specific log for validation layers
    cielim::utils::log::InitLog("log-vulkan");

    // Create default main log
    cielim::utils::log::InitLog("log-cielim");

    // Set global log format
    cielim::utils::log::set_pattern("[%Y-%m-%d %H:%M:%S.%e] %n - %^%l%$: %v");

    // Set lowest rendered level to trace i.e., everything is logged
    cielim::utils::log::set_level(cielim::utils::log::level::trace);

    // Flush warnings and above immediately instead of buffering
    cielim::utils::log::flush_on(cielim::utils::log::level::warn);

    if (volkInitialize() != VK_SUCCESS)
    {
        cielim::utils::log::critical("Volk failed to initialize!");
        return EXIT_FAILURE;
    }

    uint32_t vk_api_version = 0;
    const VkResult api_result = vkEnumerateInstanceVersion(&vk_api_version);

    if (api_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan loader could not be found: {}", string_VkResult(api_result));
        return EXIT_FAILURE;
    }

    cielim::utils::log::info(
        "Detected Vulkan loader API version: {}.{}.{}",
        VK_API_VERSION_MAJOR(vk_api_version),
        VK_API_VERSION_MINOR(vk_api_version),
        VK_API_VERSION_PATCH(vk_api_version)
    );

    // Require Vulkan 1.4+
    if (VK_API_VERSION_MAJOR(vk_api_version) < 1 || VK_API_VERSION_MINOR(vk_api_version) < 4)
    {
        cielim::utils::log::critical("Vulkan loader API version less than 1.4!");
        return EXIT_FAILURE;
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

    std::vector<const char*> req_inst_layers;

#ifndef NDEBUG
    req_inst_layers.push_back("VK_LAYER_KHRONOS_validation");
#endif

    uint32_t inst_layer_count = 0;
    vkEnumerateInstanceLayerProperties(&inst_layer_count, nullptr);

    std::vector<VkLayerProperties> inst_layers(inst_layer_count);

    const VkResult inst_layer_result = vkEnumerateInstanceLayerProperties(&inst_layer_count, inst_layers.data());

    if (inst_layer_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan instance layers could not be fetched!");
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
        cielim::utils::log::critical("Missing required instance layers: {}", fmt::join(missing_inst_layers, ", "));
        return EXIT_FAILURE;
    }

    std::vector<const char*> req_inst_extensions;

#ifndef NDEBUG
    req_inst_extensions.push_back("VK_EXT_debug_utils");
#endif

#ifdef __APPLE__
    req_inst_extensions.push_back("VK_KHR_portability_enumeration");
#endif

    uint32_t inst_ext_count = 0;
    vkEnumerateInstanceExtensionProperties(nullptr, &inst_ext_count, nullptr);

    std::vector<VkExtensionProperties> inst_extensions(inst_ext_count);

    const VkResult inst_ext_result
        = vkEnumerateInstanceExtensionProperties(nullptr, &inst_ext_count, inst_extensions.data());

    if (inst_ext_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan instance extensions could not be fetched!");
        return EXIT_FAILURE;
    }

    std::vector<const char*> missing_inst_extensions;

    for (const char* req_extension : req_inst_extensions)
    {
        bool found = false;

        for (const auto& extension : inst_extensions)
        {
            if (std::strcmp(req_extension, extension.extensionName) == 0)
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
        cielim::utils::log::critical(
            "Missing required instance extensions: {}", fmt::join(missing_inst_extensions, ", ")
        );
        return EXIT_FAILURE;
    }

#ifndef NDEBUG
    VkDebugUtilsMessengerCreateInfoEXT debug_messenger_create_info = {
        .sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
        .messageSeverity
        = VK_DEBUG_UTILS_MESSAGE_SEVERITY_VERBOSE_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT
        | VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT,
        .messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT,
        .pfnUserCallback = DebugCallback,
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

    VkInstance vk_instance;
    const VkResult instance_result = vkCreateInstance(&instance_create_info, nullptr, &vk_instance);

    if (instance_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Instance creation failed: {}", string_VkResult(instance_result));
        return EXIT_FAILURE;
    }

    volkLoadInstance(vk_instance); // Initialize Vulkan instance

#ifndef NDEBUG
    VkDebugUtilsMessengerEXT debug_messenger;
    const VkResult messenger_result
        = vkCreateDebugUtilsMessengerEXT(vk_instance, &debug_messenger_create_info, nullptr, &debug_messenger);

    if (messenger_result != VK_SUCCESS)
        cielim::utils::log::warn("Vulkan debug messenger couldn't be created");
#endif

    uint32_t num_devices = 0;
    vkEnumeratePhysicalDevices(vk_instance, &num_devices, nullptr);

    std::vector<VkPhysicalDevice> physical_devices(num_devices);

    const VkResult devices_result = vkEnumeratePhysicalDevices(vk_instance, &num_devices, physical_devices.data());

    if (devices_result != VK_SUCCESS || physical_devices.empty())
    {
        cielim::utils::log::critical("No physical devices found!");
        vkDestroyInstance(vk_instance, nullptr);
        return EXIT_FAILURE;
    }

    VkPhysicalDevice physical_device;
    uint32_t graphics_queue_family = -1;

    // Loop through all physical devices to find most suitable one
    for (const auto& device : physical_devices)
    {
        VkPhysicalDeviceProperties device_properties;
        vkGetPhysicalDeviceProperties(device, &device_properties);

        const uint32_t major = VK_API_VERSION_MAJOR(device_properties.apiVersion);
        const uint32_t minor = VK_API_VERSION_MINOR(device_properties.apiVersion);

        // Don't allow device that can't support Vulkan 1.4+
        if (major < 1 || minor < 4)
            continue;

        uint32_t num_queue_families = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(device, &num_queue_families, nullptr);

        std::vector<VkQueueFamilyProperties> queue_families(num_queue_families);

        vkGetPhysicalDeviceQueueFamilyProperties(device, &num_queue_families, queue_families.data());

        for (uint32_t index = 0; const auto& queue_family : queue_families)
        {
            // Check that the GPU supports graphics computations
            if ((queue_family.queueFlags & VK_QUEUE_GRAPHICS_BIT) != 0)
            {
                physical_device = device;
                graphics_queue_family = index; // We're just picking out the first graphics queue for everything
            }
            index++;
        }
    }

    if (physical_device == VK_NULL_HANDLE || graphics_queue_family < 0)
    {
        cielim::utils::log::critical("No device could be found that supports Vulkan 1.4+ and/or graphics queues!");
        vkDestroyInstance(vk_instance, nullptr);
        return EXIT_FAILURE;
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

    /* TODO: Add checking for support for each feature, assuming support for basic features for now. */

    VkPhysicalDeviceVulkan11Features req_dev_vulkan11_features = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES,
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

    std::vector<const char*> req_dev_extensions;

#ifdef __APPLE__
    req_dev_extensions.push_back("VK_KHR_portability_subset");
#endif

    uint32_t dev_ext_count = 0;
    vkEnumerateDeviceExtensionProperties(physical_device, nullptr, &dev_ext_count, nullptr);

    std::vector<VkExtensionProperties> dev_extensions(dev_ext_count);

    const VkResult dev_ext_result
        = vkEnumerateDeviceExtensionProperties(physical_device, nullptr, &dev_ext_count, dev_extensions.data());

    if (dev_ext_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan device extensions could not be fetched!");
#ifndef NDEBUG
        if (debug_messenger != VK_NULL_HANDLE)
            vkDestroyDebugUtilsMessengerEXT(vk_instance, debug_messenger, nullptr);
#endif
        vkDestroyInstance(vk_instance, nullptr);
        return EXIT_FAILURE;
    }

    std::vector<const char*> missing_dev_extensions;

    for (const char* req_extension : req_dev_extensions)
    {
        bool found = false;

        for (const auto& extension : dev_extensions)
        {
            if (std::strcmp(req_extension, extension.extensionName) == 0)
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
        cielim::utils::log::critical("Missing required device extensions: {}", fmt::join(missing_dev_extensions, ", "));
#ifndef NDEBUG
        if (debug_messenger != VK_NULL_HANDLE)
            vkDestroyDebugUtilsMessengerEXT(vk_instance, debug_messenger, nullptr);
#endif
        vkDestroyInstance(vk_instance, nullptr);
        return EXIT_FAILURE;
    }

    float queue_priority = 1.0f;
    const VkDeviceQueueCreateInfo queue_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = graphics_queue_family,
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

    VkDevice device;
    const VkResult device_result = vkCreateDevice(physical_device, &device_info, nullptr, &device);

    if (device_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Device creation failed: {}", string_VkResult(device_result));
#ifndef NDEBUG
        if (debug_messenger != VK_NULL_HANDLE)
            vkDestroyDebugUtilsMessengerEXT(vk_instance, debug_messenger, nullptr);
#endif
        vkDestroyInstance(vk_instance, nullptr);
        return EXIT_FAILURE;
    }

    volkLoadDevice(device);

    // Check that we can acquire the queue
    VkQueue graphics_queue;
    vkGetDeviceQueue(device, graphics_queue_family, 0, &graphics_queue);
    (void)graphics_queue;

#ifndef NDEBUG
    if (debug_messenger != VK_NULL_HANDLE)
        vkDestroyDebugUtilsMessengerEXT(vk_instance, debug_messenger, nullptr);
#endif
    vkDestroyDevice(device, nullptr);
    vkDestroyInstance(vk_instance, nullptr);

    SDL_Quit();

    return EXIT_SUCCESS;
}
