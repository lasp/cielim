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
    this->protobufreader = new ProtobufReader("scenarioAsteroidArrival_UnityViz.bin");

}

// Called every frame
void AProtobufActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime); 
    this->vizmessage = this->protobufreader->ReadInputData();
    std::string debugstr = this->vizmessage.DebugString();
    UE_LOG(LogTemp, Warning, TEXT("vizmessage: %hs"), debugstr.c_str());
    GEngine->AddOnScreenDebugMessage(-1, 30.f, FColor::White, FString::Printf(TEXT("vizmessage: %hs"), debugstr.c_str()));

}

