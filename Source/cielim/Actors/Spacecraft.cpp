//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of ASpacecraft.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "Spacecraft.h"

#include "CameraModel.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/TextureRenderTarget2D.h"

// Sets default values
ASpacecraft::ASpacecraft()
{
	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	this->PrimaryActorTick.bCanEverTick = true;

	this->RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	this->Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	this->Body->SetupAttachment(RootComponent);
}

// Called when the game starts or when spawned
void ASpacecraft::BeginPlay()
{
	Super::BeginPlay();

	this->CameraModel = GetWorld()->SpawnActor<ACameraModel>(ACameraModel::StaticClass(), this->GetActorLocation(),
															 this->GetActorRotation());
}

// Called every frame
void ASpacecraft::Tick(const float DeltaTime) { Super::Tick(DeltaTime); }

// Called when actor is destroyed
void ASpacecraft::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	this->CameraModel->Destroy();
	this->CameraModel = nullptr;

	Super::EndPlay(EndPlayReason);
}

void ASpacecraft::SetFOV(double X, double Y) const { this->CameraModel->SceneCaptureComponent2D->FOVAngle = X; }

void ASpacecraft::SetResolution(const int ResolutionWidth, const int ResolutionHeight) const
{
	this->CameraModel->SceneCaptureComponent2D->TextureTarget->ResizeTarget(ResolutionWidth, ResolutionHeight);
}

void ASpacecraft::SetCameraRelativePosition(const FVector &RelativePosition) const
{
	this->CameraModel->SetActorLocation(this->GetActorLocation() + this->GetActorRotation().RotateVector(RelativePosition));
}

void ASpacecraft::SetCameraRelativeOrientation(const FRotator &RelativeOrientation) const
{
	this->CameraModel->SetActorRotation(this->GetActorRotation().Quaternion() * RelativeOrientation.Quaternion());
}

void ASpacecraft::Update(const FVector3d &NewPosition, const FRotator &NewRotation)
{
	SetActorLocation(NewPosition);
	SetActorRotation(NewRotation);
}
