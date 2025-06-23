#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"

#include "CelestialBodyMeshModel.h"

#include "CelestialBody.generated.h"

USTRUCT(BlueprintType)
struct FBPVector3D
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	double X;
	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	double Y;
	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	double Z;
};

UCLASS()
class CIELIM_API ACelestialBody : public AActor
{
	GENERATED_BODY()

public:
	// Sets default values for this actor's properties
	ACelestialBody();

	void SetMeshModel(CelestialBodyMeshModel Model);

	UFUNCTION(BlueprintCallable, Category = "CelestialBody")
	FString GetMeshModelName() const;

	UFUNCTION(BlueprintCallable, Category = "CelestialBody")
	FRotator GetInertialToBodyRotator() const;

	FVector3d GetPrincipleAxisDistortions() const;

	// Don't know if there is a better way to do this
	UFUNCTION(BlueprintImplementableEvent)
	void SetRadiusEvent(const double &Radius);

	// Called every frame
	virtual void Tick(float DeltaTime) override;

	void Update(const FVector3d &NewPosition, const FRotator &NewRotation);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	FString Name;

	void LoadMesh(CelestialBodyMeshModel Mesh);

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	class UStaticMeshComponent *BodyStaticMeshComponent;

private:
	CelestialBodyMeshModel MeshModel;
};
