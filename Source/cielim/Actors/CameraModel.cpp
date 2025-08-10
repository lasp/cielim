//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of ACameraModel.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CameraModel.h"

#include <random>

#include "ImageUtils.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "RHIGPUReadback.h"
#include "ScreenPass.h"

#include "cielim/Shaders/CenBrightReduce.h"
#include "cielim/Shaders/CosmicRays.h"
#include "cielim/Shaders/GaussianPSF.h"
#include "cielim/Shaders/QuETonemap.h"
#include "cielim/Shaders/ReadNoise.h"
#include "cielim/Shaders/SignalGain.h"
#include "cielim/Utilities/Logging/CielimLoggingMacros.h"

DECLARE_GPU_STAT_NAMED(CielimQuETonemapping, TEXT("Cielim Quantum Efficiency Tonemapping Pass Stat"));
DECLARE_GPU_STAT_NAMED(CielimCobReductionCalculations, TEXT("Cielim Center of Brightness Reduction Calculations Stat"));
DECLARE_GPU_STAT_NAMED(CielimPostProcessCorruptionPasses, TEXT("Cielim Post-Process Corruption Passes Stat"));
DECLARE_GPU_STAT_NAMED(GaussianPSF, TEXT("Gaussian PSF Pass Stat"));
DECLARE_GPU_STAT_NAMED(CosmicRays, TEXT("Cosmic Rays Pass Stat"));
DECLARE_GPU_STAT_NAMED(ReadNoise, TEXT("Read Noise Pass Stat"));
DECLARE_GPU_STAT_NAMED(SignalGain, TEXT("Signal Gain Pass Stat"));

ACameraModel::ACameraModel()
{
	// Default reversed-Z perspective matrix with fov = 90 degrees in the case none is given
	const FMatrix ProjectionMatrix =
		FMatrix(FPlane(1.0f, 0, 0, 0), FPlane(0, 1.0f, 0, 0), FPlane(0, 0, 0, 1), FPlane(0, 0, 10.0f, 0));

	// Set up the SceneCaptureComponent2D and its default settings
	this->SceneCaptureComponent2D = CreateDefaultSubobject<UCameraViewCaptureComponent2D>(TEXT("CaptureComponent"));
	this->SceneCaptureComponent2D->TextureTarget = NewObject<UTextureRenderTarget2D>(this, TEXT("RT_Spacecraft"));
	this->SceneCaptureComponent2D->TextureTarget->InitCustomFormat(2560, 1440, PF_FloatRGBA, true);
	this->SceneCaptureComponent2D->TextureTarget->UpdateResourceImmediate();
	this->SceneCaptureComponent2D->bCaptureEveryFrame = false;
	this->SceneCaptureComponent2D->bCaptureOnMovement = false;
	this->SceneCaptureComponent2D->bUseCustomProjectionMatrix = true;
	this->SceneCaptureComponent2D->CustomProjectionMatrix = ProjectionMatrix;

	// Disable exposure and ensure we're getting the raw linear HDR color
	this->SceneCaptureComponent2D->CaptureSource = SCS_FinalColorHDR;
	this->SceneCaptureComponent2D->PostProcessBlendWeight = 0.0f;
	this->SceneCaptureComponent2D->ShowFlags.SetTonemapper(false);

	// Disable SSAO to improve performance given deep space doesn't have ambient light sources
	this->SceneCaptureComponent2D->ShowFlags.SetAmbientOcclusion(false);

	this->RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	this->Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	this->Body->SetupAttachment(RootComponent);
	this->SceneCaptureComponent2D->SetupAttachment(Body);
}

void ACameraModel::BeginPlay() { Super::BeginPlay(); }

// Called every frame
void ACameraModel::Tick(float DeltaTime) { Super::Tick(DeltaTime); }

void ACameraModel::SaveImageToDisk(const FString &FilePath, const FString &Filename)
{
	UKismetRenderingLibrary::ExportRenderTarget(this, this->SceneCaptureComponent2D->TextureTarget, FilePath, Filename);
}

