// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Serves as the program entry point. */

#define VULKAN_HPP_NO_CONSTRUCTORS           // Allows C++20 designated initializers usage instead of positional args
#define VULKAN_HPP_NO_SETTERS                // Don't need these because we have designated initializers
#define VULKAN_HPP_NO_SMART_HANDLE           // Ownership is handled manually and by the VMA
#define VULKAN_HPP_NO_EXCEPTIONS             // Exceptions can degrade runtime performance, don't need them here
#define VULKAN_HPP_DISPATCH_LOADER_DYNAMIC 1 // Use dynamic loading of Vulkan functions and extension instead of static
#include <vulkan/vulkan.hpp>

VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE

import cielim.utils.log;

auto main() -> int
{
    // Create main log
    cielim::utils::log::InitLog("log-cielim");

    // Set global log format
    cielim::utils::log::set_pattern("[%Y-%m-%d %H:%M:%S.%e] %n - %^%l%$: %v");

    // Set lowest rendered level to trace i.e., everything is logged
    cielim::utils::log::set_level(cielim::utils::log::level::trace);

    // Flush warnings and above immediately instead of buffering
    cielim::utils::log::flush_on(cielim::utils::log::level::warn);

    VULKAN_HPP_DEFAULT_DISPATCHER.init(); // Initialize Vulkan Core

    const auto [api_result, vulkan_api_version] = vk::enumerateInstanceVersion();

    if (api_result != vk::Result::eSuccess)
    {
        cielim::utils::log::critical("Vulkan loader could not be found: {}", vk::to_string(api_result));
        return -1;
    }

    cielim::utils::log::info(
        "Detected Vulkan loader API version: {}.{}.{}",
        VK_API_VERSION_MAJOR(vulkan_api_version),
        VK_API_VERSION_MINOR(vulkan_api_version),
        VK_API_VERSION_PATCH(vulkan_api_version)
    );

    // Require Vulkan 1.4+
    if (VK_API_VERSION_MAJOR(vulkan_api_version) < 1 || VK_API_VERSION_MINOR(vulkan_api_version) < 4)
    {
        cielim::utils::log::critical("Vulkan loader API version less than 1.4!");
        return -1;
    }

    // Setup application info
    constexpr vk::ApplicationInfo APP_INFO = {
        .pApplicationName = "Cielim",
        .applicationVersion = VK_MAKE_VERSION(0, 1, 0),
        .pEngineName = "CielimEngine",
        .engineVersion = VK_MAKE_VERSION(0, 1, 0),
        .apiVersion = VK_API_VERSION_1_4,
    };

    uint32_t inst_ext_count = 0;
    auto inst_ext_result = vk::enumerateInstanceExtensionProperties(nullptr, &inst_ext_count, nullptr);

    if (inst_ext_result != vk::Result::eSuccess)
    {
        cielim::utils::log::critical("Vulkan instance extension count could not be fetched!");
        return -1;
    }

    std::vector<vk::ExtensionProperties> inst_extensions(inst_ext_count);

    inst_ext_result = vk::enumerateInstanceExtensionProperties(nullptr, &inst_ext_count, inst_extensions.data());

    if (inst_ext_result != vk::Result::eSuccess)
    {
        cielim::utils::log::critical("Vulkan instance extensions could not be fetched!");
        return -1;
    }

#ifdef __APPLE__
    bool found_portable = false;
    for (uint32_t i = 0; i < inst_ext_count; i++)
    {
        if (strcmp(VK_KHR_PORTABILITY_ENUMERATION_EXTENSION_NAME, inst_extensions[i].extensionName) == 0)
        {
            found_portable = true;
            break;
        }
    }

    if (!found_portable)
    {
        cielim::utils::log::critical("MoltenVK portability extension is not supported!");
        return -1;
    }

    std::vector<const char*> instance_extensions;
    instance_extensions.push_back(VK_KHR_PORTABILITY_ENUMERATION_EXTENSION_NAME);

    vk::InstanceCreateInfo instance_create_info = {
        .flags = vk::InstanceCreateFlagBits::eEnumeratePortabilityKHR,
        .pApplicationInfo = &APP_INFO,
        .enabledExtensionCount = static_cast<uint32_t>(instance_extensions.size()),
        .ppEnabledExtensionNames = instance_extensions.data(),
    };
#else
    vk::InstanceCreateInfo instance_create_info = {
        .pApplicationInfo = &APP_INFO,
    };
#endif

    const auto [instance_result, vk_instance] = vk::createInstance(instance_create_info);

    if (instance_result != vk::Result::eSuccess)
    {
        cielim::utils::log::critical("Instance creation failed: {}", vk::to_string(instance_result));
        return -1;
    }

    VULKAN_HPP_DEFAULT_DISPATCHER.init(vk_instance); // Initialize Vulkan instance

    const auto [devices_result, physical_devices] = vk_instance.enumeratePhysicalDevices();

    if (devices_result != vk::Result::eSuccess || physical_devices.empty())
    {
        cielim::utils::log::critical("No physical devices found!");
        vk_instance.destroy();
        return -1;
    }

    uint32_t device_index = -1;
    uint32_t graphics_queue_family = -1;

    // Loop through all physical devices to find most suitable one
    for (uint32_t i = 0; const auto& device : physical_devices)
    {
        const vk::PhysicalDeviceProperties device_properties = device.getProperties();

        const uint32_t major = VK_API_VERSION_MAJOR(device_properties.apiVersion);
        const uint32_t minor = VK_API_VERSION_MINOR(device_properties.apiVersion);

        // Don't allow device that can't support Vulkan 1.4+
        if (major < 1 || minor < 4)
            continue;

        const std::vector<vk::QueueFamilyProperties> queue_families = device.getQueueFamilyProperties();

        for (uint32_t j = 0; const auto& queue_family : queue_families)
        {
            // Check that the GPU supports graphics computations
            if (queue_family.queueFlags & vk::QueueFlagBits::eGraphics)
            {
                device_index = i;
                graphics_queue_family = j; // We're just picking out the first graphics queue for everything
            }
            j++;
        }
        i++;
    }

    if (device_index < 0 || graphics_queue_family < 0)
    {
        cielim::utils::log::critical("No device could be found that supports Vulkan 1.4+ and/or graphics queues!");
        vk_instance.destroy();
        return -1;
    }

    const vk::PhysicalDevice physical_device = physical_devices[device_index];
    const vk::PhysicalDeviceProperties device_properties = physical_device.getProperties();

    cielim::utils::log::info(
        "Found device {} (graphics queue family {})", device_properties.deviceName.data(), graphics_queue_family
    );

    float queue_priority = 1.0f;
    const vk::DeviceQueueCreateInfo queue_info = {
        .queueFamilyIndex = graphics_queue_family,
        .queueCount = 1,
        .pQueuePriorities = &queue_priority,
    };

    const vk::DeviceCreateInfo device_info = {
        .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queue_info,
    };

    auto [device_result, device] = physical_device.createDevice(device_info);

    if (device_result != vk::Result::eSuccess)
    {
        cielim::utils::log::critical("Device creation failed: {}", vk::to_string(device_result));
        vk_instance.destroy();
        return -1;
    }

    VULKAN_HPP_DEFAULT_DISPATCHER.init(device); // Initialize physical device

    // Check that we can acquire the queue
    const vk::Queue graphics_queue = device.getQueue(graphics_queue_family, 0);
    (void)graphics_queue;

    const vk::PhysicalDeviceMemoryProperties memory_properties = physical_device.getMemoryProperties();

    // Total heap size in bytes for device
    vk::DeviceSize dev_local_bytes = 0;
    for (uint32_t i = 0; i < memory_properties.memoryHeapCount; i++)
    {
        if (memory_properties.memoryHeaps[i].flags & vk::MemoryHeapFlagBits::eDeviceLocal)
            dev_local_bytes += memory_properties.memoryHeaps[i].size;
    }

    constexpr float BYTES_IN_GB = 1073741824.0f;

    cielim::utils::log::info("Device heap total: {:.2f} GB", static_cast<float>(dev_local_bytes) / BYTES_IN_GB);

    device.destroy();
    vk_instance.destroy();

    return 0;
}
