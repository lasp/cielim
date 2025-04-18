//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of FRouter.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "Router.h"

#include "CielimLoggingMacros.h"
#include "ZmqConnection/UCircularQueueData.h"

FRouter::FRouter(zmq::context_t &ContextPtr, const std::string &Address, CielimCircularQueue &CircularQueue)
{
	this->Context = &ContextPtr;
	this->RouterSocket = zmq::socket_t(ContextPtr, zmq::socket_type::router);
	this->QueueSocket = zmq::socket_t(ContextPtr, zmq::socket_type::pair);

	this->MultiThreadQueue = &CircularQueue;

	this->bContinueRun = true;

	this->RouterSocket.bind(Address.c_str());
	this->QueueSocket.bind("inproc://OutboundQueueReady");

	UE_LOG(LogCielim, Display, TEXT("Router : Router bound to address: %hs"), Address.c_str());

	this->Thread = FRunnableThread::Create(this, TEXT("CielimRouterThread"));
}

void FRouter::Shutdown()
{
	if (!this->Thread)
		return;

	this->Stop();

	this->Thread->WaitForCompletion();

	delete this->Thread;
	this->Thread = nullptr;
}

bool FRouter::Init() { return true; }

uint32 FRouter::Run()
{
	while (this->bContinueRun)
	{
		zmq::pollitem_t PollItems[2] = {
			{static_cast<void *>(this->RouterSocket), 0, ZMQ_POLLIN, 0},
			{static_cast<void *>(this->QueueSocket), 0, ZMQ_POLLIN, 0},
		};

		// Poll with a timeout of 100ms

		const int NumEvents = zmq::poll(PollItems, 2, std::chrono::milliseconds(100));

		if (NumEvents < 0)
			continue;

		// Check for incoming messages
		if (PollItems[0].revents & ZMQ_POLLIN)
		{
			if (zmq::multipart_t ReceiveMessage; ReceiveMessage.recv(RouterSocket))
			{
				if (ReceiveMessage.size() < 2)
				{
					UE_LOG(LogCielim, Warning, TEXT("Router : Message received was malformed; discarding."));
					continue;
				}

				std::string ID = ReceiveMessage.popstr();

				UE_LOG(LogCielim, Display, TEXT("Router : Message received from client %hs."), ID.c_str());

				bool bUseDelim = false;

				// Message may or may not include empty delimiter depending on client type
				if (ReceiveMessage.front().size() == 0)
				{
					bUseDelim = true;
					ReceiveMessage.pop();
				}

				// Send return message

				zmq::multipart_t ReturnMessage;

				ReturnMessage.addstr(ID);
				if (bUseDelim)
					ReturnMessage.addstr("");

				FCircularQueueData ReturnData;

				ReturnData.ID = ID;
				ReturnData.bUseDelim = bUseDelim;

				ParseMessageAndSend(ReceiveMessage, ReturnMessage, ReturnData);
			}
		}
		// Check for outgoing messages
		if (PollItems[1].revents & ZMQ_POLLIN)
		{
			if (zmq::message_t Signal; QueueSocket.recv(Signal, zmq::recv_flags::none))
			{
				UE_LOG(LogCielim, Display, TEXT("Router : Outbound signal received."));

				if (!MultiThreadQueue->Responses.IsEmpty())
				{
					FCircularQueueData Data;
					MultiThreadQueue->Responses.Dequeue(Data);

					std::string ID = Data.ID;
					bool bUseDelim = Data.bUseDelim;

					UE_LOG(LogCielim, Display, TEXT("Router : Dequeued data for client %hs."), ID.c_str());

					// Send return message

					zmq::multipart_t ReturnMessage;

					ReturnMessage.addstr(ID);
					if (bUseDelim)
						ReturnMessage.addstr("");

					ParseCircularQueueDataAndSend(Data, ReturnMessage);
				}
			}
		}
	}

	return 0;
}

