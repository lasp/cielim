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

#include "Shaders/QuETonemap.h"
#include "Utilities/Logging/CielimLoggingMacros.h"

DECLARE_GPU_STAT_NAMED(CielimQuETonemapping, TEXT("Cielim Quantum Efficiency Tonemapping Pass"));

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
	InView.AntiAliasingMethod = AAM_FXAA;

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

	FCameraParams CameraParams;
	FImageCorruptionParams CorruptionParams;

	bool bIsCameraView = false;

	if (const ACameraModel *CameraModel = Cast<ACameraModel>(View.ViewActor))
	{
		CameraParams = CameraModel->CameraParams;
		CorruptionParams = CameraModel->CorruptionParams;

		bIsCameraView = true;
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
	}

	// Apply our custom passes

	QuETonemapPass(GraphBuilder, CameraParams, TextureIn, TextureOut);

	// Copy modified end result back into SceneColor texture
	AddCopyTexturePass(GraphBuilder, TextureOut, SceneColor);
}

void FCielimSceneViewExtension::QuETonemapPass(FRDGBuilder &GraphBuilder, const FCameraParams &CameraParams,
											   const FRDGTextureRef &TextureIn, const FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, CielimQuETonemapping);
	RDG_EVENT_SCOPE(GraphBuilder, "Cielim Quantum Efficiency Tonemapping Pass");

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
	QuEParams->QuECurveR = CameraParams.QuECurveR;
	QuEParams->QuECurveG = CameraParams.QuECurveG;
	QuEParams->QuECurveB = CameraParams.QuECurveB;
	QuEParams->CorrectionFactor = CameraParams.CorrectionFactor;
	QuEParams->InvFullWellCapacity = FMath::Max(1.0f / CameraParams.FullWellCapacity, 1e-6);
	QuEParams->InvGamma = FMath::Max(1.0f / CameraParams.Gamma, 1e-6);
	QuEParams->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FQuETonemap> QuETonemapShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply QuE Tonemapping"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  QuETonemapShader, QuEParams);
}
