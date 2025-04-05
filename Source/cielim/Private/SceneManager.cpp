#include "SceneManager.h"

#include "Kismet/GameplayStatics.h"

#include "CielimLoggingMacros.h"

void USceneManager::Init(zmq::context_t& ContextPtr, CielimCircularQueue& CircularQueue)
{
	this->QueueBridge = NewObject<UQueueBridge>(this, UQueueBridge::StaticClass());
	this->QueueBridge->Connect(ContextPtr, CircularQueue);
}

void USceneManager::InitWorldContext(const UObject *WorldContextObject)
{
	this->WorldContext = GEngine->GetWorldFromContextObjectChecked(WorldContextObject);

	UE_LOG(LogCielim, Display, TEXT("USceneManager : World context initialized."));

	// Find the simulation data source actor
	this->Scene = Cast<ASimulationDataSourceActor>(UGameplayStatics::GetActorOfClass(WorldContext, ASimulationDataSourceActor::StaticClass()));
}

bool USceneManager::IsTickable() const
{
	// If the scene doesn't exist yet, tick won't do anything
	if (!this->Scene)
		return false;

	// Should tick if request queue is not empty
	if (this->QueueBridge != nullptr)
		return this->QueueBridge->MultiThreadDataQueue->Requests.Count() != 0;

	return false;
}

void USceneManager::Tick(float DeltaTime)
{
	const TOptional<FCircularQueueData> QueueData = this->QueueBridge->GetQueueData();

	if (!QueueData.IsSet())
		return;

	this->Scene->ParseCommand(QueueData.GetValue(), this->QueueBridge);
	this->Scene->UpdateScene();
}

TStatId USceneManager::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USceneManager, STATGROUP_Tickables);
}
