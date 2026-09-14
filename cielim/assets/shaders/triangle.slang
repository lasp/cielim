// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

struct VertexData
{
    float2 vert_position;
    float3 vert_color;
};

struct PushConstants
{
    VertexData* vertex_info;
    uint64_t not_used1;
    uint64_t not_used2;
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

    output.sv_position = float4(pc.vertex_info[vid].vert_position, 0.0, 1.0);
    output.color = pc.vertex_info[vid].vert_color;

    return output;
}

[shader("fragment")]
float4 FragMain(VertexOutput vert_info) : SV_Target
{
    float3 color = vert_info.color;
    return float4(color, 1.0);
}
