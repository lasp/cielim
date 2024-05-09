#pragma once

#include "CielimCircularQueue.h"
#include "Connector.h"
#include "SimulationDataSource.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"
#include "ZmqMultiThreadActor.generated.h"

UCLASS()
class CIELIM_API AZmqMultiThreadActor : public AActor 
{
	GENERATED_BODY()

public:
	AZmqMultiThreadActor()=default;
	~AZmqMultiThreadActor()=default;
	
	std::optional<FCircularQueueData> GetQueueData() const;
	void PutQueueData(std::string Data) const;
	void PutImageQueueData(const TArray64<uint8>& PNGData) const;
	/** Start a timer in BP to *safely* check for thread updates! */
	UFUNCTION(BlueprintImplementableEvent, BlueprintCallable, Category=Cielim)
	void StartThreadTimerUpdate();
	
	UFUNCTION(BlueprintPure, Category=Cielim)
	bool IsThreadPaused() const;
	
	UFUNCTION(BlueprintImplementableEvent, BlueprintCallable, Category=Cielim)
	void CielimLog(const FString& Str, FLinearColor Color=FLinearColor::Yellow, float Duration=2);

	UWorld* WorldContext = nullptr;
	std::string ConnectionAddress;
	std::shared_ptr<CielimCircularQueue> MultiThreadDataQueue = nullptr;

	//
	// Multi-Threading
	//
	static int32 ThreadNameCounter;
	std::unique_ptr<Connector> ConnectorThread = nullptr;
	
	void ConnectorThreadInit();
	void ConnectorThreadShutdown();
	
	// Do not call BP callable functions or do anything that interacts with the game, from a thread
	// that is not the game's main thread
	void ConnectorThreadTick();
	
	virtual void BeginPlay() override;
	
	// Ensure the thread is shut down
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
};
