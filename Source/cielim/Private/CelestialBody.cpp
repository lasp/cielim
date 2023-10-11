#include "CelestialBody.h"

// Sets default values
ACelestialBody::ACelestialBody()
{
    // Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
    PrimaryActorTick.bCanEverTick = true;
}

// Called when the game starts or when spawned
void ACelestialBody::BeginPlay()
{
    Super::BeginPlay();
}

// Called every frame
void ACelestialBody::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
}

/**
 * @brief Update(NewPosition, NewRotation) Updates celestial body's position and rotation
 * 
 * @param NewPosition The new position
 * @param NewRotation The new rotation
 */
void ACelestialBody::Update(const FVector3d& NewPosition, const FRotator& NewRotation)
{
    SetActorLocation(NewPosition);
    SetActorRotation(NewRotation);
}

