//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of USceneData.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "SceneData.h"

#include "Components/LightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/World.h"
#include "Math/UnrealMathUtility.h"

#include "../CielimGameInstance.h"
#include "AstronomicalConstants.h"
#include "CelestialBodyMeshModel.h"
#include "CielimLoggingMacros.h"
#include "KinematicsUtilities.h"

#define m2cm 100.0
#define km2m 1000.0
const FString SunNaifBodyName("Sun");

static FVector3d GetSpacecraftPosition(const cielimMessage::Spacecraft &Craft);
static FRotator GetRotatorFromMrp(const FVector3d &Sigma);
static FVector3d GetCameraPosition(const cielimMessage::CameraModel &Camera);
static FRotator GetCameraRotation(const cielimMessage::CameraModel &Camera);
static FVector3d GetCelestialBodyPosition(const cielimMessage::CelestialBody &CelestialBody);
static FRotator GetCelestialBodyRotation(const cielimMessage::CelestialBody &CelestialBody);

// This is a mad hack and needs to be changed
void USceneData::ParseCommand(const FCircularQueueData &CommandData, FCircularQueueData &ReturnData)
{
	this->bShouldUpdateScene = false;

	// This code should be turned into some kind of handler function registration
	// a bit like an RPC or http server
	if (CommandData.query == CommandType::INIT_SCENE)
	{
		UE_LOG(LogCielim, Display, TEXT("Initiating new scene: ASimulationDataSourceActor"));

		this->bIsSceneEstablished = false;

		// Clear existing objects

		for (auto const CelestialBody : this->CelestialBodyArray)
		{
			if (CelestialBody != nullptr)
				CelestialBody->Destroy();
		}
		this->CelestialBodyArray.Reset();

		if (this->SunCelestialBody != nullptr)
		{
			this->SunCelestialBody->Destroy();
			this->SunCelestialBody = nullptr;
		}

		if (this->SunLight != nullptr)
		{
			this->SunLight->Destroy();
			this->SunLight = nullptr;
		}

		if (this->Spacecraft != nullptr)
		{
			this->Spacecraft->Destroy();
			this->Spacecraft = nullptr;
		}

		if (this->CaptureManager != nullptr)
		{
			this->CaptureManager->Destroy();
			this->CaptureManager = nullptr;
		}

		this->bIsCelestialBodiesSpawned = false;
		this->bIsSpacecraftSpawned = false;
		this->bIsSceneEstablished = false;
	}
	else if (CommandData.query == CommandType::SIM_UPDATE)
	{
		UE_LOG(LogCielim, Display, TEXT("Reading sim update data: ASimulationDataSourceActor"));

		if (const auto *TempPayload = CommandData.payload.TryGet<FUpdatePayload>())
		{
			this->CielimMessage = TempPayload->message;
		}

		if (!this->bIsSceneEstablished)
		{
			this->bIsSceneEstablished = true;

			UE_LOG(LogCielim, Display, TEXT("Initialize scene..."));

			if (const auto *TempPayload = CommandData.payload.TryGet<FUpdatePayload>())
			{
				this->CielimMessage = TempPayload->message;
			}

			this->SpawnCelestialBodies();
			this->SpawnSpacecraft();

			if (this->CielimMessage.GetMessage().has_camera())
			{
				this->bHasCameras = true;
				this->SpawnCaptureManager();
			}
		}
		else
		{
			this->bShouldUpdateScene = true;
		}
	}
	else if (CommandData.query == CommandType::REQUEST_IMAGE)
	{
		if (!this->bIsSceneEstablished)
		{
			UE_LOG(LogCielim, Warning, TEXT("Scene not initialized: ASimulationDataSourceActor"));
			return;
		}

		const double PointSpread = this->CielimMessage.GetMessage().camera().pointspreadfunction();
		const double ReadNoise = this->CielimMessage.GetMessage().camera().readnoise();
		const double SystemGain = this->CielimMessage.GetMessage().camera().systemgain();
		const double CosmicRayStdDev =
			this->CielimMessage.GetMessage().camera().renderparameters().cosmicraystddeviation();

		TArray64<uint8> PngEncodedData;

		const auto *TempPayload = CommandData.payload.TryGet<FImagePayload>();

		if (TempPayload != nullptr && TempPayload->shouldReturnImage)
		{
			this->CaptureManager->GetCorruptedImage(PngEncodedData, PointSpread, ReadNoise, SystemGain,
													CosmicRayStdDev);
		}

		ReturnData.query = CommandType::REQUEST_IMAGE;
		ReturnData.payload.Emplace<FImagePayload>(FImagePayload());
		ReturnData.payload.Get<FImagePayload>().image_data = PngEncodedData;
		ReturnData.payload.Get<FImagePayload>().centerOfBrightness = this->CaptureManager->GetCenterOfBrightness(10);

		UE_LOG(LogCielim, Display, TEXT("Put back PNG image: ASimulationDataSourceActor"));
	}
	else
	{
		UE_LOG(LogCielim, Display, TEXT("GetNextSimulationData received unrecognized Type"));
	}
}

