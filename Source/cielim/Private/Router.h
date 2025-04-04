#pragma once

#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/ThreadSafeBool.h"
#include "zmq.hpp"
#include "zmq_addon.hpp"

#include "ZmqConnection/CielimCircularQueue.h"

class CIELIM_API FRouter : public FRunnable
{
public:
    FRouter(zmq::context_t& ContextPtr, const std::string& Address, CielimCircularQueue& CircularQueue);
    ~FRouter();

    // Returns whether the thread should start (always true)
    virtual bool Init() override;

    // Function executed by spawned thread
    virtual uint32 Run() override;

    // Called when thread is killed
    virtual void Stop() override;

    // Called when spawned thread has finished execution
    virtual void Exit() override;

private:
	// Parse incoming message and push proper data to reply message
    void ParseMessage(zmq::multipart_t& Message, zmq::multipart_t& ReturnMessage) const;

	CielimCircularQueue* MultiThreadQueue;

    // Context shared from the game instance
    zmq::context_t* Context;
    zmq::socket_t RouterSocket;

    FRunnableThread* Thread;
    FThreadSafeBool bContinueRun;
};
