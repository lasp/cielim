#pragma once

#include "Containers/CircularQueue.h"

#include "CircularQueueData.h"

class CielimCircularQueue
{
public:
	CielimCircularQueue() : Requests(8), Responses(8) {}
	~CielimCircularQueue() = default;

	TCircularQueue<TSharedPtr<FCircularQueueData>> Requests;
	TCircularQueue<TSharedPtr<FCircularQueueData>> Responses;
};
