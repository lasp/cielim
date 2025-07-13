//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the ACameraModel class. The CameraModel actor owns a SceneCaptureComponent2D that
//          renders the scene and returns image data.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"

#include "CameraModel.generated.h"

struct FImageCorruptionParams
{
	// Gaussian PSF
	int KernelWidth;
	double Sigma;

	// Cosmic Rays
	uint32 NumCosmicRays;
	TResourceArray<FVector2f> StartPoints;
	TResourceArray<FVector2f> EndPoints;
	TResourceArray<float> LineWidths;

	// Read Noise
	float ReadNoiseSigma;

	// Signal Gain
	float SignalGain;
};

UCLASS()
class CIELIM_API ACameraModel : public AActor
{
	GENERATED_BODY()

public:
	ACameraModel();

	// Called every tick; should not be manually called
	virtual void Tick(float DeltaTime) override;

	UFUNCTION(BlueprintCallable)
	void SaveImageToDisk(const FString &FilePath, const FString &Filename);

	void GetCorruptedImage(TArray64<uint8> &ImageData, const double PointSpread, const double ReadNoise,
						   const double SystemGain, const double CosmicRaysStdDev) const;

	static void ApplyPostProcessShaders(UTextureRenderTarget2D *RenderTarget, FImageCorruptionParams *CorruptionParams);

	TOptional<FVector2d> GetCenterOfBrightness() const;

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent *Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	USceneCaptureComponent2D *SceneCaptureComponent2D;

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

private:
	// Returns the list of all parameters for all cosmic rays
	TTuple<float, TResourceArray<FVector2f>, TResourceArray<FVector2f>, TResourceArray<float>>
	GetCosmicRays(const float Sigma) const;

	// Calculates the parameters for a single cosmic ray at random in pixels
	TTuple<FVector2f, FVector2f, float> GetCosmicRayParams() const;
};
