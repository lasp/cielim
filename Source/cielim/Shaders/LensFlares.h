//=================== Copyright (c) 2026 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FLensFlare class used to wrap its corresponding global shader.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "GlobalShader.h"
#include "ShaderParameterStruct.h"

class FLensFlares : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FLensFlares);
	SHADER_USE_PARAMETER_STRUCT(FLensFlares, FGlobalShader);

	// Parameter block bound by Render Graph. Scene inputs (radiance, sun projection, viewport) plus
	// the FStrayLightParams tunables and the sensor's ExposureTime / IsGrayscale. See LensFlares.usf
	// for what each drives.
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
	SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
	SHADER_PARAMETER_SAMPLER(SamplerState, InputSampler)
	SHADER_PARAMETER(FVector3f, SolarSpectralRadiance) // Sun blackbody radiance (per wavelength); flare amplitude
	SHADER_PARAMETER(FVector4f, SunClipPosition) // Sun position in clip space; w<=0 gates the flare (behind camera)
	SHADER_PARAMETER(FVector2f, SunFlareUV) // Sun position in flare-UV space, remapped by off-boresight angle
	SHADER_PARAMETER(float, StrayLightVisibility) // Baffle-shield fade: 1 in view, ramps to 0 at the cutoff angle
	SHADER_PARAMETER(float, StrayLightIntensity) // Overall flare brightness as a fraction of solar radiance
	SHADER_PARAMETER(float, SunRadiusUV) // Sun angular radius in UV; core disc size
	SHADER_PARAMETER(float, AspectRatio) // Viewport aspect, to keep the flare circular
	SHADER_PARAMETER(float, CoreSize) // Core disc size scale [0.1, 1]
	SHADER_PARAMETER(float, GhostSize) // Global ghost size [0.1, 1.25]
	SHADER_PARAMETER(float, GhostTransmittance) // Global ghost brightness [0.5, 1.5]
	SHADER_PARAMETER(float, Ghost1RelativeSize) // Per-ghost size scales (1st..4th), each [0.25, 1]
	SHADER_PARAMETER(float, Ghost2RelativeSize)
	SHADER_PARAMETER(float, Ghost3RelativeSize)
	SHADER_PARAMETER(float, Ghost4RelativeSize)
	SHADER_PARAMETER(float, GhostBrightnessSizeExponent) // Ghost brightness<->size coupling exponent
	SHADER_PARAMETER(float, CoronaFalloffExponent) // Corona aureole falloff (higher = tighter) [0.5, 2]
	SHADER_PARAMETER(float, CoronaIntensity) // Corona brightness relative to the core [0, 1]
	SHADER_PARAMETER(float, NumRays) // Number of symmetric rays (even -> mirror-symmetric) [0, 15]
	SHADER_PARAMETER(float, RaySharpness) // Ray angular sharpness (higher = narrower) [0, 30]
	SHADER_PARAMETER(float, RayWeight) // Ray strength relative to the random streaks [0, 1]
	SHADER_PARAMETER(float, ExposureTime) // Sensor exposure; scales the streak length
	SHADER_PARAMETER(uint32, IsGrayscale) // 1 = achromatic ghosts, 0 = chromatic offsets
	RENDER_TARGET_BINDING_SLOTS()
	END_SHADER_PARAMETER_STRUCT()
};
