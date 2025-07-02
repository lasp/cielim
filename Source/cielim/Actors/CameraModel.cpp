//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of ACameraModel.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CameraModel.h"

#include "Components/SceneCaptureComponent2D.h"
#include "ImageUtils.h"
#include "Kismet/KismetRenderingLibrary.h"
// clang-format off
#include "OpenCV/PreOpenCVHeaders.h"
#include "opencv2/imgproc.hpp"
#include "OpenCV/PostOpenCVHeaders.h"
// clang-format on
#include "ScreenPass.h"

#include "../Shaders/ClearShader.h"
#include "RenderingFunctionsLibrary.h"

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

	this->SceneCaptureComponent2D->CaptureScene();
	this->ApplyPostProcessShaders(this->SceneCaptureComponent2D->TextureTarget);
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent2D->TextureTarget, Image));

	cv::Mat CvImage = FImageToOpenCVMat(Image);

	// Apply corruptions to image data matrix
	URenderingFunctionsLibrary::ApplyPSF_Gaussian(CvImage, 9, 9, PointSpread, PointSpread);
	URenderingFunctionsLibrary::ApplyCosmicRays(CvImage, CosmicRaysStdDev, 50.0f, 50.0f);
	URenderingFunctionsLibrary::ApplyReadNoise(CvImage, ReadNoise, 1.0f);
	URenderingFunctionsLibrary::ApplySignalGain(CvImage, 1.0f, SystemGain);
	// URenderingFunctionsLibrary::ApplyQE(PNGImageDataSerialized, 5.0f, 5.0f, 5.0f);

	FImage CorruptImage(Image);
	FMemory::Memcpy(CorruptImage.RawData.GetData(), CvImage.data, CorruptImage.RawData.Num());

	// Take modified image data from Image and copy to ImageData as PNG
	verify(FImageUtils::CompressImage(ImageData, TEXT("PNG"), CorruptImage));
}

void ACameraModel::ApplyPostProcessShaders(UTextureRenderTarget2D *RenderTarget)
{
	if (!RenderTarget)
		return;

	FTextureRenderTargetResource *RTResource = RenderTarget->GameThread_GetRenderTargetResource();

	ENQUEUE_RENDER_COMMAND(ApplyCorruptionPostProcess)
	(
		[RTResource](FRHICommandListImmediate &RHICmdList)
		{
			FRDGBuilder GraphBuilder(RHICmdList);

			const FRDGTextureRef OutputTexture =
				RegisterExternalTexture(GraphBuilder, RTResource->GetRenderTargetTexture(), TEXT("OutputTexture"));

			const FScreenPassTextureViewport Viewport(OutputTexture);

			// Pass parameters to the shader
			FClearShader::FParameters *PassParameters = GraphBuilder.AllocParameters<FClearShader::FParameters>();
			PassParameters->InputTexture = OutputTexture;
			PassParameters->InputSampler = TStaticSamplerState<SF_Point>::GetRHI();
			PassParameters->RenderTargets[0] = FRenderTargetBinding(OutputTexture, ERenderTargetLoadAction::ENoAction);

			const TShaderMapRef<FClearShader> PixelShader(GetGlobalShaderMap(GMaxRHIFeatureLevel));

			AddDrawScreenPass(GraphBuilder, RDG_EVENT_NAME("ApplyCorruptions"), GMaxRHIFeatureLevel, Viewport, Viewport,
							  PixelShader, PassParameters);

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
