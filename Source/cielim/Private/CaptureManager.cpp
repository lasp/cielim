// Fill out your copyright notice in the Description page of Project Settings.

#include "CaptureManager.h"

#include "CielimImageUtilities.h"
#include "Components/SceneCaptureComponent2D.h"
#include "ImageUtils.h"
#include "Kismet/KismetRenderingLibrary.h"

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
	this->SceneCaptureComponent->CaptureScene();
	FImage Image;
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent->TextureTarget, Image));
	return Image;
}

cv::Mat ACaptureManager::GetCorruptedImage(FImage Image, double pointSpread, double readNoise, double systemGain, int nCosmicRays) const
{
	// TArray64<uint8> PNGImageData;
	// verify(FImageUtils::CompressImage(PNGImageData, TEXT("PNG"), Image));
	//
	// TArray<uint8> PNGImageDataSerialized;
	// PNGImageDataSerialized.Append(PNGImageData.GetData(), PNGImageData.Num());
	auto CvImage = CielimImageUtilities::FImageToOpenCVMat(Image);
	// Apply corruptions to image data
	URenderingFunctionsLibrary::ApplyPSF_Gaussian(CvImage, 9, 9, pointSpread, pointSpread);
	URenderingFunctionsLibrary::ApplyCosmicRays(CvImage, nCosmicRays, 50.0f, 50.0f);
	URenderingFunctionsLibrary::ApplyReadNoise(CvImage, readNoise, 1.0f);
	URenderingFunctionsLibrary::ApplySignalGain(CvImage, 1.0f, systemGain);
	//URenderingFunctionsLibrary::ApplyQE(PNGImageDataSerialized, 5.0f, 5.0f, 5.0f);

	// Copy data back over to PNGImageData
	// PNGImageData.SetNumUninitialized(PNGImageDataSerialized.Num());
	// FMemory::Memcpy(PNGImageData.GetData(), PNGImageDataSerialized.GetData(), PNGImageDataSerialized.Num());

	return CvImage;
}
