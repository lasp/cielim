// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "cielimGameModeBase.generated.h"

// GameMode class for cielim
UCLASS()
class CIELIM_API AcielimGameModeBase : public AGameModeBase
{
	GENERATED_BODY()

public:
	// Constructor (not currently in use at the moment)
	AcielimGameModeBase();

protected:
	// Initial game setup
	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;

	// This is where game logic begins execution
	virtual void BeginPlay() override;
};
