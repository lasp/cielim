//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of UQueueBridge.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "ZmqConnection/QueueBridge.h"

#include "CielimLoggingMacros.h"

void UQueueBridge::PostInitProperties()
{
	UE_LOG(LogCielim, Display, TEXT("UQueueBridge::BeginPlay"));

	Super::PostInitProperties();
}

void UQueueBridge::BeginDestroy() { Super::BeginDestroy(); }

void UQueueBridge::Connect(zmq::context_t &ContextPtr, CielimCircularQueue &CircularQueue)
{
	this->Context = &ContextPtr;
	this->MultiThreadDataQueue = &CircularQueue;
}

TOptional<FCircularQueueData> UQueueBridge::GetQueueData() const
{
	TOptional<FCircularQueueData> QueueData;

	if (!this->MultiThreadDataQueue || this->MultiThreadDataQueue->Requests.IsEmpty())
	{
		// Do nothing for now
	}
	else if (FCircularQueueData NextCommand{}; this->MultiThreadDataQueue->Requests.Dequeue(NextCommand))
	{
		UE_LOG(LogCielim, Display, TEXT("Dequeue command: UQueueBridge"));
		QueueData = NextCommand;
	}
	else
	{
		UE_LOG(LogCielim, Display, TEXT("No command received: UQueueBridge"));
	}

	return QueueData;
}

void UQueueBridge::PutQueueData(const FCircularQueueData &Data) const
{
	this->MultiThreadDataQueue->Responses.Enqueue(Data);

	UE_LOG(LogCielim, Display, TEXT("Enqueue response: UQueueBridge"));
}
