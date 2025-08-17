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
#include "cielim/Shaders/GammaCorrect.h"
#include "cielim/Utilities/Logging/CielimLoggingMacros.h"

DECLARE_GPU_STAT_NAMED(CobReductionCalculations, TEXT("CoBReductionCalculations"));
DECLARE_GPU_STAT_NAMED(GammaCorrection, TEXT("GammaCorrection"));

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

	// Choose default camera parameters

	this->CameraParams.ApertureRadius = 0.005f;
	this->CameraParams.FocalLength = 0.16f;
	this->CameraParams.SensorWidth = 0.036f;
	this->CameraParams.SensorHeight = 0.024f;
	this->CameraParams.ExposureTime = 1e-3f;
	this->CameraParams.QuECurveR = FVector3f::One();
	this->CameraParams.QuECurveG = FVector3f::One();
	this->CameraParams.QuECurveB = FVector3f::One();
	this->CameraParams.CorrectionFactor = 1.0f;
	this->CameraParams.FullWellCapacity = 50000.0f;
	this->CameraParams.Gamma = 2.2f;
}

void ACameraModel::SetCameraParameters(const cielimMessage::CameraModel &CameraModel)
{
	// Set camera parameters

	if (CameraModel.apertureradius() > 0.0f)
		this->CameraParams.ApertureRadius = CameraModel.apertureradius();

	if (CameraModel.focallength() > 0.0f)
		this->CameraParams.FocalLength = CameraModel.focallength();

	if (CameraModel.sensorwidth() > 0.0f)
		this->CameraParams.SensorWidth = CameraModel.sensorwidth();

	if (CameraModel.sensorheight() > 0.0f)
		this->CameraParams.SensorHeight = CameraModel.sensorheight();

	if (CameraModel.exposuretime() > 0.0f)
		this->CameraParams.ExposureTime = CameraModel.exposuretime();

	if (CameraModel.integrationweightfactor() > 0.0f)
		this->CameraParams.CorrectionFactor = CameraModel.integrationweightfactor();

	if (CameraModel.fullwellcapacity() > 0.0f)
		this->CameraParams.FullWellCapacity = CameraModel.fullwellcapacity();

	if (CameraModel.gamma() > 0.0f)
		this->CameraParams.Gamma = CameraModel.gamma();

	if (CameraModel.has_qecurve())
	{
		const auto QuECurve = CameraModel.qecurve();
		CameraParams.QuECurveR.Set(QuECurve.redvalue650nm(), QuECurve.redvalue550nm(), QuECurve.redvalue450nm());
		CameraParams.QuECurveG.Set(QuECurve.greenvalue650nm(), QuECurve.greenvalue550nm(), QuECurve.greenvalue450nm());
		CameraParams.QuECurveB.Set(QuECurve.bluevalue650nm(), QuECurve.bluevalue550nm(), QuECurve.bluevalue450nm());
	}

	// Set image corruption parameters

	auto CosmicRays = GetCosmicRays(CameraModel.renderparameters().cosmicraystddeviation());

	this->CorruptionParams.KernelWidth = 7;
	this->CorruptionParams.Sigma = CameraModel.pointspreadfunction();
	this->CorruptionParams.NumCosmicRays = CosmicRays.Get<0>();
	this->CorruptionParams.StartPoints = CosmicRays.Get<1>();
	this->CorruptionParams.EndPoints = CosmicRays.Get<2>();
	this->CorruptionParams.LineWidths = CosmicRays.Get<3>();
	this->CorruptionParams.ReadNoiseSigma = CameraModel.readnoise();
	this->CorruptionParams.SignalGain = CameraModel.systemgain();
}

void ACameraModel::BeginPlay() { Super::BeginPlay(); }

// Called every frame
void ACameraModel::Tick(float DeltaTime) { Super::Tick(DeltaTime); }

void ACameraModel::SaveImageToDisk(const FString &FilePath, const FString &Filename)
{
	UKismetRenderingLibrary::ExportRenderTarget(this, this->SceneCaptureComponent2D->TextureTarget, FilePath, Filename);
}

