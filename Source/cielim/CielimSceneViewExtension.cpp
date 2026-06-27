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
#include "Shaders/DistantObjects.h"
#include "Shaders/GaussianPSF.h"
#include "Shaders/LensDistortion.h"
#include "Shaders/QuETonemap.h"
#include "Shaders/ReadNoise.h"
#include "Shaders/SignalGain.h"
#include "Utilities/Logging/CielimLoggingMacros.h"

DECLARE_GPU_STAT_NAMED(DistantObjects, TEXT("DistantObjects"));
DECLARE_GPU_STAT_NAMED(QuETonemapping, TEXT("QuantumEfficiencyTonemapping"));
DECLARE_GPU_STAT_NAMED(LensDistortion, TEXT("LensDistortion"));
DECLARE_GPU_STAT_NAMED(GaussianPSF, TEXT("GaussianPSF"));
DECLARE_GPU_STAT_NAMED(CosmicRays, TEXT("CosmicRays"));
DECLARE_GPU_STAT_NAMED(ReadNoise, TEXT("ReadNoise"));
DECLARE_GPU_STAT_NAMED(SignalGain, TEXT("SignalGain"));

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
	InView.AntiAliasingMethod = AAM_None;

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

	const FRDGTextureRef SceneColor = GetAsTexture(Inputs.SceneTextures->GetContents()->SceneColorTexture);
	const FRDGTextureRef SceneDepth = GetAsTexture(Inputs.SceneTextures->GetContents()->SceneDepthTexture);

	// Intermediates used for texture ping-pong
	FRDGTextureRef TextureIn = GraphBuilder.CreateTexture(SceneColor->Desc, TEXT("Temp Input Texture"));
	FRDGTextureRef TextureOut = GraphBuilder.CreateTexture(SceneColor->Desc, TEXT("Temp Output Texture"));

	// Init input texture as current scene color
	AddCopyTexturePass(GraphBuilder, SceneColor, TextureIn);

	const ACameraModel *CameraModel = Cast<ACameraModel>(View.ViewActor.Get());

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
		CameraParams.Transmission1 = 1.0f;
		CameraParams.Transmission2 = 1.0f;
		CameraParams.Transmission3 = 1.0f;
		CameraParams.Wavelength1 = 650.0f;
		CameraParams.Wavelength2 = 550.0f;
		CameraParams.Wavelength3 = 450.0f;
		CameraParams.QuECurveR = FVector3f::One();
		CameraParams.QuECurveG = FVector3f::One();
		CameraParams.QuECurveB = FVector3f::One();
		CameraParams.CorrectionFactor = 1.0f;
		CameraParams.FullWellCapacity = 50000.0f;
		CameraParams.Gamma = 2.2f;
		CameraParams.bIsGrayscale = false;

		CorruptionParams.KernelWidth = 7;
		CorruptionParams.Sigma = 0.25f;
	}

	if (CameraModel && CameraModel->DistantObjects.Num() > 0)
		DistantObjectsPass(GraphBuilder, View, CameraModel->SolarDirection, CameraModel->SolarSpectralIrradiance,
						   CameraModel->DistantObjects, SceneDepth, TextureIn);

	// These passes operate on light entering camera

	if (CorruptionParams.K1 != 0.0f || CorruptionParams.K2 != 0.0f || CorruptionParams.K3 != 0.0f ||
		CorruptionParams.P1 != 0.0f || CorruptionParams.P2 != 0.0f)
	{
		LensDistortionPass(GraphBuilder, CorruptionParams, TextureIn, TextureOut);
		Swap(TextureIn, TextureOut);
	}

	if (CorruptionParams.KernelWidth > 0 && CorruptionParams.Sigma > 0.0f)
	{
		GaussianPSFPass(GraphBuilder, CorruptionParams, TextureIn, TextureOut);
		Swap(TextureIn, TextureOut);
	}

	QuETonemapPass(GraphBuilder, CameraParams, CorruptionParams, TextureIn, TextureOut);
	Swap(TextureIn, TextureOut);

	// These passes operate on the signal from the sensor

	if (!CameraParams.bIsDiagnosticRun)
	{
		if (CorruptionParams.ReadNoiseSigma > 0.0f || CorruptionParams.StuckPixelRate > 0.0f ||
			CorruptionParams.DeadPixelRate > 0.0f)
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
	}

	// Copy modified end result back into SceneColor texture
	AddCopyTexturePass(GraphBuilder, TextureIn, SceneColor);
}

// ---------- Shader pass definitions ----------

