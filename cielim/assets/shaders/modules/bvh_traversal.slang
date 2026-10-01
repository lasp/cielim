// Copyright (c) 2024 Jacco Bikker
// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: MIT

/* Adapted from tinybvh (kernels/traverse_bvh2.cl), see third_party/tinybvh/LICENSE or
 * https://github.com/jbikker/tinybvh. */

/* Purpose: Software traversal of BVH in Aila-Laine (BVH_GPU) layout. */

module bvh_traversal;

import elements;
import ray;

// Max traversal stack entries, the stack grows by at most one entry per tree level
static const uint STACK_SIZE = 64;

// Child references with bit 31 set are leaf nodes, otherwise they are internal nodes
static const uint LEAF_BIT = 0x80000000u;
// Leaf triangle count starts at bit 24...
static const uint LEAF_TRI_COUNT_SHIFT = 24;
// ...and goes through bit 30 (24-30, 7 bits, 0-127 triangles per leaf)
static const uint LEAF_TRI_COUNT_MASK = 0x7Fu;
// Leaf first triangle index is stored in bits 0-23
static const uint LEAF_FIRST_TRI_MASK = 0xFFFFFFu;

// Float sign bit
static const uint SIGN_BIT = 0x80000000u;
// Replaces non-finite reciprocals, 2^100 (BVH_RCP_FAR in tinybvh)
static const float RCP_FAR = 1.2676506e30f;

// From tinybvh_safercp (tiny_bvh_base.h), compute a ray's reciprocal direction
float safe_rcp(const float x)
{
    const float r = 1.0f / x;

    if (!(abs(r) <= RCP_FAR))
        return (asuint(x) & SIGN_BIT) != 0 ? -RCP_FAR : RCP_FAR;

    return r;
}

float3 safe_rcp(const float3 v) { return float3(safe_rcp(v.x), safe_rcp(v.y), safe_rcp(v.z)); }

// Does depth-first traversal through BVH until a triangle is hit or the stack is empty
bool test_occlusion_bvh(
    BvhGpuNode* nodes, // Must point to the mesh's first node as BVH indices are mesh-relative
    BvhGpuTriangle* triangles, // Must point to the mesh's first triangle as BVH indices are mesh-relative
    const float3 origin,
    const float3 direction,
    const float3 inv_direction,
    const float t_min,
    const float t_max
)
{
    // This is used for depth-first traversal
    uint stack[STACK_SIZE];

    // Doing this gets rid of uninitialized-use warning (E41035), entries are always pushed before being popped
    stack[0] = 0;

    uint stack_ptr = 0; // Stack pointer, points to next free entry
    uint node_ref = 0; // Root node

    // Precompute this flor slab tests
    const float3 neg_origin_inv_dir = origin * -inv_direction;

    while (true)
    {
        if ((node_ref & LEAF_BIT) != 0)
        {
            const uint tri_count = (node_ref >> LEAF_TRI_COUNT_SHIFT) & LEAF_TRI_COUNT_MASK;
            const uint first_tri = node_ref & LEAF_FIRST_TRI_MASK;

            for (uint i = 0; i < tri_count; i++)
            {
                const BvhGpuTriangle triangle = triangles[first_tri + i];

                // Moller-Trumbore
                const float3 h = cross(direction, triangle.edge2.xyz);
                const float f = rcp(dot(triangle.edge1.xyz, h));
                const float3 s = origin - triangle.v0.xyz;
                const float u = f * dot(s, h);
                const float3 q = cross(s, triangle.edge1.xyz);
                const float v = f * dot(direction, q);
                const float t = f * dot(triangle.edge2.xyz, q);

                // Accept instead of reject so NaN from degenerate triangles is a miss
                if (u >= 0.0f && v >= 0.0f && u + v <= 1.0f && t > t_min && t < t_max)
                    return true;
            }

            if (stack_ptr == 0)
                break;

            node_ref = stack[--stack_ptr];
            continue;
        }

        const BvhGpuNode node = nodes[node_ref];

        // Slab test against both child boxes: (plane - origin) / direction

        const float3 left_t0 = mad(node.left_min, inv_direction, neg_origin_inv_dir);
        const float3 left_t1 = mad(node.left_max, inv_direction, neg_origin_inv_dir);
        const float3 right_t0 = mad(node.right_min, inv_direction, neg_origin_inv_dir);
        const float3 right_t1 = mad(node.right_max, inv_direction, neg_origin_inv_dir);

        const float3 left_near = min(left_t0, left_t1);
        const float3 left_far = max(left_t0, left_t1);
        const float3 right_near = min(right_t0, right_t1);
        const float3 right_far = max(right_t0, right_t1);

        const float left_entry = max(max(max(left_near.x, left_near.y), left_near.z), t_min);
        const float right_entry = max(max(max(right_near.x, right_near.y), right_near.z), t_min);
        const float left_exit = min(min(min(left_far.x, left_far.y), left_far.z), t_max);
        const float right_exit = min(min(min(right_far.x, right_far.y), right_far.z), t_max);

        const bool hit_left = left_entry <= left_exit;
        const bool hit_right = right_entry <= right_exit;

        if (hit_left && hit_right)
        {
            if (stack_ptr == STACK_SIZE)
                return true; // Treat stack overflow as occluded

            // Visit the nearer child first
            uint near_child = node.left;
            uint far_child = node.right;

            if (right_entry < left_entry)
            {
                near_child = node.right;
                far_child = node.left;
            }

            stack[stack_ptr++] = far_child;
            node_ref = near_child;
        }
        else if (hit_left)
        {
            node_ref = node.left;
        }
        else if (hit_right)
        {
            node_ref = node.right;
        }
        else
        {
            if (stack_ptr == 0)
                break;

            node_ref = stack[--stack_ptr];
        }
    }

    return false;
}

// Gets whether a ray is occluded by any triangle in the geometry
public bool is_occluded(const GeometryInfo geometry, const Ray ray)
{
    const float3 inv_direction = safe_rcp(ray.direction);

    // Loop over all meshes in the geometry
    for (uint i = 0; i < geometry.mesh_count; i++)
    {
        const MeshInfo mesh = geometry.mesh_info_address[i];

        if (test_occlusion_bvh(
                geometry.bvh_node_address + mesh.node_offset,
                geometry.bvh_triangle_address + mesh.tri_offset,
                ray.origin,
                ray.direction,
                inv_direction,
                ray.t_min,
                ray.t_max
            ))
            return true;
    }

    return false;
}
