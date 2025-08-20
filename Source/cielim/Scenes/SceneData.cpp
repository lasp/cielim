//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of USceneData.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "SceneData.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/LightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/DirectionalLight.h"
#include "Engine/World.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Math/UnrealMathUtility.h"

#include "../Actors/CelestialBodyMeshModel.h"
#include "../CielimGameInstance.h"
#include "../Utilities/Logging/CielimLoggingMacros.h"
#include "../Utilities/Math/KinematicsUtilities.h"

const FString SunNaifBodyName("sun");

static FVector3d GetSpacecraftPosition(const cielimMessage::Spacecraft &Craft);
static FRotator GetRotatorFromMrp(const FVector3d &Sigma);
static FVector3d GetCameraPosition(const cielimMessage::CameraModel &Camera);
static FRotator GetCameraRotation(const cielimMessage::CameraModel &Camera);
static FVector3d GetCelestialBodyPosition(const cielimMessage::CelestialBody &CelestialBody);
static FRotator GetCelestialBodyRotation(const cielimMessage::CelestialBody &CelestialBody);

void USceneData::Init()
{
	this->CielimMessage = MakeShared<cielimMessage::CielimMessage>();

	ActiveSunLightMPC = Cast<UMaterialParameterCollection>(
		StaticLoadObject(UMaterialParameterCollection::StaticClass(), nullptr,
						 TEXT("/Game/AsteroidMeshes/MPC_ActiveSunLight.MPC_ActiveSunLight")));

	if (!ActiveSunLightMPC)
		UE_LOG(LogCielim, Error, TEXT("Sunlight parameter collection could not be located."));
}


// This is a mad hack and needs to be changed
void USceneData::ParseCommand(const TSharedPtr<FCircularQueueData> &CommandData,
							  const TSharedPtr<FCircularQueueData> &ReturnData)
{
	this->bShouldUpdateScene = false;

	// This code should be turned into some kind of handler function registration
	// a bit like an RPC or http server
	if (CommandData->query == CommandType::INIT_SCENE)
	{
		UE_LOG(LogCielim, Display, TEXT("Initiating new scene: ASimulationDataSourceActor"));

		// Clear existing objects

		this->Actors.Reset();

		if (this->Spacecraft != nullptr)
			this->Spacecraft->CameraModel->SceneCaptureComponent2D->ShowOnlyActors.Reset();

		for (auto const CelestialBody : this->CelestialBodyArray)
		{
			if (CelestialBody != nullptr)
				CelestialBody->Destroy();
		}

		this->CelestialBodyArray.Reset();

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

		this->bIsCelestialBodiesSpawned = false;
		this->bIsSpacecraftSpawned = false;
		this->bIsSceneEstablished = false;
	}
	else if (CommandData->query == CommandType::SIM_UPDATE)
	{
		UE_LOG(LogCielim, Display, TEXT("Reading sim update data: ASimulationDataSourceActor"));

		if (const auto *TempPayload = CommandData->payload.TryGet<FUpdatePayload>())
		{
			const auto LocalMessage = TempPayload->message;
			this->CielimMessage = LocalMessage;
		}

		if (!this->bIsSceneEstablished)
		{
			this->bIsSceneEstablished = true;

			UE_LOG(LogCielim, Display, TEXT("Initialize scene..."));

			this->SpawnCelestialBodies();
			this->SpawnSpacecraft();
			this->SpawnSunLight();

			constexpr auto RenderMode = ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;

			this->Spacecraft->CameraModel->SceneCaptureComponent2D->PrimitiveRenderMode = RenderMode;
			this->Spacecraft->CameraModel->SceneCaptureComponent2D->ShowOnlyActors = Actors;
		}
		else
		{
			this->bShouldUpdateScene = true;
		}
	}
	else if (CommandData->query == CommandType::REQUEST_IMAGE)
	{
		if (!this->bIsSceneEstablished)
		{
			UE_LOG(LogCielim, Warning, TEXT("Scene not initialized: ASimulationDataSourceActor"));
			return;
		}

		if (auto *Instance = GetWorld()->GetParameterCollectionInstance(ActiveSunLightMPC); Instance != nullptr)
		{
			const FName ParamName = FName("SunDirection");
			Instance->SetVectorParameterValue(ParamName, this->SunLight->GetActorForwardVector().GetSafeNormal());
		}

		TArray64<uint8> ImageDataPng;
		TOptional<FVector2D> CobCoords;

		ACameraModel *Camera = this->Spacecraft->CameraModel;

		if (const auto *TempPayload = CommandData->payload.TryGet<FImagePayload>();
			TempPayload != nullptr && TempPayload->shouldReturnImage)
		{
			Camera->GetImageData(ImageDataPng, CobCoords);
		}
		else
		{
			Camera->GetImageData(CobCoords);
		}

		ReturnData->query = CommandType::REQUEST_IMAGE;
		ReturnData->payload.Emplace<FImagePayload>(FImagePayload());
		ReturnData->payload.Get<FImagePayload>().image_data = ImageDataPng;
		ReturnData->payload.Get<FImagePayload>().centerOfBrightness = CobCoords;

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

	if (this->CielimMessage->has_spacecraft() && this->bIsSpacecraftSpawned)
	{
		this->UpdateSpacecraft();
	}

	if (!this->CielimMessage->celestialbodies().empty() && this->bIsCelestialBodiesSpawned)
	{
		this->UpdateCelestialBodies();
	}
}

void USceneData::SpawnCelestialBodies()
{
	for (const auto &CelestialBody : CielimMessage->celestialbodies())
	{
		const FVector3d CelestialBodyPosition = GetCelestialBodyPosition(CelestialBody);
		const FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);

		ACelestialBody *TempCelestialBody =
			GetWorld()->SpawnActor<ACelestialBody>(CelestialBodyPosition, CelestialBodyRotation);
		TempCelestialBody->Name = FString(CelestialBody.bodyname().c_str());

#if WITH_EDITOR
		TempCelestialBody->SetActorLabel(TempCelestialBody->Name);
#endif

		if (CelestialBody.has_model())
		{
			UE_LOG(LogCielim, Display, TEXT("Loading mesh model for %s"), *TempCelestialBody->Name);

			FCelestialBodyMeshModel MeshModel;

			MeshModel = FCelestialBodyMeshModel::FromProtobuf(CelestialBody.model());
			TempCelestialBody->LoadMesh(MeshModel);
		}

		// Meshes are ~1,000 units in radius so we need to scale down to normalize to 1-meter radius (1 unit = 1 meter)
		constexpr float MeshNormFactor = 1.0f / 1000.0f;
		const float RadiusScale = CelestialBody.model().meanradius();
		const FVector ActorScale = TempCelestialBody->GetPrincipleAxisDistortions() * RadiusScale * MeshNormFactor;

		TempCelestialBody->SetActorScale3D(ActorScale);

		this->CelestialBodyArray.Add(TempCelestialBody);
		this->Actors.Add(TempCelestialBody);

		if (TempCelestialBody->Name.ToLower() == SunNaifBodyName)
		{
			this->SunCelestialBody = TempCelestialBody;
		}
	}

	this->bIsCelestialBodiesSpawned = true;
}

