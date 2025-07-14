//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of ACameraModel.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CameraModel.h"

#include <random>

#include "Components/SceneCaptureComponent2D.h"
#include "ImageUtils.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "RHIGPUReadback.h"
#include "ScreenPass.h"

#include "cielim/Shaders/CenBrightReduce.h"
#include "cielim/Shaders/CosmicRays.h"
#include "cielim/Shaders/GaussianPSF.h"
#include "cielim/Shaders/ReadNoise.h"
#include "cielim/Shaders/SignalGain.h"
#include "cielim/Utilities/Logging/CielimLoggingMacros.h"

ACameraModel::ACameraModel()
{
	// Default reversed-Z perspective matrix with fov = 90 degrees in the case none is given
	const FMatrix ProjectionMatrix =
		FMatrix(FPlane(1.0f, 0, 0, 0), FPlane(0, 1.0f, 0, 0), FPlane(0, 0, 0, 1), FPlane(0, 0, 10.0f, 0));

	// Set up the SceneCaptureComponent2D and its default settings
	this->SceneCaptureComponent2D = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("SceneCaptureComponent2D"));
	this->SceneCaptureComponent2D->TextureTarget = NewObject<UTextureRenderTarget2D>(this, TEXT("RT_Spacecraft"));
	this->SceneCaptureComponent2D->TextureTarget->RenderTargetFormat = RTF_RGBA8;
	this->SceneCaptureComponent2D->TextureTarget->InitAutoFormat(2560, 1440);
	this->SceneCaptureComponent2D->TextureTarget->UpdateResourceImmediate();
	this->SceneCaptureComponent2D->bCaptureEveryFrame = false;
	this->SceneCaptureComponent2D->bUseCustomProjectionMatrix = true;
	this->SceneCaptureComponent2D->CustomProjectionMatrix = ProjectionMatrix;

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
									 const double PointSpread, const double ReadNoise, const double SystemGain,
									 const double CosmicRaysStdDev) const
{
	FImage Image;

	auto CosmicRays = GetCosmicRays(CosmicRaysStdDev);

	uint32 NumCosmicRays = CosmicRays.Get<0>();
	TResourceArray<FVector2f> StartPoints = CosmicRays.Get<1>();
	TResourceArray<FVector2f> EndPoints = CosmicRays.Get<2>();
	TResourceArray<float> LineWidths = CosmicRays.Get<3>();

	FImageCorruptionParams CorruptionParams = {7,
											   PointSpread,
											   NumCosmicRays,
											   StartPoints,
											   EndPoints,
											   LineWidths,
											   static_cast<float>(ReadNoise),
											   static_cast<float>(SystemGain)};

	this->SceneCaptureComponent2D->CaptureScene();

	CobCoordinates = this->GetCenterOfBrightness(this->SceneCaptureComponent2D->TextureTarget);

	this->ApplyPostProcessShaders(this->SceneCaptureComponent2D->TextureTarget, &CorruptionParams);

	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent2D->TextureTarget, Image));

	// Take modified image data from Image and copy to ImageData as PNG
	verify(FImageUtils::CompressImage(ImageData, TEXT("PNG"), Image));
}

TOptional<FVector2d> ACameraModel::GetCenterOfBrightness(UTextureRenderTarget2D *RenderTarget)
{
	TOptional<FVector2D> Coordinates; // Equals default if image has no center of brightness

	if (!RenderTarget)
		return Coordinates;

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

			const TShaderMapRef<FCenBrightReduce> CenBrightReduceShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

			const FIntVector GroupCount = FIntVector(GroupCountX, GroupCountY, 1);
			FComputeShaderUtils::AddPass(GraphBuilder, RDG_EVENT_NAME("ComputeCOB"), CenBrightReduceShader, CobParams,
										 GroupCount);

			AddEnqueueCopyPass(GraphBuilder, &Readback, PartialSumsBuffer, sizeof(FVector4f) * NumGroups);

			GraphBuilder.Execute();
			RHICmdList.SubmitCommandsAndFlushGPU(); // Metals refuses to auto-flush unless forced
		});

	Fence.BeginFence();
	Fence.Wait();

	ENQUEUE_RENDER_COMMAND(COB_Readback)
	(
		[&Readback, &Coordinates, NumGroups](FRHICommandListImmediate &RHICmdList)
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
					Coordinates = FVector2D(CenterX, CenterY);
				}

				Readback.Unlock();
			}
		});

	Fence.BeginFence();
	Fence.Wait();

	if (Coordinates.IsSet())
		UE_LOG(LogCielim, Display, TEXT("Center of Brightness: %f, %f"), Coordinates->X, Coordinates->Y);

	return Coordinates;
}

