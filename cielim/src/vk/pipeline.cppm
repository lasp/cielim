// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: A pipeline is an immutable object dictating the parameters for fixed pipeline stages such as rasterization
 * and enumerates all of the programmable shader stages to be run. A pipeline must exist for every unique combination
 * of shader stages. */

module;

#include <array>
#include <string>
#include <vector>

#include <volk/volk.h>
#include <vulkan/vk_enum_string_helper.h>

export module cielim.vk:pipeline;

import cielim.handle;
import cielim.result;
import :context;
import :shader;
import :swapchain;

export namespace cielim::vk::pipeline
{

struct ShaderStage
{
    VkShaderStageFlagBits stage_flag;
    const shader::Shader& shader_module;
    std::string entry_point;
};

class Pipeline
{
public:
    Pipeline() = default;

    // Delete copy constructors

    Pipeline(const Pipeline&) = delete;
    auto operator=(const Pipeline&) -> Pipeline& = delete;

    // Use default move constructors

    Pipeline(Pipeline&&) = default;
    auto operator=(Pipeline&&) -> Pipeline& = default;

    ~Pipeline()
    {
        if (pipeline_layout_)
            vkDestroyPipelineLayout(this->vk_device_handle_, pipeline_layout_.get(), nullptr);

        if (pipeline_)
            vkDestroyPipeline(this->vk_device_handle_, pipeline_.get(), nullptr);
    }

    /**
     * @brief Creates the Vulkan pipeline object.
     * @details Vulkan pipelines are immutable, and so this function should never be called more than once.
     * @param context The Vulkan context.
     * @param swapchain The swapchain the pipeline should render to.
     * @param stages List of shader stages to include in the pipeline.
     * @return Void on success, error code on failure
     */
    auto create(
        const context::Context& context, const swapchain::Swapchain& swapchain, const std::vector<ShaderStage>& stages
    ) -> Result<void>
    {
        this->vk_device_handle_ = context.get_device(); // This is specifically a non-owning (borrow) handle

        // Specify shader uniform data layout

        // This is empty because no uniforms are used yet
        VkPipelineLayoutCreateInfo layout_create_info = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
            .setLayoutCount = 0,
            .pushConstantRangeCount = 0,
        };

        if (const auto result = vkCreatePipelineLayout(
                this->vk_device_handle_, &layout_create_info, nullptr, this->pipeline_layout_.put()
            );
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkPipelineError::LayoutCreateError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        // Collect all of the shader stage info structs

        std::vector<VkPipelineShaderStageCreateInfo> shader_stages;

        for (const auto& [stage_flag, shader_module, entry_point] : stages)
        {
            shader_stages.emplace_back(
                VkPipelineShaderStageCreateInfo{
                    .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                    .stage = stage_flag,
                    .module = shader_module.get_handle(),
                    .pName = entry_point.c_str(),
                }
            );
        }

        // Setup and create rendering pipeline and stages

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

        std::array dynamic_states = {VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR};

        VkPipelineDynamicStateCreateInfo dynamic_state = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
            .dynamicStateCount = static_cast<uint32_t>(dynamic_states.size()),
            .pDynamicStates = dynamic_states.data(),
        };

        VkFormat req_format = swapchain.get_format();

        VkPipelineRenderingCreateInfo pipeline_rendering_state = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO,
            .colorAttachmentCount = 1,
            .pColorAttachmentFormats = &req_format,
        };

        VkGraphicsPipelineCreateInfo pipeline_info = {
            .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
            .pNext = &pipeline_rendering_state,
            .stageCount = 2,
            .pStages = shader_stages.data(),
            .pVertexInputState = &vertex_input_state,
            .pInputAssemblyState = &input_assembly_state,
            .pViewportState = &viewport_state,
            .pRasterizationState = &rasterization_state,
            .pMultisampleState = &multisample_state,
            .pColorBlendState = &color_blend_state,
            .pDynamicState = &dynamic_state,
            .layout = this->pipeline_layout_.get(),
            .renderPass = nullptr,
        };

        if (const auto result = vkCreateGraphicsPipelines(
                this->vk_device_handle_, nullptr, 1, &pipeline_info, nullptr, this->pipeline_.put()
            );
            result != VK_SUCCESS)
        {
            error::DetailedError error = {
                .errc = make_error_code(error::VkPipelineError::PipelineCreateError),
                .detail = string_VkResult(result),
            };

            return Err(error);
        }

        return {};
    }

    [[nodiscard]] auto get_handle() const -> VkPipeline { return this->pipeline_.get(); }

private:
    // Non-owning handle for the Vulkan logical device
    VkDevice vk_device_handle_ = nullptr;

    // Vulkan pipeline layout (assumed unique per pipeline for now, may not be the case later)
    UniqueHandle<VkPipelineLayout> pipeline_layout_;

    // Vulkan render pipeline
    UniqueHandle<VkPipeline> pipeline_;
};

} // namespace cielim::vk::pipeline
