// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
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
    virtual void Tick(float DeltaTime) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
    FString name;

    UFUNCTION(BlueprintImplementableEvent)
    void SetCameraPosition(const FVector& Position);

    UFUNCTION(BlueprintImplementableEvent)
    void UpdateCameraOrientation(const FRotator& Orientation);

    void Update(const FVector3d& NewPosition, const FRotator& NewRotation);

};

