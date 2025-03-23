#include "SceneManager.h"

#include "Kismet/GameplayStatics.h"

void USceneManager::Init(const std::string& Address)
{
	this->NetworkDataSource = NewObject<UZmqMultiThreadActor>(this, UZmqMultiThreadActor::StaticClass());
	this->NetworkDataSource->Connect(Address);
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
	if (this->NetworkDataSource != nullptr)
		return this->NetworkDataSource->MultiThreadDataQueue->Requests.Count() != 0;

	return false;
}

void USceneManager::Tick(float DeltaTime)
{
	const TOptional<FCircularQueueData> QueueData = this->NetworkDataSource->GetQueueData();

	if (!QueueData.IsSet())
		return;

	this->Scene->ParseCommand(QueueData.GetValue(), this->NetworkDataSource);
	this->Scene->UpdateScene();
}

TStatId USceneManager::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USceneManager, STATGROUP_Tickables);
}
