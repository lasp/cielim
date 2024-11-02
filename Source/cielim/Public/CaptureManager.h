// Fill out your copyright notice in the Description page of Project Settings.

#pragma once
#include <OpenCV/PreOpenCVHeaders.h>
#include <opencv2/core.hpp>
#include "opencv2/imgproc.hpp"
#include <OpenCV/opencv/modules/imgcodecs/include/opencv2/imgcodecs.hpp>
#include <OpenCV/PostOpenCVHeaders.h>

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
	cv::Mat GetCorruptedImage(FImage Image, double pointSpread, double readNoise, double systemGain, int nCosmicRays) const;
	FImage GetUncorruptedImage() const;
	FVector2d GetCenterOfBrightness() const;
	
protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	UTextureRenderTarget2D* CaptureRenderTarget;

private:
	USceneCaptureComponent2D* SceneCaptureComponent;
};
