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

#include "CameraViewCaptureComponent2D.h"
#include "cielim/Protobuf/cielimMessage.pb.h"

#include "CameraModel.generated.h"

struct FCameraParams
{
	// Camera + QE
	float ApertureRadius;
	float FocalLength;
	float SensorWidth;
	float SensorHeight;
	float ExposureTime;
	FVector3f QuECurveR;
	FVector3f QuECurveG;
	FVector3f QuECurveB;
	float CorrectionFactor;
	float FullWellCapacity;
	float Gamma;
};

struct FImageCorruptionParams
{
	// Gaussian PSF
	uint32 KernelWidth;
	float Sigma;

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

	/**
	 * @brief Sets the parameters for the camera from protobuf camera model.
	 * @param CameraModel Protobuf camera model containing camera parameters.
	 */
	void SetCameraParameters(const cielimMessage::CameraModel &CameraModel);

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
	 */
	void GetCorruptedImage(TArray64<uint8> &ImageData, TOptional<FVector2D> &CobCoordinates) const;

	/**
	 * @brief Calculates center of brightness for an image.
	 * @param CobCoordinates Reference to optional FVector2D used to contain center of brightness coordinates (mutable).
	 */
	void GetCenterOfBrightness(TOptional<FVector2D> &CobCoordinates) const;

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent *Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	UCameraViewCaptureComponent2D *SceneCaptureComponent2D;

	FCameraParams CameraParams{};
	FImageCorruptionParams CorruptionParams{};

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
