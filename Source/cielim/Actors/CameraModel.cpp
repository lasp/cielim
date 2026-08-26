//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of ACameraModel.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CameraModel.h"

#include <random>
#include <chrono>

#include "ImageUtils.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "RHIGPUReadback.h"
#include "ScreenPass.h"

#include "cielim/Shaders/CenBrightReduce.h"
#include "cielim/Shaders/CoverageReduce.h"
#include "cielim/Shaders/GammaCorrect.h"
#include "cielim/Utilities/Logging/CielimLoggingMacros.h"

extern ENGINE_API float GAverageFPS;

DECLARE_GPU_STAT_NAMED(CobReductionCalculations, TEXT("CoBReductionCalculations"));
DECLARE_GPU_STAT_NAMED(CoverageReductionCalculations, TEXT("CoverageReductionCalculations"));
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
	this->CameraParams.Transmission1 = 1.0f;
	this->CameraParams.Transmission2 = 1.0f;
	this->CameraParams.Transmission3 = 1.0f;
	this->CameraParams.Wavelength1 = 650.0f;
	this->CameraParams.Wavelength2 = 550.0f;
	this->CameraParams.Wavelength3 = 450.0f;
	this->CameraParams.QuECurveR = FVector3f::One();
	this->CameraParams.QuECurveG = FVector3f::One();
	this->CameraParams.QuECurveB = FVector3f::One();
	this->CameraParams.CorrectionFactor = 1.0f;
	this->CameraParams.FullWellCapacity = 50000.0f;
	this->CameraParams.Gamma = 2.2f;
	this->CameraParams.bIsGrayscale = false;
}

