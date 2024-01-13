// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "CaptureManager.generated.h"

UCLASS()
class CIELIM_API ACaptureManager : public AActor
{
	GENERATED_BODY()
	
public:	
	// Sets default values for this actor's properties
	ACaptureManager();

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	UTextureRenderTarget2D* CaptureRenderTarget;


public:	
	// Called every frame
	virtual void Tick(float DeltaTime) override;

	void SetupRenderTarget(UTextureRenderTarget2D* RenderTarget);
	
	UFUNCTION(BlueprintCallable)
	void SaveImageToDisk(const FString& FilePath, const FString& Filename);

};
