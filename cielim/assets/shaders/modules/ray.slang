// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Ray tracing types and helpers used for ray traversal. These layouts follow Vulkan's ray conventions. */

module ray;

public struct Ray
{
    // Origin of the ray
    public float3 origin;
    // Minimum distance along the ray to consider for intersections
    public float t_min;
    // Direction of the ray
    public float3 direction;
    // Maximum distance along the ray to consider for intersections
    public float t_max;
};

// Not used yet
public struct HitInfo
{
    // Distance along the ray to the hit
    public float t;
    // Barycentric weights (u, v) of the triangle's second and third vertices at the hit
    public float2 barycentrics;
    // Index of the hit triangle within the index buffer
    public uint triangle_index;
    // Index of the hit mesh in the mesh info list
    public uint mesh_index;
};

// Use a fixed offset when the ray origin is small
static const float OFFSET_ORIGIN_THRESHOLD = 1.0f / 32.0f;
// Fixed offset scale to use below threshold (2^-16)
static const float OFFSET_FIXED_SCALE = 1.0f / 65536.0f;
// Number of float steps to offset by away from the origin
static const float OFFSET_FLOAT_STEPS = 256.0f;

/* Offsets a ray origin along the surface's geometric normal. From Wachter and Binder, "A Fast and Robust Method for
 * Avoiding Self-Intersection", Ray Tracing Gems (2019), chapter 6. */
public float3 offset_ray_origin(const float3 position, const float3 normal)
{
    const float3 fixed = position + OFFSET_FIXED_SCALE * normal;

    // Adding floats as integers moves them by that many representable values

    const int3 step_offset = int3(OFFSET_FLOAT_STEPS * normal);
    const float3 offset_origin = asfloat(asint(position) + select(position < 0.0f, -step_offset, step_offset));

    return select(abs(position) < OFFSET_ORIGIN_THRESHOLD, fixed, offset_origin);
}
