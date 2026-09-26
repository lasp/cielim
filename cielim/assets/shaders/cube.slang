// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

struct Vertex
{
    float3 vert_position;
    float3 vert_normal;
};

struct SceneInfo
{
    float4x4 view_projection;
    float3 sun_position;
};

struct PushConstants
{
    Vertex* vertex_info;
    uint64_t not_used1;
    SceneInfo* scene_info;
};

[[vk::push_constant]]
PushConstants pc;

struct VertexOutput
{
    float4 sv_position : SV_Position;
    float3 normal : NORMAL;
};

[shader("vertex")]
VertexOutput VertMain(uint vid : SV_VertexID)
{
    VertexOutput output;

    Vertex v = pc.vertex_info[vid];

    float4 world_pos = float4(v.vert_position, 1.0);
    output.sv_position = mul(pc.scene_info[0].view_projection, world_pos);
    output.normal = v.vert_normal;

    return output;
}

[shader("fragment")]
float4 FragMain(VertexOutput vert_info) : SV_Target
{
    float3 n_normal = normalize(vert_info.normal);
    float3 sun_dir = normalize(pc.scene_info[0].sun_position);

    float lambert = 0.3183f * max(0.0f, dot(n_normal, sun_dir));

    return float4(float3(lambert), 1.0);
}
