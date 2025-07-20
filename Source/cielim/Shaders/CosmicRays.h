//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FCosmicRays class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FCosmicRays : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FCosmicRays);
	SHADER_USE_PARAMETER_STRUCT(FCosmicRays, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(uint32, NumRays)
	SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float2>, StartPoints)
	SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float2>, EndPoints)
	SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float>, LineWidths)
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
