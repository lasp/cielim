// Fill out your copyright notice in the Description page of Project Settings.


#include "CaptureManager.h"

// Sets default values
ACaptureManager::ACaptureManager()
{
 	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

}

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

void ACaptureManager::SaveImageToDisk(const FString& FilePath, const FString& Filename)
{
	UKismetRenderingLibrary::ExportRenderTarget(this,this->CaptureRenderTarget, FilePath, Filename);
}

