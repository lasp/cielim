//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of FCielimSceneViewExtension.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CielimSceneViewExtension.h"

#include "PixelShaderUtils.h"
#include "PostProcess/PostProcessInputs.h"
#include "ScreenPass.h"

#include "Shaders/CosmicRays.h"
#include "Shaders/GaussianPSF.h"
#include "Shaders/QuETonemap.h"
#include "Shaders/ReadNoise.h"
#include "Shaders/SignalGain.h"
#include "Utilities/Logging/CielimLoggingMacros.h"

DECLARE_GPU_STAT_NAMED(QuETonemapping, TEXT("Quantum Efficiency Tonemapping Pass"));
DECLARE_GPU_STAT_NAMED(GaussianPSF, TEXT("Gaussian PSF Pass"));
DECLARE_GPU_STAT_NAMED(CosmicRays, TEXT("Cosmic Rays Pass"));
DECLARE_GPU_STAT_NAMED(ReadNoise, TEXT("Read Noise Pass"));
DECLARE_GPU_STAT_NAMED(SignalGain, TEXT("Signal Gain Pass"));

bool FCielimSceneViewExtension::IsActiveThisFrame_Internal(const FSceneViewExtensionContext &Context) const
{
	// Always use this scene view extension
	return true;
}

void FCielimSceneViewExtension::SetupViewFamily(FSceneViewFamily &InViewFamily)
{
	// Do nothing for now
}

void FCielimSceneViewExtension::SetupView(FSceneViewFamily &InViewFamily, FSceneView &InView)
{
	// InView.AntiAliasingMethod = AAM_FXAA;

	if (InView.ViewActor && !InView.ViewActor->GetClass()->GetName().Equals("PlayerController"))
	{
		UE_LOG(LogCielim, Display, TEXT("View setting up for actor: %s"), *InView.ViewActor->GetName());
	}
}

void FCielimSceneViewExtension::PrePostProcessPass_RenderThread(FRDGBuilder &GraphBuilder, const FSceneView &View,
																const FPostProcessingInputs &Inputs)
{
	checkSlow(View.bIsViewInfo);
	Inputs.Validate();

	const FScreenPassTexture ScreenPassTexture((*Inputs.SceneTextures)->SceneColorTexture);
	const FRDGTextureRef SceneColor = ScreenPassTexture.Texture;

	// Intermediates used for texture ping-pong
	FRDGTextureRef TextureIn = GraphBuilder.CreateTexture(SceneColor->Desc, TEXT("Temp Input Texture"));
	FRDGTextureRef TextureOut = GraphBuilder.CreateTexture(SceneColor->Desc, TEXT("Temp Output Texture"));

	// Init input texture as current scene color
	AddCopyTexturePass(GraphBuilder, SceneColor, TextureIn);

	const ACameraModel *CameraModel = Cast<ACameraModel>(View.ViewActor);

	FCameraParams CameraParams{};
	FImageCorruptionParams CorruptionParams{};

	if (CameraModel)
	{
		CameraParams = CameraModel->CameraParams;
		CorruptionParams = CameraModel->CorruptionParams;
	}
	else
	{
		// Set default camera parameters for the viewport window

		CameraParams.ApertureRadius = 0.005f;
		CameraParams.FocalLength = 0.16f;
		CameraParams.SensorWidth = 0.036f;
		CameraParams.SensorHeight = 0.024f;
		CameraParams.ExposureTime = 5e-4f;
		CameraParams.QuECurveR = FVector3f::One();
		CameraParams.QuECurveG = FVector3f::One();
		CameraParams.QuECurveB = FVector3f::One();
		CameraParams.CorrectionFactor = 1.0f;
		CameraParams.FullWellCapacity = 50000.0f;
		CameraParams.Gamma = 2.2f;

		CorruptionParams.KernelWidth = 7;
		CorruptionParams.Sigma = 0.25f;
	}

	// These passes operate on light entering camera

	if (CorruptionParams.KernelWidth > 0 && CorruptionParams.Sigma > 0.0f)
	{
		GaussianPSFPass(GraphBuilder, CorruptionParams, TextureIn, TextureOut);
		Swap(TextureIn, TextureOut);
	}

	QuETonemapPass(GraphBuilder, CameraParams, TextureIn, TextureOut);
	Swap(TextureIn, TextureOut);

	// These passes operate on the signal from the sensor

	if (CorruptionParams.ReadNoiseSigma > 0.0f)
	{
		ReadNoisePass(GraphBuilder, CameraParams, CorruptionParams, TextureIn, TextureOut);
		Swap(TextureIn, TextureOut);
	}

	if (CorruptionParams.SignalGain > 0.0f)
	{
		SignalGainPass(GraphBuilder, CorruptionParams, TextureIn, TextureOut);
		Swap(TextureIn, TextureOut);
	}

	if (CorruptionParams.NumCosmicRays > 0)
	{
		CosmicRaysPass(GraphBuilder, CorruptionParams, TextureIn, TextureOut);
		Swap(TextureIn, TextureOut);
	}

	// Copy modified end result back into SceneColor texture
	AddCopyTexturePass(GraphBuilder, TextureIn, SceneColor);
}

