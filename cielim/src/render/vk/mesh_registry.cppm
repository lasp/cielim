// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: The global registry for every mesh in use. Only one should exist for the entire program. */

module;

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <utility>
#include <vector>

#include <volk/volk.h>

#include <vma/vk_mem_alloc.h>

export module cielim.render.vk:mesh_registry;

import cielim.error;
import cielim.gpu.vk;
import cielim.mesh;
import cielim.result;
import cielim.utils;

export namespace cielim::render::vk
{

struct MeshInfo
{
    // Index of the mesh's first vertex within the flat vertex buffer (is signed)
    int32_t vertex_offset;
    // Index of the mesh's first index within the flat index buffer
    uint32_t index_offset;
    // The number of indices the mesh has
    uint32_t index_count;
    // Index of the mesh's first node within the flat BLAS node buffer
    uint32_t node_offset;
    // Index of the mesh's first triangle within the flat BLAS triangle buffer
    uint32_t tri_offset;
};

struct MeshRegistryInit
{
    // Initial number of vertices to hold in the registry's vertex buffer
    uint32_t init_vertex_size = INIT_VERT;
    // Initial number of indices to hold in the registry's index buffer
    uint32_t init_index_size = INIT_VERT;
    // Initial number of nodes to hold in the registry's BLAS node buffer
    uint32_t init_node_size = INIT_TRIANGLES;
    // Initial number of triangles to hold in the registry's BLAS triangle buffer
    uint32_t init_tri_size = INIT_TRIANGLES;

private:
    // Exactly 262,144 (2^18) triangles
    static constexpr uint32_t INIT_TRIANGLES = 1 << 18;
    static constexpr uint32_t INIT_VERT = 3 * INIT_TRIANGLES;
};

class MeshRegistry
{
public:
    // Delete copy constructors

    MeshRegistry(const MeshRegistry&) = delete;
    auto operator=(const MeshRegistry&) -> MeshRegistry& = delete;

    // Use default move constructor, delete move assignment

    MeshRegistry(MeshRegistry&&) = default;
    auto operator=(MeshRegistry&&) -> MeshRegistry& = delete;

    ~MeshRegistry() = default;

    /**
     * @brief Creates the mesh registry.
     * @param context The Vulkan context.
     * @param allocator The VMA allocator.
     * @param init_struct Struct with init params.
     * @return The mesh registry on success, error code on failure.
     */
    static auto
    create(const gpu::vk::Context& context, const gpu::vk::Allocator& allocator, const MeshRegistryInit& init_struct)
        -> Result<MeshRegistry>
    {
        // These flags are needed so that we can fetch buffer contents from shaders with device addresses
        constexpr VkBufferUsageFlags FLAGS
            = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT;

        // These flags are specifically for the index buffer because it is used by fixed function hardware
        constexpr VkBufferUsageFlags INDEX_FLAGS = VK_BUFFER_USAGE_INDEX_BUFFER_BIT;

        auto vertex_buffer_result
            = gpu::vk::DeviceBuffer<mesh::Vertex>::create(context, allocator, init_struct.init_vertex_size, FLAGS);

        if (!vertex_buffer_result.has_value())
            return Err(vertex_buffer_result.error().with_trace("failed to create mesh registry vertex buffer"));

        auto index_buffer_result
            = gpu::vk::DeviceBuffer<uint32_t>::create(context, allocator, init_struct.init_index_size, INDEX_FLAGS);

        if (!index_buffer_result.has_value())
            return Err(index_buffer_result.error().with_trace("failed to create mesh registry index buffer"));

        auto node_buffer_result
            = gpu::vk::DeviceBuffer<mesh::BvhGpuNode>::create(context, allocator, init_struct.init_node_size, FLAGS);

        if (!node_buffer_result.has_value())
            return Err(node_buffer_result.error().with_trace("failed to create mesh registry BLAS node buffer"));

        auto tri_buffer_result
            = gpu::vk::DeviceBuffer<mesh::BvhGpuTriangle>::create(context, allocator, init_struct.init_tri_size, FLAGS);

        if (!tri_buffer_result.has_value())
            return Err(tri_buffer_result.error().with_trace("failed to create mesh registry BLAS triangle buffer"));

        constexpr float BYTES_IN_MB = 1048576.0f;

        const float vertex_size = static_cast<float>(init_struct.init_vertex_size) * sizeof(mesh::Vertex);
        const float index_size = static_cast<float>(init_struct.init_index_size) * sizeof(uint32_t);
        const float node_size = static_cast<float>(init_struct.init_node_size) * sizeof(mesh::BvhGpuNode);
        const float tri_size = static_cast<float>(init_struct.init_tri_size) * sizeof(mesh::BvhGpuTriangle);

        utils::log::info(
            "Created mesh registry (Vertex: {:.2f} MiB, Index: {:.2f} MiB, BLAS Nodes: {:.2f} MiB, BLAS Triangles: "
            "{:.2f} MiB)",
            vertex_size / BYTES_IN_MB,
            index_size / BYTES_IN_MB,
            node_size / BYTES_IN_MB,
            tri_size / BYTES_IN_MB
        );

        return MeshRegistry(
            std::move(vertex_buffer_result).value(),
            std::move(index_buffer_result).value(),
            std::move(node_buffer_result).value(),
            std::move(tri_buffer_result).value()
        );
    }

