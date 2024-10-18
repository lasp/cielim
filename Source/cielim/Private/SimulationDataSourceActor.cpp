// Fill out your copyright notice in the Description page of Project Settings.

#include "SimulationDataSourceActor.h"

#include "AstronomicalConstants.h"
#include "CielimLoggingMacros.h"
#include "KinematicsUtilities.h"
#include "ProtobufFileReader.h"
#include "ZmqConnection/Commands.h"
#include "ZmqConnection/ZmqMultiThreadActor.h"
#include "Engine/World.h"
#include "Math/UnrealMathUtility.h"
#include <zmq.hpp>
#include "Components/LightComponent.h"
#include "Engine/DirectionalLight.h"

#define m2cm 100.0
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
FVector3d GetSpacecraftPosition(const cielimMessage::Spacecraft &Craft)
{
	const FVector3d PositionSpacecraft = FVector3d(Craft.position(0),
	                                               Craft.position(1),
	                                               Craft.position(2))*m2cm;
	return Right2LeftVector(PositionSpacecraft);
}

/**
 * @brief GetCameraPosition(Camera) Gets the position of a Camera Object
 * @param Camera A Camera Object
 * @return FVector3d Camera's position
 */
FVector3d GetCameraPosition(const cielimMessage::CameraModel &Camera)
{
	const FVector3d SigmaCamera = FVector3d(Camera.camerapositioninbody(0),
	                                        Camera.camerapositioninbody(1),
	                                        Camera.camerapositioninbody(2))*m2cm;
	return Right2LeftVector(SigmaCamera);
}

/**
 * @brief GetCameraRotation(Camera) Gets the rotation of a Camera Object
 * @param Camera A Camera Object
 * @return FRotator Camera's Rotation
 */
FRotator GetCameraRotation(const cielimMessage::CameraModel &Camera)
{
	// Map basilisk right-handed camera orientation to unreal left-handed camera orientation
	const FVector3d SigmaCB = FVector3d(Camera.bodyframetocameramrp(0),
										Camera.bodyframetocameramrp(1),
										Camera.bodyframetocameramrp(2));
	const FQuat Quat_CB = MRPtoQuaternion(SigmaCB);
	const FQuat Quat_B_B0 = FQuat(0.5, -0.5, 0.5, 0.5);
	const FQuat Quat_CB0 = Quat_CB * Quat_B_B0;
	return FRotator(RightQuat2LeftQuat(Quat_CB0));
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
		this->NetworkSimulationDataSource = GetWorld()->SpawnActor<AZmqMultiThreadActor>(FVector::Zero(),FRotator::ZeroRotator);
		this->NetworkSimulationDataSource->Connect(std::string(TCHAR_TO_UTF8(*CommAddress)));
	} else if(FString SimulationDataFile;
		FParse::Value(FCommandLine::Get(), TEXT("simulationDataFile"), SimulationDataFile)) {
	    UE_LOG(LogCielim, Display, TEXT("Parsed command line parameter (simulationDataFile) : %s"), *SimulationDataFile);
		this->DataSource = DataSourceType::File;
	    this->SimulationDataSource = std::make_unique<ProtobufFileReader>(std::string(TCHAR_TO_UTF8(*SimulationDataFile)));
	} else {
		UE_LOG(LogCielim, Warning, TEXT("Did not receive start up mode from command line parameter"));
		UE_LOG(LogCielim, Display, TEXT("Defaulted to (simulationDataFile) : %hs"), "protofile_proxOps.bin");
		this->DataSource = DataSourceType::File;
		this->SimulationDataSource = std::make_unique<ProtobufFileReader>("protofile_proxOps.bin");
	}
	
	int major;
	int minor;
	int patch;
	zmq::version(&major, &minor, &patch);
	UE_LOG(LogCielim, Display, TEXT("ZeroMQ version: v%d.%d.%d"), major, minor, patch);
}

void ASimulationDataSourceActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{   
	this->SimulationDataSource.reset();
	google::protobuf::ShutdownProtobufLibrary();
	Super::EndPlay(EndPlayReason);
}

