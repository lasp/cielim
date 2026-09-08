// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Creates a shader module from a compiled SPIR-V shader file. */

module;

#include <filesystem>
#include <string>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.vk:shader;

import cielim.result;
import cielim.utils;
import :context;

export namespace cielim::vk::shader
{

class Shader
{
public:
    Shader() = default;

    ~Shader()
    {
        if (this->vk_shader_ != nullptr)
            vkDestroyShaderModule(this->vk_device_handle_, this->vk_shader_, nullptr);
    }

    /**
     * @brief Creates shader module object from compiled SPIR-V bytecode.
     * @param context The Vulkan context.
     * @param path The path to the .spv shader file.
     * @return Void on success, error code on failure.
     */
    auto create(const context::Context& context, const std::filesystem::path& path) -> Result<void>
    {
        this->vk_device_handle_ = context.get_device(); // This is specifically a non-owning (borrow) handle

        auto file_result = utils::file::read_file32(path);

        if (!file_result.has_value())
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkShaderModuleError::FileOpenError),
                .detail = "'" + path.filename().string() + "': " + file_result.error().message(),
            };

            return Err(error);
        }

        const VkShaderModuleCreateInfo module_create_info = {
            .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
            .codeSize = file_result.value().size() * sizeof(uint32_t),
            .pCode = file_result.value().data(),
        };

        if (const auto result
            = vkCreateShaderModule(this->vk_device_handle_, &module_create_info, nullptr, &this->vk_shader_);
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkShaderModuleError::ModuleCreateError),
                .detail = "'" + path.stem().string() + "': " + string_VkResult(result),
            };

            return Err(error);
        }

        return {};
    }

    [[nodiscard]] auto get_handle() const -> VkShaderModule { return this->vk_shader_; }

private:
    // Non-owning handle for the Vulkan logical device
    VkDevice vk_device_handle_ = nullptr;

    // Shader module
    VkShaderModule vk_shader_ = nullptr;
};

} // namespace cielim::vk::shader