void ACameraModel::SetCameraParameters(const cielimMessage::CielimMessage &CielimMessage)
{
	if (!CielimMessage.has_camera())
		return;

	const auto CameraModel = CielimMessage.camera();

	// Set camera parameters

	const bool bHasRenderParams = CielimMessage.has_renderparameters();
	const bool bHasLensModel = CameraModel.has_lensmodel();
	const bool bHasSensorModel = CameraModel.has_sensormodel();
	const bool bHasAreaOfInterest = CameraModel.has_areaofinterest();
	const bool bHasImageFormat = CameraModel.has_imageformat();

	if (bHasRenderParams)
	{
		const auto RenderParams = CielimMessage.renderparameters();

		if (RenderParams.wavelength1() > 0.0f)
			this->CameraParams.Wavelength1 = RenderParams.wavelength1();

		if (RenderParams.wavelength2() > 0.0f)
			this->CameraParams.Wavelength2 = RenderParams.wavelength2();

		if (RenderParams.wavelength3() > 0.0f)
			this->CameraParams.Wavelength3 = RenderParams.wavelength3();

		if (RenderParams.has_straylightmodel())
		{
			const auto StrayLight = RenderParams.straylightmodel();

			// bEnabled is copied directly (false is a meaningful value). Every other field keeps its
			// FStrayLightParams default unless positively set, matching the > 0.0f guard idiom used
			// for the rest of the camera parameters (so an unset field means "use the default look").
			this->StrayLightParams.bEnabled = StrayLight.enabled();

			if (StrayLight.intensity() > 0.0f)
				this->StrayLightParams.Intensity = StrayLight.intensity();

			if (StrayLight.coresize() > 0.0f)
				this->StrayLightParams.CoreSize = StrayLight.coresize();

			if (StrayLight.ghostsize() > 0.0f)
				this->StrayLightParams.GhostSize = StrayLight.ghostsize();

			if (StrayLight.ghosttransmittance() > 0.0f)
				this->StrayLightParams.GhostTransmittance = StrayLight.ghosttransmittance();

			if (StrayLight.ghost1relativesize() > 0.0f)
				this->StrayLightParams.Ghost1RelativeSize = StrayLight.ghost1relativesize();

			if (StrayLight.ghost2relativesize() > 0.0f)
				this->StrayLightParams.Ghost2RelativeSize = StrayLight.ghost2relativesize();

			if (StrayLight.ghost3relativesize() > 0.0f)
				this->StrayLightParams.Ghost3RelativeSize = StrayLight.ghost3relativesize();

			if (StrayLight.ghost4relativesize() > 0.0f)
				this->StrayLightParams.Ghost4RelativeSize = StrayLight.ghost4relativesize();

			if (StrayLight.ghostbrightnesssizeexponent() > 0.0f)
				this->StrayLightParams.GhostBrightnessSizeExponent = StrayLight.ghostbrightnesssizeexponent();

			if (StrayLight.coronafalloffexponent() > 0.0f)
				this->StrayLightParams.CoronaFalloffExponent = StrayLight.coronafalloffexponent();

			if (StrayLight.coronaintensity() > 0.0f)
				this->StrayLightParams.CoronaIntensity = StrayLight.coronaintensity();

			if (StrayLight.numrays() > 0.0f)
				this->StrayLightParams.NumRays = StrayLight.numrays();

			if (StrayLight.raysharpness() > 0.0f)
				this->StrayLightParams.RaySharpness = StrayLight.raysharpness();

			if (StrayLight.rayweight() > 0.0f)
				this->StrayLightParams.RayWeight = StrayLight.rayweight();

			// Copied directly: 0 is meaningful (stray light only while the sun is in frame).
			this->StrayLightParams.BaffleShieldAngle = StrayLight.baffleshieldangle();
		}
	}

	if (bHasLensModel)
	{
		const auto LensModel = CameraModel.lensmodel();

		if (LensModel.apertureradius() > 0.0f)
			this->CameraParams.ApertureRadius = CameraModel.lensmodel().apertureradius();

		if (LensModel.focallength() > 0.0f)
			this->CameraParams.FocalLength = CameraModel.lensmodel().focallength();

		// This will never allow transmission1 to go to zero so that empty field gives full transmission
		if (LensModel.transmission1() > 0.0f)
			this->CameraParams.Transmission1 = FMath::Min(LensModel.transmission1(), 1.0f);

		// This will never allow transmission2 to go to zero so that empty field gives full transmission
		if (LensModel.transmission2() > 0.0f)
			this->CameraParams.Transmission2 = FMath::Min(LensModel.transmission2(), 1.0f);

		// This will never allow transmission3 to go to zero so that empty field gives full transmission
		if (LensModel.transmission3() > 0.0f)
			this->CameraParams.Transmission3 = FMath::Min(LensModel.transmission3(), 1.0f);
	}

	if (bHasSensorModel)
	{
		const auto SensorModel = CameraModel.sensormodel();

		if (SensorModel.sensorwidth() > 0.0f)
			this->CameraParams.SensorWidth = CameraModel.sensormodel().sensorwidth();

		if (SensorModel.sensorheight() > 0.0f)
			this->CameraParams.SensorHeight = CameraModel.sensormodel().sensorheight();

		if (SensorModel.exposuretime() > 0.0f)
			this->CameraParams.ExposureTime = CameraModel.sensormodel().exposuretime();

		if (SensorModel.fullwellcapacity() > 0.0f)
			this->CameraParams.FullWellCapacity = CameraModel.sensormodel().fullwellcapacity();

		if (SensorModel.gamma() > 0.0f)
			this->CameraParams.Gamma = CameraModel.sensormodel().gamma();

		if (SensorModel.has_qecurve())
		{
			const auto QuECurve = SensorModel.qecurve();

			if (QuECurve.integrationweightfactor() > 0.0f)
				this->CameraParams.CorrectionFactor = QuECurve.integrationweightfactor();

			CameraParams.QuECurveR.Set(QuECurve.redvalue1(), QuECurve.redvalue2(), QuECurve.redvalue3());
			CameraParams.QuECurveG.Set(QuECurve.greenvalue1(), QuECurve.greenvalue2(), QuECurve.greenvalue3());
			CameraParams.QuECurveB.Set(QuECurve.bluevalue1(), QuECurve.bluevalue2(), QuECurve.bluevalue3());
		}

		this->CameraParams.bIsGrayscale = SensorModel.isgrayscale();
	}

	if (bHasImageFormat)
	{
		this->ImageFormat = CameraModel.imageformat().format();
	}

	// Set diagnostic parameters
	if (bHasAreaOfInterest)
	{
		const auto AreaOfInterest = CameraModel.areaofinterest();

		if (AreaOfInterest.centerx() > 0.0f && AreaOfInterest.centery() > 0.0f)
		{
			this->DiagnosticParams.CenterPixelX = AreaOfInterest.centerx();
			this->DiagnosticParams.CenterPixelY = AreaOfInterest.centery();
		}

		if (AreaOfInterest.width() > 0.0f && AreaOfInterest.height() > 0.0f)
		{
			this->DiagnosticParams.AreaWidth = AreaOfInterest.width();
			this->DiagnosticParams.AreaHeight = AreaOfInterest.height();
		}

		if (AreaOfInterest.threshold() > 0.0f)
			this->DiagnosticParams.Threshold = AreaOfInterest.threshold();
	}

	// Set image corruption parameters

	this->CorruptionParams.KernelWidth = 7;

	if (bHasRenderParams)
	{
		auto CosmicRays = GetCosmicRays(CielimMessage.renderparameters().cosmicraystddeviation());

		this->CorruptionParams.NumCosmicRays = CosmicRays.Get<0>();
		this->CorruptionParams.StartPoints = CosmicRays.Get<1>();
		this->CorruptionParams.EndPoints = CosmicRays.Get<2>();
		this->CorruptionParams.LineWidths = CosmicRays.Get<3>();
	}

	if (bHasLensModel)
	{
		const auto LensModel = CameraModel.lensmodel();

		this->CorruptionParams.K1 = LensModel.distortionk1();
		this->CorruptionParams.K2 = LensModel.distortionk2();
		this->CorruptionParams.K3 = LensModel.distortionk3();
		this->CorruptionParams.P1 = LensModel.distortionp1();
		this->CorruptionParams.P2 = LensModel.distortionp2();

		this->CorruptionParams.Sigma = LensModel.pointspreadfunction();
	}

	if (bHasSensorModel)
	{
		const auto SensorModel = CameraModel.sensormodel();

		this->CorruptionParams.bEnableShotNoise = CameraModel.sensormodel().shotnoise();

		if (SensorModel.darkcurrent() > 0.0f)
			this->CorruptionParams.DarkCurrent = SensorModel.darkcurrent();

		this->CorruptionParams.DarkCurrentPattern = SensorModel.darkcurrentpattern();

		if (SensorModel.darkcurrentstddeviation() > 0.0f)
			this->CorruptionParams.DarkCurrentStdDeviation = SensorModel.darkcurrentstddeviation();

		if (SensorModel.readnoise() > 0.0f)
			this->CorruptionParams.ReadNoiseSigma = SensorModel.readnoise();

		this->CorruptionParams.PixelDefectPattern = SensorModel.pixeldefectpattern();

		if (SensorModel.stuckpixelrate() > 0.0f)
			this->CorruptionParams.StuckPixelRate = SensorModel.stuckpixelrate();

		if (SensorModel.deadpixelrate() > 0.0f)
			this->CorruptionParams.DeadPixelRate = SensorModel.deadpixelrate();

		if (SensorModel.systemgain() > 0.0f)
			this->CorruptionParams.SignalGain = SensorModel.systemgain();
	}
}

