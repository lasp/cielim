// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

import push_constants;

[[vk::push_constant]]
SceneDataPushConstants pc;

struct VertexOutput
{
    float4 sv_position : SV_Position;
    float3 normal : NORMAL;
};

[shader("vertex")]
VertexOutput VertMain(uint vid : SV_VulkanVertexID)
{
    VertexOutput output;

    const GeometryInfo geometry = pc.geometry_info_address[0];
    const SceneInfo scene = pc.scene_info_address[0];

    Vertex v = geometry.vertex_address[vid];

    float4 world_pos = float4(v.position, 1.0);
    output.sv_position = mul(scene.view_projection, world_pos);
    output.normal = v.normal;

    return output;
}

[shader("fragment")]
float4 FragMain(VertexOutput vert_info) : SV_Target
{
    float3 n_normal = normalize(vert_info.normal);
    float3 sun_dir = normalize(pc.scene_info_address[0].sun_position);

    float lambert = 0.3183f * max(0.0f, dot(n_normal, sun_dir));

    return float4(float3(lambert), 1.0);
}
