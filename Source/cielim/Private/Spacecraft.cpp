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
 * @brief Update(NewPosition, NewRotation) Updates the spacecraft's position and rotation
 * 
 * @param NewPosition The new position
 * @param NewRotation The new rotation
 */
void ASpacecraft::Update(const FVector3d& NewPosition, const FRotator& NewRotation) 
{
    SetActorLocation(NewPosition);
    SetActorRotation(NewRotation);
}

