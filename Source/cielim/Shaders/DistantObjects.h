//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FDistantObjects shader classes used to wrap their corresponding global shaders.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

#include "cielim/Actors/CameraModel.h" // This is to get access to the distant object struct definition

class FDistantObjectsVS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FDistantObjectsVS);
	SHADER_USE_PARAMETER_STRUCT(FDistantObjectsVS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER(FVector3f, CameraPosition)
	SHADER_PARAMETER(FMatrix44f, ViewProjectionMatrix)
	SHADER_PARAMETER(float, InverseProjectionX)
	SHADER_PARAMETER(float, InverseProjectionY)
	SHADER_PARAMETER(float, InverseViewWidth)
	SHADER_PARAMETER(float, InverseViewHeight)
	SHADER_PARAMETER(FVector3f, SolarDirection)
	SHADER_PARAMETER(FVector3f, SolarSpectralIrradiance)
	SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FDistantObject>, DistantObjects)
	END_SHADER_PARAMETER_STRUCT()
};

class FDistantObjectsPS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FDistantObjectsPS);
	SHADER_USE_PARAMETER_STRUCT(FDistantObjectsPS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};

// Combined parameters
BEGIN_SHADER_PARAMETER_STRUCT(FDistantObjectsParameters, )
SHADER_PARAMETER_STRUCT_INCLUDE(FDistantObjectsVS::FParameters, VS)
SHADER_PARAMETER_STRUCT_INCLUDE(FDistantObjectsPS::FParameters, PS)
END_SHADER_PARAMETER_STRUCT()
