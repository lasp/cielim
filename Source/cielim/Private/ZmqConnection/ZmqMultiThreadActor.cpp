#include "ZmqConnection/ZmqMultiThreadActor.h"

#include <fstream>

#include "CielimLoggingMacros.h"

//Static counter for thread creation process, for unique identification of the thread
int32 UZmqMultiThreadActor::ThreadNameCounter = 0;

void UZmqMultiThreadActor::PostInitProperties()
{
	UE_LOG(LogCielim, Display, TEXT("UZmqMultiThreadActor::BeginPlay"));

	Super::PostInitProperties();
}

void UZmqMultiThreadActor::BeginDestroy()
{
	//Allows thread to finish current task / tick cycle
	//! Freezing game thread exit process in meantime
	this->ConnectorThreadShutdown();

	this->ZmqContext.shutdown();
	this->ZmqContext.close();

	Super::BeginDestroy();
}

void UZmqMultiThreadActor::Connect(const std::string& Address)
{
	this->ZmqContext = zmq::context_t();
	this->ConnectionAddress = Address;
	this->ConnectorThreadInit();
}

void UZmqMultiThreadActor::ConnectorThreadInit()
{
	//	Thread-Safe queue to pass data and commands between queue and game thread
	UE_LOG(LogCielim, Display, TEXT("UZmqMultiThreadActor::ThreadInit"));
	this->MultiThreadDataQueue = std::make_shared<CielimCircularQueue>();

	// Thread tick rate to prevent thread from spinning if a fast update is not needed
	FTimespan ThreadWaitTime = FTimespan::FromSeconds(0.0);

	FString UniqueThreadName = "ZMQ Connector ";
	UniqueThreadName += FString::FromInt(++ThreadNameCounter);

	this->ConnectorThread = std::make_unique<Connector>(ThreadWaitTime,
														*UniqueThreadName,
														this,
														this->ZmqContext,
														this->ConnectionAddress,
														this->MultiThreadDataQueue);

	UE_LOG(LogCielim, Display, TEXT("UZmqMultiThreadActor::ThreadInit end"));
	// this->StartThreadTimerUpdate();
}

void UZmqMultiThreadActor::ConnectorThreadShutdown()
{
	UE_LOG(LogCielim, Display, TEXT("UZmqMultiThreadActor::ConnectorThreadShutdown"));
	if(this->ConnectorThread)
	{
		this->ConnectorThread->Stop();
		// Empty the queue because we're not going to process anymore data
		// This also unblocks the ActivePoller::wait call in teh Connector thread
		// which will (likely) be blocked on enqueueing data into the thread safe
		// data queue
		this->MultiThreadDataQueue->Requests.Empty();
		this->MultiThreadDataQueue->Responses.Empty();
		/* Wait here until connectorThread is verified as having stopped. This will delay PIE EndPlay or closing of
		 * the game while the thread have a chance to finish */
		while(!this->ConnectorThread->ThreadHasStopped())
		{
			FPlatformProcess::Sleep(0.1);
			UE_LOG(LogCielim, Display, TEXT("sleeping in UZmqMultiThreadActor::ConnectorThreadShutdown"));
		}

		this->ConnectorThread->ThreadShutdown();
		this->ConnectorThread.release();
	}

	this->ConnectorThread = nullptr;
}

TOptional<FCircularQueueData> UZmqMultiThreadActor::GetQueueData() const
{
	TOptional<FCircularQueueData> queueData;

	if(!this->MultiThreadDataQueue || this->MultiThreadDataQueue->Requests.IsEmpty())
	{
		// Do nothing for now
	}
	else if (FCircularQueueData NextCommand{}; this->MultiThreadDataQueue->Requests.Dequeue(NextCommand))
	{
		UE_LOG(LogCielim, Display, TEXT("Dequeue command: UZmqMultiThreadActor"));
		queueData = NextCommand;
	}
	else
	{
		UE_LOG(LogCielim, Display, TEXT("No command received: UZmqMultiThreadActor"));
	}

	return queueData;
}

void UZmqMultiThreadActor::PutQueueData(std::string Data) const
{
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

bool UZmqMultiThreadActor::IsThreadPaused() const
{
	if(this->ConnectorThread)
	{
		return this->ConnectorThread->ThreadIsPaused();
	}
	return false;
}