// Called when spawned
void ACameraModel::BeginPlay()
{
	Super::BeginPlay();

	// Do a flush to the render target to ensure actual first capture has correct data
	this->SceneCaptureComponent2D->CaptureScene();

	ENQUEUE_RENDER_COMMAND(FlushGPU)
	(
		[](FRHICommandListImmediate &RHICmdList)
		{
			RHICmdList.SubmitCommandsAndFlushGPU(); // Metals refuses to auto-flush unless forced
		});

	FlushRenderingCommands(); // Wait for GPU flush to finish
}


// Called every frame
void ACameraModel::Tick(float DeltaTime) { Super::Tick(DeltaTime); }

void ACameraModel::SaveImageToDisk(const FString &FilePath, const FString &Filename)
{
	UKismetRenderingLibrary::ExportRenderTarget(this, this->SceneCaptureComponent2D->TextureTarget, FilePath, Filename);
}

void ACameraModel::GetImageData(TArray64<uint8> &ImageData)
{
	FImage Image;

	this->CameraParams.bIsDiagnosticRun = false;
	
	const auto start = std::chrono::high_resolution_clock::now();

	this->SceneCaptureComponent2D->CaptureScene();
	this->ApplyGammaCorrection();

	// Copy the final render from the render target to Image
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent2D->TextureTarget, Image));
	
	const auto end1 = std::chrono::high_resolution_clock::now();

	// Take modified image data from Image and convert/pack and copy to ImageData
	switch (this->ImageFormat)
	{
	case cielimMessage::ImageFormat_Format_PNG:
		verify(FImageUtils::CompressImage(ImageData, TEXT("PNG"), Image));
		break;

	case cielimMessage::ImageFormat_Format_RAW_8:
		{
			TArray64<uint8> TempData;
			ExtractImage(Image, this->CameraParams.bIsGrayscale, TempData);
			ExportRaw8(TempData, ImageData);
			break;
		}

	case cielimMessage::ImageFormat_Format_RAW_12:
		{
			TArray64<uint8> TempData;
			ExtractImage(Image, this->CameraParams.bIsGrayscale, TempData);
			ExportRaw12(TempData, ImageData);
			break;
		}

	case cielimMessage::ImageFormat_Format_RAW_12_PACKED:
		{
			TArray64<uint8> TempData;
			ExtractImage(Image, this->CameraParams.bIsGrayscale, TempData);
			ExportRaw12Packed(TempData, ImageData);
			break;
		}

	case cielimMessage::ImageFormat_Format_RAW_16:
		{
			TArray64<uint8> TempData;
			ExtractImage(Image, this->CameraParams.bIsGrayscale, TempData);
			ImageData = MoveTemp(TempData);
			break;
		}

	default:
		break;
	}
	
	const auto end2 = std::chrono::high_resolution_clock::now();
	
	const auto diff1 = static_cast<float>(std::chrono::duration_cast<std::chrono::milliseconds>(end1 - start).count());
	const auto diff2 = static_cast<float>(std::chrono::duration_cast<std::chrono::milliseconds>(end2 - start).count());
	
	float CurrentFPS = GAverageFPS;
	
	UE_LOG(LogCielim, Warning, TEXT("Frame time (before png conversion): %f"), diff1);
	UE_LOG(LogCielim, Warning, TEXT("Frame time (with png conversion): %f"), diff2);
}

