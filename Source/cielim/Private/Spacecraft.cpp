// Fill out your copyright notice in the Description page of Project Settings.


#include "Spacecraft.h"

// Sets default values
ASpacecraft::ASpacecraft()
{
 	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

}

// Called when the game starts or when spawned
void ASpacecraft::BeginPlay()
{
	Super::BeginPlay();
	
}

// Called every frame
void ASpacecraft::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

}

/**
 * @brief Updates spacecraft's position and rotation
 * 
 * @param NewPosition the new position
 * @param NewRotation the new rotation
 */
void ASpacecraft::Update(const FVector3d& NewPosition, const FQuat& NewRotation) 
{
	SetActorLocation(NewPosition);
	SetActorRotation(NewRotation);
}

