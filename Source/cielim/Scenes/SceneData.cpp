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

			this->SpawnSpacecraft();
			this->SpawnCelestialBodies();

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

		ReturnData->query = CommandType::REQUEST_IMAGE;
		ReturnData->payload.Emplace<FImageResponsePayload>(FImageResponsePayload());

		if (const auto *TempPayload = CommandData->payload.TryGet<FImageRequestPayload>(); TempPayload != nullptr)
		{
			FImageResponsePayload *ReturnPayload = ReturnData->payload.TryGet<FImageResponsePayload>();
			ACameraModel *Camera = this->Spacecraft->CameraModel;

			if (TempPayload->bShouldReturnImage)
			{
				Camera->GetImageData(ReturnPayload->ImageData);
				UE_LOG(LogCielim, Display, TEXT("Put back PNG image: ASimulationDataSourceActor"));
			}

			if (TempPayload->bShouldReturnDiagnostics)
			{
				Camera->GetDiagnosticData(*ReturnPayload->Diagnostics);
				UE_LOG(LogCielim, Display, TEXT("Put back diagnostics data: ASimulationDataSourceActor"));
			}
		}
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

		if (Camera.has_lensmodel())
		{
			const cielimMessage::LensModel &LensModel = Camera.lensmodel();

			TempSpacecraft->SetFOV(FMath::RadiansToDegrees(LensModel.fieldofview(0)),
								   FMath::RadiansToDegrees(LensModel.fieldofview(1)));
		}

		if (Camera.has_sensormodel())
		{
			const cielimMessage::SensorModel &SensorModel = Camera.sensormodel();

			TempSpacecraft->SetResolution(SensorModel.resolution(0), SensorModel.resolution(1));
		}


		const FVector3d CameraPosition = GetCameraPosition(Camera);
		TempSpacecraft->SetCameraRelativePosition(CameraPosition);

		const FRotator CameraRotation = GetCameraRotation(Camera);
		TempSpacecraft->SetCameraRelativeOrientation(CameraRotation);

		TempSpacecraft->CameraModel->SetCameraParameters(*this->CielimMessage);

		this->bHasCameras = true;
	}

	this->Spacecraft = TempSpacecraft;
	this->Actors.Add(TempSpacecraft);
	this->bIsSpacecraftSpawned = true;
}

