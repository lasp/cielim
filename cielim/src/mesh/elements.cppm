// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Fundamental mesh element definitions. */

module;

#include <array>
#include <cstdint>
#include <vector>

export module cielim.mesh:elements;

export namespace cielim::mesh
{

struct Vertex
{
    std::array<float, 3> position;
    std::array<float, 3> normal;
};

struct MeshData
{
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
};

struct MeshHandle
{
    // Index in the mesh registry's array of mesh info
    uint32_t index;
};

// A BVH binary tree node in the Aila-Laine layout
struct BvhGpuNode
{
    // Left child node axis-aligned bounding box min corner position (in local frame) in meters
    std::array<float, 3> left_min;
    /** (Bit 31 = 0): Index into nodes pointing to left child. (Bit 31 = 1): A leaf with bits 24-30 being the triangle
     * count (up to 127) and bits 0-23 being the index for the first triangle in triangles. */
    uint32_t left;
    // Left child node axis-aligned bounding box max corner position (in local frame) in meters
    std::array<float, 3> left_max;
    /** (Bit 31 = 0): Index into nodes pointing to right child. (Bit 31 = 1): A leaf with bits 24-30 being the triangle
     * count (up to 127) and bits 0-23 being the index for the first triangle in triangles. */
    uint32_t right;
    // Right child node axis-aligned bounding box min corner position (in local frame) in meters
    std::array<float, 3> right_min;
    // Unused in this layout, leaves live in left and right
    uint32_t tri_count;
    // Right child node axis-aligned bounding box max corner position (in local frame) in meters
    std::array<float, 3> right_max;
    // Unused in this layout, leaves live in left and right
    uint32_t first_tri;
};

// A triangle in BVH leaf order
struct BvhGpuTriangle
{
    // The triangle's first vertex (x, y, z, w), where w is the triangle's index in the mesh
    std::array<float, 4> v0;
    // The triangle's first vertex subtracted from its second (v1 - v0)
    std::array<float, 4> edge1;
    // The triangle's first vertex subtracted from its third (v2 - v0)
    std::array<float, 4> edge2;
};

struct BvhData
{
    std::vector<BvhGpuNode> nodes;
    std::vector<BvhGpuTriangle> triangles;

    // Bounds of the whole mesh (in local frame) in meters
    std::array<float, 3> aabb_min;
    std::array<float, 3> aabb_max;
};

} // namespace cielim::mesh
