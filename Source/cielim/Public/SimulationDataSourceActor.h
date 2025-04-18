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

UCLASS(Blueprintable)
class CIELIM_API ASimulationDataSourceActor : public AActor
{
	GENERATED_BODY()

protected:
	virtual void BeginPlay() override;

public:
	void SpawnCelestialBodies();
	void SpawnSpacecraft();
	void SpawnCaptureManager();

	void UpdateCelestialBodies() const;
	void UpdateSpacecraft() const;

	UPROPERTY(EditDefaultsOnly)
	TSubclassOf<ACelestialBody> BpSun;

	UPROPERTY(EditDefaultsOnly)
	TSubclassOf<ASpacecraft> BpSpacecraft;

	UFUNCTION(BlueprintCallable)
	void DebugCielimMessage() const;

	void PointSunLight();

	void ParseCommand(const FCircularQueueData &CommandData, FCircularQueueData &ReturnData);
	void UpdateScene() const;

private:
	FCielimMessage CielimMessage;
	TArray<ACelestialBody *> CelestialBodyArray;
	ACelestialBody *SunCelestialBody;
	ADirectionalLight *SunLight;
	ASpacecraft *Spacecraft = nullptr;
	ACaptureManager *CaptureManager = nullptr;
	bool bHasCameras = false;
	bool IsCelestialBodiesSpawned = false;
	bool IsSpacecraftSpawned = false;
	bool IsSceneEstablished = false;
	bool ShouldUpdateScene = false;
};
