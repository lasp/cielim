#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FSignalGain : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FSignalGain);
	SHADER_USE_PARAMETER_STRUCT(FSignalGain, FGlobalShader);

	// Defines the parameter block recognized by Render Graph
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(float, SignalGain)
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
