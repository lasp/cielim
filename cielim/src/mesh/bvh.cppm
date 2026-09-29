// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Builds bounding volume hierarchies (BVHs) over mesh data for ray tracing. */

module;

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <format> // This can be replaced with fmt when C1116 is fixed
#include <span>
#include <vector>

#include <tiny_bvh.h>

export module cielim.mesh:bvh;

import cielim.error;
import cielim.result;
// import cielim.utils; This causes C1116 with MSVC 14.51, can be re-introduced when compiler bug is fixed
import :elements;

using TinyBvhNode = tinybvh::BVH_GPU::BVHNode;

// Check that the BvhGpu elements match tinybvh's BVH_GPU byte layout exactly during compile

static_assert(sizeof(cielim::mesh::BvhGpuNode) == sizeof(TinyBvhNode));
static_assert(offsetof(cielim::mesh::BvhGpuNode, left_min) == offsetof(TinyBvhNode, lmin));
static_assert(offsetof(cielim::mesh::BvhGpuNode, left) == offsetof(TinyBvhNode, left));
static_assert(offsetof(cielim::mesh::BvhGpuNode, left_max) == offsetof(TinyBvhNode, lmax));
static_assert(offsetof(cielim::mesh::BvhGpuNode, right) == offsetof(TinyBvhNode, right));
static_assert(offsetof(cielim::mesh::BvhGpuNode, right_min) == offsetof(TinyBvhNode, rmin));
static_assert(offsetof(cielim::mesh::BvhGpuNode, tri_count) == offsetof(TinyBvhNode, triCount));
static_assert(offsetof(cielim::mesh::BvhGpuNode, right_max) == offsetof(TinyBvhNode, rmax));
static_assert(offsetof(cielim::mesh::BvhGpuNode, first_tri) == offsetof(TinyBvhNode, firstTri));
static_assert(sizeof(cielim::mesh::BvhGpuTriangle) == 3 * sizeof(tinybvh::bvhvec4));

export namespace cielim::mesh
{

class BvhBuilder
{
public:
    BvhBuilder() = default;

    // Delete copy constructors

    BvhBuilder(const BvhBuilder&) = delete;
    auto operator=(const BvhBuilder&) -> BvhBuilder& = delete;

    // Use default move constructors

    BvhBuilder(BvhBuilder&&) = default;
    auto operator=(BvhBuilder&&) -> BvhBuilder& = default;

    /**
     * @brief Builds a BVH over a mesh in the Aila-Laine (BVH_GPU) layout for GPU traversal.
     * @details The mesh is validated first since tinybvh terminates the program on invalid input.
     * @param mesh_data The mesh to build the BVH over.
     * @return BVH data on success, error code on failure.
     */
    static auto build(const MeshData& mesh_data) -> Result<BvhData>
    {
        const std::span vertices = mesh_data.vertices;
        const std::span indices = mesh_data.indices;

        if (indices.empty())
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::MalformedMesh),
                    .detail = "mesh has no triangles",
                }
            );
        }

        if (indices.size() % 3 != 0)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::MalformedMesh),
                    .detail = std::format("index count {} is not a multiple of 3", indices.size()),
                }
            );
        }

        const size_t tri_count = indices.size() / 3;

        if (tri_count > MAX_TRIANGLES)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::BvhBuildError),
                    .detail = std::format("{} triangles exceeds the limit of {}", tri_count, MAX_TRIANGLES),
                }
            );
        }

        for (const uint32_t index : indices)
        {
            if (index >= vertices.size())
            {
                return Err(
                    error::DetailedError{
                        .errc = make_error_code(error::MeshError::MalformedMesh),
                        .detail = std::format("index {} is out of range ({} vertices)", index, vertices.size()),
                    }
                );
            }
        }

        // Tinybvh needs vertex positions padded to 16 bytes
        std::vector<tinybvh::bvhvec4> positions(vertices.size());

        for (size_t i = 0; i < vertices.size(); i++)
        {
            const auto& position = vertices[i].position;
            positions[i] = tinybvh::bvhvec4(position[0], position[1], position[2], 0.0f);
        }

        const tinybvh::bvhvec4slice position_slice(
            positions.data(), static_cast<uint32_t>(positions.size()), sizeof(tinybvh::bvhvec4)
        );

        tinybvh::BVH_GPU bvh_gpu;
        bvh_gpu.Build(position_slice, indices.data(), static_cast<uint32_t>(tri_count));

        // Without spatial splits every triangle lands in exactly one leaf, so the triangle count is unchanged
        if (bvh_gpu.usedNodes == 0 || bvh_gpu.orderedVerts.data == nullptr
            || bvh_gpu.orderedVerts.stride != sizeof(tinybvh::bvhvec4) || bvh_gpu.orderedVerts.count != 3 * tri_count)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::BvhBuildError),
                    .detail = "tinybvh produced unexpected output",
                }
            );
        }

        BvhData bvh_data;

        bvh_data.nodes.resize(bvh_gpu.usedNodes);
        std::memcpy(bvh_data.nodes.data(), bvh_gpu.bvhNode, bvh_data.nodes.size() * sizeof(BvhGpuNode));

        bvh_data.triangles.resize(tri_count);
        std::memcpy(
            bvh_data.triangles.data(), bvh_gpu.orderedVerts.data, bvh_data.triangles.size() * sizeof(BvhGpuTriangle)
        );

        bvh_data.aabb_min = {bvh_gpu.aabbMin.x, bvh_gpu.aabbMin.y, bvh_gpu.aabbMin.z};
        bvh_data.aabb_max = {bvh_gpu.aabbMax.x, bvh_gpu.aabbMax.y, bvh_gpu.aabbMax.z};

        return bvh_data;
    }

private:
    // Leaf references store their first triangle in 24 bits
    static constexpr size_t MAX_TRIANGLES = size_t{1} << 24;
};

} // namespace cielim::mesh