void ACameraModel::ExtractImage(const FImage &Image, const bool bIsGrayscale, TArray64<uint8> &OutData)
{
	const FFloat16 *SourceFloat16 = reinterpret_cast<const FFloat16 *>(Image.RawData.GetData());

	const int64 NumPixels = Image.GetNumPixels();

	if (bIsGrayscale)
	{
		// Output image will hold single 16-bit channel per pixel
		OutData.SetNumUninitialized(NumPixels * sizeof(uint16));

		uint16 *Destination = reinterpret_cast<uint16 *>(OutData.GetData());

		for (int64 i = 0; i < NumPixels; i++)
		{
			// We extract here only the R color channel

			const float RFloatValue = FMath::Clamp(SourceFloat16[i * 4].GetFloat(), 0.f, 1.f);

			const uint16 RIntValue = static_cast<uint16>(RFloatValue * 65535.0f);

			Destination[i] = RIntValue;
		}
	}
	else
	{
		// Output image will hold 16-bit RGB channels per pixel
		OutData.SetNumUninitialized(NumPixels * sizeof(uint16) * 3);

		uint16 *Destination = reinterpret_cast<uint16 *>(OutData.GetData());

		for (int64 i = 0; i < NumPixels; i++)
		{
			// We extract here the RGB color channels, no alpha channel

			const float RFloatValue = FMath::Clamp(SourceFloat16[i * 4 + 0].GetFloat(), 0.f, 1.f);
			const float GFloatValue = FMath::Clamp(SourceFloat16[i * 4 + 1].GetFloat(), 0.f, 1.f);
			const float BFloatValue = FMath::Clamp(SourceFloat16[i * 4 + 2].GetFloat(), 0.f, 1.f);

			const uint16 RIntValue = static_cast<uint16>(RFloatValue * 65535.0f);
			const uint16 GIntValue = static_cast<uint16>(GFloatValue * 65535.0f);
			const uint16 BIntValue = static_cast<uint16>(BFloatValue * 65535.0f);

			Destination[i * 3] = RIntValue;
			Destination[i * 3 + 1] = GIntValue;
			Destination[i * 3 + 2] = BIntValue;
		}
	}
}

void ACameraModel::ExportRaw8(const TArray64<uint8> &InData, TArray64<uint8> &OutData)
{
	// Number of uint16 values (1 per color channel)
	const uint64 NumSamples = InData.Num() / sizeof(uint16);

	// We only need 1 byte per sample
	OutData.SetNumUninitialized(NumSamples);

	const uint8 *ImageDataSource = InData.GetData();
	uint8 *ImageDataDestination = OutData.GetData();

	for (uint64 i = 0; i < NumSamples; i++)
	{
		// Just copy the most significant byte to the new array
		ImageDataDestination[i] = ImageDataSource[i * 2 + 1];
	}
}

