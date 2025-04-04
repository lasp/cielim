#pragma once

#include "CoreMinimal.h"
#include "zmq.hpp"

#include "CielimCircularQueue.h"

#include "ZmqMultiThreadActor.generated.h"

UCLASS()
class CIELIM_API UZmqMultiThreadActor : public UObject
{
	GENERATED_BODY()

public:
	void Connect(zmq::context_t& ContextPtr, CielimCircularQueue& CircularQueue);

	TOptional<FCircularQueueData> GetQueueData() const;
	void PutQueueData(std::string Data) const;
	void PutImageQueueData(const TArray64<uint8>& PNGData, const TOptional<FVector2d> CenterOfBrightness) const;

	virtual void PostInitProperties() override;

	// Ensure the thread is shut down
	virtual void BeginDestroy() override;

	CielimCircularQueue* MultiThreadDataQueue;

private:
	zmq::context_t* Context;
};
