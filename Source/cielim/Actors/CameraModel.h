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
	float Transmission1;
	float Transmission2;
	float Transmission3;
	FVector3f QuECurveR;
	FVector3f QuECurveG;
	FVector3f QuECurveB;
	float CorrectionFactor;
	float FullWellCapacity;
	float Gamma;
	bool bIsGrayscale;
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
	// Lens Distortion
	float K1;
	float K2;
	float K3;
	float P1;
	float P2;

	// Gaussian PSF
	uint32 KernelWidth;
	float Sigma;

	// Shot noise (on or off)
	bool bEnableShotNoise;

	// Dark Current
	float DarkCurrent;
	uint32 DarkCurrentPattern;
	float DarkCurrentStdDeviation;

	// Cosmic Rays
	uint32 NumCosmicRays;
	TResourceArray<FVector2f> StartPoints = TResourceArray<FVector2f>();
	TResourceArray<FVector2f> EndPoints = TResourceArray<FVector2f>();
	TResourceArray<float> LineWidths = TResourceArray<float>();

	// Read Noise
	float ReadNoiseSigma;

	// Pixel defects
	uint32 PixelDefectPattern;
	float StuckPixelRate;
	float DeadPixelRate;

	// Signal Gain
	float SignalGain;
};

// Tunable parameters for the lens-flare / stray-light pass (LensFlares.usf), sourced from the
// protobuf StrayLightModel. Defaults reproduce the tuned look when a scene leaves them unset.
struct FStrayLightParams
{
	bool bEnabled = false; // Master on/off for the whole pass

	// Overall brightness of the flare as a fraction of the direct solar radiance (baffle/optics
	// throughput). Scales the entire flare uniformly. 1.0 = as bright as the sun's disk; real optics
	// are far dimmer (~1e-3..1e-6), so leave low to keep the flare from saturating the frame.
	float Intensity = 1.0f;

	// Typical tuning ranges are noted in [brackets]; they bound the useful look, not hard limits.
	float CoreSize = 1.0f; // Sun core disc size (shader SunFalloffK = 8 / CoreSize; larger = bigger disc) [0.1, 1]

	// Ghosts
	float GhostSize = 1.0f; // Global ghost size scale [0.1, 1.25]
	float GhostTransmittance = 3.0f; // Global ghost brightness (>1 so ghosts read above the corona) [0.5, 1.5]
	float Ghost1RelativeSize = 1.0f; // Per-ghost size scale, first (closest to sun) ghost [0.25, 1]
	float Ghost2RelativeSize = 1.0f; // ... second ghost [0.25, 1]
	float Ghost3RelativeSize = 1.0f; // ... third ghost [0.25, 1]
	float Ghost4RelativeSize = 1.0f; // ... fourth (orb) ghost [0.25, 1]
	float GhostBrightnessSizeExponent = 2.0f; // Couples ghost brightness to inverse size (2 = area-conserving)

	// Wide corona aureole (exposure-independent power-law glow around the core)
	float CoronaFalloffExponent = 1.2f; // Falloff exponent (higher = tighter corona) [0.5, 2]
	float CoronaIntensity = 0.02f; // Corona brightness relative to the core (low so ghosts aren't washed out) [0, 1]

	// Symmetric rays radiating from the sun (on top of the random streaks)
	float NumRays = 6.0f; // Number of evenly-spaced rays (even -> mirror-symmetric across boresight) [0, 15]
	float RaySharpness = 24.0f; // Angular sharpness (higher = narrower, crisper rays) [0, 30]
	float RayWeight = 0.8f; // Ray strength relative to the random streaks [0, 1]

	// Baffle / stray-light angular reach: the sun still casts stray light while it is within
	// (FoV half-angle + BaffleShieldAngle) of the boresight, even when it is outside the frame.
	float BaffleShieldAngle = 0.0f; // [deg] Extra angle beyond the FoV half-angle (0 = only when the sun is in frame)
};

struct FDistantObject
{
	/* TODO: Fix that albedo doesn't take into account albedo map corrections */
	FVector4f WorldPosition; // Float4's are used for alignment
	FVector4f Parameters;
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

	/**
	 * @brief Decide whether a celestial body should be rendered by the distant-object shader
	 *        (true) or by the UE5 mesh rasterizer (false).
	 */
	bool IsCelestialBodyResolvable(const ACelestialBody &CelestialBody, float PhaseAngle) const;

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent *Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	UCameraViewCaptureComponent2D *SceneCaptureComponent2D;

	// Camera parameters

	FCameraParams CameraParams{};
	FDiagnosticParams DiagnosticParams{};
	FImageCorruptionParams CorruptionParams{};
	FStrayLightParams StrayLightParams{};

	cielimMessage::ImageFormat::Format ImageFormat; // Defaults to PNG

	// Distant object information

	FVector3f SunPosition{};
	FVector3f SolarDirection{};
	FVector3f SolarSpectralRadiance{};
	FVector3f SolarSpectralIrradiance{};
	TArray<FDistantObject> DistantObjects{};

protected:
	// Called when spawned
	virtual void BeginPlay() override;

private:
	// Extract needed image channels from float image and converts to uint16
	static void ExtractImage(const FImage &Image, bool bIsGrayscale, TArray64<uint8> &OutData);

	// Packs image data into raw 8 bit format
	static void ExportRaw8(const TArray64<uint8> &InData, TArray64<uint8> &OutData);

	// Packs image data into raw 12 bit unpacked format
	static void ExportRaw12(const TArray64<uint8> &InData, TArray64<uint8> &OutData);

	// Packs image data into raw 12 bit packed format
	static void ExportRaw12Packed(const TArray64<uint8> &InData, TArray64<uint8> &OutData);

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
