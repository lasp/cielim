// Fill out your copyright notice in the Description page of Project Settings.

#include "CaptureManager.h"
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

TArray64<uint8> ACaptureManager::GetPNG() const 
{
	this->SceneCaptureComponent->CaptureScene();
	
	FImage Image;
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent->TextureTarget, Image));

	TArray64<uint8> PNGImageData;
	verify(FImageUtils::CompressImage(PNGImageData, TEXT("PNG"), Image));

	TArray<uint8> PNGImageDataSerialized;
	PNGImageDataSerialized.Append(PNGImageData.GetData(), PNGImageData.Num());

	// Apply corruptions to image data
	URenderingFunctionsLibrary::ApplyPSF_Gaussian(PNGImageDataSerialized, 31, 31, 15.0f, 15.0f);
	URenderingFunctionsLibrary::ApplyReadNoise(PNGImageDataSerialized, 30.0f, 4.0f);
	URenderingFunctionsLibrary::ApplySignalGain(PNGImageDataSerialized, 3.0f, 3.0f);
	URenderingFunctionsLibrary::ApplyQE(PNGImageDataSerialized, 5.0f, 5.0f, 5.0f);

	// Copy data back over to PNGImageData
	PNGImageData.SetNumUninitialized(PNGImageDataSerialized.Num());
	FMemory::Memcpy(PNGImageData.GetData(), PNGImageDataSerialized.GetData(), PNGImageDataSerialized.Num());
	
	return PNGImageData;
}