void ACameraModel::GetImageData(TArray64<uint8> &ImageData, TOptional<FVector2D> &CobCoordinates)
{
	// Get initial diagnostic data
	this->GetImageData(CobCoordinates);

	// Get final render
	this->GetImageData(ImageData);
}

void ACameraModel::GetImageData(TArray64<uint8> &ImageData)
{
	FImage Image;

	this->CameraParams.bIsDiagnosticRun = false;

	this->SceneCaptureComponent2D->CaptureScene();
	this->ApplyGammaCorrection();

	// Copy the final render from the render target to Image
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent2D->TextureTarget, Image));

	// Take modified image data from Image and convert to PNG and copy to ImageData
	verify(FImageUtils::CompressImage(ImageData, TEXT("PNG"), Image));
}

void ACameraModel::GetImageData(TOptional<FVector2D> &CobCoordinates)
{
	this->CameraParams.bIsDiagnosticRun = true;

	this->SceneCaptureComponent2D->CaptureScene();

	CobCoordinates = this->GetCenterOfBrightness();
}

void ACameraModel::ApplyGammaCorrection() const
{
	UTextureRenderTarget2D *RenderTarget = this->SceneCaptureComponent2D->TextureTarget;

	if (!RenderTarget)
		return;

	FTextureRenderTargetResource *RTResource = RenderTarget->GameThread_GetRenderTargetResource();

	float InvGamma = 1.0f / FMath::Max(this->CameraParams.Gamma, 1e-2f);

	ENQUEUE_RENDER_COMMAND(GammaCorrection)
	(
		[RTResource, InvGamma](FRHICommandListImmediate &RHICmdList)
		{
			FRDGBuilder GraphBuilder(RHICmdList);

			const FRDGTextureRef RenderTargetBase =
				RegisterExternalTexture(GraphBuilder, RTResource->GetRenderTargetTexture(), TEXT("RenderTarget"));

			// Temp input texture
			const FRDGTextureRef TextureIn =
				GraphBuilder.CreateTexture(RenderTargetBase->Desc, TEXT("Temp Input Texture"));

			// Init input texture as current scene color
			AddCopyTexturePass(GraphBuilder, RenderTargetBase, TextureIn);

			const FScreenPassTextureViewport Viewport(TextureIn);

			FGammaCorrect::FParameters *GammaParams = GraphBuilder.AllocParameters<FGammaCorrect::FParameters>();
			GammaParams->InputTexture = TextureIn;
			GammaParams->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
			GammaParams->InvGamma = InvGamma;
			GammaParams->RenderTargets[0] = FRenderTargetBinding(RenderTargetBase, ERenderTargetLoadAction::EClear);

			{
				RDG_GPU_STAT_SCOPE(GraphBuilder, GammaCorrection);
				RDG_EVENT_SCOPE(GraphBuilder, "GammaCorrection");

				const TShaderMapRef<FGammaCorrect> GammaCorrectShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

				AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("Apply Gamma Correction"), GMaxRHIFeatureLevel, Viewport,
								  Viewport, GammaCorrectShader, GammaParams);
			}

			GraphBuilder.Execute();
		});
}

TOptional<FVector2D> ACameraModel::GetCenterOfBrightness() const
{
	TOptional<FVector2D> CobCoords;

	UTextureRenderTarget2D *RenderTarget = this->SceneCaptureComponent2D->TextureTarget;

	if (!RenderTarget)
		return CobCoords;

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
				RDG_GPU_STAT_SCOPE(GraphBuilder, CobReductionCalculations);
				RDG_EVENT_SCOPE(GraphBuilder, "CoBReductionCalculations");

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
		[&Readback, &CobCoords, NumGroups](FRHICommandListImmediate &RHICmdList)
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
					CobCoords = FVector2D(CenterX, CenterY);
				}

				Readback.Unlock();
			}
		});

	Fence.BeginFence();
	Fence.Wait();

	if (CobCoords.IsSet())
		UE_LOG(LogCielim, Display, TEXT("Center of Brightness: %f, %f"), CobCoords->X, CobCoords->Y);

	return CobCoords;
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
