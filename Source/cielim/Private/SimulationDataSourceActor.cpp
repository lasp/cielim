// Fill out your copyright notice in the Description page of Project Settings.

#include "SimulationDataSourceActor.h"

#include "CielimLoggingMacros.h"
#include "KinematicsUtilities.h"
#include "ProtobufFileReader.h"
#include "ZmqConnection/Commands.h"
#include "ZmqConnection/ZmqMultiThreadActor.h"
#include "Engine/World.h"
#include <zmq.hpp>


/**
 * @brief GetRotatorFromMrp(Sigma) Converts an MRP into an Unreal Rotation Container (FRotator) 
 * 
 * @param Sigma The MRP vector
 * @return FRotator Unreal Rotation Container
 */
FRotator GetRotatorFromMrp(const FVector3d &Sigma)
{
	const FQuat Q = MRPtoQuaternion(Sigma);
	const FQuat QLeftHand = RightQuat2LeftQuat(Q);
	return FRotator(QLeftHand);
}

/**
 * @brief GetSpacecraftPosition(Spacecraft) Gets the positions of a Spacecraft Object
 * @param Spacecraft A Spacecraft Object
 * @return FVector3d Spacecraft's position
 */
FVector3d GetSpacecraftPosition(const vizProtobufferMessage::VizMessage_Spacecraft &Craft)
{
	const FVector3d PositionSpacecraft = FVector3d(Craft.position(0),
	                                               Craft.position(1),
	                                               Craft.position(2));
	return Right2LeftVector(PositionSpacecraft);
}

/**
 * @brief GetCameraPosition(Camera) Gets the position of a Camera Object
 * @param Camera A Camera Object
 * @return FVector3d Camera's position
 */
FVector3d GetCameraPosition(const vizProtobufferMessage::VizMessage_CameraConfig &Camera)
{
	const FVector3d SigmaCamera = FVector3d(Camera.camerapos_b(0),
	                                        Camera.camerapos_b(1),
	                                        Camera.camerapos_b(2));
	return Right2LeftVector(SigmaCamera);
}

/**
 * @brief GetCameraRotation(Camera) Gets the rotation of a Camera Object
 * @param Camera A Camera Object
 * @return FRotator Camera's Rotation
 */
FRotator GetCameraRotation(const vizProtobufferMessage::VizMessage_CameraConfig &Camera)
{
	// Map basilisk right-handed camera orientation to unreal left-handed camera orientation
	const FVector3d SigmaCB = FVector3d(Camera.cameradir_b(0), Camera.cameradir_b(1), Camera.cameradir_b(2));
	const FQuat Q = MRPtoQuaternion(SigmaCB);
	const FQuat QTemp = MRPtoQuaternion(FVector3d(-1. / 3, -1. / 3, 1. / 3));
	// Temporary correction for Basilisk output CrCu (r unreal u basilisk)
	const FQuat QCorrection = FQuat(0.5, -0.5, 0.5, 0.5);
	const FVector3d SigmaCorrection = QuaterniontoMRP(Q * QCorrection * QTemp);
	return GetRotatorFromMrp(SigmaCorrection);
}


// Sets default values
ASimulationDataSourceActor::ASimulationDataSourceActor()
{
	PrimaryActorTick.bCanEverTick = true;
}

