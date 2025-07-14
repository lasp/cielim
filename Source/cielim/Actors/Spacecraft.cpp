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
	this->CameraModel->AttachToActor(this, FAttachmentTransformRules::KeepRelativeTransform);
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

void ASpacecraft::SetFOV(const double X, const double Y) const
{
	constexpr float NearPlaneDistance = 10.0f; // This is an arbitrary value

	const float TanHalfFovX = FMath::Tan(FMath::DegreesToRadians(X / 2.0f));
	const float TanHalfFovY = FMath::Tan(FMath::DegreesToRadians(Y / 2.0f));

	// Construct reversed-Z perspective matrix
	const FMatrix ProjectionMatrix = FMatrix(FPlane(1.0f / TanHalfFovX, 0, 0, 0), FPlane(0, 1.0f / TanHalfFovY, 0, 0),
											 FPlane(0, 0, 0, 1), FPlane(0, 0, NearPlaneDistance, 0));

	this->CameraModel->SceneCaptureComponent2D->CustomProjectionMatrix = ProjectionMatrix;
}

void ASpacecraft::SetResolution(const int ResolutionWidth, const int ResolutionHeight) const
{
	this->CameraModel->SceneCaptureComponent2D->TextureTarget->ResizeTarget(ResolutionWidth, ResolutionHeight);
}

void ASpacecraft::SetCameraRelativePosition(const FVector &RelativePosition) const
{
	this->CameraModel->SetActorRelativeLocation(RelativePosition);
}

void ASpacecraft::SetCameraRelativeOrientation(const FRotator &RelativeOrientation) const
{
	this->CameraModel->SetActorRelativeRotation(RelativeOrientation);
}

void ASpacecraft::Update(const FVector3d &NewPosition, const FRotator &NewRotation)
{
	SetActorLocation(NewPosition);
	SetActorRotation(NewRotation);
}