void FRouter::ParseMessageAndSend(zmq::multipart_t &Message, zmq::multipart_t &ReturnMessage,
								  FCircularQueueData &ReturnData)
{
	UE_LOG(LogCielim, Display, TEXT("Router::ParseMessage"));

	const std::string Command = Message.popstr();

	UE_LOG(LogCielim, Display, TEXT("Basilisk command: %hs"), Command.c_str());

	if (Command == "PING")
	{
		ReturnMessage.addstr("PONG");
		ReturnMessage.send(RouterSocket);
	}
	else if (Command == "INIT_SCENE")
	{
		ReturnData.query = CommandType::INIT_SCENE;

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue INIT_SCENE..."));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(ReturnData);
		}

		ReturnMessage.addstr("OK");
		ReturnMessage.send(RouterSocket);
	}
	else if (Command == "SIM_UPDATE")
	{
		ReturnData.query = CommandType::SIM_UPDATE;

		ReturnData.payload.Emplace<FUpdatePayload>(FUpdatePayload());
		ReturnData.payload.Get<FUpdatePayload>().message = FCielimMessage();

		// @TODO: fix this message parsing. It's a mad hack!
		ReturnData.payload.Get<FUpdatePayload>().message.GetMessageModifiable().ParseFromArray(
			Message[2].data(), Message[2].size() * sizeof(char));

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue SIM_UPDATE..."));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(ReturnData);
		}

		ReturnMessage.addstr("OK");
		ReturnMessage.send(RouterSocket);
	}
	else if (Command == "REQUEST_IMAGE")
	{
		ReturnData.query = CommandType::REQUEST_IMAGE;

		uint32_t CameraID = -1;
		CameraID = std::stoi(Message.popstr());

		UE_LOG(LogCielim, Display, TEXT("Camera ID: %d"), CameraID);

		ReturnData.payload.Emplace<FImagePayload>(FImagePayload());
		ReturnData.payload.Get<FImagePayload>().shouldReturnImage = static_cast<bool>(std::stoi(Message.popstr()));

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue REQUEST_IMAGE"));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(ReturnData);
		}
	}
	else
	{
		ReturnMessage.addstr("ERROR");
		ReturnMessage.send(RouterSocket);
	}
}

void FRouter::ParseCircularQueueDataAndSend(FCircularQueueData &Data, zmq::multipart_t &ReturnMessage)
{
	UE_LOG(LogCielim, Display, TEXT("Router::ParseCircularQueue"));

	const CommandType Command = Data.query;

	if (Command == CommandType::REQUEST_IMAGE)
	{
		UE_LOG(LogCielim, Display, TEXT("Response to REQUEST_IMAGE received"));

		TArray64<uint8> ResponseImage;

		auto *TempPayload = Data.payload.TryGet<FImagePayload>();

		if (TempPayload != nullptr)
		{
			ResponseImage = TempPayload->image_data;

			UE_LOG(LogCielim, Display, TEXT("Image data was not NULL"));
		}

		const auto Bytes = sizeof(ResponseImage[0]) * ResponseImage.Num();

		ReturnMessage.addmem(ResponseImage.GetData(), Bytes);
		ReturnMessage.addtyp(Bytes);

		if (TempPayload != nullptr && TempPayload->centerOfBrightness.IsSet())
		{
			ReturnMessage.addtyp<double>(TempPayload->centerOfBrightness.GetValue().X);
			ReturnMessage.addtyp<double>(TempPayload->centerOfBrightness.GetValue().Y);
		}
		else
		{
			ReturnMessage.addmem(nullptr, 0);
			ReturnMessage.addmem(nullptr, 0);
		}
	}
	else
	{
		ReturnMessage.addstr("ERROR");
	}

	ReturnMessage.send(RouterSocket);
}

void FRouter::Stop() { this->bContinueRun = false; }

void FRouter::Exit()
{
	// Do nothing for now (called when Run() ends)
}
