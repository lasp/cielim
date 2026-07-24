// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Serves as the program entry point. */

#include <algorithm>
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

static VkDebugUtilsMessengerEXT debug_messenger;
#endif

static SDL_Window* window;
static VkInstance vk_instance;
static VkSurfaceKHR surface;
static VkDevice device;
static VkSwapchainKHR swapchain;
static std::vector<VkImage> swapchain_images;
static std::vector<VkImageView> swapchain_views;

// Clean up Vulkan resources
static auto Clean() -> void
{
#ifndef NDEBUG
    if (debug_messenger != VK_NULL_HANDLE)
        vkDestroyDebugUtilsMessengerEXT(vk_instance, debug_messenger, nullptr);
#endif

    for (const auto& view : swapchain_views)
    {
        if (view != VK_NULL_HANDLE)
            vkDestroyImageView(device, view, nullptr);
    }

    if (swapchain != VK_NULL_HANDLE)
        vkDestroySwapchainKHR(device, swapchain, nullptr);

    if (device != VK_NULL_HANDLE)
        vkDestroyDevice(device, nullptr);

    if (surface != VK_NULL_HANDLE)
        vkDestroySurfaceKHR(vk_instance, surface, nullptr);

    if (vk_instance != VK_NULL_HANDLE)
        vkDestroyInstance(vk_instance, nullptr);

    if (window != nullptr)
        SDL_DestroyWindow(window);
}

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

    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS))
    {
        cielim::utils::log::critical("SDL failed to initialize: {}", SDL_GetError());
        return EXIT_FAILURE;
    }

    if (volkInitialize() != VK_SUCCESS)
    {
        cielim::utils::log::critical("Volk failed to initialize!");
        return EXIT_FAILURE;
    }

    constexpr int WINDOW_WIDTH = 1280;
    constexpr int WINDOW_HEIGHT = 720;

    window = SDL_CreateWindow("cielim", WINDOW_WIDTH, WINDOW_HEIGHT, SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE);

    if (window == nullptr)
    {
        cielim::utils::log::critical("SDL failed to create window: {}", SDL_GetError());
        return EXIT_FAILURE;
    }

    VkResult vk_result;

    uint32_t vk_api_version = 0;
    vk_result = vkEnumerateInstanceVersion(&vk_api_version);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan loader could not be found: {}", string_VkResult(vk_result));
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

    vk_result = vkEnumerateInstanceLayerProperties(&inst_layer_count, inst_layers.data());

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan instance layers could not be fetched!");
        return EXIT_FAILURE;
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

    uint32_t sdl_extension_count = 0;
    const char* const* sdl_extensions = SDL_Vulkan_GetInstanceExtensions(&sdl_extension_count);

    if (sdl_extensions == nullptr)
    {
        cielim::utils::log::critical("SDL failed to fetch instance extensions: {}", SDL_GetError());
        return EXIT_FAILURE;
    }

    req_inst_extensions.assign(sdl_extensions, sdl_extensions + sdl_extension_count);

#ifndef NDEBUG
    req_inst_extensions.push_back("VK_EXT_debug_utils");
#endif

#ifdef __APPLE__
    req_inst_extensions.push_back("VK_KHR_portability_enumeration");
#endif

    uint32_t inst_ext_count = 0;
    vkEnumerateInstanceExtensionProperties(nullptr, &inst_ext_count, nullptr);

    std::vector<VkExtensionProperties> inst_extensions(inst_ext_count);

    vk_result = vkEnumerateInstanceExtensionProperties(nullptr, &inst_ext_count, inst_extensions.data());

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan instance extensions could not be fetched!");
        return EXIT_FAILURE;
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

    vk_result = vkCreateInstance(&instance_create_info, nullptr, &vk_instance);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Instance creation failed: {}", string_VkResult(vk_result));
        Clean();
        return EXIT_FAILURE;
    }

    volkLoadInstance(vk_instance); // Initialize Vulkan instance

#ifndef NDEBUG
    vk_result = vkCreateDebugUtilsMessengerEXT(vk_instance, &debug_messenger_create_info, nullptr, &debug_messenger);

    if (vk_result != VK_SUCCESS)
        cielim::utils::log::warn("Vulkan debug messenger couldn't be created");
