// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Implements the Vulkan Memory Allocator (VMA) library code. */

// Must be included first so VMA knowns we're using Volk to dynamically load Vulkan functions
#include <volk/volk.h>

// Macro definitions are only needed in the implementation translation unit

#define VMA_IMPLEMENTATION
#define VMA_STATIC_VULKAN_FUNCTIONS 0
#define VMA_DYNAMIC_VULKAN_FUNCTIONS 1
#include <vma/vk_mem_alloc.h>
