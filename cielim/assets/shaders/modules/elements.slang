// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Definitions of the elements structs. Each struct must match its C++ counterpart byte by byte. */

module elements;

// Mesh elements

public struct Vertex
{
    public float3 position;
    public float3 normal;
};

public struct BvhGpuNode
{
    public float3 left_min;
    public uint left;
    public float3 left_max;
    public uint right;
    public float3 right_min;
    public uint tri_count;
    public float3 right_max;
    public uint first_tri;
};

public struct BvhGpuTriangle
{
    public float4 v0;
    public float4 edge1;
    public float4 edge2;
};

// Render elements

public struct GeometryInfo
{
    public MeshInfo* mesh_info_address;
    public Vertex* vertex_address;
    public uint* index_address; // Unused for now
    public BvhGpuNode* bvh_node_address;
    public BvhGpuTriangle* bvh_triangle_address;
    public uint mesh_count;
};

public struct MeshInfo
{
    public int vertex_offset;
    public uint index_offset;
    public uint index_count;
    public uint node_offset;
    public uint tri_offset;
};

public struct SceneInfo
{
    public float4x4 view_projection;
    public float3 sun_position;
};