void USceneData::SpawnCelestialBodies()
{
	for (const auto &CelestialBody : this->CielimMessage->celestialbodies())
	{
		ACelestialBody *TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>();

		const FVector CelestialBodyPosition = GetCelestialBodyPosition(CelestialBody);
		const FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);

		TempCelestialBody->SetActorLocation(CelestialBodyPosition);
		TempCelestialBody->SetActorRotation(CelestialBodyRotation);

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

			const float CelestialBodyRadius = CelestialBody.model().meanradius();
			const float CelestialBodyAlbedo = CelestialBody.model().geometricalbedo();

			// Meshes are ~1,000 units radius so we must scale down to normalize to 1 unit radius (1 unit = 1 meter)
			constexpr float MeshNormFactor = 1.0f / 1000.0f;
			const float RadiusScale = CelestialBodyRadius;
			const FVector ActorScale = TempCelestialBody->GetPrincipleAxisDistortions() * RadiusScale * MeshNormFactor;

			if (ActorScale.X > 0.0f && ActorScale.Y > 0.0f && ActorScale.Z > 0.0f)
				TempCelestialBody->SetActorScale3D(ActorScale);
			else
				UE_LOG(LogCielim, Warning, TEXT("Actor scale was invalid (<= 0), default is being used instead."));

			// If object is renderable, check whether it should be rendered as normal or distant object
			if (this->Spacecraft->CameraModel->IsCelestialBodyResolvable(*TempCelestialBody))
			{
				// Don't render with regular pipeline if sub-pixel
				TempCelestialBody->SetActorHiddenInGame(true);

				const FVector3f DistantObjectPosition =
					FVector3f(CelestialBodyPosition.X, CelestialBodyPosition.Y, CelestialBodyPosition.Z);

				FDistantObject NewObject{DistantObjectPosition, CelestialBodyRadius, CelestialBodyAlbedo};

				this->Spacecraft->CameraModel->DistantObjects.Add(NewObject);
			}
		}

		this->CelestialBodyArray.Add(TempCelestialBody);
		this->Actors.Add(TempCelestialBody);

		if (TempCelestialBody->Name.ToLower() == SunNaifBodyName)
		{
			this->SunCelestialBody = TempCelestialBody;

			// Spawn sun direction light

			this->SunLight = GetWorld()->SpawnActor<ADirectionalLight>();

			this->SunLight->SetMobility(EComponentMobility::Movable);

			this->SunLight->AttachToActor(this->SunCelestialBody, FAttachmentTransformRules::KeepRelativeTransform);
			this->SunLight->SetActorRelativeLocation(FVector::ZeroVector);
			this->SunLight->SetActorRelativeRotation(FRotator::ZeroRotator);

			ULightComponent *LightComp = this->SunLight->GetLightComponent();

			LightComp->SetMobility(EComponentMobility::Movable);

			if (UDirectionalLightComponent *DirectionalLightComp = Cast<UDirectionalLightComponent>(LightComp))
			{
				// Allow shadow maps to be seen from much further away
				DirectionalLightComp->DynamicShadowDistanceMovableLight = 10000000.0f;
				DirectionalLightComp->DistanceFieldShadowDistance = 100000000.0f;
				DirectionalLightComp->TraceDistance = 20000.0f;
			}

			UpdateSunLight();

			// Light should spawn as disabled so SceneManager can manage which scene's light is enabled
			ToggleSunLight(false);

			this->Actors.Add(SunLight);
		}
	}

	this->bIsCelestialBodiesSpawned = true;
}

void USceneData::UpdateSunLight() const
{
	const FVector3d SunLocation = this->SunLight->GetActorLocation();

	const FVector SunDirection = -SunLocation.GetSafeNormal();
	const FRotator SunRotation = FRotationMatrix::MakeFromX(SunDirection).Rotator();

	ULightComponent *LightComp = this->SunLight->GetLightComponent();

	LightComp->SetWorldRotation(SunRotation);

	float Wavelength1 = 650 * 1e-9f;
	float Wavelength2 = 550 * 1e-9f;
	float Wavelength3 = 450 * 1e-9f;

	// Check if custom wavelengths are specified in the camera model, else use visible spectrum defaults

	if (this->CielimMessage->has_renderparameters())
	{
		const auto RenderParams = this->CielimMessage->renderparameters();

		Wavelength1 = RenderParams.wavelength1() * 1e-9f;
		Wavelength2 = RenderParams.wavelength2() * 1e-9f;
		Wavelength3 = RenderParams.wavelength3() * 1e-9f;

		if (Wavelength2 != (Wavelength1 + Wavelength3) / 2.0f)
			UE_LOG(LogCielim, Warning, TEXT("W2 is not equal to (W1 + W3) / 2; QE approximation will be inaccurate."));
	}

	// Use Planck's law to calculate solar irradiance at specified wavelengths (assuming sun is ideal blackbody)

	constexpr float SunRadius = 6.957e8f; // Meters
	constexpr float SunTemperature = 5778.0f; // Kelvin
	constexpr float RadiationConstant1 = 1.191e-16f; // W * Meters^2
	constexpr float RadiationConstant2 = 1.439e-2f; // Meters * K

	const float Wavelength1Radiance = 1e-9 * RadiationConstant1 /
		(FMath::Pow(Wavelength1, 5) * (FMath::Exp(RadiationConstant2 / (Wavelength1 * SunTemperature)) - 1.0f));

	const float Wavelength2Radiance = 1e-9 * RadiationConstant1 /
		(FMath::Pow(Wavelength2, 5) * (FMath::Exp(RadiationConstant2 / (Wavelength2 * SunTemperature)) - 1.0f));

	const float Wavelength3Radiance = 1e-9 * RadiationConstant1 /
		(FMath::Pow(Wavelength3, 5) * (FMath::Exp(RadiationConstant2 / (Wavelength3 * SunTemperature)) - 1.0f));

	const float Distance = SunLocation.Length(); // Meters
	const float SunSolidAngle = 3.1415f * SunRadius * SunRadius / (Distance * Distance); // Steradians

	const float Wavelength1Irradiance = Wavelength1Radiance * SunSolidAngle; // W * Meters^-2 * Nanometer^-1
	const float Wavelength2Irradiance = Wavelength2Radiance * SunSolidAngle; // W * Meters^-2 * Nanometer^-1
	const float Wavelength3Irradiance = Wavelength3Radiance * SunSolidAngle; // W * Meters^-2 * Nanometer^-1

	// The camera needs this for distant object rendering
	this->Spacecraft->CameraModel->SolarSpectralIrradiance =
		FVector3f(Wavelength1Irradiance, Wavelength2Irradiance, Wavelength3Irradiance);

	/* We need to scale down the irradiance values so they can fit in [0,1] color and not be clamped. This will get
	 * canceled out when the color is multiplied with the intensity which is the inverse of the factor. */
	const float SunIntensity = FMath::Max(Wavelength1Irradiance, Wavelength2Irradiance, Wavelength3Irradiance) * 1.1f;

	const float RedIntensity = Wavelength1Irradiance / SunIntensity;
	const float GreenIntensity = Wavelength2Irradiance / SunIntensity;
	const float BlueIntensity = Wavelength3Irradiance / SunIntensity;

	/* The calculations determining the irradiance of the sun for each wavelength assumes all lit objects are
	 * near the origin. Anything further than ~0.1 AU from the origin will have irradiance too high/low from expected.
	 * This is because directional light intensity is constant regardless of position. */

	LightComp->SetIntensity(SunIntensity);
	LightComp->SetLightColor(FLinearColor(RedIntensity, GreenIntensity, BlueIntensity));
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

		this->Spacecraft->CameraModel->SetCameraParameters(*this->CielimMessage);
	}
}

