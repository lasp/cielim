// Fill out your copyright notice in the Description page of Project Settings.

#include "SimulationDataSourceActor.h"
#include "KinematicsUtilities.h"
#include "Engine/World.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <zmq.hpp>

// Sets default values
ASimulationDataSourceActor::ASimulationDataSourceActor()
{
    PrimaryActorTick.bCanEverTick = true;
}

// Called when the game starts or when spawned
void ASimulationDataSourceActor::BeginPlay()
{
    Super::BeginPlay();
    
    this->bHasCameras = false;
    
    FString CommAddress;
    FString SimulationDataFile;
    if(FParse::Value(FCommandLine::Get(), TEXT("directComm"), CommAddress))
    {
        
    } else if(FParse::Value(FCommandLine::Get(), TEXT("simulationDataFile"), SimulationDataFile)) {
        
    }
    
    this->Protobufreader = new ProtobufReader("simulation_protobuffer.bin");
    this->Vizmessage = this->Protobufreader->ReadInputData();

    // Check if message has cameras
    if (Vizmessage.cameras().size() > 0) {
        this->bHasCameras = true;
    }
    if (!BpCelestialBody || !BpSpacecraft) {
        UE_LOG(LogTemp, Warning, TEXT("Defualt BluePrint Classes have not been set in BP_ProtobufActor"));
        return;
    }
    this->SpawnCelestialBodies();
    this->SpawnSpacecraft();
    
    int major;
    int minor;
    int patch;
    zmq::version(&major, &minor, &patch);
    UE_LOG(LogTemp, Log, TEXT("ZeroMQ version: v%d.%d.%d"), major, minor, patch);
}

// Called every frame
void ASimulationDataSourceActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime); 
    // Read input
    this->Vizmessage = this->Protobufreader->ReadInputData();
    // Update Actor postions and rotatons
    if (!BpCelestialBody || !BpSpacecraft) {
        UE_LOG(LogTemp, Warning, TEXT("Defualt BluePrint Classes have not been set in BP_ProtobufActor"));
        return;
    }
    this->UpdateCelestialBodies();
    this->UpdateSpacecraft();
}

/**
 * @brief GetCelestialBodyPosition(CelestialBody) Gets the positions of a CelestialBody Object
 * @param CelestialBody A CelestialBody Object
 * @return FVector3d CelestialBody's position
 */
FVector3d GetCelestialBodyPosition(const vizProtobufferMessage::VizMessage_CelestialBody& CelestialBody)
{
    const FVector3d PositionCelestialBody = FVector3d(CelestialBody.position(0), CelestialBody.position(1), CelestialBody.position(2));
    return Right2LeftVector(PositionCelestialBody);
}  

/**
 * @brief GetCelestialBodyRotation(CelestialBody) Gets the rotation of a CelestialBody object
 * 
 * @param CelestialBody A CelestialBody object
 * @return FRotator celestial body's rotation 
 */
FRotator GetCelestialBodyRotation(const vizProtobufferMessage::VizMessage_CelestialBody& CelestialBody)
{
    // Create CelestialBody Rotation Quat
    const FVector Rotation1 = FVector4d(CelestialBody.rotation(0), CelestialBody.rotation(1), CelestialBody.rotation(2), 0);
    const FVector Rotation2 = FVector4d(CelestialBody.rotation(3), CelestialBody.rotation(4), CelestialBody.rotation(5), 0);
    const FVector Rotation3 = FVector4d(CelestialBody.rotation(6), CelestialBody.rotation(7), CelestialBody.rotation(8), 0);
    const FVector Rotation4 = FVector4d(0, 0, 0, 1);
    const FMatrix Mat = FMatrix(Rotation1, Rotation2, Rotation3, Rotation4);
    const FQuat Q = FQuat(Mat);
    // Get FRotator 
    const FQuat QLeftHand = RightQuat2LeftQuat(Q);
    return FRotator(QLeftHand);
}

/**
 * @brief SpawnCelestialBodies() Spawns all celestial bodies from the VizMessage into the level
 * 
 */
void ASimulationDataSourceActor::SpawnCelestialBodies()
{
    for (const auto& CelestialBody : Vizmessage.celestialbodies()) {
        // Set Location 
        FVector3d PositionCelestialBody =GetCelestialBodyPosition(CelestialBody);
        // Set Rotation
        FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);
        // Create CelestialBody Actor instance
        ACelestialBody* TempCelestialBody; 
        if (CelestialBody.bodyname() == "sun") {
            TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>(BpSun, PositionCelestialBody, CelestialBodyRotation);
        }
        else if (CelestialBody.bodyname() == "Justitia") {
            TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>(BpAsteroid, PositionCelestialBody, CelestialBodyRotation);
        }
        else {
            TempCelestialBody = GetWorld()->SpawnActor<ACelestialBody>(BpCelestialBody, PositionCelestialBody, CelestialBodyRotation);
        }
        FString CbName = FString(CelestialBody.bodyname().c_str());
        TempCelestialBody->Name = CbName;
        TempCelestialBody->SetRadiusEvent(CelestialBody.radiuseq());
        CelestialBodyArray.Add(TempCelestialBody);
    }
}

/**
 * @brief GetRotatorFromMrp(Sigma) Converts an MRP into an Unreal Rotation Container (FRotator) 
 * 
 * @param Sigma The MRP vector
 * @return FRotator Unreal Rotation Container
 */
