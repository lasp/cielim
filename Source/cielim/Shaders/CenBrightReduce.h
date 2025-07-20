//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FCenBrightReduce class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FCenBrightReduce : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FCenBrightReduce);
	SHADER_USE_PARAMETER_STRUCT(FCenBrightReduce, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER(FIntPoint, TextureSize)
	SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float4>, PartialSumBuffer)
	END_SHADER_PARAMETER_STRUCT()
};