    /**
     * @brief Uploads a mesh to the mesh registry.
     * @details Generates a bottom-level acceleration structure (BLAS) for the mesh.
     * @param mesh_data The mesh to upload.
     * @return Handle to the mesh on success, an error code on failure.
     */
    auto upload(const mesh::MeshData& mesh_data) -> Result<mesh::MeshHandle>
    {
        // Build BLAS first to avoid wasting time in case it can't be built for some reason
        const auto bvh_result = mesh::BvhBuilder::build(mesh_data);

        if (!bvh_result.has_value())
            return Err(bvh_result.error().with_trace("failed to generate BLAS for uploaded mesh"));

        const std::span vertices = mesh_data.vertices;
        const std::span indices = mesh_data.indices;
        const std::span blas_nodes = bvh_result.value().nodes;
        const std::span blas_triangles = bvh_result.value().triangles;

        if (const auto result = this->vertex_buffer_.write_many(this->vertex_write_pos_, vertices); !result.has_value())
            return Err(result.error().with_trace("failed to upload mesh vertex data to registry"));

        if (const auto result = this->index_buffer_.write_many(this->index_write_pos_, indices); !result.has_value())
            return Err(result.error().with_trace("failed to upload mesh index data to registry"));

        if (const auto result = this->node_buffer_.write_many(this->node_write_pos_, blas_nodes); !result.has_value())
            return Err(result.error().with_trace("failed to upload blas node data to registry"));

        if (const auto result = this->tri_buffer_.write_many(this->tri_write_pos_, blas_triangles); !result.has_value())
            return Err(result.error().with_trace("failed to upload blas triangle data to registry"));

        const auto num_vertices = static_cast<int32_t>(vertices.size());
        const auto num_indices = static_cast<uint32_t>(indices.size());
        const auto num_nodes = static_cast<uint32_t>(blas_nodes.size());
        const auto num_triangles = static_cast<uint32_t>(blas_triangles.size());

        // This assumes linear writing, when removal is added this will need to be replaced with a write position
        const auto mesh_index = static_cast<uint32_t>(meshes_.size());

        meshes_.emplace_back(
            MeshInfo{
                .vertex_offset = this->vertex_write_pos_,
                .index_offset = this->index_write_pos_,
                .index_count = num_indices,
                .node_offset = this->node_write_pos_,
                .tri_offset = this->tri_write_pos_,
            }
        );

        /* We wait to update the write positions until the end to make sure everything is uploaded without error,
         * otherwise we want to allow the partial data to be overwritten on next upload. */

        this->vertex_write_pos_ += num_vertices;
        this->index_write_pos_ += num_indices;
        this->node_write_pos_ += num_nodes;
        this->tri_write_pos_ += num_triangles;

        utils::log::info(
            "Uploaded mesh to mesh registry ({} vertices, {} indices, {} BLAS nodes, {} BLAS triangles)",
            num_vertices,
            num_indices,
            num_nodes,
            num_triangles
        );

        return mesh::MeshHandle{.index = mesh_index};
    }

    [[nodiscard]] auto get_mesh(const mesh::MeshHandle mesh_handle) const -> std::optional<MeshInfo>
    {
        if (mesh_handle.index >= meshes_.size())
            return std::nullopt;

        return meshes_.at(mesh_handle.index);
    }

    [[nodiscard]] auto get_vertex_handle() const -> VkBuffer { return this->vertex_buffer_.get_handle(); }
    [[nodiscard]] auto get_index_handle() const -> VkBuffer { return this->index_buffer_.get_handle(); }
    [[nodiscard]] auto get_node_handle() const -> VkBuffer { return this->node_buffer_.get_handle(); }
    [[nodiscard]] auto get_tri_handle() const -> VkBuffer { return this->tri_buffer_.get_handle(); }
    [[nodiscard]] auto get_vertex_address() const -> VkDeviceAddress { return this->vertex_buffer_.get_address(); }
    // [[nodiscard]] auto get_index_address() const -> VkDeviceAddress { return this->index_buffer_.get_address(); }
    [[nodiscard]] auto get_node_address() const -> VkDeviceAddress { return this->node_buffer_.get_address(); }
    [[nodiscard]] auto get_tri_address() const -> VkDeviceAddress { return this->tri_buffer_.get_address(); }

private:
    MeshRegistry(
        gpu::vk::DeviceBuffer<mesh::Vertex>&& vertex_buffer,
        gpu::vk::DeviceBuffer<uint32_t>&& index_buffer,
        gpu::vk::DeviceBuffer<mesh::BvhGpuNode>&& node_buffer,
        gpu::vk::DeviceBuffer<mesh::BvhGpuTriangle>&& tri_buffer
    ) :
        vertex_buffer_(std::move(vertex_buffer)), index_buffer_(std::move(index_buffer)),
        node_buffer_(std::move(node_buffer)), tri_buffer_(std::move(tri_buffer))
    {
    }

    // List of mesh info structs
    std::vector<MeshInfo> meshes_;

    // TODO: These are currently only incremented forward, add removal and defragmentation support later

    // The write position (in vertices) of the vertex buffer (signed to match vertex_offset, but is never negative)
    int32_t vertex_write_pos_ = 0;

    // The write position (in indices) of the index buffer
    uint32_t index_write_pos_ = 0;

    // The write position (in BLAS nodes) of the node buffer
    uint32_t node_write_pos_ = 0;

    // The write position (in BLAS triangles) of the triangle buffer
    uint32_t tri_write_pos_ = 0;

    // Contiguous GPU buffer containing global mesh vertex data
    gpu::vk::DeviceBuffer<mesh::Vertex> vertex_buffer_;

    // Contiguous GPU buffer containing global mesh index data
    gpu::vk::DeviceBuffer<uint32_t> index_buffer_;

    // Contiguous GPU buffer containing global mesh BLAS node data
    gpu::vk::DeviceBuffer<mesh::BvhGpuNode> node_buffer_;

    // Contiguous GPU buffer containing global mesh BLAS triangle data
    gpu::vk::DeviceBuffer<mesh::BvhGpuTriangle> tri_buffer_;
};

} // namespace cielim::render::vk
