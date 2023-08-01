// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "Math/Vector.h"

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "vizMessage.pb.h"
#include "ProtobufReader.h"
#include "CelestialBody.h"
#include "Spacecraft.h"
#include "ProtobufActor.generated.h"

UCLASS(Blueprintable)
class CIELIM_API AProtobufActor : public AActor
{
    GENERATED_BODY()
    
public:	
    // Sets default values for this actor's properties
    AProtobufActor();

protected:
    // Called when the game starts or when spawned
    virtual void BeginPlay() override;

public:	
    // Called every frame
    virtual void Tick(float DeltaTime) override;

    void SpawnCelestialBodies();
    void SpawnSpacecraft();

    void UpdateCelestialBodies();
    void UpdateSpacecraft();

    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<ACelestialBody> BpCelestialBody;

    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<ACelestialBody> BpSun;

    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<ASpacecraft> BpSpacecraft;

    void DebugVizmessage();

private:
    ProtobufReader* protobufreader;
    vizProtobufferMessage::VizMessage vizmessage;
    TArray<ACelestialBody*> CelestialBodyArray;
    ASpacecraft* Spacecraft;
    bool hasCameras;
};

