//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of UQueueBridge.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "QueueBridge.h"

#include <zmq_addon.hpp>

#include "../Utilities/Logging/CielimLoggingMacros.h"

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

	this->QueueSocket = zmq::socket_t(ContextPtr, zmq::socket_type::pair);
	this->QueueSocket.connect("inproc://OutboundQueueReady");
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

void UQueueBridge::PutQueueData(const FCircularQueueData &Data)
{
	this->MultiThreadDataQueue->Responses.Enqueue(Data);

	zmq::message_t Signal(1);
	this->QueueSocket.send(Signal, zmq::send_flags::none);

	UE_LOG(LogCielim, Display, TEXT("Enqueue response: UQueueBridge"));
}

uint32 UQueueBridge::NumQueueInbound() const { return MultiThreadDataQueue->Requests.Count(); }

uint32 UQueueBridge::NumQueueOutbound() const { return MultiThreadDataQueue->Responses.Count(); }
