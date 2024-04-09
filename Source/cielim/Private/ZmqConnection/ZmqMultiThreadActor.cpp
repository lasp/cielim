#include "ZmqConnection/ZmqMultiThreadActor.h"
#include <fstream>
#include "../Public/ZmqConnection/Commands.h"


//Static counter for thread creation process, for unique identification of the thread
int32 AZmqMultiThreadActor::ThreadNameCounter = 0;

void AZmqMultiThreadActor::BeginPlay() 
{
	Super::BeginPlay();
	UE_LOG(LogTemp, Warning, TEXT("AZmqMultiThreadActor::BeginPlay"));

	this->ThreadInit();
}

void AZmqMultiThreadActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{   
	//Allows thread to finish current task / tick cycle
	//! Freezing game thread exit process in meantime
	this->ThreadShutdown();
	
	Super::EndPlay(EndPlayReason);
}

void AZmqMultiThreadActor::ThreadInit()
{
	//	Thread-Safe queue to pass data and commands between queue and game thread
	UE_LOG(LogTemp, Warning, TEXT("AZmqMultiThreadActor::ThreadInit"));
	this->MultiThreadDataQueue = std::make_shared<CielimCircularQueue>();
	
	// Thread tick rate to prevent thread from spinning if a fast update is not needed
	FTimespan ThreadWaitTime = FTimespan::FromSeconds(0.01);
	
	FString UniqueThreadName = "ZMQ Connector ";
	UniqueThreadName += FString::FromInt(++ThreadNameCounter);
	
	this->ConnectorThread = std::make_unique<Connector>(ThreadWaitTime,
														*UniqueThreadName,
														this,
														this->MultiThreadDataQueue);
	
	if(ConnectorThread) 
	{ 
		this->ConnectorThread->ThreadInit();
		this->ConnectorThread->Init();
		this->ConnectorThread->SetThreadSafeQueue(this->MultiThreadDataQueue);
		CielimLog("Thread Initialized");
		
		UE_LOG(LogTemp, Warning, TEXT("Thread Initialized"));
	}
	 
	UE_LOG(LogTemp, Warning, TEXT("AZmqMultiThreadActor::ThreadInit end"));
	
	this->StartThreadTimerUpdate();
}

void AZmqMultiThreadActor::ThreadShutdown()
{
	UE_LOG(LogTemp, Warning, TEXT("AZmqMultiThreadActor::ThreadShutdown"));
	if(this->ConnectorThread) 
	{
		this->ConnectorThread->ThreadShutdown();
		this->ConnectorThread->Stop();
		
		/* Wait here until connectorThread is verified as having stopped. This will delay PIE EndPlay or closing of
		 * the game while the thread have a chance to finish */
		while(!this->ConnectorThread->ThreadHasStopped())
		{
			FPlatformProcess::Sleep(0.1);
		}
		
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
		UE_LOG(LogTemp, Warning, TEXT("Dequeue command: AZmqMultiThreadActor"));
		return NextCommand;
	} else {
		UE_LOG(LogTemp, Warning, TEXT("No command received: AZmqMultiThreadActor"));
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
	UE_LOG(LogTemp, Warning, TEXT("Enqueue image response: AZmqMultiThreadActor"));
	this->MultiThreadDataQueue->Responses.Enqueue(NextCommand);
}

bool AZmqMultiThreadActor::IsThreadPaused()
{
	if(this->ConnectorThread)
	{
		return this->ConnectorThread->ThreadIsPaused();
	}
	return false;
}
