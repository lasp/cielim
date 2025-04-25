//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the USceneManager class. The scene manager maintains the scene instance and tells
//          the scene to parse the circular queue and update the scene if necessary every tick.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"

#include "SimulationDataSourceActor.h"
#include "ZmqConnection/QueueBridge.h"

#include "SceneManager.generated.h"

UCLASS()
class CIELIM_API USceneManager : public UGameInstanceSubsystem, public FTickableGameObject
{
	GENERATED_BODY()

public:
	/**
	 * @brief Initializes things after constructor is finished.
	 * @param ContextPtr Reference to the global ZMQ context.
	 * @param CircularQueue Reference to the circular queue.
	 */
	void Init(zmq::context_t &ContextPtr, CielimCircularQueue &CircularQueue);

	// These functions are public but should never be called;
	// They are only ever used internally by Unreal Engine.

	virtual bool IsTickable() const override;
	virtual void Tick(float DeltaTime) override;

	virtual TStatId GetStatId() const override;

private:
	UPROPERTY()
	UQueueBridge *QueueBridge;

	UPROPERTY()
	ASimulationDataSourceActor *Scene;
};
