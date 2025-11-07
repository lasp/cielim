//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FCoverageReduce class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FCoverageReduce : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FCoverageReduce);
	SHADER_USE_PARAMETER_STRUCT(FCoverageReduce, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER(FIntPoint, TextureSize)
	SHADER_PARAMETER(float, CenterPixelX)
	SHADER_PARAMETER(float, CenterPixelY)
	SHADER_PARAMETER(float, ApothemX)
	SHADER_PARAMETER(float, ApothemY)
	SHADER_PARAMETER(float, Threshold)
	SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<uint>, PartialSumBuffer)
	END_SHADER_PARAMETER_STRUCT()
};
