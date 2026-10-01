// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Render element definitions corresponding to those used in shaders. These C++ side definitions must match
 * the corresponding shader structs exactly in layout and size. */

module;

#include <cstddef>
#include <cstdint>

#include <volk/volk.h>

export module cielim.render.vk:elements;

import cielim.math;

export namespace cielim::render::vk
{

// Mesh data locations on the GPU
struct GeometryInfo
{
    // Address of the frame-in-flight's copy of the registry's mesh info table
    VkDeviceAddress mesh_info_address = 0;
    // Address of the mesh registry's vertex buffer
    VkDeviceAddress vertex_address = 0;
    // Address of the mesh registry's index buffer
    VkDeviceAddress index_address = 0;
    // Address of the mesh registry's BLAS node buffer
    VkDeviceAddress bvh_node_address = 0;
    // Address of the mesh registry's BLAS triangle buffer
    VkDeviceAddress bvh_triangle_address = 0;
    // The number of meshes
    uint32_t mesh_count = 0;
};

static_assert(offsetof(GeometryInfo, mesh_info_address) == 0);
static_assert(offsetof(GeometryInfo, vertex_address) == 8);
static_assert(offsetof(GeometryInfo, index_address) == 16);
static_assert(offsetof(GeometryInfo, bvh_node_address) == 24);
static_assert(offsetof(GeometryInfo, bvh_triangle_address) == 32);
static_assert(offsetof(GeometryInfo, mesh_count) == 40);

// Individual mesh data locations in the mesh registry's buffers
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

static_assert(offsetof(MeshInfo, vertex_offset) == 0);
static_assert(offsetof(MeshInfo, index_offset) == 4);
static_assert(offsetof(MeshInfo, index_count) == 8);
static_assert(offsetof(MeshInfo, node_offset) == 12);
static_assert(offsetof(MeshInfo, tri_offset) == 16);

// Information specific to the scene being rendered
struct SceneInfo
{
    // Transforms world space positions into clip space
    math::Mat4 view_projection{};
    // Position of the sun in the scene inertial frame
    math::Vec3 sun_position{};
};

static_assert(offsetof(SceneInfo, view_projection) == 0);
static_assert(offsetof(SceneInfo, sun_position) == 64);

} // namespace cielim::render::vk
