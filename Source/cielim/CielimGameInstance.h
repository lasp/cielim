//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the UCielimGameInstance class. This class is used as the game instance by Cielim
//          instead of the default provided by Unreal and owns all persistent objects such as the
//          network router and context.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "zmq.hpp"

#include "Network/Router.h"
#include "Scenes/SceneManager.h"

#include "CielimGameInstance.generated.h"

UCLASS(Blueprintable)
class CIELIM_API UCielimGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	// UFUNCTION(BlueprintCallable, Category = "Scene Manager")
	USceneManager *GetSceneManager() const { return SceneManager; }

protected:
	virtual void Init() override;
	virtual void Shutdown() override;

private:
	UPROPERTY()
	USceneManager *SceneManager;

	CielimCircularQueue MultiThreadQueue;

	zmq::context_t Context;
	FRouter *Router;
};