void ACameraModel::ApplyPostProcessShaders(UTextureRenderTarget2D *RenderTarget,
										   FImageCorruptionParams *CorruptionParams)
{
	if (!RenderTarget)
		return;

	FTextureRenderTargetResource *RTResource = RenderTarget->GameThread_GetRenderTargetResource();

	ENQUEUE_RENDER_COMMAND(ApplyPostProcess)
	(
		[RTResource, CorruptionParams](FRHICommandListImmediate &RHICmdList)
		{
			FRDGBuilder GraphBuilder(RHICmdList);

			const FRDGTextureRef RenderTargetBase =
				RegisterExternalTexture(GraphBuilder, RTResource->GetRenderTargetTexture(), TEXT("RenderTargetBase"));

			// Intermediates used for texture ping-pong
			FRDGTextureRef TempTextureIn =
				GraphBuilder.CreateTexture(RenderTargetBase->Desc, TEXT("Temp Input Texture"));
			FRDGTextureRef TempTextureOut =
				GraphBuilder.CreateTexture(RenderTargetBase->Desc, TEXT("Temp Output Texture"));

			AddCopyTexturePass(GraphBuilder, RenderTargetBase, TempTextureIn);

			const FScreenPassTextureViewport Viewport(RenderTargetBase);

			if (CorruptionParams->Sigma != 0.0f)
			{
				// GaussianPSF Horizontal

				FGaussianPSF::FPermutationDomain PermutationDomain;
				PermutationDomain.Set<FGaussianPSF::FHorizontal>(true);

				FGaussianPSF::FParameters *PSFParamsH = GraphBuilder.AllocParameters<FGaussianPSF::FParameters>();
				PSFParamsH->InputTexture = TempTextureIn;
				PSFParamsH->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
				PSFParamsH->TexelSize = FVector2f(1.0f / Viewport.Rect.Width(), 1.0f / Viewport.Rect.Height());
				PSFParamsH->KernelRadius = (CorruptionParams->KernelWidth - 1.0f) / 2.0f;
				PSFParamsH->Sigma = CorruptionParams->Sigma;
				PSFParamsH->RenderTargets[0] = FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

				const TShaderMapRef<FGaussianPSF> GaussianPSFShaderH(GetGlobalShaderMap(GMaxRHIFeatureLevel),
																	 PermutationDomain);

				AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply GaussianPSF H"), GMaxRHIFeatureLevel, Viewport,
					              Viewport, GaussianPSFShaderH, PSFParamsH);

				Swap(TempTextureIn, TempTextureOut);

				// GaussianPSF Vertical

				PermutationDomain.Set<FGaussianPSF::FHorizontal>(false);

				const TShaderMapRef<FGaussianPSF> GaussianPSFShaderV(GetGlobalShaderMap(GMaxRHIFeatureLevel),
																	 PermutationDomain);

				FGaussianPSF::FParameters *PSFParamsV = GraphBuilder.AllocParameters<FGaussianPSF::FParameters>();
				PSFParamsV->InputTexture = TempTextureIn;
				PSFParamsV->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
				PSFParamsV->TexelSize = FVector2f(1.0f / Viewport.Rect.Width(), 1.0f / Viewport.Rect.Height());
				PSFParamsV->KernelRadius = (CorruptionParams->KernelWidth - 1.0f) / 2.0f;
				PSFParamsV->Sigma = CorruptionParams->Sigma;
				PSFParamsV->RenderTargets[0] = FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

				AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply GaussianPSF V"), GMaxRHIFeatureLevel, Viewport,
					              Viewport, GaussianPSFShaderV, PSFParamsV);

				Swap(TempTextureIn, TempTextureOut);
			}

			if (CorruptionParams->NumCosmicRays != 0.0f)
			{
				// Cosmic Rays

				const FRDGBufferRef StartBuffer =
					CreateStructuredBuffer<FVector2f>(GraphBuilder, TEXT("StartPoints"), CorruptionParams->StartPoints);
				const FRDGBufferRef EndBuffer =
					CreateStructuredBuffer<FVector2f>(GraphBuilder, TEXT("EndPoints"), CorruptionParams->EndPoints);
				const FRDGBufferRef WidthBuffer =
					CreateStructuredBuffer<float>(GraphBuilder, TEXT("LineWidths"), CorruptionParams->LineWidths);

				FCosmicRays::FParameters *RayParams = GraphBuilder.AllocParameters<FCosmicRays::FParameters>();
				RayParams->InputTexture = TempTextureIn;
				RayParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
				RayParams->NumRays = CorruptionParams->NumCosmicRays;
				RayParams->StartPoints = GraphBuilder.CreateSRV(StartBuffer, PF_G32R32F);
				RayParams->EndPoints = GraphBuilder.CreateSRV(EndBuffer, PF_G32R32F);
				RayParams->LineWidths = GraphBuilder.CreateSRV(WidthBuffer, PF_R32_FLOAT);
				RayParams->RenderTargets[0] = FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

				const TShaderMapRef<FCosmicRays> CosmicRayShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

				AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Cosmic Rays"), GMaxRHIFeatureLevel, Viewport,
								  Viewport, CosmicRayShader, RayParams);

				Swap(TempTextureIn, TempTextureOut);
			}

			if (CorruptionParams->ReadNoiseSigma != 0.0f)
			{
				FReadNoise::FParameters *RnParams = GraphBuilder.AllocParameters<FReadNoise::FParameters>();
				RnParams->InputTexture = TempTextureIn;
				RnParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
				RnParams->CurrentTime = static_cast<uint32>(FDateTime::UtcNow().ToUnixTimestamp());
				RnParams->ReadNoiseSigma = CorruptionParams->ReadNoiseSigma;
				RnParams->RenderTargets[0] = FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

				const TShaderMapRef<FReadNoise> ReadNoiseShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

				AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Read Noise"), GMaxRHIFeatureLevel, Viewport,
								  Viewport, ReadNoiseShader, RnParams);

				Swap(TempTextureIn, TempTextureOut);
			}

			if (CorruptionParams->SignalGain != 0.0f)
			{
				FSignalGain::FParameters *GainParams = GraphBuilder.AllocParameters<FSignalGain::FParameters>();
				GainParams->InputTexture = TempTextureIn;
				GainParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
				GainParams->SignalGain = CorruptionParams->SignalGain;
				GainParams->RenderTargets[0] = FRenderTargetBinding(TempTextureOut, ERenderTargetLoadAction::ENoAction);

				const TShaderMapRef<FSignalGain> SignalGainShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

				AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Signal Gain"), GMaxRHIFeatureLevel, Viewport,
								  Viewport, SignalGainShader, GainParams);

				Swap(TempTextureIn, TempTextureOut);
			}

			AddCopyTexturePass(GraphBuilder, TempTextureIn, RenderTargetBase);

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