void ACameraModel::GetCorruptedImage(TArray64<uint8> &ImageData, TOptional<FVector2D> &CobCoordinates,
									 const cielimMessage::CameraModel &CameraModel) const
{
	FImage Image;

	auto CosmicRays = GetCosmicRays(CameraModel.renderparameters().cosmicraystddeviation());

	uint32 NumCosmicRays = CosmicRays.Get<0>();
	TResourceArray<FVector2f> StartPoints = CosmicRays.Get<1>();
	TResourceArray<FVector2f> EndPoints = CosmicRays.Get<2>();
	TResourceArray<float> LineWidths = CosmicRays.Get<3>();

	FImageCorruptionParams CorruptionParams = {7,
											   CameraModel.pointspreadfunction(),
											   NumCosmicRays,
											   StartPoints,
											   EndPoints,
											   LineWidths,
											   static_cast<float>(CameraModel.readnoise()),
											   static_cast<float>(CameraModel.systemgain())};

	this->ApplyQuETonemapping(CameraModel);

	this->GetCenterOfBrightness(CobCoordinates);

	this->ApplyPostProcessShaders(CorruptionParams);

	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent2D->TextureTarget, Image));

	// Take modified image data from Image and copy to ImageData as PNG
	verify(FImageUtils::CompressImage(ImageData, TEXT("PNG"), Image));
}

void ACameraModel::ApplyQuETonemapping(const cielimMessage::CameraModel &CameraModel) const
{
	UTextureRenderTarget2D *RenderTarget = this->SceneCaptureComponent2D->TextureTarget;

	if (!RenderTarget)
		return;

	FTextureRenderTargetResource *RTResource = RenderTarget->GameThread_GetRenderTargetResource();

	const float ApertureRadius = CameraModel.apertureradius() == 0.0f ? 0.005f : CameraModel.apertureradius();
	const float FocalLength = CameraModel.focallength() == 0.0f ? 0.16f : CameraModel.focallength();
	const float SensorWidth = CameraModel.sensorwidth() == 0.0f ? 0.036f : CameraModel.sensorwidth();
	const float SensorHeight = CameraModel.sensorheight() == 0.0f ? 0.024f : CameraModel.sensorheight();
	const float ExposureTime = CameraModel.exposuretime() == 0.0f ? 1e-3f : CameraModel.exposuretime();
	const float CorrectionFactor =
		CameraModel.integrationweightfactor() == 0.0f ? 1.0f : CameraModel.integrationweightfactor();
	const float FullWellCapacity = CameraModel.fullwellcapacity() == 0.0f ? 50000.0f : CameraModel.fullwellcapacity();
	const float Gamma = CameraModel.gamma() == 0.0f ? 2.2f : CameraModel.gamma();

	FVector3f QuECurveR = FVector3f::One();
	FVector3f QuECurveG = FVector3f::One();
	FVector3f QuECurveB = FVector3f::One();

	if (CameraModel.has_qecurve())
	{
		const auto QuECurve = CameraModel.qecurve();
		QuECurveR = FVector3f(QuECurve.redvalue650nm(), QuECurve.redvalue550nm(), QuECurve.redvalue450nm());
		QuECurveG = FVector3f(QuECurve.greenvalue650nm(), QuECurve.greenvalue550nm(), QuECurve.greenvalue450nm());
		QuECurveB = FVector3f(QuECurve.bluevalue650nm(), QuECurve.bluevalue550nm(), QuECurve.bluevalue450nm());
	}

	FCameraParams CameraParams = {ApertureRadius,	FocalLength,	  SensorWidth, SensorHeight,
								  ExposureTime,		QuECurveR,		  QuECurveG,   QuECurveB,
								  CorrectionFactor, FullWellCapacity, Gamma};

	FRenderCommandFence Fence;

	ENQUEUE_RENDER_COMMAND(ApplyQuETonemapping)
	(
		[RTResource, &CameraParams](FRHICommandListImmediate &RHICmdList)
		{
			FRDGBuilder GraphBuilder(RHICmdList);

			{
				RDG_GPU_STAT_SCOPE(GraphBuilder, CielimQuETonemapping);
				RDG_EVENT_SCOPE(GraphBuilder, "Cielim Quantum Efficiency Tonemapping Pass");

				const FRDGTextureRef RenderTargetBase = RegisterExternalTexture(
					GraphBuilder, RTResource->GetRenderTargetTexture(), TEXT("RenderTargetBase"));

				const FRDGTextureRef TempTextureIn =
					GraphBuilder.CreateTexture(RenderTargetBase->Desc, TEXT("Temp Input Texture"));

				AddCopyTexturePass(GraphBuilder, RenderTargetBase, TempTextureIn);

				const FScreenPassTextureViewport Viewport(RenderTargetBase);

				// Pre-calculate camera constants

				const float ApertureArea = 3.1415f * CameraParams.ApertureRadius * CameraParams.ApertureRadius;
				const float SolidAngle =
					ApertureArea / FMath::Max(CameraParams.FocalLength * CameraParams.FocalLength, 1e-6);

				const float PixelWidth = CameraParams.SensorWidth / Viewport.Rect.Width();
				const float PixelHeight = CameraParams.SensorHeight / Viewport.Rect.Height();

				FQuETonemap::FParameters *QuEParams = GraphBuilder.AllocParameters<FQuETonemap::FParameters>();
				QuEParams->InputTexture = TempTextureIn;
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
				QuEParams->RenderTargets[0] =
					FRenderTargetBinding(RenderTargetBase, ERenderTargetLoadAction::ENoAction);

				const TShaderMapRef<FQuETonemap> QuETonemapShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

				AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply QuE Tonemapping"), GMaxRHIFeatureLevel, Viewport,
								  Viewport, QuETonemapShader, QuEParams);
			}

			GraphBuilder.Execute();
			RHICmdList.SubmitCommandsAndFlushGPU(); // Metals refuses to auto-flush unless forced
		});

	Fence.BeginFence();
	Fence.Wait();
}

