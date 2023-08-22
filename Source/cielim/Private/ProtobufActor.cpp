// Fill out your copyright notice in the Description page of Project Settings.

#include "ProtobufActor.h"
#include "KinematicsUtilities.h"
#include "Engine/World.h"

// Sets default values
AProtobufActor::AProtobufActor()
{
    PrimaryActorTick.bCanEverTick = true;
    this->hasCameras = false;
}

// Called when the game starts or when spawned
void AProtobufActor::BeginPlay()
{
    Super::BeginPlay();
    this->protobufreader = new ProtobufReader("simulation_protobuffer.bin");
    this->vizmessage = this->protobufreader->ReadInputData();
    // Check if message has cameras
    if (vizmessage.cameras().size() > 0) {
        this->hasCameras = true;
    }
    this->SpawnCelestialBodies();
    this->SpawnSpacecraft();
}

// Called every frame
void AProtobufActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime); 
    // Read input
    this->vizmessage = this->protobufreader->ReadInputData();
    // Update Actor postions and rotatons
    this->UpdateCelestialBodies();
    this->UpdateSpacecraft();

}

/**
 * @brief CreateCelestialBodyRotationQuat(celestialbody) Creates a Celestial Body Rotation Quaternion
 * 
 * @param celestialbody A celestial body object
 * @return FQuat celestial body's Quaternion 
 */
FQuat CreateCelestialBodyRotationQuat(const vizProtobufferMessage::VizMessage_CelestialBody& celestialbody) {
    
    FVector Rotation1 = FVector4d(celestialbody.rotation(0), celestialbody.rotation(1), celestialbody.rotation(2), 0);
    FVector Rotation2 = FVector4d(celestialbody.rotation(3), celestialbody.rotation(4), celestialbody.rotation(5), 0);
    FVector Rotation3 = FVector4d(celestialbody.rotation(6), celestialbody.rotation(7), celestialbody.rotation(8), 0);
    FVector Rotation4 = FVector4d(0, 0, 0, 1);
    FMatrix Mat = FMatrix(Rotation1, Rotation2, Rotation3, Rotation4);
    return FQuat(Mat);
}

/**
 * @brief SpawnCelestialBodies() Spawns all celestial bodies from the vizmessage into the level
 * 
 */
void AProtobufActor::SpawnCelestialBodies()
{
    if (!BpCelestialBody) {
        UE_LOG(LogTemp, Warning, TEXT("Defualt BpCelestialBody has not been set in BP_ProtobufActor"));
        return;
    }
    for (const auto& celestialbody : vizmessage.celestialbodies()) {

        // Set Location 
        FVector3d sigma_celestialbody = FVector3d(celestialbody.position(0), celestialbody.position(1), celestialbody.position(2));
        FVector3d sigma_celestialbody_lefthand = Right2LeftVector(sigma_celestialbody);
        // Set Rotation
        FQuat q = CreateCelestialBodyRotationQuat(celestialbody);
        FQuat q_lefthand = RightQuat2LeftQuat(q);
        FRotator celestialbodyRotation = FRotator(q_lefthand);
        // Create Celestialbody Actor instance
        ACelestialBody* TempCb; 
        if (celestialbody.bodyname() == "sun") {
            TempCb = GetWorld()->SpawnActor<ACelestialBody>(BpSun, sigma_celestialbody_lefthand, celestialbodyRotation);
        }
        else {
            TempCb = GetWorld()->SpawnActor<ACelestialBody>(BpCelestialBody, sigma_celestialbody_lefthand, celestialbodyRotation);
        }
        FString CbName = FString(celestialbody.bodyname().c_str());
        TempCb->name = CbName;
        TempCb->SetRadiusEvent(celestialbody.radiuseq());
        CelestialBodyArray.Add(TempCb);
    }
}

/**
 * @brief GetRotatorFromMRP(sigma) Converts an MRP into an Unreal Rotation Container (FRotator) 
 * 
 * @param sigma The MRP vector
 * @return FRotator Unreal Rotaiton Container
 */
FRotator GetRotatorFromMRP(FVector3d sigma)
{
    FQuat q = MRPtoQuaternion(sigma);
    FQuat q_lefthand = RightQuat2LeftQuat(q);
    return FRotator(q_lefthand); 
}

/**
 * @brief Basilisk2UnrealCamera(sigma_CB) maps basilisk right-handed camera orientation 
 * to unreal left-handed camera orientation 
 * 
 * @param sigma_CB 
 * @return FVector3d 
 */
FVector3d Basilisk2UnrealCamera(FVector3d sigma_CB)
{
    FQuat q = MRPtoQuaternion(sigma_CB); 
    FQuat q_temp = MRPtoQuaternion(FVector3d(-1./3, -1./3, 1./3)); // Temporary correction for Basilisk output CrCu (r unreal u basilisk)
    FQuat q_correction = FQuat(0.5, -0.5, 0.5, 0.5);
    return QuaterniontoMRP(q * q_correction * q_temp);
}

