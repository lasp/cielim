#pragma once
#include "ThreadBase.h"
#include "Commands.h"
#include "CoreMinimal.h"
#include <zmq.hpp>
#include <zmq_addon.hpp>

class CielimCircularQueue;
class AZmqMultiThreadActor;

class CIELIM_API Connector : public FThreadBase
{
public:
    typedef FThreadBase Super;

	Connector(const FTimespan& ThreadTickRate,
			  const TCHAR* ThreadDescription,
			  AZmqMultiThreadActor* Actor,
			  zmq::context_t& Context,
			  const std::string& Address,
			  std::shared_ptr<CielimCircularQueue> Queue);
	~Connector() = default;

	virtual void CustomTick() override;
	
	bool ThreadInit();
	bool Init() override;
	void ThreadShutdown();
	void SetThreadSafeQueue(const std::shared_ptr<CielimCircularQueue>& Queue);
	
protected:
	//! Because non protected ptr, (not UPROPERTY())
	//! >>> The owning actor of this thread must outlive the thread itself <<<
	//! Owning actor stops this thread on EndPlay, its own destructor starting process
	//! Owning actor freezes game thread until this thread acknowledges it has been stopped
	// AZmqMultiThreadActor* Actor = nullptr;

private:
	void Connect();
	void ParseHandler(zmq::event_flags Event);
	zmq::multipart_t ParseMessage(zmq::multipart_t& Request); 
	CommandType ParseCommand(const std::string& CommandString);

	zmq::socket_t ReplySocket;
    zmq::context_t* Context;
	zmq::active_poller_t ActivePoller;
	std::string Address{"tcp://127.0.0.1:5556"};
	std::shared_ptr<CielimCircularQueue> MultiThreadQueue = nullptr;
};
