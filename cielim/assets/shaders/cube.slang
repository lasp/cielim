// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

struct Vertex
{
    float3 vert_position;
    float3 vert_color;
};

struct CameraInfo
{
    float4x4 view_projection;
};

struct PushConstants
{
    Vertex* vertex_info;
    uint64_t not_used1;
    CameraInfo* camera_info;
};

[[vk::push_constant]]
PushConstants pc;

struct VertexOutput
{
    float4 sv_position : SV_Position;
    float3 color;
};

[shader("vertex")]
VertexOutput VertMain(uint vid : SV_VertexID)
{
    VertexOutput output;

    Vertex v = pc.vertex_info[vid];
    CameraInfo c = pc.camera_info[0];

    float4 world_pos = float4(v.vert_position, 1.0);

    output.sv_position = mul(c.view_projection, world_pos);

    output.color = v.vert_color;

    return output;
}

[shader("fragment")]
float4 FragMain(VertexOutput vert_info) : SV_Target
{
    float3 color = vert_info.color;
    return float4(color, 1.0);
}
