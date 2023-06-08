// Fill out your copyright notice in the Description page of Project Settings.

#include "ProtobufActor.h"
#include <iostream>
#include <fstream>
#include <sstream>


// Sets default values
AProtobufActor::AProtobufActor()
{
 	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

}

// Called when the game starts or when spawned
void AProtobufActor::BeginPlay()
{
	Super::BeginPlay();
    // Verify that the version of the library that we linked against is
    // compatible with the version of the headers we compiled against.
    GOOGLE_PROTOBUF_VERIFY_VERSION;

    // Create a CameraConfig object
    vizProtobufferMessage::VizMessage vizmessage;
    
    // Read the file.
    std::fstream input("/Users/pake0095/Documents/Repositories/cielim/Source/cielim/Private",
                       std::ios::in | std::ios::binary);

    if (!input){
        UE_LOG(LogTemp, Warning, TEXT("Failed to open /Users/pake0095/Documents/Repositories/cielim/Source/cielim/Private"));
        return;
    }
    
    if (vizmessage.ParseFromIstream(&input)) {
        UE_LOG(LogTemp, Warning, TEXT("Failed to parse /Users/pake0095/Documents/Repositories/cielim/Source/cielim/Private"));
        return;
    }
    UE_LOG(LogTemp, Warning, TEXT("Successfully parsed binary data."));
    
    // std::cout << camera_config.fieldofview() << " Field of View" << std::endl;

    // Optional:  Delete all global objects allocated by libprotobuf.
    google::protobuf::ShutdownProtobufLibrary();
    UE_LOG(LogTemp, Warning, TEXT("Success"));
}

// Called every frame
void AProtobufActor::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

}