void USceneData::UpdateCelestialBodies() const
{
	/* Reset distant objects buffer
	 * TODO: We need a better approach with unique ID indexing at some point so we don't have to rebuild every update */
	this->Spacecraft->CameraModel->DistantObjects.Reset();

	int Index = 0;
	const int MaxIndex = this->CelestialBodyArray.Num();

	for (const auto &CelestialBody : CielimMessage->celestialbodies())
	{
		if (Index >= MaxIndex)
			break;

		const FVector CelestialBodyPosition = GetCelestialBodyPosition(CelestialBody);
		const FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);

		/* This assumes that the ordering of the celestial bodies doesn't change in the message. If this assumption
		 * is not true, bodies will be updated erroneously. TODO: Fix this at some point. */
		ACelestialBody *TempCelestialBody = CelestialBodyArray[Index];

		TempCelestialBody->Update(CelestialBodyPosition, CelestialBodyRotation);

		if (CelestialBody.has_model())
		{
			// If object is renderable, check whether it should be rendered as normal or distant object
			if (this->Spacecraft->CameraModel->IsCelestialBodyResolvable(*TempCelestialBody))
			{
				// Don't render with regular pipeline if sub-pixel
				TempCelestialBody->SetActorHiddenInGame(true);

				const FVector3f DistantObjectPosition =
					FVector3f(CelestialBodyPosition.X, CelestialBodyPosition.Y, CelestialBodyPosition.Z);
				const float CelestialBodyRadius = CelestialBody.model().meanradius();
				const float CelestialBodyAlbedo = CelestialBody.model().geometricalbedo();

				FDistantObject NewObject{DistantObjectPosition, CelestialBodyRadius, CelestialBodyAlbedo};

				this->Spacecraft->CameraModel->DistantObjects.Add(NewObject);
			}
			else
				TempCelestialBody->SetActorHiddenInGame(false);
		}

		if (TempCelestialBody->Name.ToLower() == SunNaifBodyName)
			UpdateSunLight();

		Index++;
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
