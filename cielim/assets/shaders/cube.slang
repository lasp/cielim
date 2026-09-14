struct VertexData
{
    float3 vert_position;
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

// Hardcoded view-projection matrix.
//
// Camera: eye = (3, 3, 3), target = (0, 0, 0), world-up = (0, 0, 1)  [right-handed, Z-up]
// Projection: right-handed perspective, Vulkan clip conventions (depth range [0,1],
//             Y flipped in the matrix itself so no separate flip is needed),
//             vertical FOV = 60 deg, aspect = 1.0, near = 0.1, far = 100.0
//
// NOTE: aspect is hardcoded to 1.0 here. If your swapchain isn't square, replace
// element [0][0] with 1.73205081 / (width / height) or pass aspect as a push
// constant / uniform.
//
// Stored row-major; HLSL float4x4 is column-major by default for mul(), so we
// use mul(vp, position) with vp constructed from explicit rows below, which
// matches row_major-as-authored semantics via mul(matrix, vector).
static const float4x4 kViewProj = float4x4(
    -1.22474487,  1.22474487,  0.0,          0.0,
     0.70710678,  0.70710678, -1.41421356,   0.0,
    -0.57792820, -0.57792820, -0.57792820,   5.10125368,
    -0.57735027, -0.57735027, -0.57735027,   5.19615242
);

[shader("vertex")]
VertexOutput VertMain(uint vid : SV_VertexID)
{
    VertexOutput output;

    VertexData v = pc.vertex_info[vid];

    float4 world_pos = float4(v.vert_position, 1.0);
    output.sv_position = mul(kViewProj, world_pos);
    output.color = v.vert_color;

    return output;
}

[shader("fragment")]
float4 FragMain(VertexOutput vert_info) : SV_Target
{
    float3 color = vert_info.color;
    return float4(color, 1.0);
}
