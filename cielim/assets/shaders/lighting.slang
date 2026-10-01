// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

import bvh_traversal;
import push_constants;
import ray;

[[vk::push_constant]]
SceneDataPushConstants pc;

struct VertexOutput
{
    float4 sv_position : SV_Position;
    float3 world_pos : POSITION;
    float3 normal : NORMAL;
};

[shader("vertex")]
VertexOutput VertMain(uint vid : SV_VulkanVertexID)
{
    VertexOutput output;

    const GeometryInfo geometry = *pc.geometry_info_address;
    const SceneInfo scene = *pc.scene_info_address;

    Vertex v = geometry.vertex_address[vid];

    // Model space is world space rn because there's no model matrix yet
    float4 world_pos = float4(v.position, 1.0);

    output.sv_position = mul(scene.view_projection, world_pos);
    output.world_pos = world_pos.xyz;
    output.normal = v.normal;

    return output;
}

[shader("fragment")]
float4 FragMain(VertexOutput vert_info) : SV_Target
{
    const SceneInfo scene = *pc.scene_info_address;

    float3 n_normal = normalize(vert_info.normal);

    // Compute geometric normal from screen-space world position derivatives

    const float3 derivative_tangent = cross(ddx(vert_info.world_pos), ddy(vert_info.world_pos));
    const float magnitude_2 = dot(derivative_tangent, derivative_tangent);

    float3 geo_normal = magnitude_2 > 0.0f ? derivative_tangent * rsqrt(magnitude_2) : n_normal;

    // Make sure the geometric normal is facing the same direction as the shading normal
    if (dot(geo_normal, n_normal) < 0.0f)
        geo_normal = -geo_normal;

    const float3 to_sun = scene.sun_position - vert_info.world_pos;
    float3 sun_dir = normalize(to_sun);

    const float n_dot_sun_dir = dot(n_normal, sun_dir);

    // Don't trace ray if the surface is already facing away from the sun
    if (n_dot_sun_dir <= 0.0f)
        return float4(0.0f, 0.0f, 0.0f, 1.0f);

    // Don't trace ray if the triangle is facing away from the sun, otherwise the ray will go into the mesh
    if (dot(geo_normal, sun_dir) <= 0.0f)
        return float4(0.0f, 0.0f, 0.0f, 1.0f);

    // TODO: improve shadow terminator for smooth shading, will probably need visibility buffer

    const Ray shadow_ray = {
        offset_ray_origin(vert_info.world_pos, geo_normal),
        0.0f,
        sun_dir,
        length(to_sun),
    };

    const float lit = is_occluded(*pc.geometry_info_address, shadow_ray) ? 0.0f : 1.0f;

    const float lambert = 0.3183f * n_dot_sun_dir * lit;

    return float4(float3(lambert), 1.0);
}
