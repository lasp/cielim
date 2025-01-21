#include "CaptureManager.h"

#include "ImageUtils.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Components/SceneCaptureComponent2D.h"

#include "RenderingFunctionsLibrary.h"

// Called when the game starts or when spawned
void ACaptureManager::BeginPlay()
{
	Super::BeginPlay();
}

// Called every frame
void ACaptureManager::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

void ACaptureManager::SetupRenderTarget(UTextureRenderTarget2D* RenderTarget)
{
	this->CaptureRenderTarget = RenderTarget;
}

void ACaptureManager::SetSceneCaptureComponent(USceneCaptureComponent2D* CaptureComponent)
{
	this->SceneCaptureComponent = CaptureComponent;
}

void ACaptureManager::SaveImageToDisk(const FString& FilePath, const FString& Filename)
{
	UKismetRenderingLibrary::ExportRenderTarget(this,
	                                            this->SceneCaptureComponent->TextureTarget,
	                                            FilePath,
	                                            Filename);
}

FImage ACaptureManager::GetUncorruptedImage() const
{
	FImage Image;
	
	this->SceneCaptureComponent->CaptureScene();
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent->TextureTarget, Image));

	return Image;
}

cv::Mat ACaptureManager::FImageToOpenCVMat(const FImage& Image) const
{
	// Access color data of Image and create 4 channel matrix
	const TArrayView64<const FColor>& PixelData = Image.AsBGRA8();
	cv::Mat OpenCVMat(Image.GetHeight(), Image.GetWidth(), CV_8UC4, (void*)PixelData.GetData());
	return OpenCVMat;
}

void ACaptureManager::GetCorruptedImage(TArray64<uint8>& ImageData, double pointSpread, double readNoise, double systemGain, double cosmicRaysStdDev) const
{
	FImage Image = GetUncorruptedImage();
	cv::Mat CvImage = FImageToOpenCVMat(Image);

	// Apply corruptions to image data matrix
	URenderingFunctionsLibrary::ApplyPSF_Gaussian(CvImage, 9, 9, pointSpread, pointSpread);
	URenderingFunctionsLibrary::ApplyCosmicRays(CvImage, cosmicRaysStdDev, 50.0f, 50.0f);
	URenderingFunctionsLibrary::ApplyReadNoise(CvImage, readNoise, 1.0f);
	URenderingFunctionsLibrary::ApplySignalGain(CvImage, 1.0f, systemGain);
	//URenderingFunctionsLibrary::ApplyQE(PNGImageDataSerialized, 5.0f, 5.0f, 5.0f);

	FImage corruptImage(Image);
	FMemory::Memcpy(corruptImage.RawData.GetData(), CvImage.data, corruptImage.RawData.Num());

	// Take modified image data from Image and copy to ImageData as PNG
	verify(FImageUtils::CompressImage(ImageData, TEXT("PNG"), corruptImage));
}

TOptional<FVector2d> ACaptureManager::GetCenterOfBrightness(double Threshold) const
{
	uint32_t WeightSum = 0;
	TOptional<FVector2D> Coordinates; // Default the case where the image has no brightness

	cv::Mat GrayImage;
	const FImage Image = GetUncorruptedImage();
	cv::cvtColor(FImageToOpenCVMat(Image), GrayImage, cv::COLOR_BGR2GRAY);
	cv::threshold(GrayImage, GrayImage, Threshold, 255, cv::THRESH_BINARY);

	// Compute the center of brightness
	if (const cv::Moments Moments = cv::moments(GrayImage, true); Moments.m00 != 0) 
	{
		Coordinates.Emplace(Moments.m10 / Moments.m00, Moments.m01 / Moments.m00);
	}

	return Coordinates;
}
