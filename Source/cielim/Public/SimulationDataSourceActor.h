// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "Math/Vector.h"

#include <memory>
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "cielimMessage.pb.h"
#include "CelestialBody.h"
#include "Spacecraft.h"
#include "CaptureManager.h"
#include "ProtobufFileReader.h"
#include "ZmqConnection/ZmqMultiThreadActor.h"
#include "SimulationDataSourceActor.generated.h"

enum class DataSourceType {Network, File};

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
    TSubclassOf<ACelestialBody> BpCelestialBody;

    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<ACelestialBody> BpSun;

    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<ACelestialBody> BpAsteroid;

    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<ASpacecraft> BpSpacecraft;

    UFUNCTION(BlueprintCallable)
    void DebugCielimMessage() const;

private:
	void NetworkTick(float DeltaTime);
	void FileReaderTick(float DeltaTime);

	AZmqMultiThreadActor* NetworkSimulationDataSource;
	std::unique_ptr<ProtobufFileReader> SimulationDataSource;
    cielimMessage::CielimMessage CielimMessage;
    TArray<ACelestialBody*> CelestialBodyArray;
    ASpacecraft* Spacecraft=nullptr;
    ACaptureManager* CaptureManager=nullptr;
    bool bHasCameras=false;
    bool IsCelestialBodiesSpawned=false;
    bool IsSpacecraftSpawned=false;
    bool IsSceneEstablished=false;
	bool ShouldUpdateScene=false;
	DataSourceType DataSource=DataSourceType::File;
};

