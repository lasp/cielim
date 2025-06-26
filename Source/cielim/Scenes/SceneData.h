//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the USceneData class. The SceneData holds all of the entities stored in the scene
//          and is spawned by the SceneManager.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"
#include "Engine/DirectionalLight.h"
#include "Math/Vector.h"

#include "../Actors/CelestialBody.h"
#include "../Actors/Spacecraft.h"
#include "../Network/QueueBridge.h"
#include "../Protobuf/CielimMessage.h"

#include "SceneData.generated.h"

UCLASS()
class CIELIM_API USceneData : public UObject
{
	GENERATED_BODY()

public:
	/**
	 * @brief Parses incoming queue data and acts accordingly to the query received.
	 * @param CommandData Inbound queue data to be parsed.
	 * @param ReturnData Outbound queue data (is modified).
	 */
	void ParseCommand(const FCircularQueueData &CommandData, FCircularQueueData &ReturnData);
	/**
	 * @brief Updates the entities according to the Protobuf Message.
	 */
	void UpdateScene() const;
	/**
	 * @brief Called when instance is destroyed by GC system, should not be called directly.
	 */
	virtual void BeginDestroy() override;

private:
	// Spawns all necessary entities from the Cielim Protobuf Message into the level
	void SpawnCelestialBodies();
	void SpawnSpacecraft();
	void SpawnSunLight();

	// Updates all entity positions and rotations
	void UpdateCelestialBodies() const;
	void UpdateSpacecraft() const;

	FCielimMessage CielimMessage;

	UPROPERTY()
	TArray<AActor *> Actors;
	UPROPERTY()
	TArray<ACelestialBody *> CelestialBodyArray;
	UPROPERTY()
	ACelestialBody *SunCelestialBody;
	UPROPERTY()
	ASpacecraft *Spacecraft;
	UPROPERTY()
	ADirectionalLight *SunLight;

	bool bHasCameras = false;
	bool bIsCelestialBodiesSpawned = false;
	bool bIsSpacecraftSpawned = false;
	bool bIsSceneEstablished = false;
	bool bShouldUpdateScene = false;
};
