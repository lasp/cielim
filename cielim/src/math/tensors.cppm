// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Defines basic tensor types and operations. */

module;

// Vulkan clip space uses a depth range of [0, 1], GLM assumes OpenGL's [-1, 1] by default
#define GLM_FORCE_DEPTH_ZERO_TO_ONE

#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/quaternion.hpp>
#include <glm/gtc/type_ptr.hpp>

export module cielim.math:tensors;

// Re-export operators to make them visible via ADL
export namespace glm
{

using glm::operator+;
using glm::operator-;
using glm::operator*;
using glm::operator/;
using glm::operator==;
using glm::operator!=;

} // namespace glm

export namespace cielim::math::tensors
{

// Float 2-component vector
using Vec2 = glm::vec2;
// Float 3-component vector
using Vec3 = glm::vec3;
// Float 4-component vector
using Vec4 = glm::vec4;

// Double 2-component vector
using DVec2 = glm::dvec2;
// Double 3-component vector
using DVec3 = glm::dvec3;
// Double 4-component vector
using DVec4 = glm::dvec4;

// Integer 2-component vector
using IVec2 = glm::ivec2;
// Integer 3-component vector
using IVec3 = glm::ivec3;
// Integer 4-component vector
using IVec4 = glm::ivec4;

// Unsigned integer 2-component vector
using UVec2 = glm::uvec2;
// Unsigned integer 3-component vector
using UVec3 = glm::uvec3;
// Unsigned integer 4-component vector
using UVec4 = glm::uvec4;

// Float 3x3 matrix
using Mat3 = glm::mat3;
// Float 4x4 matrix
using Mat4 = glm::mat4;

// Float quaternion
using Quat = glm::quat;

// Vector functions

using glm::cross;
using glm::distance;
using glm::dot;
using glm::faceforward;
using glm::length;
using glm::normalize;
using glm::reflect;
using glm::refract;

// Common functions

using glm::abs;
using glm::ceil;
using glm::clamp;
using glm::floor;
using glm::fract;
using glm::max;
using glm::min;
using glm::mix;
using glm::mod;
using glm::round;
using glm::sign;
using glm::smoothstep;
using glm::step;

// Angle functions

using glm::degrees;
using glm::radians;

// Matrix transform functions (glm/gtc/matrix_transform.hpp)

using glm::frustum;
using glm::infinitePerspective;
using glm::lookAt;
using glm::ortho;
using glm::perspective;
using glm::perspectiveFov;
using glm::rotate;
using glm::scale;
using glm::translate;

// Quaternion functions (glm/gtc/quaternion.hpp)

using glm::angleAxis;
using glm::conjugate;
using glm::eulerAngles;
using glm::inverse;
using glm::mat3_cast;
using glm::mat4_cast;
using glm::quat_cast;
using glm::slerp;

// GPU interop (glm/gtc/type_ptr.hpp)

using glm::value_ptr;

} // namespace cielim::math::tensors
