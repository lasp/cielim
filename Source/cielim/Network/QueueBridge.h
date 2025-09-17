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
	void Connect(zmq::context_t &ContextPtr, CielimCircularQueue &CircularQueue);

	/**
	 * @brief Gets data off of inbound queue and returns it if exists.
	 * @note Queue could be empty, hence the need for TOptional.
	 */
	TSharedPtr<FCircularQueueData> GetQueueData() const;

	/**
	 * @brief Puts data onto outbound queue.
	 * @param Data FCircularQueueData instance containing data to be put on outbound queue.
	 */
	void PutQueueData(const TSharedPtr<FCircularQueueData> &Data);

	/**
	 * @brief Returns the number of items in the inbound queue.
	 */
	uint32 NumQueueInbound() const;
	/**
	 * @brief Returns the number of items in the outbound queue.
	 */
	uint32 NumQueueOutbound() const;

	// These functions are public but should never be called;
	// They are only ever used internally by Unreal Engine.

	// Called after the class instance has been constructed.
	virtual void PostInitProperties() override;

	// Called before the class instance is destroyed.
	virtual void BeginDestroy() override;

private:
	CielimCircularQueue *MultiThreadDataQueue;

	zmq::context_t *Context;
	zmq::socket_t QueueSocket;
};
