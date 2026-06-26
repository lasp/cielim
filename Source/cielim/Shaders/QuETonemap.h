//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FQuETonemap class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FQuETonemap : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FQuETonemap);
	SHADER_USE_PARAMETER_STRUCT(FQuETonemap, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(float, SolidAngle)
	SHADER_PARAMETER(float, PixelArea)
	SHADER_PARAMETER(float, ExposureTime)
	SHADER_PARAMETER(float, Transmission1)
	SHADER_PARAMETER(float, Transmission2)
	SHADER_PARAMETER(float, Transmission3)
	SHADER_PARAMETER(float, W1EnergyInverse)
	SHADER_PARAMETER(float, W2EnergyInverse)
	SHADER_PARAMETER(float, W3EnergyInverse)
	SHADER_PARAMETER(FVector4f, QuECurveR)
	SHADER_PARAMETER(FVector4f, QuECurveG)
	SHADER_PARAMETER(FVector4f, QuECurveB)
	SHADER_PARAMETER(float, SimpsonFactor)
	SHADER_PARAMETER(float, CorrectionFactor)
	SHADER_PARAMETER(uint32, CurrentTime)
	SHADER_PARAMETER(uint32, EnableShotNoise)
	SHADER_PARAMETER(float, DarkCurrent)
	SHADER_PARAMETER(uint32, DarkCurrentPattern)
	SHADER_PARAMETER(float, DarkCurrentLogSigma)
	SHADER_PARAMETER(uint32, GrayscaleToggle)
	SHADER_PARAMETER(float, InvFullWellCapacity)
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
