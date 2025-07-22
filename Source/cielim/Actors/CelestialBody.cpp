//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of ACelestialBody.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CelestialBody.h"

#include "KismetProceduralMeshLibrary.h"
#include "ProceduralMeshComponent.h"
#include "cielim/Utilities/Logging/CielimLoggingMacros.h"

// Sets default values
ACelestialBody::ACelestialBody()
{
	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

	this->RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void ACelestialBody::LoadMesh(const FCelestialBodyMeshModel &Model)
{
	this->MeshModel = Model;

	// Load asteroid mesh asset from disk

	FSoftObjectPath MeshPath(FString("/Game/") + FString("AsteroidMeshes/") + this->MeshModel.ShapeModel +
							 FString(".") + this->MeshModel.ShapeModel);

	UStaticMesh *MeshAsset = Cast<UStaticMesh>(MeshPath.TryLoad());

	if (MeshAsset == nullptr)
	{
		MeshPath = "/Game/AsteroidMeshes/sphere_normalized.sphere_normalized";
		MeshAsset = Cast<UStaticMesh>(MeshPath.TryLoad());
	}

	// Extract geometry data (LOD 0, section 0)

	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;
	TArray<FProcMeshTangent> Tangents;

	UKismetProceduralMeshLibrary::GetSectionFromStaticMesh(MeshAsset, 0, 0, Vertices, Triangles, Normals, UV0,
														   Tangents);

	if (Vertices.Num() > 15000)
	{
		UE_LOG(LogCielim, Warning, TEXT("Mesh has %d vertices, cannot do procedural deformations."), Vertices.Num());

		UE_LOG(LogCielim, Display, TEXT("Loading static mesh..."));

		UStaticMeshComponent *StaticMesh = NewObject<UStaticMeshComponent>(this, UStaticMeshComponent::StaticClass());
		StaticMesh->SetupAttachment(this->RootComponent);
		StaticMesh->RegisterComponent();
		StaticMesh->SetStaticMesh(MeshAsset);

		this->MeshComponent = StaticMesh;
	}
	else
	{
		UE_LOG(LogCielim, Display, TEXT("Loading procedural mesh and applying deformations..."));

		// Apply fractal perlin noise

		constexpr int Octaves = 4;
		constexpr float BaseFrequency = 0.03f;
		constexpr float BaseAmplitude = 25.0f;
		constexpr float Persistence = 0.5f;

		const FVector RandomSeedOffset = FMath::VRand() * 100.0f;

		for (FVector &Vertex : Vertices)
		{
			float Frequency = BaseFrequency;
			float Amplitude = 1.0f;
			float MaxValue = 0.0f;
			float Total = 0.0f;

			for (int i = 0; i < Octaves; i++)
			{
				const float SimpleNoise = FMath::PerlinNoise3D(Vertex * Frequency + RandomSeedOffset);
				Total += SimpleNoise * Amplitude;
				MaxValue += Amplitude;

				Frequency *= 2.0f;
				Amplitude *= Persistence;
			}

			const float Noise = Total / MaxValue;
			Vertex += Vertex.GetSafeNormal() * Noise * BaseAmplitude;
		}

		UProceduralMeshComponent *ProceduralMesh =
			NewObject<UProceduralMeshComponent>(this, UProceduralMeshComponent::StaticClass());
		ProceduralMesh->SetupAttachment(this->RootComponent);
		ProceduralMesh->RegisterComponent();

		// Give procedural mesh modified geometry data

		UKismetProceduralMeshLibrary::CalculateTangentsForMesh(Vertices, Triangles, UV0, Normals, Tangents);

		TArray<FColor> VertexColors;
		VertexColors.Init(FColor::White, Vertices.Num());

		ProceduralMesh->CreateMeshSection(0, Vertices, Triangles, Normals, UV0, VertexColors, Tangents, false);
		ProceduralMesh->SetMaterial(0, MeshAsset->GetMaterial(0));

		this->MeshComponent = ProceduralMesh;
	}

	UE_LOG(LogCielim, Display, TEXT("BRDF Model: %s"), *this->MeshModel.BrdfModel)

	if (this->MeshModel.BrdfModel.Equals("Regolith"))
	{
		UMaterialInterface *RegolithMaterial = Cast<UMaterialInterface>(StaticLoadObject(
			UMaterialInterface::StaticClass(), nullptr, TEXT("Material'/Game/AsteroidMeshes/M_Regolith.M_Regolith'")));

		this->MeshComponent->SetMaterial(0, RegolithMaterial);
	}
}

void ACelestialBody::Update(const FVector3d &NewPosition, const FRotator &NewRotation)
{
	SetActorLocation(NewPosition);
	SetActorRotation(NewRotation);
}

FString ACelestialBody::GetMeshModelName() const { return this->MeshModel.ShapeModel; }

FRotator ACelestialBody::GetInertialToBodyRotator() const { return this->MeshModel.InertialToBody; }

FVector3d ACelestialBody::GetPrincipleAxisDistortions() const
{
	return FVector3d{this->MeshModel.PrincipalAxisDistortion.X, this->MeshModel.PrincipalAxisDistortion.Y,
					 this->MeshModel.PrincipalAxisDistortion.Z};
}

// Called when the game starts or when spawned
void ACelestialBody::BeginPlay() { Super::BeginPlay(); }

// Called every frame
void ACelestialBody::Tick(float DeltaTime) { Super::Tick(DeltaTime); }
