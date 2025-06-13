//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the ASpacecraft class. The spacecraft is an entity owned by a SceneData instance
//          and itself holds the SceneCaptureComponent2D used to capture the scene from the point of
//          view of the spacecraft.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"

#include "Spacecraft.generated.h"

UCLASS()
class CIELIM_API ASpacecraft : public AActor
{
	GENERATED_BODY()

public:
	// Sets default values for this actor's properties
	ASpacecraft();

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

public:
	// Called every frame
	virtual void Tick(const float DeltaTime) override;

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent *Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	USceneCaptureComponent2D *SceneCaptureComponent2D;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	FString Name;

	void SetFOV(double X, double Y) const;

	void SetResolution(const int ResolutionWidth, const int ResolutionHeight) const;

	void SetCameraPosition(const FVector &Position) const;

	void UpdateCameraOrientation(const FRotator &Orientation) const;

	/**
	 * @brief Update(NewPosition, NewRotation) Updates the spacecraft's position and rotation
	 *
	 * @param NewPosition The new position
	 * @param NewRotation The new rotation
	 */
	void Update(const FVector3d &NewPosition, const FRotator &NewRotation);
};