void USceneData::UpdateScene() const
{
	if (!this->bShouldUpdateScene)
		return;

	if (this->CielimMessage.GetMessage().has_spacecraft() && this->bIsSpacecraftSpawned)
	{
		this->UpdateSpacecraft();
	}

	if (!this->CielimMessage.GetMessage().celestialbodies().empty() && this->bIsCelestialBodiesSpawned)
	{
		this->UpdateCelestialBodies();
	}
}

void USceneData::SpawnCelestialBodies()
{
	for (const auto &CelestialBody : CielimMessage.GetMessage().celestialbodies())
	{
		FVector3d PositionCelestialBody = GetCelestialBodyPosition(CelestialBody);
		FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);

		const FTransform SpawnLocAndRotation = FTransform(CelestialBodyRotation, PositionCelestialBody);

		ACelestialBody *TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>();
		TempCelestialBody->SetActorTransform(SpawnLocAndRotation);

		CelestialBodyMeshModel MeshModel{};
		if (CelestialBody.has_model())
		{
			MeshModel = CelestialBodyMeshModel::FromProtobuf(CelestialBody.model());
		}

		TempCelestialBody->LoadMesh(MeshModel);
		TempCelestialBody->SetActorRotation(MeshModel.InertialToBody);
		TempCelestialBody->SetActorLocation(PositionCelestialBody);
		TempCelestialBody->Name = FString(CelestialBody.bodyname().c_str());
		// meshes are in 10m scale, bring to uu/
		const FVector ActorScale =
			TempCelestialBody->GetPrincipleAxisDistortions() * CelestialBody.model().meanradius() / 1000;
		TempCelestialBody->SetActorScale3D(ActorScale);

		this->CelestialBodyArray.Add(TempCelestialBody);

		if (TempCelestialBody->Name == SunNaifBodyName)
		{
			this->SunCelestialBody = TempCelestialBody;
		}
	}

	this->bIsCelestialBodiesSpawned = true;
}

void USceneData::SpawnSpacecraft()
{
	const cielimMessage::Spacecraft &SpacecraftMessage = this->CielimMessage.GetMessage().spacecraft();

	const FVector3d PositionSpacecraft = GetSpacecraftPosition(SpacecraftMessage);
	const FVector3d AttitudeVector =
		FVector3d(SpacecraftMessage.attitude(0), SpacecraftMessage.attitude(1), SpacecraftMessage.attitude(2));
	const FRotator SpacecraftRotation = GetRotatorFromMrp(AttitudeVector);

	ASpacecraft *TempSpacecraft = GetWorld()->SpawnActor<ASpacecraft>(PositionSpacecraft, SpacecraftRotation);

	TempSpacecraft->Name = FString(SpacecraftMessage.spacecraftname().c_str());

	// Set camera
	if (this->CielimMessage.GetMessage().has_camera())
	{
		const cielimMessage::CameraModel &Camera = CielimMessage.GetMessage().camera();
		TempSpacecraft->SetFOV(FMath::RadiansToDegrees(Camera.fieldofview(0)),
							   FMath::RadiansToDegrees(Camera.fieldofview(1)));
		TempSpacecraft->SetResolution(Camera.resolution(0), Camera.resolution(1));

		const FVector3d CameraPosition = GetCameraPosition(Camera);
		TempSpacecraft->SetCameraPosition(CameraPosition);

		const FRotator CameraRotation = GetCameraRotation(Camera);
		TempSpacecraft->UpdateCameraOrientation(CameraRotation);
	}

	this->Spacecraft = TempSpacecraft;
	this->bIsSpacecraftSpawned = true;

	this->SpawnSunLight();
}

void USceneData::SpawnSunLight()
{
	this->SunLight = GetWorld()->SpawnActor<ADirectionalLight>(FVector3d::ZeroVector, FRotator::ZeroRotator);

	const double ExposureTime = this->CielimMessage.GetMessage().camera().exposuretime();
	const double LuxAt1AU = ExposureTime != 0 ? 1280 * ExposureTime : 1280;

	const float SunIntensity =
		LuxAt1AU * (AU * km2m * AU * km2m) / FMath::Square(this->SunCelestialBody->GetActorLocation().Length());
	this->SunLight->GetLightComponent()->SetIntensity(SunIntensity);
	this->SunLight->GetLightComponent()->SetMobility(EComponentMobility::Movable);

	auto Vector = -this->SunCelestialBody->GetActorLocation();
	Vector.Normalize();

	const auto RotationMatrixFromLocation = FRotationMatrix::MakeFromX(Vector);
	this->SunLight->GetLightComponent()->SetRelativeRotation(RotationMatrixFromLocation.Rotator());
}

