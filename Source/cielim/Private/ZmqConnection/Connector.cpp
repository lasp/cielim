#include "ZmqConnection/Connector.h"

#include <string>

#include "ZmqConnection/ZmqMultiThreadActor.h"
#include "CielimLoggingMacros.h"
#include "GenericPlatform/GenericPlatform.h"

/* It is necessary to silence these errors as MSVC will not build the project
   and these warnings are generated in the protobuf headers themselves. */

#if PLATFORM_WINDOWS
#pragma warning(push)
#pragma warning(disable : 4800) // Disable warnings C4800 and C4125
#pragma warning(disable : 4125)
#endif

#include "google/protobuf/util/internal/testdata/oneofs.pb.h"

#if PLATFORM_WINDOWS
#pragma warning(pop)
#endif

Connector::Connector(const FTimespan& ThreadTickRate,
                     const TCHAR* ThreadDescription,
                     AZmqMultiThreadActor* Actor,
                     zmq::context_t& Context,
                     const std::string& Address,
                     std::shared_ptr<CielimCircularQueue> Queue
                     )
	: Super(ThreadTickRate, ThreadDescription)
{
	this->Context = &Context;
	this->Address = Address;
	this->MultiThreadQueue = std::shared_ptr<CielimCircularQueue>(Queue);

	Thread = FRunnableThread::Create(this,
		ThreadDescription,
		128 * 1024,  //allocated memory
		TPri_AboveNormal,
		FPlatformAffinity::GetPoolThreadMask());
}

void Connector::Connect()
{
	this->ReplySocket = zmq::socket_t(*this->Context, zmq::socket_type::rep);
	this->ReplySocket.set(zmq::sockopt::linger, 0); // If ctx.close is called don't try to receive queued messages
	this->ReplySocket.bind(this->Address);
	this->ActivePoller.add(this->ReplySocket, zmq::event_flags::pollin, [&](zmq::event_flags Event)
	{
		zmq::multipart_t Message = zmq::multipart_t();
		Message.recv(this->ReplySocket);
		auto Response = this->ParseMessage(Message);
		Response.send(this->ReplySocket);
	});
}

void Connector::CustomTick()
{
	//Throttle Thread to avoid consuming un-needed resources
	// Set during thread startup, can be modified any time!
	if(this->ThreadTickRate.GetTotalSeconds() > 0)
	{
		this->Wait(this->ThreadTickRate.GetTotalSeconds());
	}

	if(this->ThreadIsPaused())
	{
		UE_LOG(LogCielim, Display, TEXT("Connector::ThreadIsPaused"));
		return;
	}

	if (!this->HasStopped) {
		auto n = this->ActivePoller.wait(std::chrono::milliseconds(1));
	}
}

bool Connector::ThreadInit(){ return true;}

bool Connector::Init()
{
	this->Connect();
	return true;
}

void Connector::ThreadShutdown()
{
	this->ActivePoller.remove(this->ReplySocket);
	this->ReplySocket.unbind(this->Address);
	try {
		this->ReplySocket.close();
	} catch (zmq::error_t e) {
		// I'm dismissing away all thrown errors here.
	}
}

zmq::multipart_t Connector::ParseMessage(zmq::multipart_t& RequestMessage) const
{
	UE_LOG(LogCielim, Display, TEXT("Connector::ParseMessage"));

	zmq::multipart_t Message{};
	std::string Command = RequestMessage.popstr();

	UE_LOG(LogCielim, Display, TEXT("Basilisk command: %hs"), Command.c_str());

	if (Command == "PING")
	{
		Message.pushstr("PONG");
	}
	else if (Command == "SIM_UPDATE")
	{	
		FCircularQueueData Data;
		Data.payload.Emplace<FUpdatePayload>(FUpdatePayload());

		Data.query = CommandType::SIM_UPDATE;
		Data.payload.Get<FUpdatePayload>().message = cielimMessage::CielimMessage();

		// @TODO: fix this message parsing. It's a mad hack!
		Data.payload.Get<FUpdatePayload>().message.ParseFromArray(RequestMessage[2].data(), RequestMessage[2].size() * sizeof(char));


		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue SIM_UPDATE..."));

		bool EnqueueResult = false;
		while(!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(Data);
		}

		Message.pushstr("OK");
	}
	else if (Command == "REQUEST_IMAGE")
	{
		uint32_t CameraID = -1;
		CameraID = std::stoi(RequestMessage.popstr());

		UE_LOG(LogCielim, Display, TEXT("Camera ID: %d"), CameraID);

		// A request is received and is put in the queue to be handled by the main (game) thread
		FCircularQueueData Request;

		Request.query = CommandType::REQUEST_IMAGE;
		Request.payload.Emplace<FImagePayload>(FImagePayload());
		Request.payload.Get<FImagePayload>().shouldReturnImage = (bool) std::stoi(RequestMessage.popstr());

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue REQUEST_IMAGE"));

		bool EnqueueResult = false;
		while(!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(Request);
		}

		// Loop until we get the response from the main (game) thread
		FCircularQueueData Response;

		UE_LOG(LogCielim, Display, TEXT("Waiting for reposnse to REQUEST_IMAGE"));

		bool DequeueResult = false;
		while(!DequeueResult)
		{
			// I can call this directly so the thread blocks on the image return.
			// This assumes that the next item placed in the queue is the image response.
			DequeueResult = this->MultiThreadQueue->Responses.Dequeue(Response);
		}

		UE_LOG(LogCielim, Display, TEXT("Reposnse to REQUEST_IMAGE received"));

		TArray64<uint8> ResponseImage;

		auto* tempPayload = Response.payload.TryGet<FImagePayload>();

		if (tempPayload != nullptr)
		{
			ResponseImage = tempPayload->image_data;
		}

		auto Bytes = sizeof(ResponseImage[0]) * ResponseImage.Num();

		Message.pushmem(ResponseImage.GetData(), Bytes);
		Message.pushtyp(Bytes);

		if (tempPayload != nullptr && tempPayload -> centerOfBrightness.has_value())
		{
			Message.pushtyp<double>(tempPayload -> centerOfBrightness.value().X);
			Message.pushtyp<double>(tempPayload -> centerOfBrightness.value().Y);	
		}
		else 
		{
			Message.pushmem(nullptr, 0);
			Message.pushmem(nullptr, 0);
		}
	}
	else
	{
		Message.pushstr("ERROR");
	}

	return Message;
}

void Connector::SetThreadSafeQueue(const std::shared_ptr<CielimCircularQueue>& Queue)
{
	this->MultiThreadQueue = std::shared_ptr(Queue);
}
