cmake_minimum_required(VERSION 3.28)

project(cielim LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Export compile_commands.json for clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find dependencies

find_package(glm CONFIG REQUIRED) # From vcpkg
find_package(SDL3 CONFIG REQUIRED) # From vcpkg
find_package(spdlog CONFIG REQUIRED) # From vcpkg
find_package(Vulkan REQUIRED COMPONENTS volk) # From VulkanSDK

add_executable(cielim)

# Cielim c++ source code path
set(CIELIM_CPP_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/src")

# Add C++ source files
target_sources(cielim
    PRIVATE
        ${CIELIM_CPP_SOURCE}/main.cpp
        ${CIELIM_CPP_SOURCE}/vk/vma.cpp
)

# Add C++20 module files
target_sources(cielim
    PRIVATE
        FILE_SET CXX_MODULES
        BASE_DIRS "${CIELIM_CPP_SOURCE}"
        FILES
            ${CIELIM_CPP_SOURCE}/default_shape.cppm
            ${CIELIM_CPP_SOURCE}/error.cppm
            ${CIELIM_CPP_SOURCE}/handle.cppm
            ${CIELIM_CPP_SOURCE}/math.cppm
            ${CIELIM_CPP_SOURCE}/mesh_elements.cppm
            ${CIELIM_CPP_SOURCE}/result.cppm
            ${CIELIM_CPP_SOURCE}/utils.cppm
            ${CIELIM_CPP_SOURCE}/vk.cppm
            ${CIELIM_CPP_SOURCE}/window.cppm
            ${CIELIM_CPP_SOURCE}/math/projection.cppm
            ${CIELIM_CPP_SOURCE}/math/tensors.cppm
            ${CIELIM_CPP_SOURCE}/utils/file.cppm
            ${CIELIM_CPP_SOURCE}/utils/log.cppm
            ${CIELIM_CPP_SOURCE}/vk/allocator.cppm
            ${CIELIM_CPP_SOURCE}/vk/buffer.cppm
            ${CIELIM_CPP_SOURCE}/vk/context.cppm
            ${CIELIM_CPP_SOURCE}/vk/frame_resources.cppm
            ${CIELIM_CPP_SOURCE}/vk/mesh_registry.cppm
            ${CIELIM_CPP_SOURCE}/vk/pipeline.cppm
            ${CIELIM_CPP_SOURCE}/vk/push_constants.cppm
            ${CIELIM_CPP_SOURCE}/vk/renderer.cppm
            ${CIELIM_CPP_SOURCE}/vk/shader.cppm
            ${CIELIM_CPP_SOURCE}/vk/swapchain.cppm
)

# Link dependencies

target_link_libraries(cielim PRIVATE glm::glm)
target_link_libraries(cielim PRIVATE SDL3::SDL3)
target_link_libraries(cielim PRIVATE spdlog::spdlog)
target_link_libraries(cielim PRIVATE Vulkan::volk)
