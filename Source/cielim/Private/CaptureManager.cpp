// Fill out your copyright notice in the Description page of Project Settings.

#include "CaptureManager.h"
#include "Components/SceneCaptureComponent2D.h"
#include "ImageUtils.h"
#include "Kismet/KismetRenderingLibrary.h"

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

TArray64<uint8> ACaptureManager::GetPNG() const {
	this->SceneCaptureComponent->CaptureScene();
	
	FImage Image;
	verify(FImageUtils::GetRenderTargetImage(this->SceneCaptureComponent->TextureTarget, Image));

	TArray64<uint8> PNGImageData;
	verify(FImageUtils::CompressImage(PNGImageData, TEXT("PNG"), Image));
	
	return PNGImageData;
}
