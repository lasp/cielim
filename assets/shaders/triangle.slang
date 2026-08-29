// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

static float2 positions[3] = float2[](
    float2(0.0, -0.5),
    float2(0.5, 0.5),
    float2(-0.5, 0.5)
);

static float3 colors[3] = float3[](
    float3(1.0, 0.0, 0.0),
    float3(0.0, 1.0, 0.0),
    float3(0.0, 0.0, 1.0)
);

struct VertexOutput
{
    float3 color;
    float4 sv_position : SV_Position;
};

[shader("vertex")]
VertexOutput VertMain(uint vid : SV_VertexID)
{
    VertexOutput output;

    output.color = colors[vid];
    output.sv_position = float4(positions[vid], 0.0, 1.0);

    return output;
}

[shader("fragment")]
float4 FragMain(VertexOutput vert_info) : SV_Target
{
    float3 color = vert_info.color;
    return float4(color, 1.0);
}
