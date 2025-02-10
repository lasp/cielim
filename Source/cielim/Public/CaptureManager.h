#pragma once

#include <optional>

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OpenCV/PreOpenCVHeaders.h"
#include "opencv2/core.hpp"
#include "opencv2/imgproc.hpp"
#include "OpenCV/opencv/modules/imgcodecs/include/opencv2/imgcodecs.hpp"
#include "OpenCV/PostOpenCVHeaders.h"

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
	void GetCorruptedImage(TArray64<uint8>& ImageData, double pointSpread, double readNoise, double systemGain, double cosmicRaysStdDev) const;
	TOptional<FVector2d> GetCenterOfBrightness(double Threshold) const;

	FImage GetUncorruptedImage() const;
	cv::Mat FImageToOpenCVMat(const FImage& Image) const;

	
protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	UTextureRenderTarget2D* CaptureRenderTarget;

private:
	USceneCaptureComponent2D* SceneCaptureComponent;
};