void ACameraModel::GetCenterOfBrightness(TOptional<FVector2D> &CobCoordinates) const
{
	UTextureRenderTarget2D *RenderTarget = this->SceneCaptureComponent2D->TextureTarget;

	if (!RenderTarget)
		return;

	FTextureRenderTargetResource *RTResource = RenderTarget->GameThread_GetRenderTargetResource();
	FRHIGPUBufferReadback Readback(TEXT("COB Reduction Calculations Readback"));

	const uint32 Width = RenderTarget->SizeX;
	const uint32 Height = RenderTarget->SizeY;

	const uint32 GroupCountX = FMath::DivideAndRoundUp(Width, 16u);
	const uint32 GroupCountY = FMath::DivideAndRoundUp(Height, 16u);
	const uint32 NumGroups = GroupCountX * GroupCountY;

	FRenderCommandFence Fence;

	ENQUEUE_RENDER_COMMAND(COB_Calculations)
	(
		[RTResource, &Readback, Width, Height, GroupCountX, GroupCountY,
		 NumGroups](FRHICommandListImmediate &RHICmdList)
		{
			FRDGBuilder GraphBuilder(RHICmdList);

			const FRDGTextureRef RenderTargetBase =
				RegisterExternalTexture(GraphBuilder, RTResource->GetRenderTargetTexture(), TEXT("RenderTarget"));

			const FRDGBufferDesc PartialSumsDesc = FRDGBufferDesc::CreateStructuredDesc(sizeof(FVector4f), NumGroups);
			const FRDGBufferRef PartialSumsBuffer =
				GraphBuilder.CreateBuffer(PartialSumsDesc, TEXT("PartialSumsBuffer"));

			FCenBrightReduce::FParameters *CobParams = GraphBuilder.AllocParameters<FCenBrightReduce::FParameters>();
			CobParams->InputTexture = RenderTargetBase;
			CobParams->TextureSize = FIntPoint(Width, Height);
			CobParams->PartialSumBuffer = GraphBuilder.CreateUAV(PartialSumsBuffer, PF_A32B32G32R32F);

			{
				RDG_GPU_STAT_SCOPE(GraphBuilder, CielimCobReductionCalculations);
				RDG_EVENT_SCOPE(GraphBuilder, "Cielim Center of Brightness GPU Reduction Calculations");

				const TShaderMapRef<FCenBrightReduce> CenBrightReduceShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

				const FIntVector GroupCount = FIntVector(GroupCountX, GroupCountY, 1);
				FComputeShaderUtils::AddPass(GraphBuilder, RDG_EVENT_NAME("ComputeCOB"), CenBrightReduceShader,
											 CobParams, GroupCount);

				AddEnqueueCopyPass(GraphBuilder, &Readback, PartialSumsBuffer, sizeof(FVector4f) * NumGroups);
			}

			GraphBuilder.Execute();
			RHICmdList.SubmitCommandsAndFlushGPU(); // Metals refuses to auto-flush unless forced
		});

	Fence.BeginFence();
	Fence.Wait();

	ENQUEUE_RENDER_COMMAND(COB_Readback)
	(
		[&Readback, &CobCoordinates, NumGroups](FRHICommandListImmediate &RHICmdList)
		{
			const double StartTime = FPlatformTime::Seconds();

			while (!Readback.IsReady())
			{
				FPlatformProcess::Sleep(0.001f);

				if (FPlatformTime::Seconds() - StartTime > 5.0f)
				{
					UE_LOG(LogCielim, Warning, TEXT("Readback polling has timed out; skipping readback..."));
					break;
				}
			}

			if (Readback.IsReady())
			{
				const FVector4f *RawData = static_cast<FVector4f *>(Readback.Lock(sizeof(FVector4f) * NumGroups));

				float LuminanceSum = 0;
				float XLuminanceSum = 0;
				float YLuminanceSum = 0;

				for (uint32 i = 0; i < NumGroups; i++)
				{
					const FVector4f Temp = RawData[i];
					LuminanceSum += Temp.X;
					XLuminanceSum += Temp.Y;
					YLuminanceSum += Temp.Z;
				}

				if (LuminanceSum > 0.0f)
				{
					const double CenterX = XLuminanceSum / LuminanceSum;
					const double CenterY = YLuminanceSum / LuminanceSum;
					CobCoordinates = FVector2D(CenterX, CenterY);
				}

				Readback.Unlock();
			}
		});

	Fence.BeginFence();
	Fence.Wait();

	if (CobCoordinates.IsSet())
		UE_LOG(LogCielim, Display, TEXT("Center of Brightness: %f, %f"), CobCoordinates->X, CobCoordinates->Y);
}

