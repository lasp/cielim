#pragma once

#include "CielimCircularQueue.h"
#include "Connector.h"

#include "GameFramework/Actor.h"

#include "ZmqMultiThreadActor.generated.h"

UCLASS()
class CIELIM_API AZmqMultiThreadActor : public AActor
{
	GENERATED_BODY()

public:
	
	/** Start a timer in BP to *safely* check for thread updates! */
	UFUNCTION(BlueprintImplementableEvent, BlueprintCallable, Category=Cielim)
	void StartThreadTimerUpdate();
	
	UFUNCTION(BlueprintCallable, Category=Cielim)
	void GetNextMessageFromQueue(FCircularQueueData& NewMessage);
	
	UFUNCTION(BlueprintPure, Category=Cielim)
	bool IsThreadPaused();
	
	UFUNCTION(BlueprintImplementableEvent, BlueprintCallable, Category=Cielim)
	void CielimLog(const FString& Str, FLinearColor Color=FLinearColor::Yellow, float Duration=2);
	
	std::shared_ptr<CielimCircularQueue> MultiThreadDataQueue = nullptr;

//Multi-Threading
public:
	
	//Game Thread
	static int32 ThreadNameCounter;
	std::unique_ptr<Connector> ConnectorThread = nullptr;
	
	void ThreadInit();
	void ThreadShutdown();
	
	// Do not call BP callable functions or do anything that interacts with the game, from a thread
	// that is not the game's main thread
	void ThreadTick();
	
	virtual void BeginPlay() override;
	
	// Ensure the thread is shut down
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
};
