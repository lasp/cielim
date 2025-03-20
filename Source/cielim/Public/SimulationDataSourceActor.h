// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include <memory>

#include "CoreMinimal.h"
#include "Math/Vector.h"
#include "GameFramework/Actor.h"
#include "Engine/DirectionalLight.h"
#include "ZmqConnection/ZmqMultiThreadActor.h"

#include "FCielimMessage.h"
#include "CelestialBody.h"
#include "Spacecraft.h"
#include "CaptureManager.h"

#include "SimulationDataSourceActor.generated.h"

UCLASS(Blueprintable)
class CIELIM_API ASimulationDataSourceActor : public AActor
{
    GENERATED_BODY()

public:
    // Sets default values for this actor's properties
    ASimulationDataSourceActor();

protected:
    // Called when the game starts or when spawned
    virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
    // Called every frame
    virtual void Tick(float DeltaTime) override;

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

private:
	void ParseQueue(float DeltaTime);

	AZmqMultiThreadActor* NetworkSimulationDataSource;
    FCielimMessage CielimMessage;
    TArray<ACelestialBody*> CelestialBodyArray;
	ACelestialBody* SunCelestialBody;
	ADirectionalLight* SunLight;
    ASpacecraft* Spacecraft=nullptr;
    ACaptureManager* CaptureManager=nullptr;
    bool bHasCameras=false;
    bool IsCelestialBodiesSpawned=false;
    bool IsSpacecraftSpawned=false;
    bool IsSceneEstablished=false;
	bool ShouldUpdateScene=false;
};