void ACameraModel::ExportRaw12(const TArray64<uint8> &InData, TArray64<uint8> &OutData)
{
	// Number of uint16 values (1 per color channel)
	const uint64 NumSamples = InData.Num() / sizeof(uint16);

	// Set number of uint8 values in byte data array
	OutData.SetNumUninitialized(NumSamples * 2);

	const uint16 *ImageDataSource = reinterpret_cast<const uint16 *>(InData.GetData());
	uint16 *ImageDataDestination = reinterpret_cast<uint16 *>(OutData.GetData());

	for (uint64 i = 0; i < NumSamples; i++)
	{
		// Zero out the 4 least significant bits
		ImageDataDestination[i] = (ImageDataSource[i] >> 4) << 4;
	}
}

void ACameraModel::ExportRaw12Packed(const TArray64<uint8> &InData, TArray64<uint8> &OutData)
{
	// Number of uint16 values (1 per color channel)
	const uint64 NumSamples = InData.Num() / sizeof(uint16);
	const uint64 NumSamplePairs = (NumSamples + 1) / 2; // Round pairs up in the case of odd number of samples

	// 2 color channels are packed into 3 bytes
	OutData.SetNumUninitialized(NumSamplePairs * 3);

	const uint16 *ImageDataSource = reinterpret_cast<const uint16 *>(InData.GetData());
	uint8 *ImageDataDestination = OutData.GetData();

	for (uint64 i = 0; i < NumSamplePairs; i++)
	{
		// Scale each 16-bit source sample down to 12-bit
		const uint16 SampleA = ImageDataSource[i * 2 + 0] >> 4;
		const uint16 SampleB = (i * 2 + 1 < NumSamples) ? (ImageDataSource[i * 2 + 1] >> 4) : 0;

		// Byte 0: Least significant 8 bits of A (7..0)
		ImageDataDestination[i * 3 + 0] = SampleA & 0xFF;

		// Byte 1: Remaining 4 bits of A (11..8) in rightmost bits, least significant 4 bits of B (3..0) in leftmost
		ImageDataDestination[i * 3 + 1] = ((SampleB & 0x00F) << 4) | ((SampleA & 0xF00) >> 8);

		// Byte 2: Most significant 8 bits of B (11..4)
		ImageDataDestination[i * 3 + 2] = (SampleB >> 4) & 0xFF;
	}
}

void ACameraModel::GetDiagnosticData(imageDiagnostics::DiagnosticData &Diagnostics)
{
	this->CameraParams.bIsDiagnosticRun = true;

	this->SceneCaptureComponent2D->CaptureScene();

	const FVector2D CobCoordinates = this->GetCenterOfBrightness();
	const float CoveragePercentage = this->GetCoveragePercent();

	Diagnostics.set_cob_x(CobCoordinates.X);
	Diagnostics.set_cob_y(CobCoordinates.Y);
	Diagnostics.set_coverage(CoveragePercentage);

	const float CoverageArea = this->DiagnosticParams.AreaWidth * this->DiagnosticParams.AreaHeight;
	Diagnostics.set_totalbrightpixels(static_cast<uint32>(CoveragePercentage * CoverageArea));
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

FVector2D ACameraModel::GetCenterOfBrightness() const
{
	FVector2D CobCoords;

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
				else
				{
					CobCoords = FVector2D(-1.0f, -1.0f);
				}

				Readback.Unlock();
			}
		});

	Fence.BeginFence();
	Fence.Wait();

	UE_LOG(LogCielim, Display, TEXT("Center of Brightness: %f, %f"), CobCoords.X, CobCoords.Y);

	return CobCoords;
}