// Called when the game starts or when spawned
void ASimulationDataSourceActor::BeginPlay()
{
	Super::BeginPlay();
	
	if(FString CommAddress; FParse::Value(FCommandLine::Get(), TEXT("directComm"), CommAddress))
	{
	    UE_LOG(LogCielim, Display, TEXT("Parsed command line parameter (directComm) : %s"), *CommAddress);
		this->DataSource = DataSourceType::Network;
		FVector Location(0.0f, 0.0f, 0.0f);
		FRotator Rotation(0.0f, 0.0f, 0.0f);
		FActorSpawnParameters SpawnInfo;
		this->NetworkSimulationDataSource = std::unique_ptr<AZmqMultiThreadActor>(
		GetWorld()->SpawnActor<AZmqMultiThreadActor>(Location, Rotation, SpawnInfo));
		this->NetworkSimulationDataSource->ConnectionAddress = std::string(TCHAR_TO_UTF8(*CommAddress));
	} else if(FString SimulationDataFile;
		FParse::Value(FCommandLine::Get(), TEXT("simulationDataFile"), SimulationDataFile)) {
	    UE_LOG(LogCielim, Display, TEXT("Parsed command line parameter (simulationDataFile) : %s"), *SimulationDataFile);
		this->DataSource = DataSourceType::File;
	    this->SimulationDataSource = std::make_unique<ProtobufFileReader>(std::string(TCHAR_TO_UTF8(*SimulationDataFile)));
	    this->Vizmessage = this->SimulationDataSource->GetNextSimulationData();
	} else {
		UE_LOG(LogCielim, Warning, TEXT("Did not receive start up mode from command line parameter"));
		UE_LOG(LogCielim, Display, TEXT("Defaulted to (simulationDataFile) : %hs"), "protofile_proxOps.bin");
		this->DataSource = DataSourceType::File;
		this->SimulationDataSource = std::make_unique<ProtobufFileReader>("protofile_proxOps.bin");
		this->Vizmessage = this->SimulationDataSource->GetNextSimulationData();
	}
	
	int major;
	int minor;
	int patch;
	zmq::version(&major, &minor, &patch);
	UE_LOG(LogCielim, Display, TEXT("ZeroMQ version: v%d.%d.%d"), major, minor, patch);
}

void ASimulationDataSourceActor::FileReaderTick(float DeltaTime)
{
	this->Vizmessage = this->SimulationDataSource->GetNextSimulationData();
	if (!this->IsSceneEstablished) {
		UE_LOG(LogCielim, Display, TEXT("Initialize scene..."));
		this->IsSceneEstablished = true;
		this->SpawnCelestialBodies();
		this->SpawnSpacecraft();
		if (this->Vizmessage.cameras().size() > 0)
		{
			this->bHasCameras = true;
			this->SpawnCaptureManager();
		}
		if (!BpCelestialBody || !BpSpacecraft)
		{
			UE_LOG(LogCielim, Warning, TEXT("Defualt BluePrint Classes have not been set in BP_ProtobufActor"));
		}
	}
}

// This is a mad hack and needs to be changed
void ASimulationDataSourceActor::NetworkTick(float DeltaTime)
{
	const auto QueueData = this->NetworkSimulationDataSource->GetQueueData();
	if (!QueueData.has_value())
	{
		return;
	}
	
	if (!this->IsSceneEstablished) {
		if (std::holds_alternative<SimUpdate>(QueueData.value().Query)) {
			UE_LOG(LogCielim, Display, TEXT("Initialize scene..."));
			this->Vizmessage = std::get<SimUpdate>(QueueData.value().Query).payload;
			this->IsSceneEstablished = true;
			this->SpawnCelestialBodies();
			this->SpawnSpacecraft();
			if (this->Vizmessage.cameras().size() > 0)
			{
				this->bHasCameras = true;
				this->SpawnCaptureManager();
			}
			if (!BpCelestialBody || !BpSpacecraft)
			{
				UE_LOG(LogCielim, Warning, TEXT("Defualt BluePrint Classes have not been set in BP_ProtobufActor"));
				return;
			}
		} else {
			UE_LOG(LogCielim, Warning, TEXT("Scene not initialized: ASimulationDataSourceActor"));
			return;
		}
	} 

	// This code should be turned into some kind of handler function registration
	// a bit like a RPC or http server
	if (std::holds_alternative<SimUpdate>(QueueData.value().Query)) {
		this->Vizmessage = std::get<SimUpdate>(QueueData.value().Query).payload;
		UE_LOG(LogCielim, Display, TEXT("Reading sim update data: ASimulationDataSourceActor"));
	} else if (std::holds_alternative<RequestImage>(QueueData.value().Query)) {
		this->NetworkSimulationDataSource->PutImageQueueData(this->CaptureManager->GetPNG());
		UE_LOG(LogCielim, Display, TEXT("Put back PNG image: ASimulationDataSourceActor"));
	} else {
		UE_LOG(LogCielim, Display, TEXT("GetNextSimulationData received unrecognized Type"));
	}
}

