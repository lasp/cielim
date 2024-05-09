#include "ZmqConnection/Connector.h"
#include "ZmqConnection/ZmqMultiThreadActor.h"
#include "CielimLoggingMacros.h"
#include "GenericPlatform/GenericPlatform.h"
#include "google/protobuf/util/internal/testdata/oneofs.pb.h"
#include <string>

Connector::Connector(const FTimespan& ThreadTickRate, 
                     const TCHAR* ThreadDescription, 
                     AZmqMultiThreadActor* Actor,
                     std::shared_ptr<CielimCircularQueue> Queue) 
: Super(ThreadTickRate, ThreadDescription) 
, Actor(Actor)
{
	this->MultiThreadQueue = std::shared_ptr<CielimCircularQueue>(Queue);
	this->Context = zmq::context_t();
	this->ReplySocket = zmq::socket_t(this->Context, zmq::socket_type::rep);
	this->ReplySocket.bind("tcp://127.0.0.1:5556");

	const FString UniqueThreadName = "ZMQ Connector ";
	Thread = FRunnableThread::Create(this, 
										*UniqueThreadName, 
										128 * 1024,  //allocated memory
										TPri_AboveNormal, 
										FPlatformAffinity::GetPoolThreadMask());
	this->IsListenerConnected = true;
}

void Connector::Connect()
{
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
	
	//Link to UE World  
	if(!this->Actor) 
	{
		return;
	}
	  
	//This is the connection from a wrapper of OS Threading
	// To UE Game Code.
	// I use an actor for ease of creating a Blueprint 
	// that can create timers and has a tick function that starts enabled
	
	//The thread tick should NOT call any UE code that 
	//1. Creates or destroys objects
	//2. Modifies the game world in any way
	//3. Tries to debug draw anything
	this->Listen();
}

bool Connector::ThreadInit(){ return true;}

bool Connector::Init()
{
	//Any third party C++ to do on init
	// this->ReplySocket = zmq::socket_t(this->context, zmq::socket_type::rep);
	// this->ReplySocket.bind("tcp://localhost:5556");
	this->IsListenerConnected = true;
	return true;
}
	
void Connector::ThreadShutdown()
{
	//Any third party C++ to do on shutdown
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

void Connector::Listen()
{
	UE_LOG(LogCielim, Display, TEXT("Connector::Listen"));
	//Very Long While Loop
	if(IsListenerConnected)
	{
		UE_LOG(LogCielim, Display, TEXT("Listening"));
		if(!this->MultiThreadQueue)
		{
			return;
		}
		
		if(this->ThreadIsPaused())
		{   
			return;
		}
		
		zmq::multipart_t Message = zmq::multipart_t(); 
		if (!Message.recv(this->ReplySocket))
		{
			return;
		}
		auto Response = this->ParseMessage(Message);
		Response.send(this->ReplySocket);
	}
}

void Connector::SetThreadSafeQueue(const std::shared_ptr<CielimCircularQueue>& Queue)
{
	this->MultiThreadQueue = std::shared_ptr(Queue);
}