void ASimulationDataSourceActor::FileReaderTick(float DeltaTime)
{
	auto messageResult = this->SimulationDataSource->GetNextSimulationData();
	if (messageResult.has_value())
	{
		this->CielimMessage = messageResult.value();
		this->ShouldUpdateScene = true;
	}

	if (!this->IsSceneEstablished && this->ShouldUpdateScene) {

		UE_LOG(LogCielim, Display, TEXT("Initialize scene..."));
		this->IsSceneEstablished = true;
		this->SpawnCelestialBodies();
		this->SpawnSpacecraft();
		if (this->CielimMessage.has_camera())
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
			this->CielimMessage = std::get<SimUpdate>(QueueData.value().Query).payload;
			this->IsSceneEstablished = true;
			this->SpawnCelestialBodies();
			this->SpawnSpacecraft();
			if (this->CielimMessage.has_camera())
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
		this->CielimMessage = std::get<SimUpdate>(QueueData.value().Query).payload;
		this->ShouldUpdateScene = true;
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
	this->ShouldUpdateScene = false;
	if (this->DataSource == DataSourceType::Network) {
		this->NetworkTick(DeltaTime);
	} else if (this->DataSource == DataSourceType::File) {
		this->FileReaderTick(DeltaTime);
	}

	if (this->ShouldUpdateScene)
	{
		if (this->CielimMessage.has_spacecraft() && this->IsSpacecraftSpawned) {
			this->UpdateSpacecraft();
		} if (!this->CielimMessage.celestialbodies().empty() && this->IsCelestialBodiesSpawned) {
			this->UpdateCelestialBodies();
		}
	}
}

/**
 * @brief GetCelestialBodyPosition(CelestialBody) Gets the positions of a CelestialBody Object
 * @param CelestialBody A CelestialBody Object
 * @return FVector3d CelestialBody's position
 */
FVector3d GetCelestialBodyPosition(const cielimMessage::CelestialBody &CelestialBody)
{
	const FVector3d PositionCelestialBody = FVector3d(CelestialBody.position(0),
	                                                  CelestialBody.position(1),
	                                                  CelestialBody.position(2))*m2cm;
	return Right2LeftVector(PositionCelestialBody);
}

/**
 * @brief GetCelestialBodyRotation(CelestialBody) Gets the rotation of a CelestialBody object
 * 
 * @param CelestialBody A CelestialBody object
 * @return FRotator celestial body's rotation 
 */
FRotator GetCelestialBodyRotation(const cielimMessage::CelestialBody &CelestialBody)
{
	// Create CelestialBody Rotation Quat
	const FVector Rotation1 = FVector4d(CelestialBody.attitude(0),
	                                    CelestialBody.attitude(1),
	                                    CelestialBody.attitude(2),
	                                    0);
	const FVector Rotation2 = FVector4d(CelestialBody.attitude(3),
	                                    CelestialBody.attitude(4),
	                                    CelestialBody.attitude(5),
	                                    0);
	const FVector Rotation3 = FVector4d(CelestialBody.attitude(6),
	                                    CelestialBody.attitude(7),
	                                    CelestialBody.attitude(8),
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
	return BodyName == "2000269" //Justitia
	|| BodyName == "2000623" //Chimera
	|| BodyName == "2010253" //Westerwald
	|| BodyName == "2088055" //A4
	|| BodyName == "2059980" //A6
	|| BodyName == "2023871" //A5
	|| BodyName == "2013294" //Rockox
	|| BodyName == "asteroid_b612";
}

/**
 * @brief SpawnCelestialBodies() Spawns all celestial bodies from the VizMessage into the level
 * 
 */
void ASimulationDataSourceActor::SpawnCelestialBodies()
{
	for (const auto &CelestialBody : CielimMessage.celestialbodies()) {
		// Set Location 
		FVector3d PositionCelestialBody = GetCelestialBodyPosition(CelestialBody);
		// Set Rotation
		FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);
		// Create CelestialBody Actor instance
		ACelestialBody *TempCelestialBody;
		if (CelestialBody.bodyname() == "sun_planet_data") {
			TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>(BpSun,
			                                                           PositionCelestialBody,
			                                                           CelestialBodyRotation);
			this->SunCelestialBody = TempCelestialBody;
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
		TempCelestialBody->SetRadiusEvent(CelestialBody.models().meanradius());
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
	const cielimMessage::Spacecraft &SpacecraftMessage = this->CielimMessage.spacecraft();
	// Set Location 
	const FVector3d PositionSpacecraft = GetSpacecraftPosition(SpacecraftMessage);
	// Set Rotation
	const FRotator SpacecraftRotation = GetRotatorFromMrp(FVector3d(SpacecraftMessage.attitude(0),
																		SpacecraftMessage.attitude(1),
																		SpacecraftMessage.attitude(2)));
	// Create Spacecraft Actor instance
	ASpacecraft *TempSpacecraft = GetWorld()->SpawnActor<ASpacecraft>(BpSpacecraft, PositionSpacecraft, SpacecraftRotation);
	TempSpacecraft->Name = FString(SpacecraftMessage.spacecraftname().c_str());
	// Set camera
	if (this->CielimMessage.has_camera())
	{
		const cielimMessage::CameraModel &Camera = CielimMessage.camera();
		TempSpacecraft->SetFOV(FMath::RadiansToDegrees(Camera.fieldofview(0)),
			FMath::RadiansToDegrees(Camera.fieldofview(1)));
		TempSpacecraft->SetResolution(Camera.resolution(0), Camera.resolution(1));
		// Set camera location and orientation
		const FVector3d CameraPosition = GetCameraPosition(Camera);
		TempSpacecraft->SetCameraPosition(CameraPosition);
		const FRotator CameraRotation = GetCameraRotation(Camera);
		TempSpacecraft->UpdateCameraOrientation(CameraRotation);
	}
	this->Spacecraft = TempSpacecraft;
	this->IsSpacecraftSpawned = true;

	this->PointSunLight();
}

void ASimulationDataSourceActor::PointSunLight()
{
	this->SunLight = GetWorld()->SpawnActor<ADirectionalLight>(FVector3d::ZeroVector,
		FRotator::ZeroRotator);
	double LuxAt1AU = 1000;
	this->SunLight->GetLightComponent()->SetIntensity(LuxAt1AU*(AU*AU)/(FMath::Square(this->SunCelestialBody->GetActorLocation().Length()/100000)));
	this->SunLight->GetLightComponent()->SetMobility(EComponentMobility::Movable);
	auto Vector = -this->SunCelestialBody->GetActorLocation();
	Vector.Normalize();
	auto thing = FRotationMatrix::MakeFromX(Vector);
	this->SunLight->GetLightComponent()->SetRelativeRotation(thing.Rotator());
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
	for (const auto &CelestialBody : CielimMessage.celestialbodies())
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
	const cielimMessage::Spacecraft &SpacecraftMessage = CielimMessage.spacecraft();
	const FVector3d PositionSpacecraft = GetSpacecraftPosition(SpacecraftMessage);
	const FRotator SpacecraftRotation = GetRotatorFromMrp(FVector3d(SpacecraftMessage.attitude(0),
															SpacecraftMessage.attitude(1),
															SpacecraftMessage.attitude(2)));
	this->Spacecraft->Update(PositionSpacecraft, SpacecraftRotation);
	// Update camera
	if (this->CielimMessage.has_camera())
	{
		const cielimMessage::CameraModel &Camera = CielimMessage.camera();
		const FRotator CameraRotation = GetCameraRotation(Camera);
		this->Spacecraft->UpdateCameraOrientation(CameraRotation);
	}
}

/**
 * @brief DebugVizMessage() Prints VizMessage to the console
 * 
 */
void ASimulationDataSourceActor::DebugCielimMessage() const
{
	const std::string DebugStr = this->CielimMessage.DebugString();
	UE_LOG(LogCielim, Display, TEXT("%hs"), DebugStr.c_str());
}
