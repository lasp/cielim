// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Fundamental mesh element definitions. */

module;

#include <array>

export module cielim.mesh_elements;

export namespace cielim::mesh_elements
{

struct MeshHandle
{
    // Index in the mesh registry's array of mesh info
    uint32_t index;
};

struct Vertex
{
    std::array<float, 3> position;
    std::array<float, 3> color;
};

} // namespace cielim::mesh_elements