#endif

    SDL_Vulkan_CreateSurface(window, vk_instance, nullptr, &surface);

    if (surface == VK_NULL_HANDLE)
    {
        cielim::utils::log::critical("Vulkan surface could not be created!");
        Clean();
        return EXIT_FAILURE;
    }

    uint32_t num_devices = 0;
    vkEnumeratePhysicalDevices(vk_instance, &num_devices, nullptr);

    std::vector<VkPhysicalDevice> physical_devices(num_devices);

    vk_result = vkEnumeratePhysicalDevices(vk_instance, &num_devices, physical_devices.data());

    if (vk_result != VK_SUCCESS || physical_devices.empty())
    {
        cielim::utils::log::critical("No physical devices found!");
        Clean();
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
            if ((queue_family.queueFlags & VK_QUEUE_GRAPHICS_BIT) != 0
                && SDL_Vulkan_GetPresentationSupport(vk_instance, device, index))
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
        Clean();
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

    req_dev_extensions.push_back("VK_KHR_swapchain");

#ifdef __APPLE__
    req_dev_extensions.push_back("VK_KHR_portability_subset");
#endif

    uint32_t dev_ext_count = 0;
    vkEnumerateDeviceExtensionProperties(physical_device, nullptr, &dev_ext_count, nullptr);

    std::vector<VkExtensionProperties> dev_extensions(dev_ext_count);

    vk_result = vkEnumerateDeviceExtensionProperties(physical_device, nullptr, &dev_ext_count, dev_extensions.data());

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Vulkan device extensions could not be fetched!");
        Clean();
        return EXIT_FAILURE;
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
        cielim::utils::log::critical("Missing required device extensions: {}", fmt::join(missing_dev_extensions, ", "));
        Clean();
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

    vk_result = vkCreateDevice(physical_device, &device_info, nullptr, &device);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Device creation failed: {}", string_VkResult(vk_result));
        Clean();
        return EXIT_FAILURE;
    }

    volkLoadDevice(device);

    VkSurfaceCapabilitiesKHR surface_capabilities;
    vk_result = vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical_device, surface, &surface_capabilities);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Surface capabilities could not be fetched!");
        Clean();
        return EXIT_FAILURE;
    }

    uint32_t surface_format_count = 0;
    vkGetPhysicalDeviceSurfaceFormatsKHR(physical_device, surface, &surface_format_count, nullptr);

    std::vector<VkSurfaceFormatKHR> surface_formats(surface_format_count);

    vk_result
        = vkGetPhysicalDeviceSurfaceFormatsKHR(physical_device, surface, &surface_format_count, surface_formats.data());

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Surface formats could not be fetched!");
        Clean();
        return EXIT_FAILURE;
    }

    if (surface_formats.empty())
    {
        cielim::utils::log::critical("No available surface formats!");
        Clean();
        return EXIT_FAILURE;
    }

    VkFormat req_format = VK_FORMAT_B8G8R8A8_SRGB;
    VkColorSpaceKHR req_color_space = VK_COLOR_SPACE_SRGB_NONLINEAR_KHR;

    bool found_format = false;
    for (const auto& [format, color_space] : surface_formats)
    {
        if (format == req_format && color_space == req_color_space)
            found_format = true;
    }

    if (!found_format)
    {
        cielim::utils::log::critical("Required surface format is not supported!");
        Clean();
        return EXIT_FAILURE;
    }

    // We'll skip querying present modes and use VK_PRESENT_MODE_FIFO_KHR which is always present
    VkPresentModeKHR req_present_mode = VK_PRESENT_MODE_FIFO_KHR;

    VkExtent2D req_extent;

    if (surface_capabilities.currentExtent.width == std::numeric_limits<uint32_t>::max())
    {
        req_extent.width = WINDOW_WIDTH;
        req_extent.height = WINDOW_HEIGHT;
    }
    else
    {
        req_extent = surface_capabilities.currentExtent;
    }

    req_extent.width = std::clamp<uint32_t>(
        req_extent.width, surface_capabilities.minImageExtent.width, surface_capabilities.maxImageExtent.width
    );
    req_extent.height = std::clamp<uint32_t>(
        req_extent.height, surface_capabilities.minImageExtent.height, surface_capabilities.maxImageExtent.height
    );

    uint32_t min_image_count = surface_capabilities.minImageCount;

    if (surface_capabilities.maxImageCount > 0 && min_image_count > surface_capabilities.maxImageCount)
        min_image_count = surface_capabilities.maxImageCount;

    VkSwapchainCreateInfoKHR swap_chain_create_info = {
        .sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,
        .surface = surface,
        .minImageCount = min_image_count,
        .imageFormat = req_format,
        .imageColorSpace = req_color_space,
        .imageExtent = req_extent,
        .imageArrayLayers = 1,
        .imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        .preTransform = VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,
        .compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
        .presentMode = req_present_mode,
    };

    vk_result = vkCreateSwapchainKHR(device, &swap_chain_create_info, nullptr, &swapchain);

    if (swapchain == VK_NULL_HANDLE)
    {
        cielim::utils::log::critical("Swap-chain creation failed: {}", string_VkResult(vk_result));
        Clean();
        return EXIT_FAILURE;
    }

    uint32_t image_count = 0;
    vkGetSwapchainImagesKHR(device, swapchain, &image_count, nullptr);

    swapchain_images.resize(image_count);
    swapchain_views.resize(image_count);

    vkGetSwapchainImagesKHR(device, swapchain, &image_count, swapchain_images.data());

    VkImageViewCreateInfo image_view_create_info = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
        .viewType = VK_IMAGE_VIEW_TYPE_2D,
        .format = req_format,
        .subresourceRange = {.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT, .levelCount = 1, .layerCount = 1},
    };

    for (int i = 0; auto& image : swapchain_images)
    {
        image_view_create_info.image = image;
        vk_result = vkCreateImageView(device, &image_view_create_info, nullptr, &swapchain_views[i]);

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Image view creation failed: {}", string_VkResult(vk_result));
            Clean();
            return EXIT_FAILURE;
        }
        i++;
    }

    // Check that we can acquire the queue
    VkQueue graphics_queue;
    vkGetDeviceQueue(device, graphics_queue_family, 0, &graphics_queue);
    (void)graphics_queue;

    bool is_running = true;

    while (is_running)
    {
        SDL_Event event;
        while (SDL_PollEvent(&event))
        {
            switch (event.type)
            {
            case SDL_EVENT_QUIT: is_running = false; break;
            default: break;
            }
        }
    }

    Clean();

    SDL_Quit();

    return EXIT_SUCCESS;
}
