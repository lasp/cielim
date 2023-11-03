// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CaptureManager.generated.h"

UCLASS()
class CIELIM_API ACaptureManager : public AActor
{
	GENERATED_BODY()
	
public:	
	// Sets default values for this actor's properties
	ACaptureManager()=default;
	
	virtual void Tick(float DeltaTime) override;

	void SetupRenderTarget(UTextureRenderTarget2D* RenderTarget);
	void SetSceneCaptureComponent(USceneCaptureComponent2D* CaptureComponent);

	UFUNCTION(BlueprintCallable)
	void SaveImageToDisk(const FString& FilePath, const FString& Filename);

	TArray64<uint8> GetPNG() const;
	
protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	UTextureRenderTarget2D* CaptureRenderTarget;

private:
	USceneCaptureComponent2D* SceneCaptureComponent;
};
