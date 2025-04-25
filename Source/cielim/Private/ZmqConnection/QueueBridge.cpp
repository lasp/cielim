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

void UQueueBridge::PutQueueData(std::string Data) const
{
	/* Unused for now, will just return ERROR if usage is attempted */

	FCircularQueueData NextCommand;

	NextCommand.query = CommandType::ERROR;
	this->MultiThreadDataQueue->Responses.Enqueue(NextCommand);
}

void UQueueBridge::PutImageQueueData(const TArray64<uint8> &PNGData,
									 const TOptional<FVector2d> CenterOfBrightness) const
{
	FCircularQueueData NextCommand;

	NextCommand.query = CommandType::REQUEST_IMAGE;
	NextCommand.payload.Emplace<FImagePayload>(FImagePayload());
	NextCommand.payload.Get<FImagePayload>().image_data = PNGData;
	NextCommand.payload.Get<FImagePayload>().centerOfBrightness = CenterOfBrightness;

	UE_LOG(LogCielim, Display, TEXT("Enqueue image response: UQueueBridge"));

	this->MultiThreadDataQueue->Responses.Enqueue(NextCommand);
}
