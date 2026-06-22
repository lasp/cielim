//=================== Copyright (c) 2026 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FLensDistortion class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FLensDistortion : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FLensDistortion);
	SHADER_USE_PARAMETER_STRUCT(FLensDistortion, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(float, AspectRatio)
	SHADER_PARAMETER(float, K1)
	SHADER_PARAMETER(float, K2)
	SHADER_PARAMETER(float, K3)
	SHADER_PARAMETER(float, P1)
	SHADER_PARAMETER(float, P2)
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
