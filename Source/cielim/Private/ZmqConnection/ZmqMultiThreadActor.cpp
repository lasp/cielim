#include "ZmqConnection/ZmqMultiThreadActor.h"

#include "CielimLoggingMacros.h"

void UZmqMultiThreadActor::PostInitProperties()
{
	UE_LOG(LogCielim, Display, TEXT("UZmqMultiThreadActor::BeginPlay"));

	Super::PostInitProperties();
}

void UZmqMultiThreadActor::BeginDestroy()
{
	Super::BeginDestroy();
}

void UZmqMultiThreadActor::Connect(zmq::context_t& ContextPtr, CielimCircularQueue& CircularQueue)
{
	this->Context = &ContextPtr;
	this->MultiThreadDataQueue = &CircularQueue;
}

TOptional<FCircularQueueData> UZmqMultiThreadActor::GetQueueData() const
{
	TOptional<FCircularQueueData> QueueData;

	if(!this->MultiThreadDataQueue || this->MultiThreadDataQueue->Requests.IsEmpty())
	{
		// Do nothing for now
	}
	else if (FCircularQueueData NextCommand{}; this->MultiThreadDataQueue->Requests.Dequeue(NextCommand))
	{
		UE_LOG(LogCielim, Display, TEXT("Dequeue command: UZmqMultiThreadActor"));
		QueueData = NextCommand;
	}
	else
	{
		UE_LOG(LogCielim, Display, TEXT("No command received: UZmqMultiThreadActor"));
	}

	return QueueData;
}

void UZmqMultiThreadActor::PutQueueData(std::string Data) const
{
	/* Unused for now, will just return ERROR if usage is attempted */

	FCircularQueueData NextCommand;

	NextCommand.query = CommandType::ERROR;
	this->MultiThreadDataQueue->Responses.Enqueue(NextCommand);
}

void UZmqMultiThreadActor::PutImageQueueData(const TArray64<uint8>& PNGData, const TOptional<FVector2d> CenterOfBrightness) const
{
	FCircularQueueData NextCommand;

	NextCommand.query = CommandType::REQUEST_IMAGE;
	NextCommand.payload.Emplace<FImagePayload>(FImagePayload());
	NextCommand.payload.Get<FImagePayload>().image_data = PNGData;
	NextCommand.payload.Get<FImagePayload>().centerOfBrightness = CenterOfBrightness;

	UE_LOG(LogCielim, Display, TEXT("Enqueue image response: UZmqMultiThreadActor"));

	this->MultiThreadDataQueue->Responses.Enqueue(NextCommand);
}