void ACameraModel::ApplyPostProcessShaders(const FImageCorruptionParams &CorruptionParams) const
{
	UTextureRenderTarget2D *RenderTarget = this->SceneCaptureComponent2D->TextureTarget;

	if (!RenderTarget)
		return;

	FTextureRenderTargetResource *RTResource = RenderTarget->GameThread_GetRenderTargetResource();

	ENQUEUE_RENDER_COMMAND(ApplyPostProcess)
	(
		[RTResource, &CorruptionParams](FRHICommandListImmediate &RHICmdList)
		{
			FRDGBuilder GraphBuilder(RHICmdList);

			{
				RDG_GPU_STAT_SCOPE(GraphBuilder, CielimPostProcessCorruptionPasses);
				RDG_EVENT_SCOPE(GraphBuilder, "Cielim Post-Process Corruption Passes");

				const FRDGTextureRef RenderTargetBase = RegisterExternalTexture(
					GraphBuilder, RTResource->GetRenderTargetTexture(), TEXT("RenderTargetBase"));

				// Intermediates used for texture ping-pong
				FRDGTextureRef TempTextureIn =
					GraphBuilder.CreateTexture(RenderTargetBase->Desc, TEXT("Temp Input Texture"));
				FRDGTextureRef TempTextureOut =
					GraphBuilder.CreateTexture(RenderTargetBase->Desc, TEXT("Temp Output Texture"));

				AddCopyTexturePass(GraphBuilder, RenderTargetBase, TempTextureIn);

				const FScreenPassTextureViewport Viewport(RenderTargetBase);

				if (CorruptionParams.Sigma != 0.0f)
				{
					RDG_GPU_STAT_SCOPE(GraphBuilder, GaussianPSF);
					RDG_EVENT_SCOPE(GraphBuilder, "GaussianPSF Pass");

					// GaussianPSF Horizontal

					FGaussianPSF::FPermutationDomain PermutationDomain;
					PermutationDomain.Set<FGaussianPSF::FHorizontal>(true);

					FGaussianPSF::FParameters *PSFParamsH = GraphBuilder.AllocParameters<FGaussianPSF::FParameters>();
					PSFParamsH->InputTexture = TempTextureIn;
					PSFParamsH->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
					PSFParamsH->TexelSize = FVector2f(1.0f / Viewport.Rect.Width(), 1.0f / Viewport.Rect.Height());
					PSFParamsH->KernelRadius = (CorruptionParams.KernelWidth - 1.0f) / 2.0f;
					PSFParamsH->Sigma = CorruptionParams.Sigma;
					PSFParamsH->RenderTargets[0] =
						FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

					const TShaderMapRef<FGaussianPSF> GaussianPSFShaderH(GetGlobalShaderMap(GMaxRHIFeatureLevel),
																		 PermutationDomain);

					AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply GaussianPSF H"), GMaxRHIFeatureLevel,
									  Viewport, Viewport, GaussianPSFShaderH, PSFParamsH);

					Swap(TempTextureIn, TempTextureOut);

					// GaussianPSF Vertical

					PermutationDomain.Set<FGaussianPSF::FHorizontal>(false);

					const TShaderMapRef<FGaussianPSF> GaussianPSFShaderV(GetGlobalShaderMap(GMaxRHIFeatureLevel),
																		 PermutationDomain);

					FGaussianPSF::FParameters *PSFParamsV = GraphBuilder.AllocParameters<FGaussianPSF::FParameters>();
					PSFParamsV->InputTexture = TempTextureIn;
					PSFParamsV->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
					PSFParamsV->TexelSize = FVector2f(1.0f / Viewport.Rect.Width(), 1.0f / Viewport.Rect.Height());
					PSFParamsV->KernelRadius = (CorruptionParams.KernelWidth - 1.0f) / 2.0f;
					PSFParamsV->Sigma = CorruptionParams.Sigma;
					PSFParamsV->RenderTargets[0] =
						FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

					AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply GaussianPSF V"), GMaxRHIFeatureLevel,
									  Viewport, Viewport, GaussianPSFShaderV, PSFParamsV);

					Swap(TempTextureIn, TempTextureOut);
				}

				if (CorruptionParams.NumCosmicRays != 0.0f)
				{
					// Cosmic Rays

					RDG_GPU_STAT_SCOPE(GraphBuilder, CosmicRays);
					RDG_EVENT_SCOPE(GraphBuilder, "Cosmic Rays Pass");

					const FRDGBufferRef StartBuffer = CreateStructuredBuffer<FVector2f>(
						GraphBuilder, TEXT("StartPoints"), CorruptionParams.StartPoints);
					const FRDGBufferRef EndBuffer =
						CreateStructuredBuffer<FVector2f>(GraphBuilder, TEXT("EndPoints"), CorruptionParams.EndPoints);
					const FRDGBufferRef WidthBuffer =
						CreateStructuredBuffer<float>(GraphBuilder, TEXT("LineWidths"), CorruptionParams.LineWidths);

					FCosmicRays::FParameters *RayParams = GraphBuilder.AllocParameters<FCosmicRays::FParameters>();
					RayParams->InputTexture = TempTextureIn;
					RayParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
					RayParams->NumRays = CorruptionParams.NumCosmicRays;
					RayParams->StartPoints = GraphBuilder.CreateSRV(StartBuffer, PF_G32R32F);
					RayParams->EndPoints = GraphBuilder.CreateSRV(EndBuffer, PF_G32R32F);
					RayParams->LineWidths = GraphBuilder.CreateSRV(WidthBuffer, PF_R32_FLOAT);
					RayParams->RenderTargets[0] =
						FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

					const TShaderMapRef<FCosmicRays> CosmicRayShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

					AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Cosmic Rays"), GMaxRHIFeatureLevel, Viewport,
									  Viewport, CosmicRayShader, RayParams);

					Swap(TempTextureIn, TempTextureOut);
				}

				if (CorruptionParams.ReadNoiseSigma != 0.0f)
				{
					RDG_GPU_STAT_SCOPE(GraphBuilder, ReadNoise);
					RDG_EVENT_SCOPE(GraphBuilder, "Read Noise Pass");

					FReadNoise::FParameters *RnParams = GraphBuilder.AllocParameters<FReadNoise::FParameters>();
					RnParams->InputTexture = TempTextureIn;
					RnParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
					RnParams->CurrentTime = static_cast<uint32>(FDateTime::UtcNow().ToUnixTimestamp());
					RnParams->ReadNoiseSigma = CorruptionParams.ReadNoiseSigma;
					RnParams->RenderTargets[0] =
						FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

					const TShaderMapRef<FReadNoise> ReadNoiseShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

					AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Read Noise"), GMaxRHIFeatureLevel, Viewport,
									  Viewport, ReadNoiseShader, RnParams);

					Swap(TempTextureIn, TempTextureOut);
				}

				if (CorruptionParams.SignalGain != 0.0f)
				{
					RDG_GPU_STAT_SCOPE(GraphBuilder, SignalGain);
					RDG_EVENT_SCOPE(GraphBuilder, "Signal Gain Pass");

					FSignalGain::FParameters *GainParams = GraphBuilder.AllocParameters<FSignalGain::FParameters>();
					GainParams->InputTexture = TempTextureIn;
					GainParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
					GainParams->SignalGain = CorruptionParams.SignalGain;
					GainParams->RenderTargets[0] =
						FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

					const TShaderMapRef<FSignalGain> SignalGainShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

					AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Signal Gain"), GMaxRHIFeatureLevel, Viewport,
									  Viewport, SignalGainShader, GainParams);

					Swap(TempTextureIn, TempTextureOut);
				}

				AddCopyTexturePass(GraphBuilder, TempTextureIn, RenderTargetBase);
			}

			GraphBuilder.Execute();
		});
}

