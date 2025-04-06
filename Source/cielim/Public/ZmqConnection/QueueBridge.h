//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the UQueueBridge class. The queue bridge serves as a bridge between
//          the scene manager and the circular queue allowing data to be passed between the two.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"
#include "zmq.hpp"

#include "CielimCircularQueue.h"

#include "QueueBridge.generated.h"

UCLASS()
class CIELIM_API UQueueBridge : public UObject
{
	GENERATED_BODY()

public:
	/**
	 * @brief Connects the bridge to the queue and the ZMQ context.
	 * @param ContextPtr Reference to the global ZMQ context.
	 * @param CircularQueue Reference to the queue in question.
	 */
	void Connect(zmq::context_t& ContextPtr, CielimCircularQueue& CircularQueue);

	/**
	 * @brief Gets data off of the queue and returns it.
	 * @note Queue could be empty, hence the need for TOptional.
	 */
	TOptional<FCircularQueueData> GetQueueData() const;

	// This is unused for now
	void PutQueueData(std::string Data) const;

	/**
	 * @brief Puts image data in serialized byte form onto the queue.
	 * @param PNGData Reference to serialized image data.
	 * @param CenterOfBrightness CenterOfBrightness vector; could be null.
	 */
	void PutImageQueueData(const TArray64<uint8>& PNGData, const TOptional<FVector2d> CenterOfBrightness) const;

	// These functions are public but should never be called;
	// They are only ever used internally by Unreal Engine.

	// Called after the class instance has been constructed.
	virtual void PostInitProperties() override;

	// Called before the class instance is destroyed.
	virtual void BeginDestroy() override;

	CielimCircularQueue* MultiThreadDataQueue;

private:
	zmq::context_t* Context;
};
