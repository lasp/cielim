// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Declares math module. */

export module cielim.math;

export import :projection;
export import :tensors;

// Re-export module partition namespaces under module namespace for convenience
export namespace cielim::math
{
using namespace cielim::math::projection;
using namespace cielim::math::tensors;
} // namespace cielim::math
