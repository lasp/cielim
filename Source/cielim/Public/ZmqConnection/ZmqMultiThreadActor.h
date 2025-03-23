#pragma once

#include "CoreMinimal.h"

#include "CielimCircularQueue.h"
#include "SimulationDataSource.h"
#include "Connector.h"

#include "ZmqMultiThreadActor.generated.h"

UCLASS()
class CIELIM_API UZmqMultiThreadActor : public UObject
{
	GENERATED_BODY()

public:
	void Connect(const std::string& Address);
	TOptional<FCircularQueueData> GetQueueData() const;
	void PutQueueData(std::string Data) const;
	void PutImageQueueData(const TArray64<uint8>& PNGData, const TOptional<FVector2d> CenterOfBrightness) const;

	UFUNCTION(BlueprintPure, Category=Cielim)
	bool IsThreadPaused() const;

	std::shared_ptr<CielimCircularQueue> MultiThreadDataQueue = nullptr;

	//
	// Multi-Threading
	//
	static int32 ThreadNameCounter;
	std::unique_ptr<Connector> ConnectorThread = nullptr;

	// Do not call BP callable functions or do anything that interacts with the game, from a thread
	// that is not the game's main thread
	void ConnectorThreadTick();

	virtual void PostInitProperties() override;

	// Ensure the thread is shut down
	virtual void BeginDestroy() override;

private:
	void ConnectorThreadInit();
	void ConnectorThreadShutdown();

	zmq::context_t ZmqContext;
	std::string ConnectionAddress;
};
