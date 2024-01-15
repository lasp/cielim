#pragma once
#include "ThreadBase.h"
#include "CoreMinimal.h"
#include <zmq.hpp>
#include <zmq_addon.hpp>


class CielimCircularQueue;
class AZmqMultiThreadActor;

enum Command
{
	PING,
	SIM_UPDATE,
	REQUEST_IMAGE,
	ERROR
};

class CIELIM_API Connector : public FThreadBase
{
public:
    typedef FThreadBase Super;

	Connector(const FTimespan& ThreadTickRate,
			  const TCHAR* ThreadDescription,
			  AZmqMultiThreadActor* Actor,
			  std::shared_ptr<CielimCircularQueue> Queue);
	~Connector() = default;

	virtual void CustomTick() override;
	
	bool ThreadInit();
	bool Init() override;
	void ThreadShutdown();
	void SetThreadSafeQueue(std::shared_ptr<CielimCircularQueue> Queue);
	void Connect();
	
protected:
	//! Because non protected ptr, (not UPROPERTY())
	//! >>> The owning actor of this thread must outlive the thread itself <<<
	//! Owning actor stops this thread on EndPlay, its own destructor starting process
	//! Owning actor freezes game thread until this thread acknowledges it has been stopped
	AZmqMultiThreadActor* Actor = nullptr;
    std::shared_ptr<zmq::context_t> Context;
	zmq::context_t context;
    zmq::socket_t ReplySocket;

private:
	void Listen();
	// void ThreadTick();
	zmq::multipart_t ParseMessage(zmq::multipart_t& Request); 
	void RequestImage(uint32_t CameraId);
	Command ParseCommand(std::string str);

	std::shared_ptr<CielimCircularQueue> MultiThreadQueue = nullptr;
	bool IsListenerConnected = false;
};
