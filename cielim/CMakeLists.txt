cmake_minimum_required(VERSION 3.28)

project(cielim LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Export compile_commands.json for clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find dependencies

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
)

# Add C++20 module files
target_sources(cielim
    PRIVATE
        FILE_SET CXX_MODULES
        BASE_DIRS "${CIELIM_CPP_SOURCE}"
        FILES
            ${CIELIM_CPP_SOURCE}/utils.cppm
            ${CIELIM_CPP_SOURCE}/utils/file.cppm
            ${CIELIM_CPP_SOURCE}/utils/log.cppm
)

# Link dependencies

target_link_libraries(cielim PRIVATE SDL3::SDL3)
target_link_libraries(cielim PRIVATE spdlog::spdlog)
target_link_libraries(cielim PRIVATE Vulkan::volk)
