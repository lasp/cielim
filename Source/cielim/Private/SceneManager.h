#pragma once

#include "CoreMinimal.h"

#include "SimulationDataSourceActor.h"
#include "ZmqConnection/QueueBridge.h"

#include "SceneManager.generated.h"

UCLASS()
class CIELIM_API USceneManager : public UObject, public FTickableGameObject
{
    GENERATED_BODY()

public:
	void Init(zmq::context_t& ContextPtr, CielimCircularQueue& CircularQueue);
	void InitWorldContext(const UObject* WorldContextObject);

	virtual bool IsTickable() const override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

private:
	UPROPERTY()
	UQueueBridge* QueueBridge;

	UPROPERTY()
	UWorld* WorldContext;

	UPROPERTY()
	ASimulationDataSourceActor* Scene;
};
