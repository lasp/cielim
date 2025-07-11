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
// clang-format off
#include "OpenCV/PreOpenCVHeaders.h"
#include "opencv2/imgproc.hpp"
#include "OpenCV/PostOpenCVHeaders.h"
// clang-format on
#include "ScreenPass.h"

#include "../Shaders/GaussianPSF.h"
#include "RenderingFunctionsLibrary.h"
#include "cielim/Shaders/CosmicRays.h"

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

cv::Mat ACameraModel::FImageToOpenCVMat(const FImage &Image) const
{
	// Access color data of Image and create 4 channel matrix
	const TArrayView64<const FColor> &PixelData = Image.AsBGRA8();
	cv::Mat OpenCVMat(Image.GetHeight(), Image.GetWidth(), CV_8UC4, (void *)PixelData.GetData());
	return OpenCVMat;
}

void ACameraModel::GetCorruptedImage(TArray64<uint8> &ImageData, const double PointSpread, const double ReadNoise,
									 const double SystemGain, const double CosmicRaysStdDev) const
{
	FImage Image;

	auto CosmicRays = GetCosmicRays(CosmicRaysStdDev);

	uint32 NumCosmicRays = CosmicRays.Get<0>();
	TResourceArray<FVector2f> StartPoints = CosmicRays.Get<1>();
	TResourceArray<FVector2f> EndPoints = CosmicRays.Get<2>();
	TResourceArray<float> LineWidths = CosmicRays.Get<3>();

	FImageCorruptionParams CorruptionParams = {7, PointSpread, NumCosmicRays, StartPoints, EndPoints, LineWidths};

	this->SceneCaptureComponent2D->CaptureScene();
	this->ApplyPostProcessShaders(this->SceneCaptureComponent2D->TextureTarget, &CorruptionParams);
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent2D->TextureTarget, Image));

	cv::Mat CvImage = FImageToOpenCVMat(Image);

	// Apply corruptions to image data matrix
	URenderingFunctionsLibrary::ApplyReadNoise(CvImage, ReadNoise, 1.0f);
	URenderingFunctionsLibrary::ApplySignalGain(CvImage, 1.0f, SystemGain);
	// URenderingFunctionsLibrary::ApplyQE(PNGImageDataSerialized, 5.0f, 5.0f, 5.0f);

	FImage CorruptImage(Image);
	FMemory::Memcpy(CorruptImage.RawData.GetData(), CvImage.data, CorruptImage.RawData.Num());

	// Take modified image data from Image and copy to ImageData as PNG
	verify(FImageUtils::CompressImage(ImageData, TEXT("PNG"), CorruptImage));
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

			AddCopyTexturePass(GraphBuilder, TempTextureIn, RenderTargetBase);

			GraphBuilder.Execute();
		});
}

TOptional<FVector2d> ACameraModel::GetCenterOfBrightness(double Threshold) const
{
	uint32_t WeightSum = 0;
	TOptional<FVector2D> Coordinates; // Default the case where the image has no brightness

	cv::Mat GrayImage;
	FImage Image;

	this->SceneCaptureComponent2D->CaptureScene();
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent2D->TextureTarget, Image));

	cv::cvtColor(FImageToOpenCVMat(Image), GrayImage, cv::COLOR_BGR2GRAY);
	cv::threshold(GrayImage, GrayImage, Threshold, 255, cv::THRESH_BINARY);

	// Compute the center of brightness
	if (const cv::Moments Moments = cv::moments(GrayImage, true); Moments.m00 != 0)
	{
		Coordinates.Emplace(Moments.m10 / Moments.m00, Moments.m01 / Moments.m00);
	}

	return Coordinates;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCOBTest_Center, "CaptureManager.CenterOfBrightnessTest.Center",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)

bool FCOBTest_Center::RunTest(const FString &Parameters)
{
	// Create blank image with white square in center

	// Create a 500x500 black single-channel image
	cv::Mat Image = cv::Mat::zeros(500, 500, CV_8UC1);

	// Define the size of the white square
	int SquareSize = 10;

	// Calculate starting pixel values
	int StartX = 250 - SquareSize / 2;
	int StartY = 250 - SquareSize / 2;

	// Draw the white square
	cv::rectangle(Image, cv::Point(StartX, StartY), cv::Point(StartX + SquareSize, StartY + SquareSize),
				  cv::Scalar(255), cv::FILLED);

	FVector2D Coordinates;

	// Compute the center of brightness
	cv::Moments Moments = cv::moments(Image, true);
	if (Moments.m00 != 0)
	{
		Coordinates = FVector2D(Moments.m10 / Moments.m00, Moments.m01 / Moments.m00);
	}

	// Expected center should be directly in the middle of the image
	return Coordinates.Equals(FVector2D(250, 250), 1);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCOBTest_TopRight, "CaptureManager.CenterOfBrightnessTest.TopRight",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)

bool FCOBTest_TopRight::RunTest(const FString &Parameters)
{
	// Create blank image with white square in top-right quadrant

	// Create a 500x500 black single-channel image
	cv::Mat Image = cv::Mat::zeros(500, 500, CV_8UC1);

	// Define the size of the white square
	int SquareSize = 10;

	// Calculate starting pixel values
	int StartX = 375 - SquareSize / 2;
	int StartY = 375 - SquareSize / 2;

	// Draw the white square
	cv::rectangle(Image, cv::Point(StartX, StartY), cv::Point(StartX + SquareSize, StartY + SquareSize),
				  cv::Scalar(255), cv::FILLED);

	FVector2D Coordinates;

	// Compute the center of brightness
	cv::Moments Moments = cv::moments(Image, true);
	if (Moments.m00 != 0)
	{
		Coordinates = FVector2D(Moments.m10 / Moments.m00, Moments.m01 / Moments.m00);
	}

	// Expected center should be center of top right quadrant
	return Coordinates.Equals(FVector2D(375, 375), 1);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCOBTest_CenterRight, "CaptureManager.CenterOfBrightnessTest.CenterRight",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)

bool FCOBTest_CenterRight::RunTest(const FString &Parameters)
{
	// Create blank image with right half filled in

	// Create a 500x500 black single-channel image
	cv::Mat Image = cv::Mat::zeros(500, 500, CV_8UC1);

	// Draw the white square
	cv::rectangle(Image, cv::Point(250, 0), cv::Point(500, 500), cv::Scalar(255), cv::FILLED);

	FVector2D Coordinates;

	// Compute the center of brightness
	cv::Moments Moments = cv::moments(Image, true);
	if (Moments.m00 != 0)
	{
		Coordinates = FVector2D(Moments.m10 / Moments.m00, Moments.m01 / Moments.m00);
	}

	// Expected center should be in the middle of the right half of the image
	return Coordinates.Equals(FVector2D(375, 250), 1);
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
