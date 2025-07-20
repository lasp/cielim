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

	/**
	 * @brief Saves the contents of the current render target to disk.
	 * @param FilePath Path to location where image will be saved.
	 * @param Filename Name of the saved image.
	 */
	UFUNCTION(BlueprintCallable)
	void SaveImageToDisk(const FString &FilePath, const FString &Filename);

	/**
	 * @brief Gets image data after applying corruption effects for the current render target.
	 * @param ImageData Reference to TArray64 used to contain serialized image data in PNG format (mutable).
	 * @param CobCoordinates Reference to optional FVector2D used to contain center of brightness coordinates (mutable).
	 * @param PointSpread Standard deviation value used in Gaussian PSF.
	 * @param ReadNoise Standard deviation value used in read noise.
	 * @param SystemGain Gain that will be applied to the overall image.
	 * @param CosmicRaysStdDev Standard deviation used to determine the number of cosmic rays from a poisson.
	 */
	void GetCorruptedImage(TArray64<uint8> &ImageData, TOptional<FVector2D> &CobCoordinates, const double PointSpread,
						   const double ReadNoise, const double SystemGain, const double CosmicRaysStdDev) const;

	/**
	 * @brief Calculates center of brightness for an image.
	 * @param RenderTarget Pointer to render target used in center of brightness calculations.
	 */
	static TOptional<FVector2d> GetCenterOfBrightness(UTextureRenderTarget2D *RenderTarget);

	/**
	 * @brief Queues image corruption post-processing effects on the GPU through RenderGraph.
	 * @param RenderTarget Pointer to render target that the corruption effects will be applied to.
	 * @param CorruptionParams Struct containing all necessary parameters for corruption effects.
	 */
	static void ApplyPostProcessShaders(UTextureRenderTarget2D *RenderTarget, FImageCorruptionParams *CorruptionParams);

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
