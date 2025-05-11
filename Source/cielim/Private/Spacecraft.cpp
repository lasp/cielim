#include "Spacecraft.h"

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

	this->SceneCaptureComponent2D = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("SceneCaptureComponent2D"));

	// Add settings
	this->SceneCaptureComponent2D->TextureTarget = NewObject<UTextureRenderTarget2D>(this, TEXT("RT_Spacecraft"));
	this->SceneCaptureComponent2D->TextureTarget->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8;
	this->SceneCaptureComponent2D->TextureTarget->InitAutoFormat(2560, 1440);
	this->SceneCaptureComponent2D->TextureTarget->UpdateResourceImmediate();
	this->SceneCaptureComponent2D->bCaptureEveryFrame = false;
	this->SceneCaptureComponent2D->SetupAttachment(Body);
}

// Called when the game starts or when spawned
void ASpacecraft::BeginPlay() { Super::BeginPlay(); }

// Called every frame
void ASpacecraft::Tick(const float DeltaTime) { Super::Tick(DeltaTime); }

void ASpacecraft::SetFOV(double X, double Y) const { this->SceneCaptureComponent2D->FOVAngle = X; }

void ASpacecraft::SetResolution(const int ResolutionWidth, const int ResolutionHeight) const
{
	this->SceneCaptureComponent2D->TextureTarget->ResizeTarget(ResolutionWidth, ResolutionHeight);
}

void ASpacecraft::SetCameraPosition(const FVector &Position) const
{
	this->SceneCaptureComponent2D->SetRelativeLocation(Position);
}

void ASpacecraft::UpdateCameraOrientation(const FRotator &Orientation) const
{
	this->SceneCaptureComponent2D->SetRelativeRotation(Orientation);
}

void ASpacecraft::Update(const FVector3d &NewPosition, const FRotator &NewRotation)
{
	SetActorLocation(NewPosition);
	SetActorRotation(NewRotation);
}
