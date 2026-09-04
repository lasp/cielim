// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Serves as the program entry point. */

#include <algorithm>
#include <cstdlib>
#include <expected>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_vulkan.h>

#include <SDL3/SDL_main.h> // This has to be the last SDL include

import cielim.error;
import cielim.utils;
import cielim.window;

#ifndef NDEBUG
static VKAPI_ATTR auto VKAPI_CALL debug_callback(
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

static VkInstance vk_instance = VK_NULL_HANDLE;
static VkSurfaceKHR surface = VK_NULL_HANDLE;
static VkDevice device = VK_NULL_HANDLE;
static VkSwapchainKHR swapchain = VK_NULL_HANDLE;
static std::vector<VkImage> swapchain_images;
static std::vector<VkImageView> swapchain_views;
static VkShaderModule shader_module = VK_NULL_HANDLE; // Single shader for now
static VkPipelineLayout pipeline_layout = VK_NULL_HANDLE;
static VkPipeline graphics_pipeline = VK_NULL_HANDLE;
static std::vector<VkCommandPool> command_pools;
static std::vector<VkCommandBuffer> command_buffers;
static VkSemaphore timeline_semaphore = VK_NULL_HANDLE;
static std::vector<VkSemaphore> acquire_semaphores;
static std::vector<VkSemaphore> render_finished_semaphores;

// Clean up Vulkan resources
static auto clean() -> void
{
#ifndef NDEBUG
    if (debug_messenger != VK_NULL_HANDLE)
        vkDestroyDebugUtilsMessengerEXT(vk_instance, debug_messenger, nullptr);
#endif

    for (const auto& semaphore : render_finished_semaphores)
    {
        if (semaphore != VK_NULL_HANDLE)
            vkDestroySemaphore(device, semaphore, nullptr);
    }

    for (const auto& semaphore : acquire_semaphores)
    {
        if (semaphore != VK_NULL_HANDLE)
            vkDestroySemaphore(device, semaphore, nullptr);
    }

    if (timeline_semaphore != VK_NULL_HANDLE)
        vkDestroySemaphore(device, timeline_semaphore, nullptr);

    for (const auto& pool : command_pools)
    {
        if (pool != VK_NULL_HANDLE)
            vkDestroyCommandPool(device, pool, nullptr);
    }

    if (graphics_pipeline != VK_NULL_HANDLE)
        vkDestroyPipeline(device, graphics_pipeline, nullptr);

    if (pipeline_layout != VK_NULL_HANDLE)
        vkDestroyPipelineLayout(device, pipeline_layout, nullptr);

    if (shader_module != VK_NULL_HANDLE)
        vkDestroyShaderModule(device, shader_module, nullptr);

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
}

auto main(int argc, char* argv[]) -> int
{
    // Create vulkan specific log for validation layers
    cielim::utils::log::init_log("log-vulkan");

    // Create default main log
    cielim::utils::log::init_log("log-cielim");

    // Set global log format
    cielim::utils::log::set_pattern("[%Y-%m-%d %H:%M:%S.%e] %n - %^%l%$: %v");

    // Set lowest rendered level to trace i.e., everything is logged
    cielim::utils::log::set_level(cielim::utils::log::level::trace);

    // Flush warnings and above immediately instead of buffering
    cielim::utils::log::flush_on(cielim::utils::log::level::warn);

    const char* base_path_raw = SDL_GetBasePath();

    if (base_path_raw == nullptr)
    {
        cielim::utils::log::critical("Executable location could not be found: {}", SDL_GetError());
        return EXIT_FAILURE;
    }

    std::filesystem::path base_path(base_path_raw);

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

    auto window = cielim::window::Window();

    auto win_result
        = window.create_window("cielim", WINDOW_WIDTH, WINDOW_HEIGHT, SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE);

    if (!win_result)
    {
        cielim::utils::log::critical(win_result.error().message());
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

    auto ext_result = cielim::window::Window::vk_get_extensions();

    if (!ext_result)
    {
        cielim::utils::log::critical(ext_result.error().message());
        return EXIT_FAILURE;
    }

    std::vector<const char*> req_inst_extensions = ext_result.value();

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

    vk_result = vkCreateInstance(&instance_create_info, nullptr, &vk_instance);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Instance creation failed: {}", string_VkResult(vk_result));
        clean();
        return EXIT_FAILURE;
    }

    volkLoadInstance(vk_instance); // Initialize Vulkan instance

#ifndef NDEBUG
    vk_result = vkCreateDebugUtilsMessengerEXT(vk_instance, &debug_messenger_create_info, nullptr, &debug_messenger);

    if (vk_result != VK_SUCCESS)
        cielim::utils::log::warn("Vulkan debug messenger couldn't be created");
#endif

    auto surface_result = window.vk_create_surface(vk_instance, &surface);

    if (!surface_result)
    {
        cielim::utils::log::critical(surface_result.error().message());
        clean();
        return EXIT_FAILURE;
    }

    uint32_t num_devices = 0;
    vkEnumeratePhysicalDevices(vk_instance, &num_devices, nullptr);

    std::vector<VkPhysicalDevice> physical_devices(num_devices);

    vk_result = vkEnumeratePhysicalDevices(vk_instance, &num_devices, physical_devices.data());

    if (vk_result != VK_SUCCESS || physical_devices.empty())
    {
        cielim::utils::log::critical("No physical devices found!");
        clean();
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
                && cielim::window::Window::vk_get_presentation_support(vk_instance, device, index))
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
        clean();
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
        clean();
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
        clean();
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
        clean();
        return EXIT_FAILURE;
    }

    volkLoadDevice(device);

    VkSurfaceCapabilitiesKHR surface_capabilities;
    vk_result = vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical_device, surface, &surface_capabilities);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Surface capabilities could not be fetched!");
        clean();
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
        clean();
        return EXIT_FAILURE;
    }

    if (surface_formats.empty())
    {
        cielim::utils::log::critical("No available surface formats!");
        clean();
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
        clean();
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
        clean();
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
            clean();
            return EXIT_FAILURE;
        }
        i++;
    }

    std::filesystem::path triangle_shader_path = base_path / "content" / "shaders" / "triangle.spv";

    auto triangle_shader = cielim::utils::file::read_file32(triangle_shader_path);

    if (!triangle_shader.has_value())
    {
        cielim::utils::log::error(
            "Shader {} could not be opened: {}", triangle_shader_path.string(), triangle_shader.error().message()
        );
        clean();
        return EXIT_FAILURE;
    }

    VkShaderModuleCreateInfo shader_module_create_info = {
        .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = triangle_shader->size() * sizeof(uint32_t),
        .pCode = triangle_shader->data(),
    };

    vk_result = vkCreateShaderModule(device, &shader_module_create_info, nullptr, &shader_module);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::error("Shader module could not be created: {}", string_VkResult(vk_result));
        clean();
        return EXIT_FAILURE;
    }

    VkPipelineShaderStageCreateInfo vertex_stage_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_VERTEX_BIT,
        .module = shader_module,
        .pName = "VertMain",
    };

    VkPipelineShaderStageCreateInfo frag_stage_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_FRAGMENT_BIT,
        .module = shader_module,
        .pName = "FragMain",
    };

    VkPipelineShaderStageCreateInfo shader_stages[] = {vertex_stage_info, frag_stage_info};

    // Empty for now because of shader hard-coding vertex buffer
    VkPipelineVertexInputStateCreateInfo vertex_input_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
    };

    VkPipelineInputAssemblyStateCreateInfo input_assembly_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
        .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP,
    };

    VkPipelineViewportStateCreateInfo viewport_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
        .viewportCount = 1,
        .scissorCount = 1,
    };

    VkPipelineRasterizationStateCreateInfo rasterization_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
        .depthClampEnable = VK_FALSE,
        .rasterizerDiscardEnable = VK_FALSE,
        .polygonMode = VK_POLYGON_MODE_FILL,
        .cullMode = VK_CULL_MODE_BACK_BIT,
        .frontFace = VK_FRONT_FACE_CLOCKWISE,
        .depthBiasEnable = VK_FALSE,
        .lineWidth = 1.0f,
    };

    VkPipelineMultisampleStateCreateInfo multisample_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
        .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT,
        .sampleShadingEnable = VK_FALSE,
    };

    VkPipelineColorBlendAttachmentState color_blend_attachment_state = {
        .blendEnable = VK_TRUE,
        .srcColorBlendFactor = VK_BLEND_FACTOR_SRC_ALPHA,
        .dstColorBlendFactor = VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA,
        .colorBlendOp = VK_BLEND_OP_ADD,
        .srcAlphaBlendFactor = VK_BLEND_FACTOR_ONE,
        .dstAlphaBlendFactor = VK_BLEND_FACTOR_ZERO,
        .alphaBlendOp = VK_BLEND_OP_ADD,
        .colorWriteMask
        = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT | VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT,
    };

    VkPipelineColorBlendStateCreateInfo color_blend_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
        .logicOpEnable = VK_FALSE,
        .logicOp = VK_LOGIC_OP_COPY,
        .attachmentCount = 1,
        .pAttachments = &color_blend_attachment_state,
    };

    // This is empty because no uniforms are used yet
    VkPipelineLayoutCreateInfo layout_create_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 0,
        .pushConstantRangeCount = 0,
    };

    vk_result = vkCreatePipelineLayout(device, &layout_create_info, nullptr, &pipeline_layout);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Pipeline layout could not be created: {}", string_VkResult(vk_result));
        clean();
        return EXIT_FAILURE;
    }

    std::vector<VkDynamicState> dynamic_states = {VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR};

    VkPipelineDynamicStateCreateInfo dynamic_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
        .dynamicStateCount = static_cast<uint32_t>(dynamic_states.size()),
        .pDynamicStates = dynamic_states.data(),
    };

    VkPipelineRenderingCreateInfo pipeline_rendering_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO,
        .colorAttachmentCount = 1,
        .pColorAttachmentFormats = &req_format,
    };

    VkGraphicsPipelineCreateInfo pipeline_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .pNext = &pipeline_rendering_state,
        .stageCount = 2,
        .pStages = shader_stages,
        .pVertexInputState = &vertex_input_state,
        .pInputAssemblyState = &input_assembly_state,
        .pViewportState = &viewport_state,
        .pRasterizationState = &rasterization_state,
        .pMultisampleState = &multisample_state,
        .pColorBlendState = &color_blend_state,
        .pDynamicState = &dynamic_state,
        .layout = pipeline_layout,
        .renderPass = nullptr,
    };

    vk_result = vkCreateGraphicsPipelines(device, nullptr, 1, &pipeline_info, nullptr, &graphics_pipeline);

    if (vk_result != VK_SUCCESS)
    {
        cielim::utils::log::critical("Graphics pipeline could not be created: {}", string_VkResult(vk_result));
        clean();
        return EXIT_FAILURE;
    }

    constexpr uint32_t MAX_FRAMES_IN_FLIGHT = 2;

    command_pools.resize(MAX_FRAMES_IN_FLIGHT);
    command_buffers.resize(MAX_FRAMES_IN_FLIGHT);

    for (uint32_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++)
    {
        VkCommandPoolCreateInfo command_pool_create_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
            .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
            .queueFamilyIndex = graphics_queue_family,
        };

        vk_result = vkCreateCommandPool(device, &command_pool_create_info, nullptr, &command_pools[i]);

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Command pool could not be created: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferAllocateInfo command_buffer_allocate_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
            .commandPool = command_pools[i],
            .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
            .commandBufferCount = 1,
        };

        vk_result = vkAllocateCommandBuffers(device, &command_buffer_allocate_info, &command_buffers[i]);

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Command buffer could not be allocated: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }
    }

    VkSemaphoreTypeCreateInfo timeline_semaphore_type_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,
        .semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE,
        .initialValue = 0,
    };

    VkSemaphoreCreateInfo timeline_semaphore_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
        .pNext = &timeline_semaphore_type_info,
    };

    vkCreateSemaphore(device, &timeline_semaphore_info, nullptr, &timeline_semaphore);

    VkSemaphoreCreateInfo binary_semaphore_info = {
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
    };

    acquire_semaphores.resize(MAX_FRAMES_IN_FLIGHT);

    for (auto& semaphore : acquire_semaphores)
    {
        vk_result = vkCreateSemaphore(device, &binary_semaphore_info, nullptr, &semaphore); // One per frame-in-flight

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Binary semaphore failed to be created: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }
    }

    render_finished_semaphores.resize(image_count);

    for (auto& semaphore : render_finished_semaphores)
    {
        vk_result = vkCreateSemaphore(device, &binary_semaphore_info, nullptr, &semaphore); // One per swapchain image

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Binary semaphore failed to be created: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }
    }

    VkQueue graphics_queue;
    vkGetDeviceQueue(device, graphics_queue_family, 0, &graphics_queue);

    uint64_t frame_counter = 0;

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

        frame_counter++;

        const uint32_t frame_index = (frame_counter - 1) % MAX_FRAMES_IN_FLIGHT;

        if (frame_counter > MAX_FRAMES_IN_FLIGHT)
        {
            uint64_t wait_value = frame_counter - MAX_FRAMES_IN_FLIGHT;

            VkSemaphoreWaitInfo wait_info = {
                .sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
                .semaphoreCount = 1,
                .pSemaphores = &timeline_semaphore,
                .pValues = &wait_value,
            };

            vk_result = vkWaitSemaphores(device, &wait_info, UINT64_MAX);

            if (vk_result != VK_SUCCESS)
            {
                cielim::utils::log::critical("Failed waiting on timeline semaphore: {}", string_VkResult(vk_result));
                clean();
                return EXIT_FAILURE;
            }
        }

        uint32_t image_index;

        vk_result = vkAcquireNextImageKHR(
            device, swapchain, UINT64_MAX, acquire_semaphores[frame_index], nullptr, &image_index
        );

        if (vk_result == VK_ERROR_OUT_OF_DATE_KHR)
        {
            cielim::utils::log::warn("Swapchain out of date on acquire, skipping frame");
            frame_counter--;
            continue;
        }

        if (vk_result != VK_SUCCESS && vk_result != VK_SUBOPTIMAL_KHR)
        {
            cielim::utils::log::critical("Failed to acquire swapchain image: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }

        vk_result = vkResetCommandPool(device, command_pools[frame_index], 0);

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Failed to reset command pool: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferBeginInfo begin_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        };

        vk_result = vkBeginCommandBuffer(command_buffers[frame_index], &begin_info);

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Failed to begin command buffer: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }

        // This can be reused after each command recording
        VkImageMemoryBarrier2 barrier = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
            .srcStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            .srcAccessMask = {},
            .dstStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            .dstAccessMask = VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
            .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = swapchain_images[image_index],
            .subresourceRange = {
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };

        // Same for this
        VkDependencyInfo dependency_info = {
            .sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
            .dependencyFlags = {},
            .imageMemoryBarrierCount = 1,
            .pImageMemoryBarriers = &barrier,
        };

        vkCmdPipelineBarrier2(command_buffers[frame_index], &dependency_info);

        VkClearValue clear_color = {{0.12f, 0.12f, 0.12f, 1.0f}};

        VkRenderingAttachmentInfo rendering_attachment_info = {
            .sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO,
            .imageView = swapchain_views[image_index],
            .imageLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR,
            .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
            .clearValue = clear_color,
        };

        VkRenderingInfo rendering_info = {
            .sType = VK_STRUCTURE_TYPE_RENDERING_INFO,
            .renderArea = {.offset = {.x = 0, .y = 0}, .extent = req_extent},
            .layerCount = 1,
            .colorAttachmentCount = 1,
            .pColorAttachments = &rendering_attachment_info,
        };

        vkCmdBeginRendering(command_buffers[frame_index], &rendering_info);

        vkCmdBindPipeline(command_buffers[frame_index], VK_PIPELINE_BIND_POINT_GRAPHICS, graphics_pipeline);

        VkViewport viewport = {
            .x = 0.0f,
            .y = 0.0f,
            .width = static_cast<float>(req_extent.width),
            .height = static_cast<float>(req_extent.height),
            .minDepth = 0.0f,
            .maxDepth = 0.0f,
        };

        VkRect2D scissor = {
            .offset = {.x = 0, .y = 0},
            .extent = req_extent,
        };

        vkCmdSetViewport(command_buffers[frame_index], 0, 1, &viewport);
        vkCmdSetScissor(command_buffers[frame_index], 0, 1, &scissor);

        vkCmdDraw(command_buffers[frame_index], 3, 1, 0, 0);

        vkCmdEndRendering(command_buffers[frame_index]);

        barrier = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
            .srcStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            .srcAccessMask = VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
            .dstStageMask = VK_PIPELINE_STAGE_2_BOTTOM_OF_PIPE_BIT,
            .dstAccessMask = {},
            .oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .newLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = swapchain_images[image_index],
            .subresourceRange = {
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };

        dependency_info = {
            .sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
            .dependencyFlags = {},
            .imageMemoryBarrierCount = 1,
            .pImageMemoryBarriers = &barrier,
        };

        vkCmdPipelineBarrier2(command_buffers[frame_index], &dependency_info);

        vk_result = vkEndCommandBuffer(command_buffers[frame_index]);

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Failed to end command buffer: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }

        VkCommandBufferSubmitInfo buffer_submit_info = {
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
            .commandBuffer = command_buffers[frame_index],
        };

        VkSemaphoreSubmitInfo wait_binary_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = acquire_semaphores[frame_index],
            .stageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
        };

        VkSemaphoreSubmitInfo signal_binary_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = render_finished_semaphores[image_index],
            .stageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
        };

        VkSemaphoreSubmitInfo signal_timeline_info = {
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_SUBMIT_INFO,
            .semaphore = timeline_semaphore,
            .value = frame_counter,
            .stageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT,
        };

        VkSemaphoreSubmitInfo wait_semaphores[] = {wait_binary_info};
        VkSemaphoreSubmitInfo signal_semaphores[] = {signal_binary_info, signal_timeline_info};

        VkSubmitInfo2 submit_info = {
            .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO_2,
            .waitSemaphoreInfoCount = 1,
            .pWaitSemaphoreInfos = wait_semaphores,
            .commandBufferInfoCount = 1,
            .pCommandBufferInfos = &buffer_submit_info,
            .signalSemaphoreInfoCount = 2,
            .pSignalSemaphoreInfos = signal_semaphores,
        };

        vk_result = vkQueueSubmit2(graphics_queue, 1, &submit_info, nullptr);

        if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Failed to submit command buffer: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }

        VkPresentInfoKHR present_info = {
            .sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,
            .waitSemaphoreCount = 1,
            .pWaitSemaphores = &render_finished_semaphores[image_index],
            .swapchainCount = 1,
            .pSwapchains = &swapchain,
            .pImageIndices = &image_index,
        };

        vk_result = vkQueuePresentKHR(graphics_queue, &present_info);

        if (vk_result == VK_ERROR_OUT_OF_DATE_KHR || vk_result == VK_SUBOPTIMAL_KHR)
        {
            cielim::utils::log::warn("Swapchain out of date or suboptimal for presentation");
        }
        else if (vk_result != VK_SUCCESS)
        {
            cielim::utils::log::critical("Failed to present swapchain image: {}", string_VkResult(vk_result));
            clean();
            return EXIT_FAILURE;
        }
    }

    vkDeviceWaitIdle(device);

    clean();

    SDL_Quit();

    return EXIT_SUCCESS;
}
