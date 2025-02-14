#include "AsteroidBody.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"

AAsteroidBody::AAsteroidBody()
{
    PrimaryActorTick.bCanEverTick = true;
	BodyStaticMeshComponent = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
    RootComponent = BodyStaticMeshComponent;
}

void AAsteroidBody::LoadMesh(CelestialBodyMeshModel Mesh)
{
	this->MeshModel = Mesh;
	const FString TmpPath = FString("/Game/")
	+ FString("AsteroidMeshes/")
	+ this->MeshModel.ShapeModel
	+ FString(".")
	+ this->MeshModel.ShapeModel;
	
	FStringAssetReference MeshPath(TmpPath);
	UStaticMesh* MeshAsset = Cast<UStaticMesh>(MeshPath.TryLoad());
	
	if (MeshAsset == nullptr) {
		MeshPath = "/Game/AsteroidMeshes/sphere_normalized.sphere_normalized";
		MeshAsset = Cast<UStaticMesh>(MeshPath.TryLoad());
	}
	
	BodyStaticMeshComponent->SetStaticMesh(MeshAsset);
}

// Called when the game starts or when spawned
void AAsteroidBody::BeginPlay()
{
    Super::BeginPlay();
}

// Called every frame
void AAsteroidBody::Tick(const float DeltaTime)
{
    Super::Tick(DeltaTime);
}

void AAsteroidBody::SetMeshModel(CelestialBodyMeshModel Model)
{
	this->MeshModel = Model;
}

FVector3d AAsteroidBody::GetPrincipleAccessDistortions() const
{
	return FVector3d{this->MeshModel.PrincipalAxisDistortion.X,
		this->MeshModel.PrincipalAxisDistortion.Y,
		this->MeshModel.PrincipalAxisDistortion.Z};
}

FRotator AAsteroidBody::GetInertialToBodyRotator() const
{
	return this->MeshModel.InertialToBody;
}

FString AAsteroidBody::GetMeshModelName() const
{
	return this->MeshModel.ShapeModel;	
}

/**
 * @brief Update(NewPosition, NewRotation) Updates celestial body's position and rotation
 *
 * @param NewPosition The new position
 * @param NewRotation The new rotation
 */
void AAsteroidBody::Update(const FVector3d& NewPosition, const FRotator& NewRotation)
{
    SetActorLocation(NewPosition);
    SetActorRotation(NewRotation);
}
