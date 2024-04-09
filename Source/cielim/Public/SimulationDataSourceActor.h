// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "Math/Vector.h"

#include <memory>
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "vizMessage.pb.h"
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
    void DebugVizmessage() const;

private:
	void NetworkTick(float DeltaTime);
	void FileReaderTick(float DeltaTime);

    std::unique_ptr<AZmqMultiThreadActor> NetworkSimulationDataSource;
	std::unique_ptr<ProtobufFileReader> SimulationDataSource;
    vizProtobufferMessage::VizMessage Vizmessage;
    TArray<ACelestialBody*> CelestialBodyArray;
    ASpacecraft* Spacecraft;
    ACaptureManager* CaptureManager;
    bool bHasCameras;
    bool IsCelestialBodiesSpawned=false;
    bool IsSpacecraftSpawned=false;
    bool IsSceneEstablished=false;
	DataSourceType DataSource=DataSourceType::File;
};

