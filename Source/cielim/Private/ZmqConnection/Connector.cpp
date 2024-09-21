#include "ZmqConnection/Connector.h"
#include "ZmqConnection/ZmqMultiThreadActor.h"
#include "CielimLoggingMacros.h"
#include "GenericPlatform/GenericPlatform.h"
#include "google/protobuf/util/internal/testdata/oneofs.pb.h"
#include <string>

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
	UE_LOG(LogCielim, Display, TEXT("Connector::CustomTick"));
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

CommandType Connector::ParseCommand(const std::string& CommandString)
{
	static std::unordered_map<std::string, CommandType> const table = {{"PING", CommandType::PING},
																	{"SIM_UPDATE", CommandType::SIM_UPDATE},
																	{"REQUEST_IMAGE", CommandType::REQUEST_IMAGE}};
	
	if (const auto it = table.find(CommandString); it != table.end()) {
		return it->second;
	} 
	return CommandType::ERROR;
}

zmq::multipart_t Connector::ParseMessage(zmq::multipart_t& RequestMessage) 
{
	UE_LOG(LogCielim, Display, TEXT("Connector::ParseMessage"));
	zmq::multipart_t Message;
	
	std::string TmpCommand = RequestMessage.popstr();
	std::string TrimmedCommand = TmpCommand;
	if (TmpCommand.find("REQUEST_IMAGE") != std::string::npos)
	{
		TrimmedCommand = "REQUEST_IMAGE";
	}
	FString PrintCommandString(TrimmedCommand.c_str());
	UE_LOG(LogCielim, Display, TEXT("Basilisk command: %s"), *PrintCommandString);
	switch (this->ParseCommand(TrimmedCommand))
	{
		case CommandType::PING:
			{
				Message.pushstr("PONG");
				break;
			}
		case CommandType::SIM_UPDATE:
			{
				vizProtobufferMessage::VizMessage tempMessage = vizProtobufferMessage::VizMessage();
				// @TODO: fix this message parsing. It's a mad hack!
				tempMessage.ParseFromArray(RequestMessage[2].data(), RequestMessage[2].size()*sizeof(char));
				auto Data = FCircularQueueData();
				auto Command = SimUpdate();
				Command.payload = tempMessage;
				Data.Query = Command;
				bool EnqueueResult = false;
				UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue SIM_UPDATE..."));
				while(!EnqueueResult)
				{
					EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(Data);
				}
				Message.pushstr("OK");
				break;	
			}
		case CommandType::REQUEST_IMAGE:
			{
				// TODO get name from basilisk side and make RequestScreenshot robust to spelling mistakes
				// Set cameraID to message once that information is being sent in the message
				uint32_t CameraID = -1;
				if (TmpCommand.length() > 13) {
					CameraID = std::stoi(TmpCommand.substr(14));
					UE_LOG(LogCielim, Display, TEXT("Camera ID: %d"), CameraID);
				}

				// A request is received and is put in the queue to be handled
				// by the main (game) thread
				auto Request = FCircularQueueData();
				Request.Query = RequestImage();
				bool EnqueueResult = false;
				UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue REQUEST_IMAGE..."));
				while(!EnqueueResult)
				{
					// this->Wait(0.5);
					EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(Request);
				}

				// Loop until we get the response from the main (game) thread
				auto Response = FCircularQueueData();
				bool DequeueResult = false;
				UE_LOG(LogCielim, Display, TEXT("Waiting for reposnse to REQUEST_IMAGE..."));
				while(!DequeueResult)
				{
					// I can call this directly so the thread blocks on the image return.
					// This assumes that the next item placed in the queue is the image response.
					// this->Wait(0.5);
					DequeueResult = this->MultiThreadQueue->Responses.Dequeue(Response);
				}
				UE_LOG(LogCielim, Display, TEXT("Reposnse to REQUEST_IMAGE received..."));
				
				auto ResponseImage = std::get<RequestImage>(Response.Query);
				Message.pushmem(ResponseImage.payload.GetData(), ResponseImage.payload.GetAllocatedSize());
				
				uint64_t Size = ResponseImage.payload.GetAllocatedSize();
				Message.pushmem(&Size, sizeof(uint64_t));
				break;
			}
		default:
			Message.pushstr("ERROR");
			break;
	}

	return Message;
}

void Connector::SetThreadSafeQueue(const std::shared_ptr<CielimCircularQueue>& Queue)
{
	this->MultiThreadQueue = std::shared_ptr(Queue);
}