float ACameraModel::GetCoveragePercent() const
{
	float CoveragePercent = 0.0f;

	UTextureRenderTarget2D *RenderTarget = this->SceneCaptureComponent2D->TextureTarget;

	if (!RenderTarget)
		return CoveragePercent;

	FTextureRenderTargetResource *RTResource = RenderTarget->GameThread_GetRenderTargetResource();
	FRHIGPUBufferReadback ReadbackTotal(TEXT("Coverage Reduction Calculations Readback for Total Sum"));
	FRHIGPUBufferReadback ReadbackCovered(TEXT("Coverage Reduction Calculations Readback for Covered Sum"));

	const uint32 Width = RenderTarget->SizeX;
	const uint32 Height = RenderTarget->SizeY;

	const uint32 GroupCountX = FMath::DivideAndRoundUp(Width, 16u);
	const uint32 GroupCountY = FMath::DivideAndRoundUp(Height, 16u);
	const uint32 NumGroups = GroupCountX * GroupCountY;

	const uint32 CenterPixelX =
		this->DiagnosticParams.CenterPixelX > 0.0f ? this->DiagnosticParams.CenterPixelX : Width / 2;
	const uint32 CenterPixelY =
		this->DiagnosticParams.CenterPixelY > 0.0f ? this->DiagnosticParams.CenterPixelY : Height / 2;
	const float AreaWidth = this->DiagnosticParams.AreaWidth > 0.0f ? this->DiagnosticParams.AreaWidth : Width;
	const float AreaHeight = this->DiagnosticParams.AreaHeight > 0.0f ? this->DiagnosticParams.AreaHeight : Height;
	const float Threshold = this->DiagnosticParams.Threshold >= 0.0f ? this->DiagnosticParams.Threshold : 0.0f;

	FRenderCommandFence Fence;

	ENQUEUE_RENDER_COMMAND(Coverage_Calculations)
	(
		[RTResource, &ReadbackTotal, &ReadbackCovered, Width, Height, GroupCountX, GroupCountY, NumGroups, CenterPixelX,
		 CenterPixelY, AreaWidth, AreaHeight, Threshold](FRHICommandListImmediate &RHICmdList)
		{
			FRDGBuilder GraphBuilder(RHICmdList);

			const FRDGTextureRef RenderTargetBase =
				RegisterExternalTexture(GraphBuilder, RTResource->GetRenderTargetTexture(), TEXT("RenderTarget"));

			const FRDGBufferDesc PartialTotalSumsDesc = FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), NumGroups);
			const FRDGBufferRef PartialTotalSumsBuffer =
				GraphBuilder.CreateBuffer(PartialTotalSumsDesc, TEXT("PartialTotalSumsBuffer"));

			const FRDGBufferDesc PartialSumsDesc = FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), NumGroups);
			const FRDGBufferRef PartialSumsBuffer =
				GraphBuilder.CreateBuffer(PartialSumsDesc, TEXT("PartialSumsBuffer"));

			FCoverageReduce::FParameters *CvgParams = GraphBuilder.AllocParameters<FCoverageReduce::FParameters>();
			CvgParams->InputTexture = RenderTargetBase;
			CvgParams->TextureSize = FIntPoint(Width, Height);
			CvgParams->CenterPixelX = CenterPixelX;
			CvgParams->CenterPixelY = CenterPixelY;
			CvgParams->ApothemX = AreaWidth / 2.0f;
			CvgParams->ApothemY = AreaHeight / 2.0f;
			CvgParams->Threshold = Threshold;
			CvgParams->PartialTotalSumBuffer = GraphBuilder.CreateUAV(PartialTotalSumsBuffer, PF_A32B32G32R32F);
			CvgParams->PartialSumBuffer = GraphBuilder.CreateUAV(PartialSumsBuffer, PF_A32B32G32R32F);

			{
				RDG_GPU_STAT_SCOPE(GraphBuilder, CoverageReductionCalculations);
				RDG_EVENT_SCOPE(GraphBuilder, "CoverageReductionCalculations");

				const TShaderMapRef<FCoverageReduce> CoverageReduceShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

				const FIntVector GroupCount = FIntVector(GroupCountX, GroupCountY, 1);
				FComputeShaderUtils::AddPass(GraphBuilder, RDG_EVENT_NAME("ComputeCoverage"), CoverageReduceShader,
											 CvgParams, GroupCount);

				AddEnqueueCopyPass(GraphBuilder, &ReadbackTotal, PartialTotalSumsBuffer, sizeof(uint32) * NumGroups);
				AddEnqueueCopyPass(GraphBuilder, &ReadbackCovered, PartialSumsBuffer, sizeof(uint32) * NumGroups);
			}

			GraphBuilder.Execute();
			RHICmdList.SubmitCommandsAndFlushGPU(); // Metals refuses to auto-flush unless forced
		});

	Fence.BeginFence();
	Fence.Wait();

	ENQUEUE_RENDER_COMMAND(COB_Readback)
	(
		[&ReadbackTotal, &ReadbackCovered, &CoveragePercent, NumGroups](FRHICommandListImmediate &RHICmdList)
		{
			const double StartTime = FPlatformTime::Seconds();

			// Compute coverage as percentage of total pixels above threshold

			float TotalPixels = 0;
			float CoveredPixels = 0;

			while (!ReadbackTotal.IsReady())
			{
				FPlatformProcess::Sleep(0.001f);

				if (FPlatformTime::Seconds() - StartTime > 5.0f)
				{
					UE_LOG(LogCielim, Warning, TEXT("Readback polling has timed out; skipping readback..."));
					break;
				}
			}

			if (ReadbackTotal.IsReady())
			{
				const uint32 *RawData = static_cast<uint32 *>(ReadbackTotal.Lock(sizeof(uint32) * NumGroups));

				for (uint32 i = 0; i < NumGroups; i++)
				{
					TotalPixels += RawData[i];
				}

				ReadbackTotal.Unlock();
			}

			while (!ReadbackCovered.IsReady())
			{
				FPlatformProcess::Sleep(0.001f);

				if (FPlatformTime::Seconds() - StartTime > 5.0f)
				{
					UE_LOG(LogCielim, Warning, TEXT("Readback polling has timed out; skipping readback..."));
					break;
				}
			}

			if (ReadbackCovered.IsReady())
			{
				const uint32 *RawData = static_cast<uint32 *>(ReadbackCovered.Lock(sizeof(uint32) * NumGroups));

				for (uint32 i = 0; i < NumGroups; i++)
				{
					CoveredPixels += RawData[i];
				}

				ReadbackCovered.Unlock();
			}

			CoveragePercent = CoveredPixels / FMath::Max(TotalPixels, 1e-6);
		});

	Fence.BeginFence();
	Fence.Wait();

	UE_LOG(LogCielim, Display, TEXT("Coverage Percentage: %f %%"), CoveragePercent * 100.0f);

	return CoveragePercent;
}