/**
 * @brief SpawnSpacecraft() Spawns all spacecraft from the vizmessage into the level
 * 
 */
void AProtobufActor::SpawnSpacecraft()
{
    if (!BpSpacecraft) {
        UE_LOG(LogTemp, Warning, TEXT("Defualt BpSpacecraft has not been set in BP_ProtobufActor"));
        return;
    }
    const vizProtobufferMessage::VizMessage_Spacecraft& spacecraft = vizmessage.spacecraft(0);
    // Set Location 
    FVector3d sigma_spacecraft = FVector3d(spacecraft.position(0), spacecraft.position(1), spacecraft.position(2));
    FVector3d sigma_spacecraft_lefthand = Right2LeftVector(sigma_spacecraft);
    // Set Rotation
    FRotator spacecraftRotation = GetRotatorFromMRP(FVector3d(spacecraft.rotation(0), spacecraft.rotation(1), spacecraft.rotation(2)));
    FString ScName = FString(spacecraft.spacecraftname().c_str());
    // Create Spacecraft Actor instance
    ASpacecraft* TempSc = GetWorld()->SpawnActor<ASpacecraft>(BpSpacecraft, sigma_spacecraft_lefthand, spacecraftRotation);
    TempSc->name = ScName;
    // Set camera
    if (this->hasCameras) {
        const vizProtobufferMessage::VizMessage_CameraConfig& camera = vizmessage.cameras(0);
        TempSc->SetFOV(camera.fieldofview()); // Set camera settings
        TempSc->SetResolution(camera.resolution(0), camera.resolution(1));
        // Set camera location and orientation
        FVector3d sigma_camera = FVector3d(camera.camerapos_b(0), camera.camerapos_b(1), camera.camerapos_b(2));
        FVector3d sigma_camera_lefthand = Right2LeftVector(sigma_camera);
        TempSc->SetCameraPosition(sigma_camera_lefthand);
        FVector3d sigma_correction = Basilisk2UnrealCamera(FVector3d(camera.cameradir_b(0), camera.cameradir_b(1), camera.cameradir_b(2)));
        FRotator cameraRotation = GetRotatorFromMRP(sigma_correction);
        TempSc->UpdateCameraOrientation(cameraRotation);
    }
    this->Spacecraft = TempSc;
}

/**
 * @brief UpdateCelestialBodies() Updates all celestial body positions and rotations
 * 
 */
void AProtobufActor::UpdateCelestialBodies() 
{
    if (BpCelestialBody) {
        int CBindex = 0;
        for (const auto& celestialbody : vizmessage.celestialbodies()) {
            FVector3d sigma_celestialbody = FVector3d(celestialbody.position(0), celestialbody.position(1), celestialbody.position(2));
            FVector3d sigma_celestialbody_lefthand = Right2LeftVector(sigma_celestialbody);
            FQuat celestialbodyRotation = CreateCelestialBodyRotationQuat(celestialbody);
            FQuat celestialbodyRotation_lefthand = RightQuat2LeftQuat(celestialbodyRotation);
            CelestialBodyArray[CBindex]->Update(sigma_celestialbody_lefthand, celestialbodyRotation);
            CBindex ++;
        }
    }
}

/**
 * @brief UpdateSpacecraft() Updates Spacecraft and camera positions and rotations 
 * 
 */
void AProtobufActor::UpdateSpacecraft() 
{
    if (BpSpacecraft) {
        const vizProtobufferMessage::VizMessage_Spacecraft& spacecraft = vizmessage.spacecraft(0);
        FVector3d sigma_spacecraft = FVector3d(spacecraft.position(0), spacecraft.position(1), spacecraft.position(2));
        FVector3d sigma_spacecraft_lefthand = Right2LeftVector(sigma_spacecraft);
        FRotator spacecraftRotation = GetRotatorFromMRP(FVector3d(spacecraft.rotation(0), spacecraft.rotation(1), spacecraft.rotation(2)));
        this->Spacecraft->Update(sigma_spacecraft_lefthand, spacecraftRotation);

        // Update camera
        if (this->hasCameras) {
            const vizProtobufferMessage::VizMessage_CameraConfig& camera = vizmessage.cameras(0);
            FVector3d sigma_correction = Basilisk2UnrealCamera(FVector3d(camera.cameradir_b(0), camera.cameradir_b(1), camera.cameradir_b(2)));
            FRotator cameraRotation = GetRotatorFromMRP(sigma_correction);
            this->Spacecraft->UpdateCameraOrientation(cameraRotation);
        }
    }
}

/**
 * @brief DebugVizmessage() Prints vizmessage to the console
 * 
 */
void AProtobufActor::DebugVizmessage()
{
    std::string debugstr = this->vizmessage.DebugString();
    UE_LOG(LogTemp, Warning, TEXT("%hs"),debugstr.c_str());
}

