#pragma once

#include "Containers/CircularQueue.h"
#include "UCircularQueueData.h"

class CielimCircularQueue
{
public:
	CielimCircularQueue()
			: Requests(2)
            , Responses(2)
	{ }
	~CielimCircularQueue() = default;
     
	TCircularQueue<FCircularQueueData> Requests;
	TCircularQueue<FCircularQueueData> Responses;
};