void FCielimSceneViewExtension::DistantObjectsPass(FRDGBuilder &GraphBuilder, const FSceneView &View,
												   const FVector3f &SolarDirection, const FVector3f &SolarIrradiance,
												   const TArray<FDistantObject> &DistantObjects,
												   const FRDGTextureRef &SceneDepth, const FRDGTextureRef &SceneColor)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, DistantObjects);
	RDG_EVENT_SCOPE(GraphBuilder, "DistantObjects");

	const FIntRect &ViewRect = View.UnscaledViewRect;

	FDistantObjectsVS::FParameters *DistantVSParams = GraphBuilder.AllocParameters<FDistantObjectsVS::FParameters>();
	FDistantObjectsPS::FParameters *DistantPSParams = GraphBuilder.AllocParameters<FDistantObjectsPS::FParameters>();

	const FMatrix44f ProjectionMatrix = FMatrix44f(View.ViewMatrices.GetProjectionMatrix());

	const FRDGBufferRef DistantObjectsBuffer =
		CreateStructuredBuffer<FDistantObject>(GraphBuilder, TEXT("DistantObjects"), DistantObjects);

	DistantVSParams->CameraPosition = static_cast<FVector3f>(View.ViewLocation);
	DistantVSParams->ViewProjectionMatrix = FMatrix44f(View.ViewMatrices.GetViewProjectionMatrix());
	DistantVSParams->InverseProjectionX = 1.0f / FMath::Max(ProjectionMatrix.M[0][0], 1e-6f);
	DistantVSParams->InverseProjectionY = 1.0f / FMath::Max(ProjectionMatrix.M[1][1], 1e-6f);
	DistantVSParams->InverseViewWidth = 1.0f / FMath::Max(ViewRect.Width(), 1e-6f);
	DistantVSParams->InverseViewHeight = 1.0f / FMath::Max(ViewRect.Height(), 1e-6f);
	DistantVSParams->SolarDirection = SolarDirection;
	DistantVSParams->SolarSpectralIrradiance = SolarIrradiance;
	DistantVSParams->DistantObjects = GraphBuilder.CreateSRV(DistantObjectsBuffer);

	DistantPSParams->RenderTargets[0] = FRenderTargetBinding(SceneColor, ERenderTargetLoadAction::ELoad);
	DistantPSParams->RenderTargets.DepthStencil =
		FDepthStencilBinding(SceneDepth, ERenderTargetLoadAction::ELoad, FExclusiveDepthStencil::DepthRead);

	FDistantObjectsParameters *PassParams = GraphBuilder.AllocParameters<FDistantObjectsParameters>();
	PassParams->VS = *DistantVSParams;
	PassParams->PS = *DistantPSParams;

	const TShaderMapRef<FDistantObjectsVS> DistantObjectsVS(GetGlobalShaderMap(GMaxRHIFeatureLevel));
	const TShaderMapRef<FDistantObjectsPS> DistantObjectsPS(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	const int NumInstances = DistantObjects.Num();

	GraphBuilder.AddPass(
		RDG_EVENT_NAME("Add Distant Objects"), PassParams, ERDGPassFlags::Raster,
		[PassParams, DistantObjectsVS, DistantObjectsPS, ViewRect, NumInstances](FRHICommandList &RHICmdList)
		{
			FGraphicsPipelineStateInitializer GraphicsPSOInit;
			RHICmdList.ApplyCachedRenderTargets(GraphicsPSOInit);

			RHICmdList.SetViewport(ViewRect.Min.X, ViewRect.Min.Y, 0.0f, ViewRect.Max.X, ViewRect.Max.Y, 1.0f);

			GraphicsPSOInit.BlendState =
				TStaticBlendState<CW_RGBA, BO_Add, BF_One, BF_One, BO_Add, BF_One, BF_One>::GetRHI();

			GraphicsPSOInit.RasterizerState = TStaticRasterizerState<>::GetRHI();

			GraphicsPSOInit.DepthStencilState = TStaticDepthStencilState<true, CF_GreaterEqual>::GetRHI();

			GraphicsPSOInit.PrimitiveType = PT_TriangleStrip;

			GraphicsPSOInit.BoundShaderState.VertexDeclarationRHI = GEmptyVertexDeclaration.VertexDeclarationRHI;

			GraphicsPSOInit.BoundShaderState.VertexShaderRHI = DistantObjectsVS.GetVertexShader();

			GraphicsPSOInit.BoundShaderState.PixelShaderRHI = DistantObjectsPS.GetPixelShader();

			SetGraphicsPipelineState(RHICmdList, GraphicsPSOInit, 0);

			SetShaderParameters(RHICmdList, DistantObjectsVS, DistantObjectsVS.GetVertexShader(), PassParams->VS);
			SetShaderParameters(RHICmdList, DistantObjectsPS, DistantObjectsPS.GetPixelShader(), PassParams->PS);

			RHICmdList.DrawPrimitive(0, 2, NumInstances);
		});
}