// ---------- Shader pass definitions ----------

void FCielimSceneViewExtension::QuETonemapPass(FRDGBuilder &GraphBuilder, const FCameraParams &CameraParams,
											   const FRDGTextureRef &TextureIn, const FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, QuETonemapping);
	RDG_EVENT_SCOPE(GraphBuilder, "Quantum Efficiency Tonemapping Pass");

	const FScreenPassTextureViewport Viewport(TextureIn);

	// Pre-calculate camera constants

	const float ApertureArea = 3.1415f * CameraParams.ApertureRadius * CameraParams.ApertureRadius;
	const float SolidAngle = ApertureArea / FMath::Max(CameraParams.FocalLength * CameraParams.FocalLength, 1e-6);

	const float PixelWidth = CameraParams.SensorWidth / Viewport.Rect.Width();
	const float PixelHeight = CameraParams.SensorHeight / Viewport.Rect.Height();

	FQuETonemap::FParameters *QuEParams = GraphBuilder.AllocParameters<FQuETonemap::FParameters>();
	QuEParams->InputTexture = TextureIn;
	QuEParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	QuEParams->SolidAngle = SolidAngle;
	QuEParams->PixelArea = PixelWidth * PixelHeight;
	QuEParams->ExposureTime = CameraParams.ExposureTime;
	QuEParams->QuECurveR = FVector4f(CameraParams.QuECurveR, 1.0f);
	QuEParams->QuECurveG = FVector4f(CameraParams.QuECurveG, 1.0f);
	QuEParams->QuECurveB = FVector4f(CameraParams.QuECurveB, 1.0f);
	QuEParams->CorrectionFactor = CameraParams.CorrectionFactor;
	QuEParams->InvFullWellCapacity = 1.0f / FMath::Max(CameraParams.FullWellCapacity, 1e-6);
	QuEParams->InvGamma = 1.0f / FMath::Max(CameraParams.Gamma, 1e-6);
	QuEParams->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FQuETonemap> QuETonemapShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply QuE Tonemapping"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  QuETonemapShader, QuEParams);
}

void FCielimSceneViewExtension::GaussianPSFPass(FRDGBuilder &GraphBuilder,
												const FImageCorruptionParams &CorruptionParams,
												FRDGTextureRef &TextureIn, FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, GaussianPSF);
	RDG_EVENT_SCOPE(GraphBuilder, "GaussianPSF Pass");

	const FScreenPassTextureViewport Viewport(TextureIn);

	// GaussianPSF Horizontal

	FGaussianPSF::FPermutationDomain PermutationDomain;
	PermutationDomain.Set<FGaussianPSF::FHorizontal>(true);

	FGaussianPSF::FParameters *PSFParamsH = GraphBuilder.AllocParameters<FGaussianPSF::FParameters>();
	PSFParamsH->InputTexture = TextureIn;
	PSFParamsH->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	PSFParamsH->TexelSize = FVector2f(1.0f / Viewport.Rect.Width(), 1.0f / Viewport.Rect.Height());
	PSFParamsH->KernelRadius = (CorruptionParams.KernelWidth - 1.0f) / 2.0f;
	PSFParamsH->Sigma = CorruptionParams.Sigma;
	PSFParamsH->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FGaussianPSF> GaussianPSFShaderH(GetGlobalShaderMap(GMaxRHIFeatureLevel), PermutationDomain);

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply GaussianPSF H"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  GaussianPSFShaderH, PSFParamsH);

	Swap(TextureIn, TextureOut);

	// GaussianPSF Vertical

	PermutationDomain.Set<FGaussianPSF::FHorizontal>(false);

	const TShaderMapRef<FGaussianPSF> GaussianPSFShaderV(GetGlobalShaderMap(GMaxRHIFeatureLevel), PermutationDomain);

	FGaussianPSF::FParameters *PSFParamsV = GraphBuilder.AllocParameters<FGaussianPSF::FParameters>();
	PSFParamsV->InputTexture = TextureIn;
	PSFParamsV->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	PSFParamsV->TexelSize = FVector2f(1.0f / Viewport.Rect.Width(), 1.0f / Viewport.Rect.Height());
	PSFParamsV->KernelRadius = (CorruptionParams.KernelWidth - 1.0f) / 2.0f;
	PSFParamsV->Sigma = CorruptionParams.Sigma;
	PSFParamsV->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply GaussianPSF V"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  GaussianPSFShaderV, PSFParamsV);
}

