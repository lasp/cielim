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
#include "CelestialBody.h"
#include "cielim/Protobuf/cielimMessage.pb.h"
#include "cielim/Protobuf/imageDiagnostics.pb.h"

#include "CameraModel.generated.h"

struct FCameraParams
{
	// Diagnostic indicator
	bool bIsDiagnosticRun;

	// Camera + QE
	float ApertureRadius;
	float FocalLength;
	float SensorWidth;
	float SensorHeight;
	float ExposureTime;
	float Wavelength1; // This is assumed to be the longest wavelength (650 nm by default)
	float Wavelength2; // This is assumed to be the middle wavelength (550 nm by default)
	float Wavelength3; // This is assumed to be the shortest wavelength (450 nm by default)
	FVector3f QuECurveR;
	FVector3f QuECurveG;
	FVector3f QuECurveB;
	float CorrectionFactor;
	bool bEnableShotNoise;
	float FullWellCapacity;
	float Gamma;
};

struct FDiagnosticParams
{
	// Coverage area of interest
	float CenterPixelX;
	float CenterPixelY;
	float AreaWidth;
	float AreaHeight;
	float Threshold;
};

struct FImageCorruptionParams
{
	// Gaussian PSF
	uint32 KernelWidth;
	float Sigma;

	// Cosmic Rays
	uint32 NumCosmicRays;
	TResourceArray<FVector2f> StartPoints = TResourceArray<FVector2f>();
	TResourceArray<FVector2f> EndPoints = TResourceArray<FVector2f>();
	TResourceArray<float> LineWidths = TResourceArray<float>();

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
	 * @param CielimMessage Protobuf containing camera model and other parameters.
	 */
	void SetCameraParameters(const cielimMessage::CielimMessage &CielimMessage);

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
	 * @brief Gets image data for scene render with corruption effects applied.
	 * @param ImageData Reference to TArray64 used to contain serialized image data in PNG format (mutable).
	 */
	void GetImageData(TArray64<uint8> &ImageData);

	/**
	 * @brief Gets pre-post-processing diagnostic data.
	 * @param Diagnostics Reference to protobuf containing diagnostic data (mutable).
	 */
	void GetDiagnosticData(imageDiagnostics::DiagnosticData &Diagnostics);

	bool IsCelestialBodyResolvable(const ACelestialBody &CelestialBody) const;

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent *Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	UCameraViewCaptureComponent2D *SceneCaptureComponent2D;

	FCameraParams CameraParams{};
	FDiagnosticParams DiagnosticParams{};
	FImageCorruptionParams CorruptionParams{};

protected:
	// Called when spawned
	virtual void BeginPlay() override;

private:
	/* Apply gamma correction to the render target; this is done separate from the main post-process pipeline to
	 * allow for the retrieval of a diagnostic image in linear color space. */
	void ApplyGammaCorrection() const;

	/* Enqueues CoB calculation pass on the GPU and synchronously writes resulting buffer back to the CPU and does
	 * final reduction to a 2-vector coordinate which is then returned as the final result. */
	FVector2D GetCenterOfBrightness() const;

	/* Enqueues coverage calculation pass on the GPU and synchronously writes resulting buffer back to the CPU
	 * and does final reduction to a float which is then returned as the final result. */
	float GetCoveragePercent() const;

	// Returns the list of all parameters for all cosmic rays
	TTuple<float, TResourceArray<FVector2f>, TResourceArray<FVector2f>, TResourceArray<float>>
	GetCosmicRays(const float Sigma) const;

	// Calculates the parameters for a single cosmic ray at random in pixels
	TTuple<FVector2f, FVector2f, float> GetCosmicRayParams() const;
};
