//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the ASpacecraft class. The spacecraft is an entity owned by a SceneData instance
//          and itself holds the CameraModel actor used to capture the scene from the point of
//          view of the spacecraft.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CameraModel.h"
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
	// Called when actor is destroyed
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent *Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	ACameraModel *CameraModel;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	FString Name;

	/**
	 * @brief Sets the fov of the spacecraft's camera.
	 * @param X Horizontal fov value in degrees.
	 * @param Y Vertical fov value in degrees.
	 */
	void SetFOV(const double X, const double Y) const;

	/**
	 * @brief Sets the resolution of the spacecraft's camera.
	 * @param ResolutionWidth Horizontal resolution in pixels.
	 * @param ResolutionHeight Vertical resolution in pixels.
	 */
	void SetResolution(const int ResolutionWidth, const int ResolutionHeight) const;

	/**
	 * @brief Sets the position of the spacecraft's camera relative to the spacecraft.
	 * @param RelativePosition 3D position vector for the intended relative position of the camera.
	 */
	void SetCameraRelativePosition(const FVector &RelativePosition) const;

	/**
	 * @brief Sets the orientation of the spacecraft's camera relative to the spacecraft.
	 * @param RelativeOrientation 3D rotation vector for the intended relative orientation of the camera.
	 */
	void SetCameraRelativeOrientation(const FRotator &RelativeOrientation) const;

	/**
	 * @brief Updates the spacecraft's position and rotation
	 * @param NewPosition The new position
	 * @param NewRotation The new rotation
	 */
	void Update(const FVector3d &NewPosition, const FRotator &NewRotation);
};