void FCielimSceneViewExtension::ReadNoisePass(FRDGBuilder &GraphBuilder, const FCameraParams &CameraParams,
											  const FImageCorruptionParams &CorruptionParams,
											  const FRDGTextureRef &TextureIn, const FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, ReadNoise);
	RDG_EVENT_SCOPE(GraphBuilder, "Read Noise Pass");

	const FScreenPassTextureViewport Viewport(TextureIn);

	FReadNoise::FParameters *RnParams = GraphBuilder.AllocParameters<FReadNoise::FParameters>();
	RnParams->InputTexture = TextureIn;
	RnParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	RnParams->CurrentTime = static_cast<uint32>(FDateTime::UtcNow().ToUnixTimestamp());
	RnParams->ReadNoiseSigma = CorruptionParams.ReadNoiseSigma / FMath::Max(CameraParams.FullWellCapacity, 1e-6);
	RnParams->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FReadNoise> ReadNoiseShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Read Noise"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  ReadNoiseShader, RnParams);
}

void FCielimSceneViewExtension::SignalGainPass(FRDGBuilder &GraphBuilder,
											   const FImageCorruptionParams &CorruptionParams,
											   const FRDGTextureRef &TextureIn, const FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, SignalGain);
	RDG_EVENT_SCOPE(GraphBuilder, "Signal Gain Pass");

	const FScreenPassTextureViewport Viewport(TextureIn);

	FSignalGain::FParameters *GainParams = GraphBuilder.AllocParameters<FSignalGain::FParameters>();
	GainParams->InputTexture = TextureIn;
	GainParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	GainParams->SignalGain = CorruptionParams.SignalGain;
	GainParams->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FSignalGain> SignalGainShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Signal Gain"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  SignalGainShader, GainParams);
}

void FCielimSceneViewExtension::CosmicRaysPass(FRDGBuilder &GraphBuilder,
											   const FImageCorruptionParams &CorruptionParams,
											   const FRDGTextureRef &TextureIn, const FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, CosmicRays);
	RDG_EVENT_SCOPE(GraphBuilder, "Cosmic Rays Pass");

	const FScreenPassTextureViewport Viewport(TextureIn);

	const FRDGBufferRef StartBuffer =
		CreateStructuredBuffer<FVector2f>(GraphBuilder, TEXT("StartPoints"), CorruptionParams.StartPoints);
	const FRDGBufferRef EndBuffer =
		CreateStructuredBuffer<FVector2f>(GraphBuilder, TEXT("EndPoints"), CorruptionParams.EndPoints);
	const FRDGBufferRef WidthBuffer =
		CreateStructuredBuffer<float>(GraphBuilder, TEXT("LineWidths"), CorruptionParams.LineWidths);

	FCosmicRays::FParameters *RayParams = GraphBuilder.AllocParameters<FCosmicRays::FParameters>();
	RayParams->InputTexture = TextureIn;
	RayParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	RayParams->NumRays = CorruptionParams.NumCosmicRays;
	RayParams->StartPoints = GraphBuilder.CreateSRV(StartBuffer, PF_G32R32F);
	RayParams->EndPoints = GraphBuilder.CreateSRV(EndBuffer, PF_G32R32F);
	RayParams->LineWidths = GraphBuilder.CreateSRV(WidthBuffer, PF_R32_FLOAT);
	RayParams->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FCosmicRays> CosmicRayShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Cosmic Rays"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  CosmicRayShader, RayParams);
}
