//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FReadNoise class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FReadNoise : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FReadNoise);
	SHADER_USE_PARAMETER_STRUCT(FReadNoise, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(uint32, CurrentTime)
	SHADER_PARAMETER(float, ReadNoiseSigma)
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
