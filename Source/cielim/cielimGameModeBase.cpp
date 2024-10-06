// Copyright Epic Games, Inc. All Rights Reserved.

#include "cielimGameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"

#include "CielimLoggingMacros.h"

AcielimGameModeBase::AcielimGameModeBase()
{
    // This doesn't do anything for now
}

void AcielimGameModeBase::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);

    UE_LOG(LogCielim, Log, TEXT("Cielim is now initialized..."));
}

void AcielimGameModeBase::BeginPlay()
{
    Super::BeginPlay();

    UE_LOG(LogCielim, Log, TEXT("Cielim is now starting..."));
}
