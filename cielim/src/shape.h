// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Hard-coded shape data. */

#ifndef CIELIM_SHAPE_H
#define CIELIM_SHAPE_H

// 8 unique corners: {x, y, z, r, g, b}
inline std::array vertex_info = {
    -0.5f, -0.5f, -0.5f,  0.0f, 0.0f, 0.0f, // 0
     0.5f, -0.5f, -0.5f,  1.0f, 0.0f, 0.0f, // 1
     0.5f,  0.5f, -0.5f,  1.0f, 1.0f, 0.0f, // 2
    -0.5f,  0.5f, -0.5f,  0.0f, 1.0f, 0.0f, // 3
    -0.5f, -0.5f,  0.5f,  0.0f, 0.0f, 1.0f, // 4
     0.5f, -0.5f,  0.5f,  1.0f, 0.0f, 1.0f, // 5
     0.5f,  0.5f,  0.5f,  1.0f, 1.0f, 1.0f, // 6
    -0.5f,  0.5f,  0.5f,  0.0f, 1.0f, 1.0f, // 7
};

// 12 triangles (36 indices), outward-facing CCW winding
inline std::array indices = {
    0, 2, 1,  0, 3, 2,   // -Z face
    4, 5, 6,  4, 6, 7,   // +Z face
    0, 1, 5,  0, 5, 4,   // -Y face
    3, 7, 6,  3, 6, 2,   // +Y face
    0, 4, 7,  0, 7, 3,   // -X face
    1, 2, 6,  1, 6, 5,   // +X face
};

#endif // CIELIM_SHAPE_H
