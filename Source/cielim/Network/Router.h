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

#include "CielimCircularQueue.h"

enum class EClientState
{
	Active,
	WaitingResponse
};

/* This struct contains information for each client and is the value in the Clients map.
 * ID and bUseDelim are included here so that they can be accessed during heartbeat polling
 * without incurring a slowdown with the minor cost of increased executable size.
 */
struct FClientInfo
{
	uint8 SceneID;
	TArray<uint8> ID;
	bool bUseDelim;
	EClientState ClientState;
	double LastSeen;
	double DispatchTime;
};

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
	// Parse incoming Message and push proper data to ReturnMessage and send to client
	// Will also enqueue command to inbound queue
	// ReturnMessage and ReturnData are modified
	void ParseMessageAndSend(zmq::multipart_t &Message, zmq::multipart_t &ReturnMessage,
							 const TSharedPtr<FCircularQueueData> &ReturnData);

	// Send outgoing Message to client
	// ReturnMessage is modified
	void ParseCircularQueueDataAndSend(const TSharedPtr<FCircularQueueData> &Data, zmq::multipart_t &ReturnMessage);

	static FString IDConvertToString(const TArray<uint8> &ID);

	CielimCircularQueue *MultiThreadQueue;

	// Context shared from the game instance
	zmq::context_t *Context;
	zmq::socket_t RouterSocket;
	zmq::socket_t RouterMonitor;
	zmq::socket_t QueueSocket;

	FRunnableThread *Thread;
	FThreadSafeBool bContinueRun;

	// Hash table mapping client connections
	TMap<FString, FClientInfo> Clients;
};