void FCielimSceneViewExtension::QuETonemapPass(FRDGBuilder &GraphBuilder, const FCameraParams &CameraParams,
											   const FImageCorruptionParams &CorruptionParams,
											   const FRDGTextureRef &TextureIn, const FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, QuETonemapping);
	RDG_EVENT_SCOPE(GraphBuilder, "QuantumEfficiencyTonemapping");

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
	QuEParams->Transmission1 = CameraParams.Transmission1;
	QuEParams->Transmission2 = CameraParams.Transmission2;
	QuEParams->Transmission3 = CameraParams.Transmission3;
	QuEParams->W1EnergyInverse = CameraParams.Wavelength1 * 5.034e15f; // Multiply by 1/hc [J^-1 nm^-1]
	QuEParams->W2EnergyInverse = CameraParams.Wavelength2 * 5.034e15f; // Multiply by 1/hc [J^-1 nm^-1]
	QuEParams->W3EnergyInverse = CameraParams.Wavelength3 * 5.034e15f; // Multiply by 1/hc [J^-1 nm^-1]
	QuEParams->QuECurveR = FVector4f(CameraParams.QuECurveR, 1.0f);
	QuEParams->QuECurveG = FVector4f(CameraParams.QuECurveG, 1.0f);
	QuEParams->QuECurveB = FVector4f(CameraParams.QuECurveB, 1.0f);
	QuEParams->SimpsonFactor = FMath::Abs(CameraParams.Wavelength1 - CameraParams.Wavelength3) / 6.0f;
	QuEParams->CorrectionFactor = CameraParams.CorrectionFactor;
	QuEParams->CurrentTime = static_cast<uint32>(FDateTime::UtcNow().ToUnixTimestamp());
	QuEParams->EnableShotNoise = static_cast<uint32>(CorruptionParams.bEnableShotNoise);
	QuEParams->DarkCurrent = CorruptionParams.DarkCurrent;
	QuEParams->DarkCurrentPattern = CorruptionParams.DarkCurrentPattern;
	const float Ratio = 4 * FMath::Square(CorruptionParams.DarkCurrentStdDeviation) /
		FMath::Square(FMath::Max(CorruptionParams.DarkCurrent, 1e-6));
	QuEParams->DarkCurrentLogSigma = FMath::Sqrt(FMath::Loge((1 + sqrt(1 + Ratio)) / 2));
	QuEParams->GrayscaleToggle = static_cast<uint32>(CameraParams.bIsGrayscale);
	QuEParams->InvFullWellCapacity = 1.0f / FMath::Max(CameraParams.FullWellCapacity, 1e-6);
	QuEParams->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FQuETonemap> QuETonemapShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply QuE Tonemapping"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  QuETonemapShader, QuEParams);
}

void FCielimSceneViewExtension::LensDistortionPass(FRDGBuilder &GraphBuilder,
												   const FImageCorruptionParams &CorruptionParams,
												   FRDGTextureRef &TextureIn, FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, LensDistortion);
	RDG_EVENT_SCOPE(GraphBuilder, "LensDistortion");

	const FScreenPassTextureViewport Viewport(TextureIn);

	FLensDistortion::FParameters *DistortionParams = GraphBuilder.AllocParameters<FLensDistortion::FParameters>();
	DistortionParams->InputTexture = TextureIn;
	DistortionParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	DistortionParams->AspectRatio = Viewport.Rect.Width() / Viewport.Rect.Height();
	DistortionParams->K1 = CorruptionParams.K1;
	DistortionParams->K2 = CorruptionParams.K2;
	DistortionParams->K3 = CorruptionParams.K3;
	DistortionParams->P1 = CorruptionParams.P1;
	DistortionParams->P2 = CorruptionParams.P2;
	DistortionParams->RenderTargets[0] = FRenderTargetBinding(TextureOut, ERenderTargetLoadAction::EClear);

	const TShaderMapRef<FLensDistortion> DistortionShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

	AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Lens Distortion"), GMaxRHIFeatureLevel, Viewport, Viewport,
					  DistortionShader, DistortionParams);
}

void FCielimSceneViewExtension::GaussianPSFPass(FRDGBuilder &GraphBuilder,
												const FImageCorruptionParams &CorruptionParams,
												FRDGTextureRef &TextureIn, FRDGTextureRef &TextureOut)
{
	RDG_GPU_STAT_SCOPE(GraphBuilder, GaussianPSF);
	RDG_EVENT_SCOPE(GraphBuilder, "GaussianPSF");

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
	RDG_EVENT_SCOPE(GraphBuilder, "ReadNoise");

	const FScreenPassTextureViewport Viewport(TextureIn);

	FReadNoise::FParameters *RnParams = GraphBuilder.AllocParameters<FReadNoise::FParameters>();
	RnParams->InputTexture = TextureIn;
	RnParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
	RnParams->CurrentTime = static_cast<uint32>(FDateTime::UtcNow().ToUnixTimestamp());
	RnParams->ReadNoiseSigma = CorruptionParams.ReadNoiseSigma / FMath::Max(CameraParams.FullWellCapacity, 1e-6);
	RnParams->GrayscaleToggle = static_cast<uint32>(CameraParams.bIsGrayscale);
	RnParams->StuckPixelRate = CorruptionParams.StuckPixelRate;
	RnParams->DeadPixelRate = CorruptionParams.DeadPixelRate;
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
	RDG_EVENT_SCOPE(GraphBuilder, "SignalGain");

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
	RDG_EVENT_SCOPE(GraphBuilder, "CosmicRays");

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
