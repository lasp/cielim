//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FRouter class. The router handles all networking and passes commands to the
//          circular queue to be processed by the scene manager.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/ThreadSafeBool.h"
#include "zmq.hpp"
#include "zmq_addon.hpp"

#include "ZmqConnection/CielimCircularQueue.h"

class CIELIM_API FRouter final : public FRunnable
{
public:
	FRouter(zmq::context_t &ContextPtr, const std::string &Address, CielimCircularQueue &CircularQueue);
	void Shutdown();

	// Returns whether the thread should start (always true)
	virtual bool Init() override;

	// Function executed by spawned thread
	virtual uint32 Run() override;

	// Called when thread is killed
	virtual void Stop() override;

	// Called when spawned thread has finished execution
	virtual void Exit() override;

private:
	// Parse incoming Message and push proper data to ReturnMessage
	void ParseMessage(zmq::multipart_t &Message, zmq::multipart_t &ReturnMessage) const;

	CielimCircularQueue *MultiThreadQueue;

	// Context shared from the game instance
	zmq::context_t *Context;
	zmq::socket_t RouterSocket;

	FRunnableThread *Thread;
	FThreadSafeBool bContinueRun;
};