FRotator GetRotatorFromMrp(const FVector3d& Sigma)
{
    FQuat Q = MRPtoQuaternion(Sigma);
    const FQuat QLeftHand = RightQuat2LeftQuat(Q);
    return FRotator(QLeftHand); 
}

/**
 * @brief GetSpacecraftPosition(Spacecraft) Gets the positions of a Spacecraft Object
 * @param Spacecraft A Spacecraft Object
 * @return FVector3d Spacecraft's position
 */
FVector3d GetSpacecraftPosition(const vizProtobufferMessage::VizMessage_Spacecraft& Spacecraft)
{
    const FVector3d PositionSpacecraft = FVector3d(Spacecraft.position(0), Spacecraft.position(1), Spacecraft.position(2));
    return Right2LeftVector(PositionSpacecraft);
}


/**
 * @brief GetCameraPosition(Camera) Gets the position of a Camera Object
 * @param Camera A Camera Object
 * @return FVector3d Camera's position
 */
FVector3d GetCameraPosition(const vizProtobufferMessage::VizMessage_CameraConfig& Camera)
{
    const FVector3d SigmaCamera = FVector3d(Camera.camerapos_b(0), Camera.camerapos_b(1), Camera.camerapos_b(2));
    return Right2LeftVector(SigmaCamera);
}


/**
 * @brief GetCameraRotation(Camera) Gets the rotation of a Camera Object
 * @param Camera A Camera Object
 * @return FRotator Camera's Rotation
 */
FRotator GetCameraRotation(const vizProtobufferMessage::VizMessage_CameraConfig& Camera)
{
    // Map basilisk right-handed camera orientation to unreal left-handed camera orientation
    const FVector3d SigmaCB = FVector3d(Camera.cameradir_b(0), Camera.cameradir_b(1), Camera.cameradir_b(2));
    const FQuat Q = MRPtoQuaternion(SigmaCB); 
    const FQuat QTemp = MRPtoQuaternion(FVector3d(-1./3, -1./3, 1./3)); // Temporary correction for Basilisk output CrCu (r unreal u basilisk)
    const FQuat QCorrection = FQuat(0.5, -0.5, 0.5, 0.5);
    const FVector3d SigmaCorrection = QuaterniontoMRP(Q * QCorrection * QTemp);
    return GetRotatorFromMrp(SigmaCorrection);
}

/**
 * @brief SpawnSpacecraft() Spawns all spacecraft from the VizMessage into the level
 * 
 */
void ASimulationDataSourceActor::SpawnSpacecraft()
{
    const vizProtobufferMessage::VizMessage_Spacecraft& VizSpacecraft = Vizmessage.spacecraft(0);
    // Set Location 
    const FVector3d PositionSpacecraft = GetSpacecraftPosition(VizSpacecraft);
    // Set Rotation
    const FRotator SpacecraftRotation = GetRotatorFromMrp(FVector3d(VizSpacecraft.rotation(0), VizSpacecraft.rotation(1), VizSpacecraft.rotation(2)));
    FString ScName = FString(VizSpacecraft.spacecraftname().c_str());
    // Create Spacecraft Actor instance
    ASpacecraft* TempSc = GetWorld()->SpawnActor<ASpacecraft>(BpSpacecraft, PositionSpacecraft, SpacecraftRotation);
    TempSc->Name = ScName;
    // Set camera
    if (this->bHasCameras) {
        const vizProtobufferMessage::VizMessage_CameraConfig& Camera = Vizmessage.cameras(0);
        TempSc->SetFOV(Camera.fieldofview()); // Set camera settings
        TempSc->SetResolution(Camera.resolution(0), Camera.resolution(1));
        // Set camera location and orientation
        const FVector3d CameraPosition = GetCameraPosition(Camera);
        TempSc->SetCameraPosition(CameraPosition);
        const FRotator CameraRotation = GetCameraRotation(Camera);
        TempSc->UpdateCameraOrientation(CameraRotation);
    }
    this->Spacecraft = TempSc;
}

/**
 * @brief UpdateCelestialBodies() Updates all celestial body positions and rotations
 * 
 */
void ASimulationDataSourceActor::UpdateCelestialBodies() const
{
    int Index = 0;
    for (const auto& CelestialBody : Vizmessage.celestialbodies()) {
        FVector3d PositionCelestialBody = GetCelestialBodyPosition(CelestialBody);
        FRotator CelestialBodyRotation = GetCelestialBodyRotation(CelestialBody);
        CelestialBodyArray[Index]->Update(PositionCelestialBody, CelestialBodyRotation);
        Index ++;
    }
}

/**
 * @brief UpdateSpacecraft() Updates Spacecraft and camera positions and rotations 
 * 
 */
void ASimulationDataSourceActor::UpdateSpacecraft() const 
{
    const vizProtobufferMessage::VizMessage_Spacecraft& VizSpacecraft = Vizmessage.spacecraft(0);
    const FVector3d PositionSpacecraft = GetSpacecraftPosition(VizSpacecraft);
    const FRotator SpacecraftRotation = GetRotatorFromMrp(FVector3d(VizSpacecraft.rotation(0), VizSpacecraft.rotation(1), VizSpacecraft.rotation(2)));
    this->Spacecraft->Update(PositionSpacecraft, SpacecraftRotation);
    // Update camera
    if (this->bHasCameras) {
        const vizProtobufferMessage::VizMessage_CameraConfig& Camera = Vizmessage.cameras(0);
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
    UE_LOG(LogTemp, Warning, TEXT("%hs"),DebugStr.c_str());
}

