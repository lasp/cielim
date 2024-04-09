#include "ZmqConnection/Connector.h"

#include "ZmqConnection/ZmqMultiThreadActor.h"
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
	// this->Context = std::make_shared<zmq::context_t>();
	this->MultiThreadQueue = std::shared_ptr<CielimCircularQueue>(Queue);
	this->context = zmq::context_t();
	this->ReplySocket = zmq::socket_t(this->context, zmq::socket_type::rep);
	this->ReplySocket.bind("tcp://127.0.0.1:5556");

	FString UniqueThreadName = "ZMQ Connector ";
	Thread = FRunnableThread::Create(this, 
										*UniqueThreadName, 
										128 * 1024,  //allocated memory
										TPri_AboveNormal, 
										FPlatformAffinity::GetPoolThreadMask());
	this->IsListenerConnected = true;
}

void Connector::Connect()
{
	// this->ReplySocket.bind("tpc://localhost:5556");
}

void Connector::CustomTick()
{ 
	//Throttle Thread to avoid consuming un-needed resources
	// Set during thread startup, can be modified any time!
	UE_LOG(LogTemp, Warning, TEXT("Connector::CustomTick"));
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
	//4. Simple raw data calculations are best!
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

CommandType Connector::ParseCommand(std::string CommandString)
{
	static std::unordered_map<std::string, CommandType> const table = {{"PING", CommandType::PING},
																	{"SIM_UPDATE", CommandType::SIM_UPDATE},
																	{"REQUEST_IMAGE", CommandType::REQUEST_IMAGE}};
	auto it = table.find(CommandString);
	if (it != table.end()) {
		return it->second;
	} 
	return CommandType::ERROR;
}

zmq::multipart_t Connector::ParseMessage(zmq::multipart_t& RequestMessage) 
{
	UE_LOG(LogTemp, Display, TEXT("Connector::ParseMessage"));
	zmq::multipart_t Message;
	
	std::string TmpCommand = RequestMessage.popstr();
	std::string TrimmedCommand = TmpCommand;
	if (TmpCommand.find("REQUEST_IMAGE") != std::string::npos)
	{
		TrimmedCommand = "REQUEST_IMAGE";
	}
	FString PrintCommandString(TrimmedCommand.c_str());
	UE_LOG(LogTemp, Warning, TEXT("Basilisk command: %s"), *PrintCommandString);
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
				auto data = FCircularQueueData();
				auto command = SimUpdate();
				command.payload = tempMessage;
				data.Query = command;
				bool EnqueueResult = false;
				UE_LOG(LogTemp, Display, TEXT("Waiting to enqueue SIM_UPDATE..."));
				while(!EnqueueResult)
				{
					EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(data);
				}
				Message.pushstr("OK");
				break;	
			}
		case CommandType::REQUEST_IMAGE:
			{
				// TODO get name from basilisk side and make RequestScreenshot robust to spelling mistakes
				auto ImageRequestStartTime = std::chrono::system_clock::now();
				//Set cameraID to message once that information is being sent in the message
				uint32_t CameraID = -1;
				if (TmpCommand.length() > 13) {
					std::string camIDstring = TmpCommand.substr(14);
					CameraID = std::stoi(camIDstring);
				}
				UE_LOG(LogTemp, Warning, TEXT("Camera ID: %d"), CameraID);
				this->RequestImage(CameraID);
				auto ImageTransmitStartTime = std::chrono::system_clock::now();
				Message.pushstr("IMAGE_SUCCESS");
				Message.pushstr("SECOND_MESSAGE");
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
	UE_LOG(LogTemp, Warning, TEXT("Connector::Listen"));
	//Very Long While Loop
	if(IsListenerConnected)
	{
		// CielimLog("Listening");
		UE_LOG(LogTemp, Warning, TEXT("Listening"));

		//! Always check Your Pointers!
		if(!this->MultiThreadQueue)
		{
			return;
		}
		   
		//! Make sure to come all the way out of all function routines with this same check
		//! so as to ensure thread exits as quickly as possible, allowing game thread to finish
		//! See EndPlay for more information. 
		if(this->ThreadIsPaused())
		{   
			//Exit as quickly as possible!
			return;
		}
		
		FCircularQueueData threadData;	
		
		zmq::multipart_t Message = zmq::multipart_t(); 
		if (!Message.recv(this->ReplySocket))
		{
			return;
		}
		auto Response = this->ParseMessage(Message);
		while (this->IsListenerConnected)
		{
			if (Response.send(this->ReplySocket))
			{
				break;
			}
		}
	}
}

void Connector::RequestImage(uint32_t CameraId)
{
	UE_LOG(LogTemp, Warning, TEXT("Request Image"));
}

void Connector::SetThreadSafeQueue(std::shared_ptr<CielimCircularQueue> Queue)
{
	this->MultiThreadQueue = std::shared_ptr<CielimCircularQueue>(Queue);
}