void USceneData::SpawnCaptureManager()
{
	this->CaptureManager = GetWorld()->SpawnActor<ACaptureManager>();

	this->CaptureManager->SetSceneCaptureComponent(this->Spacecraft->SceneCaptureComponent2D);

	UE_LOG(LogCielim, Display, TEXT("Set Capture Texture Target"));
}

void USceneData::UpdateCelestialBodies() const
{
	int Index = 0;
	for (const auto &CelestialBody : CielimMessage.GetMessage().celestialbodies())
	{
		FVector3d PositionCelestialBody = GetCelestialBodyPosition(CelestialBody);
		FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);

		CelestialBodyArray[Index]->Update(PositionCelestialBody, CelestialBodyRotation);

		Index++;
	}
}

void USceneData::UpdateSpacecraft() const
{
	const cielimMessage::Spacecraft &SpacecraftMessage = CielimMessage.GetMessage().spacecraft();

	const FVector3d PositionSpacecraft = GetSpacecraftPosition(SpacecraftMessage);
	const FVector3d AttitudeVector =
		FVector3d(SpacecraftMessage.attitude(0), SpacecraftMessage.attitude(1), SpacecraftMessage.attitude(2));
	const FRotator SpacecraftRotation = GetRotatorFromMrp(AttitudeVector);

	this->Spacecraft->Update(PositionSpacecraft, SpacecraftRotation);

	// Update camera
	if (this->CielimMessage.GetMessage().has_camera())
	{
		const cielimMessage::CameraModel &Camera = CielimMessage.GetMessage().camera();

		const FRotator CameraRotation = GetCameraRotation(Camera);

		this->Spacecraft->UpdateCameraOrientation(CameraRotation);
	}
}

// ---------- Helper Function Definitions ----------

// Gets the positions of a Spacecraft Object
static FVector3d GetSpacecraftPosition(const cielimMessage::Spacecraft &Craft)
{
	const FVector3d PositionSpacecraft = FVector3d(Craft.position(0), Craft.position(1), Craft.position(2));
	return Right2LeftVector(PositionSpacecraft);
}

// Converts an MRP Vector (Sigma) into an Unreal Rotation Container (FRotator)
static FRotator GetRotatorFromMrp(const FVector3d &Sigma)
{
	const FQuat Q = MRPtoQuaternion(Sigma);
	const FQuat QLeftHand = RightQuat2LeftQuat(Q);
	return FRotator(QLeftHand);
}

// Gets the position of a Camera Object
static FVector3d GetCameraPosition(const cielimMessage::CameraModel &Camera)
{
	const FVector3d SigmaCamera =
		FVector3d(Camera.camerapositioninbody(0), Camera.camerapositioninbody(1), Camera.camerapositioninbody(2));
	return Right2LeftVector(SigmaCamera);
}

// Gets the rotation of a Camera Object
static FRotator GetCameraRotation(const cielimMessage::CameraModel &Camera)
{
	// Map basilisk right-handed camera orientation to unreal left-handed camera orientation
	const FVector3d SigmaCB =
		FVector3d(Camera.bodyframetocameramrp(0), Camera.bodyframetocameramrp(1), Camera.bodyframetocameramrp(2));
	const FQuat Quat_CB = MRPtoQuaternion(SigmaCB);
	const FQuat Quat_B_B0 = FQuat(0.5, -0.5, 0.5, 0.5);
	const FQuat Quat_CB0 = Quat_CB * Quat_B_B0;
	return FRotator(RightQuat2LeftQuat(Quat_CB0));
}

// Gets the positions of a CelestialBody Object
static FVector3d GetCelestialBodyPosition(const cielimMessage::CelestialBody &CelestialBody)
{
	const FVector3d PositionCelestialBody =
		FVector3d(CelestialBody.position(0), CelestialBody.position(1), CelestialBody.position(2));
	return Right2LeftVector(PositionCelestialBody);
}

// Gets the rotation of a CelestialBody object
static FRotator GetCelestialBodyRotation(const cielimMessage::CelestialBody &CelestialBody)
{
	// Create CelestialBody Rotation Quat
	const FVector Rotation1 =
		FVector4d(CelestialBody.attitude(0), CelestialBody.attitude(1), CelestialBody.attitude(2), 0);
	const FVector Rotation2 =
		FVector4d(CelestialBody.attitude(3), CelestialBody.attitude(4), CelestialBody.attitude(5), 0);
	const FVector Rotation3 =
		FVector4d(CelestialBody.attitude(6), CelestialBody.attitude(7), CelestialBody.attitude(8), 0);
	const FVector Rotation4 = FVector4d(0, 0, 0, 1);
	const FMatrix Mat = FMatrix(Rotation1, Rotation2, Rotation3, Rotation4);
	const FQuat Q = FQuat(Mat);
	// Get FRotator
	const FQuat QLeftHand = RightQuat2LeftQuat(Q);
	return FRotator(QLeftHand);
}
