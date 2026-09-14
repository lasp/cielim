// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Contains push constant structs. These contain device addresses to buffers to be used during render passes
 * and should be populated every frame. */

module;

#include <volk/volk.h>

export module cielim.vk:push_constants;

export namespace cielim::vk::push_constants
{

struct SceneDataAddresses
{
    // Address to the buffer containing all unique mesh vertex info
    VkDeviceAddress vertex_info_address = 0;

    // Address to the buffer containing all individual object info
    VkDeviceAddress object_info_address = 0;

    // Address to the buffer containing global frame data
    VkDeviceAddress frame_data_address = 0;
};

} // namespace cielim::vk::push_constants