// Called every frame
void ASimulationDataSourceActor::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	if (this->DataSource == DataSourceType::Network) {
		this->NetworkTick(DeltaTime);
	} else if (this->DataSource == DataSourceType::File) {
		this->FileReaderTick(DeltaTime);
	}

	if (!this->Vizmessage.spacecraft().empty() && this->IsSpacecraftSpawned) {
		this->UpdateSpacecraft();
	} if (!this->Vizmessage.celestialbodies().empty() && this->IsCelestialBodiesSpawned) {
		this->UpdateCelestialBodies();
	}
}

/**
 * @brief GetCelestialBodyPosition(CelestialBody) Gets the positions of a CelestialBody Object
 * @param CelestialBody A CelestialBody Object
 * @return FVector3d CelestialBody's position
 */
FVector3d GetCelestialBodyPosition(const vizProtobufferMessage::VizMessage_CelestialBody &CelestialBody)
{
	const FVector3d PositionCelestialBody = FVector3d(CelestialBody.position(0),
	                                                  CelestialBody.position(1),
	                                                  CelestialBody.position(2));
	return Right2LeftVector(PositionCelestialBody);
}

/**
 * @brief GetCelestialBodyRotation(CelestialBody) Gets the rotation of a CelestialBody object
 * 
 * @param CelestialBody A CelestialBody object
 * @return FRotator celestial body's rotation 
 */
FRotator GetCelestialBodyRotation(const vizProtobufferMessage::VizMessage_CelestialBody &CelestialBody)
{
	// Create CelestialBody Rotation Quat
	const FVector Rotation1 = FVector4d(CelestialBody.rotation(0),
	                                    CelestialBody.rotation(1),
	                                    CelestialBody.rotation(2),
	                                    0);
	const FVector Rotation2 = FVector4d(CelestialBody.rotation(3),
	                                    CelestialBody.rotation(4),
	                                    CelestialBody.rotation(5),
	                                    0);
	const FVector Rotation3 = FVector4d(CelestialBody.rotation(6),
	                                    CelestialBody.rotation(7),
	                                    CelestialBody.rotation(8),
	                                    0);
	const FVector Rotation4 = FVector4d(0, 0, 0, 1);
	const FMatrix Mat = FMatrix(Rotation1, Rotation2, Rotation3, Rotation4);
	const FQuat Q = FQuat(Mat);
	// Get FRotator 
	const FQuat QLeftHand = RightQuat2LeftQuat(Q);
	return FRotator(QLeftHand);
}

static bool IsAsteroid(const std::string& BodyName)
{
	return BodyName == "Justitia"
	|| BodyName == "Chimera"
	|| BodyName == "Westerwald"
	|| BodyName == "2010253"
	|| BodyName == "88055"
	|| BodyName == "59980"
	|| BodyName == "Rockox"
	|| BodyName == "Itokawa";
}

/**
 * @brief SpawnCelestialBodies() Spawns all celestial bodies from the VizMessage into the level
 * 
 */
void ASimulationDataSourceActor::SpawnCelestialBodies()
{
	for (const auto &CelestialBody : Vizmessage.celestialbodies()) {
		// Set Location 
		FVector3d PositionCelestialBody = GetCelestialBodyPosition(CelestialBody);
		// Set Rotation
		FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);
		// Create CelestialBody Actor instance
		ACelestialBody *TempCelestialBody;
		if (CelestialBody.bodyname() == "sun") {
			TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>(BpSun,
			                                                           PositionCelestialBody,
			                                                           CelestialBodyRotation);
		} else if (IsAsteroid(CelestialBody.bodyname())) {
			TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>(BpAsteroid,
			                                                           PositionCelestialBody,
			                                                           CelestialBodyRotation);
		} else {
			TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>(BpCelestialBody,
			                                                           PositionCelestialBody,
			                                                           CelestialBodyRotation);
		}
		FString CbName = FString(CelestialBody.bodyname().c_str());
		TempCelestialBody->Name = CbName;
		TempCelestialBody->SetRadiusEvent(CelestialBody.radiuseq());
		CelestialBodyArray.Add(TempCelestialBody);
		this->IsCelestialBodiesSpawned = true;
	}
}

