// Fill out your copyright notice in the Description page of Project Settings.

#include "ProtobufActor.h"
#include "KinematicsUtilities.h"
#include "Engine/World.h"

// Sets default values
AProtobufActor::AProtobufActor()
{
 	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;
    this->hasCameras = false;
}

// Called when the game starts or when spawned
void AProtobufActor::BeginPlay()
{
    Super::BeginPlay();
    // scenarioAsteroidArrival_UnityViz
    // ItokawaTalonsFlyby
    this->protobufreader = new ProtobufReader("ItokawaTalonsFlyby.bin");
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
 * @brief Create a Celestial Body Rotation Quaternion
 * 
 * @param celestialbody A celestial body object
 * @return FQuat Quaternion representing the celestial body's dcm
 */
FQuat CreateCelestialBodyRotationQuat(const vizProtobufferMessage::VizMessage_CelestialBody& celestialbody) {
    
    // Set vectors
    FVector Rotation1 = FVector4d(celestialbody.rotation(0), celestialbody.rotation(1), celestialbody.rotation(2), 0);
    FVector Rotation2 = FVector4d(celestialbody.rotation(3), celestialbody.rotation(4), celestialbody.rotation(5), 0);
    FVector Rotation3 = FVector4d(celestialbody.rotation(6), celestialbody.rotation(7), celestialbody.rotation(8), 0);
    FVector Rotation4 = FVector4d(0, 0, 0, 1);

    // Set matrix
    FMatrix Mat = FMatrix(Rotation1, Rotation2, Rotation3, Rotation4);

    // Set Quaternion
    return FQuat(Mat);
}

/**
 * @brief Spawns all celestial bodies from the vizmessage into the level
 * 
 */
void AProtobufActor::SpawnCelestialBodies()
{
    for (const auto& celestialbody : vizmessage.celestialbodies()) {

        FVector3d SpawnLocation = FVector3d(celestialbody.position(0), celestialbody.position(1), celestialbody.position(2));
        

        FQuat Quat = CreateCelestialBodyRotationQuat(celestialbody);
        FQuat QuatLH = RightQuat2LeftQuat(Quat);
        FRotator SpawnRotation = FRotator(QuatLH);

        // TODO: Set name
        FString CbName = FString(celestialbody.bodyname().c_str());
        // FActorSpawnParameters SpawnParams;
        // GEngine->AddOnScreenDebugMessage(-1, 30.f, FColor::White, FString::Printf(TEXT("spawned actor %hs"), celestialbody.bodyname().c_str()));
        // SpawnParams.Name = FName(*CbName);

        if (BpCelestialBody) {
            ACelestialBody* TempCb = GetWorld()->SpawnActor<ACelestialBody>(BpCelestialBody, SpawnLocation, SpawnRotation);
            TempCb->name = CbName;
            TempCb->SetRadiusEvent(celestialbody.radiuseq());
            CelestialBodyArray.Add(TempCb);
        }
        else {
            UE_LOG(LogTemp, Warning, TEXT("Defualt BpCelestialBody has not been set in BP_ProtobufActor"));
        }

        // GEngine->AddOnScreenDebugMessage(-1, 30.f, FColor::White, FString::Printf(TEXT("radius eq %f"), celestialbody.radiuseq()));
    }
}

/**
 * @brief Spawns all spacecraft from the vizmessage into the level
 * 
 */
void AProtobufActor::SpawnSpacecraft()
{
    if (BpSpacecraft) {
        const vizProtobufferMessage::VizMessage_Spacecraft& spacecraft = vizmessage.spacecraft(0);
        FVector3d SpawnLocation = FVector3d(spacecraft.position(0), spacecraft.position(1), spacecraft.position(2));
        FQuat Quat = MRPtoQuaternion(FVector3d(spacecraft.rotation(0), spacecraft.rotation(1), spacecraft.rotation(2)));
        FQuat QuatLH = RightQuat2LeftQuat(Quat);
        FRotator SpawnRotation = FRotator(QuatLH);
        FString ScName = FString(spacecraft.spacecraftname().c_str());
        // Create Spacecraft Actor instance
        ASpacecraft* TempSc = GetWorld()->SpawnActor<ASpacecraft>(BpSpacecraft, SpawnLocation, SpawnRotation);
        TempSc->name = ScName;
        // Grab camera
        if (this->hasCameras) {
            const vizProtobufferMessage::VizMessage_CameraConfig& camera = vizmessage.cameras(0);
            FVector3d CameraSpawn = FVector3d(camera.camerapos_b(0), camera.camerapos_b(1), camera.camerapos_b(2));
            TempSc->SetCameraPosition(CameraSpawn);
            FQuat CameraQuat = MRPtoQuaternion(FVector3d(camera.cameradir_b(0), camera.cameradir_b(1), camera.cameradir_b(2)));
            FQuat CameraQuatLH = RightQuat2LeftQuat(CameraQuat);
            TempSc->UpdateCameraOrientation(FRotator(CameraQuatLH));
        }
        this->Spacecraft = TempSc;
    }
    else {
        UE_LOG(LogTemp, Warning, TEXT("Defualt BpSpacecraft has not been set in BP_ProtobufActor"));
    }
    // GEngine->AddOnScreenDebugMessage(-1, 30.f, FColor::White, Quat.ToString());
}

/**
 * @brief Update all celestial body positions and rotations
 * 
 */
void AProtobufActor::UpdateCelestialBodies() 
{
    
    int CBindex = 0;
    for (const auto& celestialbody : vizmessage.celestialbodies()) {
        FVector3d NewPosition = FVector3d(celestialbody.position(0), celestialbody.position(1), celestialbody.position(2));
        // GEngine->AddOnScreenDebugMessage(-1, 30.f, FColor::White, NewPosition.ToString());
        FQuat NewRotation = CreateCelestialBodyRotationQuat(celestialbody);
        FQuat NewRotationLH = RightQuat2LeftQuat(NewRotation);
        // Check Blueprint has been set in Actor
        if (BpCelestialBody) {
            CelestialBodyArray[CBindex]->Update(NewPosition, NewRotationLH);
            CBindex ++;
        }
    }
}

/**
 * @brief Update Spacecraft/camera positions and rotations 
 * 
 */
void AProtobufActor::UpdateSpacecraft() 
{
    if (BpSpacecraft) {
        const vizProtobufferMessage::VizMessage_Spacecraft& spacecraft = vizmessage.spacecraft(0);
        FVector3d NewPosition = FVector3d(spacecraft.position(0), spacecraft.position(1), spacecraft.position(2));
        // GEngine->AddOnScreenDebugMessage(-1, 30.f, FColor::White, NewPosition.ToString());
        FQuat NewRotation = MRPtoQuaternion(FVector3d(spacecraft.rotation(0), spacecraft.rotation(1), spacecraft.rotation(2)));
        FQuat NewRotationLH = RightQuat2LeftQuat(NewRotation);
        this->Spacecraft->Update(NewPosition, NewRotationLH);

        // Update camera
        if (this->hasCameras) {
            const vizProtobufferMessage::VizMessage_CameraConfig& camera = vizmessage.cameras(0);
            FQuat CameraQuat = MRPtoQuaternion(FVector3d(camera.cameradir_b(0), camera.cameradir_b(1), camera.cameradir_b(2)));
            FQuat CameraQuatLH = RightQuat2LeftQuat(CameraQuat);
            // GEngine->AddOnScreenDebugMessage(-1, 30.f, FColor::White, CameraQuat.ToString());
            this->Spacecraft->UpdateCameraOrientation(FRotator(CameraQuatLH));
        }
    }
}