void USceneData::SpawnSpacecraft()
{
	const cielimMessage::Spacecraft &SpacecraftMessage = this->CielimMessage->spacecraft();

	const FVector3d PositionSpacecraft = GetSpacecraftPosition(SpacecraftMessage);

	const double AttitudeX = SpacecraftMessage.attitude(0);
	const double AttitudeY = SpacecraftMessage.attitude(1);
	const double AttitudeZ = SpacecraftMessage.attitude(2);

	const FVector3d AttitudeVector = FVector3d(AttitudeX, AttitudeY, AttitudeZ);
	const FRotator SpacecraftRotation = GetRotatorFromMrp(AttitudeVector);

	ASpacecraft *TempSpacecraft = GetWorld()->SpawnActor<ASpacecraft>(PositionSpacecraft, SpacecraftRotation);

	TempSpacecraft->Name = FString(SpacecraftMessage.spacecraftname().c_str());

	// Set camera
	if (this->CielimMessage->has_camera())
	{
		const cielimMessage::CameraModel &Camera = CielimMessage->camera();

		TempSpacecraft->SetFOV(FMath::RadiansToDegrees(Camera.fieldofview(0)),
							   FMath::RadiansToDegrees(Camera.fieldofview(1)));
		TempSpacecraft->SetResolution(Camera.resolution(0), Camera.resolution(1));

		const FVector3d CameraPosition = GetCameraPosition(Camera);
		TempSpacecraft->SetCameraRelativePosition(CameraPosition);

		const FRotator CameraRotation = GetCameraRotation(Camera);
		TempSpacecraft->SetCameraRelativeOrientation(CameraRotation);

		TempSpacecraft->CameraModel->SetCameraParameters(Camera);

		this->bHasCameras = true;
	}

	this->Spacecraft = TempSpacecraft;
	this->Actors.Add(TempSpacecraft);
	this->bIsSpacecraftSpawned = true;
}

