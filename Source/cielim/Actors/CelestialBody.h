//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the ACelestialBody actor class. This represents celestial bodies in the scene.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"

#include "CelestialBodyMeshModel.h"

#include "CelestialBody.generated.h"

UCLASS()
class CIELIM_API ACelestialBody : public AActor
{
	GENERATED_BODY()

public:
	// Sets default values for this actor's properties
	ACelestialBody();
	/**
	 * @brief Sets the mesh model used by the celestial body and loads proper mesh asset.
	 * @param Model Reference to a Cielim protobuffer mesh model.
	 */
	void LoadMesh(const FCelestialBodyMeshModel &Model);
	/**
	 * @brief Updates the celestial body's position and rotation.
	 * @param NewPosition The new position
	 * @param NewRotation The new rotation
	 */
	void Update(const FVector3d &NewPosition, const FRotator &NewRotation);
	/**
	 * @brief Gets the name of the celestial body's mesh.
	 * @return Returns the mesh name as an FString.
	 */
	FString GetMeshModelName() const;
	/**
	 * @brief Gets the mean radius of the celestial body's mesh.
	 * @return Returns the mean radius as a float.
	 */
	float GetMeanRadius() const;
	/**
	 * @brief Gets the inertial-to-body rotator of the celestial body's mesh.
	 * @return Returns inertial-to-body rotator as an FRotator.
	 */
	FRotator GetInertialToBodyRotator() const;
	/**
	 * @brief Gets the principal axis distortion of the celestial body's mesh.
	 * @return Returns the x, y, and z components of the principal axis distortion in a 3-vector.
	 */
	FVector3d GetPrincipleAxisDistortions() const;

	// Don't know if there is a better way to do this
	UFUNCTION(BlueprintImplementableEvent)
	void SetRadiusEvent(const double &Radius);

	// Called every frame
	virtual void Tick(float DeltaTime) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	FString Name;

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

private:
	FCelestialBodyMeshModel MeshModel;

	UPROPERTY(VisibleAnywhere)
	UMeshComponent *MeshComponent;
};
