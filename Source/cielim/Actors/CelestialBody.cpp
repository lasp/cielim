#include "CelestialBody.h"

// Sets default values
ACelestialBody::ACelestialBody()
{
	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

	// Create the Static Mesh Component
	this->BodyStaticMeshComponent = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("StaticMeshComponent"));
	this->RootComponent = BodyStaticMeshComponent;

	// Load the mesh asset
	static ConstructorHelpers::FObjectFinder<UStaticMesh> MeshAsset(TEXT("/Content/AsteroidMeshes/sphere_normalized"));

	// Set the mesh on the component
	if (MeshAsset.Succeeded())
	{
		BodyStaticMeshComponent->SetStaticMesh(MeshAsset.Object);
	}
}

void ACelestialBody::LoadMesh(CelestialBodyMeshModel Mesh)
{
	this->MeshModel = Mesh;
	const FString TmpPath = FString("/Game/") + FString("AsteroidMeshes/") + this->MeshModel.ShapeModel + FString(".") +
		this->MeshModel.ShapeModel;

	FStringAssetReference MeshPath(TmpPath);
	UStaticMesh *MeshAsset = Cast<UStaticMesh>(MeshPath.TryLoad());

	if (MeshAsset == nullptr)
	{
		MeshPath = "/Game/AsteroidMeshes/sphere_normalized.sphere_normalized";
		MeshAsset = Cast<UStaticMesh>(MeshPath.TryLoad());
	}

	BodyStaticMeshComponent->SetStaticMesh(MeshAsset);
}

// Called when the game starts or when spawned
void ACelestialBody::BeginPlay() { Super::BeginPlay(); }

// Called every frame
void ACelestialBody::Tick(float DeltaTime) { Super::Tick(DeltaTime); }

void ACelestialBody::SetMeshModel(CelestialBodyMeshModel Model) { this->MeshModel = Model; }

FString ACelestialBody::GetMeshModelName() const { return this->MeshModel.ShapeModel; }

FVector3d ACelestialBody::GetPrincipleAxisDistortions() const
{
	return FVector3d{this->MeshModel.PrincipalAxisDistortion.X, this->MeshModel.PrincipalAxisDistortion.Y,
					 this->MeshModel.PrincipalAxisDistortion.Z};
}

FRotator ACelestialBody::GetInertialToBodyRotator() const { return this->MeshModel.InertialToBody; }

/**
 * @brief Update(NewPosition, NewRotation) Updates celestial body's position and rotation
 *
 * @param NewPosition The new position
 * @param NewRotation The new rotation
 */
void ACelestialBody::Update(const FVector3d &NewPosition, const FRotator &NewRotation)
{
	SetActorLocation(NewPosition);
	SetActorRotation(NewRotation);
}
