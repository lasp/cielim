// MIT LicenseCopyright (c) 2023 Laboratory for Atmospheric and Space PhysicsPermission is hereby granted, free of charge, to any person obtaining a copyof this software and associated documentation files (the "Software"), to dealin the Software without restriction, including without limitation the rightsto use, copy, modify, merge, publish, distribute, sublicense, and/or sellcopies of the Software, and to permit persons to whom the Software isfurnished to do so, subject to the following conditions:The above copyright notice and this permission notice shall be included in allcopies or substantial portions of the Software.THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS ORIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THEAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHERLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THESOFTWARE.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"
#include "PointLightActor.h"
#include "Spacecraft.h"
#include "SpawnScene.generated.h"


UCLASS()
class ASpawnScene : public AActor
{
	GENERATED_BODY()
public:
	/*
	UPROPERTY(EditDefaultsOnly)
	TSubclassOf<ASpacecraft> BpSpacecraft;
	*/
	UPROPERTY(EditAnywhere, Category = "BpSpacecraft")
	TSubclassOf<ASpacecraft> BpSpacecraft;

	UPROPERTY(EditAnywhere, Category = "BpSpacecraft")
	TSubclassOf<APointLightActor> BpPointLight;

private:
	
	void UpdateHorizontalPointLight(float a, float r, float h);

	void UpdateVerticalPointLight(float b, float r, float h);

	void ResetPointLight(float r, float h);

	UPROPERTY(EditDefaultsOnly)
	APointLightActor * PointLight;

	UPROPERTY(EditDefaultsOnly)
	ASpacecraft * Spacecraft;

	UPROPERTY(EditDefaultsOnly)
	float alpha = - PI / 4;

	UPROPERTY(EditDefaultsOnly)
	float beta = - PI / 4;

	UPROPERTY(EditDefaultsOnly)
	float radius = 500;

	UPROPERTY(EditDefaultsOnly)
	float height = 500;

	UPROPERTY(EditDefaultsOnly)
	bool clockwise_flag = true;

	UPROPERTY(EditDefaultsOnly)
	int alpha_flag_changes = 0;

	UPROPERTY(EditDefaultsOnly)
	int beta_flag_changes = 0;
	
	// Sets default values for this actor's properties
	ASpawnScene();
	

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

public:	
	// Called every frame
	virtual void Tick(float DeltaTime) override;
	
};
