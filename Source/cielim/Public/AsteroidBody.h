#pragma once

#include "CelestialBodyMeshModel.h"

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AsteroidBody.generated.h"

UCLASS()
class CIELIM_API AAsteroidBody : public AActor
{
    GENERATED_BODY()

public:
    AAsteroidBody();

	void LoadMesh(CelestialBodyMeshModel Mesh);
	
	void SetMeshModel(CelestialBodyMeshModel Model);
	
	UFUNCTION(BlueprintCallable, Category = "AsteroidBody")
	FRotator GetInertialToBodyRotator() const;

	FVector3d GetPrincipleAccessDistortions() const;

	UFUNCTION(BlueprintCallable, Category = "AsteroidBody")
	FString GetMeshModelName() const;
	
    // Don't know if there is a better way to do this
    UFUNCTION(BlueprintImplementableEvent)
    void SetRadiusEvent(const double& Radius);

    // Called every frame
    virtual void Tick(float DeltaTime) override;

    void Update(const FVector3d& NewPosition, const FRotator& NewRotation);
    
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
    FString Name;
	TUniquePtr<UMaterial> MaterialAsset;

protected:
    // Called when the game starts or when spawned
    virtual void BeginPlay() override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    class UStaticMeshComponent * BodyStaticMeshComponent;

private:
	CelestialBodyMeshModel MeshModel;
};
