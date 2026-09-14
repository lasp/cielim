// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Declares vk module. */

export module cielim.vk;

export import :allocator;
export import :buffer;
export import :context;
export import :frame_resources;
export import :pipeline;
export import :push_constants;
export import :renderer;
export import :shader;
export import :swapchain;

// Re-export module partition namespaces under module namespace for convenience
export namespace cielim::vk
{
using namespace cielim::vk::allocator;
using namespace cielim::vk::buffer;
using namespace cielim::vk::context;
using namespace cielim::vk::frame_resources;
using namespace cielim::vk::pipeline;
using namespace cielim::vk::push_constants;
using namespace cielim::vk::renderer;
using namespace cielim::vk::shader;
using namespace cielim::vk::swapchain;
} // namespace cielim::vk
