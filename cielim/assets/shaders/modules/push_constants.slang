// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Definitions of the push constants structs. Each struct must match its C++ counterpart byte by byte. */

module push_constants;

// Re-export the elements so that shaders importing the push constants can use the types they point to
__exported import elements;

public struct SceneDataPushConstants
{
    public GeometryInfo* geometry_info_address;
    public SceneInfo* scene_info_address;
    public uint64_t object_info_address; // Unused until object info exists
};
