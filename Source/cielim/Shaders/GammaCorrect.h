//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FGammaCorrect class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FGammaCorrect : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGammaCorrect);
	SHADER_USE_PARAMETER_STRUCT(FGammaCorrect, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(float, InvGamma)
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
