// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DirectionalLight.h"
#include "Math/Vector.h"

#include "CaptureManager.h"
#include "CelestialBody.h"
#include "FCielimMessage.h"
#include "Spacecraft.h"
#include "ZmqConnection/QueueBridge.h"

#include "SimulationDataSourceActor.generated.h"

UCLASS()
class CIELIM_API USimulationDataSourceActor : public UObject
{
	GENERATED_BODY()

public:
	void SpawnCelestialBodies();
	void SpawnSpacecraft();
	void SpawnCaptureManager();

	void UpdateCelestialBodies() const;
	void UpdateSpacecraft() const;

	void PointSunLight();

	void ParseCommand(const FCircularQueueData &CommandData, FCircularQueueData &ReturnData);
	void UpdateScene() const;

private:
	FCielimMessage CielimMessage;

	UPROPERTY()
	TArray<ACelestialBody *> CelestialBodyArray;
	UPROPERTY()
	ACelestialBody *SunCelestialBody;
	UPROPERTY()
	ADirectionalLight *SunLight;
	UPROPERTY()
	ASpacecraft *Spacecraft = nullptr;
	UPROPERTY()
	ACaptureManager *CaptureManager = nullptr;

	bool bHasCameras = false;
	bool IsCelestialBodiesSpawned = false;
	bool IsSpacecraftSpawned = false;
	bool IsSceneEstablished = false;
	bool ShouldUpdateScene = false;
};