/**
 * @brief SpawnSpacecraft() Spawns all spacecraft from the VizMessage into the level
 * 
 */
void ASimulationDataSourceActor::SpawnSpacecraft()
{
	const vizProtobufferMessage::VizMessage_Spacecraft &VizSpacecraft = Vizmessage.spacecraft(0);
	// Set Location 
	const FVector3d PositionSpacecraft = GetSpacecraftPosition(VizSpacecraft);
	// Set Rotation
	const FRotator SpacecraftRotation = GetRotatorFromMrp(
		FVector3d(VizSpacecraft.rotation(0),
			VizSpacecraft.rotation(1),
			VizSpacecraft.rotation(2)));
	FString ScName = FString(VizSpacecraft.spacecraftname().c_str());
	// Create Spacecraft Actor instance
	ASpacecraft *TempSc = GetWorld()->SpawnActor<ASpacecraft>(BpSpacecraft, PositionSpacecraft, SpacecraftRotation);
	TempSc->Name = ScName;
	// Set camera
	if (this->Vizmessage.cameras().size() > 0)
	{
		const vizProtobufferMessage::VizMessage_CameraConfig &Camera = Vizmessage.cameras(0);
		TempSc->SetFOV(Camera.fieldofview()); // Set camera settings
		TempSc->SetResolution(Camera.resolution(0), Camera.resolution(1));
		// Set camera location and orientation
		const FVector3d CameraPosition = GetCameraPosition(Camera);
		TempSc->SetCameraPosition(CameraPosition);
		const FRotator CameraRotation = GetCameraRotation(Camera);
		TempSc->UpdateCameraOrientation(CameraRotation);
	}
	this->Spacecraft = TempSc;
	this->IsSpacecraftSpawned = true;
}

void ASimulationDataSourceActor::SpawnCaptureManager()
{
	this->CaptureManager = GetWorld()->SpawnActor<ACaptureManager>();
	this->CaptureManager->SetSceneCaptureComponent(this->Spacecraft->SceneCaptureComponent2D);
	UE_LOG(LogCielim, Display, TEXT("Set Capture Texture Target"));
}

/**
 * @brief UpdateCelestialBodies() Updates all celestial body positions and rotations
 * 
 */
void ASimulationDataSourceActor::UpdateCelestialBodies() const
{
	int Index = 0;
	for (const auto &CelestialBody : Vizmessage.celestialbodies())
	{
		FVector3d PositionCelestialBody = GetCelestialBodyPosition(CelestialBody);
		FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);
		CelestialBodyArray[Index]->Update(PositionCelestialBody, CelestialBodyRotation);
		Index++;
	}
}

/**
 * @brief UpdateSpacecraft() Updates Spacecraft and camera positions and rotations 
 * 
 */
void ASimulationDataSourceActor::UpdateSpacecraft() const
{
	const vizProtobufferMessage::VizMessage_Spacecraft &VizSpacecraft = Vizmessage.spacecraft(0);
	const FVector3d PositionSpacecraft = GetSpacecraftPosition(VizSpacecraft);
	const FRotator SpacecraftRotation = GetRotatorFromMrp(
		FVector3d(VizSpacecraft.rotation(0),
			VizSpacecraft.rotation(1),
			VizSpacecraft.rotation(2)));
	this->Spacecraft->Update(PositionSpacecraft, SpacecraftRotation);
	// Update camera
	if (this->Vizmessage.cameras().size() > 0)
	{
		const vizProtobufferMessage::VizMessage_CameraConfig &Camera = Vizmessage.cameras(0);
		const FRotator CameraRotation = GetCameraRotation(Camera);
		this->Spacecraft->UpdateCameraOrientation(CameraRotation);
	}
}

/**
 * @brief DebugVizMessage() Prints VizMessage to the console
 * 
 */
void ASimulationDataSourceActor::DebugVizmessage() const
{
	const std::string DebugStr = this->Vizmessage.DebugString();
	UE_LOG(LogCielim, Display, TEXT("%hs"), DebugStr.c_str());
}