void USceneData::SpawnSunLight()
{
	const FVector3d SunLocation = this->SunCelestialBody->GetActorLocation();

	const FVector SunDirection = -SunLocation.GetSafeNormal();
	const FRotator SunRotation = FRotationMatrix::MakeFromX(SunDirection).Rotator();

	this->SunLight = GetWorld()->SpawnActor<ADirectionalLight>();

	ULightComponent *LightComp = this->SunLight->GetLightComponent();

	LightComp->SetMobility(EComponentMobility::Movable);
	LightComp->SetWorldLocation(SunLocation);
	LightComp->SetWorldRotation(SunRotation);

	// Spectral irradiance in W/m^2/nm and data from: https://lasp.colorado.edu/tsis/data/ssi-data/#summary_table

	constexpr float RedIrradianceAtOneAU = 1.55f; // 650 nm wavelength
	constexpr float GreenIrradianceAtOneAU = 1.89f; // 550 nm wavelength
	constexpr float BlueIrradianceAtOneAU = 2.06f; // 450 nm wavelength

	/* We need to scale down the irradiance values so they can fit in [0,1] color and not be clamped. This will get
	 * cancelled out when the color is multiplied with the intensity which has the inverse of the factor. */
	constexpr float IntensityScaleFactor = 2.2f;

	constexpr float RedIntensity = RedIrradianceAtOneAU / IntensityScaleFactor;
	constexpr float GreenIntensity = GreenIrradianceAtOneAU / IntensityScaleFactor;
	constexpr float BlueIntensity = BlueIrradianceAtOneAU / IntensityScaleFactor;

	// Length of 1 AU in meters
	constexpr float OneAU = 1.496e11;

	/* The calculations determining the irradiance of the sun for each wavelength assumes all lit objects are
	 * near the origin. Anything further than ~0.1 AU from the origin will have irradiance too high/low from expected.
	 * This is because directional light intensity is constant regardless of position. */
	const float SunDistanceRatio = OneAU / SunLocation.Length();
	const float SunIntensity = SunDistanceRatio * SunDistanceRatio * IntensityScaleFactor;

	LightComp->SetIntensity(SunIntensity);
	LightComp->SetLightColor(FLinearColor(RedIntensity, GreenIntensity, BlueIntensity));

	if (UDirectionalLightComponent *DirectionalLightComp = Cast<UDirectionalLightComponent>(LightComp))
	{
		// Allow shadow maps to be seen from much further away
		DirectionalLightComp->DynamicShadowDistanceMovableLight = 10000000.0f;
		DirectionalLightComp->DistanceFieldShadowDistance = 100000000.0f;
		DirectionalLightComp->TraceDistance = 20000.0f;
	}

	// Light should spawn as disabled so SceneManager can manage which scene's light is enabled
	ToggleSunLight(false);

	this->Actors.Add(SunLight);
}

void USceneData::UpdateCelestialBodies() const
{
	int Index = 0;
	for (const auto &CelestialBody : CielimMessage->celestialbodies())
	{
		FVector3d PositionCelestialBody = GetCelestialBodyPosition(CelestialBody);
		FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);

		CelestialBodyArray[Index]->Update(PositionCelestialBody, CelestialBodyRotation);

		Index++;
	}
}

void USceneData::UpdateSpacecraft() const
{
	const cielimMessage::Spacecraft &SpacecraftMessage = CielimMessage->spacecraft();

	const FVector3d PositionSpacecraft = GetSpacecraftPosition(SpacecraftMessage);
	const FVector3d AttitudeVector =
		FVector3d(SpacecraftMessage.attitude(0), SpacecraftMessage.attitude(1), SpacecraftMessage.attitude(2));
	const FRotator SpacecraftRotation = GetRotatorFromMrp(AttitudeVector);

	this->Spacecraft->Update(PositionSpacecraft, SpacecraftRotation);

	// Update camera
	if (this->CielimMessage->has_camera())
	{
		const cielimMessage::CameraModel &Camera = CielimMessage->camera();

		const FRotator CameraRotation = GetCameraRotation(Camera);

		this->Spacecraft->SetCameraRelativeOrientation(CameraRotation);

		this->Spacecraft->CameraModel->SetCameraParameters(Camera);
	}
}

bool USceneData::IsSceneEstablished() const { return this->bIsSceneEstablished; }

bool USceneData::IsSunLightOn() const { return this->SunLight->GetLightComponent()->IsVisible(); }

void USceneData::ToggleSunLight(const bool Toggle) const { this->SunLight->GetLightComponent()->SetVisibility(Toggle); }

void USceneData::BeginDestroy()
{
	for (auto const Actor : this->Actors)
	{
		if (Actor != nullptr)
			Actor->Destroy();
	}

	this->Actors.Empty();

	Super::BeginDestroy();
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
