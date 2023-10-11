#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CelestialBody.generated.h"

UCLASS()
class CIELIM_API ACelestialBody : public AActor
{
    GENERATED_BODY()
    
public:	
    // Sets default values for this actor's properties
    ACelestialBody();

protected:
    // Called when the game starts or when spawned
    virtual void BeginPlay() override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    class UStaticMeshComponent * SphereMesh;

public:	

    // Dont know if there is a better way to do this
    UFUNCTION(BlueprintImplementableEvent)
    void SetRadiusEvent(const double& Radius);

    // Called every frame
    virtual void Tick(float DeltaTime) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
    FString name;

    void Update(const FVector3d& NewPosition, const FRotator& NewRotation);
};

