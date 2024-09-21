#include "ZmqConnection/ZmqMultiThreadActor.h"
#include "CielimLoggingMacros.h"
#include <fstream>
#include "../Public/ZmqConnection/Commands.h"


//Static counter for thread creation process, for unique identification of the thread
int32 AZmqMultiThreadActor::ThreadNameCounter = 0;

void AZmqMultiThreadActor::BeginPlay() 
{
	Super::BeginPlay();
	UE_LOG(LogCielim, Display, TEXT("AZmqMultiThreadActor::BeginPlay"));
}

void AZmqMultiThreadActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{   
	//Allows thread to finish current task / tick cycle
	//! Freezing game thread exit process in meantime
	this->ConnectorThreadShutdown();
	
	this->ZmqContext.shutdown();
	this->ZmqContext.close();
	Super::EndPlay(EndPlayReason);
}

void AZmqMultiThreadActor::Connect(const std::string& Address)
{
	this->ZmqContext = zmq::context_t();
	this->ConnectionAddress = Address;
	this->ConnectorThreadInit();
}

void AZmqMultiThreadActor::ConnectorThreadInit()
{
	//	Thread-Safe queue to pass data and commands between queue and game thread
	UE_LOG(LogCielim, Display, TEXT("AZmqMultiThreadActor::ThreadInit"));
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

	UE_LOG(LogCielim, Display, TEXT("AZmqMultiThreadActor::ThreadInit end"));
	// this->StartThreadTimerUpdate();
}

void AZmqMultiThreadActor::ConnectorThreadShutdown()
{
	UE_LOG(LogCielim, Display, TEXT("AZmqMultiThreadActor::ConnectorThreadShutdown"));
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
			UE_LOG(LogCielim, Display, TEXT("sleeping in AZmqMultiThreadActor::ConnectorThreadShutdown"));
		}
		
		this->ConnectorThread->ThreadShutdown();
		this->ConnectorThread.release();
	} 
	
	this->ConnectorThread = nullptr;
}

std::optional<FCircularQueueData> AZmqMultiThreadActor::GetQueueData() const
{
	if(!this->MultiThreadDataQueue || this->MultiThreadDataQueue->Requests.IsEmpty())
	{
		return std::nullopt;
	}
	
	if (FCircularQueueData NextCommand; this->MultiThreadDataQueue->Requests.Dequeue(NextCommand)) {
		UE_LOG(LogCielim, Display, TEXT("Dequeue command: AZmqMultiThreadActor"));
		return NextCommand;
	} else {
		UE_LOG(LogCielim, Display, TEXT("No command received: AZmqMultiThreadActor"));
		return std::nullopt;
	}
}

void AZmqMultiThreadActor::PutQueueData(std::string Data) const
{
	FCircularQueueData NextCommand;
	NextCommand.Query = BSKError();
	this->MultiThreadDataQueue->Responses.Enqueue(NextCommand);
}

void AZmqMultiThreadActor::PutImageQueueData(const TArray64<uint8>& PNGData) const
{
	auto Query = RequestImage();
	Query.payload = PNGData;
	FCircularQueueData NextCommand;
	NextCommand.Query = Query;
	UE_LOG(LogCielim, Display, TEXT("Enqueue image response: AZmqMultiThreadActor"));
	this->MultiThreadDataQueue->Responses.Enqueue(NextCommand);
}

bool AZmqMultiThreadActor::IsThreadPaused() const
{
	if(this->ConnectorThread)
	{
		return this->ConnectorThread->ThreadIsPaused();
	}
	return false;
}
