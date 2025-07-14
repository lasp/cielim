//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FGaussianPSF class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FGaussianPSF : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianPSF);
	SHADER_USE_PARAMETER_STRUCT(FGaussianPSF, FGlobalShader);

	class FHorizontal : SHADER_PERMUTATION_BOOL("BLUR_HORIZONTAL");
	using FPermutationDomain = TShaderPermutationDomain<FHorizontal>;

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(FVector2f, TexelSize)
	SHADER_PARAMETER(int, KernelRadius)
	SHADER_PARAMETER(float, Sigma)
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