// Helper Functions

TTuple<float, TResourceArray<FVector2f>, TResourceArray<FVector2f>, TResourceArray<float>>
ACameraModel::GetCosmicRays(const float Sigma) const
{
	std::default_random_engine Generator;

	std::poisson_distribution CosmicRayDistribution(Sigma);
	const uint32 NumCosmicRays = CosmicRayDistribution(Generator);

	TResourceArray<FVector2f> StartPoints;
	TResourceArray<FVector2f> EndPoints;
	TResourceArray<float> LineWidths;

	if (NumCosmicRays != 0)
	{
		StartPoints.Reserve(NumCosmicRays);
		EndPoints.Reserve(NumCosmicRays);
		LineWidths.Reserve(NumCosmicRays);

		for (uint32 i = 0; i < NumCosmicRays; i++)
		{
			auto TempParams = GetCosmicRayParams();
			StartPoints.Add(TempParams.Get<0>());
			EndPoints.Add(TempParams.Get<1>());
			LineWidths.Add(TempParams.Get<2>());
		}
	}

	return TTuple<float, TResourceArray<FVector2f>, TResourceArray<FVector2f>, TResourceArray<float>>(
		NumCosmicRays, StartPoints, EndPoints, LineWidths);
}

TTuple<FVector2f, FVector2f, float> ACameraModel::GetCosmicRayParams() const
{
	const uint32 SizeX = this->SceneCaptureComponent2D->TextureTarget->SizeX;
	const uint32 SizeY = this->SceneCaptureComponent2D->TextureTarget->SizeY;

	// Calculate starting point
	const float XStartCoord = FMath::RandRange(0, SizeX);
	const float YStartCoord = FMath::RandRange(0, SizeY);

	FVector2f StartPoint(XStartCoord, YStartCoord);

	// Calculate angle
	const float Angle = FMath::FRandRange(0.0f, 2 * PI);

	// Calculate length (Exponential)
	const float Uniform0 = FMath::FRandRange(0.0, 1.0);
	const float Length = -1 * 50 * FMath::Loge(Uniform0);

	// Calculate ending point
	float XStopCoord = XStartCoord + Length * FMath::Cos(Angle);
	float YStopCoord = YStartCoord + Length * FMath::Sin(Angle);

	XStopCoord = FMath::Clamp(XStopCoord, 0.0f, static_cast<float>(SizeX));
	YStopCoord = FMath::Clamp(YStopCoord, 0.0f, static_cast<float>(SizeY));

	FVector2f EndPoint(XStopCoord, YStopCoord);

	// calculate width (Exponential)
	const float Uniform1 = FMath::FRandRange(0.0, 1.0);
	float Width = -1 * 0.5f * FMath::Loge(Uniform1);

	return TTuple<FVector2f, FVector2f, float>(StartPoint, EndPoint, Width);
}
