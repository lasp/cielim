// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The global registry for every mesh in use. Only one should exist for the entire program. */

module;

#include <optional>
#include <span>
#include <string>
#include <vector>

#include <volk/volk.h>

#include <vma/vk_mem_alloc.h>

export module cielim.vk:mesh_registry;

import cielim.error;
import cielim.mesh_elements;
import cielim.result;
import :buffer;

export namespace cielim::vk::mesh_registry
{

struct MeshInfo
{
    // Index of the mesh's first vertex within the flat vertex buffer (is signed)
    int32_t vertex_offset;
    // Index of the mesh's first index within the flat index buffer
    uint32_t index_offset;
    // The number of indices the mesh has
    uint32_t index_count;
};

class MeshRegistry
{
public:
    MeshRegistry() = default;

    // Delete copy constructors

    MeshRegistry(const MeshRegistry&) = delete;
    auto operator=(const MeshRegistry&) -> MeshRegistry& = delete;

    // Use default move constructors

    MeshRegistry(MeshRegistry&&) = default;
    auto operator=(MeshRegistry&&) -> MeshRegistry& = default;

    ~MeshRegistry() = default;

    /**
     * @brief Creates the mesh registry.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param init_size Initial size in bytes for the registry's vertex and index buffers.
     * @return Void on success, error code on failure.
     */
    auto create(const context::Context& context, const allocator::Allocator& allocator, const uint32_t init_size)
        -> Result<void>
    {
        if (const auto result = this->vertex_buffer_.create(
                context,
                allocator,
                init_size,
                VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                VMA_ALLOCATION_CREATE_MAPPED_BIT | VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT
            );
            !result.has_value())
        {
            error::DetailedError error = {
                .errc = result.error().errc,
                .detail = "mesh_registry vertex buffer",
            };

            return Err(error);
        }

        if (const auto result = this->index_buffer_.create(
                context,
                allocator,
                init_size,
                VK_BUFFER_USAGE_INDEX_BUFFER_BIT,
                VMA_ALLOCATION_CREATE_MAPPED_BIT | VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT
            );
            !result.has_value())
        {
            error::DetailedError error = {
                .errc = result.error().errc,
                .detail = "mesh_registry index buffer",
            };

            return Err(error);
        }

        return {};
    }

    /**
     * @brief Uploads a mesh to the mesh registry.
     * @param vertex_info List of vertices for the mesh.
     * @param index_info List of indices for the mesh.
     * @return Handle to the mesh on success, an error code on failure.
     */
    auto upload(const std::span<const mesh_elements::Vertex> vertex_info, const std::span<const uint32_t> index_info)
        -> Result<mesh_elements::MeshHandle>
    {
        const size_t vertex_write_pos_bytes = this->vertex_write_pos_ * sizeof(mesh_elements::Vertex);

        if (const auto result
            = vertex_buffer_.direct_write(vertex_write_pos_bytes, vertex_info.data(), vertex_info.size_bytes());
            !result.has_value())
        {
            error::DetailedError error = {
                .errc = result.error().errc,
                .detail = result.error().detail + ": could not upload mesh vertex data to registry",
            };

            return Err(error);
        }

        const size_t index_write_pos_bytes = this->index_write_pos_ * sizeof(uint32_t);

        if (const auto result
            = index_buffer_.direct_write(index_write_pos_bytes, index_info.data(), index_info.size_bytes());
            !result.has_value())
        {
            error::DetailedError error = {
                .errc = result.error().errc,
                .detail = result.error().detail + ": could not upload mesh index data to registry",
            };

            return Err(error);
        }

        const auto mesh_index = static_cast<uint32_t>(meshes_.size());

        meshes_.emplace_back(
            MeshInfo{
                .vertex_offset = vertex_write_pos_,
                .index_offset = index_write_pos_,
                .index_count = static_cast<uint32_t>(index_info.size()),
            }
        );

        // Linearly advance write positions

        vertex_write_pos_ += static_cast<int32_t>(vertex_info.size());
        index_write_pos_ += static_cast<uint32_t>(index_info.size());

        return mesh_elements::MeshHandle{.index = mesh_index};
    }

    [[nodiscard]] auto get_mesh(const mesh_elements::MeshHandle mesh_handle) const -> std::optional<MeshInfo>
    {
        if (mesh_handle.index >= meshes_.size())
            return std::nullopt;

        return meshes_.at(mesh_handle.index);
    }

    [[nodiscard]] auto get_vertex_handle() const -> VkBuffer { return this->vertex_buffer_.get_handle(); }
    [[nodiscard]] auto get_index_handle() const -> VkBuffer { return this->index_buffer_.get_handle(); }
    [[nodiscard]] auto get_vertex_address() const -> VkDeviceAddress
    { return this->vertex_buffer_.get_device_address(); }

private:
    // List of mesh info structs
    std::vector<MeshInfo> meshes_;

    // The write position (in vertices) of the vertex buffer (continuous forward write, no defragmentation for now)
    int32_t vertex_write_pos_ = 0;

    // The write position (in indices) of the index buffer (continuous forward write, no defragmentation for now)
    uint32_t index_write_pos_ = 0;

    // Contiguous GPU buffer containing global mesh vertex data
    buffer::Buffer vertex_buffer_;

    // Contiguous GPU buffer containing global mesh index data
    buffer::Buffer index_buffer_;
};

} // namespace cielim::vk::mesh_registry