bool ACameraModel::IsCelestialBodyResolvable(const ACelestialBody &CelestialBody, const float PhaseAngle) const
{
	FVector Origin;
	FVector Extent;

	// Get bounds of the celestial body

	CelestialBody.GetActorBounds(false, Origin, Extent);

	if (Extent.IsZero())
		return false;

	// This is super hacky, but we have to set this up here to get view/projection matrices

	FSceneViewInitOptions ViewInitOptions;

	ViewInitOptions.ViewFamily = nullptr; // assigned later
	ViewInitOptions.ViewOrigin = this->SceneCaptureComponent2D->GetComponentLocation();
	ViewInitOptions.ViewRotationMatrix = FInverseRotationMatrix(this->SceneCaptureComponent2D->GetComponentRotation()) *
		FMatrix(FPlane(0, 0, 1, 0), FPlane(1, 0, 0, 0), FPlane(0, 1, 0, 0), FPlane(0, 0, 0, 1));

	const int32 SizeX = this->SceneCaptureComponent2D->TextureTarget->SizeX;
	const int32 SizeY = this->SceneCaptureComponent2D->TextureTarget->SizeY;

	ViewInitOptions.SetViewRectangle(FIntRect(0, 0, SizeX, SizeY));

	ViewInitOptions.ProjectionMatrix = this->SceneCaptureComponent2D->CustomProjectionMatrix;

	const FSceneViewFamilyContext ViewFamily(FSceneViewFamily::ConstructionValues(
		nullptr, SceneCaptureComponent2D->GetScene(), SceneCaptureComponent2D->ShowFlags));

	ViewInitOptions.ViewFamily = &ViewFamily;

	const FSceneView View(ViewInitOptions);

	const auto ViewportRect = View.UnconstrainedViewRect;

	// This is the percentage of the screen size taken up by the celestial body
	const float ScreenSize = ComputeBoundsScreenSize(Origin, Extent.Size(), View);
	const float PixelSize = ScreenSize * FMath::Max(ViewportRect.Height(), ViewportRect.Width());

	/* Threshold for the mesh → distant transition: clamp(3 / (1 + cos α), 4, 15). Aims for a
	 * ~1.5-pixel mesh crescent at transition for α in [110°, 143°], and caps at 15 past 143°
	 * so the rasterized bounding box stays bounded once the crescent is sub-pixel anyway. */
	const float CrescentFactor = FMath::Max(1.0f + FMath::Cos(PhaseAngle), 0.1f);
	const float Threshold = FMath::Clamp(3.0f / CrescentFactor, 4.0f, 15.0f);

	return PixelSize <= Threshold;
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
