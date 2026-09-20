// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Hard-coded shape data. */

module;

#include <array>

export module cielim.mesh:default_shape;

import :elements;

export namespace cielim::mesh
{

/* 24 vertices: 4 per face (duplicated corners), each face gets its own smooth color gradient — {x, y, z, r, g, b}. */
inline std::array vertices = {
    Vertex{-0.5f, -0.5f, -0.5f, 0.7804f, 0.3216f, 0.1647f}, // 0  (-Z) c7522a rust
    Vertex{0.5f, -0.5f, -0.5f, 0.4549f, 0.6588f, 0.5725f},  // 1  (-Z) 74a892 teal-green
    Vertex{0.5f, 0.5f, -0.5f, 0.0f, 0.5216f, 0.5216f},      // 2  (-Z) 008585 teal
    Vertex{-0.5f, 0.5f, -0.5f, 0.8980f, 0.7569f, 0.5216f},  // 3  (-Z) e5c185 tan

    Vertex{-0.5f, -0.5f, 0.5f, 0.9843f, 0.9490f, 0.7686f}, // 4  (+Z) fbf2c4 pale cream
    Vertex{0.5f, -0.5f, 0.5f, 0.7216f, 0.8039f, 0.6706f},  // 5  (+Z) b8cdab sage
    Vertex{0.5f, 0.5f, 0.5f, 0.0f, 0.2627f, 0.2627f},      // 6  (+Z) 004343 dark teal
    Vertex{-0.5f, 0.5f, 0.5f, 0.9412f, 0.8549f, 0.6471f},  // 7  (+Z) f0daa5 light cream

    Vertex{-0.5f, -0.5f, -0.5f, 0.7804f, 0.3216f, 0.1647f}, // 8  (-Y) c7522a rust
    Vertex{0.5f, -0.5f, -0.5f, 0.4549f, 0.6588f, 0.5725f},  // 9  (-Y) 74a892 teal-green
    Vertex{0.5f, -0.5f, 0.5f, 0.7216f, 0.8039f, 0.6706f},   // 10 (-Y) b8cdab sage
    Vertex{-0.5f, -0.5f, 0.5f, 0.9843f, 0.9490f, 0.7686f},  // 11 (-Y) fbf2c4 pale cream

    Vertex{-0.5f, 0.5f, -0.5f, 0.8980f, 0.7569f, 0.5216f}, // 12 (+Y) e5c185 tan
    Vertex{-0.5f, 0.5f, 0.5f, 0.9412f, 0.8549f, 0.6471f},  // 13 (+Y) f0daa5 light cream
    Vertex{0.5f, 0.5f, 0.5f, 0.0f, 0.2627f, 0.2627f},      // 14 (+Y) 004343 dark teal
    Vertex{0.5f, 0.5f, -0.5f, 0.0f, 0.5216f, 0.5216f},     // 15 (+Y) 008585 teal

    Vertex{-0.5f, -0.5f, -0.5f, 0.7804f, 0.3216f, 0.1647f}, // 16 (-X) c7522a rust
    Vertex{-0.5f, -0.5f, 0.5f, 0.9843f, 0.9490f, 0.7686f},  // 17 (-X) fbf2c4 pale cream
    Vertex{-0.5f, 0.5f, 0.5f, 0.9412f, 0.8549f, 0.6471f},   // 18 (-X) f0daa5 light cream
    Vertex{-0.5f, 0.5f, -0.5f, 0.8980f, 0.7569f, 0.5216f},  // 19 (-X) e5c185 tan

    Vertex{0.5f, -0.5f, -0.5f, 0.4549f, 0.6588f, 0.5725f}, // 20 (+X) 74a892 teal-green
    Vertex{0.5f, 0.5f, -0.5f, 0.0f, 0.5216f, 0.5216f},     // 21 (+X) 008585 teal
    Vertex{0.5f, 0.5f, 0.5f, 0.0f, 0.2627f, 0.2627f},      // 22 (+X) 004343 dark teal
    Vertex{0.5f, -0.5f, 0.5f, 0.7216f, 0.8039f, 0.6706f},  // 23 (+X) b8cdab sage
};

/* 12 triangles (36 indices), outward-facing CCW winding — 4 indices per face, no sharing between faces since each face
 * owns its own 4 vertices. */
inline std::array indices = {
    0u,  2u,  1u,  0u,  3u,  2u,  // -Z face
    4u,  5u,  6u,  4u,  6u,  7u,  // +Z face
    8u,  9u,  10u, 8u,  10u, 11u, // -Y face
    12u, 13u, 14u, 12u, 14u, 15u, // +Y face
    16u, 17u, 18u, 16u, 18u, 19u, // -X face
    20u, 21u, 22u, 20u, 22u, 23u, // +X face
};

} // namespace cielim::mesh
