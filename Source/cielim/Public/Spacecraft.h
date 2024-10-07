// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/SceneCaptureComponent2D.h"
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

    UPROPERTY(EditAnywhere)
    USceneComponent* Root;
    
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Spacecraft Components")
    UStaticMeshComponent* Body;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Spacecraft Components")
    USceneCaptureComponent2D* SceneCaptureComponent2D;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
    FString Name;

    UFUNCTION(BlueprintImplementableEvent)
    void SetFOV(double X, double Y);

    UFUNCTION(BlueprintImplementableEvent)
    void SetResolution(const int ResolutionWidth, const int ResolutionHeight);

    UFUNCTION(BlueprintImplementableEvent)
    void SetCameraPosition(const FVector& Position);

    UFUNCTION(BlueprintImplementableEvent)
    void UpdateCameraOrientation(const FRotator& Orientation);

    void Update(const FVector3d& NewPosition, const FRotator& NewRotation);

};

